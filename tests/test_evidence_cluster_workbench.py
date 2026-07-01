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
            }
        ],
    }

    item_code, clusters = tool.parse_cluster_payload(raw)

    assert item_code == "I5B"
    assert clusters[0].formula_code == "evidence_cluster_formula_v6"
    assert clusters[0].positive_signal == Decimal("5.365")
    assert clusters[0].material_ids == (1, 2, 3)


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
