# ADR: PostgreSQL formal migration plan

## Status

Proposed.

This ADR is a proposal only. It is not accepted, finalized, applied to PostgreSQL, or treated as production DDL.

## Context

The platform chain has reached an offline contract checkpoint for canonical JSONL imports, staging mapping, unknown-field triage, staging resolver behavior, query/search targets, source targets, evidence card targets, evidence cluster resolver preparation, anchors schema proposal, anchors resolver behavior, anchors target mapping, and the smoke/checkpoint matrix.

The next step is to describe when a formal PostgreSQL migration would be allowed. This ADR records gates and stages. It does not change `db/schema.sql`, `db/postgres/001_init.sql`, canonical JSONL, or any target table.

## Decision

Use a staged formal migration process:

- keep canonical JSONL as the active source until a separate accepted migration explicitly changes that boundary;
- require every contract report and platform smoke gate to be green before drafting formal DDL;
- introduce relationship tables only after resolver outputs have manual-review gates;
- keep release and adjudication surfaces outside the first formal schema scope.

This PR only records the plan and the machine-readable readiness report.

## Formal Schema Scope

The formal schema scope is staged as follows:

- Phase 1: source/query/evidence/cluster/anchor base tables.
- Phase 2: relationship tables after resolver outputs.
- Phase 3: cutover / seed / read path switch.
- Phase 4: downstream release / adjudication tables, later only.

No DDL is included in this ADR.

## Migration Preconditions

A separate formal migration cannot proceed until all of these gates are complete:

- all contract reports green;
- apply smoke matrix green with a live primary PostgreSQL DSN;
- schema diff reviewed;
- rollback plan accepted;
- seed strategy accepted;
- read path dual-run accepted;
- manual review gates for relationship tables accepted.

## Migration Stages

- Stage 0: keep proposal-only documentation and offline reports in sync.
- Stage 1: draft isolated formal DDL for review without applying it to the production schema.
- Stage 2: run contract reports, schema diff review, and smoke checks against an isolated environment.
- Stage 3: prepare staging seed artifacts from canonical JSONL only.
- Stage 4: dual-run read validation with JSONL still authoritative.
- Stage 5: switch read behavior only behind explicit configuration after separate approval.
- Stage 6: defer write-source switch until a later approved migration.

## Validation Gates

- The production-readiness contract report must match this ADR set.
- The platform checkpoint report must include the completed chain.
- The prototype smoke contract matrix must remain green offline.
- Anchor resolver and target mapper reports must remain green.
- JSONL staging, triage, resolver, query/search, source, evidence card, and evidence cluster reports must remain green.
- `docs_tool check`, `agents-check`, `canonical-imports-check`, `validate_all.py`, `git diff --check`, and scope-check must pass before PR publication.

## Rejected Alternatives

- Modify `db/postgres/001_init.sql` now: rejected because this PR is proposal-only.
- Treat relaxed prototype targets as formal schema: rejected because prototypes do not replace reviewed DDL.
- Introduce relationship tables before resolver review gates: rejected because unresolved links must not become formal relationships.
- Switch read or write paths in this PR: rejected because cutover requires a separate approval.

## Risks

- Prototype target names may drift from future formal DDL if schema review happens too late.
- Relationship tables can appear more mature than the resolver outputs allow.
- Seed artifacts can be mistaken for source data unless the JSONL boundary remains explicit.
- Configuration switches can hide partial cutovers unless dual-run evidence is required.

## Future Work

- Draft a formal schema proposal under a separate PR without editing production schema files.
- Add table-by-table schema diff reporting.
- Define resolver review outputs for relationship tables.
- Define isolated seed artifact checksums and migration report artifacts.
- Define release-table boundaries after base table and read-path gates are complete.
