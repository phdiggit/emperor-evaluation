from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.formal_schema_draft import (  # noqa: E402
    BLOCKED_REPORT_TERMS,
    PHASE_1_BASE_TABLES,
    PHASE_2_RELATIONSHIP_TABLES,
    PHASE_3_DOWNSTREAM_TABLES,
    build_contract_report,
    main,
    report_as_json,
)


FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]
REQUIRED_REPORT_KEYS = {
    "mode",
    "draft_version",
    "status",
    "source_of_truth",
    "schema_scope",
    "phase_1_base_tables",
    "phase_2_relationship_tables",
    "phase_3_downstream_tables",
    "table_specs",
    "schema_diff_from_prototypes",
    "table_by_table_gates",
    "blocked_tables",
    "resolver_prerequisites",
    "migration_preconditions",
    "non_goals",
    "strict_boundaries",
    "future_work",
    "limitations",
}
REQUIRED_TABLE_SPEC_KEYS = {
    "table_name",
    "phase",
    "purpose",
    "source_jsonl_files",
    "prototype_tool",
    "key_columns",
    "payload_columns",
    "relationship_columns",
    "write_allowed_in_phase_1",
    "requires_resolver_output",
    "manual_review_gate_required",
    "formal_ddl_ready",
    "blocked_reason",
}
REQUIRED_GATE_KEYS = {
    "table_name",
    "contract_report_green",
    "prototype_smoke_green",
    "apply_smoke_required",
    "resolver_gate_required",
    "manual_review_gate_required",
    "seed_gate_required",
    "cutover_gate_required",
    "phase_1_allowed",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in formal schema draft")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if self.name == ".env" or "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"formal schema draft must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["draft_version"] == "formal-target-schema-draft-v1"
    assert report["status"] == "Proposed"
    assert set(report) == REQUIRED_REPORT_KEYS


def test_adr_file_exists_and_is_proposed() -> None:
    path = ROOT / "archive" / "docs" / "adr" / "ADR-formal-target-schema-draft.md"

    assert path.is_file()
    assert _status_value(path) == "Proposed."
    content = path.read_text(encoding="utf-8")
    for heading in [
        "## Status",
        "## Context",
        "## Decision",
        "## Draft Schema Scope",
        "## Phase 1 Base Tables",
        "## Phase 2 Relationship Tables",
        "## Phase 3 Downstream Tables",
        "## Table-by-Table Gates",
        "## Schema Diff from Prototypes",
        "## Rejected Alternatives",
        "## Risks",
        "## Future Work",
    ]:
        assert heading in content
    for forbidden in ["Accepted", "Finalized"]:
        assert forbidden not in content


def test_phase_1_base_tables_cover_required_domains() -> None:
    report = build_contract_report()
    phase_1 = set(report["phase_1_base_tables"])

    assert report["phase_1_base_tables"] == list(PHASE_1_BASE_TABLES)
    assert {"query_profiles", "search_tasks"} <= phase_1
    assert {"src_hosts", "src_docs", "doc_revs", "passages"} <= phase_1
    assert "evd_cards" in phase_1
    assert "clusters" in phase_1
    assert "anchors" in phase_1


def test_phase_2_relationship_tables_are_blocked_in_phase_1() -> None:
    report = build_contract_report()
    specs = {spec["table_name"]: spec for spec in report["table_specs"]}

    assert report["phase_2_relationship_tables"] == list(PHASE_2_RELATIONSHIP_TABLES)
    assert {"evd_src_links", "cluster_evd", "anchor_links"} <= set(report["phase_2_relationship_tables"])
    for table_name in report["phase_2_relationship_tables"]:
        spec = specs[table_name]
        assert spec["requires_resolver_output"] is True
        assert spec["manual_review_gate_required"] is True
        assert spec["write_allowed_in_phase_1"] is False
        assert spec["formal_ddl_ready"] is False
        assert spec["blocked_reason"]


def test_phase_3_downstream_tables_use_safe_names() -> None:
    report = build_contract_report()

    assert report["phase_3_downstream_tables"] == list(PHASE_3_DOWNSTREAM_TABLES)
    assert set(report["phase_3_downstream_tables"]) == {
        "review_items",
        "adjudication_tables",
        "metric_records",
        "metric_releases",
    }
    _assert_no_blocked_report_terms(report)


def test_every_table_spec_and_gate_has_required_fields() -> None:
    report = build_contract_report()
    spec_names = {spec["table_name"] for spec in report["table_specs"]}
    gate_names = {gate["table_name"] for gate in report["table_by_table_gates"]}

    assert spec_names == set(PHASE_1_BASE_TABLES + PHASE_2_RELATIONSHIP_TABLES + PHASE_3_DOWNSTREAM_TABLES)
    assert gate_names == spec_names
    for spec in report["table_specs"]:
        assert set(spec) == REQUIRED_TABLE_SPEC_KEYS
    for gate in report["table_by_table_gates"]:
        assert set(gate) == REQUIRED_GATE_KEYS


def test_schema_diff_from_prototypes_covers_required_diff_types() -> None:
    diff_types = {item["diff_type"] for item in build_contract_report()["schema_diff_from_prototypes"]}

    assert {"kept", "renamed", "split", "deferred", "blocked", "new_in_formal_draft"} <= diff_types


def test_table_by_table_gates_cover_apply_resolver_manual_seed_cutover() -> None:
    gates = build_contract_report()["table_by_table_gates"]
    by_table = {gate["table_name"]: gate for gate in gates}

    assert by_table["imports"]["apply_smoke_required"] is False
    assert by_table["evd_src_links"]["resolver_gate_required"] is True
    assert by_table["cluster_evd"]["manual_review_gate_required"] is True
    assert by_table["anchor_links"]["seed_gate_required"] is True
    assert by_table["metric_releases"]["cutover_gate_required"] is True
    assert by_table["metric_releases"]["phase_1_allowed"] is False


def test_source_of_truth_and_non_goals_preserve_boundaries() -> None:
    report = build_contract_report()
    non_goals = " ".join(report["non_goals"])

    assert "canonical JSONL remains source-of-truth" in report["source_of_truth"]
    assert "does not modify db/schema.sql" in non_goals
    assert "does not modify db/postgres/001_init.sql" in non_goals
    assert "does not execute DDL or migration" in non_goals
    assert "does not switch the JSONL write source" in non_goals
    assert "does not generate seed artifacts" in non_goals
    assert "does_not_read_dotenv" in report["strict_boundaries"]
    assert "does_not_connect_to_database" in report["strict_boundaries"]


def test_contract_report_contains_no_blocked_terms() -> None:
    _assert_no_blocked_report_terms(build_contract_report())


def test_source_is_contract_only() -> None:
    source = (ROOT / "scripts" / "platform" / "formal_schema_draft.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in formal schema draft CLI")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["status"] == "Proposed"


def _assert_no_blocked_report_terms(report: dict) -> None:
    text = report_as_json(report).lower()
    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def _status_value(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "## Status":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    return candidate.strip()
    raise AssertionError(f"missing status section: {path}")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
