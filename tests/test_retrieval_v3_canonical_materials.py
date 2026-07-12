from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / 'db/migrations/20260712_retrieval_v3_canonical_materials.sql').read_text(encoding='utf-8')


def test_canonical_material_schema_has_one_subject_per_event() -> None:
    assert 'canonical_event_key text not null' in SQL
    assert 'rv3_material_claims_canonical_event_uk' in SQL
    assert "where btrim(canonical_event_key) <> ''" in SQL


def test_material_claim_members_fan_in_claim_evidence() -> None:
    assert 'create table if not exists retrieval_v3.material_claim_members' in SQL
    assert 'unique(claim_key)' in SQL
    assert "member_role in ('representative','evidence_member')" in SQL
