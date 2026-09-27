"""Separate registered lifetime coverage from attributable ability evidence."""
BATTLE_REGISTRY = "docs/公共成果/军事/01-战役登记.json"
TALENT_REGISTRY = "docs/公共成果/军事/02-武将人才等级.json"
COVERAGE_STATUS = "FULL_LIFETIME_REGISTERED"
COVERAGE_LABEL = "全生涯逐战役登记已覆盖"
COVERAGE_BASIS = (
    "材料底池已按全生涯逐战役登记；代表情境只是本次能力裁决的定位索引，"
    "不是全部已检视战役的目录。没有独立武将档案不表示没有军事材料。"
)
ABILITY_LABELS = {
    "E1": "本人能力证据集中于有限可归责情境",
    "E2": "本人能力证据包含独立情境或完整变化链",
    "E3": "主要能力命题已完成归责、反例与限制核对",
}
MODE_LABELS = {
    "EPISODE_TAG": "已定档；能力外推限于可归责情境",
    "BOUNDED_PROFILE": "已定档；本人能力结论有明确适用边界",
    "FULL_GRADE": "已定档；发布全生涯能力模式与限制",
}


def evidence_scope(level: str, mode: str) -> dict:
    """Build declared public metadata; never infer coverage or grades from counts."""
    return {
        "schema_version": "m1-evidence-scope-v1",
        "material_coverage_status": COVERAGE_STATUS,
        "material_coverage_label": COVERAGE_LABEL,
        "material_coverage_basis": COVERAGE_BASIS,
        "source_refs": [BATTLE_REGISTRY, TALENT_REGISTRY],
        "ability_evidence_level": level,
        "ability_evidence_label": ABILITY_LABELS[level],
        "conclusion_mode_label": MODE_LABELS[mode],
        "attribution_boundary": "战役已登记不等于本人亲自指挥；名将战果、任务难度和国家资源不得自动转为本人能力。",
        "confidence_basis": "判断把握反映本人角色、因果归属与能力外推的确定程度，不表示全生涯材料是否登记完毕。",
        "grade_boundary": "覆盖完成不自动提高能力档位；强军事周期、角色组合、跨任务复验与稳定性仍按M1合同判断。",
    }


def verify_evidence_scope(record: dict) -> None:
    scope = record.get("evidence_scope")
    assert scope is not None, f"{record['ruler_name']}: missing M1 evidence scope"
    expected = evidence_scope(record["axis_evidence_level"], record["output_mode"])
    assert scope == expected, f"{record['ruler_name']}: inconsistent M1 coverage/ability scope"
    assert record["score_status"] == "FINAL", "registered and adjudicated M1 record must not retain an obsolete evidence-backlog status"
    assert "normative_entry_gate_mode_adjustment" not in record, "retired entry gate must not override current evidence scope"
