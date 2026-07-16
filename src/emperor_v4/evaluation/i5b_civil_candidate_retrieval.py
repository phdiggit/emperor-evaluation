from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = "i5b-civil-candidate-retrieval-v2"
DISCOVERY_VERSION = "generic-two-hop-web-discovery-v2"
GRADE_ORDER = {"historic": 0, "top": 1, "important": 2}


def _fingerprint(value: object) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _civil_candidate_queue(
    team_source: Mapping[str, Any],
    current_profiles: Mapping[str, Mapping[str, Any]],
    ruler_names: Sequence[str],
) -> list[dict[str, Any]]:
    if not any(str(value).strip() for value in ruler_names):
        raise ValueError("文官网页检索缺少皇帝历史称谓")
    queue = []
    seen: set[str] = set()
    for row in team_source.get("members") or ():
        person_ref = str(row.get("person_ref") or "")
        person = str(row.get("person") or "")
        roles = {str(value) for value in row.get("role_families") or ()}
        current = current_profiles.get(person_ref)
        if not person_ref or not person or current is None or person_ref in seen:
            continue
        grade = str(current.get("talent_grade") or "")
        is_civil = (
            "administration" in roles
            or ("correction" in roles and "military" not in roles)
            or ("decision" in roles and "military" not in roles)
        )
        if not is_civil or grade not in GRADE_ORDER:
            continue
        seen.add(person_ref)
        queue.append(
            {
                "person": person,
                "person_ref": person_ref,
                "talent_grade": grade,
                "role_families": sorted(roles),
            }
        )

    def civil_relevance(row: Mapping[str, Any]) -> tuple[int, int, int]:
        roles = set(row["role_families"])
        return (
            0 if "administration" in roles else 1,
            0 if "correction" in roles else 1,
            0 if "military" not in roles else 1,
        )

    return sorted(
        queue,
        key=lambda row: (
            GRADE_ORDER[str(row["talent_grade"])],
            civil_relevance(row),
            str(row["person"]),
        ),
    )


def _read_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 2, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2 or not isinstance(
        payload.get("entries"), dict
    ):
        raise ValueError("文官网页检索缓存格式非法")
    return payload


def _write_cache(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_civil_candidate_retrieval(
    *,
    ruler: str,
    ruler_names: Sequence[str],
    team_source: Mapping[str, Any],
    current_profiles: Mapping[str, Mapping[str, Any]],
    cache_path: Path,
    max_network_requests: int,
    max_candidate_judge_items: int,
    max_wall_clock_seconds: float,
    completion_reserve_seconds: float,
    provider_policy: Mapping[str, Any],
    discover: Callable[..., tuple[Mapping[str, Any], Mapping[str, Any]]],
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if (
        not ruler.strip()
        or max_network_requests < 2
        or max_candidate_judge_items <= 0
        or max_wall_clock_seconds <= 0
        or completion_reserve_seconds < 0
        or completion_reserve_seconds >= max_wall_clock_seconds
    ):
        raise ValueError("文官网页检索预算非法")
    candidates = _civil_candidate_queue(team_source, current_profiles, ruler_names)
    evaluation_window = team_source.get("window")
    if evaluation_window in (None, "", {}):
        raise ValueError("文官网页检索缺少皇帝评价窗口")
    # 每人严格预留“网页发现 + 史源定位”两跳，不超用皇帝级联网预算。
    batch_size = min(
        len(candidates),
        max_candidate_judge_items,
        max_network_requests // 2,
    )
    selected = candidates[:batch_size]
    input_contract = {
        "schema_version": SCHEMA_VERSION,
        "discovery_version": DISCOVERY_VERSION,
        "ruler": ruler,
        "ruler_names": list(ruler_names),
        "evaluation_window": evaluation_window,
        "candidates": candidates,
        "selected_candidates": selected,
        "max_network_requests": max_network_requests,
        "max_candidate_judge_items": max_candidate_judge_items,
        "provider_policy": dict(provider_policy),
    }
    input_fingerprint = _fingerprint(input_contract)
    cache = _read_cache(cache_path)
    cached = cache["entries"].get(input_fingerprint)
    if cached is not None:
        report = deepcopy(cached)
        initial_audit = dict(report.get("runtime_audit") or {})
        report["runtime_audit"] = {
            "cache_hit": True,
            "network_search_budget_reserved": 0,
            "database_write_count": 0,
            "model_call_count": 0,
            "initial_elapsed_seconds": initial_audit.get("elapsed_seconds"),
            "cached_provider": initial_audit.get("provider") or {},
        }
        return report

    started = clock()
    timeout_seconds = max(
        1,
        int(max_wall_clock_seconds - completion_reserve_seconds),
    )
    provider_error = None
    provider_audit: Mapping[str, Any] = {}
    payload: Mapping[str, Any] = {"candidates": [], "coverage_gaps": []}
    if selected:
        try:
            payload, provider_audit = discover(
                ruler=ruler,
                ruler_names=ruler_names,
                evaluation_window=evaluation_window,
                candidates=selected,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # external agent boundary must fail closed
            provider_audit = {
                "provider": "codex_cli_web_search_failed",
                "model_call_count": 1,
            }
            provider_error = {
                "error_type": type(exc).__name__,
                "message": str(exc),
            }

    by_ref = {str(row["person_ref"]): row for row in selected}
    judge_intake = []
    receipts = []
    for row in payload.get("candidates") or ():
        person_ref = str(row.get("person_ref") or "")
        candidate = by_ref.get(person_ref)
        if candidate is None or str(row.get("person") or "") != candidate["person"]:
            raise ValueError("文官网页检索输出越过候选边界")
        leads = [dict(lead) for lead in row.get("leads") or ()]
        receipts.append(
            {
                "person": candidate["person"],
                "person_ref": person_ref,
                "lead_count": len(leads),
                "measures": [str(lead.get("measure") or "") for lead in leads],
            }
        )
        if leads:
            judge_intake.append(
                {
                    **candidate,
                    "source_leads": leads,
                    "judge_status": "pending",
                    "judge_fields_required": [
                        "ruler_attribution",
                        "delegated_responsibility",
                        "actual_operation",
                        "policy_or_civil_outcome",
                        "independence_and_deduplication",
                        "factor_assignment",
                    ],
                }
            )
    status = (
        "provider_error_deferred"
        if provider_error is not None
        else "judge_required"
        if judge_intake
        else "retrieval_complete_no_hits"
    )
    report = {
        **input_contract,
        "input_fingerprint": input_fingerprint,
        "status": status,
        "candidate_count": len(candidates),
        "processed_candidate_count": len(selected) if provider_error is None else 0,
        "deferred_candidate_count": len(candidates) - (
            len(selected) if provider_error is None else 0
        ),
        "receipts": receipts,
        "judge_intake": judge_intake,
        "coverage_gaps": list(payload.get("coverage_gaps") or ()),
        "provider_error": provider_error,
        "runtime_audit": {
            "cache_hit": False,
            "network_search_budget_reserved": len(selected) * 2,
            "database_write_count": 0,
            "model_call_count": int(provider_audit.get("model_call_count") or 0),
            "provider": dict(provider_audit),
            "elapsed_seconds": round(clock() - started, 3),
        },
        "declarations": {
            "person_specific_query_patch_used": False,
            "two_hop_web_discovery_used": True,
            "strongest_n_frozen": False,
            "formal_fact_acceptance_performed": False,
            "formal_scoring_performed": False,
            "tier": None,
            "ranking": None,
        },
    }
    if provider_error is None:
        cache["entries"][input_fingerprint] = report
        _write_cache(cache_path, cache)
    return report
