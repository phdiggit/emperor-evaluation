from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.i5b_institution_retrieval import (
    evaluate_i5b_institution_retrieval,
    generate_i5b_institution_retrieval_report,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "i5b-institution-retrieval-contract.yml"
REPORT_PATH = (
    ROOT
    / "eval"
    / "i5b_test_set_portfolio"
    / "institution_retrieval_regression.json"
)


def _contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_lishimin_institution_is_recalled_without_chapter_answer_hint() -> None:
    report = evaluate_i5b_institution_retrieval(_contract())

    assert report["status"] == "institution_candidate_recalled"
    assert report["query"]["chapter_title_supplied"] is False
    assert report["query"]["passage_locator_supplied"] is False
    assert report["query"]["institution_answer_supplied"] is False
    assert set(report["axis_coverage"]) == {
        "person_event",
        "ruler_institution",
        "cross_person_cluster",
    }
    assert all(row["observation_count"] > 0 for row in report["axis_coverage"].values())
    assert all(row["passed"] is True for row in report["candidate"]["gate_results"].values())
    assert report["candidate"]["disposition"] == "candidate_only"
    assert len(report["candidate"]["operation_years"]) >= 2
    assert len(report["candidate"]["expression_actors"]) >= 2
    assert report["candidate"]["formal_subjects"]

    summary = report["summary"]
    assert summary["database_write_count"] == 0
    assert summary["facts_accepted"] == 0
    assert summary["factor_choices_created"] == 0
    assert summary["score_contributions_created"] == 0
    assert summary["formal_scoring_allowed"] is False


def test_missing_cross_person_axis_is_rejected() -> None:
    contract = _contract()
    contract["retrieval_axes"]["cross_person_cluster"] = []

    with pytest.raises(ValueError, match="制度检索轴缺少观察"):
        evaluate_i5b_institution_retrieval(contract)


def test_report_is_deterministic_and_matches_checked_in_artifact(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    first = generate_i5b_institution_retrieval_report(CONTRACT_PATH, output)
    second = generate_i5b_institution_retrieval_report(CONTRACT_PATH, output)

    assert first == second
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert json.loads(REPORT_PATH.read_text(encoding="utf-8")) == first
