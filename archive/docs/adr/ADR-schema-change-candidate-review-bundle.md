# ADR: Schema-Change Candidate Review Bundle

## Status

Proposed / Candidate review bundle only

## Context

- Schema-change PR preparation pack exists.
- Future schema-changing PR still requires explicit user approval.
- This PR may assemble review material only.
- Live apply and seed apply remain separate opt-in PRs.

## Decision

- Add schema-change candidate review bundle contract.
- Bundle may inspect current schema files read-only for hashes and line counts.
- Bundle may render blocked-by-default future PR body template.
- Bundle may render candidate checklist / guard flags / source-input checklist.
- Bundle must not modify schema files.
- Bundle must not emit executable SQL or apply-ready patch artifacts.
- Bundle must not approve production migration or schema-changing PR.

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
- No human sign-off forged.

## Required Flags

```text
schema_change_candidate_review_bundle_only=true
schema_change_pr_approved=false
production_migration_approved=false
production_migration_executed=false
production_seed_executed=false
schema_files_modified=false
schema_file_hashes_read_only=true
migration_sql_executable_in_this_pr=false
migration_sql_artifact_emitted=false
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

## Candidate Review Boundaries

- Current schema files may be read only for hash and line-count inspection.
- Schema file contents are not exported by this bundle.
- Exact schema diff must be reviewed in a later explicitly approved PR.
- Executable migration SQL must not be emitted by this PR.
- Apply-ready schema patch artifact must not be emitted by this PR.
- Live apply must be a separate opt-in PR.
- Seed apply must be a separate opt-in PR.
- Future production verification uses neutral platform terms: metric_records, metric_releases, downstream_release_tables.
