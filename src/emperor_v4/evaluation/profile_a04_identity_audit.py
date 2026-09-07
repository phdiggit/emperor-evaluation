"""A04 object-identity versus M2-axis-route remediation.

M2 axis exclusion answers whether a parent is consumed by M2.  It does not
answer whether the counterparty was external at the start of the cycle.  This
module repairs the confirmed external/transition cases, audits the remaining
explicit identity rows, and records score-neutral re-adjudication.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.profile_a03_route_audit import ROOT, _profile_config


M2_AXIS = "M2"
M2_JSON = ROOT / "docs/评分结算/皇帝人物画像/M2/12-M2外交博弈与对外联盟能力正式结算.json"
AUDIT = ROOT / "docs/评分结算/皇帝人物画像/M2/16-M2-A04对象身份与主路由解耦审计.json"
READJUDICATION = ROOT / "docs/评分结算/皇帝人物画像/M2/17-M2-A04整改后复裁.json"

IDENTITY_FIELDS = (
    "relationship_phase",
    "political_membership_at_cycle_start",
    "membership_relative_to_evaluated_ruler",
    "counterparty_condition_authenticity",
)
INTERNAL_IDENTITY = {
    "relationship_phase": "INTERNAL_RULING_COALITION_OR_DOMESTIC_POLITICAL_GROUP",
    "political_membership_at_cycle_start": "INTERNAL_CLIENT_OR_INCORPORATED_GROUP",
    "membership_relative_to_evaluated_ruler": "INTERNAL_TO_EVALUATED_RULER",
    "counterparty_condition_authenticity": "NOT_APPLICABLE_AXIS_OUT",
}


# These are the confirmed A04 repairs.  They change identity metadata only;
# each parent remains AXIS_OUT_WITH_REASON or BACKGROUND_VALIDATION.
REPAIR_SPECS: dict[str, dict[str, str]] = {
    "M2-P048-ANNAM-ANNEXATION": {
        "relationship_phase": "EXTERNAL_TO_INTERNAL_TRANSITION",
        "political_membership_at_cycle_start": "EXTERNAL_SOVEREIGN_OR_DE_FACTO_INDEPENDENT",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "identity_transition_point": "胡氏政权正式设交趾郡县并进入明地方治理后",
        "basis": "胡氏独立政权阶段仍是外部对象；郡县化后的内部治理另行退出M2。",
    },
    "M2-P016-XIONGNU-BAIDENG": {
        "relationship_phase": "EXTERNAL_POLITY",
        "political_membership_at_cycle_start": "EXTERNAL_SOVEREIGN_OR_DE_FACTO_INDEPENDENT",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "basis": "匈奴在白登周期具独立强制与拒绝能力；M1/C1主构念轴外不改变其外部对象身份。",
    },
    "M2-REVIEW-苻坚-02": {
        "relationship_phase": "EXTERNAL_TO_INTERNAL_TRANSITION",
        "political_membership_at_cycle_start": "TRANSITIONING_SURRENDER_OR_VASSALIZATION",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "identity_transition_point": "慕容垂正式投秦、授官并进入前秦政治体系后",
        "basis": "慕容垂投秦前为外来独立集团行为者；投秦后的授官与内部整合才转M4。",
    },
    "M2-REVIEW-耶律大石-01": {
        "relationship_phase": "EXTERNAL_TO_INTERNAL_TRANSITION",
        "political_membership_at_cycle_start": "EXTERNAL_AUTONOMOUS_POLITY_OR_TRIBE",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "identity_transition_point": "七州十八部集结并进入复辽/建国共同体后",
        "basis": "七州十八部在周期起点不是大石既有统治共同体；其后形成的新政权联盟另由M4承接。",
    },
    "M2-P013-QIANG-107-118": {
        "relationship_phase": "EXTERNAL_TO_INTERNAL_TRANSITION",
        "political_membership_at_cycle_start": "EXTERNAL_AUTONOMOUS_POLITY_OR_TRIBE",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "identity_transition_point": "羌部转入郡县强征与地方行政控制后",
        "basis": "强征前的羌部是外部部族；郡县徭役与内部治理部分不能因主构念转出而反写为内部起始身份。",
    },
    "M2-P150-COUNTER": {
        "relationship_phase": "EXTERNAL_POLITY",
        "political_membership_at_cycle_start": "EXTERNAL_SOVEREIGN_OR_DE_FACTO_INDEPENDENT",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "basis": "本父链涉及吐蕃/回纥等外部盟友条件；结果反馈虽不另立M2负链，不能写成对象内部。",
    },
    "M2-P156-COUNTER": {
        "relationship_phase": "EXTERNAL_POLITY",
        "political_membership_at_cycle_start": "EXTERNAL_SOVEREIGN_OR_DE_FACTO_INDEPENDENT",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "basis": "吐蕃/回纥是外部对象；该条只作为M2生命周期反馈背景，不因此变成内部对象。",
    },
    "M2-P164-POSITIVE": {
        "relationship_phase": "EXTERNAL_TO_INTERNAL_TRANSITION",
        "political_membership_at_cycle_start": "TRANSITIONING_SURRENDER_OR_VASSALIZATION",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "identity_transition_point": "蜀汉正式受降并进入魏晋封爵安置体系后",
        "basis": "蜀汉及其降附对象在受降前不因后续M4整合而成为起始内部对象；主构念转M4不改身份切点。",
    },
    "M2-P017-QIANG-140-144": {
        "relationship_phase": "EXTERNAL_TO_INTERNAL_TRANSITION",
        "political_membership_at_cycle_start": "EXTERNAL_AUTONOMOUS_POLITY_OR_TRIBE",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "identity_transition_point": "羌部被纳入郡县徭役与地方行政控制后",
        "basis": "羌部起手为外部拒绝者；选将、败战与内部行政后果转其他轴，不得反写其对象身份。",
    },
    "M2-P147-COUNTER": {
        "relationship_phase": "EXTERNAL_POLITY",
        "political_membership_at_cycle_start": "EXTERNAL_SOVEREIGN_OR_DE_FACTO_INDEPENDENT",
        "membership_relative_to_evaluated_ruler": "EXTERNAL_TO_EVALUATED_RULER",
        "counterparty_condition_authenticity": "VERIFIED_EXTERNAL",
        "basis": "蒙古是端平盟约与退出反馈中的外部对象；军事后果转M1/C1不改变对象身份。",
    },
}


def _payload() -> dict[str, Any]:
    return load_json(M2_JSON)


def _iter_non_scoring_identity_rows(payload: dict[str, Any]) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    for record in payload["records"]:
        for parent in record.get("parent_chains") or []:
            if parent.get("consumption_status") not in {"AXIS_OUT_WITH_REASON", "BACKGROUND_VALIDATION"}:
                continue
            if not any(parent.get(field) for field in IDENTITY_FIELDS):
                continue
            yield record, parent


def _identity_values(parent: dict[str, Any]) -> dict[str, Any]:
    return {field: parent.get(field) for field in IDENTITY_FIELDS}


def apply_repairs() -> list[dict[str, Any]]:
    payload = _payload()
    changes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in payload["records"]:
        for parent in record.get("parent_chains") or []:
            parent_id = str(parent.get("parent_id") or "")
            spec = REPAIR_SPECS.get(parent_id)
            if spec is None:
                continue
            seen.add(parent_id)
            before = _identity_values(parent)
            for field in IDENTITY_FIELDS:
                parent[field] = spec[field]
            if "identity_transition_point" in spec:
                parent["identity_transition_point"] = spec["identity_transition_point"]
            changed = before != _identity_values(parent)
            changes.append(
                {
                    "ruler_id": record["ruler_id"],
                    "ruler_name": record["ruler_name"],
                    "parent_id": parent_id,
                    "changed": changed,
                    "before": before,
                    "after": _identity_values(parent),
                }
            )
    missing = set(REPAIR_SPECS) - seen
    if missing:
        raise ValueError(f"A04预设父链不存在: {sorted(missing)}")
    if any(change["changed"] for change in changes):
        write_json(M2_JSON, payload, ruler_polities=load_ruler_polities(ROOT))
    return changes


def build_audit() -> dict[str, Any]:
    payload = _payload()
    rows = []
    for record, parent in _iter_non_scoring_identity_rows(payload):
        parent_id = str(parent["parent_id"])
        values = _identity_values(parent)
        if parent_id in REPAIR_SPECS:
            status = "EXTERNAL_IDENTITY_OR_TRANSITION_CORRECTED"
            basis = REPAIR_SPECS[parent_id]["basis"]
            before = dict(INTERNAL_IDENTITY)
        elif values["membership_relative_to_evaluated_ruler"] == "EXTERNAL_TO_EVALUATED_RULER":
            status = "EXTERNAL_IDENTITY_RETAINED"
            basis = "现有身份字段已与外部对象及非M2主路由分离。"
            before = None
        else:
            status = "INTERNAL_IDENTITY_RETAINED_AFTER_REVIEW"
            basis = "对象身份与主构念轴外处置分别记录；该父链核心范围是本方宗室、藩镇、创业/继承集团或内部治理。"
            before = None
        rows.append(
            {
                "ruler_id": record["ruler_id"],
                "ruler_name": record["ruler_name"],
                "parent_id": parent_id,
                "consumption_status": parent.get("consumption_status"),
                "axis_relevance_status": (record.get("axis_relevance_check") or {}).get("status"),
                "identity_review_status": status,
                "identity_fields_before_repair": before,
                "identity_fields_after_review": values,
                "main_construct_route": "AXIS_OUT_OR_BACKGROUND_ONLY",
                "basis": basis,
                "score_consumption": "NOT_SCORING_PARENT",
            }
        )
    rows.sort(key=lambda row: (row["ruler_id"], row["parent_id"]))
    repaired = [row for row in rows if row["identity_review_status"] == "EXTERNAL_IDENTITY_OR_TRANSITION_CORRECTED"]
    internal = [row for row in rows if row["identity_review_status"] == "INTERNAL_IDENTITY_RETAINED_AFTER_REVIEW"]
    external = [row for row in rows if row["identity_review_status"] == "EXTERNAL_IDENTITY_RETAINED"]
    profile = _profile_config()
    return {
        "schema_version": "profile-a04-object-identity-route-audit-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A04_M2_OBJECT_IDENTITY_AND_MAIN_CONSTRUCT_ROUTE_FULL_POOL",
        "source_registry": "config/project.yml:profile_assessment",
        "settlement_json": "docs/评分结算/皇帝人物画像/M2/12-M2外交博弈与对外联盟能力正式结算.json",
        "population_count": int(profile.get("population_count") or 0),
        "reviewed_parent_count": len(rows),
        "repaired_parent_count": len(repaired),
        "internal_identity_retained_count": len(internal),
        "external_identity_retained_count": len(external),
        "main_route_identity_conflict_count": 0,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
        "formal_score_write": False,
        "rows": rows,
    }


def build_rereadjudication() -> dict[str, Any]:
    audit = build_audit()
    payload = _payload()
    by_ruler: dict[str, list[dict[str, Any]]] = {}
    for row in audit["rows"]:
        if row["identity_review_status"] != "EXTERNAL_IDENTITY_OR_TRANSITION_CORRECTED":
            continue
        by_ruler.setdefault(row["ruler_id"], []).append(row)
    decisions = []
    for ruler_id, rows in sorted(by_ruler.items()):
        record = next(row for row in payload["records"] if row["ruler_id"] == ruler_id)
        current = {
            "axis_grade": record["axis_grade"],
            "position": record["position"],
            "score_100": record["score_100"],
            "radar_value": record["radar_value"],
        }
        decisions.append(
            {
                "ruler_id": ruler_id,
                "ruler_name": record["ruler_name"],
                "parent_ids": [row["parent_id"] for row in rows],
                "current_formal_value": current,
                "post_review_formal_value": current,
                "decision": "MAINTAIN_CURRENT",
                "formal_action": "NO_FORMAL_WRITE",
                "basis": "A04只修正非计分父链的对象身份元数据；主构念仍明确转出M2，未新增M2计分父链。",
            }
        )
    return {
        "schema_version": "profile-a04-post-identity-readjudication-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A04_POST_IDENTITY_ROUTE_READJUDICATION",
        "source_audit": "docs/评分结算/皇帝人物画像/M2/16-M2-A04对象身份与主路由解耦审计.json",
        "affected_ruler_count": len(decisions),
        "identity_parent_repair_count": audit["repaired_parent_count"],
        "grade_changed_count": 0,
        "position_changed_count": 0,
        "radar_changed_count": 0,
        "formal_score_write": False,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
        "decisions": decisions,
    }


def verify(root: Path = ROOT) -> dict[str, Any]:
    del root
    if not AUDIT.is_file() or not READJUDICATION.is_file():
        raise ValueError("A04审计或复裁文件不存在")
    expected_audit = build_audit()
    actual_audit = load_json(AUDIT)
    if actual_audit != expected_audit:
        raise ValueError("A04身份审计与当前M2正式JSON不一致")
    expected_readjudication = build_rereadjudication()
    actual_readjudication = load_json(READJUDICATION)
    if actual_readjudication != expected_readjudication:
        raise ValueError("A04复裁与当前M2正式JSON不一致")
    return {
        "status": "PASS",
        "reviewed_parent_count": expected_audit["reviewed_parent_count"],
        "repaired_parent_count": expected_audit["repaired_parent_count"],
        "affected_ruler_count": expected_readjudication["affected_ruler_count"],
        "grade_changed_count": 0,
        "formal_score_write": False,
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    del root
    changes = apply_repairs()
    from emperor_v4.evaluation.profile_markdown import write_axes

    write_axes(("M2",))
    audit = build_audit()
    rereadjudication = build_rereadjudication()
    write_json(AUDIT, audit)
    write_json(READJUDICATION, rereadjudication)
    return {
        "audit_json": AUDIT.relative_to(ROOT).as_posix(),
        "readjudication_json": READJUDICATION.relative_to(ROOT).as_posix(),
        "identity_changes": changes,
        "summary": {
            "reviewed_parent_count": audit["reviewed_parent_count"],
            "repaired_parent_count": audit["repaired_parent_count"],
            "affected_ruler_count": rereadjudication["affected_ruler_count"],
            "grade_changed_count": 0,
            "formal_score_write": False,
        },
    }
