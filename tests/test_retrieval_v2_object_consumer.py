from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_object_consumer as tool


def queue_row(*, diagnosis: str = "single_person_like_name", status: str = "ready") -> dict:
    return {
        "id": 1,
        "resolution_code": "ORW-001",
        "idem_key": "TGT-I5B-LH|I5B|冯唐",
        "target_id": 1,
        "target_code": "TGT-I5B-LH",
        "source_pack_id": 10,
        "source_pack_code": "SPK-I5B-LH",
        "claim_id": None,
        "object_name": "冯唐",
        "normalized_name": "冯唐",
        "object_type": "person",
        "object_group_key": "冯唐",
        "suggested_identity_key": "",
        "queue_status": status,
        "diagnosis": diagnosis,
        "resolution_note": "",
        "resolved_object_id": None,
        "queue_payload": {
            "claim_count": 1,
            "primary_binding_count": 1,
            "observed_names": ["冯唐"],
            "object_types": ["person"],
            "review_reasons": [diagnosis],
        },
    }


def link_row() -> dict:
    return {
        "claim_id": 20,
        "claim_code": "CLM-001",
        "object_name": "冯唐",
        "object_group_key": "冯唐",
        "role": "civil_delegate",
        "confidence": 0.91,
        "binding_ids": [30],
        "binding_codes": ["BND-001"],
        "binding_count": 1,
        "source_pack_id": 10,
        "target_id": 1,
        "target_code": "TGT-I5B-LH",
    }


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
        if "from retrieval_v2.object_resolution_queue" in lowered:
            self.rows = [dict(row) for row in self.conn.queue_rows]
            self.row = None
            return
        if "from retrieval_v2.claim_rule_bindings" in lowered:
            self.rows = [dict(row) for row in self.conn.link_rows]
            self.row = None
            return
        self.conn.next_id += 1
        self.row = {"id": self.conn.next_id}
        self.rows = []

    def fetchall(self) -> list[dict]:
        return self.rows

    def fetchone(self) -> dict | None:
        return self.row


class FakeConnection:
    def __init__(self) -> None:
        self.next_id = 100
        self.queue_rows = [queue_row()]
        self.link_rows = [link_row()]
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
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")
    return conn


def test_build_object_plan_blocks_non_single_person_queue() -> None:
    payload = tool.build_object_plan([queue_row(diagnosis="multiple_observed_names")], [link_row()])

    assert payload["ok"] is False
    assert payload["totals"]["blockers"] == 1
    assert payload["operation_counts"]["retrieval_v2.material_object_links"] == 0


def test_build_object_plan_counts_script_variant_name() -> None:
    row = queue_row()
    row["object_name"] = "張廷玉"
    row["normalized_name"] = "张廷玉"
    row["queue_payload"]["observed_names"] = ["張廷玉"]

    payload = tool.build_object_plan([row], [])

    assert payload["operation_counts"]["retrieval_v2.object_names"] == 2


def test_apply_defaults_to_db_backed_dry_run_without_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    conn = patch_fake_db(monkeypatch)
    output_json = tmp_path / "objects.json"
    output_md = tmp_path / "objects.md"

    assert tool.main([
        "apply",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["write_db"] is False
    assert payload["executed"] is False
    assert conn.rolled_back is True
    assert not any("insert into retrieval_v2.objects" in statement for statement in conn.statements)
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_execute_writes_objects_before_material_links(tmp_path: Path, monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_object_consumer(env_file=None, dsn_env="IGNORED_DSN", execute=True)

    assert payload["ok"] is True
    assert payload["write_db"] is True
    assert payload["executed"] is True
    assert conn.committed is True
    assert payload["executed_counts"]["retrieval_v2.objects"] == 1
    assert payload["executed_counts"]["retrieval_v2.material_object_links"] == 1
    insert_statements = [statement for statement in conn.statements if "insert into retrieval_v2." in statement]
    assert "insert into retrieval_v2.objects" in insert_statements[0]
    assert "insert into retrieval_v2.material_object_links" in insert_statements[-1]


def test_execute_writes_script_variant_name_when_normalized_differs(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.queue_rows[0]["object_name"] = "張廷玉"
    conn.queue_rows[0]["normalized_name"] = "张廷玉"
    conn.queue_rows[0]["object_group_key"] = "张廷玉"
    conn.queue_rows[0]["queue_payload"]["observed_names"] = ["張廷玉"]

    payload = tool.execute_object_consumer(env_file=None, dsn_env="IGNORED_DSN", execute=True)

    assert payload["executed_counts"]["retrieval_v2.object_names"] == 2
    name_inserts = [statement for statement in conn.statements if "insert into retrieval_v2.object_names" in statement]
    assert len(name_inserts) == 2
