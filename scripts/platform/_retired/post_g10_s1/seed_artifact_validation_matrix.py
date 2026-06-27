from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


def _repo_root() -> Path:
    for path in Path(__file__).resolve().parents:
        if (path / "db" / "schema.sql").is_file() and (path / "scripts" / "platform").is_dir():
            return path
    raise RuntimeError("could not locate repository root")


ROOT = _repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (  # noqa: E402
    formal_schema_draft,
    seed_artifact_plan,
    seed_artifact_renderer,
)


VALIDATOR_VERSION = "seed-artifact-validation-matrix-v1"
EXPECTED_SEED_CANDIDATE_TABLES = (
    *formal_schema_draft.PHASE_1_BASE_TABLES,
    "schema_rehearsal_meta",
)
EXPECTED_BLOCKED_TABLES = (
    *formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES,
    *formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES,
)
ARTIFACT_FILENAME = seed_artifact_renderer.ARTIFACT_FILENAME
MANIFEST_FILENAME = seed_artifact_renderer.MANIFEST_FILENAME
VALIDATION_RULES = (
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
)
ARTIFACT_RULES = {
    "artifact_kind_is_prototype",
    "artifact_not_written_to_repo",
    "artifact_not_applied_to_db",
    "source_of_truth_preserved",
    "seed_candidate_tables_match_phase_1",
    "table_payloads_match_seed_candidates",
    "phase_2_tables_excluded",
    "phase_3_tables_excluded",
    "blocked_seed_tables_include_phase_2_3",
    "row_count_summary_matches_payloads",
    "source_checksums_match_artifact_sources",
    "schema_rehearsal_meta_metadata_only",
    "no_blocked_report_terms",
}
MANIFEST_RULES = {
    "manifest_artifact_hash_matches",
    "manifest_table_counts_match_artifact",
    "manifest_source_checksums_match_artifact",
    "manifest_flags_are_false_for_db_and_repo",
    "manifest_secret_free_and_reproducible",
    "no_blocked_report_terms",
}
TABLE_GATE_RULES = {
    "seed_candidate_tables_match_phase_1",
    "phase_2_tables_excluded",
    "phase_3_tables_excluded",
    "table_gates_allow_payload_tables",
    "table_gates_defer_relationship_downstream_tables",
}
SOURCE_BOUNDARY_RULES = {
    "source_boundary_uses_canonical_jsonl_only",
    "source_checksums_match_artifact_sources",
    "manifest_source_checksums_match_artifact",
}
STRICT_BOUNDARIES = (
    *seed_artifact_renderer.STRICT_BOUNDARIES,
    "validate_temp_reads_prototype_json_only",
    "validate_temp_does_not_create_output_dir",
)
LIMITATIONS = (
    "static validation matrix only",
    "prototype artifact only",
    "no seed application",
    "no production readiness claim",
    "missing optional canonical JSONL files stay valid when represented consistently",
)
NON_GOALS = (
    "does not modify canonical JSONL",
    "does not modify db/schema.sql",
    "does not modify db/postgres/001_init.sql",
    "does not read .env or connection values",
    "does not connect to PostgreSQL",
    "does not execute DDL or migration",
    "does not write data",
    "does not write exports",
    "does not write repository artifact files",
    "does not apply seed artifacts",
    "does not switch the JSONL write source",
    "does not generate business conclusions",
)


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "validator_version": VALIDATOR_VERSION,
        "renderer_version": seed_artifact_renderer.RENDERER_VERSION,
        "seed_plan_version": seed_artifact_plan.SEED_PLAN_VERSION,
        "formal_schema_draft_version": formal_schema_draft.DRAFT_VERSION,
        "supported_modes": ["contract-report", "validate-rendered", "validate-temp"],
        "validation_rules": list(VALIDATION_RULES),
        "expected_seed_candidate_tables": list(EXPECTED_SEED_CANDIDATE_TABLES),
        "expected_blocked_tables": list(EXPECTED_BLOCKED_TABLES),
        "non_goals": list(NON_GOALS),
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "future_work": [
            "compare prototype artifacts to later isolated preflight contracts",
            "keep any database preflight in a separate opt-in workflow",
            "keep production seed application in a separately approved change",
        ],
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def validate_rendered(source_root: Path = ROOT) -> dict[str, Any]:
    artifact = seed_artifact_renderer.build_seed_artifact(source_root)
    manifest = seed_artifact_renderer.build_seed_manifest(artifact, source_root)
    validation = validate_artifact_and_manifest(artifact, manifest)
    report = {
        "mode": "validate-rendered",
        "source_root": str(source_root.resolve()),
        "artifact_valid": validation["artifact_valid"],
        "manifest_valid": validation["manifest_valid"],
        "table_gate_valid": validation["table_gate_valid"],
        "source_boundary_valid": validation["source_boundary_valid"],
        "passed": validation["passed"],
        "failed": validation["failed"],
        "checked_rules": validation["checked_rules"],
        "artifact_summary": _artifact_summary(artifact),
        "manifest_summary": _manifest_summary(manifest),
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def validate_temp(output_dir: Path) -> dict[str, Any]:
    safe_output_dir = validate_output_dir_for_read(output_dir)
    artifact_path = safe_output_dir / ARTIFACT_FILENAME
    manifest_path = safe_output_dir / MANIFEST_FILENAME
    missing = [
        path.name
        for path in (artifact_path, manifest_path)
        if not path.is_file()
    ]
    if missing:
        return _temp_failure_report(
            safe_output_dir,
            artifact_path,
            manifest_path,
            [build_rule_result("prototype_json_files_exist", False, "required prototype JSON files are missing")],
        )

    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _temp_failure_report(
            safe_output_dir,
            artifact_path,
            manifest_path,
            [build_rule_result("prototype_json_files_parse", False, "prototype JSON files must parse cleanly")],
        )

    validation = validate_artifact_and_manifest(artifact, manifest)
    report = {
        "mode": "validate-temp",
        "output_dir": str(safe_output_dir),
        "artifact_path": str(artifact_path),
        "manifest_path": str(manifest_path),
        "artifact_valid": validation["artifact_valid"],
        "manifest_valid": validation["manifest_valid"],
        "passed": validation["passed"],
        "failed": validation["failed"],
        "checked_rules": validation["checked_rules"],
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def validate_artifact_and_manifest(
    artifact: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    rules = _artifact_rules(artifact)
    rules.extend(_table_gate_rules(artifact))
    rules.extend(_manifest_rules(artifact, manifest))
    rules.extend(_source_boundary_rules(artifact, manifest))
    rules.append(
        build_rule_result(
            "no_blocked_report_terms",
            _has_no_blocked_terms({"artifact": artifact, "manifest": manifest}),
            "reserved report terms are absent",
        )
    )

    failed = [rule["rule"] for rule in rules if not rule["passed"]]
    passed_rule_names = {rule["rule"] for rule in rules if rule["passed"]}
    return {
        "artifact_valid": _category_passed(rules, ARTIFACT_RULES),
        "manifest_valid": _category_passed(rules, MANIFEST_RULES),
        "table_gate_valid": _category_passed(rules, TABLE_GATE_RULES),
        "source_boundary_valid": _category_passed(rules, SOURCE_BOUNDARY_RULES),
        "passed": not failed and set(VALIDATION_RULES) <= passed_rule_names,
        "failed": failed,
        "checked_rules": rules,
    }


def build_rule_result(rule: str, passed: bool, reason: str) -> dict[str, Any]:
    return {
        "rule": rule,
        "passed": passed,
        "reason": reason,
    }


def validate_output_dir_for_read(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve()
    repo_root = ROOT.resolve()
    if resolved == repo_root or _is_relative_to(resolved, repo_root):
        raise ValueError(f"output_dir must be outside repository root: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"output_dir must already exist: {resolved}")
    return resolved


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Validate prototype seed artifacts without applying them.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the validator contract report")
    mode.add_argument("--validate-rendered", action="store_true", help="validate a freshly rendered in-memory artifact")
    mode.add_argument("--validate-temp", action="store_true", help="validate safe repository-external prototype JSON files")
    parser.add_argument("--output-dir", type=Path, help="repository-external directory containing prototype JSON files")
    args = parser.parse_args(argv)

    try:
        if args.contract_report:
            report = build_contract_report()
        elif args.validate_rendered:
            report = validate_rendered()
        else:
            if args.output_dir is None:
                parser.error("--validate-temp requires --output-dir")
            report = validate_temp(args.output_dir)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0 if report.get("passed", True) else 1


def _artifact_rules(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    seed_candidate_tables = tuple(artifact.get("seed_candidate_tables", ()))
    table_payloads = artifact.get("table_payloads", {})
    table_payload_names = set(table_payloads) if isinstance(table_payloads, Mapping) else set()
    blocked_seed_tables = set(artifact.get("blocked_seed_tables", ()))
    row_count_summary = artifact.get("row_count_summary", {})
    source_files = artifact.get("source_files", {})
    source_checksums = _source_checksum_map(artifact)

    return [
        build_rule_result(
            "artifact_kind_is_prototype",
            artifact.get("artifact_kind") == seed_artifact_renderer.ARTIFACT_KIND,
            "artifact kind matches the renderer prototype contract",
        ),
        build_rule_result(
            "artifact_not_written_to_repo",
            artifact.get("artifact_written_to_repo") is False,
            "artifact declares no repository artifact write",
        ),
        build_rule_result(
            "artifact_not_applied_to_db",
            artifact.get("artifact_applied_to_db") is False,
            "artifact declares no database application",
        ),
        build_rule_result(
            "source_of_truth_preserved",
            "canonical JSONL remains source-of-truth" in str(artifact.get("source_of_truth", "")),
            "canonical JSONL remains the source-of-truth",
        ),
        build_rule_result(
            "seed_candidate_tables_match_phase_1",
            seed_candidate_tables == EXPECTED_SEED_CANDIDATE_TABLES,
            "seed candidate tables match Phase 1 plus schema metadata",
        ),
        build_rule_result(
            "table_payloads_match_seed_candidates",
            table_payload_names == set(seed_candidate_tables),
            "table payload keys match seed candidate tables",
        ),
        build_rule_result(
            "phase_2_tables_excluded",
            not table_payload_names.intersection(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
            "relationship tables are excluded from artifact payloads",
        ),
        build_rule_result(
            "phase_3_tables_excluded",
            not table_payload_names.intersection(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
            "downstream tables are excluded from artifact payloads",
        ),
        build_rule_result(
            "blocked_seed_tables_include_phase_2_3",
            set(EXPECTED_BLOCKED_TABLES) <= blocked_seed_tables,
            "blocked seed tables include relationship and downstream tables",
        ),
        build_rule_result(
            "row_count_summary_matches_payloads",
            _row_count_summary_matches_payloads(row_count_summary, table_payloads),
            "row count summary matches each payload row count",
        ),
        build_rule_result(
            "source_checksums_match_artifact_sources",
            source_checksums == _checksums_from_source_files(source_files),
            "artifact source checksum map matches source file status",
        ),
        build_rule_result(
            "schema_rehearsal_meta_metadata_only",
            _schema_rehearsal_meta_is_metadata_only(table_payloads),
            "schema rehearsal metadata is prototype metadata only",
        ),
    ]


def _table_gate_rules(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    table_payloads = artifact.get("table_payloads", {})
    table_payload_names = set(table_payloads) if isinstance(table_payloads, Mapping) else set()
    gates = _table_gates_by_name()
    return [
        build_rule_result(
            "table_gates_allow_payload_tables",
            all(
                table == "schema_rehearsal_meta" or gates.get(table, {}).get("phase_1_allowed") is True
                for table in table_payload_names
            ),
            "all artifact payload tables are Phase 1 or metadata-only",
        ),
        build_rule_result(
            "table_gates_defer_relationship_downstream_tables",
            all(gates.get(table, {}).get("phase_1_allowed") is False for table in EXPECTED_BLOCKED_TABLES),
            "relationship and downstream tables remain deferred by table gates",
        ),
    ]


def _manifest_rules(
    artifact: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        build_rule_result(
            "manifest_artifact_hash_matches",
            manifest.get("artifact_sha256") == seed_artifact_renderer.sha256_text(seed_artifact_renderer.canonical_json(artifact)),
            "manifest artifact hash matches canonical artifact JSON",
        ),
        build_rule_result(
            "manifest_table_counts_match_artifact",
            manifest.get("table_row_counts") == artifact.get("row_count_summary"),
            "manifest table counts match artifact row count summary",
        ),
        build_rule_result(
            "manifest_source_checksums_match_artifact",
            manifest.get("source_file_checksums") == _source_checksum_map(artifact),
            "manifest source checksums match artifact source checksums",
        ),
        build_rule_result(
            "manifest_flags_are_false_for_db_and_repo",
            manifest.get("artifact_applied_to_db") is False and manifest.get("artifact_written_to_repo") is False,
            "manifest declares no database application or repository artifact write",
        ),
        build_rule_result(
            "manifest_secret_free_and_reproducible",
            manifest.get("secret_free") is True and manifest.get("reproducible") is True,
            "manifest declares secret-free reproducible output",
        ),
    ]


def _source_boundary_rules(
    artifact: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_sources = set(seed_artifact_plan.CANONICAL_JSONL_FILES)
    artifact_sources = set(_mapping_keys(artifact.get("source_files", {})))
    manifest_sources = set(_mapping_keys(manifest.get("source_file_checksums", {})))
    table_payloads = artifact.get("table_payloads", {})
    payload_sources = _payload_source_files(table_payloads)
    all_sources = artifact_sources | manifest_sources | payload_sources
    return [
        build_rule_result(
            "source_boundary_uses_canonical_jsonl_only",
            artifact_sources == expected_sources
            and manifest_sources == expected_sources
            and payload_sources <= expected_sources
            and all(_is_allowed_canonical_source(path) for path in all_sources),
            "artifact and manifest reference canonical JSONL sources only",
        ),
    ]


def _temp_failure_report(
    output_dir: Path,
    artifact_path: Path,
    manifest_path: Path,
    checked_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    failed = [rule["rule"] for rule in checked_rules if not rule["passed"]]
    report = {
        "mode": "validate-temp",
        "output_dir": str(output_dir),
        "artifact_path": str(artifact_path),
        "manifest_path": str(manifest_path),
        "artifact_valid": False,
        "manifest_valid": False,
        "passed": False,
        "failed": failed,
        "checked_rules": checked_rules,
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def _artifact_summary(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_kind": artifact.get("artifact_kind"),
        "artifact_written_to_repo": artifact.get("artifact_written_to_repo"),
        "artifact_applied_to_db": artifact.get("artifact_applied_to_db"),
        "seed_candidate_tables": list(artifact.get("seed_candidate_tables", ())),
        "blocked_seed_tables": list(artifact.get("blocked_seed_tables", ())),
        "row_count_summary": dict(artifact.get("row_count_summary", {})),
    }


def _manifest_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "manifest_version": manifest.get("manifest_version"),
        "artifact_sha256": manifest.get("artifact_sha256"),
        "table_row_counts": dict(manifest.get("table_row_counts", {})),
        "artifact_written_to_repo": manifest.get("artifact_written_to_repo"),
        "artifact_applied_to_db": manifest.get("artifact_applied_to_db"),
        "secret_free": manifest.get("secret_free"),
        "reproducible": manifest.get("reproducible"),
    }


def _table_gates_by_name() -> dict[str, Mapping[str, Any]]:
    return {
        gate["table_name"]: gate
        for gate in formal_schema_draft.build_contract_report()["table_by_table_gates"]
    }


def _row_count_summary_matches_payloads(row_count_summary: Any, table_payloads: Any) -> bool:
    if not isinstance(row_count_summary, Mapping) or not isinstance(table_payloads, Mapping):
        return False
    expected = {
        table_name: payload.get("row_count")
        for table_name, payload in table_payloads.items()
        if isinstance(payload, Mapping)
    }
    actual_rows_match = all(
        not isinstance(payload, Mapping)
        or "rows" not in payload
        or payload.get("row_count") == len(payload.get("rows", ()))
        for payload in table_payloads.values()
    )
    return dict(row_count_summary) == expected and actual_rows_match


def _source_checksum_map(artifact: Mapping[str, Any]) -> dict[str, Any]:
    checksums = artifact.get("checksums", {})
    if not isinstance(checksums, Mapping):
        return {}
    source_checksums = checksums.get("source_file_sha256", {})
    if not isinstance(source_checksums, Mapping):
        return {}
    return dict(source_checksums)


def _checksums_from_source_files(source_files: Any) -> dict[str, Any]:
    if not isinstance(source_files, Mapping):
        return {}
    return {
        path: item.get("sha256")
        for path, item in source_files.items()
        if isinstance(item, Mapping)
    }


def _schema_rehearsal_meta_is_metadata_only(table_payloads: Any) -> bool:
    if not isinstance(table_payloads, Mapping):
        return False
    payload = table_payloads.get("schema_rehearsal_meta")
    if not isinstance(payload, Mapping):
        return False
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 1:
        return False
    return (
        payload.get("row_count") == 1
        and payload.get("source_files") == []
        and payload.get("dry_estimate") is True
        and payload.get("prototype_only") is True
        and "renderer_version" in rows[0]
        and "formal_schema_draft_version" in rows[0]
    )


def _payload_source_files(table_payloads: Any) -> set[str]:
    if not isinstance(table_payloads, Mapping):
        return set()
    sources: set[str] = set()
    for payload in table_payloads.values():
        if isinstance(payload, Mapping):
            sources.update(str(path) for path in payload.get("source_files", ()))
    return sources


def _is_allowed_canonical_source(path: str) -> bool:
    path = path.replace("\\", "/")
    return (
        path in seed_artifact_plan.CANONICAL_JSONL_FILES
        and not path.startswith("data/batches/")
        and "/batches/" not in path
        and not path.startswith("archive/data/")
        and not path.startswith("exports/")
    )


def _mapping_keys(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    return [str(key) for key in value]


def _category_passed(rules: Sequence[Mapping[str, Any]], category: set[str]) -> bool:
    by_name = {str(rule["rule"]): bool(rule["passed"]) for rule in rules}
    return all(by_name.get(rule_name) is True for rule_name in category)


def _has_no_blocked_terms(report: Mapping[str, Any]) -> bool:
    text = report_as_json(report).lower()
    return all(term not in text for term in formal_schema_draft.BLOCKED_REPORT_TERMS)


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    if not _has_no_blocked_terms(report):
        raise AssertionError("report unexpectedly contains a reserved report term")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
