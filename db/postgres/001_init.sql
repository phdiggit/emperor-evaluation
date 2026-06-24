CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- PostgreSQL base schema contract for the source-data platform.
-- Logical-to-physical name mapping:
--   source_documents -> src_docs
--   source_passages -> passages
--   evidence_source_links -> evd_src_links
--   candidate_matches -> cand_matches
--   evidence_cards -> evd_cards
--   evidence_clusters -> clusters
-- This file defines tables and constraints only; it does not start services,
-- implement a migration runner, dispatch workers, or migrate JSONL.

CREATE TABLE persons (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT,
    dynasty TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT person_code_uk UNIQUE (code),
    CONSTRAINT person_status_ck CHECK (status IN ('active', 'inactive', 'merged'))
);

CREATE TABLE person_aliases (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id BIGINT NOT NULL,
    alias TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    norm_alias TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT palias_person_fk FOREIGN KEY (person_id) REFERENCES persons(id),
    CONSTRAINT palias_unique_uk UNIQUE (person_id, alias_type, norm_alias),
    CONSTRAINT palias_status_ck CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE subitems (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    item_code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT subitem_code_uk UNIQUE (code),
    CONSTRAINT subitem_status_ck CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE src_hosts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    trust_class TEXT,
    base_url TEXT,
    adapter TEXT,
    rate_limit INTEGER,
    concurrency_limit INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT shost_code_uk UNIQUE (code),
    CONSTRAINT shost_status_ck CHECK (status IN ('active', 'inactive', 'blocked'))
);

CREATE TABLE jobs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    idem_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 100,
    next_run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempt_count SMALLINT NOT NULL DEFAULT 0,
    max_attempts SMALLINT NOT NULL DEFAULT 3,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    lease_until TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT job_code_uk UNIQUE (code),
    CONSTRAINT job_idem_uk UNIQUE (idem_key),
    CONSTRAINT job_kind_ck CHECK (kind IN ('search', 'fetch', 'parse', 'match', 'draft', 'review_notify')),
    CONSTRAINT job_status_ck CHECK (status IN ('queued', 'ready', 'running', 'retry_wait', 'succeeded', 'failed', 'dead_lettered', 'blocked', 'cancelled')),
    CONSTRAINT job_attempts_ck CHECK (attempt_count >= 0 AND max_attempts > 0)
);

CREATE TABLE job_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    job_id BIGINT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    worker_id TEXT,
    status TEXT NOT NULL,
    input_hash TEXT,
    output_hash TEXT,
    error_type TEXT,
    error_msg TEXT,
    trace_id TEXT,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT jrun_code_uk UNIQUE (code),
    CONSTRAINT jrun_job_fk FOREIGN KEY (job_id) REFERENCES jobs(id),
    CONSTRAINT jrun_status_ck CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled'))
);

CREATE TABLE job_deps (
    job_id BIGINT NOT NULL,
    depends_on_job_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT jdep_pk PRIMARY KEY (job_id, depends_on_job_id),
    CONSTRAINT jdep_job_fk FOREIGN KEY (job_id) REFERENCES jobs(id),
    CONSTRAINT jdep_dep_fk FOREIGN KEY (depends_on_job_id) REFERENCES jobs(id),
    CONSTRAINT jdep_self_ck CHECK (job_id <> depends_on_job_id),
    CONSTRAINT jdep_status_ck CHECK (status IN ('waiting', 'satisfied', 'blocked'))
);

CREATE TABLE outbox (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id BIGINT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_publish_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    attempts SMALLINT NOT NULL DEFAULT 0,
    last_error TEXT,
    CONSTRAINT outbox_code_uk UNIQUE (code),
    CONSTRAINT outbox_attempts_ck CHECK (attempts >= 0)
);

CREATE TABLE review_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    kind TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority SMALLINT NOT NULL DEFAULT 100,
    reason TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT review_code_uk UNIQUE (code),
    CONSTRAINT review_status_ck CHECK (status IN ('open', 'in_review', 'resolved', 'rejected', 'deferred'))
);

