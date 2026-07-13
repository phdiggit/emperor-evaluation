from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from collections import defaultdict
from typing import Any, Mapping

from emperor_v4.contracts.boundary import RuleEvidenceMember, RuleEvidenceUnitDraft


RULE_EVIDENCE_SHADOW_POLICY_VERSION = "appointment-delegation-minimum-sufficient-v1"
RULE_EVIDENCE_SHADOW_SCHEMA_VERSION = "rule-evidence-unit-shadow-review-output-v1"
RULE_VERSION = "appointment-delegation-v1-shadow"
AGGREGATION_POLICY_VERSION = "minimum-sufficient-scoring-arc-v1"

APPLICABILITY_VALUES = frozenset({"applicable", "not_applicable", "unresolved"})
DECISION_ARC_FAMILIES = frozenset(
    {
        "appointment_to_mandate",
        "appointment_feedback_correction",
        "authority_trajectory",
        "authority_restoration",
    }
)
MEMBER_ROLES = frozenset(
    {
        "initial_appointment",
        "delegation",
        "execution",
        "outcome",
        "feedback",
        "correction",
        "contraction",
        "termination",
        "restoration",
        "advice",
        "context",
    }
)
READINESS_QUESTIONS = (
    "delegation_quality",
    "supervision_quality",
    "correction_timeliness",
    "net_effect",
)
READINESS_VALUES = frozenset({"ready", "evidence_gap", "not_applicable"})

