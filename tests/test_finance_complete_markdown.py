from copy import deepcopy


from emperor_v4.evaluation import governance_state_recovery as core
from emperor_v4.evaluation import second_item_c_public as public


def test_technical_renderer_is_read_only_and_keeps_synthetic_source_text(monkeypatch):
    payload = {'scores': [{'rank': 1, 'ruler_id': 'SYNTHETIC', 'ruler_name': '合成人物',
                          'polity': '合成政权', 'state_anchors': {'S0': 1, 'S_main': 2, 'S_end': 2},
                          'main_band': 'C3-2', 'loss_grade': 'L0', 'score': 16.0,
                          'adjudication_reason': '合成的当前裁决。', 'stability_basis': '合成的边界说明。',
                          'material_basis': [{'book': '合成史源', 'original_text': '保留 空格与原文标点。'}]}]}
    original = deepcopy(payload)
    def forbidden(*args, **kwargs):
        raise AssertionError('pure renderer must not read files')
    monkeypatch.setattr(core, 'load_json', forbidden)
    result = core.render_component_markdown('C3', payload)
    assert '合成的当前裁决。' in result and '保留 空格与原文标点。' in result
    assert '\r' not in result
    assert payload == original


def test_public_refresh_creates_generated_components_without_old_markdown(tmp_path, monkeypatch):
    payloads = {axis: {'public_projection_axis': axis, 'scores': [{'ruler_id': 'SYNTHETIC'}]}
                for axis in public.FORMAL_PATHS}
    original = deepcopy(payloads)
    by_path = {tmp_path / path: payloads[axis] for axis, path in public.FORMAL_PATHS.items()}
    for axis, path in public.FORMAL_PATHS.items():
        target = (tmp_path / path).with_suffix('.md')
        target.parent.mkdir(parents=True, exist_ok=True)
        if axis not in public.GENERATED_MARKDOWN_AXES:
            target.write_text('保留的证据正文\n', encoding='utf-8')
    monkeypatch.setattr(public, 'load_json', lambda path: deepcopy(by_path[path]))
    monkeypatch.setattr(public, '_refresh_payload', lambda axis, payload: payload)
    monkeypatch.setattr(public, '_verify_payload', lambda axis, payload: {})
    monkeypatch.setattr(public, 'verify_source_bindings', lambda payloads: 0)
    monkeypatch.setattr(public, 'load_ruler_polities', lambda root: {})
    monkeypatch.setattr(public, 'write_json', lambda *args, **kwargs: None)
    monkeypatch.setattr(public, 'verify_public_projection', lambda root: {'status': 'PASS'})
    monkeypatch.setattr(public, 'render_complete_markdown', lambda payload: payload['public_projection_axis'] + '完整正文\n')
    monkeypatch.setattr(public, 'render_public_markdown', lambda markdown, payload: markdown)
    assert public.run(tmp_path, write=True)['status'] == 'WRITTEN'
    for axis in public.GENERATED_MARKDOWN_AXES:
        assert (tmp_path / public.FORMAL_PATHS[axis]).with_suffix('.md').read_bytes() == (axis + '完整正文\n').encode('utf-8')
    assert payloads == original
