from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import seed_artifact_plan  # noqa: E402
from scripts.platform.formal_schema_draft import (  # noqa: E402
    BLOCKED_REPORT_TERMS,
    PHASE_1_BASE_TABLES,
    PHASE_2_RELATIONSHIP_TABLES,
    PHASE_3_DOWNSTREAM_TABLES,
)


PROTECTED_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]
REQUIRED_CONTRACT_KEYS = {
    "mode",
    "seed_plan_version",
    "status",
    "source_of_truth",
    "formal_schema_draft_version",
    "ddl_rehearsal_version",
    "live_rehearsal_version",
    "seed_candidate_tables",
    "blocked_seed_tables",
    "source_jsonl_files",
    "checksum_manifest_contract",
    "seed_artifact_contract",
    "dry_run_plan",
    "validation_gates",
    "non_goals",
    "strict_boundaries",
    "future_work",
    "limitations",
}
REQUIRED_DRY_RUN_KEYS = {
    "mode",
    "source_of_truth",
    "source_files_checked",
    "source_files_found",
    "source_files_missing",
    "row_counts_by_source_file",
    "source_sha256_by_source_file",
    "planned_rows_by_table",
    "seed_candidate_tables",
    "blocked_seed_tables",
    "generated_artifact",
    "writes_performed",
    "strict_boundaries",
    "limitations",
}
EXPECTED_PLAN_TABLES = {
    "imports",
    "import_rows",
    "query_profiles",
    "search_tasks",
    "src_hosts",
    "src_docs",
    "doc_revs",
    "passages",
    "evd_cards",
    "clusters",
    "anchors",
    "schema_rehearsal_meta",
}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    opened: list[Path] = []
    _guard_forbidden_reads(monkeypatch, opened)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = seed_artifact_plan.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert opened == []
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["status"] == "Proposed"
    assert report["seed_plan_version"] == "seed-artifact-plan-v1"
    assert "canonical JSONL remains source-of-truth" in report["source_of_truth"]


def test_dry_run_reads_only_canonical_jsonl_and_preserves_protected_paths(monkeypatch, tmp_path) -> None:
    _guard_network(monkeypatch)
    _write_jsonl(tmp_path / "data" / "query_profiles.jsonl", 2)
    _write_jsonl(tmp_path / "data" / "source_documents.jsonl", 3)
    _write_jsonl(tmp_path / "data" / "thematic_anchors.jsonl", 1)
    opened: list[Path] = []
    _guard_forbidden_reads(monkeypatch, opened)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = seed_artifact_plan.build_dry_run_report(tmp_path)

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert set(report) == REQUIRED_DRY_RUN_KEYS
    assert report["mode"] == "dry-run"
    assert report["generated_artifact"] is False
    assert report["writes_performed"] is False
    assert set(report["source_files_found"]) == {
        "data/query_profiles.jsonl",
        "data/source_documents.jsonl",
        "data/thematic_anchors.jsonl",
    }
    assert "data/search_tasks.jsonl" in report["source_files_missing"]
    assert report["row_counts_by_source_file"]["data/query_profiles.jsonl"] == 2
    assert report["row_counts_by_source_file"]["data/search_tasks.jsonl"] is None
    assert all(_is_allowed_source(path, tmp_path) for path in opened)


def test_manifest_skeleton_is_offline_and_does_not_write(monkeypatch) -> None:
    _guard_network(monkeypatch)
    opened: list[Path] = []
    _guard_forbidden_reads(monkeypatch, opened)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = seed_artifact_plan.build_manifest_skeleton()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert opened == []
    assert report["mode"] == "manifest-skeleton"
    assert report["generated_in_this_pr"] is False
    assert report["artifact_kind"] == "proposed_seed_manifest"
    assert report["secret_free_required"] is True
    assert report["reproducible_required"] is True
    assert "source_sha256" in report["planned_checksum_fields"]
    assert "artifact_sha256" in report["planned_checksum_fields"]


def test_seed_candidate_and_blocked_tables_match_phase_contract() -> None:
    report = seed_artifact_plan.build_contract_report()
    candidate_tables = set(report["seed_candidate_tables"])
    blocked_tables = {item["table_name"] for item in report["blocked_seed_tables"]}

    assert candidate_tables == set(PHASE_1_BASE_TABLES) | {"schema_rehearsal_meta"}
    assert not candidate_tables & set(PHASE_2_RELATIONSHIP_TABLES)
    assert not candidate_tables & set(PHASE_3_DOWNSTREAM_TABLES)
    assert set(PHASE_2_RELATIONSHIP_TABLES) <= blocked_tables
    assert set(PHASE_3_DOWNSTREAM_TABLES) <= blocked_tables


