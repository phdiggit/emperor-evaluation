from __future__ import annotations

from scripts.dev import retrieval_v3_i5b_item_raw_score as tool


def test_markdown_labels_raw_signal_and_dynamic_mapping_boundary() -> None:
    report = {
        "results": [{
            "emperor": "测试帝", "weighted_raw_signal": "1.234",
            "rules": {"appointment_delegation": {
                "positive_signal": "2.000", "negative_signal": "0.500", "rule_raw_net": "1.500"}},
        }]
    }
    rendered = tool.render_markdown(report)

    assert "weighted raw signal" in rendered
    assert "最终 0–45 分和档位仍需批量动态映射" in rendered
    assert "| 测试帝 | 1.234 | 2.000 | 0.500 | 1.500 |" in rendered


def test_tool_is_read_only_and_does_not_write_final_results() -> None:
    source = open(tool.__file__, encoding="utf-8").read().lower()
    assert "insert into" not in source
    assert "update emp_item_results" not in source
    assert "final_score_generated\": false" in source
