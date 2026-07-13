BEGIN;

CREATE TABLE source_documents (
    document_id TEXT NOT NULL,
    content_version TEXT NOT NULL,
    work_identity TEXT NOT NULL,
    edition_identity TEXT,
    title TEXT NOT NULL,
    canonical_url TEXT,
    source_role TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ,
    content_hash TEXT,
    license_or_access_note TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, content_version)
);

CREATE TABLE source_passages (
    passage_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    document_content_version TEXT NOT NULL,
    section_id TEXT NOT NULL,
    section_heading TEXT NOT NULL,
    span_start INTEGER NOT NULL CHECK (span_start >= 0),
    span_end INTEGER NOT NULL CHECK (span_end > span_start),
    passage_kind TEXT NOT NULL CHECK (passage_kind IN ('atomic', 'context', 'navigation_noise')),
    content_hash TEXT NOT NULL,
    window_policy_version TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id, document_content_version)
        REFERENCES source_documents (document_id, content_version)
);

CREATE TABLE assertions (
    assertion_id TEXT PRIMARY KEY,
    source_passage_id TEXT NOT NULL REFERENCES source_passages (passage_id),
    assertion_type TEXT NOT NULL,
    assertion_semantic_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX assertions_passage_semantic_idx
    ON assertions (source_passage_id, assertion_semantic_key);

CREATE TABLE historical_episodes (
    episode_id TEXT PRIMARY KEY,
    identity_anchor TEXT NOT NULL UNIQUE,
    evaluation_context TEXT NOT NULL,
    active_semantic_version INTEGER NOT NULL CHECK (active_semantic_version >= 1),
    active_evidence_version INTEGER NOT NULL CHECK (active_evidence_version >= 1),
    active_semantic_fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE historical_episode_versions (
    episode_id TEXT NOT NULL REFERENCES historical_episodes (episode_id),
    semantic_version INTEGER NOT NULL CHECK (semantic_version >= 1),
    evidence_version INTEGER NOT NULL CHECK (evidence_version >= 1),
    semantic_fingerprint TEXT NOT NULL,
    semantic_payload_hash TEXT NOT NULL,
    evidence_payload_hash TEXT NOT NULL,
    episode_status TEXT NOT NULL,
    input_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (episode_id, semantic_version, evidence_version)
);

ALTER TABLE historical_episodes
    ADD CONSTRAINT historical_episodes_active_version_fk
    FOREIGN KEY (episode_id, active_semantic_version, active_evidence_version)
    REFERENCES historical_episode_versions (episode_id, semantic_version, evidence_version)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE episode_participants (
    episode_id TEXT NOT NULL REFERENCES historical_episodes (episode_id),
    semantic_version INTEGER NOT NULL CHECK (semantic_version >= 1),
    person_ref TEXT NOT NULL,
    role_code TEXT NOT NULL,
    role_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (episode_id, semantic_version, person_ref, role_code)
);

CREATE TABLE episode_assertion_dispositions (
    episode_id TEXT NOT NULL,
    semantic_version INTEGER NOT NULL,
    evidence_version INTEGER NOT NULL,
    assertion_id TEXT NOT NULL REFERENCES assertions (assertion_id),
    disposition TEXT NOT NULL CHECK (disposition IN ('core_of_episode', 'context_for_episode')),
    reason TEXT NOT NULL,
    follow_up TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        episode_id,
        semantic_version,
        evidence_version,
        assertion_id,
        disposition
    ),
    FOREIGN KEY (episode_id, semantic_version, evidence_version)
        REFERENCES historical_episode_versions (episode_id, semantic_version, evidence_version)
);

CREATE TABLE review_artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL CHECK (
        artifact_type IN ('boundary_review', 'relation_review_artifact', 'relation_proposal')
    ),
    artifact_status TEXT NOT NULL CHECK (
        artifact_status IN ('draft', 'proposed', 'rejected', 'superseded')
    ),
    basis_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE boundary_review_cache (
    cache_key TEXT PRIMARY KEY,
    input_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    model_family TEXT NOT NULL,
    artifact_id TEXT NOT NULL REFERENCES review_artifacts (artifact_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
