from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from emperor_v4.evaluation.i5b_material_budget_scored_shadow import (
    build_i5b_material_budget_shadow,
    render_i5b_material_budget_shadow_markdown,
)


ROOT = Path(__file__).resolve().parents[3]
INPUT_SCHEMA_VERSION = "i5b-source-review-quality-probe-v1"
INPUT_SCHEMA_VERSION_V2 = "i5b-source-review-quality-probe-v2"
SUPPORTED_INPUT_SCHEMA_VERSIONS = {INPUT_SCHEMA_VERSION, INPUT_SCHEMA_VERSION_V2}
RESULT_SCHEMA_VERSION = "i5b-source-review-quality-probe-result-v1"
Q = Decimal("0.000001")
EVENT_RULES = (
    "talent_discovery",
    "appointment_delegation",
    "tolerate_talent",
    "anti_nepotism",
)
TALENT_GRADES = {"ordinary", "usable", "important", "top", "historic"}
AUTHORITY_CONSENSUS = {"weak", "moderate", "strong", "disputed"}
EVIDENCE_STRENGTH = {"none", "weak", "moderate", "strong"}
EVIDENCE_COVERAGE = {"insufficient", "partial", "substantial", "comprehensive"}
RISK_STATUSES = {
    "established",
    "below_floor",
    "reviewed_no_material_risk",
    "insufficient_evidence",
}
RISK_SEVERITIES = {"limited", "material", "serious", "major", "systemic"}
RISK_REACH = {"bounded", "regional", "national", "era_shaping"}
RULE_FACTOR_NAMES = {
    "talent_discovery": (
        "direction_sign",
        "discovery_level",
        "talent_quality_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    ),
    "appointment_delegation": (
        "appointment_importance",
        "appointment_effect",
        "continuity_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    ),
    "tolerate_talent": {
        "positive": (
            "feedback_entry",
            "expression_safety",
            "protection_repair",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "handling_severity",
            "target_fault_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
    "anti_nepotism": {
        "positive": (
            "selection_openness",
            "institutionalization",
            "office_weight",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "favoritism_intensity",
            "office_weight",
            "displacement_harm",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
}


def _load(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"顶层必须是 object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _factor_names(rule_code: str, side: str) -> Sequence[str]:
    configured = RULE_FACTOR_NAMES[rule_code]
    if isinstance(configured, Mapping):
        return configured[side]
    return configured


def _option_value(
    policy: Mapping[str, Any], rule_code: str, factor_name: str, option_code: str
) -> Any:
    if factor_name in {"attribution_factor", "source_factor", "context_factor"}:
        options = policy["evidence_factor"][factor_name]
    else:
        options = policy["rules"][rule_code][factor_name]
    if option_code not in options:
        raise ValueError(
            f"{rule_code}.{factor_name} 不支持档位 {option_code}"
        )
    return options[option_code]


def _passage_catalog(refetch: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if refetch.get("schema_version") != "subject-mention-refetch-result-v1":
        raise ValueError("质量探针只接受人物提及精确回源结果")
    catalog = {}
    for passage in refetch.get("passages") or ():
        passage_ref = str(passage["passage_ref"])
        if (
            passage.get("status") not in {"succeeded", "shadow_source_passage"}
            or passage.get("lineage_status") != "exact_revision_offset_match"
        ):
            continue
        catalog[passage_ref] = passage
    return catalog


def _retrieved_person_identities(
    rules: Mapping[str, Any], retrieved_person_refs: set[str]
) -> dict[str, tuple[str, ...]]:
    team = rules.get("team_building")
    if not isinstance(team, Mapping):
        raise ValueError("质量探针输入缺少 team_building")
    identities: dict[str, tuple[str, ...]] = {}
    for raw_member in team.get("members") or ():
        if not isinstance(raw_member, Mapping):
            continue
        person_ref = str(raw_member.get("person_ref") or "").strip()
        if person_ref not in retrieved_person_refs:
            continue
        forms = {
            str(value).strip()
            for value in (
                raw_member.get("person"),
                *(raw_member.get("surface_forms") or ()),
            )
            if str(value or "").strip() and len(str(value).strip()) >= 2
        }
        if forms:
            identities[person_ref] = tuple(sorted(forms, key=lambda value: (-len(value), value)))
    missing = retrieved_person_refs - identities.keys()
    if missing:
        raise ValueError(
            "检索人物缺少可核正文的姓名或异名: " + ", ".join(sorted(missing))
        )
    return identities


def _require_person_text_match(
    *,
    owner: str,
    passage_refs: Sequence[str],
    person_refs: set[str],
    identities: Mapping[str, Sequence[str]],
    catalog: Mapping[str, Mapping[str, Any]],
) -> None:
    for person_ref in sorted(person_refs):
        forms = identities[person_ref]
        if not any(
            any(form in str(catalog[passage_ref].get("raw_text") or "") for form in forms)
            for passage_ref in passage_refs
        ):
            raise ValueError(f"{owner} 的 passage 正文未命中人物 {person_ref}")
    for passage_ref in passage_refs:
        raw_text = str(catalog[passage_ref].get("raw_text") or "")
        if person_refs and not any(
            form in raw_text
            for person_ref in person_refs
            for form in identities[person_ref]
        ):
            raise ValueError(f"{owner} 引用的 {passage_ref} 正文与声明人物无关")


def _validated_profile_basis(
    raw_member: Mapping[str, Any],
    *,
    passage_refs: Sequence[str],
    catalog: Mapping[str, Mapping[str, Any]],
    require_full_career_scope: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    person_ref = str(raw_member["person_ref"])
    grade = str(raw_member.get("talent_grade") or "")
    if grade not in TALENT_GRADES:
        raise ValueError(f"{person_ref} talent_grade 非法")
    basis = raw_member.get("talent_profile_basis")
    if not isinstance(basis, Mapping):
        raise ValueError(f"{person_ref} 缺少结构化 talent_profile_basis")
    try:
        confidence = float(basis["confidence"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{person_ref} 人才档置信度非法") from exc
    consensus = str(basis.get("authority_consensus") or "")
    performance = str(basis.get("performance_support") or "")
    coverage = str(basis.get("evidence_coverage") or "")
    if not 0 <= confidence <= 1:
        raise ValueError(f"{person_ref} 人才档置信度非法")
    if consensus not in AUTHORITY_CONSENSUS:
        raise ValueError(f"{person_ref} 权威评价共识非法")
    if performance not in EVIDENCE_STRENGTH or coverage not in EVIDENCE_COVERAGE:
        raise ValueError(f"{person_ref} 实绩强度或证据覆盖非法")

    profile_scope = str(basis.get("profile_scope") or "").strip()
    career_coverage = basis.get("career_coverage")
    normalized_career_coverage: dict[str, Any] | None = None
    if require_full_career_scope:
        if profile_scope != "full_career" or not isinstance(career_coverage, Mapping):
            raise ValueError(f"{person_ref} 人才定档缺少完整生涯 profile_scope")
        start_boundary = str(career_coverage.get("start_boundary") or "").strip()
        end_boundary = str(career_coverage.get("end_boundary") or "").strip()
        ruler_contexts = [
            str(value).strip()
            for value in career_coverage.get("ruler_contexts_reviewed") or ()
            if str(value).strip()
        ]
        coverage_status = str(career_coverage.get("coverage_status") or "").strip()
        omissions = [
            str(value).strip()
            for value in career_coverage.get("major_phase_omissions") or ()
            if str(value).strip()
        ]
        if (
            not start_boundary
            or not end_boundary
            or not ruler_contexts
            or coverage_status not in {"partial", "substantial", "complete"}
        ):
            raise ValueError(f"{person_ref} 完整生涯覆盖说明不完整")
        if coverage == "comprehensive" and (
            coverage_status != "complete" or omissions
        ):
            raise ValueError(f"{person_ref} comprehensive 不允许遗漏主要生涯阶段")
        if coverage == "substantial" and coverage_status == "partial":
            raise ValueError(f"{person_ref} substantial 与生涯覆盖状态不一致")
        normalized_career_coverage = {
            "start_boundary": start_boundary,
            "end_boundary": end_boundary,
            "ruler_contexts_reviewed": ruler_contexts,
            "coverage_status": coverage_status,
            "major_phase_omissions": omissions,
        }

    member_refs = set(passage_refs)
    clusters: list[dict[str, Any]] = []
    for index, raw_cluster in enumerate(basis.get("achievement_clusters") or (), start=1):
        if not isinstance(raw_cluster, Mapping):
            raise ValueError(f"{person_ref} achievement_clusters[{index}] 非法")
        cluster_ref = str(raw_cluster.get("cluster_ref") or "").strip()
        summary = str(raw_cluster.get("summary") or "").strip()
        refs = [str(value) for value in raw_cluster.get("passage_refs") or ()]
        if not cluster_ref or not summary or not refs or not set(refs) <= member_refs:
            raise ValueError(f"{person_ref} 成就簇缺少身份、事实或已选 passage")
        clusters.append({"cluster_ref": cluster_ref, "summary": summary, "passage_refs": refs})
    if grade != "ordinary" and not clusters:
        raise ValueError(f"{person_ref} {grade} 人才档缺少成就簇")

    evaluations: list[dict[str, Any]] = []
    for index, raw_evaluation in enumerate(basis.get("authority_evaluations") or (), start=1):
        if not isinstance(raw_evaluation, Mapping):
            raise ValueError(f"{person_ref} authority_evaluations[{index}] 非法")
        evaluation_ref = str(raw_evaluation.get("evaluation_ref") or "").strip()
        summary = str(raw_evaluation.get("summary") or "").strip()
        refs = [str(value) for value in raw_evaluation.get("passage_refs") or ()]
        if not evaluation_ref or not summary or not refs or not set(refs) <= member_refs:
            raise ValueError(f"{person_ref} 权威评价缺少身份、内容或已选 passage")
        evaluations.append(
            {"evaluation_ref": evaluation_ref, "summary": summary, "passage_refs": refs}
        )
    exception_reason = str(basis.get("authority_exception_reason") or "").strip()
    if grade == "historic" and (consensus != "strong" or not evaluations):
        raise ValueError(f"{person_ref} 历史级人才缺少强权威共识和评价史源")
    if grade == "top" and (consensus not in {"moderate", "strong"} or not evaluations):
        raise ValueError(f"{person_ref} 顶级人才缺少权威评价史源")
    if grade == "important" and not evaluations and not exception_reason:
        raise ValueError(f"{person_ref} 重要人才缺少权威评价或例外说明")

    risk = raw_member.get("political_risk")
    if not isinstance(risk, Mapping):
        raise ValueError(f"{person_ref} 缺少结构化 political_risk")
    risk_profile_scope = str(risk.get("profile_scope") or "").strip()
    risk_coverage_ref = str(risk.get("career_coverage_ref") or "").strip()
    if require_full_career_scope and (
        risk_profile_scope != "full_career"
        or risk_coverage_ref != "talent_profile_basis.career_coverage"
    ):
        raise ValueError(f"{person_ref} 政治风险未复用完整生涯覆盖")
    status = str(risk.get("assessment_status") or "")
    severity = risk.get("severity")
    reach = risk.get("historical_reach")
    events = list(risk.get("event_assessments") or ())
    if status not in RISK_STATUSES:
        raise ValueError(f"{person_ref} 政治风险状态非法")
    if status == "established":
        if severity not in RISK_SEVERITIES or reach not in RISK_REACH or not events:
            raise ValueError(f"{person_ref} 已确立政治风险缺少严重度、范围或事件")
        if raw_member.get("negative_talent_severity") != severity or not raw_member.get("negative_talent_class"):
            raise ValueError(f"{person_ref} 政治风险与计分适配字段不一致")
        normalized_events = []
        for index, raw_event in enumerate(events, start=1):
            if not isinstance(raw_event, Mapping):
                raise ValueError(f"{person_ref} risk event[{index}] 非法")
            event_ref = str(raw_event.get("event_ref") or "").strip()
            summary = str(raw_event.get("summary") or "").strip()
            realization = str(raw_event.get("realization") or "")
            responsibility = str(raw_event.get("responsibility") or "").strip()
            refs = [str(value) for value in raw_event.get("passage_refs") or ()]
            if (
                not event_ref
                or not summary
                or realization not in {"attempted", "realized"}
                or not responsibility
                or not refs
                or not set(refs) <= member_refs
            ):
                raise ValueError(f"{person_ref} 政治风险事件依据不完整")
            if severity in {"major", "systemic"} and realization != "realized":
                raise ValueError(f"{person_ref} 未实现风险不得定为 {severity}")
            normalized_events.append(
                {
                    "event_ref": event_ref,
                    "summary": summary,
                    "realization": realization,
                    "responsibility": responsibility,
                    "passage_refs": refs,
                }
            )
        events = normalized_events
    elif severity is not None or reach is not None or events:
        raise ValueError(f"{person_ref} 未确立政治风险不得携带严重度、范围或事件")
    elif raw_member.get("negative_talent_severity") is not None or raw_member.get("negative_talent_class") is not None:
        raise ValueError(f"{person_ref} 未确立政治风险不得进入团队负池")

    return (
        {
            "confidence": confidence,
            "authority_consensus": consensus,
            "performance_support": performance,
            "evidence_coverage": coverage,
            **({"profile_scope": profile_scope} if require_full_career_scope else {}),
            **(
                {"career_coverage": normalized_career_coverage}
                if normalized_career_coverage is not None
                else {}
            ),
            "achievement_clusters": clusters,
            "authority_evaluations": evaluations,
            **({"authority_exception_reason": exception_reason} if exception_reason else {}),
        },
        {
            "assessment_status": status,
            "severity": severity,
            "historical_reach": reach,
            "event_assessments": events,
            **(
                {
                    "profile_scope": risk_profile_scope,
                    "career_coverage_ref": risk_coverage_ref,
                }
                if require_full_career_scope
                else {}
            ),
        },
    )


def _project_material_fact(
    raw_material: Mapping[str, Any],
    *,
    rule_code: str,
    passage_refs: Sequence[str],
    catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    raw_observations = raw_material.get("projection_observations")
    continuity = str(
        (raw_material.get("factor_option_codes") or {}).get(
            "continuity_factor"
        )
        or ""
    )
    if not raw_observations:
        if (
            rule_code == "appointment_delegation"
            and continuity == "long_term_multi_stage"
        ):
            raise ValueError(
                f"{raw_material['material_id']} 声明长期多阶段，但缺少投影事实观察"
            )
        fact = str(raw_material.get("fact") or "").strip()
        if not fact:
            raise ValueError(f"{raw_material['material_id']} 缺少投影事实")
        return fact, []

    declared_refs = set(passage_refs)
    observations: list[dict[str, Any]] = []
    observed_refs: set[str] = set()
    seen_facts: set[str] = set()
    for index, raw_observation in enumerate(raw_observations, start=1):
        if not isinstance(raw_observation, Mapping):
            raise ValueError(
                f"{raw_material['material_id']} projection_observations[{index}] 必须是 object"
            )
        fact = str(raw_observation.get("fact") or "").strip().rstrip("；。")
        refs = [str(value) for value in raw_observation.get("passage_refs") or ()]
        if not fact or not refs:
            raise ValueError(
                f"{raw_material['material_id']} 投影事实观察缺少事实或 passage"
            )
        if fact in seen_facts or any(ref not in catalog for ref in refs):
            raise ValueError(
                f"{raw_material['material_id']} 投影事实观察重复或引用无效 passage"
            )
        if not set(refs) <= declared_refs:
            raise ValueError(
                f"{raw_material['material_id']} 投影事实观察引用未声明 passage"
            )
        seen_facts.add(fact)
        observed_refs.update(refs)
        observations.append({"fact": fact, "passage_refs": refs})
    if observed_refs != declared_refs:
        raise ValueError(
            f"{raw_material['material_id']} 投影事实观察未覆盖全部已选 passage"
        )
    if (
        rule_code == "appointment_delegation"
        and continuity == "long_term_multi_stage"
        and len(observations) < 2
    ):
        raise ValueError(
            f"{raw_material['material_id']} 长期多阶段至少需要两项投影事实观察"
        )
    return "；".join(row["fact"] for row in observations) + "。", observations


def _validated_episode_scope(
    raw_material: Mapping[str, Any], *, rule_code: str, ruler_window: str | None = None
) -> dict[str, str]:
    raw_scope = raw_material.get("episode_scope")
    if not isinstance(raw_scope, Mapping):
        raise ValueError(f"{raw_material['material_id']} 缺少原子 episode_scope")
    required = {"episode_ref", "time_boundary", "action_boundary", "result_boundary"}
    if rule_code == "appointment_delegation":
        required.add("authorization_key")
    if ruler_window is not None:
        required.add("ruler_window")
    scope = {key: str(raw_scope.get(key) or "").strip() for key in required}
    if any(not value for value in scope.values()):
        raise ValueError(f"{raw_material['material_id']} 原子 episode_scope 不完整")
    if ruler_window is not None and scope["ruler_window"] != ruler_window:
        raise ValueError(f"{raw_material['material_id']} episode 超出本皇帝窗口")
    return scope


def _validated_policy_review(
    decision: Mapping[str, Any],
    *,
    catalog: Mapping[str, Mapping[str, Any]],
    material_passage_refs: Mapping[str, set[str]],
) -> dict[str, Any]:
    expected_refs = {
        passage_ref
        for passage_ref, passage in catalog.items()
        if str(passage.get("subject_ref") or "") == str(decision["ruler_ref"])
        and "政策" in str(passage.get("subject_name") or "")
    }
    raw_review = decision.get("policy_review")
    if not isinstance(raw_review, Mapping):
        raise ValueError("v2 decision 缺少 policy_review")
    candidate_reviews: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for index, raw_candidate in enumerate(
        raw_review.get("candidate_reviews") or (), start=1
    ):
        if not isinstance(raw_candidate, Mapping):
            raise ValueError(f"policy_review candidate[{index}] 非法")
        candidate_ref = str(raw_candidate.get("candidate_ref") or "").strip()
        label = str(raw_candidate.get("label") or "").strip()
        disposition = str(raw_candidate.get("disposition") or "").strip()
        reason = str(raw_candidate.get("reason") or "").strip()
        material_ids = [
            str(value) for value in raw_candidate.get("material_ids") or ()
        ]
        if (
            not candidate_ref
            or candidate_ref in seen_candidates
            or not label
            or disposition
            not in {"counted", "supporting", "excluded", "insufficient"}
            or not reason
        ):
            raise ValueError(f"policy_review candidate[{index}] 字段不完整")
        if disposition == "counted" and (
            not material_ids
            or not set(material_ids) <= material_passage_refs.keys()
        ):
            raise ValueError(f"{candidate_ref} counted 未关联有效计分材料")
        if disposition != "counted" and material_ids:
            raise ValueError(f"{candidate_ref} 非计分候选不得关联 material_ids")
        seen_candidates.add(candidate_ref)
        candidate_reviews.append(
            {
                "candidate_ref": candidate_ref,
                "label": label,
                "disposition": disposition,
                "reason": reason,
                "material_ids": material_ids,
            }
        )
    dispositions: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for index, raw_disposition in enumerate(
        raw_review.get("dispositions") or (), start=1
    ):
        if not isinstance(raw_disposition, Mapping):
            raise ValueError(f"policy_review disposition[{index}] 非法")
        review_ref = str(raw_disposition.get("review_ref") or "").strip()
        disposition = str(raw_disposition.get("disposition") or "").strip()
        passage_refs = {
            str(value) for value in raw_disposition.get("passage_refs") or ()
        }
        material_ids = {
            str(value) for value in raw_disposition.get("material_ids") or ()
        }
        reason = str(raw_disposition.get("reason") or "").strip()
        if (
            not review_ref
            or disposition not in {"counted", "supporting", "excluded"}
            or not passage_refs
            or not passage_refs <= expected_refs
            or seen_refs & passage_refs
        ):
            raise ValueError(f"policy_review disposition[{index}] 身份、档位或 passage 非法")
        if disposition == "counted":
            if not material_ids or not material_ids <= material_passage_refs.keys():
                raise ValueError(f"{review_ref} counted 未关联有效计分材料")
            covered_refs = set().union(
                *(material_passage_refs[material_id] for material_id in material_ids)
            )
            if not passage_refs <= covered_refs:
                raise ValueError(f"{review_ref} counted passage 未被关联材料引用")
        elif material_ids:
            raise ValueError(f"{review_ref} 非计分处置不得关联 material_ids")
        if disposition != "counted" and not reason:
            raise ValueError(f"{review_ref} 非计分处置缺少理由")
        seen_refs.update(passage_refs)
        dispositions.append(
            {
                "review_ref": review_ref,
                "disposition": disposition,
                "passage_refs": sorted(passage_refs),
                "material_ids": sorted(material_ids),
                "reason": reason,
            }
        )
    if seen_refs != expected_refs:
        missing = expected_refs - seen_refs
        extra = seen_refs - expected_refs
        raise ValueError(
            "policy_review 未闭合全部政策精确回源 passage"
            f"（缺失 {len(missing)}，越界 {len(extra)}）"
        )
    return {
        "exact_policy_passage_count": len(expected_refs),
        "dispositions": dispositions,
        "candidate_reviews": candidate_reviews,
    }


def build_i5b_source_review_quality_probe(
    decision: Mapping[str, Any],
    *,
    refetch: Mapping[str, Any],
    policy: Mapping[str, Any],
    runtime_dir: Path,
) -> dict[str, Any]:
    input_schema_version = str(decision.get("schema_version") or "")
    if input_schema_version not in SUPPORTED_INPUT_SCHEMA_VERSIONS:
        raise ValueError("I5B 史源审阅质量探针输入版本不支持")
    require_v2_contracts = input_schema_version == INPUT_SCHEMA_VERSION_V2
    catalog = _passage_catalog(refetch)
    rules = decision.get("rules")
    if not isinstance(rules, Mapping):
        raise ValueError("质量探针输入缺少 rules")
    referenced_passages: set[str] = set()
    raw_retrieved_person_refs = [
        str(value) for value in decision.get("retrieved_person_refs") or ()
    ]
    retrieved_person_refs = set(raw_retrieved_person_refs)
    if len(raw_retrieved_person_refs) > 12 or len(retrieved_person_refs) != len(raw_retrieved_person_refs):
        raise ValueError("I5B 单皇帝检索人物必须去重且不超过12人")
    identities = _retrieved_person_identities(rules, retrieved_person_refs)
    identity_gate_required = bool(retrieved_person_refs)
    manifest_rules: dict[str, Any] = {}
    material_passage_refs: dict[str, set[str]] = {}
    empty_source_path = runtime_dir / "empty-projection-source.json"
    _write_json(empty_source_path, {"materials": []})

    for rule_code in EVENT_RULES:
        rule = rules.get(rule_code)
        if not isinstance(rule, Mapping):
            raise ValueError(f"质量探针输入缺少 {rule_code}")
        direct_materials = []
        material_ids: set[str] = set()
        for raw_material in rule.get("materials") or ():
            if not isinstance(raw_material, Mapping):
                raise ValueError(f"{rule_code} material 必须是 object")
            material_id = str(raw_material["material_id"])
            side = str(raw_material["side"])
            if material_id in material_ids or side not in {"positive", "negative"}:
                raise ValueError(f"{rule_code} material id 或 side 非法")
            material_ids.add(material_id)
            passage_refs = [str(value) for value in raw_material.get("passage_refs") or ()]
            if not passage_refs or any(value not in catalog for value in passage_refs):
                raise ValueError(f"{material_id} 引用了不存在或未精确回源的 passage")
            subject_refs = {
                str(value).strip()
                for value in raw_material.get("subject_refs") or ()
                if str(value).strip()
            }
            if identity_gate_required and not subject_refs:
                raise ValueError(f"{material_id} 缺少主体身份 Gate 的 subject_refs")
            object_ref = str(raw_material.get("object_ref") or "").strip()
            if object_ref in retrieved_person_refs and object_ref not in subject_refs:
                raise ValueError(f"{material_id} 未在 subject_refs 声明计分对象 {object_ref}")
            material_person_refs = (subject_refs | {object_ref}) & retrieved_person_refs
            if material_person_refs:
                _require_person_text_match(
                    owner=material_id,
                    passage_refs=passage_refs,
                    person_refs=material_person_refs,
                    identities=identities,
                    catalog=catalog,
                )
            referenced_passages.update(passage_refs)
            material_passage_refs[material_id] = set(passage_refs)
            option_codes = {
                str(key): str(value)
                for key, value in (raw_material.get("factor_option_codes") or {}).items()
            }
            names = _factor_names(rule_code, side)
            if set(option_codes) != set(names):
                raise ValueError(f"{material_id} factor 档位不完整")
            episode_scope = _validated_episode_scope(
                raw_material,
                rule_code=rule_code,
                ruler_window=str(decision["window"]) if require_v2_contracts else None,
            )
            fact, projection_observations = _project_material_fact(
                raw_material,
                rule_code=rule_code,
                passage_refs=passage_refs,
                catalog=catalog,
            )
            direct_materials.append(
                {
                    "material_id": material_id,
                    "subject": str(raw_material["subject"]),
                    "object_ref": str(raw_material.get("object_ref") or raw_material["subject"]),
                    "rule_evidence_unit_ref": str(
                        raw_material.get("event_ref") or material_id
                    ),
                    "side": side,
                    "factor_option_codes": option_codes,
                    "factor_values": {
                        name: _option_value(policy, rule_code, name, option_codes[name])
                        for name in names
                    },
                    "fact": fact,
                    "source_refs": passage_refs,
                    "projection_observations": projection_observations,
                    "projection_coverage": dict(
                        raw_material.get("projection_coverage") or {}
                    ),
                    "episode_scope": episode_scope,
                    **(
                        {"talent_quality_basis": dict(raw_material["talent_quality_basis"])}
                        if raw_material.get("talent_quality_basis")
                        else {}
                    ),
                }
            )
        eligible = rule.get("eligible") or {}
        selected_ids = {
            str(row["material_id"])
            for side in ("positive", "negative")
            for row in eligible.get(side) or ()
        }
        excluded_ids = {
            str(row["material_id"]) for row in rule.get("excluded") or ()
        }
        if selected_ids | excluded_ids != material_ids or selected_ids & excluded_ids:
            raise ValueError(f"{rule_code} 候选处置不闭合")
        baseline_ids = {
            str(value) for value in rule.get("baseline_material_ids") or ()
        }
        if not baseline_ids <= material_ids:
            raise ValueError(f"{rule_code} 丢失 baseline material")
        manifest_rules[rule_code] = {
            "source": str(empty_source_path),
            "direct_materials": direct_materials,
            "eligible": eligible,
            "excluded": list(rule.get("excluded") or ()),
        }

    team = rules.get("team_building")
    if not isinstance(team, Mapping):
        raise ValueError("质量探针输入缺少 team_building")
    members = []
    member_refs: set[str] = set()
    member_selection_keys: set[str] = set()
    for raw_member in team.get("members") or ():
        if not isinstance(raw_member, Mapping):
            raise ValueError("team member 必须是 object")
        passage_refs = [str(value) for value in raw_member.get("passage_refs") or ()]
        if not passage_refs or any(value not in catalog for value in passage_refs):
            raise ValueError("team member 引用了不存在或未精确回源的 passage")
        person_ref = str(raw_member["person_ref"])
        if person_ref in member_refs:
            raise ValueError("team member person_ref 重复")
        member_refs.add(person_ref)
        member_selection_keys.update((person_ref, str(raw_member["person"])))
        if person_ref in retrieved_person_refs:
            _require_person_text_match(
                owner=f"team member {person_ref}",
                passage_refs=passage_refs,
                person_refs={person_ref},
                identities=identities,
                catalog=catalog,
            )
        talent_profile_basis, political_risk = _validated_profile_basis(
            raw_member,
            passage_refs=passage_refs,
            catalog=catalog,
            require_full_career_scope=require_v2_contracts,
        )
        referenced_passages.update(passage_refs)
        members.append(
            {
                "person": str(raw_member["person"]),
                "person_ref": person_ref,
                "profile_ref": f"shadow-quality-probe:{raw_member['person_ref']}",
                "effective_talent_grade": str(raw_member["talent_grade"]),
                "talent_grade_basis": str(raw_member["talent_grade_basis"]),
                "talent_profile_basis": talent_profile_basis,
                "political_risk": political_risk,
                "role_families": list(raw_member.get("role_families") or ()),
                "supporting_unit_refs": passage_refs,
                "negative_talent_class": raw_member.get("negative_talent_class"),
                "negative_talent_severity": raw_member.get("negative_talent_severity"),
            }
        )
    team_source_path = runtime_dir / "team-source.json"
    _write_json(
        team_source_path,
        {"schema_version": "shadow-quality-probe-team-v1", "ruler": decision["ruler"], "members": members},
    )
    positive_members = [str(value) for value in team.get("positive_members") or ()]
    negative_members = [str(value) for value in team.get("negative_members") or ()]
    if len(positive_members) > 8 or len(negative_members) > 3:
        raise ValueError("team_building 冻结选择超过正8负3")
    if not set(positive_members + negative_members) <= member_selection_keys:
        raise ValueError("team_building 冻结选择引用候选池外人物")
    if retrieved_person_refs and not retrieved_person_refs <= member_refs:
        raise ValueError("team_building 候选池未覆盖全部检索人物")
    governance_results: list[dict[str, Any]] = []
    for index, raw_result in enumerate(team.get("governance_results") or (), start=1):
        if isinstance(raw_result, str):
            result = raw_result.strip()
            if not result:
                raise ValueError(f"team_building governance_results[{index}] 为空")
            governance_results.append({"result": result})
            continue
        if not isinstance(raw_result, Mapping):
            raise ValueError(
                f"team_building governance_results[{index}] 必须是字符串或 object"
            )
        result = str(raw_result.get("result") or "").strip()
        if not result:
            raise ValueError(
                f"team_building governance_results[{index}] 缺少 result"
            )
        governance_results.append({**dict(raw_result), "result": result})
    manifest_rules["team_building"] = {
        "source": str(team_source_path),
        "positive_members": positive_members,
        "negative_members": negative_members,
        "functional_complementarity": str(team["functional_complementarity"]),
        "long_term_stability": str(team["long_term_stability"]),
        "remaining_member_judge_reason": str(
            team.get("remaining_member_judge_reason") or "本批未纳入其他成员。"
        ),
        "governance_results": governance_results,
    }
    policy_review = (
        _validated_policy_review(
            decision,
            catalog=catalog,
            material_passage_refs=material_passage_refs,
        )
        if require_v2_contracts
        else None
    )

    manifest = {
        "schema_version": "i5b-material-budget-shadow-manifest-v1",
        "task_code": str(decision["task_code"]),
        "ruler": str(decision["ruler"]),
        "ruler_ref": str(decision["ruler_ref"]),
        "window": str(decision["window"]),
        "policy": str(decision["policy"]),
        "settlement_mode": str(
            decision.get("settlement_mode") or "policy_budget"
        ),
        "rules": manifest_rules,
    }
    material_report = build_i5b_material_budget_shadow(
        runtime_dir / "manifest.json", manifest_payload=manifest
    )
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "shadow_quality_probe_complete",
        "ruler": decision["ruler"],
        "ruler_ref": decision["ruler_ref"],
        "source_refetch_schema_version": refetch["schema_version"],
        "source_passage_count": len(referenced_passages),
        "source_passage_refs": sorted(referenced_passages),
        "material_report": material_report,
        "score_preview": {
            "weighted_raw_signal": material_report["summary"]["weighted_raw_signal"],
            "formal_45_point_score": None,
            "mapping_status": "blocked_pending_cross_ruler_snapshot",
            "reason": "当前链路只到 rule 净信号和 weighted raw signal；单皇帝不得生成45分映射。",
        },
        "quality_declarations": {
            "new_refetch_evidence_only": True,
            "old_historical_chain_used_as_fact_input": False,
            "factor_numeric_values_derived_from_policy": True,
            "human_frozen": False,
            "database_writes": 0,
            "formal_writes": 0,
            "ranking_writes": 0,
            "full_career_profile_ruler_window_separation": require_v2_contracts,
            "exact_policy_passage_disposition_closed": require_v2_contracts,
        },
        **({"policy_review": policy_review} if policy_review is not None else {}),
        "coverage_notes": [str(value) for value in decision.get("coverage_notes") or ()],
    }
    result["report_sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return result


def render_i5b_source_review_calculation_detail(
    result: Mapping[str, Any], policy: Mapping[str, Any]
) -> str:
    report = result["material_report"]
    weights = policy["item_raw_signal"]["rule_weights"]
    lines = [
        f"# {result['ruler']}新回源 I5B 计算详情",
        "",
        "> 本报告只计算各 rule 净信号及 weighted raw signal；45分、tier、排名均为空。",
        "",
        "## 总结果",
        "",
        "| Rule | 正向 | 负向 | 净信号 | 权重 | 加权贡献 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    weighted_parts = []
    for rule in report["rules"]:
        weight = Decimal(str(weights[rule["rule_code"]]))
        net = Decimal(str(rule["rule_raw_net"]))
        contribution = net * weight
        weighted_parts.append(contribution)
        lines.append(
            f"| {rule['rule_label']} (`{rule['rule_code']}`) | "
            f"{rule['positive_signal']} | {rule['negative_signal']} | "
            f"{rule['rule_raw_net']} | {weight} | "
            f"{contribution.quantize(Q, rounding=ROUND_HALF_UP)} |"
        )
    lines.extend(
        [
            "",
            "```text",
            "weighted_raw_signal = "
            + " + ".join(
                f"{rule['rule_raw_net']}×{weights[rule['rule_code']]}"
                for rule in report["rules"]
            ),
            f"                    = {sum(weighted_parts, Decimal('0')).quantize(Q, rounding=ROUND_HALF_UP)}",
            "```",
            "",
        ]
    )
    for rule in report["rules"]:
        lines.extend([f"## {rule['rule_label']}", ""])
        if rule["rule_code"] == "team_building":
            lines.extend(
                [
                    "```text",
                    "positive_pool = "
                    + " + ".join(
                        f"{row['person']}({row['talent_value']})"
                        for row in rule["positive_members"]
                    )
                    + f" = {rule['positive_pool']}",
                    f"positive_signal = {rule['positive_pool']} × {rule['functional_complementarity_factor']} "
                    f"× {rule['long_term_stability_factor']} = {rule['positive_signal']}",
                    f"negative_signal = {rule['negative_pool']}",
                    f"rule_raw_net = {rule['positive_signal']} - {rule['negative_signal']} = {rule['rule_raw_net']}",
                    "```",
                    "",
                ]
            )
            for row in rule["positive_members"]:
                profile_basis = row.get("talent_profile_basis") or {}
                lines.extend(
                    [
                        f"- **{row['person']}**：`{row['talent_grade']}` → `{row['talent_value']}`；"
                        f"依据：{row['talent_grade_basis']}",
                        "  - 定档："
                        f"实绩 `{profile_basis.get('performance_support')}`，"
                        f"权威共识 `{profile_basis.get('authority_consensus')}`，"
                        f"覆盖 `{profile_basis.get('evidence_coverage')}`，"
                        f"置信度 `{profile_basis.get('confidence')}`",
                        "  - 成就簇："
                        + "；".join(
                            str(item.get("summary") or "")
                            for item in profile_basis.get("achievement_clusters") or ()
                        ),
                        "  - 权威评价："
                        + (
                            "；".join(
                                str(item.get("summary") or "")
                                for item in profile_basis.get("authority_evaluations") or ()
                            )
                            or str(profile_basis.get("authority_exception_reason") or "无")
                        ),
                        f"  - passage：{', '.join(f'`{value}`' for value in row['supporting_unit_refs'])}",
                    ]
                )
            for row in rule["negative_members"]:
                risk = row.get("political_risk") or {}
                lines.append(
                    f"- **{row['person']}政治风险**：`{risk.get('assessment_status')}` / "
                    f"`{risk.get('severity')}`；"
                    + "；".join(
                        str(item.get("summary") or "")
                        for item in risk.get("event_assessments") or ()
                    )
                )
            lines.append("")
            continue
        for material in rule.get("settled_materials") or ():
            factor_expression = " × ".join(
                f"{name}={material['factor_option_codes'][name]}→{value}"
                for name, value in material["factor_values"].items()
            )
            lines.extend(
                [
                    f"### {material['subject']} — `{material['material_id']}`",
                    "",
                    f"- 事实：{material['fact']}",
                    f"- Judge：{material['judge_reason']}",
                    f"- 因子：{factor_expression}",
                    f"- 材料值：`clamp(乘积, 0, 4) = {material['material_magnitude']}`",
                    f"- passage：{', '.join(f'`{value}`' for value in material['source_refs'])}",
                    "",
                ]
            )
        supporting = rule.get("supporting_only_materials") or ()
        if supporting:
            lines.extend(["### 通过 Gate 但未进入预算", ""])
            for material in supporting:
                lines.append(
                    f"- `{material['material_id']}`，材料值 `{material.get('material_magnitude')}`："
                    f"{material['judge_reason']}"
                )
            lines.append("")
        lines.extend(
            [
                f"本 rule：`{rule['positive_signal']} - {rule['negative_signal']} = {rule['rule_raw_net']}`。",
                "",
            ]
        )
    lines.extend(["## 覆盖限制", ""])
    lines.extend(f"- {note}" for note in result.get("coverage_notes") or ())
    lines.extend(
        [
            "",
            f"报告指纹：`{result['report_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="I5B exact-source shadow quality probe")
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--refetch-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    decision = _load(args.decision)
    policy_path = Path(str(decision["policy"]))
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    result = build_i5b_source_review_quality_probe(
        decision,
        refetch=_load(args.refetch_result),
        policy=_load(policy_path),
        runtime_dir=args.output_dir,
    )
    _write_json(args.output_dir / "quality-probe.json", result)
    (args.output_dir / "material-budget-shadow.md").write_text(
        render_i5b_material_budget_shadow_markdown(result["material_report"]),
        encoding="utf-8",
        newline="\n",
    )
    (args.output_dir / "calculation-detail.md").write_text(
        render_i5b_source_review_calculation_detail(result, _load(policy_path)),
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "source_passage_count": result["source_passage_count"],
                **result["score_preview"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
