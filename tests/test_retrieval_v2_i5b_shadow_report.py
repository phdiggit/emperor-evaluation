from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_i5b_shadow_report as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_shadow_report_counts_secondary_candidates_and_quality_risks(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    person_dir = run_root / "刘邦"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(
        candidates_path,
        {
            "candidate_slices": [
                {
                    "slice_code": "SLI-1",
                    "text": "高祖拜韩信为左丞相，使击魏，又北举燕赵。",
                }
            ]
        },
    )
    write_json(
        judge_path,
        {
            "claims": [
                {
                    "claim_code": "CLM-1",
                    "object_name": "韩信",
                    "direction": "positive",
                    "claim_summary": "刘邦任韩信为左丞相击魏。",
                    "source_slice_refs": ["SLI-1"],
                    "fact_payload": {
                        "main_actor": "刘邦",
                        "target_object": "韩信",
                        "action_type": "任命",
                        "task_or_office": "左丞相击魏",
                        "event_scope": "军事",
                        "outcome_summary": "北举燕赵",
                        "outcome_polarity": "positive",
                    },
                    "evidence_spans": [
                        {"span_type": "action", "source_slice_ref": "SLI-1", "text": "拜韩信为左丞相"},
                        {"span_type": "outcome", "source_slice_ref": "SLI-1", "text": "北举燕赵"},
                    ],
                    "claim_completeness": {
                        "has_action_span": True,
                        "has_object_span": True,
                        "has_outcome_span": True,
                        "outcome_same_event_chain": True,
                        "needs_source_extension": False,
                    },
                },
                {
                    "claim_code": "CLM-2",
                    "object_name": "卢绾",
                    "direction": "negative",
                    "claim_summary": "卢绾被废。",
                    "source_slice_refs": ["SLI-MISSING"],
                    "evidence_spans": [
                        {"span_type": "outcome", "source_slice_ref": "SLI-MISSING", "text": "卢绾被废"}
                    ],
                },
            ],
            "primary_bindings": [
                {
                    "claim_code": "CLM-2",
                    "direction": "negative",
                    "predicate": "revoked_or_failed_delegate",
                    "usable_for_scoring_cluster": True,
                }
            ],
            "secondary_binding_candidates": [
                {"claim_code": "CLM-1", "rule_code": "appointment_trust", "confidence": 0.8},
                {
                    "claim_code": "CLM-1",
                    "rule_code": "delegation",
                    "confidence": 0.9,
                    "candidate_payload": {
                        "scoring_candidate": True,
                        "usable_for_scoring_cluster": True,
                        "delegation_chain": {
                            "has_authorization_or_office": True,
                            "has_named_delegate": True,
                            "has_task_or_responsibility": True,
                            "has_same_chain_outcome": True,
                        },
                        "candidate_role": "delegated_actor",
                        "delegation_domain": "military",
                        "same_chain_outcome_summary": "刘邦拜韩信击魏，北举燕赵。",
                    },
                },
                {
                    "claim_code": "CLM-2",
                    "rule_code": "delegation",
                    "confidence": 0.5,
                    "candidate_payload": {
                        "scoring_candidate": True,
                        "usable_for_scoring_cluster": True,
                        "delegation_chain": {
                            "has_authorization_or_office": True,
                            "has_named_delegate": True,
                            "has_task_or_responsibility": False,
                            "has_same_chain_outcome": False,
                        },
                        "candidate_role": "military_delegate",
                        "delegation_domain": "campaign",
                    },
                },
                {
                    "claim_code": "CLM-2",
                    "rule_code": "power_control",
                    "candidate_payload": {"hint_status": "future_rule_hint"},
                },
            ],
        },
    )
    write_json(
        run_root / "summary.json",
        {
            "capture_mode": "i5b_wide_shadow",
            "formal_consumption_source": False,
            "total_elapsed_seconds": 12.3,
            "totals": {"usage": {"input_tokens": 100, "output_tokens": 20}},
            "people": [
                {
                    "name": "刘邦",
                    "capture_mode": "i5b_wide_shadow",
                    "formal_consumption_source": False,
                    "candidate_slices": 1,
                    "fetch_error_count": 0,
                    "candidate_coverage_gap_count": 0,
                    "judge_coverage_gap_count": 1,
                    "judge_anomaly_block_count": 0,
                    "judge_anomaly_warning_count": 0,
                    "files": {
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ],
        },
    )
    (run_root / "run_events.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event": "target_start", "emperor_name": "刘邦", "elapsed_seconds": 1}, ensure_ascii=False),
                json.dumps(
                    {
                        "event": "taskgen_object_source_presearch_start",
                        "emperor_name": "刘邦",
                        "elapsed_seconds": 2,
                        "max_objects": 12,
                        "pages_per_object": 1,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "event": "taskgen_object_source_presearch_done",
                        "emperor_name": "刘邦",
                        "elapsed_seconds": 4,
                        "elapsed_seconds_stage": 2,
                        "hit_count": 9,
                    },
                    ensure_ascii=False,
                ),
                json.dumps({"event": "target_done", "emperor_name": "刘邦", "elapsed_seconds": 6}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = tool.build_report(run_root)

    assert report["shadow_contract"]["valid"] is True
    assert report["totals"]["formal_secondary_candidate_count"] == 3
    assert report["totals"]["future_hint_count"] == 1
    assert report["totals"]["candidate_status_counts"]["current_rule_candidate"] == 3
    assert report["totals"]["candidate_status_counts"]["future_rule_hint"] == 1
    assert report["totals"]["candidate_item_counts"]["I5B"] == 3
    assert report["totals"]["candidate_lane_counts"]["delegation"] == 2
    assert report["totals"]["candidate_route_problem_count"] == 0
    assert report["totals"]["delegation_candidate_count"] == 2
    assert report["totals"]["delegation_scoring_candidate_count"] == 2
    assert report["totals"]["delegation_scoring_candidate_invalid_count"] == 1
    assert report["totals"]["delegation_review_candidate_count"] == 0
    assert report["totals"]["unknown_source_slice_refs"] == 1
    assert report["totals"]["negative_disposition_risk_count"] == 1
    assert report["totals"]["claims_with_fact_payload"] == 1
    assert report["totals"]["claims_with_political_action_v1"] == 0
    assert report["totals"]["claims_with_evidence_spans"] == 2
    assert report["totals"]["claims_with_claim_completeness"] == 1
    assert report["totals"]["evidence_span_count"] == 3
    assert report["totals"]["complete_outcome_chain_claims"] == 1
    assert report["totals"]["span_unknown_source_slice_ref"] == 1
    assert report["people"][0]["elapsed_seconds"] == 5
    assert report["people"][0]["object_source_presearch_pages_per_object"] == 1
    assert report["people"][0]["object_source_presearch_hit_count"] == 9
    assert report["people"][0]["delegation_scoring_candidate_invalid_examples"][0]["claim_code"] == "CLM-2"
    assert any(row["severity"] == "block" for row in report["recommendations"])
    assert any("fact_payload" in row["message"] for row in report["recommendations"])
    assert any("evidence_spans" in row["message"] for row in report["recommendations"])
    assert any("delegation scoring candidates" in row["message"] for row in report["recommendations"])


def test_shadow_report_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    run_root = tmp_path / "run"
    person_dir = run_root / "曹操"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(candidates_path, {"candidate_slices": []})
    write_json(judge_path, {"claims": [], "primary_bindings": [], "secondary_binding_candidates": []})
    write_json(
        run_root / "summary.json",
        {
            "capture_mode": "i5b_wide_shadow",
            "formal_consumption_source": False,
            "people": [
                {
                    "name": "曹操",
                    "capture_mode": "i5b_wide_shadow",
                    "formal_consumption_source": False,
                    "files": {
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ],
        },
    )

    assert tool.main(["--run-root", str(run_root)]) == 0
    out = capsys.readouterr().out

    assert "i5b_shadow_report.json" in out
    assert (run_root / "i5b_shadow_report.json").exists()
    assert "# I5B-wide shadow pilot report" in (run_root / "i5b_shadow_report.md").read_text(encoding="utf-8")


def test_consumed_pack_review_uses_tool_chain(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(tool, "load_env_file", lambda path: calls.append(f"env:{path}") or ["DSN"])
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://review")
    monkeypatch.setattr(
        tool,
        "fetch_consumed_candidate_lane_probe",
        lambda **_: {
            "pack": [
                {
                    "pack_code": "SPK",
                    "status": "draft",
                    "coverage_status": "passed",
                    "emperor_name": "刘邦",
                }
            ],
            "candidate_counts": [
                {
                    "hint_status": "formal_candidate",
                    "candidate_item_code": "<blank>",
                    "candidate_lane": "team_building",
                    "candidate_rule_code": "team_building",
                    "has_candidate_contract_rule": True,
                    "n": 2,
                },
                {
                    "hint_status": "future_rule_hint",
                    "candidate_item_code": "<blank>",
                    "candidate_lane": "power_control",
                    "candidate_rule_code": "power_control",
                    "has_candidate_contract_rule": False,
                    "n": 1,
                },
            ],
            "future_hint_resolved_count": 0,
            "required_facts_shapes": [{"json_type": "object", "n": 3}],
            "sample_future_hints": [],
        },
    )

    def fake_promoter(**kwargs):
        assert kwargs["source_pack_codes"] == ("SPK",)
        assert kwargs["execute"] is False
        return {
            "executed": False,
            "totals": {"candidate_rows": 3, "promotions": 2, "skipped": 1},
            "promoted_by_rule": {"team_building": 2},
            "skipped_by_reason": {"future_rule_hint": 1},
            "promotions": [],
            "skipped": [],
        }

    def fake_scorer(**kwargs):
        assert kwargs["source_pack_codes"] == ("SPK",)
        assert kwargs["execute"] is False
        return {
            "ok": True,
            "executed": False,
            "totals": {"judgments": 1},
            "clusters": [
                {
                    "target_code": "TGT",
                    "emperor_name": "刘邦",
                    "positive_signal": "1.000",
                    "negative_signal": "0.000",
                }
            ],
        }

    monkeypatch.setattr(tool, "run_promoter", fake_promoter)
    monkeypatch.setattr(tool, "apply_rule_scores", fake_scorer)

    report = tool.build_consumed_pack_review(
        env_file=Path(".env"),
        dsn_env="DSN",
        source_pack_code="SPK",
    )

    assert report["command"] == "consumed-pack-review"
    assert report["totals"]["candidate_count"] == 3
    assert report["totals"]["promoter_promotions"] == 2
    assert report["safety_checks"]["source_pack_is_draft"] is True
    assert report["safety_checks"]["future_hints_not_resolved"] is True
    assert report["safety_checks"]["all_scorers_ok"] is True
    assert set(report["scorer_dry_run"]) == set(tool.I5B_REVIEW_RULES)


def test_consumed_pack_review_cli_writes_json_and_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = {
        "command": "consumed-pack-review",
        "pack_code": "SPK",
        "source_pack": {"status": "draft", "coverage_status": "passed"},
        "totals": {"candidate_count": 1},
        "candidate_lane_probe": {
            "candidate_counts": [
                {
                    "hint_status": "future_rule_hint",
                    "candidate_item_code": "<blank>",
                    "candidate_lane": "power_control",
                    "candidate_rule_code": "power_control",
                    "has_candidate_contract_rule": False,
                    "n": 1,
                }
            ],
            "future_hint_resolved_count": 0,
        },
        "promoter_dry_run": {"totals": {}},
        "scorer_dry_run": {},
        "safety_checks": {"future_hints_not_resolved": True},
    }
    monkeypatch.setattr(tool, "build_consumed_pack_review", lambda **_: payload)
    output_json = tmp_path / "review.json"
    output_md = tmp_path / "review.md"

    assert tool.main(["--source-pack-code", "SPK", "--output-json", str(output_json), "--output-md", str(output_md)]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["command"] == "consumed-pack-review"
    assert "# retrieval_v2 consumed shadow review" in output_md.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_shadow_report_accepts_item_wide_capture_mode(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    person_dir = run_root / "刘邦"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(candidates_path, {"candidate_slices": []})
    write_json(judge_path, {"claims": [], "primary_bindings": [], "secondary_binding_candidates": []})
    write_json(
        run_root / "summary.json",
        {
            "capture_mode": "i5b_item_wide_shadow",
            "formal_consumption_source": False,
            "people": [
                {
                    "name": "刘邦",
                    "capture_mode": "i5b_item_wide_shadow",
                    "formal_consumption_source": False,
                    "files": {
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ],
        },
    )

    report = tool.build_report(run_root)

    assert report["shadow_contract"]["valid"] is True
    assert report["shadow_contract"]["capture_mode"] == "i5b_item_wide_shadow"


def test_shadow_report_summarizes_personnel_political_wide_contract(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    person_dir = run_root / "朱元璋"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(
        candidates_path,
        {
            "candidate_slices": [
                {
                    "slice_code": "SLI-1",
                    "text": "太祖命徐达为大将军，北伐定中原。",
                }
            ]
        },
    )
    write_json(
        judge_path,
        {
            "claims": [
                {
                    "claim_code": "CLM-1",
                    "object_name": "徐达",
                    "direction": "positive",
                    "claim_summary": "朱元璋命徐达为大将军北伐并定中原。",
                    "source_slice_refs": ["SLI-1"],
                    "fact_payload": {
                        "fact_schema": "political_action_v1",
                        "actor": "朱元璋",
                        "object": "徐达",
                        "action_type": "授权",
                        "event_scope": "军事",
                        "office_or_domain": "大将军北伐",
                        "outcome": "定中原",
                        "cost_or_damage": "",
                        "time_context": "明初",
                        "source_span_refs": ["SLI-1"],
                        "confidence": 0.9,
                        "completeness": {
                            "has_actor": True,
                            "has_object": True,
                            "has_action": True,
                            "has_outcome": True,
                            "same_event_chain": True,
                            "needs_source_extension": False,
                        },
                    },
                    "evidence_spans": [
                        {"span_type": "action", "source_slice_ref": "SLI-1", "text": "命徐达为大将军"},
                        {"span_type": "outcome", "source_slice_ref": "SLI-1", "text": "定中原"},
                    ],
                    "claim_completeness": {
                        "has_action_span": True,
                        "has_object_span": True,
                        "has_outcome_span": True,
                        "outcome_same_event_chain": True,
                        "needs_source_extension": False,
                    },
                }
            ],
            "primary_bindings": [],
            "secondary_binding_candidates": [
                {
                    "claim_code": "CLM-1",
                    "rule_code": "delegation",
                    "candidate_item_code": "I5B",
                    "candidate_lane": "delegation",
                    "hint_status": "current_rule_candidate",
                    "direction": "positive",
                    "required_facts_present": ["actor", "object", "action_type", "outcome", "source_span_refs"],
                    "candidate_payload": {
                        "hint_status": "current_rule_candidate",
                        "scoring_candidate": True,
                        "usable_for_scoring_cluster": True,
                        "delegation_chain": {
                            "has_authorization_or_office": True,
                            "has_named_delegate": True,
                            "has_task_or_responsibility": True,
                            "has_same_chain_outcome": True,
                        },
                        "candidate_role": "delegated_actor",
                        "delegation_domain": "military",
                    },
                },
                {
                    "claim_code": "CLM-1",
                    "rule_code": "military_frontier_result",
                    "candidate_item_code": "I3",
                    "candidate_lane": "military_frontier_result",
                    "hint_status": "future_rule_hint",
                    "direction": "positive",
                    "required_facts_present": ["actor", "object", "action_type", "outcome", "source_span_refs"],
                    "candidate_payload": {"hint_status": "future_rule_hint"},
                },
            ],
        },
    )
    write_json(
        run_root / "summary.json",
        {
            "capture_mode": "personnel_political_wide_shadow",
            "capture_profile": "personnel_political_wide",
            "fact_schema": "political_action_v1",
            "candidate_route_table_version": "personnel_political_v0_1",
            "formal_consumption_source": False,
            "people": [
                {
                    "name": "朱元璋",
                    "capture_mode": "personnel_political_wide_shadow",
                    "formal_consumption_source": False,
                    "candidate_slices": 1,
                    "files": {
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ],
        },
    )

    report = tool.build_report(run_root)

    assert report["shadow_contract"]["valid"] is True
    assert report["shadow_contract"]["capture_profile"] == "personnel_political_wide"
    assert report["shadow_contract"]["fact_schema"] == "political_action_v1"
    assert report["totals"]["claims_with_political_action_v1"] == 1
    assert report["totals"]["claims_missing_political_action_fact_fields"] == 0
    assert report["totals"]["political_action_source_span_ref_missing"] == 0
    assert report["totals"]["political_action_complete_outcome_claims"] == 1
    assert report["totals"]["candidate_status_counts"]["current_rule_candidate"] == 1
    assert report["totals"]["candidate_status_counts"]["future_rule_hint"] == 1
    assert report["totals"]["candidate_item_counts"]["I3"] == 1
    assert report["totals"]["candidate_item_counts"]["I5B"] == 1
    assert report["totals"]["candidate_lane_counts"]["military_frontier_result"] == 1
    assert report["totals"]["candidate_route_problem_count"] == 0
