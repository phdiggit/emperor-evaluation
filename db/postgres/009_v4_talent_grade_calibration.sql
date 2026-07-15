BEGIN;

CREATE TABLE v4_person_profile.talent_grade_calibrations (
    calibration_ref TEXT PRIMARY KEY,
    person_ref TEXT NOT NULL REFERENCES v4_person_profile.person_identity_registry (person_ref),
    base_profile_ref TEXT NOT NULL,
    base_snapshot_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    original_grade TEXT NOT NULL CHECK (
        original_grade IN ('historic', 'top', 'important', 'usable', 'ordinary')
    ),
    original_grade_version TEXT NOT NULL,
    calibrated_grade TEXT NOT NULL CHECK (
        calibrated_grade IN ('historic', 'top', 'important', 'usable', 'ordinary')
    ),
    decision TEXT NOT NULL CHECK (decision IN ('retained', 'downgraded')),
    gate_matrix JSONB NOT NULL CHECK (jsonb_typeof(gate_matrix) = 'object'),
    failure_codes JSONB NOT NULL CHECK (jsonb_typeof(failure_codes) = 'array'),
    review_basis TEXT NOT NULL,
    source_basis TEXT NOT NULL,
    semantic_fingerprint TEXT NOT NULL UNIQUE CHECK (
        semantic_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    review_status TEXT NOT NULL CHECK (review_status = 'human_frozen'),
    idempotency_key TEXT NOT NULL UNIQUE,
    import_batch_id TEXT NOT NULL REFERENCES v4_person_profile.import_batches (import_batch_id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (person_ref, policy_version),
    FOREIGN KEY (base_profile_ref, base_snapshot_version)
        REFERENCES v4_person_profile.person_profile_snapshots (
            profile_ref, snapshot_version
        )
);

CREATE INDEX talent_grade_calibrations_effective_idx
    ON v4_person_profile.talent_grade_calibrations (
        policy_version, calibrated_grade, review_status
    );

CREATE TRIGGER talent_grade_calibrations_immutable
BEFORE UPDATE OR DELETE ON v4_person_profile.talent_grade_calibrations
FOR EACH ROW EXECUTE FUNCTION v4_person_profile.reject_immutable_snapshot_mutation();

CREATE VIEW v4_person_profile.person_profile_current AS
SELECT
    catalog.*,
    catalog.talent_grade AS inherited_talent_grade,
    COALESCE(calibration.calibrated_grade, catalog.talent_grade)
        AS effective_talent_grade,
    calibration.policy_version AS talent_calibration_policy_version,
    calibration.decision AS talent_calibration_decision,
    calibration.review_basis AS talent_calibration_basis
FROM v4_person_profile.person_profile_catalog AS catalog
LEFT JOIN v4_person_profile.talent_grade_calibrations AS calibration
  ON calibration.person_ref = catalog.person_ref
 AND calibration.base_profile_ref = catalog.profile_ref
 AND calibration.base_snapshot_version = catalog.snapshot_version
 AND calibration.review_status = 'human_frozen';

REVOKE ALL ON v4_person_profile.talent_grade_calibrations FROM PUBLIC;
REVOKE ALL ON v4_person_profile.person_profile_current FROM PUBLIC;

COMMIT;