_FORBIDDEN_KEYS = frozenset(
    {
        "historical_gold",
        "relation_gold",
        "rule_gold",
        "gold_relations",
        "score",
        "scores",
        "judgment",
        "formal_acceptance",
    }
)


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _reject_forbidden(payload: object, path: str = "$") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if normalized in _FORBIDDEN_KEYS or normalized.startswith("gold_"):
                if normalized == "gold_accessed" and value is False:
                    continue
                raise ValueError(f"RuleEvidenceUnit shadow 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_rule_evidence_shadow_worklist(
    scoring_worklist: Mapping[str, Any], scoring_final: Mapping[str, Any]
) -> dict[str, Any]:
    """按评分关系与 scoring-arc-only 连通分量建立 RuleEvidenceUnit 审查输入。"""

    _reject_forbidden(scoring_worklist)
    _reject_forbidden(scoring_final)
    if (
        scoring_final.get("status") != "minimum_sufficient_relation_slice_passed"
        or scoring_final.get("minimum_sufficient_gate_passed") is not True
        or scoring_final.get("task_code") != scoring_worklist.get("task_code")
        or scoring_final.get("unresolved_count") != 0
        or scoring_final.get("formal_relation_count") != 0
        or scoring_final.get("formal_rule_evidence_unit_count") != 0
        or scoring_final.get("database_write_count") != 0
    ):
        raise ValueError("RuleEvidenceUnit shadow 输入未通过评分最小充分 Gate 或越界")

    scoring_tasks = {
        str(task["candidate_code"]): task
        for task in scoring_worklist.get("tasks") or ()
    }
    links = []
    for proposal in scoring_final.get("scoring_relation_proposals") or ():
        code = str((proposal.get("lineage") or {}).get("candidate_code") or "")
        links.append(
            {
                "link_ref": proposal["scoring_relation_proposal_id"],
                "link_kind": "scoring_relation_proposal",
                "candidate_code": code,
                "episode_version_refs": [
                    proposal["from_episode_version_ref"],
                    proposal["to_episode_version_ref"],
                ],
                "relation_family": proposal["relation_family"],
                "relation_direction": proposal["relation_direction"],
                "scope_match": proposal["scope_match"],
                "fine_type": proposal.get("fine_type"),
                "fine_type_status": proposal["fine_type_status"],
            }
        )
    for membership in scoring_final.get("scoring_arc_memberships") or ():
        code = str((membership.get("lineage") or {}).get("candidate_code") or "")
        links.append(
            {
                "link_ref": membership["scoring_arc_membership_id"],
                "link_kind": "scoring_arc_only",
                "candidate_code": code,
                "episode_version_refs": membership["episode_version_refs"],
                "relation_family": membership["relation_family"],
                "relation_direction": membership["relation_direction"],
                "scope_match": membership["scope_match"],
                "unit_member_roles": membership["unit_member_roles"],
            }
        )
    if (
        len(links) != len(scoring_tasks)
        or {link["candidate_code"] for link in links} != set(scoring_tasks)
        or any(not link["candidate_code"] for link in links)
    ):
        raise ValueError("RuleEvidenceUnit shadow links 未完整且唯一覆盖评分候选")

    episodes: dict[str, Mapping[str, Any]] = {}
    adjacency: dict[str, set[str]] = defaultdict(set)
    links_by_episode: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for link in links:
        code = link["candidate_code"]
        task = scoring_tasks[code]
        expected_refs = {
            f"{task['left']['episode_ref']}@v1",
            f"{task['right']['episode_ref']}@v1",
        }
        refs = {str(ref) for ref in link["episode_version_refs"]}
        if refs != expected_refs or len(refs) != 2:
            raise ValueError("RuleEvidenceUnit shadow link endpoints 与候选不一致")
        for side in ("left", "right"):
            episode = task[side]
            ref = f"{episode['episode_ref']}@v1"
            previous = episodes.setdefault(ref, episode)
            if dict(previous) != dict(episode):
                raise ValueError("同一 Episode 在评分候选中载荷不一致")
            links_by_episode[ref].append(link)
        source, target = sorted(refs)
        adjacency[source].add(target)
        adjacency[target].add(source)

    components = []
    visited: set[str] = set()
    for episode_ref in sorted(episodes):
        if episode_ref in visited:
            continue
        pending = [episode_ref]
        component: set[str] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency.get(current, ()))
        visited |= component
        component_links = {
            str(link["link_ref"]): link
            for ref in component
            for link in links_by_episode[ref]
            if set(str(value) for value in link["episode_version_refs"]) <= component
        }
        datasets = {
            str(scoring_tasks[link["candidate_code"]].get("dataset_code") or "")
            for link in component_links.values()
        }
        if len(datasets) != 1 or "" in datasets:
            raise ValueError("RuleEvidenceUnit component 跨 evaluation context")
        basis = {
            "episode_version_refs": sorted(component),
            "link_refs": sorted(component_links),
            "rule_code": "appointment_delegation",
            "rule_version": RULE_VERSION,
            "aggregation_policy_version": AGGREGATION_POLICY_VERSION,
        }
        component_hash = _hash(basis)
        components.append(
            {
                "component_code": f"RUEC-{component_hash[:20].upper()}",
                "evaluation_context": next(iter(datasets)),
                "episode_version_refs": sorted(component),
                "episodes": [episodes[ref] for ref in sorted(component)],
                "links": [component_links[ref] for ref in sorted(component_links)],
                "candidate_codes": sorted(
                    link["candidate_code"] for link in component_links.values()
                ),
            }
        )

    basis = {
        "source_scoring_task_code": scoring_worklist.get("task_code"),
        "source_scoring_worklist_sha256": scoring_worklist.get("worklist_sha256"),
        "source_scoring_final_sha256": _hash(scoring_final),
        "component_codes": [row["component_code"] for row in components],
        "rule_evidence_shadow_policy_version": RULE_EVIDENCE_SHADOW_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "rule_evidence_shadow_worklist_ready",
        "task_code": f"G3C-RUE-SHADOW-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        **basis,
        "output_schema_version": RULE_EVIDENCE_SHADOW_SCHEMA_VERSION,
        "rule_code": "appointment_delegation",
        "rule_version": RULE_VERSION,
        "aggregation_policy_version": AGGREGATION_POLICY_VERSION,
        "component_count": len(components),
        "components": components,
        "review_policy": {
            "applicability_values": sorted(APPLICABILITY_VALUES),
            "rule": "只聚合足以评价皇帝任用、授权、反馈或纠错的评分弧；单纯处分或结局必须排除。",
            "no_judgment_rule": "只声明问题是否具备证据，不输出档位、分数或正式 Judgment。",
        },
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "database_write_count": 0,
    }


