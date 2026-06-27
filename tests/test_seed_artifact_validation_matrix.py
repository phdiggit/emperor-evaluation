from __future__ import annotations

import copy
import json
import socket
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import seed_artifact_renderer as renderer  # noqa: E402
from scripts.platform import seed_artifact_validation_matrix as matrix  # noqa: E402
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
    "validator_version",
    "renderer_version",
    "seed_plan_version",
    "formal_schema_draft_version",
    "supported_modes",
    "validation_rules",
    "expected_seed_candidate_tables",
    "expected_blocked_tables",
    "non_goals",
    "strict_boundaries",
    "future_work",
    "limitations",
}
EXPECTED_RULES = {
    "artifact_kind_is_prototype",
    "artifact_not_written_to_repo",
    "artifact_not_applied_to_db",
    "source_of_truth_preserved",
    "seed_candidate_tables_match_phase_1",
    "table_payloads_match_seed_candidates",
    "phase_2_tables_excluded",
    "phase_3_tables_excluded",
    "blocked_seed_tables_include_phase_2_3",
    "table_gates_allow_payload_tables",
    "table_gates_defer_relationship_downstream_tables",
    "row_count_summary_matches_payloads",
    "source_checksums_match_artifact_sources",
    "manifest_artifact_hash_matches",
    "manifest_table_counts_match_artifact",
    "manifest_source_checksums_match_artifact",
    "manifest_flags_are_false_for_db_and_repo",
    "manifest_secret_free_and_reproducible",
    "schema_rehearsal_meta_metadata_only",
    "source_boundary_uses_canonical_jsonl_only",
    "no_blocked_report_terms",
}
EXPECTED_TABLES = set(PHASE_1_BASE_TABLES) | {"schema_rehearsal_meta"}


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    _guard_network(monkeypatch)
    opened: list[Path] = []
    _guard_forbidden_reads(monkeypatch, opened)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = matrix.build_contract_report()

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert opened == []
    assert set(report) == REQUIRED_CONTRACT_KEYS
    assert report["mode"] == "contract-report"
    assert report["validator_version"] == "seed-artifact-validation-matrix-v1"
    assert set(report["supported_modes"]) == {"contract-report", "validate-rendered", "validate-temp"}
    assert set(report["validation_rules"]) == EXPECTED_RULES


def test_contract_report_tables_and_terms_are_safe() -> None:
    report = matrix.build_contract_report()

    assert set(report["expected_seed_candidate_tables"]) == EXPECTED_TABLES
    assert set(PHASE_2_RELATIONSHIP_TABLES) <= set(report["expected_blocked_tables"])
    assert set(PHASE_3_DOWNSTREAM_TABLES) <= set(report["expected_blocked_tables"])
    assert _contains_no_blocked_terms(report)


def test_validate_rendered_succeeds_without_writing(monkeypatch, tmp_path) -> None:
    _guard_network(monkeypatch)
    _write_fixture_sources(tmp_path)
    opened: list[Path] = []
    _guard_forbidden_reads(monkeypatch, opened, allowed_source_root=tmp_path)
    before = {path: _mtime(path) for path in PROTECTED_PATHS}

    report = matrix.validate_rendered(tmp_path)

    after = {path: _mtime(path) for path in PROTECTED_PATHS}
    assert after == before
    assert report["mode"] == "validate-rendered"
    assert report["artifact_valid"] is True
    assert report["manifest_valid"] is True
    assert report["table_gate_valid"] is True
    assert report["source_boundary_valid"] is True
    assert report["passed"] is True
    assert report["failed"] == []
    assert all(rule["passed"] for rule in report["checked_rules"])
    assert report["artifact_summary"]["row_count_summary"] == report["manifest_summary"]["table_row_counts"]
    assert all(_is_allowed_source(path, tmp_path) for path in opened)
    assert not (tmp_path / renderer.ARTIFACT_FILENAME).exists()
    assert not (tmp_path / renderer.MANIFEST_FILENAME).exists()


def test_validate_rendered_accepts_missing_optional_sources(tmp_path) -> None:
    _write_jsonl(tmp_path / "data" / "query_profiles.jsonl", [{"id": "query-a"}])

    report = matrix.validate_rendered(tmp_path)

    assert report["passed"] is True
    assert report["artifact_summary"]["row_count_summary"]["query_profiles"] == 1
    assert report["artifact_summary"]["row_count_summary"]["search_tasks"] == 0


