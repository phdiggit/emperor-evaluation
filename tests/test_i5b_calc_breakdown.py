from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_calc_breakdown.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_calc_breakdown_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_breakdown_report_joins_item_result_and_cluster_materials() -> None:
    tool = load_tool()
    cluster_rows = {
        ("测试帝", "talent_discovery"): {
            "emperor": "测试帝",
            "rule_code": "talent_discovery",
            "formula_code": "cluster_formula_test",
            "positive_signal": "1.300",
            "negative_signal": "0.000",
            "cluster_direction": "positive",
            "calc_detail": {
                "coverage": {"positive": "1.0", "negative": "1.0"},
                "covered_material_ids": [7, 8],
                "scored_material_ids": [7],
                "supporting_material_ids": [8],
                "object_side_scores": {"positive": {"10": "1.300"}, "negative": {}},
                "materials": [
                    {
                        "obj_src_id": 7,
                        "obj_key": "10",
                        "obj_name": "甲",
                        "side": "positive",
                        "raw_score": "1.300",
                        "abs_score": "1.300",
                        "factor_values": {"talent_quality_factor": "1.3"},
                        "factor_refs": {"talent_quality_factor": {"label": "重要人才"}},
                    }
                ],
            },
        }
    }
    result_rows = {
        "测试帝": {
            "emperor": "测试帝",
            "formula_code": "result_formula_test",
            "score": "33.300",
            "tier": "良好",
            "tier_band": "正常",
            "base_core": "1.000",
            "score_rate": "0.7400",
            "positive_response_cap": "5.5",
            "positive_response_tau": "3.5",
            "negative_response_cap": "7.0",
            "negative_response_tau": "4.0",
            "rules": {
                "talent_discovery": {
                    "cluster_id": 1,
                    "no_material": False,
                    "positive_signal": "1.300",
                    "positive_effect": "1.706",
                    "negative_signal": "0.000",
                    "negative_effect": "0.000",
                    "rule_net_effect": "1.706",
                    "rule_weight": "0.190",
                }
            },
        }
    }

    report = tool.build_breakdown_report(
        emperors=("测试帝",),
        cluster_formula="cluster_formula_test",
        result_formula="result_formula_test",
        result_rows=result_rows,
        cluster_rows=cluster_rows,
    )
    markdown = tool.render_markdown(report)

    assert report["warnings"] == []
    assert report["emperors"][0]["score"] == "33.300"
    assert report["emperors"][0]["rules"][0]["rule_label"] == "发现人才"
    assert report["emperors"][0]["rules"][0]["cluster"]["materials"]["positive"][0]["brief"] == "甲#7(1.300/1.300)"
    assert "| 指标 | 权重 | 正向信号 | 正向响应 | 负向信号 | 负向响应 | 净效应 |" in markdown
    assert "| 发现人才 (`talent_discovery`) | 0.190 | 1.300 | 1.706 | 0.000 | 0.000 | 1.706 |" in markdown
    assert "| 指标 | 证据簇正/负 | 计分/覆盖/补源 | 正向具体对象 | 负向具体对象 |" in markdown
    assert "[7]/[7, 8]/[8]" in markdown
    assert "甲#7(1.300/1.300)" in markdown


def test_breakdown_report_allows_no_material_rule_without_cluster_warning() -> None:
    tool = load_tool()
    result_rows = {
        "测试帝": {
            "emperor": "测试帝",
            "formula_code": "result_formula_test",
            "score": "22.500",
            "rules": {
                "anti_nepotism": {
                    "cluster_id": None,
                    "no_material": True,
                    "positive_signal": "0.000",
                    "positive_effect": "0.000",
                    "negative_signal": "0.000",
                    "negative_effect": "0.000",
                    "rule_net_effect": "0.000",
                    "rule_weight": "0.060",
                }
            },
        }
    }

    report = tool.build_breakdown_report(
        emperors=("测试帝",),
        cluster_formula="cluster_formula_test",
        result_formula="result_formula_test",
        result_rows=result_rows,
        cluster_rows={},
    )

    assert report["warnings"] == []
    assert report["emperors"][0]["rules"][0]["cluster"] is None
