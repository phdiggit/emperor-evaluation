from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_target_mapping import CANONICAL_JSONL_FILES as MAPPED_JSONL_FILES  # noqa: E402


MANIFEST_VERSION = "canonical-manifest-candidate-v1"
EXPECTED_JSONL_FILES = (
    "data/events.jsonl",
    "data/evidence_cards.jsonl",
    "data/evidence_clusters.jsonl",
    "data/query_profiles.jsonl",
    "data/search_logs.jsonl",
    "data/sources.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchors.jsonl",
    "data/trigger_terms.jsonl",
)
PRIMARY_KEY_BY_FILE = {
    "data/events.jsonl": "event_id",
    "data/evidence_cards.jsonl": "evidence_id",
    "data/evidence_clusters.jsonl": "cluster_id",
    "data/query_profiles.jsonl": "query_profile_id",
    "data/search_logs.jsonl": "search_id",
    "data/sources.jsonl": "source_id",
    "data/thematic_anchor_events.jsonl": "anchor_id",
    "data/thematic_anchor_mechanisms.jsonl": "anchor_id",
    "data/thematic_anchor_objects.jsonl": "anchor_id",
    "data/thematic_anchors.jsonl": "anchor_id",
    "data/trigger_terms.jsonl": "term_id",
}
EXCLUDED_PATTERNS = (
    "data/batches/**",
    "data/*_batches/**",
    "archive/data/**",
    "exports/**",
    "logs/**",
    "tmp/**",
)
REFERENCE_EDGES = (
    ("data/evidence_cards.jsonl", "source_id", "data/sources.jsonl", "source_id"),
    ("data/events.jsonl", "source_id", "data/sources.jsonl", "source_id"),
    ("data/search_logs.jsonl", "linked_evidence_id", "data/evidence_cards.jsonl", "evidence_id"),
    ("data/search_logs.jsonl", "linked_evidence_ids", "data/evidence_cards.jsonl", "evidence_id"),
    ("data/search_logs.jsonl", "linked_source_ids", "data/sources.jsonl", "source_id"),
    ("data/evidence_clusters.jsonl", "linked_evidence_ids", "data/evidence_cards.jsonl", "evidence_id"),
    ("data/thematic_anchors.jsonl", "linked_evidence_ids", "data/evidence_cards.jsonl", "evidence_id"),
    ("data/thematic_anchors.jsonl", "linked_cluster_ids", "data/evidence_clusters.jsonl", "cluster_id"),
)
DEFERRED_REFERENCE_FIELDS = {
    "item": "range/filter only; not a manifest orphan check",
    "subitem": "range/filter only; not a manifest orphan check",
    "person": "person resolver belongs to a later package",
    "persons": "person resolver belongs to a later package",
    "linked_persons": "person resolver belongs to a later package",
    "source_batch": "batch provenance is excluded from canonical manifest hash",
    "thematic_anchor_targets": "anchor resolver belongs to a later package",
    "object_anchors": "anchor resolver belongs to a later package",
}


@dataclass(frozen=True)
class FileScan:
    path: str
    exists: bool
    sha256: str | None
    row_count: int
    nonempty_line_count: int
    primary_key: str
    id_count: int
    id_prefixes: tuple[str, ...]
    duplicate_ids: Mapping[str, tuple[int, ...]]
    missing_primary_key_lines: tuple[int, ...]
    invalid_json_lines: Mapping[str, str]
    non_object_lines: tuple[int, ...]
    rows: tuple[Mapping[str, Any], ...]

    def as_report(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "sha256": self.sha256,
            "row_count": self.row_count,
            "nonempty_line_count": self.nonempty_line_count,
            "primary_key": self.primary_key,
            "id_count": self.id_count,
            "id_prefixes": list(self.id_prefixes),
            "duplicate_ids": {key: list(lines) for key, lines in self.duplicate_ids.items()},
            "missing_primary_key_lines": list(self.missing_primary_key_lines),
            "invalid_json_lines": dict(self.invalid_json_lines),
            "non_object_lines": list(self.non_object_lines),
        }


def sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_reference_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"[;,；，]", value)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = [item for item in value if isinstance(item, str)]
    else:
        values = []
    return [item.strip() for item in values if item.strip()]


