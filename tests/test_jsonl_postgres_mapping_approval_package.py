from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.canonical_manifest_gate import EXPECTED_JSONL_FILES  # noqa: E402
from scripts.platform.jsonl_postgres_mapping_approval_package import (  # noqa: E402
    G1_MANIFEST_SHA256,
    PACKAGE_VERSION,
    build_package_report,
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


def test_mapping_approval_package_reaches_g2_and_covers_g1_manifest() -> None:
    report = build_package_report(source_root=ROOT)

    assert report["mode"] == "mapping-approval-package"
    assert report["package_version"] == PACKAGE_VERSION
    assert report["gate_status"] == "G2_REQUIRED"
    assert report["approval_required_from_user"] is True
    assert report["g1_manifest_approved"] is True
    assert report["g1_manifest_sha256"] == G1_MANIFEST_SHA256
    assert report["manifest_matches_g1"] is True
    assert set(report["covered_files"]) == set(EXPECTED_JSONL_FILES)
    assert report["covered_file_count"] == 11
    assert report["missing_mapping_files"] == []


def test_package_lists_schema_differences_type_loss_and_relationship_splits() -> None:
    report = build_package_report(source_root=ROOT)

    assert report["relaxed_vs_formal_schema_differences"]
    assert report["type_loss_risks"]
    assert report["relationship_splits"]
    assert any(item["target"] == "evd_src_links" for item in report["relationship_splits"])
    assert any(item["target"] == "anchor_links" for item in report["relationship_splits"])
    assert "relationship/type-loss approval required" in report["risk_summary"]


def test_package_surfaces_manual_review_unknown_fields_without_approving_them() -> None:
    report = build_package_report(source_root=ROOT)

    assert report["mapping_unknown_fields_by_file"]["data/evidence_cards.jsonl"] == ["cluster_role", "evidence_role"]
    assert report["remaining_unknown_fields_by_file"]["data/evidence_cards.jsonl"] == [
        "cluster_role",
        "evidence_role",
    ]
    assert "remaining manual-review unknown field" in report["risk_summary"]


def test_package_keeps_events_trigger_terms_and_anchor_links_staging_only() -> None:
    report = build_package_report(source_root=ROOT)

    assert "data/events.jsonl" in report["staging_only_files"]
    assert "data/trigger_terms.jsonl" in report["staging_only_files"]
    assert "data/thematic_anchors.jsonl" in report["staging_only_files"]
    assert report["jsonb_retained_fields_by_file"]["data/trigger_terms.jsonl"]["range_filter_fields"] == [
        "item",
        "subitem",
    ]


def test_package_cli_is_offline_and_emits_json_and_markdown(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in mapping approval package tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--package-report", "--source-root", str(ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate_status"] == "G2_REQUIRED"

    assert main(["--markdown-report", "--source-root", str(ROOT)]) == 0
    markdown = capsys.readouterr().out
    assert "G2_REQUIRED" in markdown
    assert "approval_required_from_user: true" in markdown


def test_package_does_not_read_excluded_paths_or_database_credentials(monkeypatch) -> None:
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

    report = build_package_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert report["manifest_matches_g1"] is True
    assert after == before


def test_package_tool_uses_no_database_shell_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_postgres_mapping_approval_package.py").read_text(
        encoding="utf-8"
    )

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source


def test_markdown_report_contains_g2_boundary() -> None:
    markdown = report_as_markdown(build_package_report(source_root=ROOT))

    assert "G2_REQUIRED" in markdown
    assert "G1 manifest is approved; G2 mapping is not approved by this package." in markdown
    assert "The package does not connect PostgreSQL" in markdown


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
