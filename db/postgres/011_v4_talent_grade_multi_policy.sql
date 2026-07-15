BEGIN;

ALTER TABLE v4_person_profile.talent_grade_calibrations
    DROP CONSTRAINT IF EXISTS talent_grade_calibrations_decision_check;

ALTER TABLE v4_person_profile.talent_grade_calibrations
    ADD CONSTRAINT talent_grade_calibrations_decision_check
    CHECK (decision IN ('retained', 'downgraded', 'upgraded'));

DROP VIEW v4_person_profile.person_profile_current;

CREATE VIEW v4_person_profile.person_profile_current AS
SELECT
    catalog.canonical_name,
    COALESCE(calibration.calibrated_grade, catalog.talent_grade)
        AS effective_talent_grade,
    catalog.negative_risk_status,
    COALESCE(calibration.review_basis, catalog.talent_grade_basis)
        AS effective_talent_grade_basis,
    catalog.negative_talent_basis,
    catalog.negative_talent_class,
    catalog.negative_talent_severity,
    catalog.talent_grade AS inherited_talent_grade,
    catalog.talent_grade_basis AS inherited_talent_grade_basis,
    calibration.policy_version AS talent_calibration_policy_version,
    calibration.decision AS talent_calibration_decision,
    catalog.capability_domains,
    catalog.historical_context,
    catalog.profile_ref,
    catalog.snapshot_version,
    catalog.person_ref,
    catalog.talent_grade_version,
    catalog.talent_grade_confidence,
    catalog.talent_authority_consensus,
    catalog.talent_performance_support,
    catalog.talent_evidence_coverage,
    catalog.negative_talent_version,
    catalog.negative_talent_confidence,
    catalog.negative_authority_consensus,
    catalog.negative_fact_support,
    catalog.negative_evidence_coverage,
    catalog.source_profile_ref,
    catalog.review_status,
    catalog.created_at
FROM v4_person_profile.person_profile_catalog AS catalog
LEFT JOIN LATERAL (
    SELECT candidate.calibrated_grade,
           candidate.policy_version,
           candidate.decision,
           candidate.review_basis
    FROM v4_person_profile.talent_grade_calibrations AS candidate
    WHERE candidate.person_ref = catalog.person_ref
      AND candidate.base_profile_ref = catalog.profile_ref
      AND candidate.base_snapshot_version = catalog.snapshot_version
      AND candidate.review_status = 'human_frozen'
    ORDER BY candidate.created_at DESC, candidate.policy_version DESC
    LIMIT 1
) AS calibration ON TRUE;

REVOKE ALL ON v4_person_profile.person_profile_current FROM PUBLIC;

COMMIT;
