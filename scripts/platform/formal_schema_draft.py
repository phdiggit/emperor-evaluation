from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping, Sequence


DRAFT_VERSION = "formal-target-schema-draft-v1"
SOURCE_OF_TRUTH = "canonical JSONL remains source-of-truth; this draft does not switch the write source"
PHASE_1_BASE_TABLES = (
    "imports",
    "import_rows",
    "query_profiles",
    "search_tasks",
    "src_hosts",
    "src_docs",
    "doc_revs",
    "passages",
    "evd_cards",
    "clusters",
    "anchors",
)
PHASE_2_RELATIONSHIP_TABLES = (
    "search_hits",
    "cand_matches",
    "evd_src_links",
    "cluster_evd",
    "anchor_links",
)
PHASE_3_DOWNSTREAM_TABLES = (
    "review_items",
    "adjudication_tables",
    "metric_records",
    "metric_releases",
)
GATE_FIELDS = (
    "contract_report_green",
    "prototype_smoke_green",
    "apply_smoke_required",
    "resolver_gate_required",
    "manual_review_gate_required",
    "seed_gate_required",
    "cutover_gate_required",
    "phase_1_allowed",
)
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


def _base_spec(
    table_name: str,
    purpose: str,
    source_jsonl_files: Sequence[str],
    prototype_tool: str,
    key_columns: Sequence[str],
    payload_columns: Sequence[str],
) -> dict[str, Any]:
    return {
        "table_name": table_name,
        "phase": "phase_1_base",
        "purpose": purpose,
        "source_jsonl_files": list(source_jsonl_files),
        "prototype_tool": prototype_tool,
        "key_columns": list(key_columns),
        "payload_columns": list(payload_columns),
        "relationship_columns": [],
        "write_allowed_in_phase_1": True,
        "requires_resolver_output": False,
        "manual_review_gate_required": False,
        "formal_ddl_ready": True,
        "blocked_reason": None,
    }


def _relationship_spec(
    table_name: str,
    purpose: str,
    source_jsonl_files: Sequence[str],
    prototype_tool: str,
    key_columns: Sequence[str],
    relationship_columns: Sequence[str],
) -> dict[str, Any]:
    return {
        "table_name": table_name,
        "phase": "phase_2_relationship",
        "purpose": purpose,
        "source_jsonl_files": list(source_jsonl_files),
        "prototype_tool": prototype_tool,
        "key_columns": list(key_columns),
        "payload_columns": ["resolver_trace", "payload"],
        "relationship_columns": list(relationship_columns),
        "write_allowed_in_phase_1": False,
        "requires_resolver_output": True,
        "manual_review_gate_required": True,
        "formal_ddl_ready": False,
        "blocked_reason": "blocked_in_phase_1_until_resolver_and_manual_review_gates_are_green",
    }


def _downstream_spec(table_name: str, purpose: str) -> dict[str, Any]:
    return {
        "table_name": table_name,
        "phase": "phase_3_downstream",
        "purpose": purpose,
        "source_jsonl_files": [],
        "prototype_tool": "future_downstream_release_contract",
        "key_columns": ["id"],
        "payload_columns": ["payload", "created_at"],
        "relationship_columns": [],
        "write_allowed_in_phase_1": False,
        "requires_resolver_output": True,
        "manual_review_gate_required": True,
        "formal_ddl_ready": False,
        "blocked_reason": "deferred_until_platform_cutover_and_release_contracts_are_accepted",
    }


