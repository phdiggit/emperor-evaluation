from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v2_factorization_consumer as tool


def patch_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "高强度授权"},
            "appointment_effect": {"label": "结果有效"},
            "continuity_factor": {"label": "稳定任用授权。"},
            "attribution_factor": {"label": "可归因"},
            "source_factor": {"label": "正史明载"},
            "context_factor": {"label": "语境明确"},
        },
        "patch_note": "材料明确呈现皇帝授权对象承担关键职任，并有结果反馈，适合作为委任入分材料。",
    }
    row.update(overrides)
    return row


def test_validate_patch_row_requires_high_information_chinese_note() -> None:
    with pytest.raises(tool.FactorizationConsumerError, match="high-information Chinese text"):
        tool.validate_patch_row_shape(patch_row(patch_note="too short"))

    payload = tool.validate_patch_row_shape(patch_row())

    assert payload["binding_code"] == "BND-001"
    assert payload["target_action"] == "score"
    assert payload["side"] == "positive"


def test_validate_patch_row_rejects_unknown_action_and_duplicate_binding() -> None:
    with pytest.raises(tool.FactorizationConsumerError, match="unsupported target_action"):
        tool.validate_patch_row_shape(patch_row(target_action="keep"))

    with pytest.raises(tool.FactorizationConsumerError, match="duplicate binding_code"):
        tool.validate_patch_rows([patch_row(), patch_row()])


def factor_option_rows() -> list[dict[str, object]]:
    labels = [
        ("appointment_delegation", "appointment_importance", "高强度授权", 101),
        ("appointment_delegation", "appointment_effect", "结果有效", 102),
        ("appointment_delegation", "continuity_factor", "稳定任用授权。", 103),
        ("team_building", "talent_quality_factor", "历史级人才", 301),
        ("team_building", "role_complementarity_factor", "高度互补", 302),
        ("team_building", "long_term_stability_factor", "长期稳定核心班底", 303),
        ("", "attribution_factor", "可归因", 201),
        ("", "source_factor", "正史明载", 202),
        ("", "context_factor", "语境明确", 203),
    ]
    return [
        {
            "factor_id": factor_id,
            "item_code": "I5B",
            "rule_code": rule_code,
            "formula_code": "evidence_cluster_signal_v3",
            "factor_name": factor_name,
            "factor_option_id": factor_id + 1000,
            "option_code": f"OPT-{factor_id}",
            "label": label,
            "value_num": "1.000000",
        }
        for rule_code, factor_name, label, factor_id in labels
    ]


def formal_factor_option_rows() -> list[dict[str, object]]:
    labels = [
        ("appointment_delegation", "appointment_importance", "国家级、危局或长期关键授权。", 101),
        ("appointment_delegation", "appointment_effect", "正常成功或职责履行良好。", 102),
        ("appointment_delegation", "continuity_factor", "稳定任用授权。", 103),
        ("", "attribution_factor", "皇帝决策链清楚", 201),
        ("", "source_factor", "标准史源且事件链清楚", 202),
        ("", "context_factor", "中性", 203),
    ]
    return [
        {
            "factor_id": factor_id,
            "item_code": "I5B",
            "rule_code": rule_code,
            "formula_code": "evidence_cluster_signal_v3",
            "factor_name": factor_name,
            "factor_option_id": factor_id + 1000,
            "option_code": f"OPT-{factor_id}",
            "label": label,
            "value_num": "1.000000",
        }
        for rule_code, factor_name, label, factor_id in labels
    ]


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn
        self.rows: list[dict] = []
        self.row: dict | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        lowered = sql.lower()
        routed = lowered.replace("retrieval_v3", "retrieval_v2")
        self.conn.statements.append(lowered)
        self.conn.params.append(params or ())
        if "from retrieval_v2.eval_rule_factors f" in routed:
            self.rows = [dict(row) for row in self.conn.factor_option_rows]
            self.row = None
            return
        if "from retrieval_v2.claim_rule_bindings crb" in routed:
            binding_code = params[0]
            self.row = dict(self.conn.binding_rows.get(binding_code)) if binding_code in self.conn.binding_rows else None
            self.rows = []
            return
        if "insert into retrieval_v2.claim_rule_binding_factor_judgments" in routed:
            self.row = {"id": 900}
            self.rows = []
            return
        self.row = None
        self.rows = []

    def fetchall(self) -> list[dict]:
        return self.rows

    def fetchone(self) -> dict | None:
        return self.row


