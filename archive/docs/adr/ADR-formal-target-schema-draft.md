# ADR: formal target schema draft

## Status

Proposed.

This ADR is a formal schema draft proposal only. It is not applied to PostgreSQL and is not treated as a production migration.

## Context

The platform chain has already produced offline contract reports and mapper prototypes for canonical JSONL import rows, staging rows, unknown-field triage, staging resolver output, query/search targets, source targets, evidence card targets, evidence cluster preparation, anchors, platform smoke checks, and production-readiness proposals.

Those pieces now need one reviewable formal target schema draft that can be used as input for a later isolated DDL rehearsal. This ADR consolidates the prototype outputs into phase-based target table candidates, table-by-table readiness gates, and schema differences from the relaxed prototype surfaces.

## Decision

This PR does not modify `db/postgres/001_init.sql`.

This PR does not modify `db/schema.sql`.

This PR does not execute DDL.

This PR does not connect to PostgreSQL.

This PR does not read `.env` or DSN values.

This PR does not switch JSONL source-of-truth.

The formal schema draft is only an input to a later isolated DDL rehearsal. Canonical JSONL remains the source-of-truth unless a separate migration and cutover plan changes that boundary.

## Draft Schema Scope

The draft uses three phases:

- Phase 1 base tables can be considered for later isolated DDL rehearsal.
- Phase 2 relationship tables are candidates, but blocked in phase 1 until resolver output and manual review gates are green.
- Phase 3 downstream tables are placeholders for later release and adjudication-family contracts, not phase 1 DDL targets.

The machine-readable contract report is produced by:

```bash
python scripts/platform/formal_schema_draft.py --contract-report
```

The report includes schema scope, table specs, schema diff from prototypes, table-by-table gates, blocked tables, resolver prerequisites, migration preconditions, non-goals, strict boundaries, future work, and limitations.

## Phase 1 Base Tables

Phase 1 base table candidates:

- `imports`
- `import_rows`
- `query_profiles`
- `search_tasks`
- `src_hosts`
- `src_docs`
- `doc_revs`
- `passages`
- `evd_cards`
- `clusters`
- `anchors`

`passages` remains candidate / reviewed-status aware. `clusters` keeps only base cluster rows in phase 1, without `cluster_evd` writes. `anchors` keeps only base anchor rows in phase 1, without `anchor_links` writes.

## Phase 2 Relationship Tables

Phase 2 relationship table candidates:

- `search_hits`
- `cand_matches`
- `evd_src_links`
- `cluster_evd`
- `anchor_links`

All phase 2 candidates must stay blocked in phase 1. They require resolver output, manual review gates, and separate approval before relationship writes are allowed.

## Phase 3 Downstream Tables

Phase 3 downstream candidates use safe placeholder names in the machine-readable report:

- `review_items`
- `adjudication_tables`
- `metric_records`
- `metric_releases`

These tables are not phase 1 DDL targets. They remain deferred until release, adjudication-family, and cutover contracts are reviewed in a later PR.

## Table-by-Table Gates

Every table in the formal schema draft report must declare:

- `contract_report_green`
- `prototype_smoke_green`
- `apply_smoke_required`
- `resolver_gate_required`
- `manual_review_gate_required`
- `seed_gate_required`
- `cutover_gate_required`
- `phase_1_allowed`

Phase 1 base tables may be allowed for later isolated DDL rehearsal. Phase 2 relationship tables and phase 3 downstream tables must not be allowed in phase 1.

## Schema Diff from Prototypes

The report compares relaxed prototype surfaces with the formal draft table names using static categories only:

- `kept`
- `renamed`
- `split`
- `deferred`
- `blocked`
- `new_in_formal_draft`

This ADR does not run a real SQL diff, does not read production schema files as an input, and does not connect to a database.

## Rejected Alternatives

- Modify production SQL schema now: rejected because this PR is proposal-only.
- Execute PostgreSQL DDL now: rejected because schema progression is controlled by explicit Epic / Milestone / Gate approval.
- Treat relationship fields as direct writes: rejected because resolver output and manual review gates are required.
- Put relationship tables into phase 1: rejected because `evd_src_links`, `cluster_evd`, and `anchor_links` are blocked until resolver gates are green.
- Switch JSONL write source now: rejected because canonical JSONL remains source-of-truth.
- Generate seed artifacts now: rejected because seed strategy belongs to a later migration path.

## Risks

- Prototype names and formal names may drift unless the schema diff report stays reviewed with each mapper contract.
- Relationship tables may look ready before resolver output is reviewed; table gates must keep them blocked.
- Downstream placeholders can be overread as migration scope; they must remain phase 3 only.
- Hand-editing production schema files would bypass the isolated rehearsal plan; scope checks must forbid those paths.

## Future Work

- Isolated rehearsal SQL belongs to the schema rehearsal gate, not to a fixed future PR number.
- A later review can decide exact PostgreSQL column types after this draft is promoted beyond proposal status.
- Relationship resolver output can be mapped only after manual review gates are green.
- Downstream release and adjudication-family tables need a separate contract before any migration work.