def test_validate_temp_succeeds_and_reads_only_prototype_json(monkeypatch, tmp_path) -> None:
    _write_fixture_sources(tmp_path / "source")
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as temp_dir:
        output_dir = Path(temp_dir) / "seed-out"
        renderer.write_temp_artifacts(output_dir, tmp_path / "source")
        reads: list[Path] = []
        _guard_temp_json_reads(monkeypatch, reads, output_dir)

        report = matrix.validate_temp(output_dir)

    assert report["mode"] == "validate-temp"
    assert report["passed"] is True
    assert report["artifact_valid"] is True
    assert report["manifest_valid"] is True
    assert sorted(path.name for path in reads) == [
        "seed_artifact.prototype.json",
        "seed_manifest.prototype.json",
    ]


def test_validate_temp_rejects_repo_paths_without_writing() -> None:
    unsafe_paths = [
        ROOT,
        ROOT / "tmp-seed-artifact",
        ROOT / "data" / "seed-artifact",
        ROOT / "exports" / "seed-artifact",
        ROOT / "db" / "seed-artifact",
        ROOT / "docs" / "seed-artifact",
    ]

    for unsafe_path in unsafe_paths:
        try:
            matrix.validate_temp(unsafe_path)
        except ValueError as exc:
            assert "outside repository root" in str(exc)
        else:
            raise AssertionError(f"unsafe output path unexpectedly accepted: {unsafe_path}")


def test_validate_temp_missing_files_fails_gracefully(tmp_path) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as temp_dir:
        report = matrix.validate_temp(Path(temp_dir))

    assert report["passed"] is False
    assert report["artifact_valid"] is False
    assert report["manifest_valid"] is False
    assert "prototype_json_files_exist" in report["failed"]


def test_failure_cases_are_reported(tmp_path) -> None:
    artifact, manifest = _valid_artifact_and_manifest(tmp_path)

    tampered = copy.deepcopy(artifact)
    tampered["table_payloads"]["search_hits"] = {
        "table_name": "search_hits",
        "row_count": 0,
        "rows": [],
        "source_files": [],
        "dry_estimate": True,
        "prototype_only": True,
    }
    assert "phase_2_tables_excluded" in matrix.validate_artifact_and_manifest(tampered, manifest)["failed"]

    tampered = copy.deepcopy(artifact)
    tampered["artifact_applied_to_db"] = True
    assert "artifact_not_applied_to_db" in matrix.validate_artifact_and_manifest(tampered, manifest)["failed"]

    tampered = copy.deepcopy(artifact)
    tampered["artifact_written_to_repo"] = True
    assert "artifact_not_written_to_repo" in matrix.validate_artifact_and_manifest(tampered, manifest)["failed"]

    tampered_manifest = copy.deepcopy(manifest)
    tampered_manifest["artifact_sha256"] = "bad-hash"
    assert "manifest_artifact_hash_matches" in matrix.validate_artifact_and_manifest(artifact, tampered_manifest)["failed"]

    tampered_manifest = copy.deepcopy(manifest)
    tampered_manifest["table_row_counts"]["query_profiles"] = 99
    assert "manifest_table_counts_match_artifact" in matrix.validate_artifact_and_manifest(artifact, tampered_manifest)["failed"]

    tampered = copy.deepcopy(artifact)
    del tampered["table_payloads"]["schema_rehearsal_meta"]
    assert "schema_rehearsal_meta_metadata_only" in matrix.validate_artifact_and_manifest(tampered, manifest)["failed"]


