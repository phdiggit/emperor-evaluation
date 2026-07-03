from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_MAX_RETRIES,
    DEFAULT_PROFILE,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_runtime,
    normalize_workflow_code,
)


DEFAULT_FETCHER = ROOT / "scripts" / "dev" / "i5b_source_pack_fetcher.py"
DEFAULT_SOURCE_PACK_ROOT = ROOT / ".tmp" / "source-packs"
DEFAULT_JOBS_DIR = ROOT / ".tmp" / "source-pack-jobs"
DEFAULT_LOGS_DIR = ROOT / ".tmp" / "source-pack-logs"

DEFAULTS: dict[str, Any] = {
    "include_adjacent": True,
    "pages_per_query": 6,
    "context_chars": 420,
    "max_passages_per_page": 4,
    "request_delay": DEFAULT_REQUEST_DELAY_SECONDS,
    "max_retries": DEFAULT_MAX_RETRIES,
    "retry_backoff": DEFAULT_RETRY_BACKOFF_SECONDS,
    "max_retry_wait": 30,
    "max_consecutive_errors": 8,
    "max_wall_seconds": 3600,
    "max_queries_per_object": 4,
    "no_cache": False,
    "cache_only": False,
    "cache_refresh": False,
    "refresh_pack_pages": False,
}

VALUE_OPTIONS = {
    "pages_per_query": "--pages-per-query",
    "context_chars": "--context-chars",
    "max_passages_per_page": "--max-passages-per-page",
    "request_delay": "--request-delay",
    "max_retries": "--max-retries",
    "retry_backoff": "--retry-backoff",
    "max_retry_wait": "--max-retry-wait",
    "max_consecutive_errors": "--max-consecutive-errors",
    "max_wall_seconds": "--max-wall-seconds",
    "max_queries_per_object": "--max-queries-per-object",
    "max_queries": "--max-queries",
    "cache_dir": "--cache-dir",
    "cache_backend": "--cache-backend",
    "cache_dsn_env": "--cache-dsn-env",
    "cache_schema": "--cache-schema",
}

BOOL_OPTIONS = {
    "include_adjacent": "--include-adjacent",
    "no_cache": "--no-cache",
    "cache_only": "--cache-only",
    "cache_refresh": "--cache-refresh",
    "refresh_pack_pages": "--refresh-pack-pages",
}


@dataclass(frozen=True)
class WorkerConfig:
    python: str
    fetcher_script: Path
    profile: Path
    source_pack_root: Path
    jobs_dir: Path
    logs_dir: Path
    workflow_code: str
    source_scope: str | None
    poll_seconds: float


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"{iso_now()} {message}", flush=True)


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fff]+", "_", value).strip("._-")
    return cleaned or "source_pack"


