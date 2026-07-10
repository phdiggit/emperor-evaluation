import pytest

from scripts.dev import retrieval_v3_direct_binding_plan as tool


def direct_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "claim_id": 11, "contract_rule_id": 8, "rule_code": "appointment_delegation",
        "predicate": "appointed_or_delegated_authority", "direction": "positive",
        "object_role": "military_commander", "object_id": 21, "target_object_id": 31,
        "binding_note": "原文明确载有皇帝的岗位授权、具体职责与同链结果，身份锚点已经复核。",
    }
    row.update(overrides)
    return row


def test_direct_plan_requires_no_candidate() -> None:
    payload = tool.build_plan([direct_row()])

    assert payload["assessment_lane"] == "normal_direct"
    assert payload["candidate_required"] is False
    assert payload["assessments"][0]["claim_id"] == 11


def test_direct_plan_rejects_missing_identity_anchor() -> None:
    with pytest.raises(tool.DirectBindingPlanError, match="target_object_id"):
        tool.build_plan([direct_row(target_object_id=None)])
