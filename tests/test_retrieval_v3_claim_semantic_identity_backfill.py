from __future__ import annotations

from scripts.dev import retrieval_v3_claim_semantic_identity_backfill as tool


def claim(key: str, *, time: str, outcome: str = "") -> dict:
    return {
        "claim_key": key,
        "emperor_name": "李治",
        "object_name": "苏定方",
        "claim_summary": key,
        "outcome": outcome,
        "fact_payload": {"action_type": "任命", "office_or_domain": "神丘道行军大总管", "time_context": time, "outcome": outcome},
    }


def test_semantic_backfill_groups_cross_wording_claims() -> None:
    updates, report = tool.semantic_updates([claim("CLMK-1", time="显庆五年"), claim("CLMK-2", time="显庆五年（660年）")])
    assert updates[0]["canonical_event_key"] == updates[1]["canonical_event_key"]
    assert report["semantic_event_count"] == 1
    assert report["duplicate_excess"] == 1


def test_semantic_backfill_flags_conflicting_outcomes_for_review() -> None:
    _, report = tool.semantic_updates([claim("CLMK-1", time="显庆五年", outcome="百济降"), claim("CLMK-2", time="显庆五年", outcome="撤军")])
    assert report["outcome_conflict_review_count"] == 1
    assert report["duplicate_groups"][0]["outcome_conflict_review"] is True
