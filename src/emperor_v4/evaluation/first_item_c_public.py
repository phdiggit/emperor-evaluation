"""Read explicit commander prose and battle entries from the formal Markdown.

This adapter parses declared fields. It never infers a battle, command role or
grade from narrative prose, and never modifies scores or sorts the evidence.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from emperor_v4.evaluation.first_item_public_outcomes import (
    _parse_source_sections, PUBLIC_NAME_ALIASES, SOURCE_MARKDOWN_PATH as A_SOURCE,
)

SOURCE_MARKDOWN_PATH = Path('docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md')
SCHEMA = 'first-item-c-public-v1'
PUBLIC_FIELDS = {'公开裁决依据': 'public_basis', '公开责任边界': 'public_boundary'}
DIFFICULTY_LABELS = {f'D{i}': label for i, label in enumerate(('D', 'C', 'B', 'A', 'S'))}
BATTLE = re.compile(r'(.+?)\s*[｜|]\s*(前线作战|战略统筹)\s*[｜|]\s*([SABCD][+−-]?)\s*[｜|]\s*(D[0-4]|[—-])')


def parse_declared_battles(value: str) -> list[dict[str, str]]:
    if not value.strip():
        return []
    result = []
    for part in value.strip().rstrip('。').split('；'):
        match = BATTLE.fullmatch(part.strip())
        if not match:
            raise ValueError(f'统帅公开战役条目格式错误，禁止从判词补猜：{part}')
        name, role, grade, difficulty = match.groups()
        if name in {row['name'] for row in result}:
            raise ValueError(f'统帅公开战役条目重复：{name}')
        result.append({'name': name, 'role': role, 'result': grade.replace('-', '−'),
                       'difficulty': DIFFICULTY_LABELS.get(difficulty, '')})
    return result


def project_commander(fields: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source, target in PUBLIC_FIELDS.items():
        text = fields.get(source)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'统帅正式来源缺少{source}，禁止用内部判词回退')
        if re.search(r'[A-Za-z]|统帅锚|复验|本轮|旧登记', text):
            raise ValueError(f'统帅公开字段仍含内部术语：{source}')
        result[target] = text.strip()
    result['public_battles'] = parse_declared_battles(fields.get('统一链战役清单', ''))
    return result


def load_first_item_c_public(root: Path) -> dict[str, dict[str, Any]]:
    rows = _parse_source_sections(root / SOURCE_MARKDOWN_PATH)
    expected = _parse_source_sections(root / A_SOURCE)
    if not rows or rows.keys() != expected.keys():
        raise ValueError('第一项C公开说明与正式A适用人物集合不一致')
    return {name: project_commander(fields) for name, fields in rows.items()}


def public_commander_for_name(rows: dict, name: str) -> dict[str, Any]:
    return rows[PUBLIC_NAME_ALIASES.get(name, name)]


def verify_first_item_c_public(root: Path) -> dict[str, Any]:
    rows = load_first_item_c_public(root)
    return {'status': 'PASS', 'schema_version': SCHEMA, 'record_count': len(rows),
            'with_battle_list': sum(bool(row['public_battles']) for row in rows.values()),
            'battle_count': sum(len(row['public_battles']) for row in rows.values())}