def table_specs() -> list[dict[str, Any]]:
    phase_1 = [
        _base_spec(
            "imports",
            "import job header and source batch trace",
            ["data/imports.jsonl"],
            "jsonl_staging_mapper",
            ["import_id"],
            ["source_batch", "status", "created_at", "payload"],
        ),
        _base_spec(
            "import_rows",
            "raw canonical JSONL row envelope for staging",
            ["data/*.jsonl"],
            "jsonl_staging_mapper",
            ["import_id", "row_number"],
            ["source_file", "source_batch", "raw_payload", "row_status"],
        ),
        _base_spec(
            "query_profiles",
            "query/search profile base rows",
            ["data/query_profiles.jsonl"],
            "jsonl_query_search_target_mapper",
            ["query_profile_id"],
            ["person_id", "topic", "query_terms", "payload"],
        ),
        _base_spec(
            "search_tasks",
            "search task base rows without result relationships",
            ["data/search_tasks.jsonl"],
            "jsonl_query_search_target_mapper",
            ["search_task_id"],
            ["query_profile_id", "task_status", "search_provider", "payload"],
        ),
        _base_spec(
            "src_hosts",
            "source host base rows",
            ["data/source_documents.jsonl"],
            "jsonl_sources_target_mapper",
            ["src_host_id"],
            ["host_name", "host_type", "source_url", "payload"],
        ),
        _base_spec(
            "src_docs",
            "source document base rows",
            ["data/source_documents.jsonl"],
            "jsonl_sources_target_mapper",
            ["src_doc_id"],
            ["src_host_id", "source_id", "title", "source_url", "payload"],
        ),
        _base_spec(
            "doc_revs",
            "source document revision and retrieval metadata",
            ["data/source_documents.jsonl"],
            "jsonl_sources_target_mapper",
            ["doc_rev_id"],
            ["src_doc_id", "retrieved_at", "content_hash", "payload"],
        ),
        _base_spec(
            "passages",
            "candidate and reviewed-status aware source passage rows",
            ["data/source_passages.jsonl"],
            "jsonl_sources_target_mapper",
            ["passage_id"],
            ["src_doc_id", "quote_short", "passage_text", "review_status", "payload"],
        ),
        _base_spec(
            "evd_cards",
            "evidence card base rows without relationship writes",
            ["data/evidence_cards.jsonl"],
            "jsonl_evidence_cards_target_mapper",
            ["evd_card_id"],
            ["person_id", "item_id", "polarity", "summary", "payload"],
        ),
        _base_spec(
            "clusters",
            "evidence cluster base rows without cluster membership writes",
            ["data/evidence_clusters.jsonl"],
            "jsonl_evidence_clusters_resolver",
            ["cluster_id"],
            ["cluster_label", "cluster_type", "review_status", "payload"],
        ),
        _base_spec(
            "anchors",
            "anchor base rows without anchor link writes",
            [
                "data/thematic_anchors.jsonl",
                "data/thematic_anchor_objects.jsonl",
                "data/thematic_anchor_events.jsonl",
                "data/thematic_anchor_mechanisms.jsonl",
            ],
            "jsonl_anchors_target_mapper",
            ["anchor_id"],
            ["anchor_code", "anchor_type", "label", "review_status", "payload"],
        ),
    ]
    phase_2 = [
        _relationship_spec(
            "search_hits",
            "search task to candidate hit relationships",
            ["data/search_tasks.jsonl"],
            "jsonl_query_search_target_mapper",
            ["search_hit_id"],
            ["search_task_id", "src_doc_id", "hit_url"],
        ),
        _relationship_spec(
            "cand_matches",
            "candidate matching rows between query/search and source candidates",
            ["data/query_profiles.jsonl", "data/source_passages.jsonl"],
            "jsonl_staging_resolver_contract",
            ["cand_match_id"],
            ["query_profile_id", "passage_id", "match_status"],
        ),
        _relationship_spec(
            "evd_src_links",
            "evidence card to source passage links after resolver review",
            ["data/evidence_cards.jsonl", "data/source_passages.jsonl"],
            "jsonl_evidence_cards_target_mapper",
            ["evd_src_link_id"],
            ["evd_card_id", "passage_id", "link_role"],
        ),
        _relationship_spec(
            "cluster_evd",
            "cluster to evidence card membership after resolver review",
            ["data/evidence_clusters.jsonl", "data/evidence_cards.jsonl"],
            "jsonl_evidence_clusters_resolver",
            ["cluster_evd_id"],
            ["cluster_id", "evd_card_id", "membership_status"],
        ),
        _relationship_spec(
            "anchor_links",
            "anchor to target links after anchor resolver review",
            ["data/thematic_anchors.jsonl", "data/evidence_cards.jsonl", "data/evidence_clusters.jsonl"],
            "anchors_resolver_contract",
            ["anchor_link_id"],
            ["anchor_id", "target_domain", "target_id", "link_role"],
        ),
    ]
    phase_3 = [
        _downstream_spec("review_items", "manual review queue and lifecycle items after relationship gates"),
        _downstream_spec("adjudication_tables", "future adjudication-family target tables as a safe placeholder"),
        _downstream_spec("metric_records", "future metric record targets as a safe placeholder"),
        _downstream_spec("metric_releases", "future metric release targets as a safe placeholder"),
    ]
    return [*phase_1, *phase_2, *phase_3]


def schema_diff_from_prototypes() -> list[dict[str, Any]]:
    return [
        {
            "diff_type": "kept",
            "prototype_relaxed_tables": ["imports", "import_rows", "query_profiles", "search_tasks"],
            "formal_schema_draft_tables": ["imports", "import_rows", "query_profiles", "search_tasks"],
            "note": "core import and query/search base surfaces stay aligned with prototype contracts",
        },
        {
            "diff_type": "renamed",
            "prototype_relaxed_tables": ["source_documents", "source_passages", "evidence_cards", "evidence_source_links"],
            "formal_schema_draft_tables": ["src_docs", "passages", "evd_cards", "evd_src_links"],
            "note": "formal physical names use shorter target table names while preserving compatibility intent",
        },
        {
            "diff_type": "split",
            "prototype_relaxed_tables": ["sources"],
            "formal_schema_draft_tables": ["src_hosts", "src_docs", "doc_revs", "passages"],
            "note": "source mapper output is split into host, document, revision, and passage surfaces",
        },
        {
            "diff_type": "deferred",
            "prototype_relaxed_tables": ["review_items", "adjudication_outputs", "metric_outputs"],
            "formal_schema_draft_tables": ["review_items", "adjudication_tables", "metric_records", "metric_releases"],
            "note": "downstream tables remain phase 3 placeholders and are not phase 1 DDL targets",
        },
        {
            "diff_type": "blocked",
            "prototype_relaxed_tables": ["search_hits", "cand_matches", "evidence_source_links", "cluster_evidence", "anchor_links"],
            "formal_schema_draft_tables": ["search_hits", "cand_matches", "evd_src_links", "cluster_evd", "anchor_links"],
            "note": "relationship writes are blocked until resolver output and manual review gates are green",
        },
        {
            "diff_type": "new_in_formal_draft",
            "prototype_relaxed_tables": [],
            "formal_schema_draft_tables": ["doc_revs", "src_hosts"],
            "note": "formal draft separates revision and host metadata for later DDL review",
        },
    ]


