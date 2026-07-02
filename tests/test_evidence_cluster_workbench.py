from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "evidence_cluster_workbench.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("evidence_cluster_workbench_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_direction_from_signals_uses_uncapped_net() -> None:
    tool = load_tool()

    assert tool.direction_from_signals(Decimal("8.5"), Decimal("2.4")) == "positive"
    assert Decimal("8.5") - Decimal("2.4") == Decimal("6.1")
    assert tool.direction_from_signals(Decimal("1.2"), Decimal("1.2")) == "mixed"
    assert tool.direction_from_signals(Decimal("0.2"), Decimal("1.5")) == "negative"


def test_render_cluster_note_uses_chinese_narrative() -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="talent_discovery",
        positive_signal=Decimal("3.210"),
        negative_signal=Decimal("0.000"),
        formula_code="fixture",
        note="legacy note",
    )

    assert tool.render_cluster_note(cluster) == (
        "本证据簇汇总测试帝在“发现人才”维度的已回源材料，"
        "正向信号为3.210，负向信号为0.000；"
        "证据簇只保存原始聚合信号，最终分值由结果层计算。"
    )


def test_parse_cluster_payload_applies_default_formula_code() -> None:
    tool = load_tool()
    raw = {
        "item_code": "I5B",
        "formula_code": "evidence_cluster_formula_v6",
        "clusters": [
            {
                "emperor": "李世民",
                "rule_code": "talent_discovery",
                "positive_signal": "5.365",
                "negative_signal": "0",
                "note": "按当前材料重算，写入正向原始信号。",
                "material_ids": [1, 2, 3],
                "calc_detail": {"materials": [{"obj_src_id": 1, "score": "1.0"}]},
            }
        ],
    }

    item_code, clusters = tool.parse_cluster_payload(raw)

    assert item_code == "I5B"
    assert clusters[0].formula_code == "evidence_cluster_formula_v6"
    assert clusters[0].positive_signal == Decimal("5.365")
    assert clusters[0].material_ids == (1, 2, 3)
    assert clusters[0].calc_detail == {"materials": [{"obj_src_id": 1, "score": "1.0"}]}


def test_parse_cluster_payload_rejects_negative_signal() -> None:
    tool = load_tool()
    raw = {
        "item_code": "I5B",
        "formula_code": "evidence_cluster_formula_v6",
        "clusters": [
            {
                "emperor": "李世民",
                "rule_code": "talent_discovery",
                "positive_signal": "-1",
                "negative_signal": "0",
                "note": "invalid",
            }
        ],
    }

    with pytest.raises(tool.EvidenceClusterWorkbenchError, match="non-negative"):
        tool.parse_cluster_payload(raw)


def test_cluster_detail_arrays_split_covered_scored_and_supporting_ids() -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="tolerate_talent",
        positive_signal=Decimal("0.000"),
        negative_signal=Decimal("3.000"),
        formula_code="evidence_cluster_signal_test",
        note="fixture",
        material_ids=(10, 11, 12),
        calc_detail={
            "covered_material_ids": [10, 11, 12],
            "scored_material_ids": [10, 12],
            "supporting_material_ids": [11],
            "materials": [{"obj_src_id": 10}, {"obj_src_id": 12}],
        },
    )

    covered, scored, supporting = tool._cluster_detail_arrays(cluster)

    assert covered == (10, 11, 12)
    assert scored == (10, 12)
    assert supporting == (11,)


class ExpectedMaterialCursor:
    def __init__(self, expected_ids: tuple[int | tuple[int, str], ...]) -> None:
        self.expected_ids = expected_ids

    def execute(self, query: str, params: tuple[int, int, int]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[tuple[int, str]]:
        rows: list[tuple[int, str]] = []
        for material_id in self.expected_ids:
            if isinstance(material_id, tuple):
                rows.append(material_id)
            else:
                rows.append((material_id, "positive"))
        return rows


def test_validate_material_coverage_rejects_missing_material_ids() -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="talent_discovery",
        positive_signal=Decimal("1.0"),
        negative_signal=Decimal("0"),
        formula_code="fixture",
        note="fixture",
        material_ids=(10,),
        calc_detail={"materials": [{"obj_src_id": 10}]},
    )

    with pytest.raises(tool.EvidenceClusterWorkbenchError, match=r"material_ids.*missing obj_srcs=\[11\]"):
        tool._validate_material_coverage(
            ExpectedMaterialCursor((10, 11)),
            emp_id=1,
            item_id=2,
            rule_id=3,
            cluster=cluster,
        )


def test_validate_material_coverage_rejects_missing_calc_detail_materials() -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="talent_discovery",
        positive_signal=Decimal("1.0"),
        negative_signal=Decimal("0"),
        formula_code="fixture",
        note="fixture",
        material_ids=(10, 11),
        calc_detail={"materials": [{"obj_src_id": 10}]},
    )

    with pytest.raises(tool.EvidenceClusterWorkbenchError, match=r"calc_detail\.materials.*missing obj_srcs=\[11\]"):
        tool._validate_material_coverage(
            ExpectedMaterialCursor((10, 11)),
            emp_id=1,
            item_id=2,
            rule_id=3,
            cluster=cluster,
        )


def test_validate_material_coverage_allows_team_building_emp_obj_materials() -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="team_building",
        positive_signal=Decimal("1.0"),
        negative_signal=Decimal("0"),
        formula_code="fixture",
        note="fixture",
        material_ids=(10, 11),
        calc_detail={
            "materials": [
                {"obj_id": 100, "emp_obj_id": 200, "obj_name": "甲"},
                {"obj_id": 101, "emp_obj_id": 201, "obj_name": "乙"},
            ]
        },
    )

    tool._validate_material_coverage(
        ExpectedMaterialCursor((10, 11)),
        emp_id=1,
        item_id=2,
        rule_id=3,
        cluster=cluster,
    )


def test_validate_material_coverage_allows_neutral_outside_calc_detail() -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="talent_discovery",
        positive_signal=Decimal("1.0"),
        negative_signal=Decimal("0"),
        formula_code="fixture",
        note="fixture",
        material_ids=(10, 11),
        calc_detail={"materials": [{"obj_src_id": 10}]},
    )

    tool._validate_material_coverage(
        ExpectedMaterialCursor(((10, "positive"), (11, "neutral"))),
        emp_id=1,
        item_id=2,
        rule_id=3,
        cluster=cluster,
    )


def test_render_materials_markdown_includes_attrs() -> None:
    tool = load_tool()
    report = {
        "emperor": "刘秀",
        "item_code": "I5B",
        "rule_code": "talent_discovery",
        "material_count": 1,
        "rules": {
            "talent_discovery": [
                {
                    "obj_src_id": 7,
                    "direction": "positive",
                    "obj_name": "邓禹",
                    "src_key": "SRC-HHS-J16-DENGYU-LIUXIU-001",
                    "obj_src_note": "邓禹早期归附任用材料。",
                    "attrs": [
                        {
                            "attr_code": "talent_quality",
                            "value_text": "顶级人才",
                            "value_num": None,
                        }
                    ],
                }
            ]
        },
    }

    rendered = tool.render_materials_markdown(report)

    assert "`7` `positive` 邓禹" in rendered
    assert "talent_quality=顶级人才" in rendered


def test_legacy_jsonl_log_entrypoint_is_removed() -> None:
    tool = load_tool()
    parser = tool.build_parser()
    upsert = parser._subparsers._group_actions[0].choices["upsert"]
    options = {option for action in upsert._actions for option in action.option_strings}

    assert "--log" not in options
    assert not hasattr(tool, "append_calc_log")
