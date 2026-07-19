from __future__ import annotations

from pathlib import Path

from emperor_v4.persistence.postgres_schema_governance import (
    MIGRATION_KEY,
    _inventory_sha256,
    canonical_assertion_id,
    canonical_person_ref,
    canonical_section_id,
    canonical_source_profile_ref,
    migration_path,
    normalize_chinese_explanatory_text,
)


def test_schema_governance_migration_is_transactional_and_non_destructive() -> None:
    sql = migration_path().read_text(encoding="utf-8")
    upper = sql.upper()

    assert migration_path().name == "012_v4_schema_field_governance.sql"
    assert upper.lstrip().startswith("BEGIN;")
    assert upper.rstrip().endswith("COMMIT;")
    assert "DROP TABLE" not in upper
    assert "TRUNCATE" not in upper
    assert "DELETE FROM" not in upper
    assert MIGRATION_KEY == "v4-schema-field-governance-v1"


def test_schema_governance_encodes_field_contracts_and_new_write_gates() -> None:
    sql = migration_path().read_text(encoding="utf-8")

    for contract_column in (
        "assertion_id",
        "assertion_semantic_key",
        "person_ref",
        "evaluation_context",
        "document_id",
        "historical_context",
        "section_id",
        "source_profile_ref",
        "talent_grade",
    ):
        assert f"'{contract_column}'" in sql

    assert "assertions_assertion_id_family_check" in sql
    assert "assertions_semantic_key_family_check" in sql
    assert "episode_participants_canonical_person_ref_check" in sql
    assert "historical_episodes_canonical_evaluation_context_check" in sql
    assert sql.count("NOT VALID") == 9
    assert "legacy_policy" in sql
    assert "quarantined_debt" in sql
    assert "field_quality_baselines" in sql
    assert "baseline_count" in sql
    assert "legacy_value_dispositions" in sql
    assert "identity_reference_aliases" in sql
    assert "identity_reference_backfill_map" in sql
    assert "field_value_backfill_map" in sql
    assert "text_normalization_runs" in sql
    assert "resolved_episode_participants" in sql
    assert "resolved_historical_episodes" in sql
    assert "episode_participants_no_candidate_ref_check" in sql
    assert "canonical_target" in sql
    assert "quarantined" in sql
    assert "PER-V4-4EB7AC987FEC" in sql
    assert "PER-V4-E15C1B65F12F" in sql
    assert "PER-V4-C93016BB741A" in sql
    assert "PER-V4-75EF40579300" in sql


def test_full_field_canonicalizers_are_stable_and_typed() -> None:
    assert canonical_assertion_id("ASTA-legacy") == canonical_assertion_id(
        "ASTA-legacy"
    )
    assert canonical_assertion_id("AST-V4-0123456789ABCDEF0123") == (
        "AST-V4-0123456789ABCDEF0123"
    )
    assert canonical_section_id("卷一").startswith("SEC-V4-")
    assert canonical_source_profile_ref("人物画像：李世民").startswith("SPR-V4-")
    assert canonical_person_ref("RULER-NAME-CANDIDATE-737E2C4D60AC") == (
        "PER-V4-737E2C4D60AC"
    )
    assert canonical_person_ref("PER-LI-SHIMIN") == "PER-V4-737E2C4D60AC"
    assert canonical_person_ref("PER-FANG-XUANLING") == "PER-V4-C37ED24688F5"
    assert canonical_person_ref("二世使者") == "GRP-V4-3169839A92A8"


def test_explanatory_text_normalization_is_chinese_and_rejects_unknown_mix() -> None:
    normalized = normalize_chinese_explanatory_text(
        "权威评价 authority_evaluations 与 evidence_claims 完整"
    )
    assert normalized == "权威评价 权威评价 与 证据断言 完整"
    try:
        normalize_chinese_explanatory_text("中文 unknown_anchor")
    except ValueError as exc:
        assert "unknown_anchor" in str(exc)
    else:  # pragma: no cover - 防止新写入口静默放过混合文本
        raise AssertionError("unknown mixed-language anchor must be rejected")


