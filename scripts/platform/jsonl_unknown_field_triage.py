from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import build_staging_rows, load_source_rows
from scripts.platform.jsonl_target_mapping import (
    CANONICAL_JSONL_FILES,
    LIMITATIONS as MAPPING_LIMITATIONS,
    MAPPING_VERSION,
    assert_report_has_no_blocked_terms,
    build_mappings,
    is_reference_risk_field,
)


TRIAGE_VERSION = "jsonl-unknown-field-triage-v1"
LIMITATIONS = (
    "JSONL remains the write source; this report does not migrate JSONL.",
    "The report is offline and does not write PostgreSQL target business tables.",
    "Reference-risk fields require later resolver and human review before relationship writes.",
    "Suspected-deprecated fields are diagnostic only and remain preserved in staging payload data.",
    "Manual-review fields stay in unknown_fields until a later explicit mapping decision.",
)


@dataclass(frozen=True)
class TriageDecision:
    field: str
    category: str
    reason: str
    target_guidance: tuple[str, ...] = ()
    resolver_risk_guidance: str | None = None
    preserve_original_value: bool = True

    def as_report(self, occurrences: Sequence[int]) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "field": self.field,
            "category": self.category,
            "reason": self.reason,
            "occurrence_count": len(occurrences),
            "line_numbers": list(occurrences),
            "preserve_original_value": self.preserve_original_value,
        }
        if self.target_guidance:
            entry["target_guidance"] = list(self.target_guidance)
        if self.resolver_risk_guidance:
            entry["resolver_risk_guidance"] = self.resolver_risk_guidance
        return entry


def mapping(field: str, reason: str, *targets: str) -> TriageDecision:
    return TriageDecision(field=field, category="mapping", reason=reason, target_guidance=targets)


def payload(field: str, reason: str) -> TriageDecision:
    return TriageDecision(field=field, category="payload", reason=reason)


def reference_risk(field: str, reason: str, guidance: str) -> TriageDecision:
    return TriageDecision(
        field=field,
        category="reference_risk",
        reason=reason,
        resolver_risk_guidance=guidance,
    )


def manual_review(field: str, reason: str) -> TriageDecision:
    return TriageDecision(field=field, category="manual_review", reason=reason)


def suspected_deprecated(field: str, reason: str) -> TriageDecision:
    return TriageDecision(field=field, category="suspected_deprecated", reason=reason)


