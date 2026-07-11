from __future__ import annotations

from scripts.dev import retrieval_v3_evidence_sufficiency as tool


def test_missing_expected_inventory_does_not_block_operational_score() -> None:
    coverage = {"objects": [{
        "emperor_name": "甲", "active_claim_count": 5, "event_group_count": 3,
        "expected_event_count": 0, "covered_expected_event_count": 0,
    }]}
    details = {"TGT-A": {
        "emperor_name": "甲",
        "calc_detail": {
            "materials": [{
                "claim_key": "CLM-1", "event_group_keys": ["EG-1"],
                "source_document_codes": ["DOC-1", "DOC-2"],
            }],
            "object_side_scores": {"positive": {"1": {}}, "negative": {}},
        },
    }}

    report = tool.build_evidence_sufficiency(coverage=coverage, score_details=details, emperors=["甲"])
    row = report["emperors"][0]

    assert report["score_adjustment_applied"] is False
    assert report["claim_quantity_is_score_factor"] is False
    assert report["confidence_scalar_generated"] is False
    assert report["expected_event_inventory_required_for_operational_scoring"] is False
    assert row["operational_evidence_status"] == "observed_evidence_lineage_complete"
    assert row["operational_score_ready"] is True
    assert row["historical_coverage_status"] == "unassessed"
    assert row["raw_claim_count"] == 5
    assert row["scored_event_group_count"] == 1
    assert row["independent_scored_source_document_count"] == 2


def test_missing_event_and_source_lineage_blocks_only_operational_readiness() -> None:
    coverage = {"objects": [{
        "emperor_name": "甲", "expected_event_count": 2, "covered_expected_event_count": 1,
    }]}
    details = {"TGT-A": {
        "emperor_name": "甲",
        "calc_detail": {
            "materials": [{"claim_key": "CLM-1", "event_group_keys": [], "source_document_codes": []}],
            "object_side_scores": {"positive": {}, "negative": {}},
        },
    }}

    row = tool.build_evidence_sufficiency(
        coverage=coverage, score_details=details, emperors=["甲"])["emperors"][0]

    assert row["operational_evidence_status"] == "lineage_incomplete"
    assert row["operational_score_ready"] is False
    assert row["historical_coverage_status"] == "assessed_partial"
    assert row["operational_lineage_gaps"] == [
        "scored_claims_missing_event_group",
        "scored_claims_missing_source_document",
        "scored_objects_missing",
    ]
    assert row["ungrouped_scored_claim_count"] == 1
    assert row["expected_event_coverage"] == 0.5