def test_dry_run_planned_rows_cover_all_seed_candidate_domains(tmp_path) -> None:
    _write_jsonl(tmp_path / "data" / "query_profiles.jsonl", 2)
    _write_jsonl(tmp_path / "data" / "search_tasks.jsonl", 1)
    _write_jsonl(tmp_path / "data" / "source_documents.jsonl", 3)
    _write_jsonl(tmp_path / "data" / "source_passages.jsonl", 4)
    _write_jsonl(tmp_path / "data" / "evidence_cards.jsonl", 5)
    _write_jsonl(tmp_path / "data" / "evidence_clusters.jsonl", 6)
    _write_jsonl(tmp_path / "data" / "thematic_anchors.jsonl", 7)
    _write_jsonl(tmp_path / "data" / "thematic_anchor_objects.jsonl", 8)

    report = seed_artifact_plan.build_dry_run_report(tmp_path)
    planned = report["planned_rows_by_table"]

    assert set(planned) == EXPECTED_PLAN_TABLES
    assert planned["query_profiles"]["planned_rows"] == 2
    assert planned["search_tasks"]["planned_rows"] == 1
    assert planned["src_hosts"]["planned_rows"] == 3
    assert planned["src_docs"]["planned_rows"] == 3
    assert planned["doc_revs"]["planned_rows"] == 3
    assert planned["passages"]["planned_rows"] == 4
    assert planned["evd_cards"]["planned_rows"] == 5
    assert planned["clusters"]["planned_rows"] == 6
    assert planned["anchors"]["planned_rows"] == 15
    assert planned["schema_rehearsal_meta"]["planned_rows"] == 1
    assert planned["schema_rehearsal_meta"]["future_only"] is True
    for item in planned.values():
        assert item["dry_estimate"] is True
        assert item["not_seed_rows"] is True
        assert item["not_inserted_rows"] is True
        assert item["not_production_counts"] is True


def test_reports_contain_no_blocked_terms(tmp_path) -> None:
    _write_jsonl(tmp_path / "data" / "query_profiles.jsonl", 1)
    reports = [
        seed_artifact_plan.build_contract_report(),
        seed_artifact_plan.build_dry_run_report(tmp_path),
        seed_artifact_plan.build_manifest_skeleton(),
    ]

    for report in reports:
        text = seed_artifact_plan.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_cli_modes_print_json_without_connecting(monkeypatch, capsys) -> None:
    _guard_network(monkeypatch)

    assert seed_artifact_plan.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert seed_artifact_plan.main(["--dry-run"]) == 0
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["mode"] == "dry-run"
    assert dry_run["generated_artifact"] is False

    assert seed_artifact_plan.main(["--manifest-skeleton"]) == 0
    skeleton = json.loads(capsys.readouterr().out)
    assert skeleton["mode"] == "manifest-skeleton"
    assert skeleton["generated_in_this_pr"] is False


def test_source_is_seed_planner_only() -> None:
    source = (ROOT / "scripts" / "platform" / "seed_artifact_plan.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source
    assert "os.environ" not in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    protected_paths = {path.as_posix() for path in PROTECTED_PATHS}

    assert any(path.endswith("docs/皇帝综合评价体系评分标准.md") for path in protected_paths)
    assert any(path.endswith("docs/分项规则") for path in protected_paths)
    assert any(path.endswith("docs/证据规则") for path in protected_paths)
    for mojibake in ["\u9428\u56e7\u7b23", "\u934a\u55d8\u300d", "\u7487\u4f7a\u5d41"]:
        assert mojibake not in source


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in seed artifact planner")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_forbidden_reads(monkeypatch, opened: list[Path]) -> None:
    original_open = Path.open
    original_read_text = Path.read_text

    def guarded_open(self: Path, *args: object, **kwargs: object):
        mode = args[0] if args else kwargs.get("mode", "r")
        path = self.resolve()
        if "r" in str(mode):
            _assert_not_forbidden(path)
            opened.append(path)
        if any(flag in str(mode) for flag in ("w", "a", "+", "x")):
            raise AssertionError(f"seed artifact planner must not write: {self}")
        return original_open(self, *args, **kwargs)

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        _assert_not_forbidden(path)
        opened.append(path)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)


def _assert_not_forbidden(path: Path) -> None:
    parts = path.parts
    if path.name == ".env":
        raise AssertionError(f"seed artifact planner must not read: {path}")
    if "exports" in parts:
        raise AssertionError(f"seed artifact planner must not read: {path}")
    if "archive" in parts and "data" in parts:
        raise AssertionError(f"seed artifact planner must not read: {path}")
    if "data" in parts and ("batches" in parts or any(part.endswith("_batches") for part in parts)):
        raise AssertionError(f"seed artifact planner must not read: {path}")


def _is_allowed_source(path: Path, source_root: Path) -> bool:
    try:
        relative = path.relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return False
    return relative in seed_artifact_plan.CANONICAL_JSONL_FILES


def _write_jsonl(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f'{{"id": {index}}}\n' for index in range(rows)), encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
