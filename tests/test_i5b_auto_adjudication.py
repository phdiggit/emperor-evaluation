import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def script_path(script_name: str) -> Path:
    routes = {
        "validate_evidence.py": Path("scripts/validate/validate_evidence.py"),
        "build_db.py": Path("scripts/build/build_db.py"),
        "export_md.py": Path("scripts/export/export_md.py"),
        "export_i5b_auto_adjudication.py": Path("scripts/export/export_i5b_auto_adjudication.py"),
    }
    return ROOT / routes.get(script_name, Path("scripts") / script_name)
sys.path.insert(0, str(ROOT / "scripts"))
I5B_EXPORT_ROOT = ROOT / "exports" / "markdown_views" / "第五项B"
AUTO_CHAIN_ROOT = I5B_EXPORT_ROOT / "人工审核" / "自动裁判链"
AUTO_EXPORT_PATH = AUTO_CHAIN_ROOT / "自动结算草案" / "第五项B三人自动结算草案.md"
AUTO_RULES_EXPORT_PATH = AUTO_CHAIN_ROOT / "规则敏感点" / "第五项B自动结算规则敏感点清单.md"
FORMAL_EXPORT_PATH = AUTO_CHAIN_ROOT / "正式定档草案" / "第五项B三人正式定档落地表.md"
SCORE_MAP_DRAFT_EXPORT_PATH = AUTO_CHAIN_ROOT / "正式定档草案" / "第五项B评分标尺与档位映射草案.md"
CLOSURE_EXPORT_PATH = AUTO_CHAIN_ROOT / "试点闭环" / "第五项B三人试点内部闭环收尾.md"
REVIEW_ENTRY_ROOT = I5B_EXPORT_ROOT / "人工审核" / "入口"
REVIEW_ENTRY_EXPORT_PATH = REVIEW_ENTRY_ROOT / "第五项B三人专人审核入口.md"
REVIEW_WORKBENCH_EXPORT_PATH = REVIEW_ENTRY_ROOT / "第五项B三人试点人工复核工作台.md"
REVIEW_MATRIX_EXPORT_PATH = REVIEW_ENTRY_ROOT / "第五项B三人试点矩阵说明.md"
REVIEW_PLAN_EXPORT_PATH = REVIEW_ENTRY_ROOT / "第五项B试点计划.md"
LEGACY_AUTO_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人自动结算草案.md"

from export import export_i5b_auto_adjudication as auto


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path(script_name)), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def make_card(
    *,
    evidence_id: str,
    person: str,
    polarity: str,
    strength: int,
    object_anchor: str,
    evidence_role: str,
    trigger_family: str,
    quote_short: str,
    mitigation_flag: str = "",
    upper_bound_flag: str = "",
    cluster_role: str = "正向核心",
    cross_item_split: str = "本项直接证据",
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "person": person,
        "item": "第五项",
        "subitem": "第五项B",
        "polarity": polarity,
        "strength": strength,
        "human_level": "强正" if polarity == "positive" and strength >= 3 else "中正" if polarity == "positive" else "中负" if strength == 2 else "弱负",
        "source_id": f"SRC-{evidence_id}",
        "quote_short": quote_short,
        "interpretation": quote_short,
        "trigger_family": trigger_family,
        "trigger_terms": [trigger_family],
        "cross_item_split": cross_item_split,
        "scoring_effect": "测试用候选证据；不得直接入分，待人工裁判。",
        "verification_status": "source_verified",
        "case_classification": "other",
        "risk_status": "not_applicable",
        "mitigating_factors": [],
        "aggravating_factors": [],
        "reversal_or_rehabilitation": [],
        "adjudication_status": "source_verified_pending_human_adjudication",
        "object_anchor": object_anchor,
        "evidence_role": evidence_role,
        "mitigation_flag": mitigation_flag,
        "upper_bound_flag": upper_bound_flag,
        "cluster_role": cluster_role,
    }


def make_cluster(
    *,
    cluster_id: str,
    person: str,
    polarity: str,
    linked_evidence_ids: list[str],
    candidate_strength: int,
    summary: str,
    cluster_type: str = "talent_ecosystem",
    cross_item_split: str = "本项直接证据",
) -> dict[str, object]:
    return {
        "cluster_id": cluster_id,
        "person": person,
        "item": "第五项",
        "subitem": "第五项B",
        "cluster_type": cluster_type,
        "polarity": polarity,
        "linked_evidence_ids": linked_evidence_ids,
        "summary": summary,
        "five_axis_assessment": {"directness": "high"},
        "candidate_strength": candidate_strength,
        "upper_probe": "pending",
        "cross_item_split": cross_item_split,
        "adjudication_status": "source_verified_pending_human_adjudication",
        "note": "",
    }