CREATE TABLE src_docs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    host_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    work_code TEXT,
    volume TEXT,
    canon_url TEXT,
    canon_url_hash TEXT NOT NULL,
    source_type TEXT,
    author TEXT,
    dynasty TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sdoc_code_uk UNIQUE (code),
    CONSTRAINT sdoc_host_fk FOREIGN KEY (host_id) REFERENCES src_hosts(id),
    CONSTRAINT sdoc_url_uk UNIQUE (host_id, canon_url_hash),
    CONSTRAINT sdoc_status_ck CHECK (status IN ('active', 'inactive', 'blocked'))
);

CREATE TABLE doc_revs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    doc_id BIGINT NOT NULL,
    fetch_job_id BIGINT,
    sha256 TEXT NOT NULL,
    object_key TEXT NOT NULL,
    mime TEXT,
    encoding TEXT,
    size_bytes BIGINT,
    etag TEXT,
    last_modified TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fetch_status TEXT NOT NULL DEFAULT 'fetched',
    parser_ver TEXT,
    norm_ver TEXT,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT drev_code_uk UNIQUE (code),
    CONSTRAINT drev_doc_fk FOREIGN KEY (doc_id) REFERENCES src_docs(id),
    CONSTRAINT drev_job_fk FOREIGN KEY (fetch_job_id) REFERENCES jobs(id),
    CONSTRAINT drev_doc_sha_uk UNIQUE (doc_id, sha256),
    CONSTRAINT drev_fetch_ck CHECK (fetch_status IN ('queued', 'fetched', 'failed', 'skipped')),
    CONSTRAINT drev_size_ck CHECK (size_bytes IS NULL OR size_bytes >= 0)
);

CREATE TABLE passages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    rev_id BIGINT NOT NULL,
    seq INTEGER NOT NULL,
    location TEXT,
    raw_text TEXT NOT NULL,
    norm_text TEXT NOT NULL,
    token_text TEXT,
    search_vec TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', coalesce(token_text, norm_text, ''))) STORED,
    norm_ver TEXT,
    token_ver TEXT,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT passage_code_uk UNIQUE (code),
    CONSTRAINT passage_rev_fk FOREIGN KEY (rev_id) REFERENCES doc_revs(id),
    CONSTRAINT passage_rev_seq_uk UNIQUE (rev_id, seq),
    CONSTRAINT passage_seq_ck CHECK (seq > 0)
);

CREATE TABLE passage_people (
    passage_id BIGINT NOT NULL,
    person_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    confidence NUMERIC(5,4),
    alias_hit TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending',
    note TEXT,
    CONSTRAINT ppeople_pk PRIMARY KEY (passage_id, person_id, role),
    CONSTRAINT ppeople_passage_fk FOREIGN KEY (passage_id) REFERENCES passages(id),
    CONSTRAINT ppeople_person_fk FOREIGN KEY (person_id) REFERENCES persons(id),
    CONSTRAINT ppeople_conf_ck CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT ppeople_review_ck CHECK (review_status IN ('pending', 'accepted', 'rejected', 'needs_review'))
);

CREATE TABLE query_profiles (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    subitem_id BIGINT NOT NULL,
    person_id BIGINT,
    scope TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT qprof_code_uk UNIQUE (code),
    CONSTRAINT qprof_subitem_fk FOREIGN KEY (subitem_id) REFERENCES subitems(id),
    CONSTRAINT qprof_person_fk FOREIGN KEY (person_id) REFERENCES persons(id),
    CONSTRAINT qprof_status_ck CHECK (status IN ('active', 'inactive', 'draft'))
);

