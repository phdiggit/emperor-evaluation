# ADR: Production Seed/Data Apply Execution

## Status

Approved / Production seed data apply execution PR

User authorization signal: 已授权

## Context

- #285 completed the production schema live apply execution.
- This ADR covers the follow-up seed/data apply execution PR.
- PR #286 must preserve the schema files and source data files as read-only inputs.
- A production seed/data apply may only succeed when a deterministic seed manifest is explicitly approved and its hash is supplied by the operator.

## Decision

- This is a seed/data apply execution PR.
- It allows DSN read from `EMPEROR_EVAL_PG_DSN` only inside explicit execution or verification modes.
- It allows DB connect through the Python PostgreSQL driver.
- It allows import audit writes to the production schema when every gate passes.
- It requires `expected_seed_manifest_sha256`.
- It requires `expected_schema_sha256`.
- It requires PR #285 schema live apply evidence to be recorded or re-verified before execution.
- If no canonical production seed/data manifest is identified, execution must fail closed with `blocked_missing_seed_manifest`.
- It does not modify source data.
- It does not log DSN, password, connection string, host, user, or password values.
- It must not fake success.

## Required Success Flags

These flags may only be true when every execution gate passes, seed/data apply actually runs, import audit rows are written, and verification passes:

```text
seed_data_apply_executed=true
production_data_rows_written=true
import_audit_written=true
verification_passed=true
ready_for_production_migration=true
```

Blocked reports must keep those flags false.

## Failure Boundary

- If the approval token is missing or invalid, the report must be blocked.
- If schema hash is missing or mismatched, the report must be blocked.
- If seed manifest hash is missing or mismatched, the report must be blocked.
- If the schema files are not byte-identical, the report must be blocked.
- If the seed manifest is not explicitly approved, the report must be blocked with `blocked_missing_seed_manifest`.
- If DSN is missing, the report must be blocked.
- If the runtime dependency is missing, the report must be blocked.
- If connection fails, the report must be blocked.
- If PR #285 schema live apply cannot be re-verified, the report must be blocked.
- If audit write or verification fails, the report must be blocked.

## Non-Goals

- This PR does not change schema SQL files.
- This PR does not edit `data/**` or `archive/data/**`.
- This PR does not invent seed rows.
- This PR does not import from an unapproved candidate list.
