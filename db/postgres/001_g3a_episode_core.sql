BEGIN;

CREATE TABLE source_documents (
    document_id TEXT PRIMARY KEY,
    revision_ref TEXT NOT NULL,
    work_identity TEXT NOT NULL,
    edition_identity TEXT,
    title TEXT NOT NULL,
    canonical_url TEXT,
    source_role TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ,
    content_hash TEXT NOT NULL,
    license_or_access_note TEXT,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE source_passages (
    passage_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES source_documents (document_id),
    revision_ref TEXT NOT NULL,
    section_id TEXT NOT NULL,
    section_heading TEXT NOT NULL,
    span_start INTEGER NOT NULL CHECK (span_start >= 0),
    span_end INTEGER NOT NULL CHECK (span_end > span_start),
    passage_kind TEXT NOT NULL CHECK (
        passage_kind IN ('atomic', 'context', 'navigation_noise')
    ),
    content_hash TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assertions (
    assertion_id TEXT PRIMARY KEY,
    source_passage_id TEXT NOT NULL REFERENCES source_passages (passage_id),
    assertion_type TEXT NOT NULL,
    assertion_semantic_key TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX assertions_passage_semantic_idx
    ON assertions (source_passage_id, assertion_semantic_key);

CREATE TABLE historical_episodes (
    episode_id TEXT PRIMARY KEY,
    identity_anchor TEXT NOT NULL UNIQUE,
    evaluation_context TEXT NOT NULL,
    semantic_fingerprint TEXT NOT NULL,
    episode_status TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE episode_participants (
    episode_id TEXT NOT NULL REFERENCES historical_episodes (episode_id) ON DELETE CASCADE,
    person_ref TEXT NOT NULL,
    role_code TEXT NOT NULL,
    role_status TEXT NOT NULL,
    PRIMARY KEY (episode_id, person_ref, role_code)
);

CREATE TABLE episode_assertion_dispositions (
    episode_id TEXT NOT NULL REFERENCES historical_episodes (episode_id) ON DELETE CASCADE,
    assertion_id TEXT NOT NULL REFERENCES assertions (assertion_id),
    disposition TEXT NOT NULL CHECK (
        disposition IN ('core_of_episode', 'context_for_episode')
    ),
    reason TEXT NOT NULL,
    follow_up TEXT,
    PRIMARY KEY (episode_id, assertion_id, disposition)
);

CREATE TABLE episode_relations (
    relation_id TEXT PRIMARY KEY,
    from_episode_ref TEXT NOT NULL REFERENCES historical_episodes (episode_id) ON DELETE CASCADE,
    to_episode_ref TEXT NOT NULL REFERENCES historical_episodes (episode_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    semantic_fingerprint TEXT NOT NULL,
    relation_status TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (from_episode_ref <> to_episode_ref)
);

CREATE TABLE governance_achievements (
    achievement_ref TEXT PRIMARY KEY,
    independent_governance_key TEXT NOT NULL UNIQUE,
    dynasty TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    result_direction TEXT NOT NULL,
    impact_level TEXT NOT NULL CHECK (
        impact_level IN ('local', 'important', 'regional', 'national', 'era_shaping')
    ),
    semantic_fingerprint TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE governance_achievement_members (
    achievement_ref TEXT NOT NULL
        REFERENCES governance_achievements (achievement_ref) ON DELETE CASCADE,
    member_ref TEXT NOT NULL,
    member_kind TEXT NOT NULL CHECK (member_kind IN ('person', 'ruler')),
    contribution_role TEXT NOT NULL CHECK (
        contribution_role IN ('exclusive', 'lead', 'participant', 'authorized')
    ),
    PRIMARY KEY (achievement_ref, member_ref, member_kind)
);

CREATE TABLE rule_evidence_units (
    unit_ref TEXT PRIMARY KEY,
    rule_code TEXT NOT NULL,
    evaluation_context TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('positive', 'negative', 'mixed')),
    semantic_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'accepted', 'needs_review')),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rule_evidence_members (
    unit_ref TEXT NOT NULL REFERENCES rule_evidence_units (unit_ref) ON DELETE CASCADE,
    member_ref TEXT NOT NULL,
    member_type TEXT NOT NULL CHECK (
        member_type IN (
            'episode', 'relation', 'aggregate_context', 'governance_achievement'
        )
    ),
    member_role TEXT NOT NULL,
    PRIMARY KEY (unit_ref, member_ref, member_type)
);

COMMIT;