@pytest.fixture()
def temp_auto_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    export_dir = tmp_path / "exports" / "markdown_views" / "第五项B"
    auto_chain_dir = export_dir / "人工审核" / "自动裁判链"
    auto_dir = auto_chain_dir / "自动结算草案"
    auto_dir.mkdir(parents=True)

    group_path = tmp_path / "第五项B_视图分组.json"
    group_path.write_text(
        json.dumps(
            [
                {
                    "group_id": "第五项B_三人试点",
                    "group_name": "三人试点",
                    "group_type": "试点人物组",
                    "subitem": "第五项B",
                    "persons": ["测试甲"],
                    "note": "测试",
                }
            ],
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(auto, "DATA_DIR", data_dir)
    monkeypatch.setattr(auto.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)
    monkeypatch.setattr(auto, "MARKDOWN_VIEW_ROOT", tmp_path / "exports" / "markdown_views")
    monkeypatch.setattr(auto, "I5B_MARKDOWN_VIEW_ROOT", export_dir)
    monkeypatch.setattr(auto, "I5B_HUMAN_REVIEW_ROOT", export_dir / "人工审核")
    monkeypatch.setattr(auto, "AUTO_ADJUDICATION_HUMAN_ROOT", auto_chain_dir)
    monkeypatch.setattr(auto, "AUTO_DRAFT_DIR", auto_dir)
    monkeypatch.setattr(auto, "AUTO_DRAFT_DETAIL_DIR", auto_dir / "人物详情")
    monkeypatch.setattr(auto, "AUTO_DRAFT_APPENDIX_DIR", auto_dir / "附录")
    monkeypatch.setattr(auto, "RULE_SENSITIVE_DIR", auto_chain_dir / "规则敏感点")
    monkeypatch.setattr(auto, "FORMAL_DRAFT_DIR", auto_chain_dir / "正式定档草案")
    monkeypatch.setattr(auto, "TRIAL_CLOSURE_DIR", auto_chain_dir / "试点闭环")
    monkeypatch.setattr(auto, "DISPLAY_CONFIG_PATH", ROOT / "data" / "configs" / "导出展示配置" / "第五项B_markdown_view.json")
    monkeypatch.setattr(auto, "EXPORT_PATH", auto_dir / "第五项B三人自动结算草案.md")
    monkeypatch.setattr(auto, "RULES_EXPORT_PATH", auto_chain_dir / "规则敏感点" / "第五项B自动结算规则敏感点清单.md")
    monkeypatch.setattr(auto, "FORMAL_EXPORT_PATH", auto_chain_dir / "正式定档草案" / "第五项B三人正式定档落地表.md")
    monkeypatch.setattr(auto, "SCORE_MAP_DRAFT_EXPORT_PATH", auto_chain_dir / "正式定档草案" / "第五项B评分标尺与档位映射草案.md")
    monkeypatch.setattr(auto, "CLOSURE_EXPORT_PATH", auto_chain_dir / "试点闭环" / "第五项B三人试点内部闭环收尾.md")
    monkeypatch.setattr(auto, "LEGACY_FLAT_EXPORT_PATHS", (tmp_path / "exports" / "markdown_views" / "第五项B三人自动结算草案.md",))

    return data_dir


def build_temp_auto_dataset(
    data_dir: Path,
    cards: list[dict[str, object]],
    clusters: list[dict[str, object]],
) -> None:
    write_jsonl(data_dir / "evidence_cards.jsonl", cards)
    write_jsonl(data_dir / "evidence_clusters.jsonl", clusters)


DISPLAY_WARNING_HEADING = "## 人工复核提示（display-only）"
DISPLAY_WARNING_FORBIDDEN_TERMS = [
    "final_score",
    "ranking",
    "leaderboard",
    "definitive_band",
    "candidate_strength",
    "auto_band_direction",
    "net_adjudication_draft",
]


def make_display_warning_rule(**overrides: object) -> dict[str, object]:
    rule = {
        "rule_id": "I5B-CLUSTER-WARN-TEST-FIXTURE",
        "enabled": False,
        "subitem": "第五项B",
        "trigger_type": "trigger_terms",
        "trigger_terms": ["测试提示词"],
        "polarity_scope": ["positive", "negative"],
        "evidence_strength_scope": ["candidate_strength_3"],
        "warning_type": "source_review_required",
        "warning_message": "测试 fixture 人工复核提示。",
        "adjacent_item_risk": ["第五项C"],
        "required_human_review": True,
    }
    rule.update(overrides)
    return rule


def build_display_warning_fixture(
    data_dir: Path,
    *,
    person: str = "测试甲",
    evidence_id: str = "EVD-TEST-WARN-POS-001",
    cluster_id: str = "ADJ-TEST-WARN-POS-001",
    trigger_family: str = "测试提示词",
    cluster_summary: str = "测试提示词需要人工复核。",
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    cards = [
        make_card(
            evidence_id=evidence_id,
            person=person,
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family=trigger_family,
            quote_short="测试正证一",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id=cluster_id,
            person=person,
            polarity="positive",
            linked_evidence_ids=[evidence_id],
            candidate_strength=3,
            summary=cluster_summary,
        )
    ]
    build_temp_auto_dataset(data_dir, cards, clusters)
    return cards, clusters


def warning_section_from_auto_content(content: str) -> str:
    start = content.index(DISPLAY_WARNING_HEADING)
    end = content.index("### 自动结算结论", start)
    return content[start:end]


def person_section(content: str, person: str, next_person: str | None = None) -> str:
    start = content.index(f"## {person}")
    if next_person is None:
        return content[start:]
    end = content.index(f"\n## {next_person}", start + 1)
    return content[start:end]


def write_view_group(path: Path, persons: list[str]) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "group_id": "第五项B_三人试点",
                    "group_name": "多人物测试",
                    "group_type": "试点人物组",
                    "subitem": "第五项B",
                    "persons": persons,
                    "note": "测试",
                }
            ],
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )


def report_core_field_snapshot(
    report: dict[str, object],
    clusters: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "auto_band_direction": report.get("auto_band_direction"),
        "candidate_strength": [cluster.get("candidate_strength") for cluster in clusters],
        "net_adjudication_draft": report.get("net_adjudication_draft"),
        "formal_band_draft": auto.build_formal_band_draft(report),
        "internal_score_trial": auto.build_trial_score_draft(report).get("trial_score"),
    }


def test_display_warnings_default_off_does_not_render_section(temp_auto_data: Path) -> None:
    build_display_warning_fixture(temp_auto_data)

    content = auto.render_auto_adjudication()

    assert DISPLAY_WARNING_HEADING not in content


def test_markdown_view_display_config_labels_keep_machine_trace() -> None:
    config = auto.load_i5b_markdown_view_config()

    assert config["config_type"] == "markdown_view_display"
    assert config["field_render_policies"]["default"]["long_field_strategy"] == "appendix_link"
    assert config["value_labels"]["true"] == "是"
    assert config["value_labels"]["weak_to_medium"] == "弱至中"
    assert config["table_render_policy"]["long_cell_strategy"] == "appendix_link"
    assert auto.display_field_label("band_direction", config) == "自动结算方向（band_direction）"
    assert auto.display_field_label("positive_cluster_ids", config) == "正向证据簇（positive_cluster_ids）"
    assert auto.display_value(True, config) == "是"
    assert auto.display_value("medium_to_strong", config) == "中至强"
    assert auto.display_value("unknown_machine_value", config) == "unknown_machine_value"


