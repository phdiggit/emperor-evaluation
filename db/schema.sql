PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    title TEXT,
    author TEXT,
    dynasty TEXT,
    volume TEXT,
    location TEXT,
    url TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_cards (
    evidence_id TEXT PRIMARY KEY,
    person TEXT NOT NULL,
    item TEXT NOT NULL,
    subitem TEXT NOT NULL,
    polarity TEXT NOT NULL CHECK (polarity IN ('positive', 'negative')),
    strength INTEGER NOT NULL CHECK (strength IN (1, 2, 3, 4)),
    human_level TEXT NOT NULL,
    source_id TEXT NOT NULL,
    quote_short TEXT NOT NULL,
    interpretation TEXT NOT NULL,
    trigger_family TEXT NOT NULL,
    trigger_terms TEXT NOT NULL,
    cross_item_split TEXT,
    scoring_effect TEXT,
    verification_status TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_person_subitem
    ON evidence_cards (person, subitem);

CREATE INDEX IF NOT EXISTS idx_evidence_polarity_strength
    ON evidence_cards (polarity, strength);

CREATE INDEX IF NOT EXISTS idx_evidence_trigger_family
    ON evidence_cards (trigger_family);

CREATE INDEX IF NOT EXISTS idx_evidence_source_id
    ON evidence_cards (source_id);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    person TEXT,
    target TEXT,
    action_type TEXT,
    attribution_type TEXT,
    outcome TEXT,
    severity INTEGER,
    time_phase TEXT,
    event_name TEXT,
    event_date TEXT,
    description TEXT,
    source_id TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trigger_terms (
    term_id TEXT PRIMARY KEY,
    trigger_family TEXT,
    term TEXT,
    polarity TEXT CHECK (polarity IS NULL OR polarity IN ('positive', 'negative')),
    tier TEXT CHECK (tier IS NULL OR tier IN ('core', 'extended')),
    item TEXT,
    subitem TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_logs (
    search_id TEXT PRIMARY KEY,
    person TEXT,
    item TEXT,
    subitem TEXT,
    polarity TEXT CHECK (polarity IS NULL OR polarity IN ('positive', 'negative')),
    trigger_family TEXT,
    query_terms TEXT,
    query TEXT,
    source_scope TEXT,
    searched_at TEXT,
    result_status TEXT,
    result_summary TEXT,
    linked_evidence_id TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_person_subitem
    ON search_logs (person, subitem);

CREATE INDEX IF NOT EXISTS idx_search_trigger_family
    ON search_logs (trigger_family);

CREATE INDEX IF NOT EXISTS idx_search_result_status
    ON search_logs (result_status);
