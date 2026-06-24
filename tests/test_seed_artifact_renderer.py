from __future__ import annotations

import json
import socket
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import seed_artifact_renderer as renderer  # noqa: E402
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
    "renderer_version",
    "seed_plan_version",
    "artifact_kind",
    "default_output",
    "supported_modes",
    "source_files",
    "seed_candidate_tables",
    "blocked_seed_tables",
    "write_temp_policy",
    "manifest_policy",
    "non_goals",
    "strict_boundaries",
    "future_work",
    "limitations",
}
REQUIRED_ARTIFACT_KEYS = {
    "artifact_kind",
    "artifact_version",
    "generated_in_this_pr",
    "source_of_truth",
    "source_files",
    "seed_candidate_tables",
    "blocked_seed_tables",
    "table_payloads",
    "row_count_summary",
    "checksums",
    "strict_boundaries",
    "limitations",
    "artifact_written_to_repo",
    "artifact_applied_to_db",
}
REQUIRED_MANIFEST_KEYS = {
    "manifest_version",
    "artifact_kind",
    "artifact_sha256",
    "source_file_checksums",
    "source_row_counts",
    "table_row_counts",
    "tool_version",
    "seed_plan_version",
    "formal_schema_draft_version",
    "ddl_rehearsal_version",
    "live_rehearsal_version",
    "generated_at",
    "secret_free",
    "reproducible",
    "source_of_truth",
    "artifact_applied_to_db",
    "artifact_written_to_repo",
    "limitations",
}
EXPECTED_TABLES = set(PHASE_1_BASE_TABLES) | {"schema_rehearsal_meta"}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    opened: list[Path] = []
    _guard_forbidden_reads(monkeypatch, opened)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = renderer.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert opened == []
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["artifact_kind"] == "prototype_seed_artifact"
    assert report["default_output"] == "stdout"
    assert {"render-artifact", "render-manifest", "write-temp"} <= set(report["supported_modes"])
    assert any("canonical JSONL" in item["path"] or item["path"].startswith("data/") for item in report["source_files"])


def test_contract_report_tables_match_phase_boundaries() -> None:
    report = renderer.build_contract_report()
    candidate_tables = set(report["seed_candidate_tables"])
    blocked_tables = set(report["blocked_seed_tables"])

    assert candidate_tables == EXPECTED_TABLES
    assert set(PHASE_2_RELATIONSHIP_TABLES) <= blocked_tables
    assert set(PHASE_3_DOWNSTREAM_TABLES) <= blocked_tables
    assert not candidate_tables & blocked_tables
    assert "canonical JSONL files only" in report["manifest_policy"]["source_file_checksums"]


def test_render_artifact_contains_only_phase_1_payloads_and_stable_hash(tmp_path) -> None:
    _write_fixture_sources(tmp_path)

    first = renderer.build_seed_artifact(tmp_path)
    second = renderer.build_seed_artifact(tmp_path)

    assert set(first) == REQUIRED_ARTIFACT_KEYS
    assert first["artifact_kind"] == "prototype_seed_artifact"
    assert first["generated_in_this_pr"] is True
    assert first["artifact_written_to_repo"] is False
    assert first["artifact_applied_to_db"] is False
    assert set(first["table_payloads"]) == EXPECTED_TABLES
    assert not set(first["table_payloads"]) & set(PHASE_2_RELATIONSHIP_TABLES)
    assert not set(first["table_payloads"]) & set(PHASE_3_DOWNSTREAM_TABLES)
    assert first["table_payloads"]["query_profiles"]["rows"][0]["line_no"] == 1
    assert first["table_payloads"]["query_profiles"]["rows"][1]["line_no"] == 2
    assert renderer.sha256_text(renderer.canonical_json(first)) == renderer.sha256_text(renderer.canonical_json(second))


def test_render_artifact_tolerates_missing_optional_source_files(tmp_path) -> None:
    _write_jsonl(tmp_path / "data" / "query_profiles.jsonl", [{"id": "query-a"}])

    artifact = renderer.build_seed_artifact(tmp_path)

    assert artifact["source_files"]["data/search_tasks.jsonl"]["present"] is False
    assert artifact["source_files"]["data/search_tasks.jsonl"]["row_count"] is None
    assert artifact["table_payloads"]["search_tasks"]["rows"] == []
    assert artifact["table_payloads"]["schema_rehearsal_meta"]["row_count"] == 1


def test_render_manifest_contains_checksums_and_flags(tmp_path) -> None:
    _write_fixture_sources(tmp_path)
    artifact = renderer.build_seed_artifact(tmp_path)

    manifest = renderer.build_seed_manifest(artifact, tmp_path)

    assert set(manifest) == REQUIRED_MANIFEST_KEYS
    assert manifest["artifact_sha256"] == renderer.sha256_text(renderer.canonical_json(artifact))
    assert manifest["source_file_checksums"]["data/query_profiles.jsonl"]
    assert manifest["source_file_checksums"]["data/search_tasks.jsonl"]
    assert manifest["source_file_checksums"]["data/source_passages.jsonl"] is None
    assert manifest["source_row_counts"]["data/query_profiles.jsonl"] == 2
    assert manifest["table_row_counts"] == artifact["row_count_summary"]
    assert manifest["artifact_applied_to_db"] is False
    assert manifest["artifact_written_to_repo"] is False
    assert manifest["secret_free"] is True
    assert manifest["reproducible"] is True