def test_auto_adjudication_overview_table_order_follows_config() -> None:
    config = auto.load_i5b_markdown_view_config()
    config["keep_machine_field_name"] = False
    config["view_profiles"]["human_review"]["table_fields"]["auto_adjudication_overview"] = [
        "detail_page",
        "person",
        "display_warning_count",
    ]
    report = {
        "person": "测试甲",
        "auto_band_direction": "强正",
        "strong_positive_count": 1,
        "coverage_dimension_count": 1,
        "negative_boundary_tier": "none",
        "confidence": "high",
        "positive_cluster_rows": [],
        "negative_cluster_rows": [],
        "positive_cluster_ids": [],
        "negative_cluster_ids": [],
    }

    content = auto.render_split_index_page([report], {}, {}, [], config)

    assert "| 详情页 | 人物 | 人工复核提示数量 |" in content
    assert "| 人物 | 自动结算方向 |" not in content


def test_markdown_display_table_long_cell_uses_appendix_link() -> None:
    config = auto.load_i5b_markdown_view_config()
    config["table_render_policy"] = {
        **config["table_render_policy"],
        "max_inline_table_cell_chars": 72,
        "long_cell_strategy": "appendix_link",
    }
    long_value = "很长的表格单元格内容-" + "甲" * 90
    appendix_items: list[dict[str, object]] = []
    table = auto.markdown_display_table(
        ["rule_sensitive_points"],
        [{"rule_sensitive_points": long_value}],
        display_config=config,
        table_appendix_items=appendix_items,
        appendix_link_target="./附录/合成表格长字段附录.md",
    )
    appendix = auto.render_table_appendix_page(
        "合成表格长字段附录",
        "../合成表格.md",
        appendix_items,
        config,
    )

    assert long_value not in table
    assert (
        "[见附录：规则敏感点（rule_sensitive_points）]"
        "(./附录/合成表格长字段附录.md#appendix-rule_sensitive_points)"
    ) in table
    assert "超长内容已转入" not in table
    assert long_value in appendix
    assert "### appendix-rule_sensitive_points" in appendix
    assert "……（共" not in table + appendix
    assert "<details" not in table + appendix
    assert "<summary" not in table + appendix


