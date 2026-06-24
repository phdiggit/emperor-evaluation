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

CREATE TABLE IF NOT EXISTS evidence_clusters (
    cluster_id TEXT PRIMARY KEY,
    person TEXT,
    item TEXT,
    subitem TEXT,
    cluster_type TEXT,
    polarity TEXT CHECK (polarity IS NULL OR polarity IN ('positive', 'negative')),
    linked_evidence_ids TEXT NOT NULL,
    summary TEXT,
    five_axis_assessment TEXT,
    candidate_strength INTEGER CHECK (candidate_strength IS NULL OR candidate_strength IN (1, 2, 3, 4)),
    upper_probe TEXT,
    cross_item_split TEXT,
    adjudication_status TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clusters_person_subitem
    ON evidence_clusters (person, subitem);

CREATE INDEX IF NOT EXISTS idx_clusters_polarity_strength
    ON evidence_clusters (polarity, candidate_strength);

CREATE TABLE IF NOT EXISTS thematic_anchors (
    anchor_id TEXT PRIMARY KEY,
    theme TEXT,
    item TEXT,
    subitem TEXT,
    persons TEXT NOT NULL,
    linked_evidence_ids TEXT NOT NULL,
    linked_cluster_ids TEXT NOT NULL,
    anchor_summary TEXT,
    comparative_value TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anchors_theme_subitem
    ON thematic_anchors (theme, subitem);

CREATE TABLE IF NOT EXISTS anchor_objects (
    anchor_id TEXT PRIMARY KEY,
    item TEXT,
    subitem TEXT,
    anchor_kind TEXT,
    anchor_scope TEXT,
    object_type TEXT,
    object_name TEXT,
    object_level TEXT,
    anchor_role TEXT,
    usable_for TEXT,
    cross_item_risks TEXT,
    consensus_level TEXT,
    review_status TEXT,
    linked_persons TEXT,
    source_batch TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aobj_item
    ON anchor_objects (item, subitem);

CREATE INDEX IF NOT EXISTS idx_aobj_type_level
    ON anchor_objects (object_type, object_level);

CREATE INDEX IF NOT EXISTS idx_aobj_review
    ON anchor_objects (review_status);

CREATE INDEX IF NOT EXISTS idx_aobj_src_batch
    ON anchor_objects (source_batch);

CREATE TABLE IF NOT EXISTS anchor_events (
    anchor_id TEXT PRIMARY KEY,
    item TEXT,
    subitem TEXT,
    anchor_kind TEXT,
    anchor_scope TEXT,
    object_type TEXT,
    object_name TEXT,
    object_level TEXT,
    anchor_role TEXT,
    usable_for TEXT,
    cross_item_risks TEXT,
    consensus_level TEXT,
    review_status TEXT,
    linked_persons TEXT,
    source_batch TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aevt_item
    ON anchor_events (item, subitem);

CREATE INDEX IF NOT EXISTS idx_aevt_type_level
    ON anchor_events (object_type, object_level);

CREATE INDEX IF NOT EXISTS idx_aevt_review
    ON anchor_events (review_status);

CREATE INDEX IF NOT EXISTS idx_aevt_src_batch
    ON anchor_events (source_batch);

CREATE TABLE IF NOT EXISTS anchor_mechanisms (
    anchor_id TEXT PRIMARY KEY,
    item TEXT,
    subitem TEXT,
    anchor_kind TEXT,
    anchor_scope TEXT,
    object_type TEXT,
    object_name TEXT,
    object_level TEXT,
    anchor_role TEXT,
    usable_for TEXT,
    cross_item_risks TEXT,
    consensus_level TEXT,
    review_status TEXT,
    linked_persons TEXT,
    source_batch TEXT,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_amech_item
    ON anchor_mechanisms (item, subitem);

CREATE INDEX IF NOT EXISTS idx_amech_type_level
    ON anchor_mechanisms (object_type, object_level);

CREATE INDEX IF NOT EXISTS idx_amech_review
    ON anchor_mechanisms (review_status);

CREATE INDEX IF NOT EXISTS idx_amech_src_batch
    ON anchor_mechanisms (source_batch);

CREATE TABLE IF NOT EXISTS query_profiles (
    query_profile_id TEXT PRIMARY KEY,
    item TEXT,
    subitem TEXT,
    search_modes TEXT NOT NULL,
    positive_terms TEXT NOT NULL,
    negative_terms TEXT NOT NULL,
    reversal_terms TEXT NOT NULL,
    source_scopes TEXT NOT NULL,
    reverse_search_required_when TEXT NOT NULL,
    thematic_anchor_targets TEXT NOT NULL,
    cross_item_split_notes TEXT NOT NULL,
    note TEXT,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_profiles_item_subitem
    ON query_profiles (item, subitem);
