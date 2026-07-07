from __future__ import annotations

import importlib.util
import json
import sys
from types import SimpleNamespace
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "scoring_rule_table_sync.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("scoring_rule_table_sync_under_test", TOOL_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_i5b_snapshot_includes_factor_options_and_rule_weights() -> None:
    tool = load_tool()

    payload = tool.extract_snapshot(
        item_code="I5B",
        rule_doc=tool.factor_sync.I5B_RULE_DOC,
        default_factor_doc=tool.factor_sync.DEFAULT_FACTOR_DOC,
        include_defaults=True,
        scope="all",
    )

    assert "factor_options" in payload
    assert "rule_score_weights" in payload
    weights = payload["rule_score_weights"]
    assert [row["rule_code"] for row in weights] == [
        "talent_discovery",
        "appointment_trust",
        "delegation",
        "team_building",
        "tolerate_talent",
        "anti_nepotism",
    ]
    assert sum(Decimal(str(row["weight_num"])) for row in weights) == Decimal("1.00")
    assert len({row["source_line"] for row in weights}) == 6
    assert [row["source_line"] for row in weights] == sorted(row["source_line"] for row in weights)


def test_generic_rule_doc_can_use_non_i5b_item_code(tmp_path: Path) -> None:
    tool = load_tool()
    rule_doc = tmp_path / "rule.md"
    rule_doc.write_text(
        "\n".join(
            [
                "当前证据簇公式版本",
                "`evidence_cluster_signal_v9`",
                "",
                "### `rule_alpha` 甲规则",
                "",
                "`alpha_factor`：",
                "",
                "| 档位 | 数值 | 说明 |",
                "| --- | --- | --- |",
                "| 高 | 1.2 | 高信息说明 |",
                "| 低 | 0.5 | 低信息说明 |",
                "",
                "item_score =",
                "  0.7 * rule_alpha.rule_net_effect",
            ]
        ),
        encoding="utf-8",
    )

    payload = tool.extract_snapshot(
        item_code="IX",
        rule_doc=rule_doc,
        default_factor_doc=tool.factor_sync.DEFAULT_FACTOR_DOC,
        include_defaults=False,
        scope="all",
    )

    assert [row["item_code"] for row in payload["factor_options"]] == ["IX", "IX"]
    assert [row["rule_code"] for row in payload["factor_options"]] == ["rule_alpha", "rule_alpha"]
    assert payload["rule_score_weights"] == [
        {
            "item_code": "IX",
            "rule_code": "rule_alpha",
            "rule_label": "甲规则",
            "formula_code": "evidence_cluster_signal_v9",
            "weight_version": "v1",
            "weight_num": "0.7",
            "weight_order": 10,
            "weight_basis": "IX 总分权重：甲规则 在 evidence_cluster_signal_v9 总分公式中的线性权重。",
            "source_doc": rule_doc.resolve().relative_to(ROOT).as_posix(),
            "source_line": 14,
        }
    ]


def test_render_weight_upsert_sql_targets_generic_weight_table() -> None:
    tool = load_tool()
    rows = tool.extract_rule_score_weights(tool.factor_sync.I5B_RULE_DOC, item_code="I5B")

    sql = tool.render_weight_upsert_sql(rows)

    assert "retrieval_v2.item_rule_score_weights" in sql
    for column in ["item_code", "rule_code", "rule_label", "formula_code", "weight_version"]:
        assert column in sql
    assert "rv2_item_rule_score_weights_item_rule_formula_version_uk" in sql
    assert "I5B_item_rule_score_weights" not in sql
    assert "'source', 'scoring_rule_table_sync'" in sql


def test_main_render_upsert_sql_can_emit_factor_and_weight_sql(capsys) -> None:
    tool = load_tool()

    assert tool.main(["--scope", "all", "--render-upsert-sql"]) == 0

    sql = capsys.readouterr().out
    assert "retrieval_v2.eval_rule_factors" in sql
    assert "retrieval_v2.eval_rule_factor_options" in sql
    assert "retrieval_v2.item_rule_score_weights" in sql
    assert "-- factor options" in sql
    assert "-- rule score weights" in sql