CREATE TABLE search_tasks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    query_profile_id BIGINT NOT NULL,
    person_id BIGINT,
    subitem_id BIGINT NOT NULL,
    search_mode TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    query_text TEXT NOT NULL,
    idem_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority SMALLINT NOT NULL DEFAULT 100,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stask_code_uk UNIQUE (code),
    CONSTRAINT stask_qprof_fk FOREIGN KEY (query_profile_id) REFERENCES query_profiles(id),
    CONSTRAINT stask_person_fk FOREIGN KEY (person_id) REFERENCES persons(id),
    CONSTRAINT stask_subitem_fk FOREIGN KEY (subitem_id) REFERENCES subitems(id),
    CONSTRAINT stask_idem_uk UNIQUE (idem_key),
    CONSTRAINT stask_status_ck CHECK (status IN ('queued', 'ready', 'running', 'retry_wait', 'succeeded', 'failed', 'blocked', 'cancelled'))
);

CREATE TABLE search_hits (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    search_task_id BIGINT NOT NULL,
    host_id BIGINT,
    fetch_job_id BIGINT,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    rank INTEGER,
    status TEXT NOT NULL DEFAULT 'new',
    reject_reason TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT shit_code_uk UNIQUE (code),
    CONSTRAINT shit_task_fk FOREIGN KEY (search_task_id) REFERENCES search_tasks(id),
    CONSTRAINT shit_host_fk FOREIGN KEY (host_id) REFERENCES src_hosts(id),
    CONSTRAINT shit_job_fk FOREIGN KEY (fetch_job_id) REFERENCES jobs(id),
    CONSTRAINT shit_url_uk UNIQUE (search_task_id, url_hash),
    CONSTRAINT shit_status_ck CHECK (status IN ('new', 'accepted', 'rejected', 'fetched', 'blocked')),
    CONSTRAINT shit_rank_ck CHECK (rank IS NULL OR rank > 0)
);

CREATE TABLE cand_matches (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    search_task_id BIGINT NOT NULL,
    passage_id BIGINT NOT NULL,
    matcher_ver TEXT NOT NULL,
    score NUMERIC(5,4),
    status TEXT NOT NULL DEFAULT 'candidate',
    match_role TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cmatch_code_uk UNIQUE (code),
    CONSTRAINT cmatch_task_fk FOREIGN KEY (search_task_id) REFERENCES search_tasks(id),
    CONSTRAINT cmatch_passage_fk FOREIGN KEY (passage_id) REFERENCES passages(id),
    CONSTRAINT cmatch_task_pass_uk UNIQUE (search_task_id, passage_id, matcher_ver),
    CONSTRAINT cmatch_score_ck CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
    CONSTRAINT cmatch_status_ck CHECK (status IN ('candidate', 'accepted', 'rejected', 'needs_review', 'drafted'))
);

CREATE TABLE evd_cards (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    person_id BIGINT NOT NULL,
    subitem_id BIGINT NOT NULL,
    polarity TEXT NOT NULL,
    strength SMALLINT NOT NULL,
    human_level TEXT,
    quote_short TEXT NOT NULL,
    interpretation TEXT NOT NULL,
    cross_item_split TEXT,
    scoring_effect TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending',
    adjudication_status TEXT NOT NULL DEFAULT 'not_started',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT evd_code_uk UNIQUE (code),
    CONSTRAINT evd_person_fk FOREIGN KEY (person_id) REFERENCES persons(id),
    CONSTRAINT evd_subitem_fk FOREIGN KEY (subitem_id) REFERENCES subitems(id),
    CONSTRAINT evd_polarity_ck CHECK (polarity IN ('positive', 'negative')),
    CONSTRAINT evd_strength_ck CHECK (strength IN (1, 2, 3, 4)),
    CONSTRAINT evd_verify_ck CHECK (verification_status IN ('pending', 'verified', 'rejected', 'needs_review')),
    CONSTRAINT evd_adjud_ck CHECK (adjudication_status IN ('not_started', 'pending', 'accepted', 'rejected', 'deferred'))
);

