from __future__ import annotations

from scripts.dev import retrieval_v2_claim_patch as tool


def test_parse_patch_row_accepts_top_level_and_nested_set_fields() -> None:
    patch = tool.parse_patch_row(
        {
            "claim_key": "CLMK-001",
            "set": {"emperor_name": "李治", "direction": "neutral"},
            "action_type": "其他",
            "expected": {"emperor_name": "李世民"},
            "reason": "reviewed owner and direction repair",
        }
    )

    assert patch.claim_key == "CLMK-001"
    assert patch.set_values == {"emperor_name": "李治", "direction": "neutral", "action_type": "其他"}
    assert patch.expected == {"emperor_name": "李世民"}


def test_patch_preview_blocks_expected_mismatch() -> None:
    patch = tool.parse_patch_row(
        {
            "claim_key": "CLMK-001",
            "set": {"emperor_name": "李治"},
            "expected": {"emperor_name": "李渊"},
        }
    )

    preview = tool.patch_preview(patch, {"claim_key": "CLMK-001", "emperor_name": "李世民"})

    assert preview["status"] == "blocked_expected_mismatch"
    assert preview["expected_mismatches"] == {"emperor_name": {"expected": "李渊", "actual": "李世民"}}


def test_build_patch_report_marks_missing_rows_not_ok() -> None:
    patches = [
        tool.parse_patch_row({"claim_key": "CLMK-001", "set": {"direction": "neutral"}}),
        tool.parse_patch_row({"claim_key": "CLMK-002", "set": {"status": "needs_review"}}),
    ]

    report = tool.build_patch_report(
        patches,
        {"CLMK-001": {"claim_key": "CLMK-001", "direction": "negative", "status": "active"}},
    )

    assert report["ok"] is False
    assert report["totals"]["changed"] == 1
    assert report["totals"]["missing"] == 1


def test_repair_payload_records_previous_values() -> None:
    patch = tool.parse_patch_row(
        {
            "claim_key": "CLMK-001",
            "set": {"direction": "neutral"},
            "reason": "negative direction lacks actual damage",
        }
    )

    payload = tool.repair_payload(
        patch,
        {"emperor_name": "李世民", "direction": "negative", "action_type": "纳谏", "status": "active"},
        {"direction": {"from": "negative", "to": "neutral"}},
    )

    assert payload["reason"] == "negative direction lacks actual damage"
    assert payload["previous"]["direction"] == "negative"
    assert payload["changes"]["direction"]["to"] == "neutral"
