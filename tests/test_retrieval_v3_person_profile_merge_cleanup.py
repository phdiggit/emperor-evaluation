from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/migrations/20260712_retrieval_v3_person_profile_merge_cleanup.sql").read_text(encoding="utf-8")


def test_noncanonical_profiles_are_archived_then_removed_from_main_table() -> None:
    assert "person_profile_merge_audit" in SQL
    assert "to_jsonb(r)" in SQL
    assert "delete from retrieval_v3.person_profiles" in SQL
    assert "identity_status in ('merged','rejected','retired')" in SQL


def test_identity_transition_installs_profile_cleanup_trigger() -> None:
    assert "rv3_objects_archive_noncanonical_profile_trg" in SQL
    assert "update of identity_status" in SQL