def test_cli_modes_print_json_and_return_expected_codes(capsys, tmp_path) -> None:
    assert matrix.main(["--contract-report"]) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["mode"] == "contract-report"

    assert matrix.main(["--validate-rendered"]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["mode"] == "validate-rendered"
    assert rendered["passed"] is True

    with tempfile.TemporaryDirectory(dir=ROOT.parent) as temp_dir:
        assert matrix.main(["--validate-temp", "--output-dir", str(Path(temp_dir))]) == 1
    missing = json.loads(capsys.readouterr().out)
    assert missing["mode"] == "validate-temp"
    assert missing["passed"] is False


def test_source_is_offline_validation_matrix_only() -> None:
    source = (Path(matrix.__file__)).read_text(encoding="utf-8")

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


def _valid_artifact_and_manifest(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    _write_fixture_sources(root)
    artifact = renderer.build_seed_artifact(root)
    manifest = renderer.build_seed_manifest(artifact, root)
    return artifact, manifest


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in seed artifact validation matrix")

    monkeypatch.setattr(socket, "socket", fail_socket)


def _guard_forbidden_reads(monkeypatch, opened: list[Path], allowed_source_root: Path | None = None) -> None:
    original_open = Path.open
    original_read_text = Path.read_text

    def guarded_open(self: Path, *args: object, **kwargs: object):
        mode = args[0] if args else kwargs.get("mode", "r")
        path = self.resolve()
        if "r" in str(mode):
            _assert_not_forbidden(path)
            opened.append(path)
        if any(flag in str(mode) for flag in ("w", "a", "+", "x")):
            raise AssertionError(f"seed artifact validation matrix must not write: {self}")
        return original_open(self, *args, **kwargs)

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        _assert_not_forbidden(path)
        opened.append(path)
        return original_read_text(self, *args, **kwargs)

    def assert_allowed(path: Path) -> None:
        _assert_not_forbidden(path)
        if allowed_source_root is not None and not _is_allowed_source(path, allowed_source_root):
            raise AssertionError(f"unexpected read path: {path}")

    def guarded_open_with_allowlist(self: Path, *args: object, **kwargs: object):
        mode = args[0] if args else kwargs.get("mode", "r")
        path = self.resolve()
        if "r" in str(mode):
            assert_allowed(path)
            opened.append(path)
        if any(flag in str(mode) for flag in ("w", "a", "+", "x")):
            raise AssertionError(f"seed artifact validation matrix must not write: {self}")
        return original_open(self, *args, **kwargs)

    def guarded_read_text_with_allowlist(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        assert_allowed(path)
        opened.append(path)
        return original_read_text(self, *args, **kwargs)

    if allowed_source_root is None:
        monkeypatch.setattr(Path, "open", guarded_open)
        monkeypatch.setattr(Path, "read_text", guarded_read_text)
    else:
        monkeypatch.setattr(Path, "open", guarded_open_with_allowlist)
        monkeypatch.setattr(Path, "read_text", guarded_read_text_with_allowlist)


def _guard_temp_json_reads(monkeypatch, reads: list[Path], output_dir: Path) -> None:
    original_read_text = Path.read_text
    expected = {
        (output_dir / renderer.ARTIFACT_FILENAME).resolve(),
        (output_dir / renderer.MANIFEST_FILENAME).resolve(),
    }

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        if path not in expected:
            raise AssertionError(f"unexpected temp read path: {path}")
        reads.append(path)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)


def _assert_not_forbidden(path: Path) -> None:
    parts = path.parts
    if path.name == ".env":
        raise AssertionError(f"seed artifact validation matrix must not read: {path}")
    if "exports" in parts:
        raise AssertionError(f"seed artifact validation matrix must not read: {path}")
    if "archive" in parts and "data" in parts:
        raise AssertionError(f"seed artifact validation matrix must not read: {path}")
    if "data" in parts and ("batches" in parts or any(part.endswith("_batches") for part in parts)):
        raise AssertionError(f"seed artifact validation matrix must not read: {path}")


def _is_allowed_source(path: Path, source_root: Path) -> bool:
    try:
        relative = path.relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return False
    return relative in renderer.CANONICAL_JSONL_FILES


def _contains_no_blocked_terms(report: dict[str, object]) -> bool:
    text = matrix.report_as_json(report).lower()
    return all(term not in text for term in BLOCKED_REPORT_TERMS)


def _write_fixture_sources(root: Path) -> None:
    _write_jsonl(
        root / "data" / "query_profiles.jsonl",
        [{"id": "query-b"}, {"id": "query-a"}],
    )
    _write_jsonl(root / "data" / "search_tasks.jsonl", [{"search_task_id": "task-a"}])
    _write_jsonl(root / "data" / "source_documents.jsonl", [{"source_id": "src-a"}])
    _write_jsonl(root / "data" / "source_passages.jsonl", [{"passage_id": "passage-a"}])
    _write_jsonl(root / "data" / "evidence_cards.jsonl", [{"evidence_id": "evd-a"}])
    _write_jsonl(root / "data" / "evidence_clusters.jsonl", [{"cluster_id": "cluster-a"}])
    _write_jsonl(root / "data" / "thematic_anchors.jsonl", [{"anchor_code": "anchor-a"}])
    _write_jsonl(root / "data" / "thematic_anchor_objects.jsonl", [{"anchor_object_id": "object-a"}])


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
