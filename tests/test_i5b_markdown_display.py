from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from i5b_markdown_display import load_display_dictionary, render_long_list, render_table_cell  # noqa: E402


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
