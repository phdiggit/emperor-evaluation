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

from scripts.platform import g9_i5b_formal_publication_release as g9  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_g9_publication_report_releases_person_scores_and_ranking(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G9 publication report")

    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g9.build_current_publication_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["package_version"] == "g9-i5b-formal-publication-release-v1"
    assert report["gate_status"] == "approved_formal_scores_and_ranking_released"
    assert report["g9_approval_comment"] == 4809664701
    assert report["g8_release_pr"] == 309
    assert report["g8_release_merge_commit"] == "05c24d084fb36a15c2539d41a0e5a8445e32d035"
    assert report["score_framework"]["positive_benefit_total"] == 1500
    assert report["release_state"] == {
        "formal_algorithm_released": True,
        "formal_score_values_released": True,
        "formal_ranking_released": True,
        "contains_person_formal_score_values": True,
        "contains_ranking_or_leaderboard": True,
        "contains_stage_or_final_total_table": False,
    }
    assert report["deterministic_rerun_contract"]["person_specific_override_allowed"] is False
    assert report["deterministic_rerun_contract"]["manual_final_grade_allowed"] is False
    assert report["deterministic_rerun_contract"]["manual_final_score_allowed"] is False

    rows = report["publication_rows"]
    assert [row["person"] for row in rows] == ["李世民", "刘秀", "刘庄"]
    assert [row["formal_rank"] for row in rows] == [1, 2, 3]
    assert rows[0]["formal_score_value_45"] == "44.02"
    assert rows[1]["formal_score_value_45"] == "32.15"
    assert rows[2]["formal_score_value_45"] == "23.39"
    assert {row["manual_final_score_allowed"] for row in rows} == {False}
    assert report["remaining_gate_boundaries"]["destructive_cleanup"] == "G10"
    assert report["remaining_gate_boundaries"]["stage_or_final_total_table"] == "not_in_this_pr"


def test_g9_publication_markdown_and_cli(capsys) -> None:
    assert g9.main(["--publication-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "publication-report"
    assert report["release_state"]["formal_score_values_released"] is True

    assert g9.main(["--publication-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G9 Fifth Item B Formal Score And Ranking Publication" in markdown
    assert "formal_score_values_released: `true`" in markdown
    assert "| 1 | 李世民 | 历史极限 | 44.02 | 高位强正，上探极正候选 |" in markdown


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
