from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_recall_feedback as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_feedback_overlay_buckets_terms_by_consumption_result(tmp_path: Path) -> None:
    feedback_path = tmp_path / "feedback.jsonl"
    write_jsonl(
        feedback_path,
        [
            {
                "claim_id": "CLM-1",
                "recall_terms": ["宠任"],
                "consumption_status": "accepted",
                "candidate_lane": "I5B.appointment_delegation",
            },
            {
                "claim_id": "CLM-2",
                "recall_terms": ["宠任"],
                "consumption_status": "accepted",
                "candidate_lane": "I5B.appointment_delegation",
            },
            {
                "claim_id": "CLM-3",
                "recall_terms": ["宠任"],
                "consumption_status": "accepted",
                "candidate_lane": "I5B.appointment_delegation",
            },
            {
                "claim_id": "CLM-4",
                "matched_rule_terms": ["信欲反"],
                "consumption_status": "rejected",
                "reject_reason": "context_only",
            },
            {
                "claim_id": "CLM-5",
                "matched_rule_terms": ["信欲反"],
                "consumption_status": "rejected",
                "reject_reason": "context_only",
            },
            {
                "claim_id": "CLM-6",
                "matched_rule_terms": ["分兵"],
                "consumption_status": "rejected",
                "reject_reason": "context_only",
            },
            {
                "claim_id": "CLM-7",
                "matched_rule_terms": ["分兵"],
                "consumption_status": "rejected",
                "reject_reason": "context_only",
            },
            {
                "claim_id": "CLM-8",
                "source_terms": ["未分类词"],
                "consumption_status": "accepted",
                "factor_hint_overridden": True,
                "reject_reason": "wrong_lane",
            },
            {"claim_id": "CLM-9", "consumption_status": "accepted"},
        ],
    )

    report = tool.build_feedback_overlay_report(
        [feedback_path],
        min_feedback=2,
        min_accept_rate=0.6,
        max_reject_rate=0.25,
        min_demote_reject_rate=0.75,
    )

    suggestions = report["suggestions"]
    assert report["inputs"]["feedback_row_count"] == 9
    assert report["inputs"]["rows_without_terms"] == 1
    assert [row["term"] for row in suggestions["promote_next_run_terms"]] == ["宠任"]
    assert [row["term"] for row in suggestions["demote_terms"]] == ["信欲反"]
    assert [row["term"] for row in suggestions["context_only_terms"]] == ["分兵"]
    assert [row["term"] for row in suggestions["needs_human_review_terms"]] == ["未分类词"]
    assert suggestions["promote_next_run_terms"][0]["policy"]["profile_action"] == "append_rule_term"
    assert suggestions["context_only_terms"][0]["policy"]["profile_action"] == "context_only"


def test_feedback_overlay_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    feedback_path = tmp_path / "feedback.jsonl"
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    write_jsonl(
        feedback_path,
        [
            {"claim_id": "CLM-1", "recall_terms": ["谋反"], "consumption_status": "accepted"},
            {"claim_id": "CLM-2", "recall_terms": ["谋反"], "consumption_status": "accepted"},
            {"claim_id": "CLM-3", "recall_terms": ["谋反"], "consumption_status": "supporting_only"},
        ],
    )

    assert (
        tool.main(
            [
                "--feedback-jsonl",
                str(feedback_path),
                "--min-feedback",
                "2",
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
            ]
        )
        == 0
    )

    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert output_json.exists()
    assert "# retrieval_v2 recall feedback overlay report" in output_md.read_text(encoding="utf-8")
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["suggestions"]["promote_next_run_terms"][0]["term"] == "谋反"


def test_feedback_policy_filters_single_char_tokens_and_office_context() -> None:
    assert tool.feedback_term_policy("将")["policy_group"] == "feedback_token_noise"
    assert tool.feedback_term_policy("相")["profile_action"] == "reject_term"
    assert tool.feedback_term_policy("丞相")["policy_group"] == "feedback_context"
    assert tool.feedback_term_policy("都督")["profile_action"] == "context_only"
    assert tool.feedback_term_policy("宠任")["profile_action"] == "append_rule_term"
    assert tool.feedback_term_policy("谋反")["profile_action"] == "conditional_term"


def test_source_refinement_feedback_is_excluded_from_recall_overlay(tmp_path: Path) -> None:
    feedback_path = tmp_path / "feedback.jsonl"
    write_jsonl(
        feedback_path,
        [
            {
                "claim_id": "CLM-HWY",
                "emperor_name": "朱元璋",
                "object_name": "胡惟庸",
                "recall_terms": ["谋反", "伏诛"],
                "candidate_lane": "I5B.appointment_delegation",
                "rule_code": "appointment_delegation",
                "consumption_status": "supporting_only",
                "reject_reason": "weak_same_chain",
                "gap_type": "source_missing",
                "gap_reason": "annals_only_disposition_without_authorization_abuse_chain",
                "required_source_type": ["object_biography", "chronicle_cross_check"],
                "missing_material": ["任内权责滥用", "授权链条失控"],
                "recommended_action": "run_object_source_refiner",
                "do_not_add_recall_terms": True,
            },
            {
                "claim_id": "CLM-TH",
                "emperor_name": "朱元璋",
                "object_name": "汤和",
                "recall_terms": ["征南", "提督海运"],
                "candidate_lane": "I5B.appointment_delegation",
                "rule_code": "appointment_delegation",
                "consumption_status": "supporting_only",
                "reject_reason": "object_claim_undercoverage",
                "gap_type": "object_claim_undercoverage",
                "gap_reason": "biography_has_multiple_political_action_facts_not_split",
                "queue": "source_pack_refinement",
                "missing_material": ["征南", "提督海运", "镇北平"],
                "recommended_action": "run_object_source_refiner",
                "do_not_add_recall_terms": True,
            },
            {
                "claim_id": "CLM-OK-1",
                "recall_terms": ["宠任"],
                "consumption_status": "accepted",
                "gap_type": "not_a_gap",
            },
            {
                "claim_id": "CLM-OK-2",
                "recall_terms": ["宠任"],
                "consumption_status": "accepted",
                "gap_type": "not_a_gap",
            },
        ],
    )

    report = tool.build_feedback_overlay_report(
        [feedback_path],
        min_feedback=2,
        min_accept_rate=0.6,
        max_reject_rate=0.25,
        min_demote_reject_rate=0.75,
    )

    assert report["inputs"]["excluded_from_overlay_count"] == 2
    assert report["inputs"]["rows_without_terms"] == 2
    assert report["summary"]["gap_type_counts"] == {"not_a_gap": 2, "object_claim_undercoverage": 1, "source_missing": 1}
    assert report["summary"]["source_missing_rows"] == 1
    assert report["summary"]["source_refinement_rows"] == 2
    assert [row["term"] for row in report["terms"]] == ["宠任"]
    assert [row["term"] for row in report["suggestions"]["promote_next_run_terms"]] == ["宠任"]
    assert report["source_gap_feedback"]["rows"][0]["object_name"] == "胡惟庸"
    assert report["source_gap_feedback"]["rows"][0]["recommended_action"] == "run_object_source_refiner"
    assert report["source_gap_feedback"]["rows"][1]["object_name"] == "汤和"
    assert report["source_gap_feedback"]["rows"][1]["gap_type"] == "object_claim_undercoverage"
    assert report["source_gap_feedback"]["rows"][1]["queue"] == "source_pack_refinement"