CREATE TABLE evd_src_links (
    evd_id BIGINT NOT NULL,
    passage_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    span_start INTEGER NOT NULL DEFAULT 0,
    span_end INTEGER,
    confidence NUMERIC(5,4),
    review_status TEXT NOT NULL DEFAULT 'pending',
    note TEXT,
    CONSTRAINT eslink_pk PRIMARY KEY (evd_id, passage_id, role, span_start),
    CONSTRAINT eslink_evd_fk FOREIGN KEY (evd_id) REFERENCES evd_cards(id),
    CONSTRAINT eslink_passage_fk FOREIGN KEY (passage_id) REFERENCES passages(id),
    CONSTRAINT eslink_span_ck CHECK (span_start >= 0 AND (span_end IS NULL OR span_end >= span_start)),
    CONSTRAINT eslink_conf_ck CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT eslink_review_ck CHECK (review_status IN ('pending', 'accepted', 'rejected', 'needs_review'))
);

CREATE TABLE clusters (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    person_id BIGINT NOT NULL,
    subitem_id BIGINT NOT NULL,
    polarity TEXT,
    candidate_strength SMALLINT,
    summary TEXT,
    adjudication_status TEXT NOT NULL DEFAULT 'not_started',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cluster_code_uk UNIQUE (code),
    CONSTRAINT cluster_person_fk FOREIGN KEY (person_id) REFERENCES persons(id),
    CONSTRAINT cluster_subitem_fk FOREIGN KEY (subitem_id) REFERENCES subitems(id),
    CONSTRAINT cluster_polarity_ck CHECK (polarity IS NULL OR polarity IN ('positive', 'negative')),
    CONSTRAINT cluster_strength_ck CHECK (candidate_strength IS NULL OR candidate_strength IN (1, 2, 3, 4)),
    CONSTRAINT cluster_adjud_ck CHECK (adjudication_status IN ('not_started', 'pending', 'accepted', 'rejected', 'deferred'))
);

CREATE TABLE cluster_evd (
    cluster_id BIGINT NOT NULL,
    evd_id BIGINT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    CONSTRAINT clusterevd_pk PRIMARY KEY (cluster_id, evd_id),
    CONSTRAINT clusterevd_cluster_fk FOREIGN KEY (cluster_id) REFERENCES clusters(id),
    CONSTRAINT clusterevd_evd_fk FOREIGN KEY (evd_id) REFERENCES evd_cards(id),
    CONSTRAINT clusterevd_role_ck CHECK (role IN ('member', 'primary', 'context', 'weakening'))
);

CREATE TABLE imports (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    tool_version TEXT,
    input_hash TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT import_code_uk UNIQUE (code),
    CONSTRAINT import_status_ck CHECK (status IN ('running', 'succeeded', 'failed', 'dry_run')),
    CONSTRAINT import_rows_ck CHECK (row_count >= 0)
);

CREATE TABLE import_rows (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL,
    import_id BIGINT NOT NULL,
    source_file TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    payload_hash TEXT,
    import_status TEXT NOT NULL,
    target_table TEXT,
    target_id BIGINT,
    error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT irow_code_uk UNIQUE (code),
    CONSTRAINT irow_import_fk FOREIGN KEY (import_id) REFERENCES imports(id),
    CONSTRAINT irow_line_uk UNIQUE (import_id, source_file, line_no),
    CONSTRAINT irow_line_ck CHECK (line_no > 0),
    CONSTRAINT irow_status_ck CHECK (import_status IN ('pending', 'accepted', 'rejected', 'skipped', 'error'))
);

