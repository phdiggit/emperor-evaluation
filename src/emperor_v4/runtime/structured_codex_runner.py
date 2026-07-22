from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
from statistics import median
import subprocess
import tempfile
from threading import Event, Lock
from time import monotonic
from typing import Any, Mapping

from emperor_v4.adapters.structured_output_contract import (
    validate_codex_output_schema,
    validate_payload_against_schema,
)


class ModelBatchAnomalyError(TimeoutError):
    """A model subprocess exceeded the adaptive peer-duration envelope."""


MIN_ADAPTIVE_BASELINE_SAMPLES = 3
MIN_ADAPTIVE_TIMEOUT_SECONDS = 45.0


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Best-effort termination without letting inherited pipes defeat timeout."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def _terminate_and_drain(process: subprocess.Popen[str]) -> tuple[str, str]:
    _terminate_process_tree(process)
    try:
        return process.communicate(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        return "", ""


def _environment() -> dict[str, str]:
    allowed = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
        "LOCALAPPDATA", "APPDATA", "USERPROFILE", "CODEX_HOME",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


class StructuredCodexRunner:
    def __init__(
        self,
        *,
        codex_bin: str,
        model: str,
        reasoning_effort: str,
        output_schema_path: Path,
        timeout_seconds: int,
        cwd: Path,
        max_prompt_chars: int = 180_000,
        max_output_bytes: int = 4_000_000,
        deadline_monotonic: float | None = None,
    ) -> None:
        self.codex_bin = codex_bin
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.output_schema_path = output_schema_path.resolve()
        self.timeout_seconds = timeout_seconds
        self.cwd = cwd.resolve()
        self.max_prompt_chars = max_prompt_chars
        self.max_output_bytes = max_output_bytes
        self.deadline_monotonic = deadline_monotonic
        self._successful_calls: list[tuple[int, float]] = []
        self._successful_calls_lock = Lock()
        self._batch_cancelled = Event()
        self._batch_anomaly_lock = Lock()
        self._batch_anomaly_message: str | None = None
        self.schema = json.loads(self.output_schema_path.read_text(encoding="utf-8"))
        validate_codex_output_schema(self.schema, require_all_properties=False)
        self.policy_fingerprint = sha256(
            json.dumps(
                {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "schema_sha256": sha256(self.output_schema_path.read_bytes()).hexdigest(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def _record_success(self, *, prompt_chars: int, elapsed_seconds: float) -> None:
        with self._successful_calls_lock:
            self._successful_calls.append((prompt_chars, elapsed_seconds))
            del self._successful_calls[:-32]

    def _adaptive_timeout_seconds(self, prompt_chars: int) -> float:
        limit, _, _ = self._adaptive_timeout_profile(prompt_chars)
        return limit

    def _adaptive_timeout_profile(
        self, prompt_chars: int
    ) -> tuple[float, float | None, int]:
        with self._successful_calls_lock:
            all_elapsed = [elapsed for _, elapsed in self._successful_calls]
            comparable = [
                elapsed
                for chars, elapsed in self._successful_calls
                if 0.5 <= chars / max(1, prompt_chars) <= 2.0
            ]
        baseline_samples = comparable or all_elapsed
        if not baseline_samples:
            return float(self.timeout_seconds), None, 0
        baseline = float(median(baseline_samples))
        if len(baseline_samples) < MIN_ADAPTIVE_BASELINE_SAMPLES:
            return float(self.timeout_seconds), baseline, len(baseline_samples)
        return (
            min(
                float(self.timeout_seconds),
                max(MIN_ADAPTIVE_TIMEOUT_SECONDS, 2.0 * baseline),
            ),
            baseline,
            len(baseline_samples),
        )

    def _raise_anomaly(
        self,
        process: subprocess.Popen[str],
        *,
        elapsed_seconds: float,
        limit_seconds: float,
        adaptive: bool,
        prompt_chars: int,
        prompt_fingerprint: str,
        baseline_seconds: float | None,
        comparable_count: int,
        prompt_refs: tuple[str, ...],
    ) -> None:
        _, stderr = _terminate_and_drain(process)
        reason = "同类已完成调用中位耗时的两倍" if adaptive else "单批硬超时"
        stderr_tail = " ".join(stderr.splitlines()[-6:])[-800:]
        message = (
            f"结构化模型子进程异常：运行 {elapsed_seconds:.1f}s，超过{reason} "
            f"{limit_seconds:.1f}s；prompt_chars={prompt_chars}，"
            f"prompt_sha256={prompt_fingerprint}，"
            f"baseline_median={baseline_seconds if baseline_seconds is not None else 'none'}，"
            f"comparable_calls={comparable_count}，prompt_refs={list(prompt_refs)}，"
            f"stderr_tail={stderr_tail!r}；已终止进程树并熔断同批调用"
        )
        with self._batch_anomaly_lock:
            if self._batch_anomaly_message is None:
                self._batch_anomaly_message = message
            first_message = self._batch_anomaly_message
            self._batch_cancelled.set()
        raise ModelBatchAnomalyError(first_message)

    def run(self, prompt: str) -> tuple[Mapping[str, Any], dict[str, Any]]:
        if len(prompt) > self.max_prompt_chars:
            raise ValueError("结构化模型 Prompt 超限")
        if self._batch_cancelled.is_set():
            raise ModelBatchAnomalyError(
                self._batch_anomaly_message or "当前模型批次已因异常子进程熔断"
            )
        started = monotonic()
        prompt_fingerprint = sha256(prompt.encode("utf-8")).hexdigest()[:16]
        prompt_refs = tuple(
            dict.fromkeys(
                re.findall(
                    r"(?:BATCH|OUTCOME)-AUTO-[A-F0-9]+|PROMPT-GROUP-[A-F0-9]+|DYNGOV-[^\s]+",
                    prompt,
                )
            )
        )[:8]
        timeout_seconds = self.timeout_seconds
        if self.deadline_monotonic is not None:
            remaining = self.deadline_monotonic - started
            if remaining <= 1:
                raise TimeoutError("结构化模型调用已到皇帝链路硬墙钟")
            timeout_seconds = min(timeout_seconds, max(1, int(remaining)))
        with tempfile.TemporaryDirectory(prefix="emperor-structured-codex-") as directory:
            output = Path(directory) / "output.json"
            command = [
                self.codex_bin,
                "-m",
                self.model,
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "exec",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--skip-git-repo-check",
                "--output-schema",
                str(self.output_schema_path),
                "--output-last-message",
                str(output),
                "-",
            ]
            popen_kwargs: dict[str, Any] = {}
            if os.name == "nt":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(
                command,
                text=True,
                encoding="utf-8",
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                env=_environment(),
                **popen_kwargs,
            )
            submitted = False
            waited_seconds = 0.0
            while True:
                if self._batch_cancelled.is_set():
                    _terminate_and_drain(process)
                    raise ModelBatchAnomalyError(
                        self._batch_anomaly_message
                        or "同批模型子进程异常，当前调用已取消"
                    )
                elapsed_seconds = max(monotonic() - started, waited_seconds)
                adaptive_limit, baseline_seconds, comparable_count = (
                    self._adaptive_timeout_profile(len(prompt))
                )
                limit_seconds = min(float(timeout_seconds), adaptive_limit)
                remaining = limit_seconds - elapsed_seconds
                if remaining <= 0:
                    self._raise_anomaly(
                        process,
                        elapsed_seconds=elapsed_seconds,
                        limit_seconds=limit_seconds,
                        adaptive=adaptive_limit < float(timeout_seconds),
                        prompt_chars=len(prompt),
                        prompt_fingerprint=prompt_fingerprint,
                        baseline_seconds=baseline_seconds,
                        comparable_count=comparable_count,
                        prompt_refs=prompt_refs,
                    )
                wait_slice = min(0.5, remaining)
                try:
                    stdout, stderr = process.communicate(
                        input=prompt if not submitted else None,
                        timeout=wait_slice,
                    )
                    break
                except subprocess.TimeoutExpired:
                    submitted = True
                    waited_seconds += wait_slice
                    continue
            if process.returncode != 0:
                tail = " ".join(stderr.splitlines()[-12:])[-2000:]
                raise RuntimeError(
                    f"结构化模型调用失败: exit={process.returncode}; stderr={tail!r}"
                )
            if not output.is_file() or not 0 < output.stat().st_size <= self.max_output_bytes:
                raise RuntimeError("结构化模型输出文件缺失或大小非法")
            payload = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("结构化模型输出必须是 JSON object")
        validate_payload_against_schema(payload, self.schema)
        elapsed_seconds = monotonic() - started
        self._record_success(
            prompt_chars=len(prompt), elapsed_seconds=elapsed_seconds
        )
        return payload, {
            "elapsed_seconds": round(elapsed_seconds, 3),
            "prompt_chars": len(prompt),
            "output_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            "policy_fingerprint": self.policy_fingerprint,
        }
