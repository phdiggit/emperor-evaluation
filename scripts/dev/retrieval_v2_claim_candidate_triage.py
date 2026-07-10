from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from scripts.dev import retrieval_v2_llm_providers as llm_providers


TRIAGE_PROVIDER_NONE = "none"
TRIAGE_PROVIDER_DEEPSEEK = "deepseek"
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_MAX_TOKENS = 2048
DEFAULT_DUPLICATE_TEXT_SIMILARITY = 0.72


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
            "你只能识别同一 object、同一 source document 内近乎重复的同一事件切片，不判断 claim、人物归属、正负向、证据强度或切片优先级。",
            "每个 slice_code 必须恰好输出一条 decision。仅当它和更早出现的另一 slice_code 叙述同一事件、且没有新增时间、行动、结果或人物时，duplicate_of 才可写该更早 slice_code；否则必须为空字符串。",
            "不同 source document、不同事件、不同时间、不同 outcome 或拿不准时一律 duplicate_of 置空。reason 只写简短理由。",
            "只返回一个 JSON object：{\"decisions\":[{\"slice_code\":\"...\",\"duplicate_of\":\"\",\"reason\":\"...\"}]}。",
            "输入：",
            stable_json(payload),
        ]
    )


def normalize_decisions(payload: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, dict[str, str]], list[str]]:
    row_by_code = {text(row.get("slice_code")): row for row in rows if text(row.get("slice_code"))}
    position_by_code = {code: index for index, code in enumerate(row_by_code)}
    errors: list[str] = []
    decisions: dict[str, dict[str, str]] = {}
    raw_decisions = payload.get("decisions") if isinstance(payload.get("decisions"), list) else []
    for raw in raw_decisions:
        if not isinstance(raw, Mapping):
            errors.append("decision_not_object")
            continue
        slice_code = text(raw.get("slice_code"))
        duplicate_of = text(raw.get("duplicate_of"))
        if slice_code not in row_by_code:
            errors.append(f"unknown_slice_code:{slice_code or '<empty>'}")
            continue
        if slice_code in decisions:
            errors.append(f"duplicate_decision:{slice_code}")
            continue
        if duplicate_of:
            original = row_by_code[slice_code]
            duplicate = row_by_code.get(duplicate_of)
            if (
                duplicate is None
                or text(duplicate.get("object_name")) != text(original.get("object_name"))
                or text(duplicate.get("document_code")) != text(original.get("document_code"))
                or position_by_code[duplicate_of] >= position_by_code[slice_code]
            ):
                errors.append(f"invalid_duplicate_of:{slice_code}")
                continue
        decisions[slice_code] = {
            "duplicate_of": duplicate_of,
            "reason": text(raw.get("reason")),
        }
    missing = sorted(set(row_by_code) - set(decisions))
    if missing:
        errors.extend(f"missing_decision:{code}" for code in missing)
    return decisions, errors


def text_similarity(left: str, right: str) -> float:
    normalized_left = "".join(left.split())
    normalized_right = "".join(right.split())
    if normalized_left == normalized_right:
        return 1.0
    if not normalized_left or not normalized_right:
        return 0.0
    width = 3
    left_grams = {normalized_left[index : index + width] for index in range(max(1, len(normalized_left) - width + 1))}
    right_grams = {normalized_right[index : index + width] for index in range(max(1, len(normalized_right) - width + 1))}
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def distinct_event_terms(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_terms = {text(value) for value in left.get("matched_outcome_terms") or [] if text(value)}
    right_terms = {text(value) for value in right.get("matched_outcome_terms") or [] if text(value)}
    return bool(left_terms and right_terms and left_terms != right_terms)


def select_prompt_candidates(
    candidates: Mapping[str, Any],
    decisions: Mapping[str, Mapping[str, str]],
    *,
    duplicate_text_similarity: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not 0 < duplicate_text_similarity <= 1:
        raise ClaimCandidateTriageError("duplicate_text_similarity must be in (0, 1]")
    result = json.loads(stable_json(candidates))
    rows = candidate_slices(result)
    rows_by_code = {text(row.get("slice_code")): row for row in rows}
    selected_codes = set(rows_by_code)
    deferred: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        slice_code = text(row.get("slice_code"))
        decision = decisions[slice_code]
        duplicate_of = decision["duplicate_of"]
        if not duplicate_of:
            continue
        representative = rows_by_code[duplicate_of]
        similarity = text_similarity(text(row.get("text")), text(representative.get("text")))
        if similarity < duplicate_text_similarity or distinct_event_terms(row, representative):
            continue
        selected_codes.discard(slice_code)
        deferred.append(
            {
                "slice_code": slice_code,
                "object_name": text(row.get("object_name")),
                "duplicate_of": duplicate_of,
                "reason": decision["reason"],
                "defer_reason": "verified_near_duplicate",
                "text_similarity": round(similarity, 4),
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
        "mode": "deepseek_duplicate_suggestion",
        "input_slice_count": len(rows),
        "selected_slice_count": len(result["candidate_slices"]),
        "deferred_slice_count": len(deferred),
        "duplicate_text_similarity": duplicate_text_similarity,
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
    duplicate_text_similarity: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_provider = text(provider).lower() or TRIAGE_PROVIDER_NONE
    if not 0 < duplicate_text_similarity <= 1:
        raise ClaimCandidateTriageError("duplicate_text_similarity must be in (0, 1]")
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
        selected, report = select_prompt_candidates(original, decisions, duplicate_text_similarity=duplicate_text_similarity)
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
