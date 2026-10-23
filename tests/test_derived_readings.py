"""Generated reading lifecycle; no adjudication snapshots."""
import importlib.util
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation import derived_readings as views


def test_readonly_check_and_rebuild_touch_only_registered_views(tmp_path, monkeypatch):
    source = tmp_path / 'source.json'
    source.write_bytes(b'{"evidence":"original"}')
    monkeypatch.setattr(views, 'render_views', lambda root: {'reading.md': '完整正文。\n'})
    target = tmp_path / 'reading.md'
    with pytest.raises(ValueError, match='reading-views'):
        views.run(tmp_path, check=True)
    assert not target.exists()
    views.run(tmp_path)
    assert target.read_text(encoding='utf-8') == '完整正文。\n'
    stamp = target.stat().st_mtime_ns
    assert views.run(tmp_path)['updated'] == []
    assert target.stat().st_mtime_ns == stamp
    target.write_text('过期副本', encoding='utf-8')
    with pytest.raises(ValueError, match='过期'):
        views.run(tmp_path, check=True)
    assert target.read_text(encoding='utf-8') == '过期副本'
    assert source.read_bytes() == b'{"evidence":"original"}'


def test_unregistered_output_is_rejected_before_reading_source(tmp_path, monkeypatch):
    monkeypatch.setattr(views, 'view_sources', lambda root: {})
    with pytest.raises(ValueError, match='未登记'):
        views.render_views(tmp_path, ['authority.md'])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('existing', [False, True])
def test_package_renders_missing_or_stale_views_without_writing_them(tmp_path, monkeypatch, existing):
    spec = importlib.util.spec_from_file_location('package_views_test', Path(__file__).resolve().parents[1] / 'package_net_review.py')
    packager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packager)
    target = tmp_path / 'reading.md'
    if existing:
        target.write_text('过期副本', encoding='utf-8')
    monkeypatch.setattr(packager, 'collect', lambda root, package: [target])
    monkeypatch.setattr(packager, 'view_sources', lambda root: {'reading.md': ('synthetic', 'source.json')})
    monkeypatch.setattr(packager, 'render_views', lambda root, paths: {'reading.md': '当前完整正文。'})
    entries, manifest = packager.prepare(tmp_path)
    assert entries['reading.md'].decode() == '当前完整正文。'
    assert manifest['files'][0]['transformation'] == 'GENERATED'
    assert target.exists() == existing
    if existing:
        assert target.read_text(encoding='utf-8') == '过期副本'


def test_ab_view_rebuilds_from_both_json_inputs_without_old_markdown(tmp_path, monkeypatch):
    from emperor_v4.evaluation import five_dynasties_third_item as renderer
    from emperor_v4.evaluation.third_fourth_item_public import THIRD_CREDIT_PATH
    formal = tmp_path / 'formal.json'
    formal.write_text(json.dumps({'records': [{'ruler_id': 'X', 'fact': '当前正式事实'}]}), encoding='utf-8')
    credit = tmp_path / THIRD_CREDIT_PATH; credit.parent.mkdir(parents=True)
    credit.write_text(json.dumps({'records': [{'ruler_id': 'X', 'basis': '当前信用依据'}]}), encoding='utf-8')
    original = {p: p.read_bytes() for p in (formal, credit)}
    monkeypatch.setattr(renderer, '_render_formal_markdown', lambda kind, rows, *, credit_rows:
                        rows[0]['fact'] + '；' + credit_rows['X']['basis'] + '\n')
    monkeypatch.setattr(views, 'view_sources', lambda root: {'reading.md': ('third.AB', 'formal.json')})
    views.run(tmp_path)
    assert (tmp_path / 'reading.md').read_text(encoding='utf-8') == '当前正式事实；当前信用依据\n'
    assert {p: p.read_bytes() for p in original} == original
