from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

import pytest

from emperor_v4.evaluation.i5b_current_value_runner import (
    build_i5b_current_value,
    main as runner_main,
    render_scoring_detail_markdown,
)
from emperor_v4.eval import main as eval_main


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_value_chain_is_complete_and_shadow_only(ruler: str) -> None:
    report = build_i5b_current_value(ROOT / "eval/i5b_current_value" / ruler / "source-pack.json")

    assert report["status"] == "current_shadow_chain_complete"
    assert report["declarations"]["three_channel_materials_consumed"] is True
    assert report["declarations"]["linked_ruler_context_count"] > 0
    assert set(report["three_channel_input"]["channel_counts"]) == {
        "ruler_chronicle",
        "person_biography",
        "dynasty_governance",
    }
    assert report["declarations"]["episode_count"] > 0
    assert report["declarations"]["episode_count"] > report["declarations"]["rule_evidence_unit_count"]
    assert set(report["three_channel_disposition"]) == set(report["three_channel_input"]["channel_counts"])
    assert any(row["rule_code"] == "team_building" for row in report["rule_evidence_units"])
    assert report["declarations"]["database_write_count"] == 0
    assert report["declarations"]["formal_score_write_count"] == 0
    assert report["declarations"]["profile_material_coverage_complete"] is True
    assert report["declarations"]["profile_values_frozen"] is True
    assert report["declarations"]["profile_freeze_gate_passed"] is True
    assert report["declarations"]["formal_scoring_ready"] is False
    assert report["declarations"]["profile_member_with_open_gap_count"] == 0
    assert report["declarations"]["historical_outcome_cluster_count"] > 0
    assert report["declarations"]["campaign_outcome_count"] > 0
    assert report["declarations"]["governance_outcome_count"] > 0
    assert report["net_signal_status"] == "stable_profile_inputs"
    assert all(
        row["value_status"] == "frozen_after_complete_coverage"
        for row in report["profile_projection_review"]
    )
    assert all(not row["coverage_gaps"] for row in report["profile_projection_review"])
    assert report["declarations"]["score_45"] is None
    assert report["declarations"]["ranking"] is None
    assert report["net_signal"] == report["material_budget"]["summary"]["weighted_raw_signal"]
    assert {episode["episode_type"] for episode in report["episodes"]} >= {
        "ruler_person_governance_event", "campaign_outcome_chain", "governance_outcome_chain"
    }
    linked_episodes = [
        episode for episode in report["episodes"]
        if episode["lineage"].get("ruler_context_refs")
    ]
    assert linked_episodes
    assert all(
        any(link["relation"] == "corroborates" for link in episode["assertion_links"])
        for episode in linked_episodes
    )
    episode_member_refs = [
        member["member_ref"]
        for reu in report["rule_evidence_units"]
        for member in reu["members"]
        if member["member_type"] == "episode"
    ]
    assert len(episode_member_refs) > len(set(episode_member_refs))
    assert all(not any(key in episode for key in ("semantic_version", "evidence_version", "previous_status")) for episode in report["episodes"])


def test_source_pack_hash_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][0]["fact_summary"] += "篡改"
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        build_i5b_current_value(target)


def test_duplicate_settlement_event_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][1]["settlement_event_key"] = payload["materials"][0][
        "independence_key"
    ]
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="重复结算事件"):
        build_i5b_current_value(target)


def test_profile_values_cannot_freeze_before_material_coverage(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["profile_projection_gate"]["material_coverage_complete"] = False
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="材料覆盖未闭合"):
        build_i5b_current_value(target)


def test_profile_values_cannot_claim_complete_without_grade_registries(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["profile_projection_gate"]["material_coverage_complete"] = True
    payload["members"][0]["profile_review"]["talent_grade"]["rule_alignment"]["outcome_refs"] = []
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="仍存在 lineage 缺口"):
        build_i5b_current_value(target)


