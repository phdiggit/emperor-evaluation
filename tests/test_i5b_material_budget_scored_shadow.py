from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import yaml

from emperor_v4.eval import main as eval_main
from emperor_v4.evaluation.i5b_material_budget_scored_shadow import (
    _appointment_density,
    build_i5b_material_budget_shadow,
    render_i5b_material_budget_shadow_markdown,
    write_i5b_material_budget_shadow,
)
from emperor_v4.evaluation.i5b_appointment_responsibility_contract import (
    build_appointment_responsibility_projection,
    render_appointment_responsibility_markdown,
)
from emperor_v4.evaluation.i5b_scoring_policy import evaluate_i5b_scoring_policy


ROOT = Path(__file__).parents[1]
MANIFEST = (
    ROOT
    / "eval/i5b_team_building_historical_coverage/lishimin_material_budget_shadow_manifest_v1.yml"
)
RESPONSIBILITY_MANIFEST = (
    ROOT
    / "tests/fixtures/i5b_appointment_responsibility_contract.yml"
)


def _by_rule(report: dict) -> dict[str, dict]:
    return {row["rule_code"]: row for row in report["rules"]}


def test_policy_requires_gate_then_strongest_n_without_empty_slot_penalty() -> None:
    policy = yaml.safe_load(
        (ROOT / "config/i5b-scoring-policy.yml").read_text(encoding="utf-8")
    )
    report = evaluate_i5b_scoring_policy(policy)

    assert report["summary"]["settlement_budget_enabled"] is True
    assert policy["settlement_budget"]["numeric_top_k_selection_allowed_after_gate"] is True
    assert policy["settlement_budget"]["domain_representation_quota_allowed"] is False
    assert policy["settlement_budget"]["unfilled_budget_reduces_score"] is False
    assert policy["settlement_budget"]["context_labels_are_scoring_slots"] is False
    assert "channel_factor" not in policy["rules"]["talent_discovery"]
    assert policy["rules"]["appointment_delegation"]["appointment_effect"][
        "exceptional_success"
    ] == 1.8


