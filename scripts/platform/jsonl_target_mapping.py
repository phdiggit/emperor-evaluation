from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
MAPPING_VERSION = "jsonl-target-mapping-v1"
CANONICAL_JSONL_FILES = (
    "data/query_profiles.jsonl",
    "data/search_logs.jsonl",
    "data/sources.jsonl",
    "data/evidence_cards.jsonl",
    "data/evidence_clusters.jsonl",
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
)
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")
LIMITATIONS = (
    "当前 JSONL 仍是写源；本契约不迁移 JSONL。",
    "本契约只定义 staging/target 映射规则，不写 PostgreSQL 业务事实表。",
    "reference risk 字段必须经后续人工复核与解析后才能落外键。",
    "从 staging 进入 target table 必须另开 PR。",
)


@dataclass(frozen=True)
class JsonlFileMapping:
    source_file: str
    target_tables: tuple[str, ...]
    code_field: str | None
    required_fields: tuple[str, ...]
    direct_fields: Mapping[str, str]
    candidate_fields: Mapping[str, tuple[str, ...]]
    payload_fields: tuple[str, ...]
    reference_risk_fields: Mapping[str, str]
    range_filter_fields: Mapping[str, str]
    deferred_relationships: Mapping[str, str]
    staging_only: bool = False
    blocked_reason: str | None = None

    def known_fields(self) -> set[str]:
        fields = set(self.required_fields)
        fields.update(self.direct_fields)
        fields.update(self.candidate_fields)
        fields.update(self.payload_fields)
        fields.update(self.reference_risk_fields)
        fields.update(self.range_filter_fields)
        return fields

    def as_report(self) -> dict[str, Any]:
        return {
            "target_tables": list(self.target_tables),
            "direct_fields": dict(self.direct_fields),
            "candidate_fields": {key: list(value) for key, value in self.candidate_fields.items()},
            "payload_fields": list(self.payload_fields),
            "reference_risk_fields": dict(self.reference_risk_fields),
            "range_filter_fields": dict(self.range_filter_fields),
            "deferred_relationships": dict(self.deferred_relationships),
            "staging_only": self.staging_only,
            "blocked_reason": self.blocked_reason,
        }


