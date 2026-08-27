from __future__ import annotations

import copy
import json

import pytest

from emperor_v4.evaluation.profile_m4_settlement import (
    AUDIT,
    FULL_POOL_REVIEW,
    HIGH_REVIEW,
    SETTLEMENT,
)
from emperor_v4.evaluation.profile_m4_verifier import verify, verify_payloads


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_m4_formal_settlement_passes_stable_verifier() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert result["parent_count"] == 368
    assert result["grade_change_count"] == 24


def test_profile_m4_high_grade_gate_covers_full_alliance_lifecycle() -> None:
    high = _load(HIGH_REVIEW)
    assert high["candidate_count"] == len(high["reviews"])
    assert all(row["mechanism_count"] == 4 for row in high["reviews"])
    assert all(row["full_power_window_review"] == "CLOSED" for row in high["reviews"])
    assert all(row["conflict_and_exit_review"] == "CLOSED" for row in high["reviews"])


def test_profile_m4_rejects_open_lifecycle_and_source_grade_conversion() -> None:
    settlement = _load(SETTLEMENT)
    audit = _load(AUDIT)
    high = _load(HIGH_REVIEW)
    review = _load(FULL_POOL_REVIEW)

    broken = copy.deepcopy(settlement)
    broken["records"][0]["parents"][0]["exit_result"] = ""
    with pytest.raises(AssertionError, match="open M4 lifecycle"):
        verify_payloads(broken, audit, high, review)

    broken = copy.deepcopy(settlement)
    broken["records"][0]["source_axis_grade"] = "source_axis_grade"
    with pytest.raises(AssertionError):
        verify_payloads(broken, audit, high, review)


def test_profile_m4_two_pass_review_is_full_pool_and_bidirectional() -> None:
    review = _load(FULL_POOL_REVIEW)
    assert review["mechanical_screen_count"] == 184
    assert review["semantic_review_count"] == 184
    assert review["grade_change_count"] == 24
    assert all(row["positive_and_negative_checked"] for row in review["records"])
    assert all(row["full_lifecycle_closed"] for row in review["records"])