def read_job(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("job must be a JSON object")
    person = payload.get("person")
    if not isinstance(person, str) or not person.strip():
        raise ValueError("job.person must be a non-empty string")
    return payload


def job_workflow_code(job: dict[str, Any], config: WorkerConfig) -> str:
    return normalize_workflow_code(str(job.get("workflow_code") or config.workflow_code))


def _job_options(job: dict[str, Any]) -> dict[str, Any]:
    return {**DEFAULTS, **{key: value for key, value in job.items() if key in DEFAULTS or key in VALUE_OPTIONS}}


def _job_source_scope(job: dict[str, Any], config: WorkerConfig, workflow_code: str) -> str | None:
    if isinstance(job.get("source_scope"), str) and job["source_scope"].strip():
        return job["source_scope"].strip()
    if config.source_scope:
        return config.source_scope
    runtime = load_source_excerpt_pool_runtime(workflow_code=workflow_code)
    source_scope = runtime.get("source_scope")
    return source_scope if isinstance(source_scope, str) and source_scope.strip() else None


def build_command(job: dict[str, Any], config: WorkerConfig, output_dir: Path) -> list[str]:
    workflow_code = job_workflow_code(job, config)
    profile = Path(str(job.get("profile") or config.profile))
    cmd = [
        config.python,
        str(config.fetcher_script),
        "--profile",
        str(profile),
        "--person",
        str(job["person"]),
        "--workflow-code",
        workflow_code,
        "--output-dir",
        str(output_dir),
    ]
    source_scope = _job_source_scope(job, config, workflow_code)
    if source_scope:
        cmd.extend(["--source-scope", source_scope])
    options = _job_options(job)
    for key, flag in VALUE_OPTIONS.items():
        value = options.get(key)
        if value is not None:
            cmd.extend([flag, str(value)])
    for key, flag in BOOL_OPTIONS.items():
        if options.get(key):
            cmd.append(flag)
    return cmd


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_log_line(handle: Any, message: str) -> None:
    handle.write(f"{iso_now()} {message}\n")
    handle.flush()


def process_job(job_path: Path, config: WorkerConfig) -> None:
    running_path = job_path.with_suffix(job_path.suffix + ".running")
    done_path = job_path.with_suffix(job_path.suffix + ".done")
    failed_path = job_path.with_suffix(job_path.suffix + ".failed")
    try:
        job_path.rename(running_path)
    except FileNotFoundError:
        return

    started_at = iso_now()
    status_path = config.logs_dir / f"{running_path.stem}.status.json"
    try:
        job = read_job(running_path)
        workflow_code = job_workflow_code(job, config)
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        output_name = safe_name(str(job.get("output_name") or f"{job['person']}_{stamp}"))
        output_dir = config.source_pack_root / output_name
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = config.logs_dir / f"{output_name}.log"
        cmd = build_command(job, config, output_dir)
        write_status(
            status_path,
            {
                "status": "running",
                "workflow_code": workflow_code,
                "person": job["person"],
                "job": str(running_path),
                "output_dir": str(output_dir),
                "log_path": str(log_path),
                "started_at": started_at,
                "cmd": cmd,
            },
        )
        log(f"start workflow={workflow_code} job={running_path.name} person={job['person']} output={output_dir}")
        env = {**os.environ, "PYTHONUTF8": "1", "LC_ALL": "C.UTF-8"}
        with log_path.open("w", encoding="utf-8") as handle:
            write_log_line(handle, f"start workflow={workflow_code} job={running_path.name} person={job['person']} output={output_dir}")
            write_log_line(handle, "cmd=" + json.dumps(cmd, ensure_ascii=False))
            result = subprocess.run(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True, env=env, check=False)
            write_log_line(handle, f"finish rc={result.returncode}")
        finished_at = iso_now()
        status_payload = {
            "status": "complete" if result.returncode == 0 else "failed",
            "workflow_code": workflow_code,
            "person": job["person"],
            "returncode": result.returncode,
            "job": str(running_path),
            "output_dir": str(output_dir),
            "log_path": str(log_path),
            "started_at": started_at,
            "finished_at": finished_at,
        }
        write_status(status_path, status_payload)
        if result.returncode == 0:
            shutil.move(str(running_path), str(done_path))
            log(f"complete workflow={workflow_code} job={done_path.name} output={output_dir}")
        else:
            shutil.move(str(running_path), str(failed_path))
            log(f"failed workflow={workflow_code} job={failed_path.name} rc={result.returncode} log={log_path}")
    except Exception as exc:
        write_status(
            status_path,
            {
                "status": "failed",
                "job": str(running_path),
                "error": repr(exc),
                "started_at": started_at,
                "finished_at": iso_now(),
            },
        )
        try:
            shutil.move(str(running_path), str(failed_path))
        except FileNotFoundError:
            pass
        log(f"failed job={running_path.name} error={exc!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume source-pack job JSON files and call the source-pack fetcher.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--fetcher-script", type=Path, default=DEFAULT_FETCHER)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--jobs-dir", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE)
    parser.add_argument("--source-scope", default=None)
    parser.add_argument("--poll-seconds", type=float, default=15)
    return parser


def resolve_config(args: argparse.Namespace) -> WorkerConfig:
    workflow_code = normalize_workflow_code(args.workflow_code)
    runtime = load_source_excerpt_pool_runtime(workflow_code=workflow_code)
    paths = runtime.get("paths") if isinstance(runtime.get("paths"), dict) else {}
    source_scope = args.source_scope or runtime.get("source_scope")
    return WorkerConfig(
        python=str(args.python),
        fetcher_script=args.fetcher_script,
        profile=args.profile or paths.get("query_profile") or DEFAULT_PROFILE,
        source_pack_root=args.source_pack_root or paths.get("source_pack_root") or DEFAULT_SOURCE_PACK_ROOT,
        jobs_dir=args.jobs_dir or paths.get("jobs_dir") or DEFAULT_JOBS_DIR,
        logs_dir=args.logs_dir or paths.get("logs_dir") or DEFAULT_LOGS_DIR,
        workflow_code=workflow_code,
        source_scope=source_scope if isinstance(source_scope, str) and source_scope.strip() else None,
        poll_seconds=args.poll_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    config = resolve_config(build_parser().parse_args(argv))
    for directory in (config.jobs_dir, config.logs_dir, config.source_pack_root):
        directory.mkdir(parents=True, exist_ok=True)
    if not config.fetcher_script.exists():
        raise SystemExit(f"fetcher not found: {config.fetcher_script}")
    log(f"worker started workflow={config.workflow_code} jobs={config.jobs_dir} packs={config.source_pack_root}")
    while True:
        for job_path in sorted(config.jobs_dir.glob("*.json")):
            process_job(job_path, config)
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
