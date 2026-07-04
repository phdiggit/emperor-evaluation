from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_factor_table_sync.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_factor_table_sync_under_test", TOOL_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_current_rule_docs_contains_expected_i5b_factor_options() -> None:
    tool = load_tool()
    rows = tool.extract_factor_options()

    object_weight_rows = [row for row in rows if row.factor_name == "object_weight"]
    assert {row.rule_code for row in object_weight_rows} == {""}
    assert any(row.value_num == Decimal("1.3") and "核心岗位" in row.label for row in object_weight_rows)

    source_rows = [row for row in rows if row.factor_name == "source_factor"]
    assert any(row.value_num == Decimal("1.15") and row.label == "多源可互证" for row in source_rows)
    assert all(row.note == "" for row in source_rows)
    assert any("多源可互证" in row.description for row in source_rows)

    handling_rows = [row for row in rows if row.rule_code == "tolerate_talent" and row.factor_name == "handling_severity"]
    assert any(row.value_num == Decimal("3.0") and "灾难级安全破坏" in row.label for row in handling_rows)
    assert all(row.note != row.label for row in handling_rows)

    target_fault_labels = [
        row.label
        for row in rows
        if row.rule_code == "tolerate_talent" and row.factor_name == "target_fault_factor"
    ]
    assert len(target_fault_labels) == 5
    assert all("政权安全" not in label for label in target_fault_labels)
    assert all("相邻项" not in label for label in target_fault_labels)

    rank_decay_rows = [row for row in rows if row.rule_code == "team_building" and row.factor_name == "rank_decay"]
    assert [row.label for row in rank_decay_rows] == ["第 1 位", "第 2 位", "第 3 位", "第 4-6 位", "第 7 位以后"]

    discovery_quality_rows = [
        row
        for row in rows
        if row.rule_code == "talent_discovery" and row.factor_name == "talent_quality_factor"
    ]
    assert [row.label for row in discovery_quality_rows] == ["普通人才", "可用人才", "重要人才", "顶级人才", "历史级人才"]
    assert [row.factor_scope for row in discovery_quality_rows] == ["attribute_mapping"] * 5
    assert [row.value_num for row in discovery_quality_rows] == [
        Decimal("0.5"),
        Decimal("0.9"),
        Decimal("1.3"),
        Decimal("1.8"),
        Decimal("2.5"),
    ]

    retired_factor_names = {"founder_pressure", "retention_signal", "certainty_factor", "spillover_factor", "disposition_severity"}
    assert not ({row.factor_name for row in rows} & retired_factor_names)


def test_render_upsert_sql_links_factor_options_to_items_and_rules() -> None:
    tool = load_tool()
    rows = [
        row
        for row in tool.extract_factor_options()
        if row.rule_code == "tolerate_talent" and row.factor_name == "handling_severity"
    ][:1]
    assert rows

    sql = tool.render_upsert_sql(rows)

    assert "public.eval_rule_factors" in sql
    assert "public.eval_rule_factor_options" in sql
    assert "public.eval_items" in sql
    assert "public.eval_rules" in sql
    assert "description" in sql
    assert "on conflict (item_code, rule_code, formula_code, factor_name)" in sql
    assert "on conflict (factor_id, label)" in sql


def test_compare_rows_reports_missing_and_extra_options() -> None:
    tool = load_tool()
    actual = [
        tool.FactorOption(
            item_code="I5B",
            rule_code="tolerate_talent",
            formula_code="evidence_cluster_signal_v3",
            factor_name="target_fault_factor",
            factor_scope="rule",
            label="无故构陷",
            value_num=Decimal("1.5"),
            sort_no=1,
            source_doc="doc.md",
            source_heading="heading",
            source_line=10,
        )
    ]
    expected = [
        {
            "item_code": "I5B",
            "rule_code": "tolerate_talent",
            "formula_code": "evidence_cluster_signal_v3",
            "factor_name": "target_fault_factor",
            "factor_scope": "rule",
            "label": "过错轻微",
            "value_num": "1.2",
        }
    ]

    diff = tool.compare_rows(expected, actual)

    assert diff["missing"] == [tool.normalize_row_dict(expected[0])]
    assert diff["extra"] == [tool.normalize_row_dict(actual[0].to_dict())]