def _gates_for(spec: Mapping[str, Any]) -> dict[str, Any]:
    phase = str(spec["phase"])
    phase_1_allowed = bool(spec["write_allowed_in_phase_1"])
    return {
        "table_name": spec["table_name"],
        "contract_report_green": True,
        "prototype_smoke_green": True,
        "apply_smoke_required": False,
        "resolver_gate_required": bool(spec["requires_resolver_output"]),
        "manual_review_gate_required": bool(spec["manual_review_gate_required"]),
        "seed_gate_required": phase != "phase_1_base",
        "cutover_gate_required": phase == "phase_3_downstream",
        "phase_1_allowed": phase_1_allowed,
    }


def build_contract_report() -> dict[str, Any]:
    specs = table_specs()
    report = {
        "mode": "contract-report",
        "draft_version": DRAFT_VERSION,
        "status": "Proposed",
        "source_of_truth": SOURCE_OF_TRUTH,
        "schema_scope": {
            "proposal_only": True,
            "formal_ddl_rehearsal_input_only": True,
            "production_migration": False,
            "phase_model": ["phase_1_base", "phase_2_relationship", "phase_3_downstream"],
        },
        "phase_1_base_tables": list(PHASE_1_BASE_TABLES),
        "phase_2_relationship_tables": list(PHASE_2_RELATIONSHIP_TABLES),
        "phase_3_downstream_tables": list(PHASE_3_DOWNSTREAM_TABLES),
        "table_specs": specs,
        "schema_diff_from_prototypes": schema_diff_from_prototypes(),
        "table_by_table_gates": [_gates_for(spec) for spec in specs],
        "blocked_tables": [
            {
                "table_name": spec["table_name"],
                "phase": spec["phase"],
                "blocked_reason": spec["blocked_reason"],
            }
            for spec in specs
            if spec["blocked_reason"]
        ],
        "resolver_prerequisites": [
            "staging resolver contract remains green",
            "relationship resolver output must use reviewed target identifiers",
            "manual review gate must be explicit before relationship writes",
            "anchor links require anchors resolver contract output",
            "cluster membership requires evidence clusters resolver output",
            "source links require evidence card to passage resolver output",
        ],
        "migration_preconditions": [
            "all contract reports green",
            "schema diff reviewed",
            "table-by-table gates reviewed",
            "isolated formal DDL rehearsal accepted in a later PR",
            "canonical JSONL remains write source",
            "no production target write path enabled",
        ],
        "non_goals": [
            "does not modify db/schema.sql",
            "does not modify db/postgres/001_init.sql",
            "does not execute DDL or migration",
            "does not connect to PostgreSQL",
            "does not read .env or DSN values",
            "does not switch the JSONL write source",
            "does not generate seed artifacts",
            "does not write production target business tables",
            "does not generate business conclusions",
        ],
        "strict_boundaries": [
            "does_not_read_dotenv",
            "does_not_read_dsn",
            "does_not_connect_to_database",
            "does_not_execute_ddl",
            "does_not_execute_migration",
            "does_not_modify_canonical_jsonl",
            "does_not_modify_db_schema_sql",
            "does_not_modify_postgres_init_sql",
            "does_not_write_target_business_tables",
            "does_not_switch_jsonl_write_source",
            "does_not_generate_seed_artifact",
        ],
        "future_work": [
            "PR_259_isolated_formal_ddl_rehearsal",
            "generate isolated rehearsal SQL outside production schema files",
            "review relationship resolver outputs before relationship table writes",
            "review downstream release contracts in a separate PR",
        ],
        "limitations": [
            "offline_static_schema_draft_only",
            "no_real_sql_diff",
            "no_database_connection",
            "no_data_or_archive_reads",
            "no_generated_seed_artifact",
            "phase_2_relationship_tables_blocked_in_phase_1",
            "phase_3_downstream_tables_blocked_in_phase_1",
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

    parser = argparse.ArgumentParser(description="Report the offline formal target schema draft contract.")
    parser.add_argument("--contract-report", action="store_true", help="print the formal schema draft report")
    args = parser.parse_args(argv)
    if not args.contract_report:
        parser.error("--contract-report is required")

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