def build_mappings() -> dict[str, JsonlFileMapping]:
    query_range = {
        "item": "range/filter only; resolve to subitems in a later mapper",
        "subitem": "range/filter only; resolve to subitems in a later mapper",
    }
    person_range = {"person": "range/filter only; resolve to persons in a later mapper"}
    anchor_block = "current PostgreSQL schema has no anchors or anchor_links target tables"
    return {
        "data/query_profiles.jsonl": JsonlFileMapping(
            source_file="data/query_profiles.jsonl",
            target_tables=("query_profiles",),
            code_field="query_profile_id",
            required_fields=("query_profile_id", "item", "subitem"),
            direct_fields={
                "query_profile_id": "query_profiles.code",
                "profile_scope": "query_profiles.scope candidate",
                "status": "query_profiles.status candidate",
            },
            candidate_fields={},
            payload_fields=(
                "query",
                "query_terms",
                "notes",
                "note",
                "source_scope",
                "search_mode",
                "search_modes",
                "source_scopes",
                "positive_terms",
                "negative_terms",
                "reversal_terms",
                "positive_dimensions",
                "negative_dimensions",
                "reversal_or_balance_dimensions",
                "reverse_search_required_when",
                "coverage_policy",
                "evidence_policy",
                "retention_policy",
                "source_batch",
                "profile_role",
                "schema_version",
            ),
            reference_risk_fields={
                "inherits_from": "query profile inheritance requires resolved profile code",
                "object_anchors": "embedded anchor objects require later anchor resolver review",
                "thematic_anchor_targets": "anchor target names require later anchor resolver review",
            },
            range_filter_fields={**query_range, **person_range},
            deferred_relationships={
                "persons": "person names/codes require resolver output before person_id",
                "subitems": "item/subitem require resolver output before subitem_id",
            },
        ),
        "data/search_logs.jsonl": JsonlFileMapping(
            source_file="data/search_logs.jsonl",
            target_tables=("search_tasks", "search_hits"),
            code_field="search_id",
            required_fields=("search_id",),
            direct_fields={
                "search_id": "search_tasks.code",
                "query": "search_tasks.query_text candidate",
                "status": "search_tasks.status candidate",
            },
            candidate_fields={"query_terms": ("search_tasks.query_text", "search_tasks.payload")},
            payload_fields=(
                "result_summary",
                "source_scope",
                "search_mode",
                "notes",
                "note",
                "searched_at",
                "result_status",
                "polarity",
                "trigger_family",
                "derived_from_dimension",
                "expected_source_scope",
                "next_action",
                "rejection_reason",
                "source_batch",
                "source_polarity",
                "source_status",
            ),
            reference_risk_fields={
                "query_profile_id": "query_profiles.code reference requires resolved query profile row",
                "linked_source_ids": "do not write FK until source documents/passages are resolved",
                "linked_evidence_ids": "do not write FK until evidence card codes are resolved",
            },
            range_filter_fields={**query_range, **person_range},
            deferred_relationships={
                "search_hits": "split result entries only when URL/result payload is present",
            },
        ),
        "data/sources.jsonl": JsonlFileMapping(
            source_file="data/sources.jsonl",
            target_tables=("src_hosts", "src_docs", "doc_revs", "passages"),
            code_field="source_id",
            required_fields=("source_id",),
            direct_fields={
                "title": "src_docs.title",
                "source_title": "src_docs.title",
                "url": "src_docs.canon_url",
                "source_url": "src_docs.canon_url",
                "host": "src_hosts.code candidate",
                "source_host": "src_hosts.code candidate",
            },
            candidate_fields={"source_id": ("src_docs.code", "doc_revs.code")},
            payload_fields=(
                "quote",
                "context",
                "raw_text",
                "excerpt",
                "notes",
                "note",
                "meta",
                "author",
                "dynasty",
                "volume",
                "location",
            ),
            reference_risk_fields={},
            range_filter_fields={},
            deferred_relationships={
                "doc_revs": "source_id may fan out to revisions after fetch/version rules exist",
                "passages": "quote/context text may become passages only after context review",
            },
        ),
        "data/evidence_cards.jsonl": JsonlFileMapping(
            source_file="data/evidence_cards.jsonl",
            target_tables=("evd_cards", "evd_src_links"),
            code_field="evidence_id",
            required_fields=("evidence_id",),
            direct_fields={
                "evidence_id": "evd_cards.code",
                "polarity": "evd_cards.polarity candidate",
                "strength": "evd_cards.strength candidate",
                "human_level": "evd_cards.human_level",
                "quote_short": "evd_cards.quote_short",
                "interpretation": "evd_cards.interpretation",
                "cross_item_split": "evd_cards.cross_item_split candidate",
                "scoring_effect": "evd_cards.scoring_effect candidate",
            },
            candidate_fields={},
            payload_fields=(
                "verification_status",
                "adjudication_status",
                "notes",
                "meta",
                "aggravating_factors",
                "case_classification",
                "mitigating_factors",
                "mitigation_flag",
                "reversal_or_rehabilitation",
                "risk_status",
                "trigger_family",
                "trigger_terms",
                "upper_bound_flag",
            ),
            reference_risk_fields={
                "source_id": "source_id is not passage_id; resolve source/passages before evd_src_links",
                "linked_source_ids": "do not write FK until source documents/passages are resolved",
                "linked_cluster_ids": "do not write FK until clusters are resolved",
                "cross_item_split_signals": "requires adjacent-item review before any relationship write",
                "cluster_candidate_id": "candidate cluster code requires resolved cluster review before relationship write",
                "object_anchor": "anchor name requires later anchor resolver review",
            },
            range_filter_fields={**query_range, **person_range},
            deferred_relationships={
                "evd_src_links": "requires resolved evd_cards.code plus reviewed passage span",
            },
        ),
        "data/evidence_clusters.jsonl": JsonlFileMapping(
            source_file="data/evidence_clusters.jsonl",
            target_tables=("clusters", "cluster_evd"),
            code_field="cluster_id",
            required_fields=("cluster_id",),
            direct_fields={
                "cluster_id": "clusters.code",
                "summary": "clusters.summary",
                "status": "clusters.status candidate",
                "adjudication_status": "clusters.adjudication_status candidate",
                "candidate_strength": "clusters.candidate_strength candidate",
                "polarity": "clusters.polarity candidate",
            },
            candidate_fields={"cluster_type": ("clusters.cluster_type",)},
            payload_fields=("notes", "note", "meta", "five_axis_assessment", "upper_probe"),
            reference_risk_fields={
                "linked_evidence_ids": "cluster_evd requires resolved evidence card codes",
            },
            range_filter_fields={**query_range, **person_range},
            deferred_relationships={
                "cluster_evd": "write only after linked_evidence_ids resolve to evd_cards.code",
            },
        ),
        "data/thematic_anchors.jsonl": anchor_mapping("data/thematic_anchors.jsonl", anchor_block),
        "data/thematic_anchor_objects.jsonl": anchor_mapping("data/thematic_anchor_objects.jsonl", anchor_block),
        "data/thematic_anchor_events.jsonl": anchor_mapping("data/thematic_anchor_events.jsonl", anchor_block),
        "data/thematic_anchor_mechanisms.jsonl": anchor_mapping(
            "data/thematic_anchor_mechanisms.jsonl", anchor_block
        ),
    }


