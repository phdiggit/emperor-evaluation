# ADR: Production Schema Live-Apply Execution

## Status

Approved / Production schema live-apply execution PR

## Context

- #281 completed the formal schema file update.
- #282 added the production schema live-apply entrypoint guard.
- #283 added the execution PR scaffold.
- #284 added the final execution preflight package.
- The user explicitly said “批准所有权限”; this ADR records that statement as the authorization signal for this schema live apply PR.

## Decision

- This is a schema live apply execution PR.
- It allows DSN read from `EMPEROR_EVAL_PG_DSN` only inside explicit execution or verification modes.
- It allows DB connect through the Python PostgreSQL driver.
- It allows SQL execution of the byte-identical formal schema file.
- It allows public schema write for DDL objects.
- It writes only redacted execution evidence and verification summaries.

## Required Success Flags

```text
production_schema_live_apply_execution_pr=true
schema_live_apply_approved=true
schema_live_apply_executed=true
sql_executed=true
production_db_connected=true
production_dsn_read=true
public_schema_write_attempted=true
schema_files_modified=false
schema_files_read_only=true
schema_files_byte_identical_required=true
production_schema_hashes_rendered=true
post_apply_verification_executed=true
production_seed_executed=false
seed_apply_executed=false
ready_for_live_apply=false
ready_for_production_migration=false
future_target_importer_gate_required=true
```

## Non-Goals

- This PR does not execute seed/data apply.
- This PR does not execute JSONL or data import.
- This PR does not write business data rows.
- This PR does not log DSN, password, connection string, host, user, or password values.
- This PR does not mark production migration complete.
- This PR does not set `ready_for_production_migration=true`.

## Failure Boundary

- If DSN is missing, the report must be blocked.
- If the runtime dependency is missing, the report must be blocked.
- If connection fails, the report must be blocked.
- If SQL execution fails, the report must be blocked.
- If verification fails, the report must be blocked.
- The script must not fake success.
- It must not claim `schema_live_apply_executed=true` unless the schema SQL actually ran and verification passed.

## Future Work

- Future target importer gate required.
- Seed/data apply and business target writes remain separate Epic 1 work.
