from __future__ import annotations

from pathlib import Path

from scripts.dev import retrieval_v3_canonical_material_rebuild as tool


def test_rebuild_uses_explicit_gate_bypass_and_canonical_identity() -> None:
    source=Path(tool.__file__).read_text(encoding='utf-8')
    assert "set local retrieval_v3.rebuild_bypass='on'" in source
    assert 'partition by c.canonical_event_key' in source
    assert 'material_claim_members' in source
    assert "'neutral'" in source


def test_rebuild_replaces_links_and_first_claim_references() -> None:
    source=Path(tool.__file__).read_text(encoding='utf-8')
    assert 'old_passages' in source
    assert 'old_objects' in source
    assert 'old_target_first' in source
    assert 'first_claim_id=x.new_claim_id' in source


def test_rebuild_fans_in_all_active_claims_for_existing_events() -> None:
    source=Path(tool.__file__).read_text(encoding='utf-8')
    assert "from retrieval_v3.claim_cache c" in source
    assert "where c.status='active'" in source
    assert 'join retrieval_v3.material_claims m on m.canonical_event_key=c.canonical_event_key' in source
