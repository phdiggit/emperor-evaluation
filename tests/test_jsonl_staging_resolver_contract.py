from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_resolver_contract import (
    RESOLVER_VERSION,
    build_contract_report,
    main,
    report_as_json,
)
from scripts.platform.jsonl_target_mapping import CANONICAL_JSONL_FILES


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "jsonl_import"
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


def test_resolver_contract_report_has_required_shape() -> None:
    report = build_contract_report(source_root=ROOT)

    assert report["mode"] == "contract-report"
    assert report["resolver_version"] == RESOLVER_VERSION
    assert set(report["source_files"]) == set(CANONICAL_JSONL_FILES)
    for field in [
        "resolver_inputs_by_file",
        "resolver_rules",
        "resolver_requirements_by_domain",
        "unresolved_references_by_file",
        "manual_review_fields_by_file",
        "staging_only_reference_domains",
        "blocked_relationship_writes",
        "limitations",
    ]:
        assert field in report


def test_contract_cli_is_offline_and_prints_json(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in resolver contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(FIXTURE_ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["resolver_version"] == RESOLVER_VERSION


def test_default_contract_reads_only_canonical_jsonl_not_batches_or_archive(monkeypatch) -> None:
    original_read_text = Path.read_text
    forbidden_parts = (("data", "batches"), ("archive", "data"))

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        for first, second in forbidden_parts:
            if first in parts and second in parts:
                raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert set(report["source_files"]) == set(CANONICAL_JSONL_FILES)
    assert after == before


def test_source_id_resolves_to_document_not_passage_or_link_table() -> None:
    report = build_contract_report(source_root=ROOT)
    rules = _rules_by_field(report, "data/evidence_cards.jsonl")
    source_rule = rules[("source_id", "source_document")]
    passage_rule = rules[("source_id", "source_passage")]

    assert source_rule["resolution_target"] != "passage_id"
    assert source_rule["blocked_action"] == "passage_id_write_or_evd_src_links_write"
    assert passage_rule["blocked_action"] == "automatic_passage_link_write"
    assert any(item["blocked_action"] == "passage_id_write_or_evd_src_links_write" for item in report["blocked_relationship_writes"])


def test_linked_ids_remain_resolver_input_and_block_relationship_writes() -> None:
    report = build_contract_report(source_root=ROOT)
    blocked = {(item["source_file"], item["field"]): item for item in report["blocked_relationship_writes"]}

    assert blocked[("data/search_logs.jsonl", "linked_source_ids")]["resolver_domain"] == "source_document"
    assert blocked[("data/search_logs.jsonl", "linked_evidence_ids")]["resolver_domain"] == "evidence_card"
    assert blocked[("data/evidence_clusters.jsonl", "linked_evidence_ids")]["blocked_action"] == (
        "direct_fk_write_without_resolver"
    )


def test_person_item_and_subitem_are_inputs_not_direct_relationships(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "evidence_cards.jsonl").write_text(
        '{"evidence_id":"EVD-TEST-001","person":"刘秀","item":"第五项","subitem":"B"}\n',
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)
    inputs = {item["field"]: item for item in report["resolver_inputs_by_file"]["data/evidence_cards.jsonl"]}
    rules = _rules_by_field(report, "data/evidence_cards.jsonl")

    assert inputs["person"]["resolver_domain"] == "person"
    assert rules[("person", "person")]["blocked_action"] == "direct_person_id_write"
    assert inputs["item"]["resolver_domain"] == "subitem"
    assert inputs["subitem"]["resolver_domain"] == "subitem"
    assert rules[("item", "subitem")]["blocked_action"] == "evidence_relationship_write"


def test_thematic_anchor_references_are_staging_only_and_schema_blocked(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "thematic_anchors.jsonl").write_text(
        '{"anchor_id":"ANCH-TEST-001","persons":["刘秀"],"linked_evidence_ids":["EVD-TEST-001"]}\n',
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)
    assert report["staging_only_reference_domains"] == [
        {
            "source_file": "data/thematic_anchors.jsonl",
            "resolver_domain": "anchor",
            "staging_only": True,
            "blocked_reason": "current PostgreSQL schema has anchors but no formal anchor_links target table",
            "blocked_action": "anchors_or_anchor_links_write",
        }
    ]
    assert any(item["field"] == "anchor_id" for item in report["blocked_relationship_writes"])


def test_manual_review_fields_remain_manual_review_inputs(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "evidence_cards.jsonl").write_text(
        '{"evidence_id":"EVD-TEST-001","cluster_role":"primary","evidence_role":"support"}\n',
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)
    manual_fields = {
        item["field"]: item for item in report["manual_review_fields_by_file"]["data/evidence_cards.jsonl"]
    }
    rules = _rules_by_field(report, "data/evidence_cards.jsonl")

    assert set(manual_fields) == {"cluster_role", "evidence_role"}
    assert rules[("cluster_role", "query_profile")]["manual_review_required"] is True
    assert rules[("evidence_role", "query_profile")]["allowed_action"] == "manual_review_only"


def test_report_contains_no_blocked_terms() -> None:
    text = report_as_json(build_contract_report(source_root=ROOT)).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_resolver_contract_tool_uses_no_database_shell_or_driver() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_staging_resolver_contract.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "psycopg" not in source


def _rules_by_field(report: dict[str, object], source_file: str) -> dict[tuple[str, str], dict[str, object]]:
    rules = {}
    for item in report["resolver_rules"]:
        if item["source_file"] == source_file:
            rules[(item["field"], item["resolver_domain"])] = item
    return rules


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
