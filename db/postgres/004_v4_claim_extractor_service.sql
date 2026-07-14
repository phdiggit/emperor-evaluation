BEGIN;

CREATE SCHEMA IF NOT EXISTS v4_claim_extractor;

CREATE TABLE v4_claim_extractor.requests (
    idempotency_key TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    input_fingerprint TEXT NOT NULL,
    profile_code TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK (contract_version = 'assertion-extraction-contract-v2'),
    result_status TEXT NOT NULL CHECK (
        result_status IN (
            'succeeded',
            'succeeded_with_gaps',
            'succeeded_no_relevant_facts'
        )
    ),
    output_fingerprint TEXT NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE v4_claim_extractor.assertion_drafts (
    assertion_code TEXT PRIMARY KEY,
    source_passage_ref TEXT NOT NULL,
    assertion_semantic_key TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_passage_ref, assertion_semantic_key, input_fingerprint)
);

CREATE TABLE v4_claim_extractor.request_assertions (
    idempotency_key TEXT NOT NULL REFERENCES v4_claim_extractor.requests (idempotency_key),
    assertion_code TEXT NOT NULL REFERENCES v4_claim_extractor.assertion_drafts (assertion_code),
    PRIMARY KEY (idempotency_key, assertion_code)
);

CREATE TABLE v4_claim_extractor.jobs (
    job_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    input_fingerprint TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    request_payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ready', 'running', 'retry_wait', 'succeeded', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    output_fingerprint TEXT,
    result_payload JSONB,
    error_type TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((status = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (status <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL))
);

CREATE INDEX claim_extractor_jobs_runnable_idx
    ON v4_claim_extractor.jobs (priority DESC, next_attempt_at, created_at)
    WHERE status IN ('ready', 'retry_wait');

CREATE INDEX claim_extractor_jobs_expired_lease_idx
    ON v4_claim_extractor.jobs (lease_expires_at) WHERE status = 'running';

CREATE TABLE v4_claim_extractor.job_runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES v4_claim_extractor.jobs (job_id),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    worker_id TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'lease_expired')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    output_fingerprint TEXT,
    result_payload JSONB,
    error_type TEXT,
    error_message TEXT,
    UNIQUE (job_id, attempt_number)
);

COMMIT;
