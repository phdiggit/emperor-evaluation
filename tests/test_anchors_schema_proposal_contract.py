from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.anchors_schema_proposal import (  # noqa: E402
    BLOCKED_REPORT_TERMS,
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


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors schema proposal tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["proposal_version"] == "anchors-schema-proposal-v1"
    assert report["status"] == "Proposed"
    assert set(report["proposed_tables"]) == {"anchors", "anchor_links"}
    assert set(report["proposed_columns_by_table"]) == {"anchors", "anchor_links"}


def test_proposed_columns_include_core_anchor_and_link_contract() -> None:
    report = build_contract_report()

    anchors = set(report["proposed_columns_by_table"]["anchors"])
    anchor_links = set(report["proposed_columns_by_table"]["anchor_links"])

    assert {"code", "anchor_type", "payload"} <= anchors
    assert {"anchor_code", "target_domain", "target_code", "resolver_status", "payload"} <= anchor_links


def test_input_sources_and_anchor_reference_fields_are_complete() -> None:
    report = build_contract_report()

    assert set(report["input_jsonl_sources"]) == {
        "data/thematic_anchors.jsonl",
        "data/thematic_anchor_objects.jsonl",
        "data/thematic_anchor_events.jsonl",
        "data/thematic_anchor_mechanisms.jsonl",
        "data/query_profiles.jsonl",
        "data/evidence_cards.jsonl",
        "data/evidence_clusters.jsonl",
    }
    assert set(report["anchor_source_files"]) == {
        "data/thematic_anchors.jsonl",
        "data/thematic_anchor_objects.jsonl",
        "data/thematic_anchor_events.jsonl",
        "data/thematic_anchor_mechanisms.jsonl",
    }
    assert {"object_anchor", "object_anchors", "thematic_anchor_targets"} <= set(report["anchor_reference_fields"])


def test_resolver_status_domains_and_blocked_relationship_writes_are_declared() -> None:
    report = build_contract_report()

    assert report["first_stage_resolver_status_values"] == [
        "unresolved_candidate",
        "manual_review_required",
        "blocked_pending_schema",
    ]
    assert "resolver_ready" in report["resolver_status_values"]
    assert set(report["target_domains"]) == {
        "person",
        "evidence_card",
        "evidence_cluster",
        "source_document",
        "source_passage_candidate",
        "query_profile",
        "search_task",
        "subitem",
    }
    assert {
        "anchor_links_write",
        "evidence_relationship_write",
        "cluster_relationship_write",
        "source_relationship_write",
        "downstream_release_write",
    } <= set(report["blocked_relationship_writes"])


def test_contract_report_contains_no_blocked_terms_or_connection_details() -> None:
    text = report_as_json(build_contract_report()).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text
    for forbidden in ["postgresql://", "password", "lan ip", "192.168.", "10.0.", "172.16."]:
        assert forbidden not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors schema proposal tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["proposal_version"] == "anchors-schema-proposal-v1"


def test_default_contract_paths_do_not_touch_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors schema proposal tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before


def test_proposal_tool_uses_no_database_driver_shell_or_forbidden_dsn_names() -> None:
    source = (ROOT / "scripts" / "platform" / "anchors_schema_proposal.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