def test_main_can_check_db_sync_against_active_table_snapshot(monkeypatch, capsys) -> None:
    tool = load_tool()
    doc_row = tool.FactorOption(
        item_code="I5B",
        rule_code="tolerate_talent",
        formula_code="evidence_cluster_signal_v3",
        factor_name="target_fault_factor",
        factor_scope="rule",
        label="文档取值",
        value_num=Decimal("1.5"),
        sort_no=1,
        source_doc="doc.md",
        source_heading="heading",
        source_line=10,
    )
    table_row = doc_row.to_dict()
    table_row["label"] = "表内旧取值"

    monkeypatch.setattr(tool, "extract_factor_options", lambda **kwargs: [doc_row])
    monkeypatch.setattr(tool, "resolve_dsn", lambda env_name: "postgres://example")
    monkeypatch.setattr(tool, "dump_db_factor_options", lambda dsn, item_code="I5B", formula_code=None: [table_row])

    assert tool.main(["--check-db-sync"]) == 0

    output = capsys.readouterr().out
    assert "table_only" in output
    assert "doc_only" in output
    assert "表内旧取值" in output
    assert "文档取值" in output


def test_audit_calc_detail_factor_refs_reports_table_mismatches() -> None:
    tool = load_tool()
    factor_rows = [
        {
            "factor_option_id": 1,
            "rule_code": "tolerate_talent",
            "factor_name": "handling_severity",
            "factor_scope": "rule",
            "label": "大规模牵连",
            "value_num": "3.0",
        },
        {
            "factor_option_id": 2,
            "rule_code": "",
            "factor_name": "object_weight",
            "factor_scope": "shared",
            "label": "常规可计入对象。",
            "value_num": "1.0",
        },
    ]
    calc_rows = [
        {
            "cluster_id": 10,
            "emperor": "测试帝",
            "rule_code": "tolerate_talent",
            "calc_detail": {
                "materials": [
                    {
                        "obj_src_id": 100,
                        "obj_name": "甲",
                        "factor_values": {"handling_severity": "2.0", "object_weight": "1.0"},
                        "factor_refs": {
                            "handling_severity": {"label": "大规模牵连"},
                            "object_weight": {"label": "常规可计入对象。"},
                            "source_factor": "1.0",
                            "founder_pressure": {"label": "开国压力"},
                        },
                    }
                ]
            },
        }
    ]

    report = tool.audit_calc_detail_factor_refs(calc_rows, factor_rows)

    statuses = {issue["status"] for issue in report["issues"]}
    assert report["ok"] is False
    assert "value_mismatch" in statuses
    assert "literal_factor_ref" in statuses
    assert "retired_factor" in statuses
    assert report["checked_factor_refs"] == 4
    assert report["matched_factor_refs"] == 1


def test_audit_calc_detail_factor_refs_rejects_literal_team_factor() -> None:
    tool = load_tool()
    factor_rows = [
        {
            "factor_option_id": 91,
            "rule_code": "team_building",
            "factor_name": "role_complementarity_factor",
            "factor_scope": "rule",
            "label": "高度互补，四个粗功能面均有重要及以上对象支撑，且其中至少两个功能面有顶级或历史级对象承担核心作用。",
            "value_num": "1.30",
        }
    ]
    calc_rows = [
        {
            "cluster_id": 20,
            "emperor": "测试帝",
            "rule_code": "team_building",
            "calc_detail": {
                "team_factors": {
                    "factor_values": {"role_complementarity_factor": "1.30"},
                    "factor_refs": {"role_complementarity_factor": "1.30"},
                }
            },
        }
    ]

    report = tool.audit_calc_detail_factor_refs(calc_rows, factor_rows)

    assert report["ok"] is False
    assert report["error_count"] == 1
    assert report["issues"][0]["path"] == "team_factors.factor_refs.role_complementarity_factor"
    assert report["issues"][0]["status"] == "literal_factor_ref"
