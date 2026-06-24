from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    formal_ddl_live_rehearsal,
    formal_ddl_rehearsal,
    formal_schema_draft,
    seed_artifact_plan,
)


RENDERER_VERSION = "seed-artifact-renderer-v1"
ARTIFACT_VERSION = "prototype-seed-artifact-v1"
MANIFEST_VERSION = "prototype-seed-manifest-v1"
ARTIFACT_KIND = "prototype_seed_artifact"
SOURCE_OF_TRUTH = "canonical JSONL remains source-of-truth; rendered artifacts are review prototypes only"
ARTIFACT_FILENAME = "seed_artifact.prototype.json"
MANIFEST_FILENAME = "seed_manifest.prototype.json"
SEED_CANDIDATE_TABLES = seed_artifact_plan.SEED_CANDIDATE_TABLES
BLOCKED_SEED_TABLES = seed_artifact_plan.BLOCKED_SEED_TABLES
CANONICAL_JSONL_FILES = seed_artifact_plan.CANONICAL_JSONL_FILES
TABLE_SOURCE_FILES = {
    "imports": CANONICAL_JSONL_FILES,
    "import_rows": CANONICAL_JSONL_FILES,
    "query_profiles": ("data/query_profiles.jsonl",),
    "search_tasks": ("data/search_tasks.jsonl",),
    "src_hosts": ("data/source_documents.jsonl",),
    "src_docs": ("data/source_documents.jsonl",),
    "doc_revs": ("data/source_documents.jsonl",),
    "passages": ("data/source_passages.jsonl",),
    "evd_cards": ("data/evidence_cards.jsonl",),
    "clusters": ("data/evidence_clusters.jsonl",),
    "anchors": (
        "data/thematic_anchors.jsonl",
        "data/thematic_anchor_objects.jsonl",
        "data/thematic_anchor_events.jsonl",
        "data/thematic_anchor_mechanisms.jsonl",
    ),
    "schema_rehearsal_meta": (),
}
STRICT_BOUNDARIES = (
    "offline_only",
    "stdout_by_default",
    "does_not_read_dotenv",
    "does_not_read_dsn",
    "does_not_connect_to_database",
    "does_not_execute_ddl",
    "does_not_execute_migration",
    "does_not_read_data_batches",
    "does_not_read_archive_data",
    "does_not_read_exports",
    "does_not_modify_canonical_jsonl",
    "does_not_modify_db_schema_sql",
    "does_not_modify_postgres_init_sql",
    "does_not_write_repo_artifact",
    "does_not_write_data",
    "does_not_write_exports",
    "does_not_write_db",
    "does_not_apply_seed",
    "phase_2_3_tables_excluded",
)
LIMITATIONS = (
    "prototype artifact only",
    "minimal row envelopes only",
    "canonical payload is not copied into artifact rows",
    "missing canonical JSONL files are reported as optional missing sources",
    "no production readiness claim",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "renderer_version": RENDERER_VERSION,
        "seed_plan_version": seed_artifact_plan.SEED_PLAN_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "default_output": "stdout",
        "supported_modes": ["contract-report", "render-artifact", "render-manifest", "write-temp"],
        "source_files": _source_file_contract(),
        "seed_candidate_tables": list(SEED_CANDIDATE_TABLES),
        "blocked_seed_tables": list(BLOCKED_SEED_TABLES),
        "write_temp_policy": {
            "requires_write_temp_flag": True,
            "requires_output_dir": True,
            "output_dir_must_be_outside_repo": True,
            "files_written": [ARTIFACT_FILENAME, MANIFEST_FILENAME],
            "repo_write_performed": False,
            "db_write_performed": False,
        },
        "manifest_policy": {
            "manifest_version": MANIFEST_VERSION,
            "artifact_sha256_from_canonical_artifact_json": True,
            "source_file_checksums": "canonical JSONL files only",
            "secret_free": True,
            "reproducible": True,
        },
        "non_goals": [
            "does not modify canonical JSONL",
            "does not modify db/schema.sql",
            "does not modify db/postgres/001_init.sql",
            "does not read .env or DSN values",
            "does not connect to PostgreSQL",
            "does not execute DDL or migration",
            "does not switch the JSONL write source",
            "does not write production target tables",
            "does not generate business conclusions",
        ],
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "future_work": [
            "validate rendered artifact against formal schema draft",
            "cross-check table gates before any future seed application",
            "keep production seed application in a separate approved PR",
        ],
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_seed_artifact(source_root: Path = ROOT) -> dict[str, Any]:
    source_records = _load_source_records(source_root)
    source_files = _source_file_status(source_records, source_root)
    table_payloads = {
        table_name: _table_payload(table_name, source_records)
        for table_name in SEED_CANDIDATE_TABLES
    }
    row_count_summary = {
        table_name: payload["row_count"]
        for table_name, payload in table_payloads.items()
    }
    artifact = {
        "artifact_kind": ARTIFACT_KIND,
        "artifact_version": ARTIFACT_VERSION,
        "generated_in_this_pr": True,
        "source_of_truth": SOURCE_OF_TRUTH,
        "source_files": source_files,
        "seed_candidate_tables": list(SEED_CANDIDATE_TABLES),
        "blocked_seed_tables": list(BLOCKED_SEED_TABLES),
        "table_payloads": table_payloads,
        "row_count_summary": row_count_summary,
        "checksums": {
            "source_file_sha256": {
                path: item["sha256"]
                for path, item in source_files.items()
            }
        },
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "limitations": list(LIMITATIONS),
        "artifact_written_to_repo": False,
        "artifact_applied_to_db": False,
    }
    assert_report_has_no_blocked_terms(artifact)
    return artifact


def build_seed_manifest(artifact: Mapping[str, Any], source_root: Path = ROOT) -> dict[str, Any]:
    source_files = _source_file_status(_load_source_records(source_root), source_root)
    artifact_sha256 = sha256_text(canonical_json(artifact))
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "artifact_sha256": artifact_sha256,
        "source_file_checksums": {
            path: item["sha256"]
            for path, item in source_files.items()
        },
        "source_row_counts": {
            path: item["row_count"]
            for path, item in source_files.items()
        },
        "table_row_counts": dict(artifact["row_count_summary"]),
        "tool_version": RENDERER_VERSION,
        "seed_plan_version": seed_artifact_plan.SEED_PLAN_VERSION,
        "formal_schema_draft_version": formal_schema_draft.DRAFT_VERSION,
        "ddl_rehearsal_version": formal_ddl_rehearsal.REHEARSAL_VERSION,
        "live_rehearsal_version": formal_ddl_live_rehearsal.LIVE_REHEARSAL_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "secret_free": True,
        "reproducible": True,
        "source_of_truth": SOURCE_OF_TRUTH,
        "artifact_applied_to_db": False,
        "artifact_written_to_repo": False,
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(manifest)
    return manifest


def write_temp_artifacts(output_dir: Path, source_root: Path = ROOT) -> dict[str, Any]:
    safe_output_dir = validate_output_dir(output_dir)
    artifact = build_seed_artifact(source_root)
    manifest = build_seed_manifest(artifact, source_root)
    artifact_text = report_as_json(artifact)
    manifest_text = report_as_json(manifest)

    safe_output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = safe_output_dir / ARTIFACT_FILENAME
    manifest_path = safe_output_dir / MANIFEST_FILENAME
    artifact_path.write_text(artifact_text + "\n", encoding="utf-8", newline="\n")
    manifest_path.write_text(manifest_text + "\n", encoding="utf-8", newline="\n")

    report = {
        "mode": "write-temp",
        "output_dir": str(safe_output_dir),
        "artifact_path": str(artifact_path),
        "manifest_path": str(manifest_path),
        "artifact_sha256": sha256_text(canonical_json(artifact)),
        "manifest_sha256": sha256_text(canonical_json(manifest)),
        "repo_write_performed": False,
        "db_write_performed": False,
        "passed": True,
        "failed": [],
    }
    assert_report_has_no_blocked_terms(report)
    return report


def canonical_json(obj: Mapping[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve()
    repo_root = ROOT.resolve()
    if resolved == repo_root or _is_relative_to(resolved, repo_root):
        raise ValueError(f"output_dir must be outside repository root: {resolved}")
    return resolved


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render prototype seed artifacts without applying them.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the renderer contract report")
    mode.add_argument("--render-artifact", action="store_true", help="print the prototype seed artifact")
    mode.add_argument("--render-manifest", action="store_true", help="print the checksum manifest")
    mode.add_argument("--write-temp", action="store_true", help="write artifact and manifest to a safe temp directory")
    parser.add_argument("--output-dir", type=Path, help="safe repository-external output directory for --write-temp")
    args = parser.parse_args(argv)

    try:
        if args.contract_report:
            report = build_contract_report()
        elif args.render_artifact:
            report = build_seed_artifact()
        elif args.render_manifest:
            artifact = build_seed_artifact()
            report = build_seed_manifest(artifact)
        else:
            if args.output_dir is None:
                parser.error("--write-temp requires --output-dir")
            report = write_temp_artifacts(args.output_dir)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0


def _source_file_contract() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "required": False,
            "source_role": _source_role(path),
        }
        for path in CANONICAL_JSONL_FILES
    ]


def _load_source_records(source_root: Path) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for relative_path in CANONICAL_JSONL_FILES:
        path = source_root / relative_path
        if not path.is_file():
            records[relative_path] = []
            continue
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                rows.append(
                    {
                        "source_file": relative_path,
                        "line_no": line_no,
                        "record_key": _stable_record_key(relative_path, line_no),
                    }
                )
        records[relative_path] = rows
    return records


def _source_file_status(
    source_records: Mapping[str, Sequence[Mapping[str, Any]]],
    source_root: Path,
) -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for relative_path in CANONICAL_JSONL_FILES:
        path = source_root / relative_path
        present = path.is_file()
        status[relative_path] = {
            "present": present,
            "required": False,
            "row_count": len(source_records.get(relative_path, ())) if present else None,
            "sha256": seed_artifact_plan.sha256_file(path) if present else None,
        }
    return status


def _table_payload(
    table_name: str,
    source_records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if table_name == "schema_rehearsal_meta":
        rows = [
            {
                "record_key": "schema_rehearsal_meta:prototype",
                "renderer_version": RENDERER_VERSION,
                "formal_schema_draft_version": formal_schema_draft.DRAFT_VERSION,
                "ddl_rehearsal_version": formal_ddl_rehearsal.REHEARSAL_VERSION,
            }
        ]
    elif table_name == "imports":
        rows = [
            {
                "record_key": f"import:{relative_path}",
                "source_file": relative_path,
                "line_count": len(source_records.get(relative_path, ())),
                "source_present": bool(source_records.get(relative_path)),
            }
            for relative_path in CANONICAL_JSONL_FILES
            if source_records.get(relative_path)
        ]
    else:
        rows = [
            _row_for_table(table_name, record)
            for relative_path in TABLE_SOURCE_FILES[table_name]
            for record in source_records.get(relative_path, ())
        ]
    return {
        "table_name": table_name,
        "row_count": len(rows),
        "rows": rows,
        "source_files": list(TABLE_SOURCE_FILES[table_name]),
        "dry_estimate": True,
        "prototype_only": True,
    }


def _row_for_table(table_name: str, record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_key": f"{table_name}:{record['record_key']}",
        "source_file": record["source_file"],
        "line_no": record["line_no"],
        "source_record_key": record["record_key"],
    }


def _stable_record_key(source_file: str, line_no: int) -> str:
    return f"{source_file}:{line_no}"


def _source_role(path: str) -> str:
    if "query" in path or "search" in path:
        return "query"
    if "source_" in path:
        return "source"
    if "evidence_cards" in path:
        return "evidence"
    if "evidence_clusters" in path:
        return "cluster"
    if "thematic_anchor" in path:
        return "anchor"
    return "canonical"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = report_as_json(report).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


if __name__ == "__main__":
    raise SystemExit(main())
