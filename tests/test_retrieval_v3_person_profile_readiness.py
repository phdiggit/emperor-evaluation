from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/migrations/20260712_retrieval_v3_person_profile_readiness.sql").read_text(encoding="utf-8")


def test_readiness_migration_has_required_states_and_inputs() -> None:
    for value in ("no_claim", "claim_pending_authority", "talent_evaluable", "profile_complete"):
        assert value in SQL
    assert "talent_grade_version" in SQL
    assert "negative_talent_version" in SQL
    assert "profile_field='authority_evaluation'" in SQL
    assert "cc.status='active'" in SQL


def test_readiness_is_refreshed_from_claim_authority_and_profile_changes() -> None:
    assert "rv3_claim_cache_profile_readiness_trg" in SQL
    assert "rv3_profile_claim_links_readiness_trg" in SQL
    assert "rv3_person_profiles_readiness_trg" in SQL
    assert "refresh_person_profile_readiness" in SQL
