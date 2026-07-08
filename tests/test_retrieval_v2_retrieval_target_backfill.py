from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_retrieval_target_backfill as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def cache_root(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    write_jsonl(
        root / "seeds" / "shard_0001.jsonl",
        [
            {"name": "张良", "target_emperors": ["刘邦"]},
            {"name": "房玄龄", "target_emperors": ["李世民"]},
            {"name": "萧何", "target_emperors": ["刘邦"]},
        ],
    )
    return root


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
        self.conn.params.append(params)
        if "from retrieval_v3.rule_contracts" in lowered:
            self.row = dict(self.conn.contract)
            self.rows = []
            return
        if "count(*) as count" in lowered and "from retrieval_v3.rule_contract_rules" in lowered:
            self.row = {"count": len(self.conn.rules)}
            self.rows = []
            return
        if "from retrieval_v3.rule_contract_rules" in lowered:
            self.rows = [dict(row) for row in self.conn.rules]
            self.row = None
            return
        if "insert into retrieval_v3.retrieval_targets" in lowered:
            self.conn.next_id += 1
            self.row = {"id": self.conn.next_id, "target_code": f"TGT-I5B-{self.conn.next_id}"}
            self.rows = []
            return
        if "insert into retrieval_v3.target_rule_requirements" in lowered:
            self.conn.next_id += 1
            self.row = {"id": self.conn.next_id}
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
        self.next_id = 100
        self.contract = {
            "contract_id": 9,
            "contract_code": "I5B-RETRIEVAL-V3-TEST",
            "item_code": "I5B",
            "status": "active",
        }
        self.rules = [
            {"id": 1, "rule_code": "appointment_delegation", "rule_order": 10, "is_core_for_retrieval": True, "requirement_payload": {"min_usable_claims": 1}},
            {"id": 2, "rule_code": "team_building", "rule_order": 20, "is_core_for_retrieval": True, "requirement_payload": {"min_usable_claims": 1}},
        ]
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


def patch_fake_db(monkeypatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")
    return conn


def test_target_emperors_from_cache_dedupes_names(tmp_path: Path) -> None:
    assert tool.target_emperors_from_cache(cache_root(tmp_path)) == ["刘邦", "李世民"]


def test_apply_defaults_to_dry_run_without_target_inserts(tmp_path: Path, monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    root = cache_root(tmp_path)
    out_json = tmp_path / "targets.json"
    out_md = tmp_path / "targets.md"

    assert tool.main([
        "apply",
        "--cache-root",
        str(root),
        "--output-json",
        str(out_json),
        "--output-md",
        str(out_md),
    ]) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["write_db"] is False
    assert payload["executed"] is False
    assert payload["operation_counts"]["retrieval_v3.retrieval_targets"] == 2
    assert payload["operation_counts"]["retrieval_v3.retrieval_intents"] == 4
    assert conn.rolled_back is True
    assert any("from retrieval_v3.rule_contracts" in statement for statement in conn.statements)
    assert not any("insert into retrieval_v3.retrieval_targets" in statement for statement in conn.statements)


def test_execute_commits_seed_target_rows_with_v3_schema(tmp_path: Path, monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_target_backfill(
        cache_root=cache_root(tmp_path),
        emperor_names=(),
        env_file=None,
        dsn_env="IGNORED",
        schema_name="retrieval_v3",
        item_code="I5B",
        contract_code="",
        execute=True,
    )

    assert payload["write_db"] is True
    assert payload["executed"] is True
    assert conn.committed is True
    assert payload["executed_counts"]["retrieval_v3.retrieval_targets"] == 2
    assert payload["executed_counts"]["retrieval_v3.target_rule_requirements"] == 4
    assert payload["executed_counts"]["retrieval_v3.retrieval_intents"] == 4
    assert any("insert into retrieval_v3.retrieval_targets" in statement for statement in conn.statements)
    assert any("insert into retrieval_v3.retrieval_intents" in statement for statement in conn.statements)
