BEGIN;

ALTER TABLE v4_claim_extractor.requests
    DROP CONSTRAINT IF EXISTS requests_result_status_check;

ALTER TABLE v4_claim_extractor.requests
    ADD CONSTRAINT requests_result_status_check
    CHECK (
        result_status IN (
            'succeeded',
            'succeeded_with_gaps',
            'succeeded_no_relevant_facts'
        )
    );

COMMIT;
