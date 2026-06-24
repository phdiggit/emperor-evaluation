# ADR: Schema Diff Draft Renderer

## Status

Proposed

`schema_diff_draft_only=true`

`schema_files_modified=false`

`sql_executed=false`

`production_db_connected=false`

Future production migration PR required.

## Context

- migration SQL draft renderer exists
- production migration dry-run package exists
- production migration admission card exists
- formal schema draft exists
- formal DDL rehearsal exists
- current `db/schema.sql` and `db/postgres/001_init.sql` remain unchanged

The current platform chain has proposal-only reports for admission, dry-run
packaging, formal migration planning, and SQL draft review. This ADR adds the
offline schema diff draft step so a later approved production migration PR can
review table-level drift before changing schema files.

## Decision

- This ADR defines an offline schema diff draft renderer only.
- This PR does not modify `db/schema.sql`.
- This PR does not modify `db/postgres/001_init.sql`.
- This PR does not execute migration SQL.
- This PR does not connect to PostgreSQL.
- This PR does not execute production seed.
- Future production migration PR remains separately required.

## Diff Renderer Scope

- read current schema files for comparison only
- read formal target schema draft constants
- compare target tables and deferred tables at proposal level
- emit structured JSON diff report to stdout
- include schema file checksum metadata
- include no-write verification fields

## Schema File Boundaries

- schema files are read-only schema inputs
- schema files are not modified
- schema diff is proposal-only
- schema diff is not applied to DB
- schema diff does not imply production readiness

## Diff Categories

- target_phase_1_tables
- deferred_phase_2_relationship_tables
- deferred_phase_3_downstream_tables
- currently_declared_schema_files
- missing_from_current_schema_files
- present_in_current_schema_files
- proposal_only_changes

## Explicit Non-goals

- no production migration in this PR
- no production seed in this PR
- no db/schema.sql edit
- no db/postgres/001_init.sql edit
- no schema file edits in this PR
- no production DB connection
- no evaluation metric or business conclusion changes

## Consequences

- future production migration PR can review schema diff shape
- executable schema change still requires separate approved PR
