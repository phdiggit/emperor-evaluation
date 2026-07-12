# ADR: Production Schema Live-Apply Execution PR Scaffold

## Status

Proposed / Production schema live-apply execution PR scaffold only

## Context

- PR #281 has entered the schema-changing file-update chain and modified formal schema files.
- PR #282 added the production schema live-apply entrypoint guard.
- The user has authorized continuing toward data migration work, but this PR remains live-apply execution PR scaffold only.
- This PR is not the live apply PR.
- This PR does not execute SQL, connect to PostgreSQL, read DSN material, execute seed data, write public schema, or record human sign-offs.

## Decision

- Add a scaffold contract for a future production schema live-apply execution PR.
- Render a blocked-by-default future PR body template.
- Render an operator evidence manifest template.
- Render rollback / restore placeholder material.
- Render future execution command checklist placeholder material without a runnable database command.
- Render schema source fingerprints for `db/schema.sql` and `db/postgres/001_init.sql`.
- Keep schema files read-only and metadata-only in this PR.

## Required Flags

```text
live_apply_execution_pr_scaffold_only=true
schema_files_modified=false
schema_files_read_only=true
schema_files_byte_identical_required=true
production_schema_hashes_rendered=true
live_apply_pr_approved=false
live_apply_executed=false
sql_executed=false
production_db_connected=false
production_dsn_read=false
production_seed_executed=false
seed_apply_executed=false
operator_evidence_recorded=false
human_signoffs_recorded=false
ready_for_live_apply=false
ready_for_production_migration=false
future_live_apply_execution_pr_required=true
future_seed_apply_pr_required=true
```

## Non-Goals

- No SQL execution.
- No DB connection.
- No DSN access.
- No production seed execution.
- No seed apply execution.
- No live apply execution.
- No public schema write.
- No sign-off forgery.
- No live apply approval record.
- No production migration completion record.
- No seed apply completion record.

## Scaffold Outputs

- `--contract-report` prints the scaffold contract.
- `--execution-scaffold-report` prints the machine-readable scaffold gate report.
- `--render-execution-request-json` prints the non-executing request JSON.
- `--render-future-pr-body-template` prints a blocked-by-default future PR body template.
- `--render-operator-evidence-template-md` prints an operator evidence manifest template.
- `--lint-execution-scaffold-report` validates scaffold flags and blocked content.
- `--adr-check` validates this ADR.

## Future Work Boundary

- Future live apply execution PR remains required.
- Future seed apply PR remains required.
- The future live apply execution PR must be a separate PR with explicit approval evidence.
- The future seed apply PR must remain separate from live apply.
- `ready_for_live_apply=false` remains required in this PR.
- `ready_for_production_migration=false` remains required in this PR.

## Operator Boundary

- The future PR body template is not execution approval.
- The operator evidence manifest template is not execution approval.
- The rollback / restore placeholder is not a recovery runbook.
- These templates are not execution approval and do not include runnable database commands.
- Human sign-off fields are placeholders only and are not recorded by this PR.

## Rejected Semantics

This ADR rejects the following claims:

- Reject setting `live_apply_pr_approved` to `true`.
- Reject setting `live_apply_executed` to `true`.
- Reject setting `sql_executed` to `true`.
- Reject setting `production_db_connected` to `true`.
- Reject setting `production_dsn_read` to `true`.
- Reject setting `ready_for_live_apply` to `true`.
- Reject setting `ready_for_production_migration` to `true`.
- Reject claims that production migration is completed.
- Reject claims that seed apply is completed.
