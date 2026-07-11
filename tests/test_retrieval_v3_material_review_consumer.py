from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_material_review_consumer as tool


def patch_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "review_code": "MRW-001",
        "queue_status": "resolved",
        "review_note": "噶礼案只证明其江南总督身份与互劾经过，不能证明康熙作出可计分授权；保留为上下文材料。",
        "binding_review_status": "supporting_context",
    }
    row.update(overrides)
    return row


def test_validate_patch_row_requires_high_information_chinese_note() -> None:
    with pytest.raises(tool.MaterialReviewConsumerError, match="high-information Chinese text"):
        tool.validate_patch_row(patch_row(review_note="not enough"))

    payload = tool.validate_patch_row(patch_row())

    assert payload["review_code"] == "MRW-001"
    assert payload["queue_status"] == "resolved"
    assert payload["binding_review_status"] == "supporting_context"


def test_validate_patch_row_rejects_unknown_statuses() -> None:
    with pytest.raises(tool.MaterialReviewConsumerError, match="unsupported queue_status"):
        tool.validate_patch_row(patch_row(queue_status="done"))

    with pytest.raises(tool.MaterialReviewConsumerError, match="unsupported binding_review_status"):
        tool.validate_patch_row(patch_row(binding_review_status="done"))


def test_validate_patch_rows_rejects_duplicate_review_code() -> None:
    with pytest.raises(tool.MaterialReviewConsumerError, match="duplicate review_code"):
        tool.validate_patch_rows([patch_row(), patch_row()])


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
        self.conn.statements.append(lowered)
        if "from retrieval_v3.material_review_queue mrq" in lowered and "where mrq.review_code" in lowered:
            code = params[0]
            row = self.conn.review_rows.get(code)
            self.row = dict(row) if row else None
            self.rows = []
            return
        if "from retrieval_v3.material_review_queue mrq" in lowered:
            self.rows = [dict(row) for row in self.conn.worklist_rows]
            self.row = None
            return
        self.row = None
        self.rows = []

    def fetchall(self) -> list[dict]:
        return self.rows

    def fetchone(self) -> dict | None:
        return self.row


class FakeConnection:
    def __init__(self) -> None:
        self.review_rows = {
            "MRW-001": {
                "id": 1,
                "review_code": "MRW-001",
                "queue_status": "ready",
                "review_note": "",
                "binding_id": 20,
                "candidate_id": None,
            }
        }
        self.worklist_rows = [
            {
                "review_code": "MRW-001",
                "queue_status": "ready",
                "review_kind": "low_confidence",
                "emperor_name": "玄烨",
                "object_name": "噶礼",
                "claim_summary": "噶礼以江南总督身份与巡抚张伯行互劾。",
            }
        ]
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


def patch_fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))
    return conn


def test_apply_patch_rows_defaults_to_db_backed_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.apply_patch_rows(dsn="postgresql://fake", rows=[patch_row()], execute=False)

    assert payload["ok"] is True
    assert payload["write_db"] is False
    assert payload["applied_counts"]["retrieval_v3.material_review_queue"] == 1
    assert payload["applied_counts"]["retrieval_v3.claim_rule_bindings"] == 1
    assert conn.rolled_back is True
    assert any("update retrieval_v3.material_review_queue" in statement for statement in conn.statements)
    assert any("update retrieval_v3.claim_rule_bindings" in statement for statement in conn.statements)


def test_apply_patch_rows_refuses_terminal_status_change(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.review_rows["MRW-001"]["queue_status"] = "resolved"
    conn.review_rows["MRW-001"]["review_note"] = "噶礼案只证明其江南总督身份与互劾经过，不能证明康熙作出可计分授权；保留为上下文材料。"

    with pytest.raises(tool.MaterialReviewConsumerError, match="terminal status"):
        tool.apply_patch_rows(dsn="postgresql://fake", rows=[patch_row(queue_status="blocked")], execute=True)


def test_cli_apply_patch_reads_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    conn = patch_fake_db(monkeypatch)
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")
    patch_path = tmp_path / "patch.jsonl"
    patch_path.write_text(json.dumps(patch_row(), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    output_json = tmp_path / "material_review.json"

    assert tool.main([
        "apply-patch",
            "--patch-jsonl",
            str(patch_path),
            "--pg-schema",
            "retrieval_v3",
            "--output-json",
        str(output_json),
    ]) == 0

    assert conn.rolled_back is True
    assert json.loads(output_json.read_text(encoding="utf-8"))["rows"] == 1
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_worklist_report_counts_pending_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_fake_db(monkeypatch)
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")

    payload = tool.worklist_report(env_file=None, dsn_env="IGNORED", item_code="I5B", scope="accepted-packs")

    assert payload["totals"]["material_review_items"] == 1
    assert payload["items"][0]["review_code"] == "MRW-001"
