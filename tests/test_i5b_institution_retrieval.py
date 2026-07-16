from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.i5b_institution_retrieval import (
    evaluate_i5b_institution_retrieval,
    generate_i5b_institution_retrieval_report,
)
from emperor_v4.evaluation.i5b_candidate_retrieval_gate import (
    build_cross_rule_orphan_audit,
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


def test_report_is_deterministic(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    first = generate_i5b_institution_retrieval_report(CONTRACT_PATH, output)
    second = generate_i5b_institution_retrieval_report(CONTRACT_PATH, output)

    assert first == second
    assert json.loads(output.read_text(encoding="utf-8")) == first


def test_weizheng_cross_rule_passage_blocks_premature_talent_freeze() -> None:
    audit = build_cross_rule_orphan_audit(
        target_rule_code="talent_discovery",
        routed_passages=[
            {
                "passage_ref": "SP-D826159D11DB463515E7",
                "accepted_rules": ["appointment_delegation"],
                "eligible_rules": ["appointment_delegation", "talent_discovery"],
            }
        ],
        candidate_passage_refs=[],
    )

    assert audit["status"] == "complete"
    assert audit["unresolved_orphan_count"] == 1
    assert audit["unresolved_orphans"] == [
        {
            "passage_ref": "SP-D826159D11DB463515E7",
            "accepted_rules": ["appointment_delegation"],
            "eligible_rules": ["appointment_delegation", "talent_discovery"],
            "reason": "eligible_cross_rule_passage_missing_candidate_binding",
        }
    ]


def test_cross_rule_orphan_is_closed_only_by_target_candidate_binding() -> None:
    routed = [
        {
            "passage_ref": "SP-D826159D11DB463515E7",
            "accepted_rules": ["appointment_delegation"],
            "eligible_rules": ["appointment_delegation", "talent_discovery"],
        }
    ]
    first = build_cross_rule_orphan_audit(
        target_rule_code="talent_discovery",
        routed_passages=routed,
        candidate_passage_refs=["SP-D826159D11DB463515E7"],
    )
    second = build_cross_rule_orphan_audit(
        target_rule_code="talent_discovery",
        routed_passages=routed,
        candidate_passage_refs=["SP-D826159D11DB463515E7"],
    )

    assert first == second
    assert first["unresolved_orphan_count"] == 0
    assert first["database_write_count"] == 0
    assert first["model_call_count"] == 0
