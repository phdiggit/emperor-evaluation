from __future__ import annotations

from scripts.dev import retrieval_v3_evidence_sufficiency as tool


def test_missing_expected_inventory_blocks_confidence_without_adjusting_score() -> None:
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
    assert row["confidence_status"] == "unassessed_missing_expected_event_inventory"
    assert row["raw_claim_count"] == 5
    assert row["scored_event_group_count"] == 1
    assert row["independent_scored_source_document_count"] == 2


def test_ungrouped_scored_claim_blocks_calibration() -> None:
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

    assert row["confidence_status"] == "provisional_event_group_incomplete"
    assert row["ungrouped_scored_claim_count"] == 1
    assert row["expected_event_coverage"] == 0.5
