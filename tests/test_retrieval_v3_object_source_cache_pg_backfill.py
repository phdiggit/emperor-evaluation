from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_object_source_cache_pg_backfill as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def cache_root(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    write_jsonl(
        root / "seeds" / "shard_0001.jsonl",
        [
            {
                "name": "张良",
                "normalized_name": "张良",
                "object_code": "raw_obj:101",
                "object_pool_aliases": [{"alias": "张良", "alias_kind": "canonical"}],
                "aliases": ["张良", "子房"],
                "expanded_aliases": ["张良", "張良", "子房"],
                "object_type": "person",
                "period": "西汉",
                "person_cache_code": "PSC-ZL",
                "seed_sources": ["raw_objs", "raw_obj_aliases"],
                "source_hints": ["史记"],
                "target_emperors": ["刘邦"],
            }
        ],
    )
    write_jsonl(
        root / "person_coverage.jsonl",
        [
            {
                "person_name": "张良",
                "person_cache_code": "PSC-ZL",
                "has_source_document": True,
                "has_biography_source": True,
                "source_document_count": 1,
                "mention_slice_count": 2,
            }
        ],
    )
    write_jsonl(
        root / "source_documents.jsonl",
        [
            {
                "person_name": "张良",
                "document_cache_code": "OSD-001",
                "source_key": "wikisource:史记/卷55",
                "source_title": "史记/卷55",
                "source_role": "object_biography_or_mentions",
                "source_shape": "object_existing_source_candidate",
                "mention_slice_count": 2,
            }
        ],
    )
    write_jsonl(
        root / "mention_slices.jsonl",
        [
            {"person_name": "张良", "slice_cache_code": "OSS-001"},
            {"person_name": "张良", "slice_cache_code": "OSS-002"},
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
        if "from retrieval_v3.retrieval_targets" in lowered:
            self.rows = [dict(row) for row in self.conn.target_rows]
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
        self.target_rows = [{"target_id": 7, "target_code": "TGT-I5B-LB", "emperor_name": "刘邦", "item_code": "I5B"}]
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


def test_build_object_rows_from_cache_artifacts(tmp_path: Path) -> None:
    root = cache_root(tmp_path)
    payload = tool.build_object_rows(
        cache_root=root,
        cache_rows=tool.load_cache_rows(root),
        target_rows=[{"target_id": 7, "target_code": "TGT-I5B-LB", "emperor_name": "刘邦", "item_code": "I5B"}],
        item_code="I5B",
        schema_name="retrieval_v3",
    )

    assert payload["operation_counts"]["retrieval_v3.objects"] == 1
    assert payload["operation_counts"]["retrieval_v3.object_names"] == 3
    assert payload["operation_counts"]["retrieval_v3.person_profiles"] == 1
    assert payload["operation_counts"]["retrieval_v3.person_affiliations"] == 1
    assert payload["operation_counts"]["retrieval_v3.target_objects"] == 1
    assert {row["name_kind"] for row in payload["object_name_rows"]} == {"canonical", "alias", "script_variant"}
    assert payload["profile_rows"][0]["profile_payload"]["coverage"]["mention_slice_count"] == 2


def test_apply_defaults_to_dry_run_without_inserts(tmp_path: Path, monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    root = cache_root(tmp_path)
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    assert tool.main([
        "apply",
        "--cache-root",
        str(root),
        "--output-json",
        str(out_json),
        "--output-md",
        str(out_md),
        "--item-code",
        "I5B",
    ]) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["write_db"] is False
    assert payload["executed"] is False
    assert conn.rolled_back is True
    assert any("from retrieval_v3.retrieval_targets" in statement for statement in conn.statements)
    assert not any("insert into retrieval_v3.objects" in statement for statement in conn.statements)


def test_execute_commits_and_uses_v3_schema(tmp_path: Path, monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    root = cache_root(tmp_path)

    payload = tool.execute_backfill(
        cache_root=root,
        env_file=None,
        dsn_env="IGNORED",
        schema_name="retrieval_v3",
        item_code="I5B",
        execute=True,
    )

    assert payload["write_db"] is True
    assert payload["executed"] is True
    assert conn.committed is True
    assert payload["executed_counts"]["retrieval_v3.objects"] == 1
    assert any("insert into retrieval_v3.objects" in statement for statement in conn.statements)
    assert any("rv3_objects_identity_key_uk" in statement for statement in conn.statements)