class FakeConnection:
    def __init__(self) -> None:
        self.factor_option_rows = factor_option_rows()
        self.binding_rows = {
            "BND-001": {
                "binding_id": 10,
                "binding_code": "BND-001",
                "claim_id": 20,
                "rule_code": "appointment_delegation",
                "binding_direction": "positive",
                "binding_usable_for_scoring_cluster": True,
                "binding_payload": {},
                "source_pack_id": 30,
                "target_id": 40,
                "item_code": "I5B",
                "candidate_id": None,
                "candidate_code": None,
                "candidate_payload": None,
            },
            "BND-BLOCKED": {
                "binding_id": 12,
                "binding_code": "BND-BLOCKED",
                "claim_id": 22,
                "rule_code": "appointment_delegation",
                "binding_direction": "positive",
                "binding_usable_for_scoring_cluster": False,
                "binding_payload": {"source": "retrieval_v2_candidate_promoter", "candidate_id": 120},
                "source_pack_id": 30,
                "target_id": 40,
                "item_code": "I5B",
                "candidate_id": 120,
                "candidate_code": "CRBC-BLOCKED",
                "candidate_payload": {
                    "scoring_candidate": False,
                    "usable_for_scoring_cluster": False,
                    "appointment_delegation_chain": {
                        "has_appointment_or_authorization": False,
                        "has_named_actor": True,
                        "has_task_or_responsibility": False,
                        "has_result_or_feedback": False,
                    },
                },
            },
            "BND-TEAM": {
                "binding_id": 11,
                "binding_code": "BND-TEAM",
                "claim_id": 21,
                "rule_code": "team_building",
                "binding_direction": "positive",
                "binding_usable_for_scoring_cluster": True,
                "binding_payload": {},
                "source_pack_id": 30,
                "target_id": 40,
                "item_code": "I5B",
                "candidate_id": None,
                "candidate_code": None,
                "candidate_payload": None,
            }
        }
        self.statements: list[str] = []
        self.params: list[object] = []
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakePsycopg:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def connect(self, *args, **kwargs) -> FakeConnection:
        return self.conn


def patch_fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))
    return conn


