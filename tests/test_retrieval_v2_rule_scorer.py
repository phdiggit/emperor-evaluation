from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.dev import retrieval_v2_rule_scorer as tool


def judgment(
    judgment_id: int,
    *,
    value: str,
    object_id: int = 100,
    binding_code: str | None = None,
    claim_id: int | None = None,
    predicate: str = "delegated_authority",
    object_role: str = "civil_delegate",
    choices: tuple[tool.FactorChoice, ...] | None = None,
) -> tool.JudgmentInput:
    return tool.JudgmentInput(
        factor_judgment_id=judgment_id,
        binding_id=judgment_id + 1000,
        binding_code=binding_code or f"BND-{judgment_id}",
        claim_id=claim_id if claim_id is not None else judgment_id + 2000,
        target_id=1,
        target_code="RT-I5B-LB",
        emperor_name="刘邦",
        source_pack_id=10,
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        target_action="score",
        side="positive",
        predicate=predicate,
        object_role=object_role,
        object_id=object_id,
        target_object_id=object_id + 5000,
        object_name="萧何",
        choices=choices or (tool.FactorChoice("source_factor", "基础史源", "SRC", Decimal(value)),),
    )


def test_compute_target_cluster_applies_same_object_decay() -> None:
    cluster = tool.compute_target_cluster([judgment(1, value="2.0"), judgment(2, value="1.0")])

    assert cluster["positive_signal"] == Decimal("2.350")
    assert cluster["negative_signal"] == Decimal("0.000")
    assert cluster["action_counts"] == {"score": 2}
    assert cluster["calc_detail"]["object_side_scores"]["positive"]["100"]["score"] == "2.350"


def test_compute_target_cluster_dedupes_same_claim_object_side() -> None:
    cluster = tool.compute_target_cluster(
        [
            judgment(1, value="2.0", claim_id=2000, object_role="revoked_or_failed_delegate"),
            judgment(2, value="2.0", claim_id=2000, object_role="military_delegate"),
        ]
    )

    assert cluster["positive_signal"] == Decimal("2.000")
    assert cluster["action_counts"]["score"] == 1
    assert len(cluster["material_scores"]) == 1
    assert cluster["calc_detail"]["scored_factor_judgment_ids"] == [1]
    assert cluster["calc_detail"]["deduped_factor_judgment_ids"] == [2]
    assert cluster["calc_detail"]["deduped_material_scores"][0]["reason"] == "same_claim_object_side"


def test_material_score_caps_single_material_at_four() -> None:
    score = tool.score_material(judgment(1, value="5.5"))

    assert score.raw_score == Decimal("5.500")
    assert score.abs_score == Decimal("4.000")


def test_material_score_rejects_positive_side_negative_result_feedback() -> None:
    bad = judgment(
        1,
        value="1.0",
        choices=(
            tool.FactorChoice("result_feedback", "效果较差", "BAD", Decimal("-0.700")),
        ),
    )

    with pytest.raises(tool.RetrievalV2RuleScorerError, match="positive side cannot use negative result_feedback"):
        tool.score_material(bad)


def flat_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for judgment_id, value in [(1, "2.0"), (2, "1.0")]:
        rows.append(
            {
                "factor_judgment_id": judgment_id,
                "binding_id": judgment_id + 1000,
                "binding_code": f"BND-{judgment_id}",
                "claim_id": judgment_id + 2000,
                "target_id": 1,
                "target_code": "RT-I5B-LB",
                "emperor_name": "刘邦",
                "source_pack_id": 10,
                "item_code": "I5B",
                "rule_code": "delegation",
                "formula_code": "evidence_cluster_signal_v3",
                "target_action": "score",
                "side": "positive",
                "object_role": "civil_delegate",
                "object_id": 100,
                "target_object_id": 5100,
                "object_name": "萧何",
                "factor_name": "source_factor",
                "option_label": "基础史源",
                "option_code": "SRC",
                "value_num": value,
            }
        )
    rows.append(
        {
            "factor_judgment_id": 3,
            "binding_id": 1003,
            "binding_code": "BND-3",
            "claim_id": 2003,
            "target_id": 1,
            "target_code": "RT-I5B-LB",
            "emperor_name": "刘邦",
            "source_pack_id": 10,
            "item_code": "I5B",
            "rule_code": "delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "target_action": "supporting_only",
            "side": "positive",
            "object_role": "civil_delegate",
            "object_id": 100,
            "target_object_id": 5100,
            "object_name": "萧何",
            "factor_name": "",
            "option_label": "",
            "option_code": "",
            "value_num": None,
        }
    )
    return rows


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn
        self.rows: list[dict] = []
        self.rowcount = 0

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        lowered = sql.lower()
        self.conn.statements.append(lowered)
        if "group by j.formula_code" in lowered:
            self.rows = [dict(row) for row in self.conn.alternate_formula_rows]
            self.rowcount = len(self.rows)
            return
        if "from retrieval_v2.claim_rule_binding_factor_judgments j" in lowered:
            self.rows = [dict(row) for row in self.conn.judgment_rows]
            self.rowcount = len(self.rows)
            return
        self.rows = []
        self.rowcount = 1

    def fetchall(self) -> list[dict]:
        return self.rows


class FakeConnection:
    def __init__(self) -> None:
        self.judgment_rows = flat_rows()
        self.alternate_formula_rows: list[dict[str, object]] = []
        self.statements: list[str] = []
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


def patch_fake_db(monkeypatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))
    return conn


def test_apply_rule_scores_defaults_to_db_backed_dry_run(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.apply_rule_scores(
        dsn="postgresql://fake",
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["write_db"] is False
    assert payload["totals"] == {"targets": 1, "judgments": 3, "material_scores": 2, "deduped_material_scores": 0}
    assert payload["clusters"][0]["positive_signal"] == "2.350"
    assert payload["applied_counts"]["retrieval_v2.claim_rule_binding_material_scores"] == 2
    assert payload["applied_counts"]["retrieval_v2.target_rule_score_clusters"] == 1
    assert conn.rolled_back is True
    assert any("insert into retrieval_v2.claim_rule_binding_material_scores" in statement for statement in conn.statements)
    assert any("insert into retrieval_v2.target_rule_score_clusters" in statement for statement in conn.statements)
    assert any("distinct on (sp2.target_id, sp2.contract_id)" in statement for statement in conn.statements)
    assert any("sp2.status = 'accepted'" in statement for statement in conn.statements)
    assert any("sp2.coverage_status = 'passed'" in statement for statement in conn.statements)


def test_apply_rule_scores_rejects_empty_wrong_formula_when_alternates_exist(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.judgment_rows = []
    conn.alternate_formula_rows = [
        {"formula_code": "evidence_cluster_signal_v3", "judgment_count": 18, "target_count": 1}
    ]

    with pytest.raises(tool.RetrievalV2RuleScorerError, match="available formula judgments"):
        tool.apply_rule_scores(
            dsn="postgresql://fake",
            item_code="I5B",
            rule_code="delegation",
            formula_code="standard",
            execute=False,
        )


def test_cli_apply_writes_report(tmp_path: Path, monkeypatch, capsys) -> None:
    conn = patch_fake_db(monkeypatch)
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")
    output_json = tmp_path / "score.json"

    assert tool.main([
        "apply",
        "--output-json",
        str(output_json),
    ]) == 0

    assert conn.rolled_back is True
    totals = json.loads(output_json.read_text(encoding="utf-8"))["totals"]
    assert totals["material_scores"] == 2
    assert totals["deduped_material_scores"] == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
