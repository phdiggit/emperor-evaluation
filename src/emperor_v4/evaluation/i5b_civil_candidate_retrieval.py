from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


GRADE_ORDER = {"historic": 0, "top": 1, "important": 2}
SOURCE_PACK_SCHEMA_VERSION = "i5b-civil-browser-source-pack-v1"
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


def build_civil_browser_worklist(
    *,
    ruler: str,
    ruler_names: Sequence[str],
    team_source: Mapping[str, Any],
    current_profiles: Mapping[str, Mapping[str, Any]],
    max_candidate_judge_items: int,
) -> list[dict[str, Any]]:
    people = _civil_candidate_queue(team_source, current_profiles, ruler_names)[
        : max(0, max_candidate_judge_items - 1)
    ]
    return [
        *(
            dict(row) | {"query": f"{row['person']} 举措"}
            for row in people
        ),
        {
            "person": f"{ruler}用人政策",
            "person_ref": f"POLICY-{_fingerprint(ruler)[:16].upper()}",
            "talent_grade": "policy",
            "role_families": ["policy"],
            "query": f"{ruler} 用人政策",
        },
    ]


def run_civil_candidate_retrieval(
    *,
    ruler: str,
    ruler_names: Sequence[str],
    team_source: Mapping[str, Any],
    current_profiles: Mapping[str, Mapping[str, Any]],
    max_candidate_judge_items: int,
    source_pack: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = _civil_candidate_queue(team_source, current_profiles, ruler_names)
    selected = build_civil_browser_worklist(
        ruler=ruler,
        ruler_names=ruler_names,
        team_source=team_source,
        current_profiles=current_profiles,
        max_candidate_judge_items=max_candidate_judge_items,
    )
    selected_people = [row for row in selected if row["talent_grade"] != "policy"]
    if source_pack.get("schema_version") != SOURCE_PACK_SCHEMA_VERSION:
        raise ValueError("浏览器文官候选包版本不支持")
    if source_pack.get("ruler") != ruler:
        raise ValueError("浏览器文官候选包皇帝不匹配")
    payload_candidates = source_pack.get("candidates") or ()
    allowed = {row["person_ref"]: row["person"] for row in selected}
    supplied = {str(row.get("person_ref") or "") for row in payload_candidates}
    if supplied != set(allowed):
        raise ValueError("浏览器文官候选包必须完整且不得越过候选边界")
    materials = []
    eligible = []
    excluded = []
    episodes = []
    for candidate in payload_candidates:
        person_ref = str(candidate.get("person_ref") or "")
        if str(candidate.get("person") or "") != allowed[person_ref]:
            raise ValueError("浏览器文官候选包人物标识不匹配")
        leads = candidate.get("leads") or ()
        if len(leads) > 3:
            raise ValueError("每个文官最多保留三条浏览器候选")
        for lead in leads:
            material_id = "WEB-AD-" + _fingerprint(
                [person_ref, lead["measure"], lead["source_url"]]
            )[:16].upper()
            option_codes = {name: str(lead[name]) for name in FACTOR_VALUES}
            try:
                factor_values = {
                    name: FACTOR_VALUES[name][option]
                    for name, option in option_codes.items()
                }
            except KeyError as exc:
                raise ValueError("浏览器文官候选包因子档位非法") from exc
            factor_values |= {
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
                    "object_ref": person_ref,
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
            if lead["judge_disposition"] == "eligible":
                eligible.append(decision)
                episodes.append(
                    {
                        "episode_id": "EP-WEB-"
                        + _fingerprint(
                            [person_ref, lead["independence_key"], lead["source_url"]]
                        )[:16].upper(),
                        "episode_type": "appointment_delegation_evidence_episode",
                        "episode_status": "shadow_accepted_source_pack",
                        "action": "；".join(
                            (
                                str(lead["delegated_responsibility"]),
                                str(lead["measure"]),
                            )
                        ),
                        "responsibility": str(lead["delegated_responsibility"]),
                        "outcome": [str(lead["policy_or_civil_outcome"])],
                        "consequence": [],
                        "participants": [
                            {
                                "person_ref": person_ref,
                                "role_codes": ["focal_person"],
                                "role_status": "resolved",
                            }
                        ],
                        "assertion_links": [],
                        "lineage": {
                            "unit_ref": material_id,
                            "source_url": str(lead["source_url"]),
                        },
                        "provenance": {
                            "builder": "i5b_civil_browser_source_pack_v1",
                            "input_version": SOURCE_PACK_SCHEMA_VERSION,
                        },
                    }
                )
            else:
                excluded.append(decision)
    return {
        "ruler": ruler,
        "candidate_count": len(candidates),
        "processed_candidate_count": len(selected_people),
        "deferred_candidate_count": len(candidates) - len(selected_people),
        "materials": materials,
        "eligible": eligible,
        "excluded": excluded,
        "episodes": episodes,
    }
