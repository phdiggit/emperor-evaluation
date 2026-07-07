from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_prompt_governance as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_root_report_measures_prompt_files_and_usage(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    (run_root / "target").mkdir(parents=True)
    (run_root / "target" / "judge_prompt.round0.JSH-R00-00.md").write_text("甲乙丙丁\n戊己", encoding="utf-8")
    (run_root / "target" / "alias_refiner_prompt.judge.round0.md").write_text("alias prompt", encoding="utf-8")
    (run_root / "target" / "notes.md").write_text("ignore", encoding="utf-8")
    write_json(
        run_root / "summary.json",
        {
            "totals": {
                "usage": {
                    "input_tokens": 123,
                    "output_tokens": 45,
                }
            }
        },
    )

    report = tool.run_root_report(run_root)

    assert report["report_type"] == "run_root_prompt_budget"
    assert report["usage"] == {"input_tokens": 123, "output_tokens": 45}
    assert report["totals"]["prompt_count"] == 2
    assert report["totals"]["prompt_count_by_kind"] == {"alias_refiner_prompt": 1, "judge_prompt": 1}
    assert report["prompts"][0]["path"].endswith("alias_refiner_prompt.judge.round0.md")
    assert any(row.get("sharded") is True for row in report["prompts"])


def test_candidates_prompt_report_builds_judge_prompt_budget(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.final.json"
    write_json(
        candidates_path,
        {
            "task_identity": {"rule_code": "appointment_delegation", "emperor_name": "李渊"},
            "target_profile": {"primary_name": "李渊"},
            "rule": {"rule_code": "appointment_delegation", "keywords": ["命"]},
            "coverage_matrix": {"rule_code": "appointment_delegation", "role_families": []},
            "object_seeds": [{"name": "李世民"}],
            "source_documents": [{"document_code": "DOC-1", "text": "高祖命秦王为元帅。"}],
            "candidate_slices": [
                {
                    "slice_code": "SLI-1",
                    "document_code": "DOC-1",
                    "object_name": "李世民",
                    "matched_rule_terms": ["命"],
                    "text": "高祖命秦王为元帅。",
                }
            ],
        },
    )

    report = tool.candidates_prompt_report(candidates_path)

    assert report["report_type"] == "candidate_prompt_budget"
    assert report["candidate_slice_count"] == 1
    assert report["object_seed_count"] == 1
    assert report["prompt"]["prompt_kind"] == "judge_prompt"
    assert report["prompt"]["chars"] > len("高祖命秦王为元帅。")
    assert report["prompt"]["rough_token_units_4chars"] > 0


def test_debt_template_names_migration_targets_not_case_terms() -> None:
    report = tool.debt_template()

    assert report["report_type"] == "prompt_debt_template"
    debt_codes = {row["debt_code"] for row in report["debt_items"]}
    assert "source_recall_terms_in_prompt" in debt_codes
    assert "source_discovery_profile" in json.dumps(report, ensure_ascii=False)
    assert "刘基" not in json.dumps(report, ensure_ascii=False)
    assert "总中书政" not in json.dumps(report, ensure_ascii=False)


def test_source_debt_report_classifies_prompt_migration_targets(tmp_path: Path) -> None:
    source = tmp_path / "prompt_source.py"
    source.write_text(
        "\n".join(
            [
                '"importance_hint 只用 nominal_light | real_duty | unknown"',
                '"appointment_delegation 召回优先级：优先抽取同链条收益 claim"',
                '"secondary_binding_candidates 必须写 candidate_lane 与 hint_status"',
                '"fact_payload 必须写 personnel_profile 和 power_control_profile"',
                '"刘基 只应进入一次性诊断，不得进入长期 prompt"',
            ]
        ),
        encoding="utf-8",
    )

    report = tool.source_debt_report(source)

    assert report["report_type"] == "source_prompt_debt_inventory"
    by_code = {row["debt_code"]: row for row in report["debt_items"]}
    assert by_code["case_term_in_prompt"]["severity"] == "block"
    assert by_code["source_recall_terms_in_prompt"]["preferred_location"] == "source_discovery_profile"
    assert by_code["finite_enum_verbatim"]["match_count"] == 1
    assert by_code["route_table_verbatim"]["match_count"] == 1
    assert by_code["profile_schema_verbatim"]["match_count"] == 1
    assert report["summary"]["debt_item_count_by_severity"]["block"] == 1


def test_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    run_root = tmp_path / "run"
    (run_root / "target").mkdir(parents=True)
    (run_root / "target" / "judge_prompt.round0.md").write_text("prompt", encoding="utf-8")
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"

    assert tool.main(["run-root", "--run-root", str(run_root), "--output-json", str(output_json), "--output-md", str(output_md)]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert output_json.exists()
    assert "# retrieval_v2 prompt governance report" in output_md.read_text(encoding="utf-8")


def test_cli_source_debt_writes_report(tmp_path: Path, capsys) -> None:
    source = tmp_path / "prompt_source.py"
    source.write_text('"召回优先级：高优先级候选不放进长期 prompt"', encoding="utf-8")
    output_json = tmp_path / "debt.json"
    output_md = tmp_path / "debt.md"

    assert (
        tool.main(
            [
                "source-debt",
                "--source",
                str(source),
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
    assert out["report_type"] == "source_prompt_debt_inventory"
    assert "source_recall_terms_in_prompt" in output_md.read_text(encoding="utf-8")
