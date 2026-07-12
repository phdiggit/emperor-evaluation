from pathlib import Path

from scripts.dev import retrieval_v3_claim_route_consumer as tool


def test_route_replay_detaches_stale_resolved_binding_but_preserves_review() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "existing_binding.claim_id = excluded.claim_id" in source
    assert "then null" in source
    assert "candidate_review,review_verdict" in source
    assert "when 'accepted_candidate' then 'accepted'" in source
    assert "when 'rejected' then 'rejected'" in source


def test_route_claim_keys_expands_event_chain_members() -> None:
    assert tool.route_claim_keys(
        {
            "route_source_kind": "event_chain",
            "route_source_key": "CHN-1",
            "evidence": {"member_claim_keys": ["CLMK-2", "CLMK-1", "CLMK-2"]},
        }
    ) == ["CLMK-1", "CLMK-2"]


def test_route_claim_keys_keeps_atomic_claim() -> None:
    assert tool.route_claim_keys(
        {"route_source_kind": "claim", "route_source_key": "CLMK-1"}
    ) == ["CLMK-1"]


def test_route_status_maps_mechanical_only_to_candidate() -> None:
    assert tool.route_status_for_cache("mechanical_current_rule_candidate") == "candidate"
    assert tool.route_status_for_cache("ready_for_rule_route_review") == "needs_review"


def test_routable_rules_cover_all_claim_driven_current_rules() -> None:
    assert set(tool.ROUTABLE_RULE_CODES) == {
        "talent_discovery", "appointment_delegation", "tolerate_talent", "anti_nepotism"
    }
