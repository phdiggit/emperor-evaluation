# ADR: Production Migration PR Admission

## Status

Proposed

`admission_only=true`

`production_migration_executed=false`

`ready_for_production_migration=false`

Future production migration PR required.

## Context

- formal migration proposal exists
- cutover readiness matrix exists
- isolated DDL rehearsal exists
- isolated live DDL rehearsal exists
- seed artifact validation exists
- isolated dry-apply exists
- rollback / restore rehearsal exists

The current platform chain can define the admission rules for a later production
migration PR, but this ADR does not approve or execute that migration.

## Decision

- This ADR defines admission requirements only.
- This PR does not execute production migration.
- This PR does not modify `db/schema.sql`.
- This PR does not modify `db/postgres/001_init.sql`.
- A future production migration PR may modify those schema files only after all
  gates pass.

## Allowed Future Production Migration PR File Scope

- `db/schema.sql`
- `db/postgres/001_init.sql`
- migration-specific docs or ADR
- migration validation tests

## Forbidden In This Admission PR

- no production migration in this PR
- no production seed in this PR
- no public schema write
- no production DB connection
- no data artifact write
- no export artifact write
- no schema file edits in this PR

## Required Machine Gates

- schema diff generated
- migration SQL linted
- full validation suite green
- cutover readiness matrix green
- dry apply rehearsal green
- rollback / restore rehearsal green
- seed artifact checksum reviewed

## Required Human Gates

- schema reviewer sign-off
- data/source-of-truth reviewer sign-off
- rollback owner sign-off
- operator sign-off
- final maintainer sign-off

## Required Rollback Plan

- backup point identified
- restore path documented
- rollback timing documented
- verification queries documented
- emergency stop condition documented

## Explicit Non-goals

- no production migration in this PR
- no production seed in this PR
- no formal schema file edits in this PR
- no evaluation metric changes
- no business conclusion changes

## Consequences

- project gets a checklist for the next production migration PR
- production migration remains blocked until a separate approved PR
