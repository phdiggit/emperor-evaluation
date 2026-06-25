from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.canonical_manifest_gate import EXPECTED_JSONL_FILES  # noqa: E402
from scripts.platform.jsonl_postgres_mapping_approval_package import G1_MANIFEST_SHA256  # noqa: E402
from scripts.platform.jsonl_staging_diff_verification import (  # noqa: E402
    VERIFICATION_VERSION,
    build_verification_report,
    main,
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


def test_staging_diff_verification_reaches_1c_without_new_gate() -> None:
    report = build_verification_report(source_root=ROOT)

    assert report["mode"] == "staging-diff-verification"
    assert report["verification_version"] == VERIFICATION_VERSION
    assert report["gate_status"] == "NO_NEW_GATE"
    assert report["approval_required_from_user"] is False
    assert report["g1_manifest_approved"] is True
    assert report["g2_mapping_approved"] is True
    assert report["next_user_gate"] == "G3_REQUIRED_BEFORE_PRODUCTION_BUSINESS_WRITE"
    assert report["production_success_inferred"] is False
    assert report["g1_manifest_sha256"] == G1_MANIFEST_SHA256
    assert report["manifest_matches_g1"] is True


def test_staging_diff_verification_covers_manifest_rows_ids_hashes_and_orphans() -> None:
    report = build_verification_report(source_root=ROOT)

    assert set(report["covered_files"]) == set(EXPECTED_JSONL_FILES)
    assert report["covered_file_count"] == 11
    assert report["rows_total"] == 251
    assert report["staging_report_summary"]["rows_mapped"] == 251
    assert report["row_count_diffs_by_file"] == {}
    assert report["id_count_diffs_by_file"] == {}
    assert report["orphan_reference_report"]["total_orphan_references"] == 0
    assert set(report["file_hashes_by_file"]) == set(EXPECTED_JSONL_FILES)
    assert all(item["sha256"] for item in report["file_hashes_by_file"].values())


def test_staging_diff_verification_surfaces_reference_and_lossy_conversion_risks() -> None:
    report = build_verification_report(source_root=ROOT)

    assert report["staging_report_summary"]["rows_with_reference_risk"] == 109
    assert report["staging_report_summary"]["rows_with_unknown_fields"] == 39
    assert report["staging_report_summary"]["rows_with_validation_errors"] == 0
    assert report["reference_diff_report"]["unresolved_references_by_file"]
    assert report["reference_diff_report"]["blocked_relationship_writes"]
    assert report["lossy_conversion_report"]["type_loss_risks"]
    assert report["lossy_conversion_report"]["relationship_splits"]
    assert report["lossy_conversion_report"]["remaining_unknown_fields_by_file"]["data/evidence_cards.jsonl"] == [
        "cluster_role",
        "evidence_role",
    ]
    assert "lossy conversion risks documented" in report["diff_summary"]
    assert "G3 still required before production business write" in report["diff_summary"]


def test_staging_diff_verification_cli_is_offline_and_emits_json_and_markdown(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in staging diff verification tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--verification-report", "--source-root", str(ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate_status"] == "NO_NEW_GATE"

    assert main(["--markdown-report", "--source-root", str(ROOT)]) == 0
    markdown = capsys.readouterr().out
    assert "NO_NEW_GATE" in markdown
    assert "production_success_inferred: false" in markdown


def test_staging_diff_verification_does_not_read_excluded_paths_or_database_credentials(monkeypatch) -> None:
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

    report = build_verification_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert report["manifest_matches_g1"] is True
    assert after == before


def test_staging_diff_verification_tool_has_no_apply_or_database_client_path() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_staging_diff_verification.py").read_text(encoding="utf-8")

    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "psycopg" not in source
    assert "--apply" not in source
    assert "read_dotenv" not in source


def test_markdown_report_contains_1c_boundary() -> None:
    markdown = report_as_markdown(build_verification_report(source_root=ROOT))

    assert "NO_NEW_GATE" in markdown
    assert "G3_REQUIRED_BEFORE_PRODUCTION_BUSINESS_WRITE" in markdown
    assert "does not read production credentials" in markdown


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
