from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.canonical_manifest_gate import (  # noqa: E402
    EXPECTED_JSONL_FILES,
    MANIFEST_VERSION,
    build_candidate_report,
    main,
    normalize_reference_values,
    report_as_markdown,
)


FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
    ROOT / ".env",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def seed_expected_files(root: Path) -> None:
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for relative in EXPECTED_JSONL_FILES:
        (root / relative).write_text("", encoding="utf-8")


def test_real_manifest_candidate_covers_all_top_level_data_jsonl() -> None:
    report = build_candidate_report(source_root=ROOT)

    assert report["mode"] == "manifest-candidate-report"
    assert report["manifest_version"] == MANIFEST_VERSION
    assert report["gate_status"] == "G1_REQUIRED"
    assert report["approval_required_from_user"] is True
    assert report["data_survey"]["covered_files"] == list(EXPECTED_JSONL_FILES)
    assert report["blockers"]["missing_files"] == []
    assert report["blockers"]["unexpected_files"] == []
    assert report["repository_survey"]["reads_database_dsn"] is False
    assert report["repository_survey"]["connects_database"] is False


def test_report_reads_only_top_level_data_jsonl_not_excluded_paths(monkeypatch) -> None:
    original_read_text = Path.read_text
    forbidden_parts = (
        ("data", "batches"),
        ("archive", "data"),
        ("exports",),
        (".env",),
    )

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        for forbidden in forbidden_parts:
            if all(part in parts for part in forbidden):
                raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_candidate_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert report["data_survey"]["covered_file_scope"] == "top-level data/*.jsonl only"
    assert after == before


def test_fail_closed_on_missing_unexpected_duplicate_schema_and_orphan(tmp_path: Path) -> None:
    seed_expected_files(tmp_path)
    write_jsonl(tmp_path / "data" / "sources.jsonl", [{"source_id": "SRC-OK-001"}])
    write_jsonl(
        tmp_path / "data" / "evidence_cards.jsonl",
        [
            {"evidence_id": "EVD-OK-001", "source_id": "SRC-MISSING-001"},
            {"evidence_id": "EVD-OK-001", "source_id": "SRC-OK-001"},
            {"source_id": "SRC-OK-001"},
        ],
    )
    (tmp_path / "data" / "events.jsonl").unlink()
    (tmp_path / "data" / "unexpected.jsonl").write_text("[]\n", encoding="utf-8")

    report = build_candidate_report(source_root=tmp_path)

    assert report["fail_closed"] is True
    assert report["blockers"]["missing_files"] == ["data/events.jsonl"]
    assert report["blockers"]["unexpected_files"] == ["data/unexpected.jsonl"]
    assert report["blockers"]["duplicate_ids_by_file"]["data/evidence_cards.jsonl"]["EVD-OK-001"] == [1, 2]
    assert report["blockers"]["schema_mismatches_by_file"]["data/evidence_cards.jsonl"][
        "missing_primary_key_lines"
    ] == [3]
    assert report["blockers"]["orphan_references"][0]["value"] == "SRC-MISSING-001"


def test_mapping_coverage_flags_events_and_trigger_terms_for_milestone_1b() -> None:
    report = build_candidate_report(source_root=ROOT)
    coverage = report["schema_survey"]["mapping_coverage_by_file"]

    assert coverage["data/evidence_cards.jsonl"]["covered_by_jsonl_target_mapping"] is True
    assert coverage["data/events.jsonl"]["covered_by_jsonl_target_mapping"] is False
    assert coverage["data/trigger_terms.jsonl"]["note"] == "requires_milestone_1b_mapping_extension"


def test_reference_values_split_legacy_semicolon_and_comma_strings() -> None:
    assert normalize_reference_values("EVD-001; EVD-002，EVD-003, EVD-004") == [
        "EVD-001",
        "EVD-002",
        "EVD-003",
        "EVD-004",
    ]


def test_cli_prints_json_and_markdown_without_network(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in canonical manifest gate tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--candidate-report", "--source-root", str(ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest_version"] == MANIFEST_VERSION

    assert main(["--markdown-report", "--source-root", str(ROOT)]) == 0
    markdown = capsys.readouterr().out
    assert "G1_REQUIRED" in markdown
    assert "approval_required_from_user: true" in markdown


def test_markdown_report_exposes_g1_block_and_boundary() -> None:
    markdown = report_as_markdown(build_candidate_report(source_root=ROOT))

    assert "G1_REQUIRED" in markdown
    assert "does not approve canonical production data manifest" in markdown
    assert "does not read production DSN" in markdown


def test_manifest_gate_tool_uses_no_database_shell_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "canonical_manifest_gate.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "psycopg" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
