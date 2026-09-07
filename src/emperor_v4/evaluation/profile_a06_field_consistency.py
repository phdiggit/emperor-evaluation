"""A06 formal-profile adjudication-field consistency audit.

The audit is deliberately score-neutral.  It checks the eight formal profile
axes for direct grade/position claims in the explanatory fields, explicit PS
level contradictions, and counterpattern references that do not resolve to
the record's formal parent chains.  Negated historical comparisons such as
“不能进G4” are not treated as current adjudications.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)
from emperor_v4.evaluation.profile_a03_route_audit import ROOT, _profile_config


AUDIT = ROOT / "docs/评分结算/皇帝人物画像/交叉轴复核/08-A06裁决字段自洽审计.json"
FORMAL_AXES = ("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5")
EXPLANATION_FIELDS = ("grade_basis", "position_basis")

GRADE_CLAIM_RE = re.compile(
    r"(?:当前(?:正式)?(?:档位|结论)?(?:为|是|：|:)|"
    r"正式(?:档位|结论)?(?:为|是|：|:)|"
    r"定为|定位为|裁为|改判|改定|改为|上调为|下调为|重裁为|恢复|"
    r"降至|升为|维持|保留|取|置)\s*`?\s*"
    r"(?P<grade>G[0-5])(?:-(?P<position>LOW|MID|HIGH))?"
    r"(?:\s*(?P<cn_position>低位|中位|高位))?"
)
PS_RE = re.compile(r"PS[0-4]")
NEGATION_RE = re.compile(
    r"(?:不能|不足|不进|不宜|不再|不应|未|尚未|尚不足|无法|不得|没有|"
    r"阻止|避免|拒绝|不(?:足|会|至|构成|符合|能|宜|应))"
)
CN_POSITION = {"低位": "LOW", "中位": "MID", "高位": "HIGH"}
SCORE_POINTS = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12},
    "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51},
    "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87},
    "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}


# These are explanation-only repairs identified by the full-pool mechanical
# scan.  No score, grade, position, parent chain, or counterpattern is
# changed by this table.
REPAIR_SPECS: dict[str, dict[str, str]] = {
    "RULER-PUBLIC-6339E33979E7CCF5": {
        "position_basis": "PS4已成立；宁锦下沿、继承风险与臣僚/前线归责限制上沿，取G5-LOW，不进入G5-MID。",
    },
    "RULER-ROSTER-323631DDD7CB22F6": {
        "position_basis": "不同国家级约束下的目标排序、继承配置与新附集团重构已达到PS4；短窗口、边界执行未完与征服现场归责限制上沿，取G5-LOW。",
    },
    "RULER-FD-LI-BIAN": {
        "position_basis": "政权转换、外部机会克制与内部强臣—储嗣制衡共同支撑G4-MID；短窗口和高压危机复验不足阻止HIGH。",
    },
    "RULER-SHADOW-宇文泰": {
        "position_basis": "关陇建基与制度承载的C1主体保留；突厥—柔然信用处置和宇文护交接结构的两类DW2压低上沿，取G4-MID。",
    },
    "RULER-ROSTER-B32BFAF97E1D9690": {
        "position_basis": "1643继承资源重构与1644入关—北京承载构成两条重大周期；本人集中化侵蚀与新占区控制成本限制上沿，取G4-LOW。",
    },
    "RULER-SHADOW-姚苌": {
        "position_basis": "创业建基与生前继承资源预置是两个独立国家级问题，达到G4准入；短窗口及一正一负结构限制档内位置，取G4-LOW。",
    },
    "RULER-SHADOW-拓跋宏": {
        "position_basis": "迁洛的国家空间—集团重组与继承资源重构是两个独立PS2，构成G4门；南征DW2和九年亲政窗口压在LOW，取G4-LOW。",
    },
    "RULER-SHADOW-石勒": {
        "position_basis": "葛陂南耗后的襄国建基与内部集团承载保留PS3主体；DW3、张宾设计份额和跨域复验限制上沿，取G4-LOW。",
    },
    "RULER-NS-ZHAO-KUANGYIN": {
        "position_basis": "正式C1能力达到PS4；具体战役解题归将领、决策窗口较短且继承风险未闭，取G5-LOW，不进入G5-MID。",
    },
    "RULER-LIAO-YELU-DASHI": {
        "position_basis": "极坏牌下的跨联盟、资源与国家重建构成PS3；唯一超长生命周期及东征目标—承载失配限制上沿，取G4-LOW。",
    },
    "RULER-SHADOW-宇文邕": {
        "position_basis": "北齐路线与诛护后内部强制资源重组是两个独立国家级问题，G4门成立；河阴DW2和六年亲政短窗口限制上沿，取G4-LOW。",
    },
    "RULER-YUAN-OGEDEI": {
        "position_basis": "灭金与西征分工形成两个独立重大周期并达到G4下沿；晚年信息旁路、继承未闭合及臣下/宗王设计份额限制上沿，取G4-LOW。",
    },
}

AXIS_REPAIR_SPECS: dict[str, dict[str, dict[str, str]]] = {
    "C1": REPAIR_SPECS,
    "M1": {
        "RULER-SHADOW-慕容德": {
            "position_basis": "档内低位：主要适用机会已覆盖，不因全在FOUNDING_PRIMARY阻断。；情境集中且无同强失败反馈，限制历史级判断；取G4低位。；限制：INSUFFICIENT_WHOLE_DISTRIBUTION_THICKNESS、MAJOR_PHASE_COVERAGE_INCOMPLETE",
        },
        "RULER-SHADOW-沮渠蒙逊": {
            "position_basis": "档内低位：难度不是E3统一门，主要适用战区和机会已覆盖。；一次混合撤转提供真实下沿，其他三次表现稳定偏强；范围仍局限河西，取G4低位。；限制：E3_HIGH_DIFFICULTY_OR_HIGH_PRESSURE_DISTRIBUTION_INSUFFICIENT、FOUR_CONTEXTS_DO_NOT_ESTABLISH_HISTORICALLY_STABLE_LOWER_TAIL",
        },
        "RULER-SHADOW-钱镠": {
            "position_basis": "档内低位：主要军事生涯集中创业期，覆盖其适用机会。；战区范围有限且缺同强反例，取G4低位而非G5。；限制：INSUFFICIENT_WHOLE_DISTRIBUTION_THICKNESS、MAJOR_PHASE_COVERAGE_INCOMPLETE",
        },
        "RULER-TANG-LIZHI": {
            "position_basis": "档内低位：苏定方、李勣等前线能力不继承，只计目标、统帅配置、持续投入和反馈调整。；后期对新罗、吐蕃和突厥方向出现控制回撤，且本人无亲临统帅；强战略成果与后期下沿并存，取G3低位。；限制：SINGLE_CONTEXT_ONLY",
        },
    },
}


def _payloads(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    profile = _profile_config()
    return {
        axis: load_json(root / entry["json"])
        for axis, entry in profile["settled_axes"].items()
    }


def _parent_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    return list(record.get("parent_chains") or record.get("parents") or [])


def _expected_label(record: dict[str, Any]) -> str:
    return f"{record['axis_grade']}-{record['position']}"


def _repair_specs(axis: str, ruler_id: str) -> dict[str, str] | None:
    return AXIS_REPAIR_SPECS.get(axis, {}).get(ruler_id)


def _adjudication_text(value: Any) -> str:
    """Keep the declared basis and discard appended process-log sections."""

    text = str(value or "")
    for marker in ("---", "###", "##"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def _claim_label(match: re.Match[str]) -> str:
    position = match.group("position") or CN_POSITION.get(match.group("cn_position") or "")
    return f"{match.group('grade')}-{position}" if position else match.group("grade")


def _is_negated(text: str, match: re.Match[str]) -> bool:
    boundary = max(
        text.rfind("。", 0, match.start()),
        text.rfind("；", 0, match.start()),
        text.rfind("，", 0, match.start()),
        text.rfind(",", 0, match.start()),
        text.rfind("\n", 0, match.start()),
    )
    prefix = text[boundary + 1 : match.start()]
    return bool(NEGATION_RE.search(prefix))


def _direct_grade_conflicts(axis: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    expected_grade = str(record.get("axis_grade") or "")
    expected_label = _expected_label(record)
    conflicts: list[dict[str, Any]] = []
    for field in EXPLANATION_FIELDS:
        text = _adjudication_text(record.get(field))
        claims = [match for match in GRADE_CLAIM_RE.finditer(text) if not _is_negated(text, match)]
        for match in claims[-1:]:
            claim = _claim_label(match)
            if claim not in {expected_grade, expected_label}:
                conflicts.append(
                    {
                        "kind": "DIRECT_GRADE_OR_POSITION_CLAIM",
                        "axis": axis,
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "field": field,
                        "formal_value": expected_label,
                        "claim": claim,
                        "excerpt": text[max(0, match.start() - 28) : min(len(text), match.end() + 36)],
                    }
                )
    return conflicts


def _ps_conflicts(axis: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    grade_text = _adjudication_text(record.get("grade_basis"))
    position_text = _adjudication_text(record.get("position_basis"))
    grade_ps = {int(value[-1]) for value in PS_RE.findall(grade_text)}
    position_ps = {int(value[-1]) for value in PS_RE.findall(position_text)}
    if not grade_ps or not position_ps:
        return []
    lower_position = position_text.replace(" ", "")
    has_lower_bound_language = any(
        marker in lower_position
        for marker in ("不足", "止于", "只确认", "仅确认", "不能达到", "尚不足")
    )
    if not has_lower_bound_language or not any(value < max(grade_ps) for value in position_ps):
        return []
    return [
        {
            "kind": "PS_LEVEL_CONFLICT",
            "axis": axis,
            "ruler_id": record["ruler_id"],
            "ruler_name": record["ruler_name"],
            "formal_value": _expected_label(record),
            "grade_basis_ps": sorted(grade_ps),
            "position_basis_ps": sorted(position_ps),
            "grade_basis_excerpt": grade_text,
            "position_basis_excerpt": position_text,
        }
    ]


def _counterpattern_conflicts(axis: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    counterpattern = record.get("counterpattern")
    if not isinstance(counterpattern, dict):
        return []
    parents = {str(parent.get("parent_id")): parent for parent in _parent_rows(record)}
    conflicts: list[dict[str, Any]] = []
    for key, refs in counterpattern.items():
        if not key.endswith("_parent_refs") or not isinstance(refs, list):
            continue
        for ref in refs:
            ref = str(ref)
            parent = parents.get(ref)
            if parent is None:
                conflicts.append(
                    {
                        "kind": "COUNTERPATTERN_PARENT_REF_MISSING",
                        "axis": axis,
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "field": f"counterpattern.{key}",
                        "parent_ref": ref,
                    }
                )
                continue
            direction = str(parent.get("direction") or "")
            if key == "positive_parent_refs":
                allowed = {"POSITIVE", "MIXED_POSITIVE", "MIXED"}
            elif key in {"counter_parent_refs", "negative_parent_refs"}:
                allowed = {"NEGATIVE", "MIXED_NEGATIVE", "MIXED_BALANCED", "MIXED", "LIMITATION"}
            else:
                allowed = {"MIXED", "MIXED_POSITIVE", "MIXED_NEGATIVE", "MIXED_BALANCED"}
            if direction not in allowed:
                conflicts.append(
                    {
                        "kind": "COUNTERPATTERN_DIRECTION_MISMATCH",
                        "axis": axis,
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "field": f"counterpattern.{key}",
                        "parent_ref": ref,
                        "parent_direction": direction,
                    }
                )
    return conflicts


def _coverage_and_score_errors(payloads: dict[str, dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    del root
    profile = _profile_config()
    expected_ids: set[str] | None = None
    for axis in FORMAL_AXES:
        rows = list(payloads[axis].get("records") or [])
        ids = {str(row.get("ruler_id") or "") for row in rows}
        if len(rows) != int(profile.get("population_count") or 0):
            errors.append({"kind": "RECORD_COUNT", "axis": axis, "actual": len(rows)})
        if expected_ids is None:
            expected_ids = ids
        elif ids != expected_ids:
            errors.append({"kind": "POOL_COVERAGE", "axis": axis})
        for row in rows:
            grade = str(row.get("axis_grade") or "")
            position = str(row.get("position") or "")
            expected_score = SCORE_POINTS.get(grade, {}).get(position)
            if expected_score is None:
                errors.append({"kind": "ILLEGAL_GRADE_POSITION", "axis": axis, "ruler_id": row.get("ruler_id")})
            elif row.get("score_100") != expected_score or row.get("radar_value") != expected_score:
                errors.append({"kind": "SCORE_PROJECTION", "axis": axis, "ruler_id": row.get("ruler_id")})
    return errors


def build_audit(root: Path = ROOT) -> dict[str, Any]:
    payloads = _payloads(root)
    direct_conflicts: list[dict[str, Any]] = []
    ps_conflicts: list[dict[str, Any]] = []
    counterpattern_conflicts: list[dict[str, Any]] = []
    repair_status: list[dict[str, Any]] = []
    for axis in FORMAL_AXES:
        for record in payloads[axis]["records"]:
            direct_conflicts.extend(_direct_grade_conflicts(axis, record))
            ps_conflicts.extend(_ps_conflicts(axis, record))
            counterpattern_conflicts.extend(_counterpattern_conflicts(axis, record))
            expected_fields = _repair_specs(axis, record["ruler_id"])
            if expected_fields:
                repair_status.append(
                    {
                        "axis": axis,
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "fields": sorted(expected_fields),
                        "status": (
                            "REPAIRED"
                            if all(record.get(key) == value for key, value in expected_fields.items())
                            else "PENDING_REPAIR"
                        ),
                    }
                )
    structural_errors = _coverage_and_score_errors(payloads, root)
    unresolved = direct_conflicts + ps_conflicts + counterpattern_conflicts + structural_errors
    del root
    profile = _profile_config()
    return {
        "schema_version": "profile-a06-adjudication-field-consistency-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A06_ADJUDICATION_FIELDS_FULL_POOL_EIGHT_AXES",
        "source_registry": "config/project.yml:profile_assessment",
        "source_axes": list(FORMAL_AXES),
        "population_count": int(profile.get("population_count") or 0),
        "record_count": sum(len(payloads[axis]["records"]) for axis in FORMAL_AXES),
        "axis_record_count": {axis: len(payloads[axis]["records"]) for axis in FORMAL_AXES},
        "direct_grade_or_position_conflict_count": len(direct_conflicts),
        "ps_level_conflict_count": len(ps_conflicts),
        "counterpattern_conflict_count": len(counterpattern_conflicts),
        "structural_error_count": len(structural_errors),
        "unresolved_count": len(unresolved),
        "repair_spec_count": sum(len(specs) for specs in AXIS_REPAIR_SPECS.values()),
        "repair_status": sorted(repair_status, key=lambda row: (row["axis"], row["ruler_id"])),
        "direct_grade_or_position_conflicts": direct_conflicts,
        "ps_level_conflicts": ps_conflicts,
        "counterpattern_conflicts": counterpattern_conflicts,
        "structural_errors": structural_errors,
        "formal_score_write": False,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
    }


def apply_repairs(root: Path = ROOT) -> list[dict[str, str]]:
    payloads = _payloads(root)
    changes: list[dict[str, str]] = []
    ruler_polities = load_ruler_polities(root)
    profile = _profile_config()
    for axis in FORMAL_AXES:
        changed = False
        for record in payloads[axis]["records"]:
            specs = _repair_specs(axis, str(record.get("ruler_id") or ""))
            if not specs:
                continue
            for field, expected in specs.items():
                if record.get(field) == expected:
                    continue
                changes.append(
                    {
                        "axis": axis,
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "field": field,
                    }
                )
                record[field] = expected
                changed = True
        if changed:
            write_json(
                root / profile["settled_axes"][axis]["json"],
                payloads[axis],
                ruler_polities=ruler_polities,
            )
    return changes


def verify(root: Path = ROOT) -> dict[str, Any]:
    expected = build_audit(root)
    if not AUDIT.is_file():
        raise ValueError(f"A06审计文件不存在: {AUDIT}")
    actual = load_json(AUDIT)
    if actual != expected:
        raise ValueError("A06审计文件与当前八轴正式画像不一致")
    if expected["unresolved_count"]:
        raise ValueError(f"A06存在未解决字段冲突: {expected['unresolved_count']}")
    if any(row["status"] != "REPAIRED" for row in expected["repair_status"]):
        raise ValueError("A06已登记修复项未全部完成")
    return {
        "status": "PASS",
        "population_count": expected["population_count"],
        "axis_count": len(FORMAL_AXES),
        "record_count": expected["record_count"],
        "repair_count": len(expected["repair_status"]),
        "formal_score_write": False,
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    changes = apply_repairs(root)
    from emperor_v4.evaluation.profile_markdown import write_axes

    markdown_paths = write_axes(tuple(AXIS_REPAIR_SPECS))
    audit = build_audit(root)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    write_json(AUDIT, audit)
    if audit["unresolved_count"]:
        raise ValueError(f"A06写入后仍有未解决字段冲突: {audit['unresolved_count']}")
    return {
        "audit_json": AUDIT.relative_to(root).as_posix(),
        "markdown": [path.relative_to(root).as_posix() for path in markdown_paths],
        "field_changes": changes,
        "summary": {
            "population_count": audit["population_count"],
            "axis_count": len(FORMAL_AXES),
            "record_count": audit["record_count"],
            "repair_count": len(audit["repair_status"]),
            "formal_score_write": False,
            "grade_write": False,
            "position_write": False,
            "radar_write": False,
        },
    }


if __name__ == "__main__":
    import json
    import sys

    action = sys.argv[1] if len(sys.argv) > 1 else "verify"
    result = write() if action == "write" else verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
