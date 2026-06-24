from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.anchors_resolver_contract import (
    ANCHOR_SOURCE_FILES,
    REFERENCE_SOURCE_FILES,
    build_contract_report,
    main,
    report_as_json,
)


BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_report_is_offline_and_has_required_shape(monkeypatch, tmp_path: Path) -> None:
    fixture_root = write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors resolver contract tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=fixture_root)

    assert report["mode"] == "contract-report"
    assert report["anchor_source_files"] == list(ANCHOR_SOURCE_FILES)
    assert report["reference_source_files"] == list(REFERENCE_SOURCE_FILES)
    assert report["resolver_status_values"] == [
        "unresolved_candidate",
        "manual_review_required",
        "blocked_pending_schema",
    ]
    assert len(report["anchor_candidates_by_file"]["data/thematic_anchors.jsonl"]) == 1
    assert report["anchor_link_candidate_plan"]["candidate_rows"] == 7


def test_anchor_candidates_keep_display_label_separate_from_identity(tmp_path: Path) -> None:
    report = build_contract_report(source_root=write_fixture_root(tmp_path))

    candidate = report["anchor_candidates_by_file"]["data/thematic_anchor_objects.jsonl"][0]
    assert candidate["anchor_code_candidate"] is None
    assert candidate["diagnostic_key"] == "data/thematic_anchor_objects.jsonl:1"
    assert candidate["display_label"] == "display-only object"
    assert candidate["display_label_is_stable_id"] is False
    assert candidate["resolver_status"] == "manual_review_required"


def test_reference_inputs_cover_anchor_fields_and_remain_unresolved(tmp_path: Path) -> None:
    report = build_contract_report(source_root=write_fixture_root(tmp_path))

    by_file = report["anchor_reference_inputs_by_file"]
    query_fields = [item["field"] for item in by_file["data/query_profiles.jsonl"]]
    card_fields = [item["field"] for item in by_file["data/evidence_cards.jsonl"]]
    cluster_fields = [item["field"] for item in by_file["data/evidence_clusters.jsonl"]]

    assert query_fields == ["object_anchors", "object_anchors", "thematic_anchor_targets"]
    assert card_fields == ["object_anchor", "thematic_anchor_targets"]
    assert cluster_fields == ["object_anchors", "thematic_anchor_targets"]
    assert {item["relationship_proven"] for rows in by_file.values() for item in rows} == {False}


def test_anchor_links_and_indirect_relationships_are_blocked(tmp_path: Path) -> None:
    report = build_contract_report(source_root=write_fixture_root(tmp_path))
    text = report_as_json(report)

    blocked_actions = {item["blocked_action"] for item in report["blocked_relationship_writes"]}
    assert "anchor_links_write" in blocked_actions
    assert "evidence_relationship_write" in blocked_actions
    assert "cluster_relationship_write" in blocked_actions
    assert '"target_table": "anchor_links"' in text
    assert '"relationship_proven": false' in text


def test_default_contract_paths_do_not_read_batches_archive_env_or_touch_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors resolver contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert set(report["source_files"]).issubset(set(ANCHOR_SOURCE_FILES) | set(REFERENCE_SOURCE_FILES))


def test_report_contains_no_blocked_report_terms(tmp_path: Path) -> None:
    text = report_as_json(build_contract_report(source_root=write_fixture_root(tmp_path))).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys, tmp_path: Path) -> None:
    fixture_root = write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors resolver contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(fixture_root)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["anchor_link_candidate_plan"]["candidate_rows"] == 7


def test_resolver_source_has_no_dsn_driver_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "anchors_resolver_contract.py").read_text(encoding="utf-8")

    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "import psycopg" not in source
    assert "psycopg" not in source
    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    write_jsonl(data_dir / "thematic_anchors.jsonl", [{"anchor_id": "ANCH-THEME-1", "label": "theme label"}])
    write_jsonl(data_dir / "thematic_anchor_objects.jsonl", [{"object_name": "display-only object"}])
    write_jsonl(data_dir / "thematic_anchor_events.jsonl", [{"code": "ANCH-EVENT-1", "label": "event label"}])
    write_jsonl(data_dir / "thematic_anchor_mechanisms.jsonl", [{"stable_key": "ANCH-MECH-1", "name": "mechanism label"}])
    write_jsonl(
        data_dir / "query_profiles.jsonl",
        [
            {
                "query_profile_id": "QRY-ANCH-1",
                "object_anchors": [
                    {"anchor_id": "ANCH-OBJ-1", "label": "object label"},
                    {"label": "display only reference"},
                ],
                "thematic_anchor_targets": ["ANCH-THEME-1"],
            }
        ],
    )
    write_jsonl(
        data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-ANCH-1",
                "object_anchor": "ANCH-OBJ-1",
                "thematic_anchor_targets": [{"code": "ANCH-EVENT-1"}],
                "linked_cluster_ids": ["CLUSTER-ANCH-1"],
            }
        ],
    )
    write_jsonl(
        data_dir / "evidence_clusters.jsonl",
        [
            {
                "cluster_id": "CLUSTER-ANCH-1",
                "object_anchors": ["ANCH-MECH-1"],
                "thematic_anchor_targets": [{"name": "display only cluster reference"}],
                "linked_evidence_ids": ["EVD-ANCH-1"],
            }
        ],
    )
    return tmp_path


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
