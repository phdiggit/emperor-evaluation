from __future__ import annotations

from scripts.dev import retrieval_v3_material_candidate_consumer as tool


class FakeCursor:
    def __init__(self) -> None:
        self.executed = []

    def execute(self, sql, params) -> None:
        self.executed.append((sql, params))

    def fetchall(self):
        return [
            {
                "claim_code": "CLM-1",
                "claim_id": 101,
                "source_pack_id": 7,
                "source_pack_code": "SPK-1",
                "target_id": 11,
                "target_code": "TGT-1",
                "candidate_contract_rule_id": 22,
            }
        ]


def test_resolve_rows_maps_material_claims_to_candidate_contract() -> None:
    cur = FakeCursor()
    resolved, missing = tool.resolve_rows(
        cur,
        [
            {
                "candidate_code": "CLM-1::CANDIDATE::appointment_delegation",
                "source_material_claim_code": "CLM-1",
                "candidate_reason": "命中任用",
                "matched_signals": ["任用/信任/撤任事实"],
                "matched_terms": ["任"],
                "candidate_direction": "negative",
                "candidate_object_role": "misappointed_actor",
                "required_facts_present": {
                    "has_appointment_or_authorization": True,
                    "has_named_actor": True,
                    "has_task_or_responsibility": True,
                    "has_result_or_feedback": True,
                    "has_continuity_or_reuse": False,
                },
            },
            {
                "candidate_code": "CLM-2::CANDIDATE::appointment_delegation",
                "source_material_claim_code": "CLM-2",
                "candidate_reason": "命中任用",
                "matched_signals": ["任用/信任/撤任事实"],
                "matched_terms": ["任"],
            },
        ],
    )

    assert len(resolved) == 1
    assert resolved[0]["claim_id"] == 101
    assert resolved[0]["candidate_contract_rule_id"] == 22
    assert resolved[0]["review_status"] == "pending"
    assert resolved[0]["source_contract_rule_id"] is None
    assert resolved[0]["candidate_direction"] == "negative"
    assert resolved[0]["candidate_object_role"] == "misappointed_actor"
    assert resolved[0]["required_facts_present"]["has_result_or_feedback"] is True
    assert missing == [{"source_material_claim_code": "CLM-2", "reason": "material_claim_not_found"}]
