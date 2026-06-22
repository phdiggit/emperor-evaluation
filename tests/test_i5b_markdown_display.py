from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import i5b_markdown_display as legacy_i5b_markdown_display  # noqa: E402
from shared import i5b_markdown_display  # noqa: E402
from shared.i5b_markdown_display import (  # noqa: E402
    human_review_table_fields,
    load_display_dictionary,
    render_long_list,
    render_table_cell,
)


DISPLAY_CONFIG = {
    "field_labels": {
        "evidence_id": "证据ID",
        "linked_object_anchors": "对象锚点",
        "quote_short": "短摘",
    },
    "value_labels": {
        "positive": "正向",
    },
    "table_render_policy": {
        "max_inline_table_cell_chars": 72,
        "appendix_link_text_template": "见附录：{label}",
    },
    "list_render_policy": {
        "enabled": True,
        "default": {
            "strategy": "preserve_items",
            "min_items_to_compact": 6,
            "max_group_chars": 120,
            "separator": "；",
            "group_label_template": "第{start}-{end}项",
        },
        "field_overrides": {
            "linked_object_anchors": {
                "strategy": "compact_groups",
                "min_items_to_compact": 3,
                "max_group_chars": 8,
                "separator": "；",
            },
            "quote_short": {
                "strategy": "appendix_link",
            },
        },
    },
    "keep_machine_field_name": True,
}

PUBLIC_API_NAMES = (
    "AppendixEntry",
    "display_field_label",
    "display_value",
    "human_review_table_fields",
    "load_display_dictionary",
    "render_appendix_page",
    "render_markdown_kv",
    "render_markdown_table",
    "render_long_list",
    "render_table_cell",
)


def test_new_and_legacy_i5b_markdown_display_imports_expose_public_api() -> None:
    for api_name in PUBLIC_API_NAMES:
        assert hasattr(i5b_markdown_display, api_name)
        assert hasattr(legacy_i5b_markdown_display, api_name)


def test_default_display_config_path_still_points_to_i5b_markdown_view_config() -> None:
    assert i5b_markdown_display.DEFAULT_DISPLAY_CONFIG_PATH == (
        ROOT / "data" / "configs" / "导出展示配置" / "第五项B_markdown_view.json"
    )
    assert legacy_i5b_markdown_display.DEFAULT_DISPLAY_CONFIG_PATH == i5b_markdown_display.DEFAULT_DISPLAY_CONFIG_PATH


def test_render_long_list_preserves_locator_items() -> None:
    assert render_long_list("evidence_id", ["E-001", "E-002"], DISPLAY_CONFIG) == ["E-001", "E-002"]


def test_render_long_list_compacts_groups_with_range_labels() -> None:
    rendered = render_long_list("linked_object_anchors", ["A", "B", "C", "D", "E"], DISPLAY_CONFIG)

    assert rendered == ["**第1-4项**：A；B；C；D", "**第5-5项**：E"]


def test_render_table_cell_uses_appendix_link_strategy_and_preserves_original_value() -> None:
    appendix_entries = []

    cell = render_table_cell(
        "一段必须完整保留的原始短摘",
        field="quote_short",
        row_anchor="E-I5B-001",
        appendix_relative_path="../附录/测试长字段附录.md",
        appendix_entries=appendix_entries,
        config=DISPLAY_CONFIG,
    )

    assert cell == "[见附录：短摘（quote_short）](../附录/测试长字段附录.md#e-i5b-001-quote_short)"
    assert appendix_entries[0].value == "一段必须完整保留的原始短摘"


def test_i5b_display_dictionary_contains_context_labels_and_values() -> None:
    config = load_display_dictionary()

    assert config["field_labels"]["quote_context"] == "上下文摘录"
    assert config["field_labels"]["context_summary"] == "上下文摘要"
    assert config["field_labels"]["context_scope"] == "上下文范围"
    assert config["field_labels"]["context_effect"] == "上下文影响"
    assert config["field_labels"]["adjudication_bridge"] == "裁判桥接说明"
    assert config["value_labels"]["missing"] == "缺失"
    assert config["value_labels"]["pending"] == "待补"
    assert config["value_labels"]["source_verified"] == "已回源核验"
    assert config["value_labels"]["source_verified_auto_classified_cluster_review_pending"] == "已回源，自动归类，待证据簇复核"
    assert config["value_labels"]["split_only"] == "仅用于相邻项剥离"
    assert config["value_labels"]["needs_context_source_review"] == "需回源 / 需上下文"
    assert config["view_profiles"]["human_review"]["show_machine_fields"] is False
    assert "evidence_id" in config["view_profiles"]["human_review"]["hidden_fields"]
    assert config["view_profiles"]["machine_audit"]["include_all_fields"] is True
    assert config["list_render_policy"]["field_overrides"]["quote_context"]["strategy"] == "appendix_link"
    assert config["list_render_policy"]["field_overrides"]["context_summary"]["strategy"] == "appendix_link"
    assert config["list_render_policy"]["field_overrides"]["adjudication_bridge"]["strategy"] == "appendix_link"
    table_fields = config["view_profiles"]["human_review"]["table_fields"]
    assert table_fields["auto_adjudication_overview"] == human_review_table_fields("auto_adjudication_overview", config)
    assert table_fields["auto_adjudication_matrix"][0:3] == ["person", "auto_band_direction", "confidence"]
    assert table_fields["score_mapping_draft"] == [
        "band",
        "entry_condition",
        "typical_evidence_structure",
        "negative_intercept_condition",
        "cross_item_split",
        "direct_score_allowed",
        "rule_confirmation_needed",
        "relative_score_range_draft",
    ]
    assert "evidence_id" not in table_fields["targeted_supplement_evidence_cards"]
    assert "source_id" not in table_fields["targeted_supplement_sources"]
    assert table_fields["targeted_supplement_evidence_cards"][-1] == "supplement_gap_addressed"
    assert table_fields["micro_supplement_evidence_cards"][-1] == "micro_gap_addressed"
    assert table_fields["net_evidence_cards"] == human_review_table_fields("net_evidence_cards", config)
    assert table_fields["net_evidence_cards"][0:4] == ["person", "polarity", "human_level", "trigger_family"]
    assert "evidence_id" not in table_fields["net_evidence_cards"]
    assert "cluster_id" not in table_fields["net_evidence_clusters"]
