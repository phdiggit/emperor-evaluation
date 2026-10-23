import json
from pathlib import Path
import pytest
from emperor_v4.json_format import json_text, format_repository


def test_standard_json_lossless_deterministic_and_ordered():
    value = {'records': [{'text': '原文  空格\n下一行\t"引文"', 'values': [None, False, 0, 1.25]}],
             'collections': {'scores': {'records': [{'id': 'a'}, {'id': 'b'}]}}}
    result = json_text(value)
    assert json.dumps(json.loads(result), ensure_ascii=False) == json.dumps(value, ensure_ascii=False)
    assert json_text(json.loads(result)) == result


def test_repository_scope_check_and_repeat_write(tmp_path, monkeypatch):
    monkeypatch.setattr('emperor_v4.json_format.subprocess.check_output', lambda *a, **k: b'config/example.json\0archive/example.json\0')
    for name in ('config/example.json', 'archive/example.json', 'reader/data/example.json', '.tmp/untouched.json'):
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{ "records": [{"x": 1}] }', encoding='utf-8')
    assert format_repository(tmp_path, check=True)['status'] == 'OUTDATED'
    assert format_repository(tmp_path)['changed_count'] == 3
    assert format_repository(tmp_path, check=True)['status'] == 'PASS'
    assert format_repository(tmp_path)['changed_count'] == 0
    assert (tmp_path / '.tmp/untouched.json').read_text() == '{ "records": [{"x": 1}] }'


def test_duplicate_keys_fail_before_writing_any_file(tmp_path, monkeypatch):
    monkeypatch.setattr('emperor_v4.json_format.subprocess.check_output', lambda *a, **k: b'a.json\0b.json\0')
    a=tmp_path/'a.json'; a.write_text('{ "x": 1 }')
    (tmp_path/'b.json').write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError, match='重复字段'): format_repository(tmp_path)
    assert a.read_text() == '{ "x": 1 }'
