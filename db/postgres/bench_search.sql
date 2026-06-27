-- Optional PostgreSQL search benchmark contract.
--
-- The source_ingest benchmark runner was removed by #354. This SQL remains as
-- a historical/reference search-shape contract only.
--
-- This file is intentionally isolated from 001_init.sql. It uses temporary
-- objects only and is not a migration, production schema change, worker hook,
-- JSONL writer, or evidence/score/rank generator.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TEMP TABLE bench_passages (
    passage_code text PRIMARY KEY,
    raw_text text NOT NULL,
    norm_text text NOT NULL,
    token_text text NOT NULL,
    search_vec tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(token_text, norm_text, ''))
    ) STORED
);

CREATE INDEX bench_search_vec_gin ON bench_passages USING gin (search_vec);
CREATE INDEX bench_norm_trgm ON bench_passages USING gin (norm_text gin_trgm_ops);

CREATE TEMP TABLE bench_queries (
    case_id text PRIMARY KEY,
    category text NOT NULL,
    query text NOT NULL,
    normalized_query text NOT NULL,
    expected_passage_codes text[] NOT NULL
);

-- The runner inserts fixture rows from tests/fixtures/source_search and then
-- compares three strategies:
--   A. search_vec @@ plainto_tsquery('simple', normalized_query)
--   B. norm_text LIKE '%' || normalized_query || '%'
--   C. norm_text % normalized_query
--
-- The report includes expected_passage_codes, matched_by_tsvector,
-- matched_by_like, matched_by_trgm, missed_by_strategy, and
-- unexpected_by_strategy for each case. EXPLAIN output is gathered by the
-- runner for shape inspection only; tests must not assert fragile cost values.
