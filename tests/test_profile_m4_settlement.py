from __future__ import annotations

import copy

import pytest

from emperor_v4.evaluation.formal_json_store import load_json

from emperor_v4.evaluation.profile_m4_settlement import (
    AUDIT,
    FULL_POOL_REVIEW,
    HIGH_REVIEW,
    MARKDOWN,
    SETTLEMENT,
)
from emperor_v4.evaluation.profile_m4_verifier import verify, verify_payloads


def _load(path):
    return load_json(path)


def test_profile_m4_formal_settlement_passes_stable_verifier() -> None:
    result = verify()
    assert result["status"] == "PASS"


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
    assert all(row["positive_and_negative_checked"] for row in review["records"])
    assert all(row["all_scoring_parents_closed"] for row in review["records"])
    assert all(row["unclosed_observations_excluded_from_scoring"] for row in review["records"])


def test_profile_m4_overview_omits_shared_and_table_limitations() -> None:
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert "### 共用限制说明" not in markdown
    assert "| 序 | 人物 | 政权 | 实际权力窗口 | 档位 | 位置 | 雷达值 | 证据 | 输出 | 状态 | 父链 | 典型模式 |" in markdown
    assert "| 序 | 人物 | 政权 | 实际权力窗口 | 档位 | 位置 | 雷达值 | 证据 | 输出 | 状态 | 父链 | 典型模式 | 限制 |" not in markdown
    assert "边；疆；政；治" not in markdown
