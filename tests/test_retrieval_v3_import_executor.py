from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_import_executor as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_fixture(root: Path, review_root: Path | None = None, *, missing_passage_ref: bool = False, bad_candidate_direction: bool = False) -> dict[str, str]:
    pack = "SPK-I5B-LH-DELEGATION-ABC"
    target = "TGT-I5B-LH"
    doc = f"{pack}::DOC-001"
    passage = f"{pack}::PAS-001"
    claim = f"{pack}::CLM-001"
    binding = f"{pack}::BND-001"
    candidate = f"{pack}::CRBC-001"
    source_passage_refs = [f"{pack}::PAS-MISSING"] if missing_passage_ref else [passage]
    write_jsonl(
        root / "source_packs.jsonl",
        [
            {
                "source_pack_code": pack,
                "target_code": target,
                "emperor_name": "刘恒",
                "item_code": "I5B",
                "rule_code": "delegation",
                "run_root": "tmp/run",
                "run_dir": "tmp/run/TGT-I5B-LH_delegation",
                "manifest_payload": {"accepted": True},
            }
        ],
    )
    write_jsonl(root / "source_pack_artifacts.jsonl", [{"source_pack_code": pack, "kind": "judge", "path": "judge.json"}])
    write_jsonl(
        root / "source_documents.jsonl",
        [
            {
                "source_pack_code": pack,
                "document_code": doc,
                "raw_document_code": "DOC-001",
                "title": "史記/卷102",
                "source_title": "史記",
            }
        ],
    )
    write_jsonl(
        root / "source_passages.jsonl",
        [
            {
                "source_pack_code": pack,
                "document_code": doc,
                "passage_code": passage,
                "raw_passage_code": "PAS-001",
                "locator": "chars:1-20",
                "raw_text": "上令冯唐持节赦魏尚。",
                "quote_hash": "abc",
            }
        ],
    )
    write_jsonl(
        root / "material_claims.jsonl",
        [
            {
                "source_pack_code": pack,
                "claim_code": claim,
                "raw_claim_code": "CLM-001",
                "emperor_name": "刘恒",
                "object_name": "冯唐",
                "object_type": "person",
                "claim_summary": "文帝遣冯唐持节赦魏尚。",
                "direction": "positive",
                "source_passage_refs": source_passage_refs,
            }
        ],
    )
    write_jsonl(
        root / "primary_claim_rule_bindings.jsonl",
        [
            {
                "source_pack_code": pack,
                "binding_code": binding,
                "raw_binding_code": "BND-001",
                "claim_code": claim,
                "rule_code": "delegation",
                "predicate": "delegated_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
            }
        ],
    )
    write_jsonl(
        root / "claim_rule_binding_candidates.jsonl",
        [
            {
                "source_pack_code": pack,
                "candidate_code": candidate,
                "claim_code": claim,
                "source_item_code": "I5B",
                "source_rule_code": "delegation",
                "candidate_item_code": "",
                "candidate_rule_code": "team_building",
                "candidate_direction": "sideways" if bad_candidate_direction else "",
                "reason": "同一事实也可提示团队建设。",
                "candidate_payload": {
                    "hint_status": "future_rule_hint",
                    "source_binding": {"rule_code": "team_building"},
                },
            }
        ],
    )
    write_jsonl(root / "coverage_gap_events.jsonl", [{"idem_key": "gap-1", "source_pack_code": pack, "target_code": target, "rule_code": "delegation"}])
    if review_root is not None:
        write_jsonl(
            review_root / "object_resolution_worklist.jsonl",
            [
                {
                    "object_resolution_code": "ORW-001",
                    "emperor_name": "刘恒",
                    "item_code": "I5B",
                    "object_group_key": "冯唐",
                    "canonical_name_candidate": "冯唐",
                    "object_types": ["person"],
                    "review_status": "candidate_new_or_existing",
                    "review_reasons": ["single_person_like_name"],
                    "source_pack_codes": [pack],
                }
            ],
        )
        write_jsonl(
            review_root / "material_review_worklist.jsonl",
            [
                {
                    "material_review_code": "MRW-001",
                    "review_status": "needs_review",
                    "review_flags": ["low_confidence"],
                    "claim_code": claim,
                    "binding_code": binding,
                }
            ],
        )
    return {"pack": pack, "target": target, "claim": claim, "binding": binding}


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
        self.conn.executions.append((lowered, params))
        if "from retrieval_v3.retrieval_targets" in lowered:
            self.rows = [{"id": 1, "target_code": "TGT-I5B-LH", "contract_id": 10, "emperor_name": "刘恒", "item_code": "I5B"}]
            self.row = None
            return
        if "from retrieval_v3.rule_contract_rules" in lowered:
            self.rows = [
                {"id": 20, "contract_id": 10, "rule_code": "delegation"},
                {"id": 21, "contract_id": 10, "rule_code": "team_building"},
            ]
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
        self.statements: list[str] = []
        self.executions: list[tuple[str, object]] = []
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


