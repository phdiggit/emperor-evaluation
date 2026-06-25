# ADR: Schema-Changing Formal Schema Update

## Status

Proposed / Schema-changing formal schema file update

## Context

- The explicit approval request handoff exists.
- User approval to start the migration chain was provided in the task handoff: "随时可以开启数据迁移".
- This PR is the first schema-changing file update in the guarded migration chain.
- Live apply and seed apply remain separate opt-in PRs.

## Decision

- Update `db/schema.sql`.
- Update `db/postgres/001_init.sql`.
- Keep the two formal schema files logically consistent.
- Add the formal Phase 1 `anchors` base table to the PostgreSQL schema contract.
- Use neutral platform field names for matching and hit ordering metadata.
- Keep this PR schema-file-only and offline.

## Non-goals

- No SQL execution.
- No PostgreSQL connection.
- No DSN access.
- No production seed execution.
- No live apply execution.
- No apply-ready live command.
- No production migration completion record.
- No human sign-off forged.

## Required Flags

```text
schema_changing_pr=true
schema_files_modified=true
production_migration_approved=true
schema_change_user_approval_recorded=true
sql_executed=false
production_db_connected=false
production_dsn_read=false
production_seed_executed=false
live_apply_executed=false
ready_for_schema_change_pr=true
ready_for_production_migration=false
future_live_apply_pr_required=true
future_seed_apply_pr_required=true
```

## Approval Source

User message: "随时可以开启数据迁移"

This approval allows entering the schema-changing file-update chain only. It does not approve live DB apply and does not approve production seed apply.

## Schema File Boundary

- `db/schema.sql` is now the formal PostgreSQL schema mirror.
- `db/postgres/001_init.sql` remains the PostgreSQL base schema contract.
- Both files are schema / DDL definitions only.
- Neither file contains seed data, connection material, or live apply commands.

## Future Work Boundary

- Future live apply PR remains separate.
- Future seed apply PR remains separate.
- `ready_for_production_migration=false` remains required until live apply and seed apply are separately approved and reviewed.
