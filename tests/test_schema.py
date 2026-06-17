from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_schema_exists_and_contains_core_tables() -> None:
    schema_path = ROOT / "db" / "schema.sql"
    assert schema_path.exists()

    schema = schema_path.read_text(encoding="utf-8")
    for table in [
        "sources",
        "evidence_cards",
        "events",
        "trigger_terms",
        "search_logs",
        "evidence_clusters",
        "thematic_anchors",
        "query_profiles",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema


def test_schema_contains_matrix_fields_and_indexes() -> None:
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")

    for field in [
        "tier TEXT",
        "target TEXT",
        "action_type TEXT",
        "attribution_type TEXT",
        "outcome TEXT",
        "severity INTEGER",
        "time_phase TEXT",
        "person TEXT",
        "query_terms TEXT",
        "result_status TEXT",
        "linked_evidence_id TEXT",
        "linked_evidence_ids TEXT NOT NULL",
        "candidate_strength INTEGER",
        "linked_cluster_ids TEXT NOT NULL",
        "query_profile_id TEXT PRIMARY KEY",
        "thematic_anchor_targets TEXT NOT NULL",
    ]:
        assert field in schema

    for index in [
        "idx_evidence_person_subitem",
        "idx_evidence_polarity_strength",
        "idx_evidence_trigger_family",
        "idx_evidence_source_id",
        "idx_search_person_subitem",
        "idx_search_trigger_family",
        "idx_search_result_status",
        "idx_clusters_person_subitem",
        "idx_clusters_polarity_strength",
        "idx_anchors_theme_subitem",
        "idx_query_profiles_item_subitem",
    ]:
        assert index in schema