def test_governance_support_is_selected_by_current_result_quality() -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    team_reu = next(
        row for row in report["rule_evidence_units"] if row["rule_code"] == "team_building"
    )
    selected = {
        row["outcome_ref"]
        for row in team_reu["payload"]["governance_dispositions"]
        if row["disposition"] == "selected_team_result_support"
    }
    selected_labels = {
        row["canonical_label"]
        for row in report["historical_outcome_clusters"]
        if row["outcome_ref"] in selected
    }
    assert "房玄龄主持中枢政务并参与贞观律令修订" in selected_labels
    assert "贡举中以文体轻薄黜落知名候选人" not in selected_labels
    disposition_by_label = {
        next(
            cluster["canonical_label"]
            for cluster in report["historical_outcome_clusters"]
            if cluster["outcome_ref"] == row["outcome_ref"]
        ): row["disposition"]
        for row in report["governance_dispositions"]
    }
    assert disposition_by_label["建立州县义仓并用于饥馑赈给"] == (
        "excluded_no_preserved_positive_result"
    )
    assert disposition_by_label["贞观律令与刑罚体系修订"] == (
        "supporting_policy_context_not_i5b_team_score"
    )
    assert disposition_by_label["建立并扩充多层官学网络"] == (
        "supporting_policy_context_not_i5b_team_score"
    )


def test_representative_ruler_policies_render_with_current_disposition() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_rendered = render_scoring_detail_markdown(li)
    assert "| 功臣世袭刺史 | 正向 |" in li_rendered
    assert "| 皇子出任地方实职 | 未计入 |" in li_rendered
    assert "建立州县义仓并用于饥馑赈给" in li_rendered
    assert "专业目标已实现，整体混合结果及跨领域代价另行结算" in li_rendered

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    policy_contexts = {
        next(
            cluster["canonical_label"]
            for cluster in liu["historical_outcome_clusters"]
            if cluster["outcome_ref"] == row["outcome_ref"]
        )
        for row in liu["governance_dispositions"]
        if row["disposition"] == "supporting_policy_context_not_i5b_team_score"
    }
    assert policy_contexts == {"汉初约法轻租与财政节用", "疑狱逐级上报程序"}


def test_representative_military_materials_keep_three_channel_lineage() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_contexts = set(li["linked_ruler_context_refs"])
    assert "NMAT-900F470DB8A079C3F11F" in li_contexts
    assert "NMAT-2830CE53C58D4AF38E77" in li_contexts

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    appointment = next(
        row for row in liu["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    appointment_ids = {
        row["material_id"]
        for key in ("settled_materials", "supporting_only_materials")
        for row in appointment[key]
    }
    assert "MAT-刘邦-AD-LB-ZHOUBO-WARTIME-COMMAND" in appointment_ids
    zhou_bo = next(
        row for row in liu["profile_projection_review"] if row["person"] == "周勃"
    )
    assert zhou_bo["candidate_negative_talent_severity"] == "serious"
    assert set(zhou_bo["profile_evidence_refs"]["political_risk"]) == {
        "PFACT-B16F3241641256A60A24",
        "PFACT-41CE7721509571B8E874",
    }


def test_current_value_cli_writes_only_current_result(tmp_path: Path) -> None:
    assert eval_main([
        "i5b-current-value",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(ROOT),
        "--output-dir",
        str(tmp_path),
    ]) == 0
    assert (tmp_path / "result.json").is_file()
    assert (tmp_path / "result.md").is_file()
    report = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    result_markdown = (tmp_path / "result.md").read_text(encoding="utf-8")
    assert result_markdown == render_scoring_detail_markdown(report)
    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |" in result_markdown
    assert "## 各臣子 Episode" not in result_markdown


def test_direct_runner_uses_the_same_markdown_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_json = tmp_path / "result.json"
    output_markdown = tmp_path / "result.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "i5b_current_value_runner",
            "--source-pack",
            str(ROOT / "eval/i5b_current_value/刘邦/source-pack.json"),
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
    )

    assert runner_main() == 0
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert output_markdown.read_text(encoding="utf-8") == (
        render_scoring_detail_markdown(report)
    )


