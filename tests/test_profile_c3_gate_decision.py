"""Current decision consistency, using synthetic records rather than frozen rulings."""
import pytest

from emperor_v4.evaluation.profile_c3_verifier import verify_resolved_gate_decision


def sample(outcome):
    return {
        "ruler_id": "synthetic-ruler", "ruler_name": "合成对象",
        "axis_grade": "G3", "position": "HIGH",
        "resolved_high_gate_decision": {
            "ruler_id": "synthetic-ruler", "ruler_name": "合成对象",
            "outcome": outcome, "reason": "独立闭环仍不足。",
        },
    }


@pytest.mark.parametrize("outcome", ["UPGRADE_G4_LOW", "RETAIN_G3_LOW", "RETAIN_G2_HIGH"])
def test_rejects_stale_grade_or_position(outcome):
    with pytest.raises(AssertionError, match="stale C3 gate decision"):
        verify_resolved_gate_decision(sample(outcome))


@pytest.mark.parametrize("outcome", ["RETAIN_G3_HIGH", "RETAIN_G3_HIGH_EXCEPTIONAL_MILITARY_CHAIN"])
def test_accepts_matching_decisions_and_qualified_codes(outcome):
    verify_resolved_gate_decision(sample(outcome))


def test_legitimate_grade_change_passes_when_decision_is_synchronized():
    row = sample("UPGRADE_G4_LOW")
    row.update(axis_grade="G4", position="LOW")
    verify_resolved_gate_decision(row)


def test_decision_must_belong_to_the_same_person():
    row = sample("RETAIN_G3_HIGH")
    row["resolved_high_gate_decision"]["ruler_id"] = "another-person"
    with pytest.raises(AssertionError, match="detached"):
        verify_resolved_gate_decision(row)


def test_absent_optional_decision_is_allowed():
    row = sample("RETAIN_G3_HIGH")
    row.pop("resolved_high_gate_decision")
    verify_resolved_gate_decision(row)


@pytest.mark.parametrize("chain_count", [1, 2])
def test_high_gate_requires_independent_chains_but_not_different_domains(monkeypatch, chain_count):
    from emperor_v4.evaluation import profile_c3_verifier as verifier
    rid = "SYNTHETIC"
    parents = []
    for phase in range(chain_count):
        parent = dict(parent_id=f"phase-{phase}", closure_status="CLOSED", direction="POSITIVE",
                      material_strength="MI2", source_refs=[f"synthetic-source-{phase}"],
                      lifecycle_narrative=f"第{phase}阶段的独立授权与交付。",
                      boundary_review=dict(c5_excluded=True, m4_excluded=True, result_only_excluded=True))
        parent.update({field: f"阶段{phase}独立闭合。" for field in (
            "task_requirement", "candidate_identification", "position_configuration",
            "actual_authority", "delivery", "feedback", "authorization_response")})
        parents.append(parent)
    row = dict(task_code=f"PROFILE-C3-{rid}", ruler_id=rid, ruler_name="合成对象",
               axis_grade="G4", position="LOW", radar_value=77, score_100=77,
               axis_evidence_level="E3", output_mode="FULL_GRADE", confidence="HIGH",
               score_status="FINAL", formal_status="FORMAL_CURRENT", parent_chains=parents,
               representative_parent_ids=[p["parent_id"] for p in parents],
               major_task_domains_observed=["同一领域"], typical_pattern="分阶段复验。",
               grade_basis="同一领域有独立授权、交付与反馈。", position_basis="范围有限。",
               limitations=["未主张跨领域经验。"], axis_relevance_check={key: False for key in (
                   "famous_minister_count_used", "office_count_used", "final_outcome_backsolve_used",
                   "c5_ethics_leakage", "m4_group_outcome_leakage")})
    payload = dict(records=[row], record_count=1, axis_code="C3", contract_version="SYNTHETIC",
                   schema_version="profile-c3-formal-settlement-v2", canonical_status="FORMAL_CURRENT",
                   authority_mode="FORMAL_SETTLEMENT_PATCH_SOURCE", formal_rank_write=False,
                   profile_total_enabled=False, profile_ranking_enabled=False, database_write=False)
    monkeypatch.setattr(verifier, "_load", lambda path: {"records": [{"ruler_id": rid, "pool_status": "INCLUDED"}]})
    if chain_count == 1:
        with pytest.raises(AssertionError, match="single giant chain"):
            verifier.verify_payloads(payload)
    else:
        assert verifier.verify_payloads(payload)["status"] == "PASS"
