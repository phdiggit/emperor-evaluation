from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence


GRADE_ORDER = {"historic": 0, "top": 1, "important": 2}
FACTOR_VALUES = {
    "appointment_importance": {
        "nominal_or_light": 0.6,
        "real_bounded": 1.0,
        "major_affairs": 1.25,
        "critical_national_or_long_term": 1.4,
    },
    "appointment_effect": {
        "weak_feedback": 0.4,
        "normal_success": 1.0,
        "major_success": 1.5,
        "exceptional_success": 1.8,
    },
    "continuity_factor": {
        "short_or_one_off": 0.85,
        "stable": 1.0,
        "long_term_multi_stage": 1.15,
    },
}


def _fingerprint(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _civil_candidate_queue(
    team_source: Mapping[str, Any],
    current_profiles: Mapping[str, Mapping[str, Any]],
    ruler_names: Sequence[str],
) -> list[dict[str, Any]]:
    if not any(str(value).strip() for value in ruler_names):
        raise ValueError("文官检索缺少皇帝称谓")
    queue = []
    for row in team_source.get("members") or ():
        person_ref = str(row.get("person_ref") or "")
        person = str(row.get("person") or "")
        roles = {str(value) for value in row.get("role_families") or ()}
        profile = current_profiles.get(person_ref)
        grade = str((profile or {}).get("talent_grade") or "")
        civil = (
            "administration" in roles
            or ("military" not in roles and bool(roles & {"decision", "correction"}))
        )
        if person_ref and person and civil and grade in GRADE_ORDER:
            queue.append(
                {
                    "person": person,
                    "person_ref": person_ref,
                    "talent_grade": grade,
                    "role_families": sorted(roles),
                }
            )
    return sorted(
        {row["person_ref"]: row for row in queue}.values(),
        key=lambda row: (
            GRADE_ORDER[row["talent_grade"]],
            0 if "administration" in row["role_families"] else 1,
            0 if "correction" in row["role_families"] else 1,
            row["person"],
        ),
    )


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _save_cache(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
    candidates = _civil_candidate_queue(team_source, current_profiles, ruler_names)
    window = team_source.get("window")
    selected = candidates[
        : min(max_candidate_judge_items, max_network_requests // 2)
    ]
    cache_key = _fingerprint(
        {
            "version": "civil-two-hop-shadow-v1",
            "ruler": ruler,
            "ruler_names": list(ruler_names),
            "window": window,
            "candidates": selected,
            "provider": dict(provider_policy),
        }
    )
    cache = _load_cache(cache_path)
    if cache_key in cache:
        result = deepcopy(cache[cache_key])
        first_elapsed = result["runtime"]["elapsed_seconds"]
        result["runtime"] = {
            "cache_hit": True,
            "elapsed_seconds": 0,
            "first_run_elapsed_seconds": first_elapsed,
            "model_call_count": 0,
        }
        return result

    started = clock()
    payload, provider_runtime = discover(
        ruler=ruler,
        ruler_names=ruler_names,
        evaluation_window=window,
        candidates=selected,
        timeout_seconds=max(
            1, int(max_wall_clock_seconds - completion_reserve_seconds)
        ),
    )
    materials = []
    eligible = []
    excluded = []
    for candidate in payload.get("candidates") or ():
        for lead in candidate.get("leads") or ():
            material_id = "WEB-AD-" + _fingerprint(
                [candidate["person_ref"], lead["measure"], lead["source_url"]]
            )[:16].upper()
            option_codes = {name: str(lead[name]) for name in FACTOR_VALUES}
            factor_values = {
                name: FACTOR_VALUES[name][option]
                for name, option in option_codes.items()
            } | {
                "attribution_factor": 1.0,
                "source_factor": 1.1,
                "context_factor": 1.0,
            }
            option_codes |= {
                "attribution_factor": "direct",
                "source_factor": "complete_direct_chain",
                "context_factor": "clear",
            }
            materials.append(
                {
                    "material_id": material_id,
                    "subject": candidate["person"],
                    "object_ref": candidate["person_ref"],
                    "side": "positive",
                    "factor_values": factor_values,
                    "factor_option_codes": option_codes,
                    "fact": "；".join(
                        str(lead[name])
                        for name in (
                            "delegated_responsibility",
                            "measure",
                            "policy_or_civil_outcome",
                        )
                    ),
                    "source_refs": [lead["source_url"]],
                }
            )
            decision = {
                "material_id": material_id,
                "independence_key": lead["independence_key"],
                "judge_reason": lead["judge_reason"],
            }
            (eligible if lead["judge_disposition"] == "eligible" else excluded).append(
                decision
            )
    result = {
        "ruler": ruler,
        "candidate_count": len(candidates),
        "processed_candidate_count": len(selected),
        "deferred_candidate_count": len(candidates) - len(selected),
        "materials": materials,
        "eligible": eligible,
        "excluded": excluded,
        "runtime": {
            "cache_hit": False,
            "elapsed_seconds": round(clock() - started, 3),
            "model_call_count": int(provider_runtime["model_call_count"]),
        },
    }
    cache[cache_key] = result
    _save_cache(cache_path, cache)
    return result
