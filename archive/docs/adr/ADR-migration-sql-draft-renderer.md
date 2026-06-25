# ADR: Migration SQL Draft Renderer

## Status

Proposed

`migration_sql_draft_only=true`

`sql_executed=false`

`schema_files_modified=false`

`production_db_connected=false`

Future production migration PR required.

## Context

- production migration dry-run package exists
- production migration admission card exists
- formal migration proposal exists
- formal schema draft exists
- formal DDL rehearsal exists

The dry-run package names a later migration SQL draft review step. This ADR
defines that step as proposal text only, without approving or executing any
production database action.

## Decision

- This ADR defines an offline migration SQL draft renderer only.
- This PR does not execute migration SQL.
- This PR does not modify `db/schema.sql`.
- This PR does not modify `db/postgres/001_init.sql`.
- This PR does not connect to PostgreSQL.
- This PR does not execute production seed.
- Future production migration PR remains separately required.

## Draft Renderer Scope

- render SQL draft text from existing formal DDL rehearsal output
- include header warning that SQL is proposal-only
- include source metadata
- include target table summary
- include deferred Phase 2/3 table summary
- include lint-only report

## SQL Draft Boundaries

- SQL draft is stdout / in-memory only by default
- SQL draft is not written to formal schema files
- SQL draft is not executed
- SQL draft is not applied to DB
- SQL draft does not contain production DSN
- SQL draft does not contain psql command text
- SQL draft does not contain subprocess instruction text

## Lint Rules

- no production execution command
- no public schema hard-code
- no DSN / password / host
- no psql / subprocess instruction
- no production seed statement
- no COPY / LOAD DATA / UPSERT / ON CONFLICT
- no blocked report terms
- contains draft-only header
- contains do-not-execute warning
- contains source metadata
- contains target table summary
- contains deferred Phase 2/3 table summary

## Explicit Non-goals

- no production migration in this PR
- no production seed in this PR
- no db/schema.sql edit
- no db/postgres/001_init.sql edit
- no schema file edits in this PR
- no production DB connection
- no evaluation metric or business conclusion changes

## Consequences

- future production migration PR can review draft SQL shape
- executable migration still requires separate approved PR
