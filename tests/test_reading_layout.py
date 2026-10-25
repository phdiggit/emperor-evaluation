"""Pagination, provenance and navigation contracts using only synthetic people."""
from pathlib import Path
import re

import pytest

from emperor_v4.evaluation import reading_layout as layout


def document():
    return ('# 合成总览\n\n[甲](#a)\n\n## 裁决\n\n'
            + layout.person_start('PERSON-A') + '\n### 同名人物\n\n甲的裁决。\n'
            + layout.PERSON_END + '\n\n'
            + layout.person_start('PERSON-B') + '\n### 同名人物\n\n乙的裁决。\n'
            + layout.PERSON_END + '\n\n## 史源\n\n'
            + layout.person_start('PERSON-A') + '\n### 同名人物\n\n<a id="a"></a>\n\n'
            + '原文 标点。\n\n[来源](../evidence/source.json?r=1#record)\n'
            + '[原书](https://example.test/book_(part)#chapter)\n'
            + layout.PERSON_END + '\n')


def test_identity_merges_sections_without_using_names_and_rebases_sources():
    path = 'docs/results/index.md'
    text = document()
    files = layout.reading_files(path, text)
    assert files == layout.reading_files(path, text)
    a = files['docs/results/index-逐人阅读/PERSON-A.md']
    b = files['docs/results/index-逐人阅读/PERSON-B.md']
    assert '甲的裁决。' in a and '原文 标点。' in a and '## 史源' in a
    assert '乙的裁决。' not in a and '甲的裁决。' not in b
    assert '../../evidence/source.json?r=1#record' in a
    assert 'https://example.test/book_(part)#chapter' in a
    assert '../index.md' in a
    assert '甲的裁决。' not in files[path]
    assert 'PERSON-A.md#a' in files[path]
    assert text == document()


def test_pages_preserve_complete_units_and_balanced_details(monkeypatch):
    monkeypatch.setattr(layout, 'PAGE_BYTES', 300)
    monkeypatch.setattr(layout, 'PAGE_LINES', 15)
    units = ['#### 甲节\n\n' + '第一段证据。' * 8 + '\n\n',
             '<details><summary>乙节</summary>\n\n' + '第二段证据。' * 8 + '\n\n</details>\n\n',
             '- 第三段证据。\n  采用范围不得丢失。\n', '- 第四段证据。\n  来源不得丢失。\n']
    body = ''.join(units)
    pages = layout._pages(body)
    assert len(pages) > 1 and ''.join(pages) == body
    for page in pages:
        assert page.count('<details>') == page.count('</details>')
    text = '# 总览\n\n' + layout.person_start('PERSON-A') + '\n### 甲\n\n' + body + layout.PERSON_END + '\n'
    files = layout.reading_files('docs/index.md', text)
    assert '正文第1页' in files['docs/index-逐人阅读/PERSON-A.md']
    for name, content in files.items():
        for link in re.findall(r'\]\(([^)]+)\)', content):
            if link.startswith(('http', '#')):
                continue
            from urllib.parse import unquote
            target = (Path(name).parent / unquote(link)).as_posix()
            import posixpath
            assert posixpath.normpath(target) in files


def test_readonly_verification_detects_damaged_and_stale_pages(tmp_path):
    text = document(); path = 'docs/index.md'
    layout.write_reading(tmp_path, path, text)
    baseline = {p: p.read_bytes() for p in tmp_path.rglob('*.md')}
    layout.check_reading(tmp_path, path, text)
    assert baseline == {p: p.read_bytes() for p in baseline}
    page = tmp_path / 'docs/index-逐人阅读/PERSON-A.md'
    page.write_text('损坏正文', encoding='utf-8')
    with pytest.raises(ValueError, match='过期'):
        layout.check_reading(tmp_path, path, text)
    assert page.read_text(encoding='utf-8') == '损坏正文'
    layout.write_reading(tmp_path, path, text)
    directory = page.parent
    stale = directory / 'OLD.md'
    stale.write_text('<!-- generated-reading: docs/index.md -->\n旧生成内容', encoding='utf-8')
    personal = directory / 'personal.md'; personal.write_text('用户笔记', encoding='utf-8')
    with pytest.raises(ValueError, match='OLD.md'):
        layout.check_reading(tmp_path, path, text)
    layout.write_reading(tmp_path, path, text)
    assert not stale.exists() and personal.read_text(encoding='utf-8') == '用户笔记'


def test_unmarked_authorities_and_literal_code_are_unchanged():
    text = '# 真源\n\n原文不改。\n'
    assert layout.reading_files('authority.md', text) == {'authority.md': text}
    code = '```md\n[x](../a.md)\n```\n`[x](../a.md)`\n[x](../a.md)\n'
    moved = layout.relocate_links(code, 'docs/index.md', 'docs/parts/person.md')
    assert moved.count('[x](../a.md)') == 2
    assert '[x](../../a.md)' in moved


def test_incomplete_identity_markers_fail_closed():
    with pytest.raises(ValueError, match='未闭合'):
        layout.reading_files('docs/index.md', '# 总览\n' + layout.person_start('PERSON-A') + '\n### 甲\n正文')


def test_identity_cannot_be_overwritten_by_a_numbered_page(monkeypatch):
    monkeypatch.setattr(layout, 'PAGE_BYTES', 30)
    a = layout.person_start('PERSON-A') + '\n### 甲\n\n第一段正文。\n\n第二段正文。\n\n第三段正文。\n' + layout.PERSON_END
    b = layout.person_start('PERSON-A-01') + '\n### 乙\n\n乙正文。\n' + layout.PERSON_END
    with pytest.raises(ValueError, match='文件名冲突'):
        layout.reading_files('docs/index.md', '# 总览\n\n' + a + '\n\n' + b + '\n')
