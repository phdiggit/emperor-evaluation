BEGIN;

CREATE SCHEMA IF NOT EXISTS v4_source_cache;

CREATE TABLE v4_source_cache.requests (
    idempotency_key TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    input_fingerprint TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK (contract_version = 'source-cache-contract-v2'),
    source_policy_version TEXT NOT NULL,
    request_mode TEXT NOT NULL CHECK (request_mode IN ('ensure', 'supplement', 'refresh')),
    result_status TEXT NOT NULL CHECK (result_status IN ('succeeded', 'succeeded_with_warnings')),
    output_fingerprint TEXT NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE v4_source_cache.document_revisions (
    document_cache_id TEXT NOT NULL,
    content_version TEXT NOT NULL,
    work_identity TEXT NOT NULL,
    edition_identity TEXT NOT NULL,
    title TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_role TEXT NOT NULL,
    source_host TEXT NOT NULL,
    source_document_ref TEXT NOT NULL,
    revision_ref TEXT NOT NULL,
    revision_timestamp TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    raw_content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_cache_id, content_version)
);

CREATE TABLE v4_source_cache.passages (
    passage_id TEXT PRIMARY KEY,
    document_cache_id TEXT NOT NULL,
    document_content_version TEXT NOT NULL,
    section_id TEXT NOT NULL,
    span_start INTEGER NOT NULL CHECK (span_start >= 0),
    span_end INTEGER NOT NULL CHECK (span_end > span_start),
    passage_kind TEXT NOT NULL CHECK (passage_kind IN ('atomic', 'context', 'navigation_noise')),
    content_hash TEXT NOT NULL,
    window_policy_version TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_cache_id, document_content_version)
        REFERENCES v4_source_cache.document_revisions (document_cache_id, content_version)
);

CREATE TABLE v4_source_cache.request_documents (
    idempotency_key TEXT NOT NULL REFERENCES v4_source_cache.requests (idempotency_key),
    document_cache_id TEXT NOT NULL,
    document_content_version TEXT NOT NULL,
    PRIMARY KEY (idempotency_key, document_cache_id, document_content_version),
    FOREIGN KEY (document_cache_id, document_content_version)
        REFERENCES v4_source_cache.document_revisions (document_cache_id, content_version)
);

CREATE TABLE v4_source_cache.request_passages (
    idempotency_key TEXT NOT NULL REFERENCES v4_source_cache.requests (idempotency_key),
    passage_id TEXT NOT NULL REFERENCES v4_source_cache.passages (passage_id),
    PRIMARY KEY (idempotency_key, passage_id)
);

COMMIT;
