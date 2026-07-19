BEGIN;

ALTER TABLE v4_person_profile.person_profiles
    ADD COLUMN IF NOT EXISTS political_risk_profile JSONB NOT NULL DEFAULT '{
      "assessment_status": "insufficient_evidence",
      "severity": null,
      "risk_dynasties": [],
      "risk_domains": [],
      "findings": [],
      "source_refs": [],
      "confidence": 0,
      "review_status": "shadow_candidate",
      "version": "political-risk-v3"
    }'::jsonb;

ALTER TABLE v4_person_profile.person_profiles
    DROP CONSTRAINT IF EXISTS person_profiles_political_risk_profile_check;

ALTER TABLE v4_person_profile.person_profiles
    ADD CONSTRAINT person_profiles_political_risk_profile_check CHECK (
        jsonb_typeof(political_risk_profile) = 'object'
        AND political_risk_profile ?& ARRAY[
            'assessment_status', 'severity', 'risk_dynasties', 'risk_domains',
            'findings', 'source_refs', 'confidence', 'review_status', 'version'
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
    );

COMMENT ON COLUMN v4_person_profile.person_profiles.political_risk_profile IS
    '五档政治风险画像；按负面行为实际发生朝代记录risk_dynasties，不改写人才等级轴。';

COMMIT;
