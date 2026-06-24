# ADR: Formal Migration Proposal

## Status

Proposed

This ADR is a proposal only. It does not approve, execute, or prepare any
production database action.

## Context

- canonical JSONL remains source-of-truth
- formal schema draft exists
- isolated DDL rehearsal exists
- live DDL rehearsal exists
- seed artifact renderer exists
- seed artifact validation matrix exists
- DB preflight contract exists
- isolated seed dry-apply exists
- rollback / restore rehearsal exists
- cutover readiness matrix exists

The cutover readiness matrix currently supports moving to a formal migration
proposal update. It also declares `ready_for_production_migration=false`.

## Decision

- Update migration proposal only
- Do not modify formal schema files in this PR
- Do not execute production migration
- Do not execute production seed
- Require separate production migration PR

Production migration requires separate approved PR before any production
database action can be considered.

## Readiness Summary

- readiness matrix state: ready for formal migration proposal update
- offline gates: formal schema draft, DDL rehearsal, seed artifact, DB preflight,
  isolated dry-apply, and rollback / restore contracts are represented by the
  readiness matrix
- optional DB evidence state: skipped by default and not required for this
  proposal
- next stage recommendation: prepare a separate production migration PR
  admission card

`ready_for_production_migration=false` remains the required state for this ADR.

## Migration Plan Outline

- Phase A: schema freeze proposal
- Phase B: production migration PR approval
- Phase C: production seed approval
- Phase D: rollback / restore runbook approval

## Required Production PR Gates

- schema diff reviewed
- migration SQL reviewed
- backup/restore plan reviewed
- seed artifact checksum reviewed
- rollback/restore rehearsal result reviewed
- operator sign-off

## Explicit Non-goals

- no db/schema.sql change
- no db/postgres/001_init.sql change
- no production migration
- no production DB connection
- no production seed
- no production seed application
- no public schema write
- no business conclusion changes

## Risks

- schema drift
- seed artifact drift
- operator error
- rollback gap
- source-of-truth mismatch

## Rollback Strategy

- production rollback must be separate approved runbook
- this PR only references isolated rehearsal evidence

## Consequences

- project can prepare production migration PR
- formal schema remains unchanged until separate PR
