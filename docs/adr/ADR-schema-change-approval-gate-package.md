# ADR: Schema-Change Approval Gate Package

## Status

Proposed / Approval gate package only

## Context

- The schema-change candidate review bundle exists.
- A future schema-changing PR still requires explicit user approval.
- This PR may define an approval gate package only.
- Live apply and seed apply remain separate opt-in PRs.

## Decision

- Add a schema-change approval gate package contract.
- Gate package may inspect current schema files read-only for hashes and line counts.
- Gate package may render a human approval request template for a later conversation.
- Gate package may render a blocked-by-default future schema-changing PR body template.
- Gate package must not record user approval.
- Gate package must not record human sign-off.
- Gate package must not set ready_for_schema_change_pr to true.
- Gate package must not set ready_for_production_migration to true.
- Gate package must not modify formal schema files.
- Gate package must not emit executable SQL or apply-ready patch artifacts.

## Non-goals

- No production migration execution.
- No production seed execution.
- No schema modification.
- No executable migration SQL artifact.
- No apply-ready schema patch artifact.
- No DB connection.
- No DSN access.
- No approval of production migration.
- No approval of schema-changing PR.
- No recorded user approval.
- No recorded human sign-off.

## Required Flags

```text
schema_change_approval_gate_package_only=true
schema_change_user_approval_recorded=false
schema_change_pr_approved=false
production_migration_approved=false
production_migration_executed=false
production_seed_executed=false
schema_files_modified=false
schema_file_hashes_read_only=true
migration_sql_executable_in_this_pr=false
migration_sql_artifact_emitted=false
apply_ready_schema_patch_artifact_emitted=false
sql_executed=false
production_db_connected=false
production_dsn_read=false
human_signoffs_recorded=false
ready_for_schema_change_pr=false
ready_for_production_migration=false
future_schema_change_pr_requires_explicit_user_approval=true
future_schema_change_pr_required=true
future_live_apply_pr_required=true
future_seed_apply_pr_required=true
```

## Human Approval Template Boundary

- Explicit user approval: NOT RECORDED IN THIS PR
- Human schema reviewer sign-off: PLACEHOLDER ONLY
- Migration operator sign-off: PLACEHOLDER ONLY
- Rollback owner sign-off: PLACEHOLDER ONLY
- Final maintainer sign-off: PLACEHOLDER ONLY

## Future Work Boundary

- Future schema-changing PR still requires explicit user approval.
- Future schema-changing PR must show the exact schema file diff in that later PR.
- Live apply remains a separate opt-in PR.
- Seed apply remains a separate opt-in PR.
- Current schema files may be read only for hash and line-count inspection.
- Schema file contents are not exported by this gate package.