def validate_rule_evidence_shadow_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "rule_evidence_shadow_reviews_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("rule_evidence_shadow_policy_version")
        != RULE_EVIDENCE_SHADOW_POLICY_VERSION
        or response.get("output_schema_version")
        != RULE_EVIDENCE_SHADOW_SCHEMA_VERSION
        or not str(response.get("reviewer") or "")
    ):
        raise ValueError("RuleEvidenceUnit shadow response 与 worklist/policy/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_rule_evidence_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
        or response.get("judgment_performed") is not False
        or response.get("scoring_performed") is not False
        or response.get("database_write_count") != 0
    ):
        raise ValueError("RuleEvidenceUnit shadow reviewer 未声明完整隔离与零副作用")

    component_by_code = {
        str(row["component_code"]): row for row in worklist.get("components") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {
        str(row.get("component_code") or ""): row for row in results
    }
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(component_by_code)
    ):
        raise ValueError("RuleEvidenceUnit shadow reviewer 未完整且唯一覆盖 component")

    for code, component in component_by_code.items():
        row = result_by_code[code]
        applicability = row.get("applicability")
        if applicability not in APPLICABILITY_VALUES:
            raise ValueError("RuleEvidenceUnit applicability 非法")
        if not str(row.get("reason") or "").strip():
            raise ValueError("RuleEvidenceUnit shadow review 缺少 reason")
        evidence_refs = tuple(str(ref) for ref in row.get("evidence_assertion_refs") or ())
        allowed_by_episode = {
            f"{episode['episode_ref']}@v1": {
                str(assertion["assertion_ref"])
                for assertion in episode.get("assertions") or ()
            }
            for episode in component["episodes"]
        }
        if (
            not evidence_refs
            or len(evidence_refs) != len(set(evidence_refs))
            or not set(evidence_refs) <= set().union(*allowed_by_episode.values())
            or any(not set(evidence_refs) & refs for refs in allowed_by_episode.values())
        ):
            raise ValueError("RuleEvidenceUnit evidence 必须只引用且覆盖每个 Episode")

        if applicability == "unresolved":
            if any(
                row.get(key) not in (None, {}, [], ())
                for key in (
                    "ruler_ref",
                    "person_ref",
                    "decision_arc_family",
                    "episode_member_roles",
                    "included_link_refs",
                    "question_readiness",
                )
            ):
                raise ValueError("unresolved RuleEvidenceUnit 不得声明聚合语义")
            continue
        if applicability == "not_applicable":
            if any(
                row.get(key) not in (None, {}, [], ())
                for key in (
                    "ruler_ref",
                    "person_ref",
                    "decision_arc_family",
                    "episode_member_roles",
                    "included_link_refs",
                    "question_readiness",
                )
            ):
                raise ValueError("not_applicable 不得生成 RuleEvidenceUnit 成员")
            continue

        if row.get("decision_arc_family") not in DECISION_ARC_FAMILIES:
            raise ValueError("RuleEvidenceUnit decision_arc_family 非法")
        subjects = {
            str(assertion.get("subject") or "")
            for episode in component["episodes"]
            for assertion in episode.get("assertions") or ()
        }
        if str(row.get("ruler_ref") or "") not in subjects:
            raise ValueError("RuleEvidenceUnit ruler_ref 缺少 endpoint Assertion 支持")
        focal_refs = {
            str(episode.get("focal_person_ref") or "")
            for episode in component["episodes"]
        }
        if str(row.get("person_ref") or "") not in focal_refs:
            raise ValueError("RuleEvidenceUnit person_ref 不属于 component focal person")

        roles = {
            str(ref): str(role)
            for ref, role in (row.get("episode_member_roles") or {}).items()
        }
        if set(roles) != set(component["episode_version_refs"]):
            raise ValueError("RuleEvidenceUnit member roles 未完整覆盖 Episode")
        if any(role not in MEMBER_ROLES for role in roles.values()):
            raise ValueError("RuleEvidenceUnit member role 非法")
        allowed_links = {str(link["link_ref"]) for link in component["links"]}
        included_links = tuple(str(ref) for ref in row.get("included_link_refs") or ())
        if (
            not included_links
            or len(included_links) != len(set(included_links))
            or set(included_links) != allowed_links
        ):
            raise ValueError("RuleEvidenceUnit included links 必须完整且唯一覆盖 component")
        readiness = row.get("question_readiness") or {}
        if set(readiness) != set(READINESS_QUESTIONS) or any(
            value not in READINESS_VALUES for value in readiness.values()
        ):
            raise ValueError("RuleEvidenceUnit question readiness 不完整或非法")
    return result_by_code