def test_one_command_exports_full_ruler_scoring_detail(
    tmp_path: Path, capsys,
) -> None:
    assert eval_main(
        [
            "i5b-scoring-detail-export",
            "--ruler",
            "李世民",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    output_dir = tmp_path / "李世民"
    payload = json.loads(
        (output_dir / "scoring-detail.json").read_text(encoding="utf-8")
    )
    ruler = payload["selected_ruler_reports"][0]
    assert ruler["summary"]["historical_coverage_complete_rule_count"] == 5
    assert ruler["selection_summary"] == {
        "complete_five_rule_signal": True,
        "selected_rule_count": 5,
        "selected_rule_weighted_raw_signal": "7.248",
    }
    markdown = (output_dir / "scoring-detail.md").read_text(encoding="utf-8")
    assert "### 计入材料" in markdown
    assert "| 对象 | 实际计入信号 | 方向 | 材料分 |" in markdown
    assert "| 人物 | 计入正池 | 计入负池 |" in markdown
    assert "**反馈入口强度**" not in markdown
    assert "制度化反馈入口 (`institutionalized_feedback_entry`) =" not in markdown
    stdout = capsys.readouterr().out
    assert "历史覆盖：5/5" in stdout
    assert "五条rule加权raw signal：7.248" in stdout


def test_appointment_density_uses_competition_rank_for_ties() -> None:
    selected = [
        {"object_ref": "A", "material_magnitude": Decimal("2.5")},
        {"object_ref": "B", "material_magnitude": Decimal("2.5")},
        {"object_ref": "C", "material_magnitude": Decimal("1.0")},
    ]

    expected = Decimal("1.5") * (
        Decimal("2.5") + Decimal("2.5") + Decimal("1") / Decimal("3").sqrt()
    )
    assert _appointment_density(selected, "positive") == expected


def test_lishimin_budget_shadow_uses_original_aggregation_without_slots() -> None:
    report = build_i5b_material_budget_shadow(MANIFEST)
    rules = _by_rule(report)

    assert report["summary"]["weighted_raw_signal"] == "7.248086"
    assert report["summary"]["settled_event_positive_count"] == 11
    assert report["summary"]["settled_event_negative_count"] == 2
    assert report["summary"]["team_positive_member_count"] == 8
    assert report["summary"]["team_negative_member_count"] == 1
    assert rules["talent_discovery"]["rule_raw_net"] == "4.864200"
    assert rules["appointment_delegation"]["rule_raw_net"] == "9.823203"
    assert rules["team_building"]["rule_raw_net"] == "7.632074"
    assert rules["tolerate_talent"]["rule_raw_net"] == "5.995550"
    assert rules["anti_nepotism"]["rule_raw_net"] == "1.760000"
    assert all("slot_rows" not in rule for rule in report["rules"])
    assert report["amplitude_diagnostic"]["amplitude_change_recommended"] is None
    assert report["amplitude_diagnostic"]["cohort_ruler_count"] == 1
    assert report["amplitude_diagnostic"]["theoretical_positive_envelope"][
        "appointment_delegation"
    ] == "13.706742"


def test_appointment_uses_strongest_eligible_materials_without_domain_quota() -> None:
    appointment = _by_rule(build_i5b_material_budget_shadow(MANIFEST))[
        "appointment_delegation"
    ]
    selected_ids = {row["material_id"] for row in appointment["settled_materials"]}
    supporting_ids = {
        row["material_id"] for row in appointment["supporting_only_materials"]
    }

    assert {
        "MAT-LSM-LIJING-POS",
        "MAT-LSM-HOUJUNJI-POS",
        "MAT-LSM-LIJI-POS-V2",
    } <= selected_ids
    assert "MAT-LSM-MAZHOU-POS" in supporting_ids
    assert "MAT-LSM-FANGXUANLING-POS-V2" in supporting_ids
    assert "MAT-LSM-INSTITUTION-MERIT-STAFFING-POS" in supporting_ids
    assert appointment["eligible_candidate_count"] == 9
    assert all(
        row["selection_basis"] == "eligibility_gate_then_strongest_n"
        for row in appointment["settled_materials"]
    )
    assert appointment["positive_budget"] == 3
    assert appointment["negative_budget"] == 3

    by_id = {row["material_id"]: row for row in appointment["settled_materials"]}
    assert by_id["MAT-LSM-LIJING-POS"]["factor_option_codes"][
        "appointment_effect"
    ] == "exceptional_success"
    assert by_id["MAT-LSM-LIJING-POS"]["material_magnitude"] == "3.506580"
    assert by_id["MAT-LSM-HOUJUNJI-POS"]["material_magnitude"] == "2.922150"
    assert "李靖总帅链下" in by_id["MAT-LSM-HOUJUNJI-POS"]["judge_reason"]
    assert by_id["MAT-LSM-HOUJUNJI-NEG"]["factor_option_codes"][
        "appointment_effect"
    ] == "bounded_control_failure"
    assert by_id["MAT-LSM-HOUJUNJI-NEG"]["material_magnitude"] == "0.406560"
    assert "释放" in by_id["MAT-LSM-HOUJUNJI-NEG"]["fact"]


def test_unfilled_budget_is_neutral_and_team_is_one_window_unit() -> None:
    report = build_i5b_material_budget_shadow(MANIFEST)
    rules = _by_rule(report)
    anti = rules["anti_nepotism"]
    team = rules["team_building"]

    assert len(anti["settled_materials"]) == 2
    assert anti["positive_budget"] == 3
    assert anti["positive_signal"] == "1.760000"
    assert len(team["positive_members"]) == 8
    assert len(team["negative_members"]) == 1
    assert len(team["supporting_only_members"]) == 15


def test_report_is_deterministic_readable_and_byte_idempotent(tmp_path: Path) -> None:
    first = build_i5b_material_budget_shadow(MANIFEST)
    second = build_i5b_material_budget_shadow(MANIFEST)
    assert first == second

    markdown = render_i5b_material_budget_shadow_markdown(first)
    assert "不使用领域固定槽位" in markdown
    assert "未用满预算不扣分" in markdown
    assert "本报告不生成45分、tier或排名" in markdown
    assert "李绩" in markdown

    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    write_i5b_material_budget_shadow(
        manifest_path=MANIFEST,
        output_json=output_json,
        output_markdown=output_md,
    )
    before = (output_json.read_bytes(), output_md.read_bytes())
    write_i5b_material_budget_shadow(
        manifest_path=MANIFEST,
        output_json=output_json,
        output_markdown=output_md,
    )
    assert before == (output_json.read_bytes(), output_md.read_bytes())
    assert json.loads(output_json.read_text(encoding="utf-8"))["declarations"][
        "database_write_count"
    ] == 0


def test_appointment_responsibility_contract_supports_group_and_requires_operation(
    tmp_path: Path,
) -> None:
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "units": [
                    {
                        "assertion_drafts": [
                            {
                                "assertion_code": code,
                                "formal_acceptance_disposition": "accept",
                                "source_passage_ref": f"SP-{index}",
                            }
                            for index, code in enumerate(
                                (
                                    "ASTA-0CC2E92D5ADF147CDB73",
                                    "ASTA-86D457E43B573C460F6A",
                                    "ASTA-25258DD38813785B020A",
                                ),
                                start=1,
                            )
                        ]
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(RESPONSIBILITY_MANIFEST.read_text(encoding="utf-8"))
    manifest["formal_acceptance_source"] = str(acceptance)
    runtime_manifest = tmp_path / "responsibility.yml"
    runtime_manifest.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    report = build_appointment_responsibility_projection(runtime_manifest)

    assert report["summary"] == {
        "unit_count": 2,
        "eligible_material_count": 1,
        "insufficient_unit_count": 1,
    }
    material = report["materials"][0]
    assert material["subject_kind"] == "responsibility_group"
    assert material["subject"] == "房玄龄等中枢员额责任群体"
    assert material["material_magnitude"] == "1.439900"
    assert material["factor_option_codes"] == {
        "appointment_importance": "critical_national_or_long_term",
        "appointment_effect": "normal_success",
        "continuity_factor": "short_or_one_off",
        "attribution_factor": "direct",
        "source_factor": "complete_direct_chain",
        "context_factor": "core_mechanism_direct",
    }
    assert report["insufficient_units"][0]["missing_inputs"] == [
        "actual_operation_observation"
    ]
    markdown = render_appointment_responsibility_markdown(report)
    assert "具体受任者" not in report["insufficient_units"][0]["judge_reason"]
    assert "本报告不生成45分、tier或排名" in markdown
