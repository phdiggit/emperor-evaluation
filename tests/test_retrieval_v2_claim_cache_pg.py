from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_cache as fs_tool
from scripts.dev import retrieval_v2_claim_cache_pg as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_cache(cache_root: Path) -> None:
    slice_hash = fs_tool.slice_hash_from_row(
        {
            "slice_code": "SLI-001",
            "document_code": "DOC-001",
            "object_name": "汤和",
            "text": "帝命汤和守常州，常州安辑。",
        }
    )
    claim = {
        "claim_key": "CLMK-001",
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "object_type": "person",
        "direction": "positive",
        "claim_summary": "朱元璋命汤和镇守常州。",
        "confidence": 0.9,
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "朱元璋",
            "object": "汤和",
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "outcome": "常州安辑",
            "time_context": "洪武初",
        },
        "first_run_code": "RUN-001",
        "last_run_code": "RUN-001",
        "raw_output_path": "/tmp/judge_result.final.json",
        "extractor_version": "claim_extraction_only",
        "status": "active",
        "seen_count": 2,
    }
    source_slice = {
        "slice_hash": slice_hash,
        "object_name": "汤和",
        "document_code": "DOC-001",
        "source_slice_ref": "SLI-001",
        "slice_text_preview": "帝命汤和守常州，常州安辑。",
        "first_run_code": "RUN-001",
        "seen_count": 2,
    }
    evidence = {
        "evidence_key": "EVD-001",
        "claim_key": "CLMK-001",
        "slice_hash": slice_hash,
        "source_slice_ref": "SLI-001",
        "document_code": "DOC-001",
        "object_name": "汤和",
        "span_payload": {"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"},
        "slice_text_preview": "帝命汤和守常州，常州安辑。",
        "raw_output_path": "/tmp/judge_result.final.json",
        "first_run_code": "RUN-001",
    }
    write_jsonl(cache_root / "claims.jsonl", [claim])
    write_jsonl(cache_root / "source_slices.jsonl", [source_slice])
    write_jsonl(cache_root / "claim_evidence.jsonl", [evidence])
    write_jsonl(cache_root / "import_runs.jsonl", [{"run_code": "RUN-001", "claim_key_count": 1}])


def test_prepared_cache_rows_maps_filesystem_cache_to_pg_shape(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)

    rows = tool.prepared_cache_rows(cache_root)

    assert tool.row_counts(rows) == {
        "claim_cache": 1,
        "claim_source_slices": 1,
        "claim_evidence": 1,
        "import_runs": 1,
    }
    assert rows["claims"][0]["claim_type"] == "material_action"
    assert rows["claims"][0]["fact_schema"] == "political_action_v1"
    assert rows["claims"][0]["action_type"] == "授权"
    assert rows["claims"][0]["seen_count"] == 2
    assert rows["claims"][0]["canonical_event_key"].startswith("CEK-")
    assert rows["claims"][0]["event_group_key"].startswith("CEG-")
    assert rows["claims"][0]["claim_grain"] == "event_chain"
    assert rows["claims"][0]["fact_type"] == "material_action"
    assert rows["claims"][0]["outcome_support"] == "direct"
    assert rows["claims"][0]["atomic_fact_payload"]["outcome_support"] == "direct"
    assert rows["claims"][0]["near_duplicate_group_payload"]["object_name"] == "汤和"
    assert rows["claims"][0]["quality_flags"] == []
    assert rows["source_slices"][0]["text_hash"]
    assert rows["claim_evidence"][0]["support_level"] == "direct"
    assert rows["claim_evidence"][0]["quote_preview"] == "命汤和守常州"
    assert tool.validate_prepared_rows(rows) == []


def test_validate_prepared_rows_reports_broken_evidence(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)
    write_jsonl(
        cache_root / "claim_evidence.jsonl",
        [
            {
                "evidence_key": "EVD-BAD",
                "claim_key": "CLMK-MISSING",
                "slice_hash": "SLH-MISSING",
            }
        ],
    )

    rows = tool.prepared_cache_rows(cache_root)
    issues = tool.validate_prepared_rows(rows)

    assert {issue["kind"] for issue in issues} == {"evidence_missing_claim", "evidence_missing_slice"}


def test_object_inventory_counts_directions_and_actions(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)

    inventory = tool.object_inventory(tool.prepared_cache_rows(cache_root))

    assert inventory["汤和"]["claim_count"] == 1
    assert inventory["汤和"]["direction_counts"] == {"positive": 1}
    assert inventory["汤和"]["action_type_counts"] == {"授权": 1}


