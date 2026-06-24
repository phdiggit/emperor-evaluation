from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import formal_ddl_live_rehearsal, formal_ddl_rehearsal, formal_schema_draft


SEED_PLAN_VERSION = "seed-artifact-plan-v1"
MANIFEST_VERSION = "proposed-seed-manifest-v1"
ARTIFACT_KIND = "proposed_seed_manifest"
SOURCE_OF_TRUTH = "canonical JSONL remains source-of-truth; seed artifacts are derived only"
CANONICAL_JSONL_FILES = (
    "data/query_profiles.jsonl",
    "data/search_tasks.jsonl",
    "data/source_documents.jsonl",
    "data/source_passages.jsonl",
    "data/evidence_cards.jsonl",
    "data/evidence_clusters.jsonl",
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
)
SEED_CANDIDATE_TABLES = (*formal_schema_draft.PHASE_1_BASE_TABLES, "schema_rehearsal_meta")
BLOCKED_SEED_TABLES = (
    *formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES,
    *formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES,
)
CHECKSUM_MANIFEST_FIELDS = (
    "manifest_version",
    "source_file",
    "source_row_count",
    "source_sha256",
    "tool_version",
    "formal_schema_draft_version",
    "ddl_rehearsal_version",
    "seed_plan_version",
    "generated_at",
    "artifact_sha256",
    "artifact_kind",
    "secret_free",
    "reproducible",
    "source_of_truth",
)
PLANNED_ARTIFACT_FIELDS = (
    "artifact_kind",
    "seed_plan_version",
    "source_of_truth",
    "source_files",
    "table_plan",
    "validation_gates",
    "checksum_manifest",
)
VALIDATION_GATES = (
    "canonical JSONL source boundary verification",
    "formal schema draft contract report green",
    "isolated formal DDL rehearsal contract report green",
    "isolated live rehearsal contract report green",
    "phase 1 seed candidate table review",
    "phase 2 and phase 3 table exclusion review",
    "future checksum manifest review",
)
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not read .env or DSN values",
    "does not connect to PostgreSQL",
    "does not execute DDL or migration",
    "does not generate seed artifact",
    "does not write checksum manifest file",
    "does not write exports",
    "does not switch the JSONL write source",
    "does not write production target tables",
    "does not generate business conclusions",
)
STRICT_BOUNDARIES = (
    "offline_only",
    "stdout_only",
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
    "does_not_write_data",
    "does_not_write_exports",
    "does_not_write_db",
    "does_not_generate_seed_artifact",
    "does_not_write_checksum_manifest_file",
    "does_not_switch_jsonl_write_source",
)
LIMITATIONS = (
    "dry estimates only",
    "missing canonical JSONL files are reported as optional missing sources",
    "no seed rows are generated",
    "no inserted rows are counted",
    "no production counts are claimed",
    "source host and document revision counts are dry derived estimates",
    "schema_rehearsal_meta is future metadata only",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "seed_plan_version": SEED_PLAN_VERSION,
        "status": "Proposed",
        "source_of_truth": SOURCE_OF_TRUTH,
        "formal_schema_draft_version": formal_schema_draft.DRAFT_VERSION,
        "ddl_rehearsal_version": formal_ddl_rehearsal.REHEARSAL_VERSION,
        "live_rehearsal_version": formal_ddl_live_rehearsal.LIVE_REHEARSAL_VERSION,
        "seed_candidate_tables": list(SEED_CANDIDATE_TABLES),
        "blocked_seed_tables": _blocked_table_plan(),
        "source_jsonl_files": _source_file_contract(),
        "checksum_manifest_contract": {
            "manifest_version": MANIFEST_VERSION,
            "artifact_kind": ARTIFACT_KIND,
            "planned_fields": list(CHECKSUM_MANIFEST_FIELDS),
            "source_sha256_field": "future_or_dry_run_only",
            "artifact_sha256_field": "future_only",
            "generated_in_this_pr": False,
            "writes_performed": False,
            "secret_free_required": True,
            "reproducible_required": True,
        },
        "seed_artifact_contract": {
            "artifact_kind": "future_seed_artifact",
            "generated_artifact": False,
            "writes_performed": False,
            "source": "canonical JSONL only",
            "phase_1_tables_only": True,
            "phase_2_3_tables_excluded": True,
            "future_output_path_pattern": "future ignored or reviewed artifact path only",
        },
        "dry_run_plan": _dry_run_plan_contract(),
        "validation_gates": list(VALIDATION_GATES),
        "non_goals": list(NON_GOALS),
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "future_work": [
            "future opt-in seed artifact renderer prototype",
            "future checksum report review",
            "future temporary or ignored artifact output only",
            "future production seed application requires separate approval",
        ],
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_dry_run_report(source_root: Path = ROOT) -> dict[str, Any]:
    checked = list(CANONICAL_JSONL_FILES)
    found: list[str] = []
    missing: list[str] = []
    row_counts: dict[str, int | None] = {}
    source_sha256: dict[str, str | None] = {}

    for relative_path in checked:
        path = source_root / relative_path
        if path.is_file():
            found.append(relative_path)
            row_counts[relative_path] = load_jsonl_count(path)
            source_sha256[relative_path] = sha256_file(path)
        else:
            missing.append(relative_path)
            row_counts[relative_path] = None
            source_sha256[relative_path] = None

    report = {
        "mode": "dry-run",
        "source_of_truth": SOURCE_OF_TRUTH,
        "source_files_checked": checked,
        "source_files_found": found,
        "source_files_missing": missing,
        "row_counts_by_source_file": row_counts,
        "source_sha256_by_source_file": source_sha256,
        "planned_rows_by_table": _planned_rows_by_table(row_counts),
        "seed_candidate_tables": list(SEED_CANDIDATE_TABLES),
        "blocked_seed_tables": _blocked_table_plan(),
        "generated_artifact": False,
        "writes_performed": False,
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_manifest_skeleton() -> dict[str, Any]:
    report = {
        "mode": "manifest-skeleton",
        "manifest_version": MANIFEST_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_in_this_pr": False,
        "source_files": _source_file_contract(),
        "planned_checksum_fields": list(CHECKSUM_MANIFEST_FIELDS),
        "planned_artifact_fields": list(PLANNED_ARTIFACT_FIELDS),
        "secret_free_required": True,
        "reproducible_required": True,
        "future_output_path_pattern": "future ignored or reviewed manifest path only",
        "non_goals": list(NON_GOALS),
        "limitations": [
            "skeleton only",
            "does not calculate artifact_sha256",
            "does not write checksum manifest file",
            "does not generate seed artifact",
        ],
    }
    assert_report_has_no_blocked_terms(report)
    return report


def load_jsonl_count(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Plan a future seed artifact contract without writing artifacts.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the seed artifact contract report")
    mode.add_argument("--dry-run", action="store_true", help="print dry source and table row estimates")
    mode.add_argument("--manifest-skeleton", action="store_true", help="print the future checksum manifest skeleton")
    args = parser.parse_args(argv)

    if args.contract_report:
        report = build_contract_report()
    elif args.dry_run:
        report = build_dry_run_report()
    else:
        report = build_manifest_skeleton()

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


def _blocked_table_plan() -> list[dict[str, str]]:
    return [
        {
            "table_name": table,
            "seed_plan": "blocked",
            "reason": "phase_2_or_3_excluded_from_seed_candidate_tables",
        }
        for table in BLOCKED_SEED_TABLES
    ]


def _dry_run_plan_contract() -> dict[str, Any]:
    return {
        "row_count_source": "canonical JSONL line counts only",
        "planned_rows_label": "dry estimates",
        "not_seed_rows": True,
        "not_inserted_rows": True,
        "not_production_counts": True,
        "source_files_checked": list(CANONICAL_JSONL_FILES),
        "table_groups": {
            "query": ["query_profiles", "search_tasks"],
            "source": ["src_hosts", "src_docs", "doc_revs", "passages"],
            "evidence": ["evd_cards"],
            "cluster": ["clusters"],
            "anchor": ["anchors"],
            "import_envelope": ["imports", "import_rows"],
            "schema_metadata": ["schema_rehearsal_meta"],
        },
    }


def _planned_rows_by_table(row_counts: Mapping[str, int | None]) -> dict[str, dict[str, Any]]:
    source_total = _sum_counts(row_counts)
    anchor_total = _sum_counts(
        row_counts,
        only=(
            "data/thematic_anchors.jsonl",
            "data/thematic_anchor_objects.jsonl",
            "data/thematic_anchor_events.jsonl",
            "data/thematic_anchor_mechanisms.jsonl",
        ),
    )
    source_documents = row_counts.get("data/source_documents.jsonl")
    source_passages = row_counts.get("data/source_passages.jsonl")
    plans = {
        "imports": _plan_entry(len([value for value in row_counts.values() if value is not None]), "found source files"),
        "import_rows": _plan_entry(source_total, "all found canonical JSONL rows"),
        "query_profiles": _plan_entry(row_counts.get("data/query_profiles.jsonl"), "query_profiles.jsonl rows"),
        "search_tasks": _plan_entry(row_counts.get("data/search_tasks.jsonl"), "search_tasks.jsonl rows"),
        "src_hosts": _plan_entry(source_documents, "source_documents.jsonl dry derived estimate"),
        "src_docs": _plan_entry(source_documents, "source_documents.jsonl dry derived estimate"),
        "doc_revs": _plan_entry(source_documents, "source_documents.jsonl dry derived estimate"),
        "passages": _plan_entry(source_passages, "source_passages.jsonl rows"),
        "evd_cards": _plan_entry(row_counts.get("data/evidence_cards.jsonl"), "evidence_cards.jsonl rows"),
        "clusters": _plan_entry(row_counts.get("data/evidence_clusters.jsonl"), "evidence_clusters.jsonl rows"),
        "anchors": _plan_entry(anchor_total, "thematic anchor JSONL rows"),
        "schema_rehearsal_meta": _plan_entry(1, "future schema metadata marker"),
    }
    plans["schema_rehearsal_meta"]["future_only"] = True
    return plans


def _plan_entry(planned_rows: int | None, basis: str) -> dict[str, Any]:
    return {
        "planned_rows": planned_rows,
        "basis": basis,
        "dry_estimate": True,
        "not_seed_rows": True,
        "not_inserted_rows": True,
        "not_production_counts": True,
    }


def _sum_counts(row_counts: Mapping[str, int | None], *, only: Sequence[str] | None = None) -> int:
    keys = only if only is not None else row_counts.keys()
    return sum(value for key in keys for value in [row_counts.get(key)] if value is not None)


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


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = report_as_json(report).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


if __name__ == "__main__":
    raise SystemExit(main())
