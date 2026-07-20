BEGIN;

CREATE TABLE historical_outcome_clusters (
    outcome_ref TEXT PRIMARY KEY CHECK (outcome_ref ~ '^OUTCOME-[A-Z0-9-]+$'),
    outcome_kind TEXT NOT NULL CHECK (outcome_kind IN ('campaign', 'governance')),
    independent_key TEXT NOT NULL,
    canonical_label TEXT NOT NULL,
    result_status TEXT NOT NULL CHECK (
        result_status IN ('implemented', 'operated', 'completed', 'mixed', 'failed', 'unclear')
    ),
    result_direction TEXT NOT NULL CHECK (
        result_direction IN ('positive', 'mixed', 'negative', 'unclear')
    ),
    scale_level TEXT NOT NULL CHECK (
        scale_level IN ('local', 'important', 'regional', 'national', 'era_shaping')
    ),
    semantic_fingerprint TEXT NOT NULL CHECK (
        semantic_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    input_fingerprint TEXT NOT NULL CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    acceptance_status TEXT NOT NULL CHECK (
        acceptance_status IN ('shadow', 'human_frozen', 'needs_review')
    ),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (outcome_kind, independent_key)
);

CREATE TABLE outcome_cluster_members (
    outcome_ref TEXT NOT NULL
        REFERENCES historical_outcome_clusters (outcome_ref) ON DELETE CASCADE,
    actor_ref TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('person', 'ruler')),
    role_code TEXT NOT NULL CHECK (
        role_code IN (
            'commander_in_chief', 'principal_commander', 'deputy_commander',
            'participant', 'exclusive', 'lead', 'governance_participant', 'authorized'
        )
    ),
    contribution_scope TEXT NOT NULL,
    PRIMARY KEY (outcome_ref, actor_ref, actor_kind)
);

CREATE TABLE outcome_episode_links (
    outcome_ref TEXT NOT NULL
        REFERENCES historical_outcome_clusters (outcome_ref) ON DELETE CASCADE,
    episode_id TEXT NOT NULL
        REFERENCES historical_episodes (episode_id) ON DELETE RESTRICT,
    link_role TEXT NOT NULL CHECK (
        link_role IN ('core_result_chain', 'implementation', 'outcome', 'cost', 'context')
    ),
    PRIMARY KEY (outcome_ref, episode_id)
);

INSERT INTO historical_outcome_clusters (
    outcome_ref, outcome_kind, independent_key, canonical_label, result_status,
    result_direction, scale_level, semantic_fingerprint, input_fingerprint,
    acceptance_status, payload
)
SELECT
    'OUTCOME-GOV-' || UPPER(SUBSTRING(MD5(achievement_ref), 1, 20)),
    'governance', independent_governance_key, title,
    CASE implementation_status WHEN 'modified' THEN 'operated' ELSE implementation_status END,
    result_direction, impact_level,
    MD5(payload::TEXT) || MD5(independent_governance_key),
    MD5(semantic_fingerprint) || MD5(achievement_ref),
    'needs_review', payload
FROM governance_achievements;

INSERT INTO outcome_cluster_members (
    outcome_ref, actor_ref, actor_kind, role_code, contribution_scope
)
SELECT
    'OUTCOME-GOV-' || UPPER(SUBSTRING(MD5(member.achievement_ref), 1, 20)),
    member.member_ref,
    member.member_kind,
    CASE member.contribution_role
        WHEN 'participant' THEN 'governance_participant'
        ELSE member.contribution_role
    END,
    '由既有治理成果当前值迁移；须补 Episode 链接后重新接受'
FROM governance_achievement_members AS member;

DROP TABLE governance_achievement_members;
DROP TABLE governance_achievements;

ALTER TABLE rule_evidence_members
    DROP CONSTRAINT rule_evidence_members_member_type_check;
ALTER TABLE rule_evidence_members
    ADD CHECK (
        member_type IN ('episode', 'relation', 'aggregate_context', 'outcome_cluster')
    );

COMMIT;