def test_claim_cache_pg_sql_stays_in_cache_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    rendered = tool.schema_cursor
    assert rendered
    assert tool.DEFAULT_DSN_ENV == "EMPEROR_EVAL_RETRIEVAL_V3_DSN"
    assert tool.DEFAULT_PG_SCHEMA == "retrieval_v3"
    assert tool.DEFAULT_ALLOWED_EXTRACTOR_VERSIONS == ("claim_extraction_only:v4_structured_ref_policy",)
    assert "retrieval_v2.claim_cache" in source
    assert "canonical_event_key" in source
    assert "near_duplicate_group_payload" in source
    assert "claim_grain" in source
    assert "quality_flags" in source
    assert "event_group_key" in source
    assert "atomic_fact_payload" in source
    assert "cleanup-orphan-source-slices" in source
    assert "retrieval_v2.claim_source_slices" in source
    assert "retrieval_v2.claim_evidence" in source
    assert "insert into retrieval_v2.claim_rule_bindings" not in source
    assert "insert into retrieval_v2.target_rule_score_clusters" not in source


def test_extractor_version_policy_blocks_legacy_by_default(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)
    rows = tool.prepared_cache_rows(cache_root)

    issues = tool.validate_extractor_version_policy(
        rows,
        allowed_extractor_versions=tool.DEFAULT_ALLOWED_EXTRACTOR_VERSIONS,
    )

    assert issues == [
        {
            "kind": "unsupported_extractor_version",
            "allowed_extractor_versions": ["claim_extraction_only:v4_structured_ref_policy"],
            "observed_extractor_versions": {"claim_extraction_only": 1},
            "blocked_extractor_versions": {"claim_extraction_only": 1},
            "hint": "Pass --allowed-extractor-version for a reviewed current version, or --allow-legacy-extractor-version for an explicit legacy import.",
        }
    ]


def test_extractor_version_policy_allows_explicit_legacy_import(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)
    rows = tool.prepared_cache_rows(cache_root)

    issues = tool.validate_extractor_version_policy(
        rows,
        allowed_extractor_versions=tool.DEFAULT_ALLOWED_EXTRACTOR_VERSIONS,
        allow_legacy_extractor_version=True,
    )

    assert issues == []


def test_cleanup_where_clause_requires_selector() -> None:
    try:
        tool.cleanup_where_clause()
    except tool.ClaimCachePgError as exc:
        assert "requires at least one selector" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cleanup_where_clause should reject empty selectors")


def test_cleanup_where_clause_is_parameterized() -> None:
    where_sql, params = tool.cleanup_where_clause(
        last_run_codes=["RUN-OLD"],
        extractor_versions=["claim_extraction_only"],
        emperor_names=["朱元璋"],
    )

    assert where_sql == "where last_run_code = any(%s) and extractor_version = any(%s) and emperor_name = any(%s)"
    assert params == [["RUN-OLD"], ["claim_extraction_only"], ["朱元璋"]]


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
        if "from retrieval_v3.claim_cache" in lowered and "count(*) as count" not in lowered:
            self.rows = [dict(row) for row in self.conn.claim_rows]
            self.row = None
            return
        if "select count(*) as count from retrieval_v3." in lowered:
            self.row = {"count": len(self.conn.claim_rows) if "retrieval_v3.claim_cache" in lowered else 0}
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
        self.claim_rows = [
            {
                "claim_key": "CLMK-001",
                "emperor_name": "朱元璋",
                "object_name": "汤和",
                "object_type": "person",
                "direction": "positive",
                "action_type": "授权",
                "event_scope": "军事",
                "office_or_domain": "常州镇守",
                "time_context": "洪武初",
                "outcome": "常州安辑",
                "claim_summary": "朱元璋命汤和镇守常州。",
                "fact_payload": {"fact_schema": "political_action_v1", "object": "汤和"},
                "canonical_event_key": "",
                "claim_grain": "",
            }
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


def test_quality_backfill_defaults_to_dry_run(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    report = tool.backfill_quality_fields(
        env_file=None,
        dsn_env="IGNORED",
        schema_name="retrieval_v3",
        execute=False,
    )

    assert report["write_db"] is False
    assert report["totals"]["candidate_claims"] == 1
    assert conn.rolled_back is True
    assert not any("update retrieval_v3.claim_cache" in statement for statement in conn.statements)


def test_quality_backfill_execute_updates_hot_fields(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    report = tool.backfill_quality_fields(
        env_file=None,
        dsn_env="IGNORED",
        schema_name="retrieval_v3",
        execute=True,
    )

    assert report["executed"] is True
    assert report["executed_counts"]["retrieval_v3.claim_cache"] == 1
    assert conn.committed is True
    assert any("update retrieval_v3.claim_cache" in statement for statement in conn.statements)
    update_params = next(params for statement, params in zip(conn.statements, conn.params) if "update retrieval_v3.claim_cache" in statement)
    assert update_params[0].startswith("CEK-")
    assert update_params[3] == "event_chain"