def materialize_rule_evidence_shadow(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Any]:
    """构造 proposal-only RuleEvidenceUnitDraft，并审计重复消费与 lineage。"""

    rows = validate_rule_evidence_shadow_response(worklist, response)
    component_by_code = {
        str(row["component_code"]): row for row in worklist.get("components") or ()
    }
    units = []
    exclusions = []
    unresolved = []
    episode_owners: dict[str, str] = {}
    duplicate_episode_refs: set[str] = set()
    for code in sorted(component_by_code):
        component = component_by_code[code]
        row = rows[code]
        if row["applicability"] == "unresolved":
            unresolved.append({"component_code": code, "reason": row["reason"]})
            continue
        if row["applicability"] == "not_applicable":
            exclusions.append({"component_code": code, "reason": row["reason"]})
            continue
        members = [
            RuleEvidenceMember(ref, "episode", row["episode_member_roles"][ref])
            for ref in sorted(component["episode_version_refs"])
        ]
        link_by_ref = {str(link["link_ref"]): link for link in component["links"]}
        relation_refs = [
            ref
            for ref in row["included_link_refs"]
            if link_by_ref[ref]["link_kind"] == "scoring_relation_proposal"
        ]
        members.extend(
            RuleEvidenceMember(ref, "relation", "scoring_link")
            for ref in sorted(relation_refs)
        )
        semantic = {
            "rule_code": worklist["rule_code"],
            "rule_version": worklist["rule_version"],
            "aggregation_policy_version": worklist["aggregation_policy_version"],
            "evaluation_context": component["evaluation_context"],
            "ruler_ref": row["ruler_ref"],
            "person_ref": row["person_ref"],
            "decision_arc_family": row["decision_arc_family"],
            "members": [
                {
                    "member_ref": member.member_ref,
                    "member_type": member.member_type,
                    "member_role": member.member_role,
                }
                for member in members
            ],
        }
        fingerprint = _hash(semantic)
        draft = RuleEvidenceUnitDraft(
            unit_code=f"RUE-{fingerprint[:20].upper()}",
            rule_code=worklist["rule_code"],
            rule_version=worklist["rule_version"],
            aggregation_policy_version=worklist["aggregation_policy_version"],
            evaluation_context=component["evaluation_context"],
            semantic_fingerprint=fingerprint,
            semantic_version=1,
            evidence_version=1,
            members=tuple(members),
            aggregation_reason=row["reason"],
            status="draft",
            lineage={
                "component_code": code,
                "source_scoring_task_code": str(worklist["source_scoring_task_code"]),
            },
            provenance={
                "policy_version": RULE_EVIDENCE_SHADOW_POLICY_VERSION,
                "reviewer": str(response["reviewer"]),
            },
        )
        for episode_ref in draft.episode_refs:
            previous = episode_owners.setdefault(episode_ref, draft.unit_code)
            if previous != draft.unit_code:
                duplicate_episode_refs.add(episode_ref)
        unit = asdict(draft)
        unit.update(
            {
                "ruler_ref": row["ruler_ref"],
                "person_ref": row["person_ref"],
                "decision_arc_family": row["decision_arc_family"],
                "included_link_refs": list(row["included_link_refs"]),
                "scoring_arc_only_refs": [
                    ref
                    for ref in row["included_link_refs"]
                    if link_by_ref[ref]["link_kind"] == "scoring_arc_only"
                ],
                "evidence_assertion_refs": list(row["evidence_assertion_refs"]),
                "question_readiness": dict(row["question_readiness"]),
            }
        )
        units.append(unit)

    readiness_gap_count = sum(
        value == "evidence_gap"
        for unit in units
        for value in unit["question_readiness"].values()
    )
    gate_passed = not unresolved and not duplicate_episode_refs and bool(units)
    return {
        "schema_version": 1,
        "status": (
            "rule_evidence_unit_shadow_ready"
            if gate_passed
            else "rule_evidence_unit_shadow_failed_closed"
        ),
        "task_code": worklist.get("task_code"),
        "component_count": len(component_by_code),
        "draft_unit_count": len(units),
        "not_applicable_component_count": len(exclusions),
        "unresolved_component_count": len(unresolved),
        "readiness_evidence_gap_count": readiness_gap_count,
        "duplicate_consumption_episode_refs": sorted(duplicate_episode_refs),
        "rule_evidence_unit_drafts": units,
        "not_applicable_components": exclusions,
        "unresolved_components": unresolved,
        "direct_episode_projection_refs": [],
        "shadow_gate_passed": gate_passed,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "formal_projection_count": 0,
        "judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
