from __future__ import annotations

from scripts.dev import retrieval_v3_clean_summary as tool


def test_judge_anomalies_blocks_mixed_scoring_claim_without_negative_split() -> None:
    payload = {
        "claims": [
            {
                "claim_code": "CLM-MIXED",
                "object_name": "薛万彻",
                "direction": "mixed",
            }
        ],
        "primary_bindings": [
            {
                "claim_code": "CLM-MIXED",
                "direction": "positive",
                "usable_for_scoring_cluster": True,
            }
        ],
        "coverage_gaps": [],
    }

    rows = tool.judge_anomalies(payload)

    assert rows == [
        {
            "severity": "block",
            "code": "mixed_claim_not_split",
            "claim_code": "CLM-MIXED",
            "object_name": "薛万彻",
            "direction": "mixed",
            "message": "mixed claim has scoring binding but no negative split binding or gap",
        }
    ]


def test_judge_anomalies_accepts_negative_claim_with_queued_gap() -> None:
    payload = {
        "claims": [
            {
                "claim_code": "CLM-NEGATIVE",
                "object_name": "张郃",
                "direction": "negative",
            }
        ],
        "primary_bindings": [
            {
                "claim_code": "CLM-NEGATIVE",
                "direction": "negative",
                "usable_for_scoring_cluster": False,
            }
        ],
        "coverage_gaps": [
            {
                "gap_type": "negative_undercoverage",
                "family_code": "revoked_or_failed_delegate",
                "object_name": "张郃",
            }
        ],
    }

    assert tool.judge_anomalies(payload) == []


def test_anomaly_counts_groups_severity() -> None:
    rows = [
        {"severity": "block"},
        {"severity": "warning"},
        {"severity": "warning"},
        {"severity": "other"},
    ]

    assert tool.anomaly_counts(rows) == {"block": 1, "warning": 2}
