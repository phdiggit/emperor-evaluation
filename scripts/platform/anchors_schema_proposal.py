from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL_VERSION = "anchors-schema-proposal-v1"
INPUT_JSONL_SOURCES = (
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
    "data/query_profiles.jsonl",
    "data/evidence_cards.jsonl",
    "data/evidence_clusters.jsonl",
)
ANCHOR_SOURCE_FILES = (
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
)
ANCHOR_REFERENCE_FIELDS = (
    "object_anchor",
    "object_anchors",
    "thematic_anchor_targets",
    "linked_evidence_ids",
    "linked_cluster_ids",
)
RESOLVER_STATUS_VALUES = (
    "unresolved_candidate",
    "manual_review_required",
    "resolver_ready",
    "blocked_pending_schema",
)
FIRST_STAGE_RESOLVER_STATUS_VALUES = (
    "unresolved_candidate",
    "manual_review_required",
    "blocked_pending_schema",
)
TARGET_DOMAINS = (
    "person",
    "evidence_card",
    "evidence_cluster",
    "source_document",
    "source_passage_candidate",
    "query_profile",
    "search_task",
    "subitem",
)
PROPOSED_COLUMNS_BY_TABLE = {
    "anchors": (
        "id",
        "code",
        "anchor_type",
        "label",
        "status",
        "payload",
        "created_at",
        "updated_at",
    ),
    "anchor_links": (
        "id",
        "anchor_code",
        "target_domain",
        "target_code",
        "link_role",
        "resolver_status",
        "payload",
        "created_at",
    ),
}
PROPOSED_COLUMN_DETAILS = {
    "anchors": {
        "id": "BIGSERIAL / identity",
        "code": "TEXT UNIQUE NOT NULL",
        "anchor_type": "TEXT NOT NULL",
        "label": "TEXT",
        "status": "TEXT",
        "payload": "JSONB NOT NULL DEFAULT '{}'",
        "created_at": "TIMESTAMPTZ",
        "updated_at": "TIMESTAMPTZ",
    },
    "anchor_links": {
        "id": "BIGSERIAL / identity",
        "anchor_code": "TEXT NOT NULL",
        "target_domain": "TEXT NOT NULL",
        "target_code": "TEXT NOT NULL",
        "link_role": "TEXT",
        "resolver_status": "TEXT NOT NULL",
        "payload": "JSONB NOT NULL DEFAULT '{}'",
        "created_at": "TIMESTAMPTZ",
    },
}
ANCHOR_TYPE_VALUES = (
    "theme",
    "object",
    "event",
    "mechanism",
    "person_object",
    "policy_object",
)
BLOCKED_RELATIONSHIP_WRITES = (
    "anchor_links_write",
    "evidence_relationship_write",
    "cluster_relationship_write",
    "source_relationship_write",
    "person_subitem_identifier_write",
    "downstream_release_write",
    "adjudication_write",
)
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


def build_contract_report() -> dict[str, Any]:
    report = {
        "mode": "contract-report",
        "proposal_version": PROPOSAL_VERSION,
        "status": "Proposed",
        "proposed_tables": ["anchors", "anchor_links"],
        "proposed_columns_by_table": {
            table: list(columns) for table, columns in PROPOSED_COLUMNS_BY_TABLE.items()
        },
        "proposed_column_details": PROPOSED_COLUMN_DETAILS,
        "anchor_type_values": list(ANCHOR_TYPE_VALUES),
        "input_jsonl_sources": list(INPUT_JSONL_SOURCES),
        "anchor_source_files": list(ANCHOR_SOURCE_FILES),
        "anchor_reference_fields": list(ANCHOR_REFERENCE_FIELDS),
        "resolver_status_values": list(RESOLVER_STATUS_VALUES),
        "first_stage_resolver_status_values": list(FIRST_STAGE_RESOLVER_STATUS_VALUES),
        "target_domains": list(TARGET_DOMAINS),
        "blocked_relationship_writes": list(BLOCKED_RELATIONSHIP_WRITES),
        "migration_boundary": [
            "proposal_only_no_postgresql_ddl",
            "no_canonical_jsonl_migration",
            "no_target_business_table_writes",
            "resolver_output_required_before_relationship_writes",
        ],
        "relationship_boundary": [
            "anchor_name_or_code_is_not_anchor_id",
            "object_anchor_is_resolver_input_only",
            "object_anchors_are_resolver_input_only",
            "thematic_anchor_targets_are_resolver_input_only",
            "linked_evidence_and_cluster_inputs_do_not_route_through_anchors",
        ],
        "future_work": [
            "anchors_resolver_contract",
            "anchor_terms_review",
            "postgresql_ddl_after_contract_acceptance",
            "target_mapper_after_resolver_output",
        ],
        "limitations": [
            "offline_static_schema_proposal",
            "does_not_read_env_files",
            "does_not_connect_to_postgresql",
            "does_not_access_network",
            "does_not_read_batch_or_archive_data",
            "does_not_write_release_metric_downstream_tables",
        ],
    }
    assert_report_has_no_blocked_terms(report)
    return report


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

    parser = argparse.ArgumentParser(description="Report the offline anchors schema proposal contract.")
    parser.add_argument("--contract-report", action="store_true", help="print the offline anchors schema proposal")
    parser.parse_args(argv)

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