def test_i5b_run_uses_current_ruler_catalog_and_can_export_detail(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source_dir = workspace / "eval/current/ruler"
    source_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    (source_dir / "source-pack.json").write_bytes(source.read_bytes())
    config_dir = workspace / "config"
    config_dir.mkdir()
    (config_dir / "project.yml").write_text(
        """i5b_current_value:
  rulers:
    刘邦:
      source_pack: eval/current/ruler/source-pack.json
      result: eval/current/ruler/result.json
""",
        encoding="utf-8",
    )
    detail = tmp_path / "detail.md"

    assert eval_main([
        "i5b-run",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(workspace),
        "--detail-output",
        str(detail),
    ]) == 0
    assert (source_dir / "result.json").is_file()
    assert (source_dir / "result.md").is_file()
    assert "未计分支持材料" in detail.read_text(encoding="utf-8")


def test_i5b_run_rejects_unconfigured_ruler(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "project.yml").write_text(
        "i5b_current_value:\n  rulers: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="尚未进入当前 I5B 运行目录"):
        eval_main([
            "i5b-run",
            "--ruler",
            "unknown",
            "--workspace-root",
            str(tmp_path),
        ])


def test_current_scoring_detail_export_uses_factor_values_for_unscored_materials(
    tmp_path: Path,
) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    rendered = render_scoring_detail_markdown(report)

    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |" in rendered
    assert "### 未计分支持材料" in rendered
    assert "| 对象 | 判定 | 因子取值 | 事实 |" in rendered
    assert "| 对象 | 判定 | 说明 | 事实 |" not in rendered
    assert "识才方向 1.000000" in rendered
    assert "材料分低于当前" not in rendered
    team = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "team_building"
    )
    assert all(row["political_risk"].get("basis") for row in team["negative_members"])
    assert all(row["political_risk"]["basis"] in rendered for row in team["negative_members"])

    output = tmp_path / "scoring-detail.md"
    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "李世民",
        "--workspace-root",
        str(ROOT),
        "--output",
        str(output),
    ]) == 0
    assert output.read_text(encoding="utf-8") == rendered


def test_scoring_detail_can_filter_one_person(tmp_path: Path) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    rendered = render_scoring_detail_markdown(report, person="周勃")

    assert "# 刘邦 / 周勃第五项B材料预算计分验证" in rendered
    assert "## 当前人物画像" in rendered
    assert "人才等级确立理由" in rendered
    assert "规则对应" in rendered
    assert "登记支撑" in rendered
    assert "config/talent-grade-v11-domain-equivalent-historic.yml#top_fallback" in rendered
    assert "## 人才等级成果登记" in rendered
    assert "campaign" in rendered
    assert "serious" in rendered
    assert "屠马邑" in rendered
    assert "屠浑都存在地名与人名断句争议" in rendered
    assert "## HistoricalEpisode" in rendered
    assert "英布 |" not in rendered
    episode_ids = report["episode_index_by_person"]["周勃"]
    assert len(episode_ids) == len(set(episode_ids))
    outcome_ids = [value for value in episode_ids if value.startswith("EP-OUTCOME-")]
    assert len(outcome_ids) == 1
    assert rendered.count(outcome_ids[0]) == 1

    output = tmp_path / "zhou-bo.md"
    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "刘邦",
        "--person",
        "周勃",
        "--workspace-root",
        str(ROOT),
        "--output",
        str(output),
    ]) == 0
    assert output.read_text(encoding="utf-8") == rendered

    with pytest.raises(ValueError, match="不存在臣子"):
        render_scoring_detail_markdown(report, person="不存在")


def test_default_detail_export_rebuilds_from_source_pack_not_stale_result(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    current_dir = workspace / "eval/i5b_current_value/刘邦"
    current_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    (current_dir / "source-pack.json").write_bytes(source.read_bytes())
    (current_dir / "result.json").write_text(
        '{"ruler":"刘邦","stale":true}', encoding="utf-8"
    )
    output = tmp_path / "han-xin.md"

    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "刘邦",
        "--person",
        "韩信",
        "--workspace-root",
        str(workspace),
        "--output",
        str(output),
    ]) == 0
    assert "# 刘邦 / 韩信第五项B材料预算计分验证" in output.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_signals_do_not_exceed_theoretical_envelopes(ruler: str) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    )
    diagnostic = report["material_budget"]["amplitude_diagnostic"]

    for rule in report["material_budget"]["rules"]:
        code = rule["rule_code"]
        assert Decimal(rule["positive_signal"]) <= Decimal(
            diagnostic["theoretical_positive_envelope"][code]
        )
        assert Decimal(rule["negative_signal"]) <= Decimal(
            diagnostic["theoretical_negative_envelope"][code]
        )