def id_prefix(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    return re.sub(r"[-_][0-9]+$", "", stripped)


def scan_jsonl_file(source_root: Path, relative: str) -> FileScan:
    path = source_root / relative
    primary_key = PRIMARY_KEY_BY_FILE[relative]
    if not path.exists():
        return FileScan(
            path=relative,
            exists=False,
            sha256=None,
            row_count=0,
            nonempty_line_count=0,
            primary_key=primary_key,
            id_count=0,
            id_prefixes=(),
            duplicate_ids={},
            missing_primary_key_lines=(),
            invalid_json_lines={},
            non_object_lines=(),
            rows=(),
        )

    rows: list[Mapping[str, Any]] = []
    id_lines: dict[str, list[int]] = {}
    missing_primary_key_lines: list[int] = []
    invalid_json_lines: dict[str, str] = {}
    non_object_lines: list[int] = []
    nonempty_line_count = 0

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        nonempty_line_count += 1
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            invalid_json_lines[str(line_no)] = exc.msg
            continue
        if not isinstance(payload, dict):
            non_object_lines.append(line_no)
            continue
        rows.append(payload)
        raw_key = payload.get(primary_key)
        key = raw_key.strip() if isinstance(raw_key, str) else ""
        if not key:
            missing_primary_key_lines.append(line_no)
            continue
        id_lines.setdefault(key, []).append(line_no)

    duplicate_ids = {key: tuple(lines) for key, lines in id_lines.items() if len(lines) > 1}
    prefixes = sorted({id_prefix(key) for key in id_lines if id_prefix(key)})
    return FileScan(
        path=relative,
        exists=True,
        sha256=sha256_bytes(path),
        row_count=len(rows),
        nonempty_line_count=nonempty_line_count,
        primary_key=primary_key,
        id_count=len(id_lines),
        id_prefixes=tuple(prefixes),
        duplicate_ids=duplicate_ids,
        missing_primary_key_lines=tuple(missing_primary_key_lines),
        invalid_json_lines=invalid_json_lines,
        non_object_lines=tuple(non_object_lines),
        rows=tuple(rows),
    )


def find_top_level_jsonl(source_root: Path) -> list[str]:
    data_dir = source_root / "data"
    if not data_dir.exists():
        return []
    return sorted(path.relative_to(source_root).as_posix() for path in data_dir.glob("*.jsonl") if path.is_file())


def build_reference_report(scans: Mapping[str, FileScan]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids_by_file: dict[str, set[str]] = {}
    for relative, scan in scans.items():
        primary_key = PRIMARY_KEY_BY_FILE[relative]
        ids = {
            str(row[primary_key]).strip()
            for row in scan.rows
            if isinstance(row.get(primary_key), str) and str(row[primary_key]).strip()
        }
        ids_by_file[relative] = ids

    edges: list[dict[str, Any]] = []
    orphan_refs: list[dict[str, Any]] = []
    for source_file, source_field, target_file, target_field in REFERENCE_EDGES:
        values: dict[str, list[int]] = {}
        for line_index, row in enumerate(scans[source_file].rows, start=1):
            for value in normalize_reference_values(row.get(source_field)):
                values.setdefault(value, []).append(line_index)
        missing = {
            value: lines
            for value, lines in values.items()
            if value not in ids_by_file.get(target_file, set())
        }
        edge = {
            "source_file": source_file,
            "source_field": source_field,
            "target_file": target_file,
            "target_field": target_field,
            "reference_count": sum(len(lines) for lines in values.values()),
            "unique_reference_count": len(values),
            "orphan_count": len(missing),
        }
        edges.append(edge)
        for value, lines in missing.items():
            orphan_refs.append({**edge, "value": value, "line_numbers": lines})
    return edges, orphan_refs


def build_manifest_digest(files: Sequence[FileScan]) -> str:
    payload = [
        {
            "path": item.path,
            "sha256": item.sha256,
            "row_count": item.row_count,
            "primary_key": item.primary_key,
        }
        for item in files
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_candidate_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    actual_top_level = find_top_level_jsonl(source_root)
    expected = list(EXPECTED_JSONL_FILES)
    scans = {relative: scan_jsonl_file(source_root, relative) for relative in expected}
    file_entries = [scans[relative] for relative in expected]
    reference_edges, orphan_refs = build_reference_report(scans)
    unexpected_files = sorted(set(actual_top_level) - set(expected))
    missing_files = [relative for relative, scan in scans.items() if not scan.exists]
    duplicate_ids = {
        relative: {key: list(lines) for key, lines in scan.duplicate_ids.items()}
        for relative, scan in scans.items()
        if scan.duplicate_ids
    }
    schema_mismatches = {
        relative: {
            "missing_primary_key_lines": list(scan.missing_primary_key_lines),
            "invalid_json_lines": dict(scan.invalid_json_lines),
            "non_object_lines": list(scan.non_object_lines),
        }
        for relative, scan in scans.items()
        if scan.missing_primary_key_lines or scan.invalid_json_lines or scan.non_object_lines
    }
    mapped = set(MAPPED_JSONL_FILES)
    mapping_coverage = {
        relative: {
            "covered_by_jsonl_target_mapping": relative in mapped,
            "note": "ready_for_milestone_1b_mapping_review"
            if relative in mapped
            else "requires_milestone_1b_mapping_extension",
        }
        for relative in expected
    }
    blockers = {
        "missing_files": missing_files,
        "unexpected_files": unexpected_files,
        "duplicate_ids_by_file": duplicate_ids,
        "schema_mismatches_by_file": schema_mismatches,
        "orphan_references": orphan_refs,
    }
    fail_closed = any(bool(value) for value in blockers.values())
    return {
        "mode": "manifest-candidate-report",
        "manifest_version": MANIFEST_VERSION,
        "gate_status": "G1_REQUIRED",
        "approval_required_from_user": True,
        "fail_closed": fail_closed,
        "manifest_candidate": "generated report: python scripts/platform/canonical_manifest_gate.py --candidate-report",
        "manifest_sha256": build_manifest_digest(file_entries),
        "repository_survey": {
            "source_root": str(source_root),
            "canonical_build_entrypoint": "scripts/build/build_db.py",
            "sqlite_schema_path": "db/sqlite/001_cache.sql",
            "postgres_schema_contract_paths": ["db/postgres/001_init.sql", "db/schema.sql"],
            "writes_data": False,
            "reads_database_dsn": False,
            "connects_database": False,
        },
        "data_survey": {
            "covered_file_scope": "top-level data/*.jsonl only",
            "covered_files": expected,
            "covered_file_count": len(expected),
            "excluded_patterns": list(EXCLUDED_PATTERNS),
            "actual_top_level_data_jsonl": actual_top_level,
            "rows_total": sum(scan.row_count for scan in file_entries),
        },
        "schema_survey": {
            "primary_keys": dict(PRIMARY_KEY_BY_FILE),
            "mapping_coverage_by_file": mapping_coverage,
            "deferred_reference_fields": dict(DEFERRED_REFERENCE_FIELDS),
        },
        "files": [scan.as_report() for scan in file_entries],
        "reference_edges": reference_edges,
        "blockers": blockers,
        "risk_summary": [
            "missing file" if missing_files else "no missing file",
            "unexpected file" if unexpected_files else "no unexpected file",
            "duplicate ID" if duplicate_ids else "no duplicate ID",
            "orphan reference" if orphan_refs else "no orphan reference",
            "schema mismatch" if schema_mismatches else "no schema mismatch",
        ],
        "boundaries": [
            "does not approve canonical production data manifest",
            "does not modify data or archive data",
            "does not read data batches or archive data",
            "does not read production DSN",
            "does not connect PostgreSQL",
            "does not freeze JSONL write source",
            "does not switch PostgreSQL unique write source",
        ],
    }


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def report_as_markdown(report: Mapping[str, Any]) -> str:
    files = report["files"]
    lines = [
        "# Canonical Production Data Manifest 候选包",
        "",
        "```text",
        "G1_REQUIRED",
        f"manifest_candidate: {report['manifest_candidate']}",
        "covered_files:",
        "  - data/*.jsonl only",
        "excluded_files:",
    ]
    lines.extend(f"  - {pattern}" for pattern in report["data_survey"]["excluded_patterns"])
    lines.extend(
        [
            "risk_summary:",
            *[f"  - {item}" for item in report["risk_summary"]],
            "approval_required_from_user: true",
            "```",
            "",
            f"- manifest_version: `{report['manifest_version']}`",
            f"- manifest_sha256: `{report['manifest_sha256']}`",
            f"- fail_closed: `{str(report['fail_closed']).lower()}`",
            f"- covered_file_count: `{report['data_survey']['covered_file_count']}`",
            f"- rows_total: `{report['data_survey']['rows_total']}`",
            "",
            "| file | rows | primary_key | sha256 | id_prefixes |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )
    for item in files:
        prefixes = ", ".join(item["id_prefixes"]) if item["id_prefixes"] else "-"
        lines.append(
            f"| `{item['path']}` | {item['row_count']} | `{item['primary_key']}` | `{item['sha256']}` | {prefixes} |"
        )
    lines.extend(
        [
            "",
            "## Reference Edges",
            "",
            "| source | field | target | references | orphans |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for edge in report["reference_edges"]:
        lines.append(
            "| "
            f"`{edge['source_file']}` | `{edge['source_field']}` | "
            f"`{edge['target_file']}.{edge['target_field']}` | "
            f"{edge['reference_count']} | {edge['orphan_count']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["boundaries"])
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build the Epic 1 canonical manifest candidate gate report.")
    parser.add_argument("--candidate-report", action="store_true", help="print the manifest candidate JSON report")
    parser.add_argument("--markdown-report", action="store_true", help="print the manifest candidate Markdown report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root to scan")
    parser.add_argument("--strict-exit", action="store_true", help="return non-zero when the report is fail-closed")
    args = parser.parse_args(argv)

    report = build_candidate_report(source_root=args.source_root)
    if args.markdown_report:
        sys.stdout.write(report_as_markdown(report))
    else:
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
    if args.strict_exit and report["fail_closed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
