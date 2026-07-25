BEGIN;

CREATE SCHEMA IF NOT EXISTS v4_person_profile;
REVOKE ALL ON SCHEMA v4_person_profile FROM PUBLIC;

CREATE TABLE v4_person_profile.person_identity_registry (
    person_ref TEXT PRIMARY KEY CHECK (person_ref ~ '^PER-V4-[0-9A-F]{12}$'),
    canonical_name TEXT NOT NULL,
    historical_context TEXT NOT NULL,
    identity_fingerprint TEXT NOT NULL UNIQUE CHECK (
        identity_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    identity_status TEXT NOT NULL CHECK (
        identity_status IN ('candidate', 'active', 'merged', 'retired')
    ),
    supersedes_person_ref TEXT REFERENCES v4_person_profile.person_identity_registry (person_ref),
    idempotency_key TEXT NOT NULL UNIQUE,
    source_import_batch_ref TEXT,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (supersedes_person_ref IS NULL OR supersedes_person_ref <> person_ref)
);

CREATE TABLE v4_person_profile.person_profiles (
    person_ref TEXT PRIMARY KEY
        REFERENCES v4_person_profile.person_identity_registry (person_ref),
    canonical_name TEXT NOT NULL,
    historical_context TEXT NOT NULL,
    talent_grade TEXT NOT NULL CHECK (
        talent_grade IN ('historic', 'top', 'important', 'usable', 'ordinary')
    ),
    talent_grade_basis TEXT NOT NULL,
    talent_grade_confidence NUMERIC(6, 5) NOT NULL CHECK (
        talent_grade_confidence >= 0 AND talent_grade_confidence <= 1
    ),
    talent_authority_consensus TEXT NOT NULL,
    talent_performance_support TEXT NOT NULL,
    talent_evidence_coverage TEXT NOT NULL,
    negative_risk_status TEXT NOT NULL CHECK (
        negative_risk_status IN ('established', 'no_established_class')
    ),
    negative_talent_class TEXT,
    negative_talent_severity TEXT,
    negative_talent_basis TEXT NOT NULL,
    negative_talent_confidence NUMERIC(6, 5) NOT NULL CHECK (
        negative_talent_confidence >= 0 AND negative_talent_confidence <= 1
    ),
    negative_authority_consensus TEXT NOT NULL,
    negative_fact_support TEXT NOT NULL,
    negative_evidence_coverage TEXT NOT NULL,
    political_risk_profile JSONB NOT NULL DEFAULT '{
      "assessment_status": "insufficient_evidence",
      "severity": null,
      "risk_dynasties": [],
      "risk_domains": [],
      "findings": [],
      "source_refs": [],
      "confidence": 0,
      "review_status": "shadow_candidate"
    }'::jsonb CHECK (
        jsonb_typeof(political_risk_profile) = 'object'
        AND political_risk_profile ?& ARRAY[
            'assessment_status', 'severity', 'risk_dynasties', 'risk_domains',
            'findings', 'source_refs', 'confidence', 'review_status'
        ]
        AND political_risk_profile->>'assessment_status' IN (
            'established', 'below_floor', 'reviewed_no_material_risk',
            'insufficient_evidence'
        )
        AND jsonb_typeof(political_risk_profile->'risk_dynasties') = 'array'
        AND jsonb_typeof(political_risk_profile->'risk_domains') = 'array'
        AND jsonb_typeof(political_risk_profile->'findings') = 'array'
        AND jsonb_typeof(political_risk_profile->'source_refs') = 'array'
        AND (
            (
                political_risk_profile->>'assessment_status' = 'established'
                AND political_risk_profile->>'severity' IN (
                    'limited', 'material', 'serious', 'major', 'systemic'
                )
                AND jsonb_array_length(political_risk_profile->'findings') > 0
            )
            OR (
                political_risk_profile->>'assessment_status' <> 'established'
                AND political_risk_profile->'severity' = 'null'::jsonb
            )
        )
    ),
    capability_domains JSONB NOT NULL CHECK (
        jsonb_typeof(capability_domains) = 'array'
    ),
    profile_ref TEXT NOT NULL UNIQUE,
    source_profile_ref TEXT NOT NULL CHECK (
        source_profile_ref ~ '^SPR-V4-[0-9A-F]{16}$'
    ),
    review_status TEXT NOT NULL CHECK (review_status = 'human_frozen'),
    source_created_at TIMESTAMPTZ NOT NULL,
    CHECK (
        (negative_talent_class IS NULL AND negative_talent_severity IS NULL
            AND negative_risk_status = 'no_established_class')
        OR (negative_talent_class IS NOT NULL AND negative_talent_severity IS NOT NULL
            AND negative_risk_status = 'established')
    ),
    CHECK (
        NOT (talent_grade_basis ~ '[一-龥]' AND talent_grade_basis ~ '[A-Za-z]')
        AND NOT (negative_talent_basis ~ '[一-龥]' AND negative_talent_basis ~ '[A-Za-z]')
    )
);

CREATE INDEX person_profiles_name_idx
    ON v4_person_profile.person_profiles (canonical_name, historical_context);
CREATE INDEX person_profiles_talent_idx
    ON v4_person_profile.person_profiles (
        talent_grade, review_status
    );

COMMENT ON SCHEMA v4_person_profile IS 'V4 当前人物身份与唯一有效人物画像。';
COMMENT ON TABLE v4_person_profile.person_identity_registry IS 'V4 当前规范人物身份注册表。';
COMMENT ON TABLE v4_person_profile.person_profiles IS '当前工作流唯一人物画像表；人才等级字段已经合并所有有效校准。';
COMMENT ON COLUMN v4_person_profile.person_profiles.talent_grade IS '当前唯一有效人才等级。';
COMMENT ON COLUMN v4_person_profile.person_profiles.political_risk_profile IS '五档政治风险画像；按负面行为实际发生朝代记录risk_dynasties，不改写人才等级轴。';

REVOKE ALL ON v4_person_profile.person_identity_registry FROM PUBLIC;
REVOKE ALL ON v4_person_profile.person_profiles FROM PUBLIC;

COMMIT;