def build_decision_registry() -> dict[str, dict[str, TriageDecision]]:
    registry = {
        "data/query_profiles.jsonl": [
            payload("coverage_policy", "Profile policy text belongs with the profile audit payload."),
            payload("evidence_policy", "Profile policy text belongs with the profile audit payload."),
            payload("negative_dimensions", "Dimension lists are query-profile configuration payload."),
            payload("negative_terms", "Term lists are query-profile configuration payload."),
            payload("note", "Singular note is legacy note payload."),
            payload("positive_dimensions", "Dimension lists are query-profile configuration payload."),
            payload("positive_terms", "Term lists are query-profile configuration payload."),
            payload("retention_policy", "Retention note is profile audit payload."),
            payload("reversal_or_balance_dimensions", "Dimension lists are query-profile configuration payload."),
            payload("reversal_terms", "Term lists are query-profile configuration payload."),
            payload("reverse_search_required_when", "Search trigger notes are profile configuration payload."),
            payload("search_modes", "Mode list is profile configuration payload."),
            payload("source_scopes", "Scope list is profile configuration payload."),
            reference_risk(
                "inherits_from",
                "Parent profile code requires profile resolver review.",
                "Resolve against query_profiles.code before any parent-child relationship write.",
            ),
            reference_risk(
                "object_anchors",
                "Embedded anchor objects require later anchor resolver review.",
                "Keep as reference-risk data until anchor identity and relationship rules exist.",
            ),
            reference_risk(
                "thematic_anchor_targets",
                "Anchor target names require later anchor resolver review.",
                "Keep as reference-risk data until anchor target semantics are defined.",
            ),
            suspected_deprecated("profile_role", "Migration-role marker; keep for audit only."),
            suspected_deprecated("schema_version", "Legacy source marker; keep for audit only."),
            suspected_deprecated("source_batch", "Batch provenance marker; keep for audit only."),
        ],
        "data/search_logs.jsonl": [
            payload("derived_from_dimension", "Search derivation label belongs with task audit payload."),
            payload("expected_source_scope", "Expected source scope belongs with task audit payload."),
            payload("next_action", "Next-action note belongs with task audit payload."),
            payload("note", "Singular note is legacy note payload."),
            payload("polarity", "Search polarity is task context payload, not a relationship."),
            payload("rejection_reason", "Rejection note belongs with task audit payload."),
            payload("result_status", "Result status is task outcome payload."),
            payload("searched_at", "Search date is task audit payload."),
            payload("source_polarity", "Source polarity is task context payload."),
            payload("source_status", "Source status is task context payload."),
            payload("trigger_family", "Trigger label belongs with task audit payload."),
            suspected_deprecated("source_batch", "Batch provenance marker; keep for audit only."),
        ],
        "data/sources.jsonl": [
            payload("author", "Bibliographic metadata belongs with source payload."),
            payload("dynasty", "Bibliographic metadata belongs with source payload."),
            payload("location", "Citation locator belongs with source payload."),
            payload("note", "Singular note is legacy note payload."),
            payload("volume", "Citation volume belongs with source payload."),
        ],
        "data/evidence_cards.jsonl": [
            payload("aggravating_factors", "Factor list belongs with evidence-card audit payload."),
            payload("case_classification", "Case label belongs with evidence-card audit payload."),
            payload("mitigating_factors", "Factor list belongs with evidence-card audit payload."),
            payload("mitigation_flag", "Mitigation marker belongs with evidence-card audit payload."),
            payload("reversal_or_rehabilitation", "Review-balance marker belongs with evidence-card audit payload."),
            payload("risk_status", "Context-risk marker belongs with evidence-card audit payload."),
            payload("trigger_family", "Trigger label belongs with evidence-card audit payload."),
            payload("trigger_terms", "Trigger term list belongs with evidence-card audit payload."),
            reference_risk(
                "cluster_candidate_id",
                "Candidate cluster code requires cluster resolver review.",
                "Resolve against cluster code before any evidence-cluster relationship write.",
            ),
            reference_risk(
                "object_anchor",
                "Anchor name requires later anchor resolver review.",
                "Keep as reference-risk data until anchor identity rules exist.",
            ),
            manual_review("cluster_role", "Relationship role semantics need human placement review."),
            manual_review("evidence_role", "Evidence role semantics need human placement review."),
            suspected_deprecated("upper_bound_flag", "Upper-bound marker is diagnostic only."),
        ],
        "data/evidence_clusters.jsonl": [
            mapping("cluster_type", "Cluster type is a clear cluster candidate field.", "clusters.cluster_type"),
            mapping("status", "Cluster status is a clear cluster candidate field.", "clusters.status"),
            payload("five_axis_assessment", "Assessment object belongs with cluster audit payload."),
            payload("note", "Singular note is legacy note payload."),
            suspected_deprecated("upper_probe", "Upper-probe marker is diagnostic only."),
        ],
        "data/thematic_anchors.jsonl": [
            payload("anchor_summary", "Anchor summary belongs with staging-only anchor payload."),
            payload("comparative_value", "Comparative note belongs with staging-only anchor payload."),
            payload("note", "Singular note is staging-only anchor payload."),
            payload("theme", "Theme label belongs with staging-only anchor payload."),
            reference_risk(
                "persons",
                "Person names require person resolver review.",
                "Resolve person names to person codes before any anchor-person relationship write.",
            ),
        ],
        "data/thematic_anchor_objects.jsonl": anchor_payload_decisions(),
        "data/thematic_anchor_events.jsonl": anchor_payload_decisions(),
        "data/thematic_anchor_mechanisms.jsonl": anchor_payload_decisions(),
    }
    return {source: {decision.field: decision for decision in decisions} for source, decisions in registry.items()}


