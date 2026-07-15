BEGIN;

CREATE SCHEMA IF NOT EXISTS v4_person_profile;
REVOKE ALL ON SCHEMA v4_person_profile FROM PUBLIC;

CREATE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is immutable; insert a new version instead', TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;

CREATE TABLE v4_person_profile.import_batches (
    import_batch_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    source_system TEXT NOT NULL,
    source_freeze_ref TEXT NOT NULL,
    source_package_fingerprint TEXT NOT NULL CHECK (
        source_package_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    contract_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('prepared', 'reviewed', 'applied', 'partially_blocked', 'rejected')
    ),
    legacy_numeric_id_reused BOOLEAN NOT NULL DEFAULT FALSE CHECK (
        legacy_numeric_id_reused = FALSE
    ),
    database_write_mode TEXT NOT NULL DEFAULT 'v4_only' CHECK (
        database_write_mode = 'v4_only'
    ),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE v4_person_profile.person_identity_registry (
    person_ref TEXT PRIMARY KEY CHECK (person_ref !~ '^[0-9]+$'),
    canonical_name TEXT NOT NULL,
    historical_context TEXT NOT NULL,
    identity_fingerprint TEXT NOT NULL UNIQUE CHECK (
        identity_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    identity_status TEXT NOT NULL CHECK (
        identity_status IN ('candidate', 'active', 'merged', 'retired')
    ),
    semantic_version INTEGER NOT NULL CHECK (semantic_version >= 1),
    supersedes_person_ref TEXT REFERENCES v4_person_profile.person_identity_registry (person_ref),
    idempotency_key TEXT NOT NULL UNIQUE,
    import_batch_id TEXT REFERENCES v4_person_profile.import_batches (import_batch_id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (supersedes_person_ref IS NULL OR supersedes_person_ref <> person_ref),
    UNIQUE (person_ref, semantic_version)
);

CREATE TABLE v4_person_profile.person_legacy_refs (
    legacy_ref_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL CHECK (source_system <> 'v4'),
    source_object_ref TEXT NOT NULL,
    source_identity_fingerprint TEXT NOT NULL CHECK (
        source_identity_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    person_ref TEXT NOT NULL REFERENCES v4_person_profile.person_identity_registry (person_ref),
    mapping_status TEXT NOT NULL CHECK (
        mapping_status IN (
            'accepted',
            'accepted_existing_v4_identity',
            'accepted_user_authorized_v3_identity'
        )
    ),
    mapping_basis_refs JSONB NOT NULL CHECK (
        jsonb_typeof(mapping_basis_refs) = 'array'
        AND jsonb_array_length(mapping_basis_refs) > 0
    ),
    idempotency_key TEXT NOT NULL UNIQUE,
    import_batch_id TEXT NOT NULL REFERENCES v4_person_profile.import_batches (import_batch_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, source_object_ref),
    UNIQUE (source_system, source_identity_fingerprint),
    CHECK (person_ref <> source_object_ref)
);

CREATE TABLE v4_person_profile.person_profile_snapshots (
    profile_ref TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    person_ref TEXT NOT NULL REFERENCES v4_person_profile.person_identity_registry (person_ref),
    talent_grade TEXT NOT NULL CHECK (
        talent_grade IN ('historic', 'top', 'important', 'usable', 'ordinary')
    ),
    talent_grade_version TEXT NOT NULL,
    talent_grade_confidence NUMERIC(6, 5) NOT NULL CHECK (
        talent_grade_confidence >= 0 AND talent_grade_confidence <= 1
    ),
    talent_authority_consensus TEXT NOT NULL CHECK (
        talent_authority_consensus IN ('weak', 'moderate', 'strong', 'disputed')
    ),
    talent_performance_support TEXT NOT NULL CHECK (
        talent_performance_support IN ('none', 'weak', 'moderate', 'strong')
    ),
    talent_evidence_coverage TEXT NOT NULL CHECK (
        talent_evidence_coverage IN ('insufficient', 'partial', 'substantial', 'comprehensive')
    ),
    capability_domains JSONB NOT NULL CHECK (
        jsonb_typeof(capability_domains) = 'array'
        AND jsonb_array_length(capability_domains) > 0
    ),
    negative_talent_class TEXT CHECK (
        negative_talent_class IS NULL OR negative_talent_class IN (
            'sycophant',
            'favorite',
            'power_abuser',
            'framer',
            'extractive_official',
            'cruel_official',
            'incompetent_harmful',
            'traitorous_actor',
            'mixed_or_disputed'
        )
    ),
    negative_talent_severity TEXT CHECK (
        negative_talent_severity IS NULL OR negative_talent_severity IN (
            'minor', 'material', 'major', 'historic'
        )
    ),
    negative_talent_version TEXT NOT NULL,
    source_profile_ref TEXT NOT NULL,
    source_row_fingerprint TEXT NOT NULL CHECK (
        source_row_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    semantic_fingerprint TEXT NOT NULL UNIQUE CHECK (
        semantic_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    review_status TEXT NOT NULL CHECK (review_status = 'human_frozen'),
    idempotency_key TEXT NOT NULL UNIQUE,
    import_batch_id TEXT REFERENCES v4_person_profile.import_batches (import_batch_id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_ref, snapshot_version),
    UNIQUE (person_ref, snapshot_version),
    UNIQUE (source_profile_ref, source_row_fingerprint),
    CHECK (
        (negative_talent_class IS NULL AND negative_talent_severity IS NULL)
        OR (negative_talent_class IS NOT NULL AND negative_talent_severity IS NOT NULL)
    )
);

CREATE TABLE v4_person_profile.person_profile_lineage (
    profile_ref TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    lineage_ref TEXT NOT NULL,
    lineage_kind TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_fingerprint TEXT CHECK (
        source_fingerprint IS NULL OR source_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    idempotency_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_ref, snapshot_version, lineage_ref),
    FOREIGN KEY (profile_ref, snapshot_version)
        REFERENCES v4_person_profile.person_profile_snapshots (
            profile_ref, snapshot_version
        )
);

CREATE TABLE v4_person_profile.ruler_team_window_snapshots (
    window_ref TEXT NOT NULL,
    ruler_ref TEXT NOT NULL REFERENCES v4_person_profile.person_identity_registry (person_ref),
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    date_precision TEXT NOT NULL CHECK (
        date_precision IN ('day', 'month', 'year', 'reign_year')
    ),
    window_policy_version TEXT NOT NULL,
    roster_version TEXT NOT NULL,
    profile_snapshot_version TEXT NOT NULL,
    semantic_fingerprint TEXT NOT NULL UNIQUE CHECK (
        semantic_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    status TEXT NOT NULL CHECK (status = 'human_frozen'),
    lineage JSONB NOT NULL CHECK (jsonb_typeof(lineage) = 'object'),
    idempotency_key TEXT NOT NULL UNIQUE,
    import_batch_id TEXT REFERENCES v4_person_profile.import_batches (import_batch_id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (window_ref, window_policy_version),
    UNIQUE (
        ruler_ref,
        window_start,
        window_end,
        date_precision,
        window_policy_version,
        roster_version,
        profile_snapshot_version
    )
);

CREATE TABLE v4_person_profile.ruler_team_window_members (
    window_ref TEXT NOT NULL,
    window_policy_version TEXT NOT NULL,
    person_ref TEXT NOT NULL REFERENCES v4_person_profile.person_identity_registry (person_ref),
    profile_ref TEXT NOT NULL,
    profile_snapshot_version TEXT NOT NULL,
    active_from TEXT NOT NULL,
    active_to TEXT NOT NULL,
    role_families JSONB NOT NULL CHECK (
        jsonb_typeof(role_families) = 'array'
        AND jsonb_array_length(role_families) > 0
    ),
    evidence_refs JSONB NOT NULL CHECK (
        jsonb_typeof(evidence_refs) = 'array'
        AND jsonb_array_length(evidence_refs) > 0
    ),
    semantic_fingerprint TEXT NOT NULL CHECK (
        semantic_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (window_ref, window_policy_version, person_ref),
    UNIQUE (window_ref, window_policy_version, semantic_fingerprint),
    FOREIGN KEY (window_ref, window_policy_version)
        REFERENCES v4_person_profile.ruler_team_window_snapshots (
            window_ref, window_policy_version
        ),
    FOREIGN KEY (profile_ref, profile_snapshot_version)
        REFERENCES v4_person_profile.person_profile_snapshots (
            profile_ref, snapshot_version
        )
);

CREATE INDEX person_profile_snapshots_person_idx
    ON v4_person_profile.person_profile_snapshots (person_ref, created_at);

CREATE INDEX ruler_team_window_snapshots_ruler_idx
    ON v4_person_profile.ruler_team_window_snapshots (
        ruler_ref, window_start, window_end
    );

CREATE TRIGGER person_profile_snapshots_immutable
BEFORE UPDATE OR DELETE ON v4_person_profile.person_profile_snapshots
FOR EACH ROW EXECUTE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation();

CREATE TRIGGER person_profile_lineage_immutable
BEFORE UPDATE OR DELETE ON v4_person_profile.person_profile_lineage
FOR EACH ROW EXECUTE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation();

CREATE TRIGGER ruler_team_window_snapshots_immutable
BEFORE UPDATE OR DELETE ON v4_person_profile.ruler_team_window_snapshots
FOR EACH ROW EXECUTE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation();

CREATE TRIGGER ruler_team_window_members_immutable
BEFORE UPDATE OR DELETE ON v4_person_profile.ruler_team_window_members
FOR EACH ROW EXECUTE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation();

REVOKE ALL ON ALL TABLES IN SCHEMA v4_person_profile FROM PUBLIC;

COMMIT;
