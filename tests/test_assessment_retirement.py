from pathlib import Path

import pytest

from emperor_v4.eval import _parser
from emperor_v4.evaluation import canonical_ruler_pool as pool
from emperor_v4.evaluation.maintenance import current_entries
from emperor_v4.evaluation.profile_c1_verifier import _source_path
from emperor_v4.evaluation.profile_radar import AXIS_COLORS, AXIS_ORDER
from emperor_v4.evaluation.profile_registry import load_project_config


ROOT = Path(__file__).resolve().parents[1]


def test_retired_components_are_not_current_or_cli_entries():
    project = load_project_config()
    entries = current_entries(ROOT)
    for component in project['retired_assessments']:
        assert component not in project['formal_settlements']
    assert 'I5' not in entries
    assert 'profile.M3' not in entries
    assert len(AXIS_COLORS) == len(AXIS_ORDER)
    for argv in (['profile-m3-verify'], ['profile-m3-settlement'],
                 ['formal-settlements-verify', '--item', 'fifth_item']):
        with pytest.raises(SystemExit):
            _parser().parse_args(argv)


def test_candidate_identity_does_not_depend_on_retired_settlements(monkeypatch):
    original = pool._read_json

    def current_only(path):
        assert 'archive' not in path.parts
        assert '第五项统治者政治素质' not in path.parts
        return original(path)

    monkeypatch.setattr(pool, '_read_json', current_only)
    current = original(ROOT / pool.POOL_JSON)
    rebuilt = pool.build_canonical_ruler_pool(ROOT)
    assert {r['ruler_id'] for r in rebuilt['records']} == {r['ruler_id'] for r in current['records']}
    assert 'fifth_item' not in rebuilt['selection_policy']['requires_formal_scores_for_composite_readiness']


def test_archive_source_locator_resolves_as_evidence(tmp_path):
    target = tmp_path / 'archive' / 'retired' / 'evidence.md'
    target.parent.mkdir(parents=True)
    target.write_text('Synthetic source evidence', encoding='utf-8')
    assert _source_path(tmp_path, 'archive/retired/evidence.md#episode') == target