CREATE INDEX palias_person_idx ON person_aliases (person_id);
CREATE INDEX palias_norm_idx ON person_aliases (norm_alias);
CREATE INDEX subitem_item_idx ON subitems (item_code);
CREATE INDEX sdoc_host_idx ON src_docs (host_id);
CREATE INDEX sdoc_work_idx ON src_docs (work_code, volume);
CREATE INDEX drev_doc_fetch_idx ON doc_revs (doc_id, fetched_at DESC);
CREATE INDEX drev_job_idx ON doc_revs (fetch_job_id);
CREATE INDEX passage_rev_idx ON passages (rev_id);
CREATE INDEX passage_search_gin ON passages USING GIN (search_vec);
CREATE INDEX passage_norm_trgm ON passages USING GIN (norm_text gin_trgm_ops);
CREATE INDEX ppeople_person_idx ON passage_people (person_id);
CREATE INDEX qprof_subitem_idx ON query_profiles (subitem_id);
CREATE INDEX qprof_person_idx ON query_profiles (person_id);
CREATE INDEX stask_qprof_idx ON search_tasks (query_profile_id);
CREATE INDEX stask_person_idx ON search_tasks (person_id);
CREATE INDEX stask_subitem_idx ON search_tasks (subitem_id);
CREATE INDEX stask_ready_idx ON search_tasks (priority, created_at) WHERE status IN ('ready', 'retry_wait');
CREATE INDEX shit_task_idx ON search_hits (search_task_id);
CREATE INDEX shit_host_url_idx ON search_hits (host_id, url_hash);
CREATE INDEX shit_job_idx ON search_hits (fetch_job_id);
CREATE INDEX cmatch_task_status_idx ON cand_matches (search_task_id, status, score DESC);
CREATE INDEX cmatch_passage_idx ON cand_matches (passage_id);
CREATE INDEX evd_person_idx ON evd_cards (person_id);
CREATE INDEX evd_subitem_idx ON evd_cards (subitem_id);
CREATE INDEX evd_scope_idx ON evd_cards (person_id, subitem_id, polarity, strength);
CREATE INDEX eslink_passage_role_idx ON evd_src_links (passage_id, role);
CREATE INDEX cluster_person_idx ON clusters (person_id);
CREATE INDEX cluster_subitem_idx ON clusters (subitem_id);
CREATE INDEX cluster_scope_idx ON clusters (person_id, subitem_id, polarity, candidate_strength);
CREATE INDEX clusterevd_evd_idx ON cluster_evd (evd_id);
CREATE INDEX review_target_idx ON review_items (target_table, target_id);
CREATE INDEX review_status_idx ON review_items (status, priority);
CREATE INDEX job_ready_idx ON jobs (next_run_at, priority) WHERE status IN ('ready', 'retry_wait');
CREATE INDEX job_status_idx ON jobs (status, kind);
CREATE INDEX jrun_job_idx ON job_runs (job_id, started_at DESC);
CREATE INDEX jdep_dep_idx ON job_deps (depends_on_job_id);
CREATE INDEX outbox_ready_idx ON outbox (next_publish_at, created_at) WHERE published_at IS NULL;
CREATE INDEX import_status_idx ON imports (status, started_at);
CREATE INDEX irow_import_idx ON import_rows (import_id);
CREATE INDEX irow_target_idx ON import_rows (target_table, target_id);

COMMENT ON TABLE src_docs IS 'Physical table for logical source_documents.';
COMMENT ON TABLE passages IS 'Physical table for logical source_passages.';
COMMENT ON TABLE evd_src_links IS 'Physical table for logical evidence_source_links.';
COMMENT ON TABLE cand_matches IS 'Physical table for logical candidate_matches.';
COMMENT ON TABLE evd_cards IS 'Physical table for logical evidence_cards.';
COMMENT ON TABLE clusters IS 'Physical table for logical evidence_clusters.';
COMMENT ON TABLE outbox IS 'Transactional event outbox; RabbitMQ carries only light job or event messages.';
COMMENT ON TABLE imports IS 'Import batch audit header for future JSONL dry-run and frozen import workflows.';
COMMENT ON TABLE import_rows IS 'Per-row import audit for future JSONL dry-run checks.';
