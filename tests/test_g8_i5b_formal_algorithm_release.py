from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from export.dimension_adapters.i5b_people_delegation.formal_algorithm import (  # noqa: E402
    FORMAL_ALGORITHM_VERSION,
    FORMAL_GRADE_ENUM,
    compute_formal_algorithm_result,
)
from scripts.platform import g8_i5b_formal_algorithm_release as g8  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_formal_algorithm_uses_v3_2_nine_grade_enum_and_45_point_ranges() -> None:
    result = compute_formal_algorithm_result(
        {
            "auto_band_direction": "高位强正，上探极正候选",
            "confidence": "high_mid",
            "coverage_dimension_count": 3,
            "positive_three_core_coverage": True,
            "negative_boundary_tier": "weak_to_medium",
            "negative_boundary_blocking": False,
            "has_extreme_negative_core": False,
        }
    )

    assert result["algorithm_version"] == FORMAL_ALGORITHM_VERSION
    assert result["formal_grade_enum"] == list(FORMAL_GRADE_ENUM)
    assert len(result["formal_grade_enum"]) == 9
    assert result["formal_grade"] == "历史极限"
    assert result["score_range_45"] == "43.20—44.10"
    assert result["formal_score_value_suppressed_until_g9"] is True
    assert result["formal_ranking_suppressed_until_g9"] is True
    assert result["person_specific_override_allowed"] is False
    assert result["manual_final_grade_allowed"] is False
    assert result["manual_final_score_allowed"] is False

    negative_result = compute_formal_algorithm_result({"auto_band_direction": "强负"})
    assert negative_result["formal_grade"] == "极差"
    assert negative_result["score_range_45"] == "0.00 <= 分值 < 13.50"


def test_algorithm_report_releases_algorithm_but_blocks_g9_outputs(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G8 algorithm report")

    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g8.build_algorithm_report()
    markdown = g8.render_algorithm_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["package_version"] == "g8-i5b-formal-algorithm-release-v1"
    assert report["gate_status"] == "approved_algorithm_released"
    assert report["g7_rule_change_pr"] == 308
    assert report["g7_rule_change_merge_commit"] == "ae5d9730ab716c110e521b0bf9076a4470e0123c"
    assert report["score_framework"]["positive_benefit_total"] == 1500
    assert report["score_framework"]["positive_item_weights"]["第六项 关键历史决策能力"] == 180
    assert report["score_framework"]["sixth_item_weights"] == {
        "A 重大节点判断": 60,
        "B 风险控制与止损": 50,
        "C 长期战略眼光": 70,
    }
    assert report["formal_grade_enum"] == list(FORMAL_GRADE_ENUM)
    assert report["release_state"] == {
        "formal_algorithm_released": True,
        "formal_score_values_released": False,
        "formal_ranking_released": False,
    }
    assert report["followup_gate_boundaries"]["formal_score_values_or_ranking_publication"] == "G9"
    assert "formal_score_values_released: `false`" in markdown
    assert "positive_benefit_total: `1500`" in markdown


def test_active_scoring_standard_uses_1500_total_and_not_1440_current_cap() -> None:
    scoring_standard = (ROOT / "docs" / "皇帝综合评价体系评分标准.md").read_text(encoding="utf-8")
    project_rules = (ROOT / "docs" / "项目总纲" / "总规则.md").read_text(encoding="utf-8")

    assert "正收益总盘1500分" in scoring_standard
    assert "| 第六项 | 关键历史决策能力 | 180 |" in scoring_standard
    assert "| **正收益合计** |  | **1500** |" in scoring_standard
    assert "> 260 + 460 + 250 + 180 + 170 + 180 = 1500" in scoring_standard
    assert "本阶段按 **正收益上限1440分** 执行" not in scoring_standard
    assert "正收益合计** |  | **1440" not in scoring_standard
    assert "V3.2 已定义 1500 正收益总盘" in project_rules
    assert "V3.2 已定义 1440 正收益总盘" not in project_rules


def test_impact_report_is_aggregate_and_suppresses_person_level_values() -> None:
    report = g8.build_impact_report(
        [
            {
                "auto_band_direction": "高位强正，上探极正候选",
                "confidence": "high",
                "coverage_dimension_count": 3,
                "positive_three_core_coverage": True,
                "negative_boundary_tier": "none",
                "negative_boundary_blocking": False,
                "has_extreme_negative_core": False,
            },
            {
                "auto_band_direction": "强正受压制，不上探极正",
                "confidence": "medium_high",
                "coverage_dimension_count": 2,
                "positive_three_core_coverage": False,
                "negative_boundary_tier": "medium_to_strong",
                "negative_boundary_blocking": True,
                "has_extreme_negative_core": False,
            },
        ]
    )

    assert report["mode"] == "impact-report"
    assert report["evaluated_person_count"] == 2
    assert report["formal_grade_distribution"]["历史极限"] == 1
    assert report["formal_grade_distribution"]["良好"] == 1
    assert report["person_level_rows_suppressed_until_g9"] is True
    assert report["formal_score_values_released"] is False
    assert report["formal_ranking_released"] is False
    assert report["contains_person_formal_score_values"] is False
    assert report["contains_ranking_or_leaderboard"] is False


def test_cli_modes_emit_json_and_markdown(capsys) -> None:
    assert g8.main(["--algorithm-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "algorithm-report"

    assert g8.main(["--algorithm-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G8 Fifth Item B Formal Algorithm Release" in markdown


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