def test_apply_patch_rows_dry_run_writes_judgment_and_factor_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.apply_patch_rows(
        dsn="postgresql://fake",
        rows=[patch_row()],
        item_code="I5B",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["write_db"] is False
    assert payload["applied_counts"]["retrieval_v3.claim_rule_binding_factor_judgments"] == 1
    assert payload["applied_counts"]["retrieval_v3.claim_rule_bindings_scoring_gate"] == 1
    assert payload["applied_counts"]["retrieval_v3.claim_rule_binding_factor_choices"] == 6
    assert conn.rolled_back is True
    assert any("insert into retrieval_v3.claim_rule_binding_factor_judgments" in statement for statement in conn.statements)
    assert any("update retrieval_v3.claim_rule_bindings" in statement for statement in conn.statements)
    assert any("usable_for_scoring_cluster = %s" in statement for statement in conn.statements)
    assert any(params and params[0] is True for params in conn.params)
    assert any("delete from retrieval_v3.claim_rule_binding_factor_choices" in statement for statement in conn.statements)
    assert any("insert into retrieval_v3.claim_rule_binding_factor_choices" in statement for statement in conn.statements)


def test_apply_patch_rows_rejects_appointment_delegation_non_scoring_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_fake_db(monkeypatch)
    row = patch_row(binding_code="BND-BLOCKED")

    with pytest.raises(tool.FactorizationConsumerError, match="non-scoring binding"):
        tool.apply_patch_rows(
            dsn="postgresql://fake",
            rows=[row],
            item_code="I5B",
            formula_code="evidence_cluster_signal_v3",
            execute=False,
        )


def test_apply_patch_rows_supporting_marks_binding_not_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)
    row = patch_row(target_action="supporting_only", side=None, factor_refs={})

    payload = tool.apply_patch_rows(
        dsn="postgresql://fake",
        rows=[row],
        item_code="I5B",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["action_counts"] == {"supporting_only": 1}
    assert any(params and params[0] is False for params in conn.params)


def test_apply_patch_rows_canonicalizes_known_factor_label_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.factor_option_rows = formal_factor_option_rows()

    payload = tool.apply_patch_rows(
        dsn="postgresql://fake",
        rows=[patch_row()],
        item_code="I5B",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["canonicalized_label_count"] == 5
    canonicalized = {(row["factor_name"], row["from"], row["to"]) for row in payload["canonicalized_labels"]}
    assert ("appointment_importance", "高强度授权", "国家级、危局或长期关键授权。") in canonicalized
    assert ("source_factor", "正史明载", "标准史源且事件链清楚") in canonicalized


def test_apply_patch_rows_team_building_uses_team_factor_keys_only(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)
    row = patch_row(
        binding_code="BND-TEAM",
        factor_refs={
            "talent_quality_factor": {"label": "历史级人才"},
            "role_complementarity_factor": {"label": "高度互补"},
            "long_term_stability_factor": {"label": "长期稳定核心班底"},
        },
    )

    payload = tool.apply_patch_rows(
        dsn="postgresql://fake",
        rows=[row],
        item_code="I5B",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["applied_counts"]["retrieval_v3.claim_rule_binding_factor_choices"] == 3


def test_apply_patch_rows_rejects_unknown_factor_label(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_fake_db(monkeypatch)
    row = patch_row()
    row["factor_refs"] = dict(row["factor_refs"])  # type: ignore[arg-type]
    row["factor_refs"]["source_factor"] = {"label": "不存在的选项"}  # type: ignore[index]

    with pytest.raises(tool.FactorizationConsumerError, match="unknown factor option"):
        tool.apply_patch_rows(
            dsn="postgresql://fake",
            rows=[row],
            item_code="I5B",
            formula_code="evidence_cluster_signal_v3",
            execute=False,
        )


def test_apply_patch_rows_rejects_positive_side_negative_appointment_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.factor_option_rows.append(
        {
            "factor_id": 104,
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "factor_name": "appointment_effect",
            "factor_option_id": 1104,
            "option_code": "OPT-104",
            "label": "错任、错信、偏信、弱匹配或授权后结果较差，显示任用授权判断有问题。",
            "value_num": "-0.700000",
        }
    )
    row = patch_row()
    row["factor_refs"] = dict(row["factor_refs"])  # type: ignore[arg-type]
    row["factor_refs"]["appointment_effect"] = {"label": "错任、错信、偏信、弱匹配或授权后结果较差，显示任用授权判断有问题。"}  # type: ignore[index]

    with pytest.raises(tool.FactorizationConsumerError, match="positive side cannot use negative appointment_effect"):
        tool.apply_patch_rows(
            dsn="postgresql://fake",
            rows=[row],
            item_code="I5B",
            formula_code="evidence_cluster_signal_v3",
            execute=False,
        )


def test_cli_apply_patch_reads_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    conn = patch_fake_db(monkeypatch)
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")
    patch_path = tmp_path / "patch.jsonl"
    patch_path.write_text(json.dumps(patch_row(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    output_json = tmp_path / "factorization.json"

    assert tool.main([
        "apply-patch",
        "--patch-jsonl",
        str(patch_path),
        "--output-json",
        str(output_json),
    ]) == 0

    assert conn.rolled_back is True
    assert json.loads(output_json.read_text(encoding="utf-8"))["rows"] == 1
    assert json.loads(capsys.readouterr().out)["ok"] is True