def anchor_payload_decisions() -> list[TriageDecision]:
    return [
        payload("anchor_role", "Anchor role belongs with staging-only anchor payload."),
        payload("anchor_scope", "Anchor scope belongs with staging-only anchor payload."),
        payload("consensus_level", "Consensus label belongs with staging-only anchor payload."),
        payload("note", "Singular note is staging-only anchor payload."),
        suspected_deprecated("source_batch", "Batch provenance marker; keep for audit only."),
    ]


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = CANONICAL_JSONL_FILES,
) -> dict[str, Any]:
    mappings = build_mappings()
    registry = build_decision_registry()
    source_rows = load_source_rows(source_root=source_root, relative_files=relative_files)
    staging_rows = build_staging_rows(source_rows)
    files_seen = [
        relative.replace("\\", "/")
        for relative in relative_files
        if (source_root / relative).exists()
    ]
    rows_by_file: dict[str, int] = {relative: 0 for relative in files_seen}
    observed: dict[str, dict[str, list[int]]] = {}
    decisions_by_file: dict[str, list[dict[str, Any]]] = {}
    unclassified_fields_by_file: dict[str, list[str]] = {}
    remaining_unknown_fields_by_file: dict[str, list[str]] = {}
    decision_counts = {
        "mapping": 0,
        "payload": 0,
        "reference_risk": 0,
        "manual_review": 0,
        "suspected_deprecated": 0,
    }

    for row in source_rows:
        rows_by_file[row.source_file] = rows_by_file.get(row.source_file, 0) + 1
        mapping_contract = mappings.get(row.source_file)
        known_fields = mapping_contract.known_fields() if mapping_contract else set()
        source_registry = registry.get(row.source_file, {})
        for field in row.payload:
            decision = source_registry.get(field)
            if decision is None and field in known_fields:
                continue
            if decision is None and is_reference_risk_field(field):
                decision = reference_risk(
                    field,
                    "Dynamic reference-style field requires resolver review.",
                    "Keep as reference-risk data until the resolver proves the target row.",
                )
            if decision is None:
                decision = manual_review(field, "No explicit triage decision is registered for this observed field.")
                unclassified_fields_by_file.setdefault(row.source_file, [])
                if field not in unclassified_fields_by_file[row.source_file]:
                    unclassified_fields_by_file[row.source_file].append(field)
            observed.setdefault(row.source_file, {}).setdefault(field, []).append(row.line_no)

    for source_file, fields in observed.items():
        source_registry = registry.get(source_file, {})
        entries = []
        for field in sorted(fields):
            decision = source_registry.get(field)
            if decision is None and is_reference_risk_field(field):
                decision = reference_risk(
                    field,
                    "Dynamic reference-style field requires resolver review.",
                    "Keep as reference-risk data until the resolver proves the target row.",
                )
            if decision is None:
                decision = manual_review(field, "No explicit triage decision is registered for this observed field.")
            entries.append(decision.as_report(fields[field]))
            decision_counts[decision.category] += 1
        decisions_by_file[source_file] = entries

    for row in staging_rows:
        if row.unknown_fields:
            remaining = remaining_unknown_fields_by_file.setdefault(row.source_file, [])
            for field in row.unknown_fields:
                if field not in remaining:
                    remaining.append(field)

    report = {
        "mode": "contract-report",
        "triage_version": TRIAGE_VERSION,
        "mapping_version": MAPPING_VERSION,
        "source_files": files_seen,
        "rows_by_file": rows_by_file,
        "observed_unknown_fields_by_file": {
            source_file: sorted(fields) for source_file, fields in sorted(observed.items())
        },
        "decisions_by_file": decisions_by_file,
        "decision_counts": decision_counts,
        "unclassified_fields_by_file": {
            source_file: sorted(fields) for source_file, fields in sorted(unclassified_fields_by_file.items())
        },
        "remaining_unknown_fields_by_file": {
            source_file: sorted(fields) for source_file, fields in sorted(remaining_unknown_fields_by_file.items())
        },
        "limitations": list(LIMITATIONS) + list(MAPPING_LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Classify canonical JSONL staging unknown fields offline.")
    parser.add_argument("--contract-report", action="store_true", help="print the offline triage contract report")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root or fixture root")
    args = parser.parse_args(argv)

    report = build_contract_report(source_root=args.source_root)
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