def test_compare_weight_rows_reports_table_and_doc_diffs() -> None:
    tool = load_tool()
    doc_row = tool.RuleScoreWeight(
        item_code="IX",
        rule_code="rule_alpha",
        rule_label="甲规则",
        formula_code="evidence_cluster_signal_v9",
        weight_version="v1",
        weight_num=Decimal("0.7"),
        weight_order=10,
        weight_basis="IX 总分权重：甲规则。",
        source_doc="doc.md",
        source_line=14,
    )
    table_row = doc_row.to_dict()
    table_row["weight_num"] = "0.6"

    diff = tool.compare_weight_rows([table_row], [doc_row])

    assert diff["missing"][0]["weight_num"] == "0.6"
    assert diff["extra"][0]["weight_num"] == "0.7"


def test_main_check_db_sync_compares_factors_and_weights(monkeypatch, tmp_path: Path, capsys) -> None:
    tool = load_tool()
    rule_doc = tmp_path / "rule.md"
    rule_doc.write_text(
        "\n".join(
            [
                "当前证据簇公式版本",
                "`evidence_cluster_signal_v9`",
                "### `rule_alpha` 甲规则",
                "`alpha_factor`：",
                "| 档位 | 数值 |",
                "| --- | --- |",
                "| 高 | 1.2 |",
                "item_score =",
                "  0.7 * rule_alpha.rule_net_effect",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tool.factor_sync, "resolve_dsn", lambda env_name: "postgres://example")
    monkeypatch.setattr(tool, "dump_retrieval_v2_factor_options", lambda *args, **kwargs: [])
    monkeypatch.setattr(tool, "dump_rule_score_weights", lambda *args, **kwargs: [])

    assert tool.main(["--item-code", "IX", "--rule-doc", str(rule_doc), "--check-db-sync"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["factor_options"]["doc_only"][0]["item_code"] == "IX"
    assert payload["rule_score_weights"]["doc_only"][0]["rule_code"] == "rule_alpha"


def test_audit_factor_judgments_reports_stale_or_mismatched_choices(monkeypatch) -> None:
    tool = load_tool()

    class FakeCursor:
        description = [
            SimpleNamespace(name=name)
            for name in (
                "factor_judgment_id",
                "emperor_name",
                "target_code",
                "rule_code",
                "target_action",
                "side",
                "binding_code",
                "factor_name",
                "option_label",
                "judgment_value",
                "factor_rule_code",
                "factor_option_id",
                "active_value",
            )
        ]

        def execute(self, sql, params) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self):
            return [
                (1, "刘邦", "TGT-I5B-LB", "appointment_trust", "score", "positive", "BND-1", "object_weight", "旧对象权重", "1.3", None, None, None),
                (2, "刘邦", "TGT-I5B-LB", "appointment_trust", "score", "positive", "BND-2", "trust_depth", "有实际职责的任用。", "1.5", "appointment_trust", 42, "1.0"),
                (3, "刘邦", "TGT-I5B-LB", "appointment_trust", "score", "positive", "BND-3", "source_factor", "标准史源，事实链清楚。", "1.0", "", 43, "1.0"),
            ]

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def cursor(self):
            return FakeCursor()

    fake_psycopg = SimpleNamespace(connect=lambda dsn: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    report = tool.audit_factor_judgments(
        "postgres://example",
        item_code="I5B",
        formula_code="evidence_cluster_signal_v3",
        rule_codes=("appointment_trust",),
        target_codes=("TGT-I5B-LB",),
    )

    assert report["ok"] is False
    statuses = {issue["status"] for issue in report["issues"]}
    assert statuses == {"stale_or_unknown_factor_option", "factor_value_mismatch"}
    assert report["checked_factor_choices"] == 3


def test_main_audit_factor_judgments_honors_fail_on_diff(monkeypatch, capsys) -> None:
    tool = load_tool()

    monkeypatch.setattr(tool.factor_sync, "resolve_dsn", lambda env_name: "postgres://example")
    monkeypatch.setattr(
        tool,
        "audit_factor_judgments",
        lambda *args, **kwargs: {"ok": False, "checked_factor_choices": 1, "judgment_rows": 1, "error_count": 1, "issues": []},
    )

    rc = tool.main(["--audit-factor-judgments", "--rule-code", "appointment_trust", "--target-code", "TGT-I5B-LB", "--fail-on-diff"])

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