def anchor_mapping(source_file: str, blocked_reason: str) -> JsonlFileMapping:
    return JsonlFileMapping(
        source_file=source_file,
        target_tables=("anchors_candidate", "anchor_links_candidate"),
        code_field="anchor_id",
        required_fields=("anchor_id",),
        direct_fields={},
        candidate_fields={
            "anchor_id": ("anchors.code",),
            "anchor_kind": ("anchors.kind",),
            "object_type": ("anchors.object_type",),
            "object_name": ("anchors.object_name",),
            "object_level": ("anchors.object_level",),
            "review_status": ("anchors.review_status",),
        },
        payload_fields=(
            "cross_item_risks",
            "usable_for",
            "notes",
            "note",
            "meta",
            "anchor_role",
            "anchor_scope",
            "consensus_level",
            "source_batch",
            "anchor_summary",
            "comparative_value",
            "theme",
        ),
        reference_risk_fields={
            "linked_persons": "anchor links require resolved person codes",
            "linked_evidence_ids": "anchor links require resolved evidence card codes",
            "linked_cluster_ids": "anchor links require resolved cluster codes",
            "persons": "person names require resolved person codes",
        },
        range_filter_fields={
            "item": "range/filter only; anchor does not prove evidence by itself",
            "subitem": "range/filter only; anchor does not prove evidence by itself",
        },
        deferred_relationships={
            "anchors": "define real PostgreSQL target schema in a later PR",
            "anchor_links": "define link semantics in a later PR",
        },
        staging_only=True,
        blocked_reason=blocked_reason,
    )


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = CANONICAL_JSONL_FILES,
) -> dict[str, Any]:
    mappings = build_mappings()
    files_seen: list[str] = []
    files_missing: list[str] = []
    unmapped_files: list[str] = []
    unknown_fields_by_file: dict[str, list[str]] = {}
    missing_required_fields_by_file: dict[str, dict[str, list[int]]] = {}
    duplicate_codes_by_file: dict[str, dict[str, list[int]]] = {}
    invalid_json_by_file: dict[str, dict[str, str]] = {}
    rows_by_file: dict[str, int] = {}
    dynamic_reference_risks: dict[str, set[str]] = {}

    for relative in relative_files:
        display_path = relative.replace("\\", "/")
        mapping = mappings.get(display_path)
        if mapping is None:
            unmapped_files.append(display_path)
        path = source_root / relative
        if not path.exists():
            files_missing.append(display_path)
            continue

        files_seen.append(display_path)
        if mapping is None:
            continue

        code_lines: dict[str, list[int]] = {}
        seen_unknown_fields: set[str] = set()
        rows = 0
        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            rows += 1
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                invalid_json_by_file.setdefault(display_path, {})[str(line_no)] = exc.msg
                continue
            if not isinstance(payload, dict):
                invalid_json_by_file.setdefault(display_path, {})[str(line_no)] = "JSON payload must be an object"
                continue

            missing = [field for field in mapping.required_fields if not payload.get(field)]
            if missing:
                by_field = missing_required_fields_by_file.setdefault(display_path, {})
                for field in missing:
                    by_field.setdefault(field, []).append(line_no)

            if mapping.code_field:
                code = str(payload.get(mapping.code_field) or "").strip()
                if code:
                    code_lines.setdefault(code, []).append(line_no)

            for field in payload:
                if field in mapping.known_fields():
                    continue
                if is_reference_risk_field(field):
                    dynamic_reference_risks.setdefault(display_path, set()).add(sanitize_report_field(field))
                    continue
                seen_unknown_fields.add(sanitize_report_field(field))

        rows_by_file[display_path] = rows
        unknown = sorted(seen_unknown_fields)
        if unknown:
            unknown_fields_by_file[display_path] = unknown
        duplicates = {code: lines for code, lines in code_lines.items() if len(lines) > 1}
        if duplicates:
            duplicate_codes_by_file[display_path] = duplicates

    report = {
        "mode": "contract-report",
        "files_seen": files_seen,
        "files_missing": files_missing,
        "mapping_version": MAPPING_VERSION,
        "files": {path: mappings[path].as_report() for path in CANONICAL_JSONL_FILES},
        "unmapped_files": sorted(set(unmapped_files)),
        "unknown_fields_by_file": unknown_fields_by_file,
        "missing_required_fields_by_file": missing_required_fields_by_file,
        "duplicate_codes_by_file": duplicate_codes_by_file,
        "invalid_json_by_file": invalid_json_by_file,
        "rows_by_file": rows_by_file,
        "reference_risk_summary": build_reference_risk_summary(mappings, dynamic_reference_risks),
        "staging_only_files": sorted(path for path, mapping in mappings.items() if mapping.staging_only),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def is_reference_risk_field(field: str) -> bool:
    lowered = field.lower()
    return (
        lowered == "source_id"
        or lowered.startswith("linked_")
        or lowered.endswith("_ids")
        or lowered.startswith("cross_item")
    )


def build_reference_risk_summary(
    mappings: Mapping[str, JsonlFileMapping],
    dynamic_reference_risks: Mapping[str, set[str]],
) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {}
    for path, mapping in mappings.items():
        fields = {sanitize_report_field(field) for field in mapping.reference_risk_fields}
        fields.update(dynamic_reference_risks.get(path, set()))
        if fields:
            summary[path] = sorted(fields)
    return summary


def sanitize_report_field(field: str) -> str:
    lowered = field.lower()
    if any(term in lowered for term in BLOCKED_REPORT_TERMS):
        return "[blocked-report-field]"
    return field


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for term in BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report JSONL to PostgreSQL staging/target mapping rules.")
    parser.add_argument("--contract-report", action="store_true", help="print the mapping contract report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root or fixture root")
    args = parser.parse_args(argv)

    sys.stdout.write(report_as_json(build_contract_report(source_root=args.source_root)))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
