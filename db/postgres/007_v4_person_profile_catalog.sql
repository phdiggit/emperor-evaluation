BEGIN;

CREATE TABLE v4_person_profile.person_profile_catalog (
    profile_ref TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    person_ref TEXT NOT NULL REFERENCES v4_person_profile.person_identity_registry (person_ref),
    canonical_name TEXT NOT NULL,
    historical_context TEXT NOT NULL,
    talent_grade TEXT NOT NULL CHECK (
        talent_grade IN ('historic', 'top', 'important', 'usable', 'ordinary')
    ),
    talent_grade_version TEXT NOT NULL,
    talent_grade_confidence NUMERIC(6, 5) NOT NULL CHECK (
        talent_grade_confidence >= 0 AND talent_grade_confidence <= 1
    ),
    talent_grade_basis TEXT NOT NULL,
    talent_authority_consensus TEXT NOT NULL,
    talent_performance_support TEXT NOT NULL,
    talent_evidence_coverage TEXT NOT NULL,
    negative_risk_status TEXT NOT NULL CHECK (
        negative_risk_status IN ('established', 'no_established_class')
    ),
    negative_talent_class TEXT CHECK (
        negative_talent_class IS NULL OR negative_talent_class IN (
            'sycophant', 'favorite', 'power_abuser', 'framer',
            'extractive_official', 'cruel_official', 'incompetent_harmful',
            'traitorous_actor', 'mixed_or_disputed'
        )
    ),
    negative_talent_severity TEXT CHECK (
        negative_talent_severity IS NULL OR negative_talent_severity IN (
            'minor', 'material', 'major', 'historic'
        )
    ),
    negative_talent_basis TEXT NOT NULL,
    negative_talent_version TEXT NOT NULL,
    negative_talent_confidence NUMERIC(6, 5) NOT NULL CHECK (
        negative_talent_confidence >= 0 AND negative_talent_confidence <= 1
    ),
    negative_authority_consensus TEXT NOT NULL,
    negative_fact_support TEXT NOT NULL,
    negative_evidence_coverage TEXT NOT NULL,
    capability_domains JSONB NOT NULL CHECK (
        jsonb_typeof(capability_domains) = 'array'
        AND jsonb_array_length(capability_domains) > 0
    ),
    source_profile_ref TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status = 'human_frozen'),
    idempotency_key TEXT NOT NULL UNIQUE,
    import_batch_id TEXT REFERENCES v4_person_profile.import_batches (import_batch_id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_ref, snapshot_version),
    UNIQUE (person_ref, snapshot_version),
    FOREIGN KEY (profile_ref, snapshot_version)
        REFERENCES v4_person_profile.person_profile_snapshots (
            profile_ref, snapshot_version
        ),
    CHECK (
        (negative_talent_class IS NULL AND negative_talent_severity IS NULL
            AND negative_risk_status = 'no_established_class')
        OR (negative_talent_class IS NOT NULL AND negative_talent_severity IS NOT NULL
            AND negative_risk_status = 'established')
    )
);

CREATE INDEX person_profile_catalog_name_idx
    ON v4_person_profile.person_profile_catalog (canonical_name, historical_context);

CREATE INDEX person_profile_catalog_talent_idx
    ON v4_person_profile.person_profile_catalog (
        talent_grade_version, talent_grade, review_status
    );

CREATE INDEX person_profile_catalog_negative_idx
    ON v4_person_profile.person_profile_catalog (
        negative_talent_version, negative_talent_class,
        negative_talent_severity, review_status
    );

CREATE TRIGGER person_profile_catalog_immutable
BEFORE UPDATE OR DELETE ON v4_person_profile.person_profile_catalog
FOR EACH ROW EXECUTE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation();

REVOKE ALL ON v4_person_profile.person_profile_catalog FROM PUBLIC;

COMMIT;