def test_display_warnings_default_off_does_not_call_loader(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_display_warning_fixture(temp_auto_data)

    def fail_loader() -> list[dict[str, object]]:
        raise AssertionError("default-off display warning path must not load rules")

    def fail_matcher(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise AssertionError("default-off display warning path must not match warnings")

    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise AssertionError("default-off display warning path must not render warnings")

    monkeypatch.setattr(auto, "load_i5b_cluster_warning_rules", fail_loader)
    monkeypatch.setattr(auto, "match_display_only_cluster_warnings", fail_matcher)
    monkeypatch.setattr(auto, "render_display_only_cluster_warning_section", fail_renderer)

    content = auto.render_auto_adjudication()

    assert "第五项B三人自动结算草案" in content
    assert DISPLAY_WARNING_HEADING not in content


def test_auto_adjudication_cluster_layout_uses_cards_not_wide_table(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id=f"EVD-TEST-LONG-POS-00{index}",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor=f"锚点{index}",
            evidence_role=f"证据角色{index}",
            trigger_family=f"触发族{index}",
            quote_short=f"长字段证据{index}",
            upper_bound_flag=f"上限标记{index}",
            mitigation_flag=f"剥离标记{index}",
            cluster_role=f"簇角色{index}",
            cross_item_split=f"证据拆分{index}",
        )
        for index in range(1, 5)
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-LONG-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=[str(card["evidence_id"]) for card in cards],
            candidate_strength=3,
            summary="长字段布局测试。",
            cross_item_split="簇级拆分",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    content = auto.render_auto_adjudication()
    cluster_start = content.index("### 证据簇自动结算")
    feature_start = content.index("### 自动特征", cluster_start)
    conclusion_start = content.index("### 自动结算结论", cluster_start)
    cluster_section = content[cluster_start:feature_start]

    assert "| cluster_id | polarity | cluster_type" not in content
    for field in ["linked_object_anchors", "linked_evidence_roles", "linked_trigger_families"]:
        assert f"| {field} |" not in content
    assert "<details" not in content
    assert "</details>" not in content
    assert "<summary" not in content
    assert "**ADJ-TEST-LONG-POS-001｜正向｜候选强度（candidate_strength）=3｜强正候选**" in cluster_section
    for label in [
        "簇类型（cluster_type）",
        "边界档（boundary_tier）",
        "是否阻断极限档（blocking_extreme）",
        "剩余强度（residual_level）",
        "对象锚点（linked_object_anchors）",
        "证据角色（linked_evidence_roles）",
        "触发类型（linked_trigger_families）",
        "证据强度（linked_strengths）",
        "上限封顶标记（linked_upper_bound_flags）",
        "减轻/剥离标记（linked_mitigation_flags）",
        "簇内角色（linked_cluster_roles）",
        "相邻项剥离说明（cross_item_split_signals）",
    ]:
        assert f"* **{label}**：" in cluster_section
    for english_label in [
        "cluster_type",
        "boundary_tier",
        "blocking_extreme",
        "residual_level",
        "linked_object_anchors",
        "linked_evidence_roles",
        "linked_trigger_families",
        "linked_strengths",
        "linked_upper_bound_flags",
        "linked_mitigation_flags",
        "linked_cluster_roles",
        "cross_item_split_signals",
    ]:
        assert f"* {english_label}：" not in cluster_section
    assert "* cluster_type：" not in cluster_section
    assert "* boundary_tier：" not in cluster_section
    assert "* **边界档（boundary_tier）**：无" in cluster_section
    assert "* **是否阻断极限档（blocking_extreme）**：否" in cluster_section
    assert "* **剩余强度（residual_level）**：强" in cluster_section
    expected_full_lists = {
        "对象锚点（linked_object_anchors）": ["锚点1", "锚点2", "锚点3", "锚点4"],
        "证据角色（linked_evidence_roles）": ["证据角色1", "证据角色2", "证据角色3", "证据角色4"],
        "触发类型（linked_trigger_families）": ["触发族1", "触发族2", "触发族3", "触发族4"],
        "证据强度（linked_strengths）": ["3"],
        "上限封顶标记（linked_upper_bound_flags）": ["上限标记1", "上限标记2", "上限标记3", "上限标记4"],
        "减轻/剥离标记（linked_mitigation_flags）": ["剥离标记1", "剥离标记2", "剥离标记3", "剥离标记4"],
        "簇内角色（linked_cluster_roles）": ["簇角色1", "簇角色2", "簇角色3", "簇角色4"],
    }
    for label, values in expected_full_lists.items():
        field_start = cluster_section.index(f"* **{label}**：")
        field_end = cluster_section.find("\n\n", field_start)
        field_section = cluster_section[field_start:] if field_end == -1 else cluster_section[field_start:field_end]
        for index, value in enumerate(values, start=1):
            assert f"  {index}. {value}" in field_section

    cross_item_section = cluster_section[cluster_section.index("* **相邻项剥离说明（cross_item_split_signals）**：") :]
    assert "  1. 簇级拆分" in cluster_section
    assert "  2. 证据拆分1" in cross_item_section
    assert "  3. 证据拆分2" in cross_item_section
    assert "  4. 证据拆分3" in cross_item_section
    assert "  5. 证据拆分4" in cross_item_section
    assert "……（共" not in cluster_section
    assert "- **自动结算方向（band_direction）**：" in content[conclusion_start:]
    assert "- **置信度（confidence）**：" in content[conclusion_start:]
    assert "- band_direction：" not in content[conclusion_start:]
    assert "- confidence：" not in content[conclusion_start:]


def test_cli_default_off_does_not_call_warning_stack(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_display_warning_fixture(temp_auto_data)

    def fail_loader() -> list[dict[str, object]]:
        raise AssertionError("default-off CLI path must not load rules")

    def fail_matcher(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise AssertionError("default-off CLI path must not match warnings")

    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise AssertionError("default-off CLI path must not render warnings")

    monkeypatch.setattr(auto, "load_i5b_cluster_warning_rules", fail_loader)
    monkeypatch.setattr(auto, "match_display_only_cluster_warnings", fail_matcher)
    monkeypatch.setattr(auto, "render_display_only_cluster_warning_section", fail_renderer)

    assert auto.main([]) == 0

    auto_content = auto.EXPORT_PATH.read_text(encoding="utf-8")
    assert DISPLAY_WARNING_HEADING not in auto_content


def test_display_warnings_enabled_renders_fixture_warning_section(temp_auto_data: Path) -> None:
    build_display_warning_fixture(temp_auto_data)

    content = auto.render_auto_adjudication(
        include_display_warnings=True,
        warning_rules=[make_display_warning_rule()],
    )
    section = warning_section_from_auto_content(content)

    assert DISPLAY_WARNING_HEADING in content
    assert "I5B-CLUSTER-WARN-TEST-FIXTURE" in section
    assert "测试 fixture 人工复核提示。" in section
    assert content.index("### 触发的规则敏感点") < content.index(DISPLAY_WARNING_HEADING)
    assert content.index(DISPLAY_WARNING_HEADING) < content.index("### 自动结算结论")


def test_cli_include_display_warnings_writes_temp_auto_draft_only(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_display_warning_fixture(temp_auto_data)
    monkeypatch.setattr(auto, "load_i5b_cluster_warning_rules", lambda: [make_display_warning_rule()])

    assert auto.main(["--include-display-warnings"]) == 0

    auto_content = auto.EXPORT_PATH.read_text(encoding="utf-8")
    formal_content = auto.FORMAL_EXPORT_PATH.read_text(encoding="utf-8")
    score_map_content = auto.SCORE_MAP_DRAFT_EXPORT_PATH.read_text(encoding="utf-8")
    closure_export_content = auto.CLOSURE_EXPORT_PATH.read_text(encoding="utf-8")

    assert DISPLAY_WARNING_HEADING in auto_content
    assert "测试 fixture 人工复核提示。" in auto_content
    retired_closure_doc = auto.MARKDOWN_VIEW_ROOT.parents[1] / "docs" / "第五项B三人试点内部闭环收尾.md"
    assert not retired_closure_doc.exists()
    for content in (formal_content, score_map_content, closure_export_content):
        assert DISPLAY_WARNING_HEADING not in content


def test_display_warnings_enabled_keeps_section_inside_each_person(
    tmp_path: Path,
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_path = tmp_path / "第五项B_多人物测试.json"
    write_view_group(group_path, ["测试甲", "测试乙"])
    monkeypatch.setattr(auto.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)

    first_cards, first_clusters = build_display_warning_fixture(
        temp_auto_data,
        person="测试甲",
        evidence_id="EVD-TEST-WARN-POS-001",
        cluster_id="ADJ-TEST-WARN-POS-001",
        trigger_family="甲提示词",
        cluster_summary="甲提示词需要人工复核。",
    )
    second_cards, second_clusters = build_display_warning_fixture(
        temp_auto_data,
        person="测试乙",
        evidence_id="EVD-TEST-WARN-POS-002",
        cluster_id="ADJ-TEST-WARN-POS-002",
        trigger_family="乙提示词",
        cluster_summary="乙提示词需要人工复核。",
    )
    build_temp_auto_dataset(temp_auto_data, first_cards + second_cards, first_clusters + second_clusters)

    content = auto.render_auto_adjudication(
        include_display_warnings=True,
        warning_rules=[
            make_display_warning_rule(
                rule_id="I5B-CLUSTER-WARN-TEST-FIRST",
                trigger_terms=["甲提示词"],
                warning_message="测试甲人工复核提示。",
            ),
            make_display_warning_rule(
                rule_id="I5B-CLUSTER-WARN-TEST-SECOND",
                trigger_terms=["乙提示词"],
                warning_message="测试乙人工复核提示。",
            ),
        ],
    )

    overview_block = content[content.index("## 自动结算总览") : content.index("## 逐人自动草案")]
    assert DISPLAY_WARNING_HEADING not in overview_block

    first_section = person_section(content, "测试甲", next_person="测试乙")
    second_section = person_section(content, "测试乙")
    for section in (first_section, second_section):
        assert section.index("### 触发的规则敏感点") < section.index(DISPLAY_WARNING_HEADING)
        assert section.index(DISPLAY_WARNING_HEADING) < section.index("### 自动结算结论")

    assert "测试甲人工复核提示。" in first_section
    assert "ADJ-TEST-WARN-POS-001" in first_section
    assert "测试乙人工复核提示。" not in first_section
    assert "ADJ-TEST-WARN-POS-002" not in first_section
    assert "测试乙人工复核提示。" in second_section
    assert "ADJ-TEST-WARN-POS-002" in second_section
    assert "测试甲人工复核提示。" not in second_section
    assert "ADJ-TEST-WARN-POS-001" not in second_section


def test_display_warnings_enabled_stays_out_of_non_auto_outputs_and_keeps_core_fields(
    temp_auto_data: Path,
) -> None:
    cards, clusters = build_display_warning_fixture(temp_auto_data)
    evidence_lookup = {row["evidence_id"]: row for row in cards}
    before = report_core_field_snapshot(auto.evaluate_person("测试甲", clusters, evidence_lookup), clusters)

    auto_content = auto.render_auto_adjudication(
        include_display_warnings=True,
        warning_rules=[make_display_warning_rule()],
    )
    after = report_core_field_snapshot(auto.evaluate_person("测试甲", clusters, evidence_lookup), clusters)
    warning_section = warning_section_from_auto_content(auto_content)

    assert before == after
    for content in (
        auto.render_formal_landing_table(),
        auto.render_score_mapping_draft(),
        auto.render_three_pilot_closure(),
    ):
        assert DISPLAY_WARNING_HEADING not in content
        assert "**ADJ-" not in content
        assert "<details" not in content
        assert "<summary" not in content
        assert "### 证据簇自动结算" not in content
    for forbidden_term in DISPLAY_WARNING_FORBIDDEN_TERMS:
        assert forbidden_term not in warning_section


def test_display_warnings_enabled_no_match_outputs_no_extra_hint(temp_auto_data: Path) -> None:
    build_display_warning_fixture(
        temp_auto_data,
        trigger_family="未命中词",
        cluster_summary="未命中内容。",
    )

    content = auto.render_auto_adjudication(
        include_display_warnings=True,
        warning_rules=[make_display_warning_rule(trigger_terms=["测试提示词"])],
    )
    section = warning_section_from_auto_content(content)

    assert DISPLAY_WARNING_HEADING in section
    assert "无额外提示。" in section


def test_split_layout_outputs_index_and_person_detail_page(temp_auto_data: Path) -> None:
    build_display_warning_fixture(temp_auto_data)

    outputs = auto.render_split_auto_adjudication_outputs(
        include_display_warnings=True,
        warning_rules=[make_display_warning_rule()],
    )

    detail_path = auto.person_detail_export_path("测试甲")
    index_content = outputs[auto.EXPORT_PATH]
    detail_content = outputs[detail_path]

    assert "[测试甲详情](./人物详情/测试甲.md)" in index_content
    assert "## 总览索引" in index_content
    assert "人工复核提示数量" in index_content
    assert "# 测试甲：第五项B自动结算草案" in detail_content
    assert "[返回索引](../第五项B三人自动结算草案.md)" in detail_content
    assert "## 人工复核提示（display-only）" in detail_content
    assert "* **命中字段**" in detail_content
    assert "linked_cards[0].trigger_terms" in detail_content
    assert "<details" not in detail_content
    assert "<summary" not in detail_content
    assert "</details>" not in detail_content
    assert "……（共" not in detail_content
    assert "* **对象锚点（linked_object_anchors）**" in detail_content
    assert "* **证据角色（linked_evidence_roles）**" in detail_content
    assert "* **触发类型（linked_trigger_families）**" in detail_content
    assert "* **相邻项剥离说明（cross_item_split_signals）**" in detail_content


@pytest.mark.export_full
@pytest.mark.integration
def test_export_i5b_auto_adjudication_split_layout_writes_index_and_three_detail_pages() -> None:
    result = run_script("export_i5b_auto_adjudication.py", "--output-layout", "split", "--include-display-warnings")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "validated human-readable split markdown exports" in result.stdout
    index_content = AUTO_EXPORT_PATH.read_text(encoding="utf-8")
    targets = list(auto.config_loaders.get_i5b_trial_config()["targets"])

    assert targets == ["李世民", "刘秀", "刘庄"]
    assert "## 总览索引" in index_content
    assert "人工复核提示数量" in index_content
    for person in targets:
        path = auto.person_detail_export_path(person)
        assert path.exists()
        assert f"[{person}详情](./人物详情/{path.name})" in index_content
        detail_content = path.read_text(encoding="utf-8")
        assert f"# {person}：第五项B自动结算草案" in detail_content
        assert "## 人工复核提示（display-only）" in detail_content
        assert "<details" not in detail_content
        assert "<summary" not in detail_content
        assert "</details>" not in detail_content
        assert "……（共" not in detail_content
        assert "* **对象锚点（linked_object_anchors）**" in detail_content
        assert "* **相邻项剥离说明（cross_item_split_signals）**" in detail_content
        assert " True" not in detail_content
        assert " False" not in detail_content
        assert "：True" not in detail_content
        assert "：False" not in detail_content
        assert "weak_to_medium" not in detail_content
        assert "medium_to_strong" not in detail_content
        assert "负向边界档（negative_boundary_tier）" in detail_content
        assert "是否单维集中（single_dimension_flag）" in detail_content
        assert "../附录/" in detail_content


def test_split_export_runs_human_readable_markdown_validation(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_display_warning_fixture(temp_auto_data)
    calls: list[tuple[Path, list[str]]] = []

    def fake_validate(root: Path, targets: list[str]) -> list[str]:
        calls.append((root, targets))
        return []

    monkeypatch.setattr(auto.human_readable_markdown_validator, "validate_exports", fake_validate)

    auto.export_auto_adjudication(output_layout=auto.OUTPUT_LAYOUT_SPLIT, include_display_warnings=True)

    assert calls == [
        (
            auto.MARKDOWN_VIEW_ROOT.parent.parent,
            list(auto.config_loaders.get_i5b_trial_config()["targets"]),
        )
    ]


def test_split_by_person_cli_reports_successful_validation(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_display_warning_fixture(temp_auto_data)
    monkeypatch.setattr(auto.human_readable_markdown_validator, "validate_exports", lambda root, targets: [])

    result = auto.main(["--split-by-person", "--include-display-warnings"])

    captured = capsys.readouterr()
    assert result == 0
    assert "validated human-readable split markdown exports" in captured.out


def test_split_export_validation_failure_returns_nonzero(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_display_warning_fixture(temp_auto_data)
    monkeypatch.setattr(
        auto.human_readable_markdown_validator,
        "validate_exports",
        lambda root, targets: [f"{auto.EXPORT_PATH}: broken split export"],
    )

    result = auto.main(["--output-layout", "split"])

    captured = capsys.readouterr()
    assert result == 1
    assert "Human-readable Markdown export validation failed:" in captured.out
    assert "broken split export" in captured.out


def test_canonical_export_does_not_run_split_validation(
    temp_auto_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_display_warning_fixture(temp_auto_data)

    def fail_validate(root: Path, targets: list[str]) -> list[str]:
        raise AssertionError("canonical export should not run split validation")

    monkeypatch.setattr(auto.human_readable_markdown_validator, "validate_exports", fail_validate)

    auto.export_auto_adjudication(output_layout=auto.OUTPUT_LAYOUT_CANONICAL)


@pytest.mark.export_full
@pytest.mark.integration
def test_export_i5b_auto_adjudication_generates_rule_views() -> None:
    result = run_script("export_i5b_auto_adjudication.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert AUTO_EXPORT_PATH.exists()
    assert AUTO_RULES_EXPORT_PATH.exists()
    assert FORMAL_EXPORT_PATH.exists()
    assert SCORE_MAP_DRAFT_EXPORT_PATH.exists()
    assert CLOSURE_EXPORT_PATH.exists()

    auto_content = AUTO_EXPORT_PATH.read_text(encoding="utf-8")
    rules_content = AUTO_RULES_EXPORT_PATH.read_text(encoding="utf-8")
    formal_content = FORMAL_EXPORT_PATH.read_text(encoding="utf-8")
    score_map_content = SCORE_MAP_DRAFT_EXPORT_PATH.read_text(encoding="utf-8")
    closure_export_content = CLOSURE_EXPORT_PATH.read_text(encoding="utf-8")

    assert "第五项B三人自动结算草案" in auto_content
    assert "负向边界档（negative_boundary_tier）" in auto_content
    assert "负向边界是否阻断（negative_boundary_blocking）" in auto_content
    assert "weak_to_medium" not in auto_content
    assert "medium_to_strong" not in auto_content
    assert "：True" not in auto_content
    assert "：False" not in auto_content
    assert "弱至中" in auto_content
    assert "中至强" in auto_content
    assert "高位强正，上探极正候选" in auto_content
    assert "强正受压制，不上探极正" in auto_content
    assert "中正受中负压制" in auto_content
    assert "RULE-I5B-BOUNDARY-WEAK-TO-MEDIUM" in rules_content
    assert "RULE-I5B-BOUNDARY-MEDIUM-TO-STRONG" in rules_content
    assert "RULE-I5B-SINGLE-DIMENSION-STRONG-POS-THREE-CORE" in rules_content
    assert "RULE-I5B-ADJACENT-STRONG-NEG-RESIDUAL-DETAIL" in rules_content
    assert "RULE-I5B-STRONG-NEG-CORE-SUPPRESSES-STRONG-POS" in rules_content
    assert "第五项B三人正式定档落地表" in formal_content
    assert "正式档位草案" in formal_content
    assert "是否不出分" in formal_content
    assert "是否不排名" in formal_content
    assert "出分阶段前置条件（score_stage_prerequisites）" in formal_content
    assert "需另建第五项B档位到分值映射，并经规则级确认；本表不得直接推分。" in formal_content
    assert "| score |" not in formal_content
    assert "| ranking |" not in formal_content
    assert "| rank |" not in formal_content
    assert "李世民" in formal_content and "极正候选 / 高位强正上探极正" in formal_content
    assert "刘秀" in formal_content and "强正受压制" in formal_content
    assert "刘庄" in formal_content and "中正受中负压制" in formal_content
    assert "第五项B评分标尺与档位映射草案" in score_map_content
    assert "状态：规则草案 / 待规则级确认 / 不正式出分" in score_map_content
    assert "不正式出分" in score_map_content
    assert "V3.2 对齐边界" in score_map_content
    assert "第五项B《用人与授权》正式上限为 45 分" in score_map_content
    assert "内部100制相对试算指数" in score_map_content
    assert "不是 V3.2 正式得分率" in score_map_content
    assert "不能按 `45 × index / 100` 机械换算" in score_map_content
    assert "本 PR 不改变任何人物现有 trial index" in score_map_content
    assert "待总标尺确认" not in score_map_content
    assert "不得给李世民、刘秀、刘庄三人正式分" in score_map_content
    assert "| score |" not in score_map_content
    assert "| rank |" not in score_map_content
    assert "第五项B三人试点内部闭环收尾" in closure_export_content
    assert "内部试算区间" in closure_export_content
    assert "内部试算分" in closure_export_content
    assert "不输出正式分，不排名，不生成阶段总榜或总榜" in closure_export_content
    assert not LEGACY_AUTO_EXPORT_PATH.exists()
    assert "V3.2 已定义正式总标尺和第五项B 45分上限" in closure_export_content
    assert "100制相对诊断指数" in closure_export_content
    assert "尚未进入45分正式映射" in closure_export_content
    assert "不构成人物正式分、排名或总榜" in closure_export_content
    assert "后续七大项完成后再统一映射" not in closure_export_content
    assert "**是否可进入扩展试点**：可" in closure_export_content


def test_real_data_reflects_issue46_rule_decisions() -> None:
    config = auto.config_loaders.get_i5b_trial_config()
    evidence_cards = auto.read_jsonl(auto.DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = auto.read_jsonl(auto.DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    reports = {
        person: auto.evaluate_person(person, evidence_clusters, evidence_lookup)
        for person in config["targets"]
    }
    cluster_lookup = {row["cluster_id"]: row for row in evidence_clusters if row.get("cluster_id")}

    assert reports["李世民"]["auto_band_direction"] == "高位强正，上探极正候选"
    assert reports["李世民"]["negative_boundary_tier"] == "weak_to_medium"
    assert reports["李世民"]["negative_boundary_blocking"] is False
    assert reports["李世民"]["rule_sensitive_points"] == [
        {
            "rule": "弱负上调中负边界",
            "decision": "不阻断极正或高位上探；只降低置信度，不进入强负核心。",
        }
    ]

    assert reports["刘秀"]["auto_band_direction"] == "强正受压制，不上探极正"
    assert reports["刘秀"]["negative_boundary_tier"] == "medium_to_strong"
    assert reports["刘秀"]["negative_boundary_blocking"] is True
    assert reports["刘秀"]["rule_sensitive_points"] == [
        {
            "rule": "中负上调强负边界",
            "decision": "阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。",
        },
        {
            "rule": "强负核心压制强正",
            "decision": "保留强正基础，但自动标记为强正受压制，不上探极正。",
        },
    ]

    assert reports["刘庄"]["auto_band_direction"] == "中正受中负压制"
    assert reports["刘庄"]["negative_boundary_tier"] == "adjacent_item_medium_residual"
    assert reports["刘庄"]["cross_item_split_residual_level"] == "medium"
    assert reports["刘庄"]["rule_sensitive_points"] == [
        {
            "rule": "相邻项主导剥离",
            "decision": "大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。",
        },
        {
            "rule": "B项剩余默认中负",
            "decision": "默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。",
        },
    ]

    liuzhuang_cluster = auto.evaluate_cluster(
        cluster_lookup["ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001"],
        evidence_lookup,
    )
    assert liuzhuang_cluster["residual_level"] == "medium"
    assert liuzhuang_cluster["boundary_tier"] == "adjacent_item_medium_residual"
    assert liuzhuang_cluster["auto_cluster_result"] == "中负边界"


@pytest.mark.export_full
@pytest.mark.integration
def test_formal_landing_table_reflects_auto_drafts() -> None:
    result = run_script("export_i5b_auto_adjudication.py")

    assert result.returncode == 0, result.stdout + result.stderr
    formal_content = FORMAL_EXPORT_PATH.read_text(encoding="utf-8")

    assert "人物（person） | 自动结算方向（auto_band_direction） | 正式档位草案（formal_band_draft）" in formal_content
    assert "李世民 | 高位强正，上探极正候选 | 极正候选 / 高位强正上探极正" in formal_content
    assert "刘秀 | 强正受压制，不上探极正 | 强正受压制" in formal_content
    assert "刘庄 | 中正受中负压制 | 中正受中负压制" in formal_content
    assert "剩余规则问题（remaining_rule_questions）" in formal_content
    assert "出分阶段前置条件（score_stage_prerequisites）" in formal_content
    assert "是否不出分（not_scored_flag）" in formal_content
    assert "是否不排名（ranking_suppressed_flag）" in formal_content
    assert "需另建第五项B档位到分值映射，并经规则级确认；本表不得直接推分。" in formal_content


@pytest.mark.export_full
@pytest.mark.integration
def test_export_md_generates_i5b_review_entry_views() -> None:
    result = run_script("export_md.py", "--profile", "i5b-auto")

    assert result.returncode == 0, result.stdout + result.stderr
    for path in [
        REVIEW_ENTRY_EXPORT_PATH,
        REVIEW_WORKBENCH_EXPORT_PATH,
        REVIEW_MATRIX_EXPORT_PATH,
        REVIEW_PLAN_EXPORT_PATH,
    ]:
        assert path.is_file(), path

    entry_content = REVIEW_ENTRY_EXPORT_PATH.read_text(encoding="utf-8")
    for person in ["李世民", "刘秀", "刘庄"]:
        assert f"### {person}" in entry_content
        assert f"exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/人物详情/{person}.md" in entry_content
        assert f"exports/markdown_views/第五项B/人工审核/证据链/净证据池/第五项B_{person}人工审核净证据池.md" in entry_content
    for needle in [
        "exports/markdown_views/第五项B/人工审核/自动裁判链/",
        "exports/markdown_views/第五项B/人工审核/证据链/",
        "exports/markdown_views/第五项B/机器审计/",
        "旧 `docs/` 同名文件已退役",
        "数据质量核验栏位",
        "不生成正式分数",
        "不生成最终排名",
    ]:
        assert needle in entry_content
    for forbidden in ["manual_score_override", "human_final_score"]:
        assert forbidden not in entry_content

    workbench_content = REVIEW_WORKBENCH_EXPORT_PATH.read_text(encoding="utf-8")
    assert "warning 保持 display-only" in workbench_content
    assert "不做单人人工 override" in workbench_content
    assert "数据质量核验栏位" in workbench_content
    matrix_content = REVIEW_MATRIX_EXPORT_PATH.read_text(encoding="utf-8")
    assert "checked_no_hard_evidence" in matrix_content
    assert "evidence_found_card_created" in matrix_content
    plan_content = REVIEW_PLAN_EXPORT_PATH.read_text(encoding="utf-8")
    assert "不在本计划中写入旧分数或新分数" in plan_content


def test_weak_boundary_negative_does_not_block_extreme(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
            upper_bound_flag="不得因战功上探",
            mitigation_flag="不回填后效",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
            upper_bound_flag="不得因战功上探",
            mitigation_flag="不回填后效",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
            upper_bound_flag="不得因战功上探",
            mitigation_flag="不回填后效",
        ),
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=1,
            object_anchor="边界负证",
            evidence_role="弱负边界",
            trigger_family="疑忌杀害",
            quote_short="轻微外溢，不成寒意",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探中负",
            cluster_role="边界负证",
            cross_item_split="事件主因切第五项C/D",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单维强正三核心",
        ),
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=1,
            summary="弱负升中负边界",
            cluster_type="talent_security",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)
    cluster = auto.evaluate_cluster(clusters[1], evidence_lookup)

    assert report["auto_band_direction"] == "高位强正，上探极正候选"
    assert report["confidence"] == "high_mid"
    assert report["negative_boundary_tier"] == "weak_to_medium"
    assert report["negative_boundary_blocking"] is False
    assert cluster["residual_level"] == "weak"
    assert cluster["boundary_tier"] == "weak_to_medium"
    assert cluster["auto_cluster_result"] == "弱负边界"


def test_medium_boundary_negative_blocks_extreme_and_becomes_core(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
        ),
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="中负边界",
            trigger_family="容谏纳言",
            quote_short="群臣莫敢正言",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探强负",
            cluster_role="边界负证",
            cross_item_split="表达安全直接受损",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单维强正三核心",
        ),
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="中负升强负边界",
            cluster_type="talent_security",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)
    cluster = auto.evaluate_cluster(clusters[1], evidence_lookup)

    assert report["auto_band_direction"] == "强正受压制，不上探极正"
    assert report["negative_boundary_tier"] == "medium_to_strong"
    assert report["negative_boundary_blocking"] is True
    assert report["has_strong_negative_core"] is True
    assert cluster["residual_level"] == "strong"
    assert cluster["boundary_tier"] == "medium_to_strong"
    assert cluster["blocking_extreme"] is True
    assert cluster["negative_core"] is True
    assert cluster["auto_cluster_result"] == "强负候选"


def test_single_dimension_three_strong_positives_can_probe_extreme(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单一维度三强正核心",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)

    assert report["single_dimension_flag"] is True
    assert report["strong_positive_count"] == 3
    assert report["auto_band_direction"] == "高位强正，上探极正候选"
    assert report["confidence"] == "high"


def test_single_dimension_below_three_strong_positives_is_capped(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002"],
            candidate_strength=3,
            summary="单一维度两强正核心",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)

    assert report["single_dimension_flag"] is True
    assert report["strong_positive_count"] == 2
    assert report["auto_band_direction"] == "强正封顶，不上探极正"
    assert report["confidence"] == "medium_high"


def test_adjacent_item_strong_negative_defaults_to_medium_residual(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=3,
            object_anchor="楚狱边界负证",
            evidence_role="强负核心",
            trigger_family="疑忌杀害",
            quote_short="楚獄遂至累年，其辭語相連，坐死徙者以千數。",
            mitigation_flag="剥离政权安全与司法严酷",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="宗室控制、司法严酷、政治残酷性切相邻项",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=3,
            summary="大案剥离后的中负残余",
            cluster_type="talent_security_and_political_implication_risk",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    cluster = auto.evaluate_cluster(clusters[0], evidence_lookup)

    assert cluster["residual_level"] == "medium"
    assert cluster["boundary_tier"] == "adjacent_item_medium_residual"
    assert cluster["blocking_extreme"] is False
    assert cluster["auto_cluster_result"] == "中负边界"


def test_direct_expression_hard_evidence_keeps_strong_negative_core(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="强负核心",
            trigger_family="容谏纳言",
            quote_short="群臣莫敢正言",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="表达安全直接受损",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="表达安全硬证",
            cluster_type="remonstrance_safety_and_expression_risk",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    cluster = auto.evaluate_cluster(clusters[0], evidence_lookup)

    assert cluster["residual_level"] == "strong"
    assert cluster["boundary_tier"] == "medium_to_strong"
    assert cluster["blocking_extreme"] is True
    assert cluster["negative_core"] is True
    assert cluster["auto_cluster_result"] == "强负候选"


def test_extended_direct_safety_keywords_cover_variants(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="强负核心",
            trigger_family="容谏纳言",
            quote_short="人才退缩，授权可信度破坏，表达入口被破坏",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="表达安全直接受损",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="寒蝉与授权可信度破坏",
            cluster_type="remonstrance_safety_and_expression_risk",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    cluster = auto.evaluate_cluster(clusters[0], evidence_lookup)

    assert auto.has_direct_safety_hard_evidence(cards) is True
    assert cluster["boundary_tier"] == "medium_to_strong"
    assert cluster["blocking_extreme"] is True
    assert cluster["negative_core"] is True


def test_strong_positive_base_with_strong_negative_core_is_suppressed(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
        ),
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="强负核心",
            trigger_family="容谏纳言",
            quote_short="群臣莫敢正言",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="表达安全直接受损",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单一维度三强正核心",
        ),
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="强负核心压制强正",
            cluster_type="remonstrance_safety_and_expression_risk",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)

    assert report["auto_band_direction"] == "强正受压制，不上探极正"
    assert report["negative_boundary_tier"] == "medium_to_strong"
    assert report["negative_boundary_blocking"] is True
    assert report["has_strong_negative_core"] is True
