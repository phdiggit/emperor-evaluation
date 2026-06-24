# ADR: anchors schema proposal

## Status

Proposed.

This ADR is a schema proposal only. It is not accepted, finalized, applied to PostgreSQL, or treated as a target mapper.

## Context

The current platform chain has moved from canonical JSONL through staging mapper, unknown-field triage, resolver contract, query/search target mapper, sources target mapper, evidence cards target mapper, and evidence clusters resolver preparation.

The thematic anchor files remain staging-only:

- `data/thematic_anchors.jsonl`
- `data/thematic_anchor_objects.jsonl`
- `data/thematic_anchor_events.jsonl`
- `data/thematic_anchor_mechanisms.jsonl`

Earlier target mapper and resolver contract work keeps anchor-related fields as reference risk or blocked schema inputs. These fields include `object_anchor`, `object_anchors`, and `thematic_anchor_targets`. They are not formal PostgreSQL identifiers and do not prove relationships by themselves.

## Decision

Define a stable but unapplied proposal for future anchors target work:

- `anchors`
- `anchor_links`
- `anchor_terms` as future work, not part of the first core target proposal

This ADR does not change `db/postgres/001_init.sql` or any production schema. A later resolver contract must decide how candidate anchor codes become reviewed target rows.

## Proposed Tables

### anchors

Proposed columns:

| column | proposed type | note |
| --- | --- | --- |
| `id` | `BIGSERIAL` / identity | internal surrogate identifier after schema adoption |
| `code` | `TEXT UNIQUE NOT NULL` | stable anchor code, not inferred from display text alone |
| `anchor_type` | `TEXT NOT NULL` | candidate values: `theme`, `object`, `event`, `mechanism`, `person_object`, `policy_object` |
| `label` | `TEXT` | display label |
| `status` | `TEXT` | review or lifecycle status |
| `payload` | `JSONB NOT NULL DEFAULT '{}'` | source details and unresolved metadata |
| `created_at` | `TIMESTAMPTZ` | creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | update timestamp |

### anchor_links

Proposed columns:

| column | proposed type | note |
| --- | --- | --- |
| `id` | `BIGSERIAL` / identity | internal surrogate identifier after schema adoption |
| `anchor_code` | `TEXT NOT NULL` | candidate anchor code, not a resolved `anchor_id` |
| `target_domain` | `TEXT NOT NULL` | candidate domain: `person`, `evidence_card`, `evidence_cluster`, `source_document`, `source_passage_candidate`, `query_profile`, `search_task`, `subitem` |
| `target_code` | `TEXT NOT NULL` | unresolved target code or candidate code |
| `link_role` | `TEXT` | optional role label |
| `resolver_status` | `TEXT NOT NULL` | candidate values: `unresolved_candidate`, `manual_review_required`, `resolver_ready`, `blocked_pending_schema` |
| `payload` | `JSONB NOT NULL DEFAULT '{}'` | resolver trace and source details |
| `created_at` | `TIMESTAMPTZ` | creation timestamp |

The first stage may only use `unresolved_candidate`, `manual_review_required`, or `blocked_pending_schema`. No link in this ADR is an already-resolved factual relationship.

### anchor_terms

`anchor_terms` remains future work. If added later, proposed columns are:

- `anchor_code`
- `term`
- `term_type`
- `payload`

The first schema proposal keeps aliases and terms out of the core target surface to avoid making display strings look like reviewed identifiers.

## Input JSONL Sources

The proposal is scoped to these sources:

- `data/thematic_anchors.jsonl`
- `data/thematic_anchor_objects.jsonl`
- `data/thematic_anchor_events.jsonl`
- `data/thematic_anchor_mechanisms.jsonl`
- `data/query_profiles.jsonl`
- `data/evidence_cards.jsonl`
- `data/evidence_clusters.jsonl`

Source interpretation:

- `thematic_*` JSONL files provide anchor candidates.
- `object_anchor`, `object_anchors`, and `thematic_anchor_targets` provide anchor resolver inputs.
- `linked_evidence_ids` and `linked_cluster_ids` remain direct resolver inputs for their own target contracts and must not be routed through anchors as indirect relationship writes.

Batch and archive data are out of scope for this ADR.

## Resolver Boundary

- Anchor name or code is not a formal `anchor_id`.
- `object_anchor` does not directly write `anchor_links`.
- `object_anchors` does not directly write `anchor_links`.
- `thematic_anchor_targets` does not directly write `anchor_links`.
- `linked_evidence_ids` and `linked_cluster_ids` do not write relationships indirectly through anchors.
- Anchors do not prove evidence relationships.
- Anchors do not prove cluster relationships.
- Anchors do not prove item or subitem relationships.

The first resolver stage can only emit candidate states:

- `unresolved_candidate`
- `manual_review_required`
- `blocked_pending_schema`

## Relationship Boundary

This ADR forbids direct writes to:

- `anchor_links`
- evidence relationship tables
- `cluster_evd`
- `evd_src_links`
- `person_id` / `subitem_id`
- `score_records` / `score_releases`
- `adjudications`

Future work may describe resolver output, but this PR does not implement any writer, mapper, or production table.

## Migration / Backfill Boundary

No migration or backfill runs in this PR. Future migration work must:

- keep canonical JSONL as the source until a separate migration plan is accepted;
- introduce resolver output before any target relationship write;
- use reviewed target codes instead of display names;
- run in a separate PR after a contract-report-only resolver proposal.

## Rejected Alternatives

- Modify `db/postgres/001_init.sql` now: rejected because the current chain only needs a proposal.
- Treat `object_anchor` or `thematic_anchor_targets` as direct links: rejected because those fields are unresolved inputs.
- Route evidence or cluster relationships through anchors: rejected because anchors do not prove those relationships.
- Add `anchor_terms` as a core first-stage table: rejected for now because terms and aliases need their own review rules.

## Validation / Tests

Validation for this ADR is covered by:

- `python scripts/platform/anchors_schema_proposal.py --contract-report`
- `pytest -q tests/test_anchors_schema_proposal_contract.py`
- docs governance checks for the new ADR registration

The contract report must stay offline, must not read `.env`, must not connect to PostgreSQL, and must not access the network.

## Future Work

- PR #255 can define an anchors resolver contract.
- A later PR can decide whether `anchor_terms` belongs in the core target surface.
- A later migration PR can propose PostgreSQL DDL after resolver semantics are reviewed.
- A later mapper PR can convert reviewed resolver output into target writes.