def test_write_temp_rejects_repo_paths_without_writing(tmp_path) -> None:
    unsafe_paths = [
        ROOT,
        ROOT / "tmp-seed-artifact",
        ROOT / "data" / "seed-artifact",
        ROOT / "exports" / "seed-artifact",
        ROOT / "db" / "seed-artifact",
        ROOT / "docs" / "seed-artifact",
    ]

    for unsafe_path in unsafe_paths:
        before = sorted(path for path in tmp_path.rglob("*"))
        try:
            renderer.write_temp_artifacts(unsafe_path, tmp_path)
        except ValueError as exc:
            assert "outside repository root" in str(exc)
        else:
            raise AssertionError(f"unsafe output path unexpectedly accepted: {unsafe_path}")
        assert sorted(path for path in tmp_path.rglob("*")) == before


def test_write_temp_writes_exactly_two_files_under_safe_tmp(monkeypatch, tmp_path) -> None:
    _guard_network(monkeypatch)
    _write_fixture_sources(tmp_path / "source")
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    with tempfile.TemporaryDirectory(dir=ROOT.parent) as temp_dir:
        output_dir = Path(temp_dir) / "out"
        report = renderer.write_temp_artifacts(output_dir, tmp_path / "source")

        after = {path: _mtime(path) for path in PROTECTED_PATHS}
        assert after == before
        assert report["mode"] == "write-temp"
        assert report["repo_write_performed"] is False
        assert report["db_write_performed"] is False
        assert report["passed"] is True
        assert report["failed"] == []
        files = sorted(path.name for path in output_dir.iterdir())
        assert files == ["seed_artifact.prototype.json", "seed_manifest.prototype.json"]
        artifact_path = Path(report["artifact_path"])
        manifest_path = Path(report["manifest_path"])
        assert artifact_path.parent == output_dir.resolve()
        assert manifest_path.parent == output_dir.resolve()
        assert report["artifact_sha256"]
        assert report["manifest_sha256"]


def test_reports_contain_no_blocked_terms(tmp_path) -> None:
    _write_fixture_sources(tmp_path)
    artifact = renderer.build_seed_artifact(tmp_path)
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as temp_dir:
        reports = [
            renderer.build_contract_report(),
            artifact,
            renderer.build_seed_manifest(artifact, tmp_path),
            renderer.write_temp_artifacts(Path(temp_dir) / "out", tmp_path),
        ]

    for report in reports:
        text = renderer.report_as_json(report).lower()
        for term in BLOCKED_REPORT_TERMS:
            assert term not in text


def test_cli_modes_print_json(capsys, tmp_path) -> None:
    assert renderer.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert renderer.main(["--render-artifact"]) == 0
    artifact = json.loads(capsys.readouterr().out)
    assert artifact["artifact_kind"] == "prototype_seed_artifact"

    assert renderer.main(["--render-manifest"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["manifest_version"] == "prototype-seed-manifest-v1"

    with tempfile.TemporaryDirectory(dir=ROOT.parent) as temp_dir:
        assert renderer.main(["--write-temp", "--output-dir", str(Path(temp_dir) / "cli-out")]) == 0
        temp_report = json.loads(capsys.readouterr().out)
    assert temp_report["mode"] == "write-temp"


def test_source_is_offline_renderer_only() -> None:
    source = (ROOT / "scripts" / "platform" / "seed_artifact_renderer.py").read_text(encoding="utf-8")

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
        raise AssertionError("network access is forbidden in seed artifact renderer")

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
            raise AssertionError(f"seed artifact renderer must not write: {self}")
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
        raise AssertionError(f"seed artifact renderer must not read: {path}")
    if "exports" in parts:
        raise AssertionError(f"seed artifact renderer must not read: {path}")
    if "archive" in parts and "data" in parts:
        raise AssertionError(f"seed artifact renderer must not read: {path}")
    if "data" in parts and ("batches" in parts or any(part.endswith("_batches") for part in parts)):
        raise AssertionError(f"seed artifact renderer must not read: {path}")


def _write_fixture_sources(root: Path) -> None:
    _write_jsonl(
        root / "data" / "query_profiles.jsonl",
        [{"id": "query-b"}, {"id": "query-a"}],
    )
    _write_jsonl(root / "data" / "search_tasks.jsonl", [{"search_task_id": "task-a"}])
    _write_jsonl(root / "data" / "source_documents.jsonl", [{"source_id": "src-a"}])
    _write_jsonl(root / "data" / "evidence_cards.jsonl", [{"evidence_id": "evd-a"}])
    _write_jsonl(root / "data" / "evidence_clusters.jsonl", [{"cluster_id": "cluster-a"}])
    _write_jsonl(root / "data" / "thematic_anchors.jsonl", [{"anchor_code": "anchor-a"}])


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
