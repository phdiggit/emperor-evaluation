# ADR: Schema-Change Explicit Approval Request Handoff

## Status

Proposed / Explicit approval request handoff only

## Context

- The schema-change approval gate package exists.
- A real schema-changing PR still requires explicit user approval.
- This PR may prepare an approval request handoff only.
- Live apply and seed apply remain separate opt-in PRs.

## Decision

- Add explicit approval request handoff contract.
- Render exact user-facing approval request text.
- Render machine-readable approval request JSON.
- Render blocked-by-default future schema-changing PR body template.
- May read current schema files only for hash and line-count fingerprints.
- Must not record approval or human sign-off.
- Must not modify schema files.
- Must not emit SQL or patch artifacts.

## Non-goals

- No production migration execution.
- No production seed execution.
- No schema modification.
- No executable migration SQL artifact.
- No apply-ready schema patch artifact.
- No DB connection.
- No DSN access.
- No production migration approval.
- No schema-changing PR approval.
- No recorded user approval.
- No recorded human sign-off.

## Required Flags

```text
schema_change_explicit_approval_request_handoff_only=true
schema_change_user_approval_recorded=false
schema_change_approval_request_rendered=true
schema_change_approval_request_status=pending_external_user_decision
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

## Exact Approval Request Boundary

- This handoff is NOT an approval record in PR #280.
- Explicit approval must be provided outside this PR.
- The requested user decision is limited to authorizing a future schema-changing PR draft.
- Live apply and seed apply remain separate opt-in PRs.

## Future Work Boundary

- Future schema-changing PR remains separate.
- Future live apply PR remains separate.
- Future seed apply PR remains separate.
- Current schema files may be read only for hash and line-count inspection.
- Schema file contents are not exported by this handoff package.
