"""Read explicit commander prose and battle entries from the formal Markdown.

This adapter parses declared fields. It never infers a battle, command role or
grade from narrative prose, and never modifies scores or sorts the evidence.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any
from urllib.parse import urlsplit

from emperor_v4.evaluation.first_item_public_outcomes import (
    _parse_source_sections, PUBLIC_NAME_ALIASES, SOURCE_MARKDOWN_PATH as A_SOURCE,
)
from emperor_v4.evaluation.first_item_c_evidence import load_evidence_index, project_evidence, declared_positive_values

SOURCE_MARKDOWN_PATH = Path('docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md')
SCHEMA = 'first-item-c-public-v2'
PUBLIC_FIELDS = {'公开裁决依据': 'public_basis', '公开责任边界': 'public_boundary'}
READING_FIELDS = {'公开阅读问题': 'public_question', '公开阅读正文': 'public_story',
                  '评价窗口': 'public_window', '本人责任与独立案例': 'public_cases'}
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
    for source, target in READING_FIELDS.items():
        value = fields.get(source)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'统帅正式来源缺少{source}，禁止用内部判词回退')
        result[target] = value.strip()
    if re.search(r'[A-Za-z]|统帅锚|复验|本轮|旧登记', result['public_question'] + result['public_story']):
        raise ValueError('统帅默认阅读正文仍含内部术语')
    result['public_battles'] = parse_declared_battles(fields.get('统一链战役清单', ''))
    try:
        setbacks = json.loads(fields['统一链受挫清单'])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('统帅缺少显式受挫清单，禁止从正文猜测') from exc
    if not isinstance(setbacks, list):
        raise ValueError('统帅受挫清单必须是数组')
    names = set()
    for row in setbacks:
        if not isinstance(row, dict) or set(row) != {'name', 'direction', 'process'}:
            raise ValueError('统帅受挫条目须明确名称、结果方向和过程')
        if any(not isinstance(v, str) or not v.strip() for v in row.values()):
            raise ValueError('统帅受挫条目不允许空字段')
        if row['direction'] not in {'失败', '受阻', '成败混合', '结果受损'} or row['name'] in names:
            raise ValueError('统帅受挫方向未知或条目重复')
        names.add(row['name'])
    result['public_setbacks'] = setbacks
    grade = re.fullmatch(r'([\d.]+)/40（(C-[0-5](?:-(?:LOW|MID|HIGH))?)）。', fields.get('C结算', '').replace('**', ''))
    from emperor_v4.evaluation.first_item_weights import C_POINTS
    if not grade or grade[2] not in C_POINTS or float(grade[1]) != C_POINTS[grade[2]]:
        raise ValueError('统帅公开分值与正式档位不同值')
    result['total_points'] = C_POINTS[grade[2]]
    return result


def load_first_item_c_public(root: Path) -> dict[str, dict[str, Any]]:
    rows = _parse_source_sections(root / SOURCE_MARKDOWN_PATH)
    expected = _parse_source_sections(root / A_SOURCE)
    if not rows or rows.keys() != expected.keys():
        raise ValueError('第一项C公开说明与正式A适用人物集合不一致')
    text = (root / SOURCE_MARKDOWN_PATH).read_text(encoding='utf-8')
    method = re.search(r'^- \*\*公开计分说明\*\*：(.*)$', text.split('## 一、', 1)[0], re.M)
    if not method:
        raise ValueError('统帅缺少上游公开计分说明')
    projected = {}
    evidence_index = load_evidence_index(root)
    for name, fields in rows.items():
        record = project_commander(fields)
        record['public_evidence'] = project_evidence(fields.get('公共战役证据链'), evidence_index, person=name)
        try:
            battle_refs = json.loads(fields.get('战役清单引用', ''))
        except (ValueError, TypeError) as exc:
            raise ValueError(f'C已定档清单缺少显式公共本人引用：{name}') from exc
        if not isinstance(battle_refs, dict) or set(battle_refs) != {b['name'] for b in record['public_battles']}:
            raise ValueError(f'C已定档清单与公共引用不同集：{name}')
        for battle in record['public_battles']:
            declared = battle_refs[battle['name']]
            matches = [e for e in record['public_evidence'] if all(e.get(k) == declared.get(k) for k in ('war_event_id', 'kind', 'ref'))]
            if len(matches) != 1 or matches[0]['disposition'] not in {'采用', '同情境合并'}:
                raise ValueError(f'C战役清单引用未采用的本人材料：{name}/{battle["name"]}')
            evidence = matches[0]
            if (battle['role'], battle['result'], battle['difficulty']) not in declared_positive_values(evidence_index, declared):
                raise ValueError(f'C清单的本人角色、战果档或难度与公共登记不同值：{name}/{battle["name"]}')
            parent = evidence_index['records'][evidence['war_event_id']]
            battle['public_source'] = evidence['public_source']
            if parent.get('record_level') != 'person_command_result_registration' and parent.get('settlement_scope') != 'PERSON_RESULT_ONLY':
                battle['archive_url'] = 'military.html#battle=' + evidence['war_event_id']
        try:
            setback_refs = json.loads(fields.get('受挫清单引用', ''))
        except (ValueError, TypeError) as exc:
            raise ValueError(f'C受挫清单缺少显式公共本人引用：{name}') from exc
        if not isinstance(setback_refs, dict) or set(setback_refs) != {b['name'] for b in record['public_setbacks']}:
            raise ValueError(f'C受挫清单与公共引用不同集：{name}')
        for setback in record['public_setbacks']:
            declared_refs = setback_refs[setback['name']]
            if not isinstance(declared_refs, list) or not declared_refs:
                raise ValueError(f'C受挫未绑定公共材料：{name}/{setback["name"]}')
            setback['public_sources'] = []
            for declared in declared_refs:
                if not isinstance(declared, dict) or set(declared) != {'war_event_id', 'kind', 'ref'}:
                    raise ValueError(f'C受挫公共引用格式错误：{name}')
                matches = [e for e in record['public_evidence'] if all(e.get(k) == declared[k] for k in declared)]
                if len(matches) != 1:
                    raise ValueError(f'C受挫未绑定当前本人证据链：{name}/{setback["name"]}')
                if matches[0]['disposition'] in {'窗口外', '独立方向', '同名异人'}:
                    raise ValueError(f'C受挫引用超出本人主链窗口：{name}/{setback["name"]}')
                setback['public_sources'].append(matches[0]['public_source'])
        refs = re.findall(r'\[[^\]]+\]\(([^)]+)\)', fields.get('材料来源', ''))
        if not refs:
            raise ValueError(f'统帅缺少史源引用：{name}')
        sources = [SOURCE_MARKDOWN_PATH.as_posix()]
        for ref in refs:
            parsed = urlsplit(ref)
            if parsed.scheme:
                raise ValueError('C史料须先进入公共战役登记，不能在C材料来源另起直引证据链')
            else:
                path = (root / SOURCE_MARKDOWN_PATH.parent / parsed.path).resolve()
                if not path.is_file() or not path.is_relative_to(root.resolve()):
                    raise ValueError(f'统帅史源路径无效：{ref}')
                if not path.is_relative_to((root / 'docs/公共成果/军事').resolve()):
                    raise ValueError('C事实来源须直接指公共战役登记，不得从人物画像或武将汇总反推')
                if '02-武将人才等级' in str(path):
                    raise ValueError('武将汇总仅供定位，C须绑定公共战役本人条目')
                sources.append(path.relative_to(root.resolve()).as_posix() + ('#' + parsed.fragment if parsed.fragment else ''))
        record.update(public_method=method[1], public_sources=list(dict.fromkeys(sources)))
        if set(record['public_sources'][1:]) != {e['public_source'] for e in record['public_evidence']}:
            raise ValueError(f'C材料来源未与当前公共本人证据精确绑定：{name}')
        projected[name] = record
    return projected


def public_commander_for_name(rows: dict, name: str) -> dict[str, Any]:
    return rows[PUBLIC_NAME_ALIASES.get(name, name)]


def verify_first_item_c_public(root: Path) -> dict[str, Any]:
    rows = load_first_item_c_public(root)
    return {'status': 'PASS', 'schema_version': SCHEMA, 'record_count': len(rows),
            'with_battle_list': sum(bool(row['public_battles']) for row in rows.values()),
            'battle_count': sum(len(row['public_battles']) for row in rows.values()),
            'setback_count': sum(len(row['public_setbacks']) for row in rows.values()),
            'public_evidence_bindings': sum(len(row['public_evidence']) for row in rows.values())}
