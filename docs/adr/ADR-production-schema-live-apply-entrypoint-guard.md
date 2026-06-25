# ADR: Production Schema Live-Apply Entrypoint Guard

## Status

Proposed / Production schema live-apply entrypoint guard only

## Context

- PR #281 entered the schema-changing file-update chain.
- The formal schema files are now the review source for a later live apply step.
- This PR is the live apply entrypoint guard package before any live apply.
- This PR is not a live apply PR.
- This PR does not execute SQL, connect to PostgreSQL, read DSN material, or execute seed data.
- Seed apply remains separate.

## Decision

- Add an offline entrypoint guard that renders only guard reports, a live-apply request JSON, and an operator runbook.
- Read `db/schema.sql` and `db/postgres/001_init.sql` only for hash, line-count, table-count, byte-identity, table-name consistency, and `anchors` presence checks.
- Keep schema files read-only in this PR.
- Emit no SQL files, shell scripts, connection material, raw schema text, or apply-ready command.
- Require a future live apply execution PR with explicit approval and review.
- Require a future seed apply PR with explicit approval and review.

## Required Flags

```text
live_apply_entrypoint_guard_only=true
schema_files_modified=false
schema_files_read_only=true
schema_files_byte_identical_required=true
production_schema_hashes_rendered=true
live_apply_approved=false
live_apply_executed=false
sql_executed=false
production_db_connected=false
production_dsn_read=false
production_seed_executed=false
seed_apply_executed=false
ready_for_live_apply=false
ready_for_production_migration=false
future_live_apply_execution_pr_required=true
future_seed_apply_pr_required=true
```

## Non-Goals

- No live apply execution.
- No PostgreSQL connection.
- No DSN access.
- No migration SQL execution.
- No production seed execution.
- No seed apply execution.
- No apply-ready command.
- No public schema write.
- No human sign-off forged.
- No production migration completion record.

## Guard Outputs

- `--contract-report` prints the guard contract.
- `--entrypoint-guard-report` prints the gate summary.
- `--render-live-apply-request-json` prints the non-executing request package.
- `--render-operator-runbook-md` prints an operator runbook that is not an approval or command.
- `--lint-entrypoint-guard-report` validates guard flags and blocked content.
- `--adr-check` validates this ADR.

## Operator Boundary

The operator runbook must include:

```text
THIS RUNBOOK IS NOT AN EXECUTION APPROVAL.
NO DSN IS READ BY THIS PR.
NO SQL IS EXECUTED BY THIS PR.
FUTURE LIVE APPLY EXECUTION PR REQUIRED.
```

The runbook must not include a database command, connection value, schema body, seed body, or apply-ready command.

## Future Work Boundary

- Future live apply execution PR remains required.
- Future seed apply PR remains required.
- `ready_for_live_apply=false` remains required in this PR.
- `ready_for_production_migration=false` remains required in this PR.
- This PR does not claim live apply, seed apply, or production migration completion.