def test_apply_defaults_to_db_backed_dry_run_without_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    normalized = tmp_path / "normalized"
    review = tmp_path / "review"
    write_fixture(normalized, review)
    conn = patch_fake_db(monkeypatch)
    output_json = tmp_path / "apply.json"
    output_md = tmp_path / "apply.md"

    assert tool.main([
        "apply",
        "--normalized-root",
        str(normalized),
        "--review-root",
        str(review),
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
    assert not any("insert into retrieval_v3.source_packs" in statement for statement in conn.statements)
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_execute_import_uses_dependency_order_with_fake_connection(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    review = tmp_path / "review"
    write_fixture(normalized, review)
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_import(
        normalized_root=normalized,
        review_root=review,
        env_file=None,
        dsn_env="IGNORED_DSN",
        execute=True,
    )

    assert payload["ok"] is True
    assert payload["write_db"] is True
    assert payload["executed"] is True
    assert conn.committed is True
    assert payload["executed_counts"]["retrieval_v3.source_packs"] == 1
    assert payload["executed_counts"]["retrieval_v3.material_review_queue"] == 1
    insert_statements = [statement for statement in conn.statements if "insert into retrieval_v3." in statement]
    assert "insert into retrieval_v3.source_packs" in insert_statements[0]
    assert any("insert into retrieval_v3.claim_rule_bindings" in statement for statement in insert_statements)


def test_execute_import_can_write_draft_source_pack_for_shadow_runs(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized)
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_import(
        normalized_root=normalized,
        review_root=None,
        env_file=None,
        dsn_env="IGNORED_DSN",
        execute=True,
        source_pack_status="draft",
    )

    assert payload["ok"] is True
    assert payload["source_pack_status"] == "draft"
    source_pack_params = next(params for sql, params in conn.executions if "insert into retrieval_v3.source_packs" in sql)
    assert "draft" in source_pack_params


def test_execute_import_preserves_claim_and_binding_review_status(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized)
    claim_rows = [
        json.loads(line)
        for line in (normalized / "material_claims.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    claim_rows[0]["review_status"] = "needs_review"
    write_jsonl(normalized / "material_claims.jsonl", claim_rows)
    binding_rows = [
        json.loads(line)
        for line in (normalized / "primary_claim_rule_bindings.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    binding_rows[0]["review_status"] = "needs_review"
    write_jsonl(normalized / "primary_claim_rule_bindings.jsonl", binding_rows)
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_import(
        normalized_root=normalized,
        review_root=None,
        env_file=None,
        dsn_env="IGNORED_DSN",
        execute=True,
    )

    assert payload["ok"] is True
    claim_params = next(params for sql, params in conn.executions if "insert into retrieval_v3.material_claims" in sql)
    binding_params = next(params for sql, params in conn.executions if "insert into retrieval_v3.claim_rule_bindings" in sql)
    assert "needs_review" in claim_params
    assert "needs_review" in binding_params


def test_execute_import_writes_structured_candidate_payload(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized)
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_import(
        normalized_root=normalized,
        review_root=None,
        env_file=None,
        dsn_env="IGNORED_DSN",
        execute=True,
    )

    assert payload["ok"] is True
    candidate_params = next(params for sql, params in conn.executions if "insert into retrieval_v3.claim_rule_binding_candidates" in sql)
    assert candidate_params[8] == "team_building"
    assert candidate_params[9] == "future_rule_hint"
    assert json.loads(candidate_params[10]) == {}
    candidate_payload = json.loads(candidate_params[-1])
    assert candidate_payload["hint_status"] == "future_rule_hint"
    assert candidate_payload["source_binding"]["rule_code"] == "team_building"


def test_execute_import_writes_candidate_lane_required_facts_and_profile(tmp_path: Path, monkeypatch) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized)
    rows = [
        json.loads(line)
        for line in (normalized / "claim_rule_binding_candidates.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[0]["candidate_item_code"] = "I5C"
    rows[0]["candidate_rule_code"] = "power_control"
    rows[0]["candidate_lane"] = "I5C.power_control"
    rows[0]["hint_status"] = "future_rule_hint"
    rows[0]["required_facts_present"] = {"actor": True, "action": True, "outcome": False}
    rows[0]["routed_by_profile"] = "personnel_political_wide"
    write_jsonl(normalized / "claim_rule_binding_candidates.jsonl", rows)
    conn = patch_fake_db(monkeypatch)

    payload = tool.execute_import(
        normalized_root=normalized,
        review_root=None,
        env_file=None,
        dsn_env="IGNORED_DSN",
        execute=True,
    )

    assert payload["ok"] is True
    candidate_params = next(params for sql, params in conn.executions if "insert into retrieval_v3.claim_rule_binding_candidates" in sql)
    assert candidate_params[7] == "power_control"
    assert candidate_params[8] == "I5C.power_control"
    assert candidate_params[9] == "future_rule_hint"
    assert json.loads(candidate_params[10]) == {"actor": True, "action": True, "outcome": False}
    assert candidate_params[11] == "personnel_political_wide"
