from __future__ import annotations

from scripts.dev import retrieval_v2_claim_rule_intake_shadow as tool


def chain(*, claim_keys: tuple[str, ...] = ("CLMK-001", "CLMK-002", "CLMK-003")) -> dict:
    return {
        "chain_key": "CCG-001",
        "emperor_name": "朱元璋",
        "object_name": "胡惟庸",
        "chain_type": "delegated_power_abuse_chain",
        "chain_strength": "strong_chain",
        "route_readiness": "ready_for_chain_route_review",
        "members": [{"claim_key": value} for value in claim_keys],
    }


def material(claim_key: str, **overrides) -> dict:
    row = {
        "claim_key": claim_key,
        "material_claim_id": 1,
        "source_pack_status": "accepted",
        "source_pack_coverage_status": "passed",
        "linked_passage_count": 1,
        "has_open_material_review": False,
    }
    row.update(overrides)
    return row


def accepted_object(**overrides) -> dict:
    row = {
        "emperor_name": "朱元璋",
        "object_name": "胡惟庸",
        "object_id": 10,
        "target_object_id": 20,
        "object_identity_key": "PERSON:HU-WEIYONG",
        "target_object_review_status": "accepted",
    }
    row.update(overrides)
    return row


def test_missing_cache_to_material_mapping_stays_at_intake_gate() -> None:
    plan = tool.build_shadow_plan([chain()], material_rows=[], object_rows=[])
    row = plan["chains"][0]

    assert row["next_step"] == "needs_cache_intake"
    assert row["blockers"] == ["missing_cache_claim_intake_mapping"]
    assert row["object_alignment"]["identity_status"] == "deferred_identity_resolution"
    assert row["formal_binding_allowed"] is False


def test_consumable_material_reaches_rule_review_without_waiting_for_object_resolution() -> None:
    plan = tool.build_shadow_plan(
        [chain()],
        material_rows=[material("CLMK-001"), material("CLMK-002"), material("CLMK-003")],
        object_rows=[],
    )
    row = plan["chains"][0]

    assert row["next_step"] == "ready_for_rule_candidate_review"
    assert row["material_alignment"]["consumable_material_claim_count"] == 3
    assert row["object_alignment"]["identity_gate"] == "deferred_until_formal_binding"


def test_open_material_review_blocks_candidate_generation() -> None:
    plan = tool.build_shadow_plan(
        [chain()],
        material_rows=[material("CLMK-001", has_open_material_review=True), material("CLMK-002"), material("CLMK-003")],
        object_rows=[accepted_object()],
    )
    row = plan["chains"][0]

    assert row["next_step"] == "needs_passage_review"
    assert "open_material_review" in row["blockers"]
    assert tool.material_is_consumable(material("CLMK-001", linked_passage_count=0)) is False
