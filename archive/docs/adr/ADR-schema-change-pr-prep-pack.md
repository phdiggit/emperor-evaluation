# ADR: Schema-Change PR Preparation Pack

## Status

Proposed / Preparation pack only

## Context

- Guarded executable migration PR proposal exists.
- Future schema-changing PR still requires explicit user approval.
- This PR prepares review material only.
- Live apply and seed apply remain separately opt-in.

## Decision

- Add schema-change PR preparation pack contract.
- Pack renders blocked-by-default future PR body template.
- Pack renders machine-readable review checklist / guard flags.
- Pack may summarize intended future schema-change sections as placeholders only.
- Pack must not modify schema files or execute SQL.
- Pack must not record approvals or human sign-offs.

## Non-goals

- No production migration execution.
- No production seed execution.
- No schema modification.
- No DB connection.
- No DSN access.
- No approval of production migration.
- No approval of schema-changing PR.
- No executable SQL in this PR.
- No human sign-off forged.

## Required Flags

```text
schema_change_pr_prep_pack_only=true
schema_change_pr_approved=false
production_migration_approved=false
production_migration_executed=false
production_seed_executed=false
schema_files_modified=false
migration_sql_executable_in_this_pr=false
sql_executed=false
production_db_connected=false
production_dsn_read=false
human_signoffs_recorded=false
ready_for_schema_change_pr=false
ready_for_production_migration=false
future_schema_change_pr_required=true
future_live_apply_pr_required=true
future_seed_apply_pr_required=true
```

## Future PR Body Template Boundaries

- Exact schema file changes remain placeholders in this PR.
- Required user approval remains NOT RECORDED IN THIS PR.
- Rollback/restore plan remains placeholder only.
- Live apply / seed apply must be separate opt-in PRs.
- Production verification uses neutral platform terms: metric_records, metric_releases, downstream_release_tables.

## Preparation Pack Contents

- Future schema file section placeholders.
- Future schema change summary placeholders.
- Future migration SQL source placeholders.
- Rollback / restore placeholders.
- Required approval placeholders.
- Non-execution guarantees for this preparation PR.
