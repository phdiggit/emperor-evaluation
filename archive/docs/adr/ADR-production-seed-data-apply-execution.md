# ADR: Production Seed Manifest Import-Audit Scaffold

## Status

Audit-only / Import-audit scaffold, not production seed/data apply execution

## Context

- #285 completed the production schema live apply execution.
- PR #286 was closed without becoming a safe production seed/data apply path.
- The follow-up scope is narrowed to canonical seed manifest discovery and import-audit scaffold behavior.
- Schema files and source data files remain read-only inputs.
- A missing canonical production seed/data manifest must fail closed before DSN read with `blocked_missing_seed_manifest`.
- The real business target importer is deferred to Epic 1.

## Decision

- This is an import-audit scaffold, not production seed/data apply execution.
- It allows DSN read from `EMPEROR_EVAL_PG_DSN` only inside explicit execution or verification modes.
- It allows DB connect through the Python PostgreSQL driver.
- It allows import audit scaffold writes to `imports` and `import_rows` only when every gate passes.
- It requires `expected_seed_manifest_sha256`.
- It requires `expected_schema_sha256`.
- It requires PR #285 schema live apply evidence to be recorded or re-verified before execution.
- If no canonical production seed/data manifest is identified, execution must fail closed with `blocked_missing_seed_manifest`.
- `imports` and `import_rows` are audit tables; they are not business target migration tables.
- `target_table` in `import_rows` must not be used to claim real target table writes.
- File-level SHA values may identify source files or audit envelope inputs, but must not be represented as source row payload hashes.
- Verification of audit header/count only proves the audit scaffold, not production migration completion.
- It does not modify source data.
- It does not log DSN, password, connection string, host, user, or password values.
- It must not fake migration success.

## Permanently Blocked Success Flags

These flags remain false in this scaffold, even if audit rows are written:

```text
seed_data_apply_executed=false
production_data_rows_written=false
verification_passed=false
ready_for_production_migration=false
```

`import_audit_written=true` may only mean audit scaffold rows were written to `imports` / `import_rows`; it does not imply business target table writes, seed/data apply, or readiness for production migration.

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
- If audit write or audit verification fails, the report must be blocked.
- If audit verification passes but no business target importer exists, the report must remain blocked with `blocked_target_business_importer_not_implemented_epic1`.

## Non-Goals

- This PR does not change schema SQL files.
- This PR does not edit `data/**` or `archive/data/**`.
- This PR does not invent seed rows.
- This PR does not import from an unapproved candidate list.
- This PR does not write business target tables.
- This PR does not mark production migration complete.
- This PR does not make PostgreSQL the unique write source.
