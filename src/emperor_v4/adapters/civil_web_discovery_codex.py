from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
from time import monotonic
from typing import Any, Mapping, Sequence

from emperor_v4.adapters.claim_extractor_codex import (
    _codex_subprocess_environment,
)


PROMPT_POLICY_VERSION = "civil-web-discovery-v3"


def _output_schema(max_candidates: int) -> dict[str, Any]:
    lead = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "measure",
            "delegated_responsibility",
            "policy_or_civil_outcome",
            "source_title",
            "source_url",
            "source_locator",
            "source_excerpt",
            "judge_disposition",
            "judge_reason",
            "independence_key",
            "appointment_importance",
            "appointment_effect",
            "continuity_factor",
        ],
        "properties": {
            key: {"type": "string"}
            for key in (
                "measure",
                "delegated_responsibility",
                "policy_or_civil_outcome",
                "source_title",
                "source_url",
                "source_locator",
                "source_excerpt",
            )
        } | {
            "judge_disposition": {
                "type": "string",
                "enum": ["eligible", "excluded"],
            },
            "judge_reason": {"type": "string"},
            "independence_key": {"type": "string"},
            "appointment_importance": {
                "type": "string",
                "enum": [
                    "nominal_or_light",
                    "real_bounded",
                    "major_affairs",
                    "critical_national_or_long_term",
                ],
            },
            "appointment_effect": {
                "type": "string",
                "enum": [
                    "weak_feedback",
                    "normal_success",
                    "major_success",
                    "exceptional_success",
                ],
            },
            "continuity_factor": {
                "type": "string",
                "enum": ["short_or_one_off", "stable", "long_term_multi_stage"],
            },
        },
    }
    candidate = {
        "type": "object",
        "additionalProperties": False,
        "required": ["person", "person_ref", "leads"],
        "properties": {
            "person": {"type": "string"},
            "person_ref": {"type": "string"},
            "leads": {"type": "array", "maxItems": 3, "items": lead},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates"],
        "properties": {
            "candidates": {
                "type": "array",
                "minItems": max_candidates,
                "maxItems": max_candidates,
                "items": candidate,
            },
        },
    }


def build_civil_web_discovery_prompt(
    *,
    ruler: str,
    ruler_names: Sequence[str],
    evaluation_window: object,
    candidates: Sequence[Mapping[str, Any]],
) -> str:
    payload = {
        "ruler": ruler,
        "ruler_names": list(ruler_names),
        "evaluation_window": evaluation_window,
        "candidates": [dict(row) for row in candidates],
    }
    return (
        "你是 I5B 文官任用与治理成果的网页检索员，只生成待 Judge 的史料候选，不接受事实、不计分。\n"
        "不得读取本地文件或修改任何内容。必须使用网页搜索，按输入顺序逐人处理。\n"
        "每个对象只做一次宽检索，不得换近义词反复搜索：普通文臣使用‘人物名 举措’，"
        "role_families 含 policy 的对象使用‘皇帝名 用人政策’。直接利用搜索结果的 AI 概览理解关键词，"
        "再对识别出的具体举措或政策做史料回源。不得为某个人发明专用规则。\n"
        "结果必须可归责于输入皇帝。跨越 evaluation_window 的长期职责，可以保留窗口内可独立观察的运作与结果；"
        "只有完全发生在窗口外、或无法切分窗口内贡献的政绩才排除。\n"
        "只保留能同时说明受托职责、实际运作以及政策或文治结果的候选；单纯任官、品行赞语、"
        "现代摘要本身均不能作为史源。优先正史本传、实录、政书、诏令奏议原文；现代网页只作线索。\n"
        "source_url 必须直达实际史源页；同一史源有 Wikisource 页面时优先 Wikisource，"
        "source_excerpt 仅摘录支持核心链条的短句；找不到可靠史源则 leads 为空。\n"
        "同一次完成 report-only shadow Judge：只有皇帝归责、受托职责、实际运行、结果和独立性均闭合才标 eligible。"
        "appointment_importance 依次表示轻量、真实有限、重大事务、国家级或长期核心责任；"
        "appointment_effect 依次表示反馈弱、正常成功、重大成功、改变国家格局的顶级成功；"
        "continuity_factor 依次表示一次性、稳定运行、跨阶段长期运行。不得因人物名望抬档。\n"
        "independence_key 必须描述可去重的事实链。不得输出因子数值、得分、正式接受、tier 或排名。"
        "只输出符合 schema 的 JSON。\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def run_codex_civil_web_discovery(
    *,
    ruler: str,
    ruler_names: Sequence[str],
    evaluation_window: object,
    candidates: Sequence[Mapping[str, Any]],
    codex_bin: str,
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not candidates or timeout_seconds <= 0:
        raise ValueError("文官网页检索 provider 输入非法")
    prompt = build_civil_web_discovery_prompt(
        ruler=ruler,
        ruler_names=ruler_names,
        evaluation_window=evaluation_window,
        candidates=candidates,
    )
    started = monotonic()
    with tempfile.TemporaryDirectory(prefix="v4-civil-web-discovery-") as temp_dir:
        root = Path(temp_dir)
        schema_path = root / "output.schema.json"
        output_path = root / "last-message.json"
        schema_path.write_text(
            json.dumps(_output_schema(len(candidates)), ensure_ascii=False),
            encoding="utf-8",
        )
        command = [
            codex_bin,
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--search",
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            cwd=root,
            env=_codex_subprocess_environment(),
            check=False,
        )
        if completed.returncode != 0 or not output_path.is_file():
            diagnostic = sha256(completed.stderr.encode("utf-8")).hexdigest()[:16]
            raise RuntimeError(
                "Codex 文官网页检索失败: "
                f"exit={completed.returncode}; stderr_sha256={diagnostic}"
            )
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Codex 文官网页检索输出必须是 JSON object")
    allowed = {str(row["person_ref"]): str(row["person"]) for row in candidates}
    seen: set[str] = set()
    for row in payload.get("candidates") or ():
        person_ref = str(row.get("person_ref") or "")
        if (
            person_ref not in allowed
            or str(row.get("person") or "") != allowed[person_ref]
            or person_ref in seen
        ):
            raise ValueError("Codex 文官网页检索输出越过候选边界")
        seen.add(person_ref)
    if seen != set(allowed):
        raise ValueError("Codex 文官网页检索未完整处理候选批次")
    audit = {"elapsed_seconds": round(monotonic() - started, 3), "model_call_count": 1}
    return payload, audit