def test_schema_governance_comments_every_current_and_future_business_field() -> None:
    sql = migration_path().read_text(encoding="utf-8")

    assert "CREATE OR REPLACE FUNCTION v4_governance.ensure_schema_comments()" in sql
    assert "COMMENT ON %s %I.%I IS %L" in sql
    assert "COMMENT ON COLUMN %I.%I.%I IS %L" in sql
    assert "obj_description" in sql
    assert "col_description" in sql
    for schema_name in (
        "public",
        "v4_source_cache",
        "v4_claim_extractor",
        "v4_person_profile",
        "v4_governance",
    ):
        assert f"'{schema_name}'" in sql


def test_schema_inventory_hash_is_stable_and_shape_sensitive() -> None:
    first = [
        {
            "schema": "public",
            "relation": "assertions",
            "relation_kind": "r",
            "column": "assertion_id",
            "data_type": "text",
            "nullability": "not_null",
        }
    ]
    same = [dict(first[0])]
    changed = [dict(first[0], column="assertion_semantic_key")]

    assert _inventory_sha256(first) == _inventory_sha256(same)
    assert _inventory_sha256(first) != _inventory_sha256(changed)


def test_all_postgres_bootstraps_route_through_schema_governance() -> None:
    root = Path(__file__).parents[1] / "src" / "emperor_v4" / "persistence"
    for module_name in (
        "postgres.py",
        "postgres_source_cache.py",
        "postgres_claim_extractor.py",
        "postgres_person_profile.py",
    ):
        source = (root / module_name).read_text(encoding="utf-8")
        assert "ensure_schema_governance" in source

    release = (
        Path(__file__).parents[1] / "src" / "emperor_v4" / "runtime" / "release.py"
    ).read_text(encoding="utf-8")
    assert release.count("db/postgres/012_v4_schema_field_governance.sql") == 2
    assert release.count("postgres_schema_governance.py") == 2


def test_active_postgres_writers_canonicalize_governed_fields_before_insert() -> None:
    root = Path(__file__).parents[1] / "src" / "emperor_v4"
    registry = (root / "persistence" / "postgres_registry.py").read_text(
        encoding="utf-8"
    )
    source_cache = (root / "persistence" / "postgres_source_cache.py").read_text(
        encoding="utf-8"
    )
    for helper in (
        "canonical_assertion_id",
        "canonical_section_id",
        "canonical_person_ref",
    ):
        assert helper in registry
    assert "canonical_section_id" in source_cache
    assert not (
        root / "infrastructure" / "postgres_person_profile_repository.py"
    ).exists()


def test_text_quality_metrics_are_ratcheted_and_physically_normalized() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "emperor_v4"
        / "persistence"
        / "postgres_schema_governance.py"
    ).read_text(encoding="utf-8")

    assert "mixed_han_latin" in source
    assert "field quality baseline regression" in source
    assert "baseline_count = LEAST(" in source
    assert "_refresh_legacy_value_dispositions" in source
    assert "_refresh_identity_reference_aliases" in source
    assert "assertion_evaluation_context_name" in source
    assert "linked.role_code = 'actor'" in source
    assert "r.canonical_name = linked.subject_name" in source
    assert "linked.role_code NOT IN ('ruler', 'actor')" in source
    assert "r.canonical_name = linked.object_name" in source
    assert "IDENTITY_RESOLVER_VERSION.encode()" in source
    assert "_apply_physical_identity_backfill" in source
    assert "_apply_full_field_normalization" in source
    assert "normalize_chinese_explanatory_text" in source
    assert "governance_participant_projection" in source
    assert "VALIDATE CONSTRAINT" in source
    for column in (
        "talent_grade_basis",
        "negative_talent_basis",
        "reason",
        "follow_up",
    ):
        assert f'"{column}"' in source
