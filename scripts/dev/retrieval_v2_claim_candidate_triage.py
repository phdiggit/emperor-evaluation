from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from scripts.dev import retrieval_v2_llm_providers as llm_providers


TRIAGE_PROVIDER_NONE = "none"
TRIAGE_PROVIDER_DEEPSEEK = "deepseek"
DEFAULT_MAX_SLICES_PER_OBJECT = 2
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_MAX_TOKENS = 2048
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


class ClaimCandidateTriageError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def candidate_slices(candidates: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in candidates.get("candidate_slices") or [] if isinstance(row, Mapping)]


def prompt_rows(candidates: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in candidate_slices(candidates):
        rows.append(
            {
                "slice_code": text(row.get("slice_code")),
                "object_name": text(row.get("object_name")),
                "document_code": text(row.get("document_code")),
                "source_title": text(row.get("source_title") or row.get("document_title")),
                "text": text(row.get("text")),
            }
        )
    return rows


def build_prompt(candidates: Mapping[str, Any]) -> str:
    identity = candidates.get("task_identity") if isinstance(candidates.get("task_identity"), Mapping) else {}
    target_profile = candidates.get("target_profile") if isinstance(candidates.get("target_profile"), Mapping) else {}
    payload = {
        "emperor_name": text(identity.get("emperor_name") or target_profile.get("primary_name")),
        "rule_code": text(identity.get("rule_code")),
        "candidate_slices": prompt_rows(candidates),
    }
    return "\n".join(
        [
            "你是候选史料切片的低风险分诊器，不是事实裁判。",
            "只按同一 object 内的材料信息密度和重复程度排序，不判断 claim 是否成立、人物归属、正负向或证据强度。",
            "每个 slice_code 必须恰好输出一条 decision：priority 只能为 high、medium、low；duplicate_of 只能是同 object 的另一 slice_code 或空字符串。",
            "reason 只写简短理由。没有把握时 priority=high，duplicate_of 置空。",
            "只返回一个 JSON object：{\"decisions\":[{\"slice_code\":\"...\",\"priority\":\"high\",\"duplicate_of\":\"\",\"reason\":\"...\"}]}。",
            "输入：",
            stable_json(payload),
        ]
    )


def normalize_decisions(payload: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, dict[str, str]], list[str]]:
    row_by_code = {text(row.get("slice_code")): row for row in rows if text(row.get("slice_code"))}
    errors: list[str] = []
    decisions: dict[str, dict[str, str]] = {}
    raw_decisions = payload.get("decisions") if isinstance(payload.get("decisions"), list) else []
    for raw in raw_decisions:
        if not isinstance(raw, Mapping):
            errors.append("decision_not_object")
            continue
        slice_code = text(raw.get("slice_code"))
        priority = text(raw.get("priority")).lower()
        duplicate_of = text(raw.get("duplicate_of"))
        if slice_code not in row_by_code:
            errors.append(f"unknown_slice_code:{slice_code or '<empty>'}")
            continue
        if slice_code in decisions:
            errors.append(f"duplicate_decision:{slice_code}")
            continue
        if priority not in _PRIORITY_RANK:
            errors.append(f"invalid_priority:{slice_code}")
            continue
        if duplicate_of:
            original = row_by_code[slice_code]
            duplicate = row_by_code.get(duplicate_of)
            if duplicate is None or text(duplicate.get("object_name")) != text(original.get("object_name")):
                errors.append(f"invalid_duplicate_of:{slice_code}")
                continue
        decisions[slice_code] = {
            "priority": priority,
            "duplicate_of": duplicate_of,
            "reason": text(raw.get("reason")),
        }
    missing = sorted(set(row_by_code) - set(decisions))
    if missing:
        errors.extend(f"missing_decision:{code}" for code in missing)
    return decisions, errors


def select_prompt_candidates(
    candidates: Mapping[str, Any],
    decisions: Mapping[str, Mapping[str, str]],
    *,
    max_slices_per_object: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if max_slices_per_object < 1:
        raise ClaimCandidateTriageError("max_slices_per_object must be at least 1")
    result = json.loads(stable_json(candidates))
    rows = candidate_slices(result)
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault(text(row.get("object_name")) or "<unknown>", []).append((index, row))
    selected_codes: set[str] = set()
    deferred: list[dict[str, Any]] = []
    selected_by_object: dict[str, list[str]] = {}
    for object_name, object_rows in grouped.items():
        ranked = sorted(
            object_rows,
            key=lambda item: (
                _PRIORITY_RANK[decisions[text(item[1].get("slice_code"))]["priority"]],
                bool(decisions[text(item[1].get("slice_code"))]["duplicate_of"]),
                item[0],
            ),
        )
        chosen = ranked[:max_slices_per_object]
        chosen_codes = [text(row.get("slice_code")) for _, row in chosen]
        selected_by_object[object_name] = chosen_codes
        selected_codes.update(chosen_codes)
        for index, row in ranked[max_slices_per_object:]:
            slice_code = text(row.get("slice_code"))
            decision = decisions[slice_code]
            deferred.append(
                {
                    "slice_code": slice_code,
                    "object_name": object_name,
                    "priority": decision["priority"],
                    "duplicate_of": decision["duplicate_of"],
                    "reason": decision["reason"],
                    "defer_reason": "prompt_budget",
                    "original_index": index,
                }
            )
    result["candidate_slices"] = [row for row in rows if text(row.get("slice_code")) in selected_codes]
    stats = dict(result.get("stats") or {})
    stats["candidate_slices_before_triage"] = len(rows)
    stats["candidate_slices"] = len(result["candidate_slices"])
    stats["candidate_slices_deferred_by_triage"] = len(deferred)
    result["stats"] = stats
    report = {
        "status": "succeeded",
        "mode": "deepseek_prompt_budget",
        "input_slice_count": len(rows),
        "selected_slice_count": len(result["candidate_slices"]),
        "deferred_slice_count": len(deferred),
        "max_slices_per_object": max_slices_per_object,
        "selected_slice_codes_by_object": selected_by_object,
        "deferred_slices": deferred,
        "decisions": [
            {
                "slice_code": text(row.get("slice_code")),
                "object_name": text(row.get("object_name")),
                **dict(decisions[text(row.get("slice_code"))]),
            }
            for row in rows
        ],
    }
    return result, report


def triage_candidates(
    candidates: Mapping[str, Any],
    *,
    provider: str,
    model: str | None,
    api_key_env: str,
    base_url: str | None,
    timeout_seconds: int,
    thinking: str | None,
    max_tokens: int | None,
    max_slices_per_object: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_provider = text(provider).lower() or TRIAGE_PROVIDER_NONE
    if max_slices_per_object < 1:
        raise ClaimCandidateTriageError("max_slices_per_object must be at least 1")
    original = json.loads(stable_json(candidates))
    rows = prompt_rows(original)
    if normalized_provider == TRIAGE_PROVIDER_NONE:
        return original, {"enabled": False, "status": "disabled", "input_slice_count": len(rows), "selected_slice_count": len(rows)}
    if normalized_provider != TRIAGE_PROVIDER_DEEPSEEK:
        raise ClaimCandidateTriageError(f"unsupported candidate triage provider: {provider}")
    if len(rows) <= 1:
        return original, {"enabled": True, "status": "not_needed", "provider": normalized_provider, "input_slice_count": len(rows), "selected_slice_count": len(rows)}
    try:
        response = llm_providers.run_deepseek_chat(
            prompt=build_prompt(original),
            model=model,
            api_key_env=api_key_env,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            thinking=thinking,
            max_tokens=max_tokens,
        )
        payload = response.get("payload") if isinstance(response.get("payload"), Mapping) else {}
        decisions, errors = normalize_decisions(payload, rows)
        if errors:
            return original, {
                "enabled": True,
                "status": "invalid_response_fallback",
                "provider": normalized_provider,
                "input_slice_count": len(rows),
                "selected_slice_count": len(rows),
                "validation_errors": errors,
                "usage": response.get("usage") or {},
                "elapsed_seconds": response.get("elapsed_seconds"),
            }
        selected, report = select_prompt_candidates(original, decisions, max_slices_per_object=max_slices_per_object)
        report.update({"enabled": True, "provider": normalized_provider, "usage": response.get("usage") or {}, "elapsed_seconds": response.get("elapsed_seconds")})
        return selected, report
    except (llm_providers.LlmProviderError, ValueError, TypeError) as exc:
        return original, {
            "enabled": True,
            "status": "provider_failure_fallback",
            "provider": normalized_provider,
            "input_slice_count": len(rows),
            "selected_slice_count": len(rows),
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
