"""Consume authored M1 reading without deriving a verdict or historical prose."""
from __future__ import annotations

import re
import posixpath
import json
from pathlib import Path
from urllib.parse import quote

SCHEMA = 'profile-m1-authored-reading-v1'
FIELDS = ('headline', 'summary', 'grade_reason', 'position_reason', 'higher_grade_limit')
CASE_FIELDS = ('title', 'action', 'result', 'meaning', 'boundary')
INTERNAL = re.compile(r'G[0-5]|D[0-4]|材料底池|本轮|父卡|消费|闭合|例外路径|逐项复核|规范军事登记')


def public_grade(row: dict) -> str:
    return {'G0':'E','G1':'D','G2':'C','G3':'B','G4':'A','G5':'S'}[row['axis_grade']] + {'LOW':'−','MID':'','HIGH':'+'}[row['position']]


def validate_public_reading(row: dict) -> None:
    reading = row.get('public_reading')
    if reading is None:
        return
    if not isinstance(reading, dict) or reading.get('schema_version') != SCHEMA:
        raise ValueError('M1公开正文版本无效')
    required = {'schema_version', 'cases', *FIELDS}
    if not required <= set(reading) or set(reading) - required - {'career_review', 'comparisons', 'sources'}:
        raise ValueError('M1公开正文须完整声明人物结论、事例与定档说明')
    for key in FIELDS:
        if key == 'summary' and reading[key] == '':
            continue
        _prose(reading[key])
    for item in reading.get('career_review', []):
        if set(item) != {'title', 'basis', 'battle_refs'} or not item['battle_refs']:
            raise ValueError('M1生涯说明须绑定战役或本人行动记录')
        _prose(item['title'])
        _prose(item['basis'])
    comparator_ids = set()
    for item in reading.get('comparisons', []):
        if not {'ruler_id', 'basis'} <= set(item) or set(item) - {'ruler_id', 'basis', 'comparison_role'} or not isinstance(item['ruler_id'], str) or not item['ruler_id'] or item['ruler_id'] == row.get('ruler_id') or item['ruler_id'] in comparator_ids:
            raise ValueError('M1公开比较须唯一绑定其他人物的当前M1记录')
        comparator_ids.add(item['ruler_id'])
        _prose(item['basis'])
    cases = reading['cases']
    if not isinstance(cases, list) or (not cases and not reading.get('sources')):
        raise ValueError('M1公开正文缺少具名事例')
    roles = {item['capability_episode_ref']: item for item in row['m1_role_projection']['items']}
    parents = {item['parent_ref']: item for item in row.get('representative_parent_contexts', [])}
    stability = {item['cycle_ref']: item for item in (row.get('m1_stability_review') or {}).get('cases', [])}
    seen = set()
    for case in cases:
        compact = {'episode_ref', 'sources', 'title', 'text'} <= set(case) and not (set(case) - {'episode_ref', 'sources', 'title', 'text', 'role_label'})
        if not compact and set(case) != {'episode_ref', 'sources', *CASE_FIELDS}:
            raise ValueError('M1公开事例须分别说明本人行动、结果、能力含义与责任边界')
        ref = case['episode_ref']
        if ref not in roles and ref not in parents and ref not in stability or ref in seen:
            raise ValueError('M1公开事例须唯一绑定本人正式角色记录')
        seen.add(ref)
        for key in (('title', 'text') if compact else CASE_FIELDS):
            _prose(case[key])
        if case.get('role_label'):
            _prose(case['role_label'])
        allowed = set(roles.get(ref, {}).get('source_refs', [])) | set(parents.get(ref, {}).get('source_refs', [])) | set(stability.get(ref, {}).get('source_refs', []))
        allowed.add('docs/评分结算/人物画像/M1/01-M1军事判断与统帅能力正式结算.json#ruler_id=' + str(row.get('ruler_id', '')))
        if not case['sources']:
            raise ValueError('M1公开事例缺少来源')
        for source in case['sources']:
            if set(source) != {'ref', 'label'} or source['ref'] not in allowed:
                raise ValueError('M1公开来源未在对应本人情境中登记')
            _prose(source['label'])
    for source in reading.get('sources', []):
        if set(source) != {'ref', 'label'} or not source['ref'].startswith(('docs/', 'config/', 'https://', 'http://')):
            raise ValueError('M1公开来源路径无效')
        _prose(source['label'])


def load_archive_context(root: Path) -> dict:
    """One operation owns its evidence indexes; nothing is cached across edits."""
    from .battle_registry_store import load_battle_registry
    from .formal_json_store import load_json
    from .profile_registry import profile_axis_entry
    battles = {r['war_event_id']: r for r in load_battle_registry(root / 'docs/公共成果/军事/01-战役登记.json')['records']}
    index = json.loads((root / 'reader/data/military/battles-index.json').read_text(encoding='utf-8'))
    commanders = json.loads((root / 'reader/data/military/commanders-index.json').read_text(encoding='utf-8'))
    registry_path = root / 'docs/公共成果/军事/01-战役登记.json'
    manifest = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else {}
    locations = {}
    for shard in manifest.get('shards', []):
        shard_path = registry_path.parent / shard['path']
        for record in json.loads(shard_path.read_text(encoding='utf-8'))['records']:
            locations[record['war_event_id']] = shard_path.relative_to(root).as_posix() + '#war_event_id=' + record['war_event_id']
    return {'battles': battles, 'index': index, 'indexed_ids': {r['id'] for r in index['records']},
            'locations': locations,
            'commanders': {r['profile_ref']: r for r in commanders['records']},
            'peers': {r['ruler_id']: r for r in load_json(root / profile_axis_entry('M1')['json'])['records']}}


def _prose(value: object) -> None:
    if not isinstance(value, str) or not value.strip() or INTERNAL.search(value):
        raise ValueError('M1公开正文缺失或含内部核对术语')


def archive_projection(row: dict, root: Path, context: dict | None = None) -> dict:
    """Resolve existing archive IDs only; commander grades are never consumed."""
    reading = row.get('public_reading') or {}
    if not reading.get('career_review') and not reading.get('comparisons'):
        return {}
    validate_public_reading(row)
    context = context or load_archive_context(root)
    battles, indexed_ids = context['battles'], context['indexed_ids']
    profile_ref = (row.get('m1_role_projection') or {}).get('profile_ref')
    commander = context['commanders'].get(profile_ref)
    if profile_ref and commander is None:
        raise ValueError('M1本人武将档案连接缺失')
    result = {'commander': {'label': commander['name'] + '的武将档案',
                            'href': 'military.html#commander=' + quote(profile_ref, safe='')} if commander else None,
              'career': [], 'comparisons': []}
    for item in reading.get('career_review', []):
        links = []
        for ref in item['battle_refs']:
            if ref not in battles:
                raise ValueError('M1生涯说明引用了不存在的战役或本人行动')
            battle = battles[ref]
            if ref in indexed_ids:
                links.append({'label': battle['canonical_label'], 'href': 'military.html#battle=' + quote(ref, safe='')})
            elif battle.get('settlement_scope') == 'PERSON_RESULT_ONLY' and battle.get('public_outcome_registered') is False:
                # Personal action supplements are not new public battles.
                refs = battle.get('source_refs', [])
                if not refs:
                    raise ValueError('M1本人行动补充缺少原始依据')
                valid = [source for source in refs if source.startswith(('https://', 'http://'))]
                if valid:
                    links.extend({'label': battle['canonical_label'] + ' · 本人行动依据', 'href': source} for source in valid)
                elif ref in context.get('locations', {}):
                    links.append({'label': battle['canonical_label'] + ' · 本人行动正式记录（含原始引用）', 'ref': context['locations'][ref]})
                else:
                    raise ValueError('M1本人行动依据缺少可定位的公开来源')
            else:
                raise ValueError('M1战役档案尚未生成，须先同步既有档案索引')
        result['career'].append({'title': item['title'], 'basis': item['basis'], 'links': links})
    if reading.get('comparisons'):
        peers = context['peers']
        for item in reading['comparisons']:
            if item['ruler_id'] not in peers:
                raise ValueError('M1比较人物缺少当前正式M1记录')
            role = item.get('comparison_role')
            peer = peers[item['ruler_id']]
            same = [r for r in peers.values() if r['ruler_id'] != row.get('ruler_id') and (r['axis_grade'], r['position']) == (row['axis_grade'], row['position'])]
            if role == 'SAME_POSITION' and (peer['axis_grade'], peer['position']) != (row['axis_grade'], row['position']):
                raise ValueError('M1同档同位参照不符当前正式位置')
            if role == 'NO_SAME_POSITION_PEER' and (same or peer['axis_grade'] != row['axis_grade'] or peer['position'] == row['position']):
                raise ValueError('M1同档邻位例外不符合当前池')
            if role == 'POSITION_CONTRAST' and (peer['axis_grade'] != row['axis_grade'] or peer['position'] == row['position']):
                raise ValueError('M1位置对照须同档异位')
            if role not in {None, 'SAME_POSITION', 'NO_SAME_POSITION_PEER', 'POSITION_CONTRAST'}:
                raise ValueError('M1比较类型未知')
            projected = comparison_projection(row, peer, item['basis'])
            if role == 'NO_SAME_POSITION_PEER':
                projected['relation'] = '同档邻位（本位无其他样本）'
                projected['label'] = projected['relation'] + ' · ' + projected['name'] + ' ' + projected['grade']
            result['comparisons'].append(projected)
    return result


def comparison_projection(row: dict, peer: dict, basis: str) -> dict:
    """Project current M1 labels and a direct axis route, never a new verdict."""
    letters = {'G0': 'E', 'G1': 'D', 'G2': 'C', 'G3': 'B', 'G4': 'A', 'G5': 'S'}
    positions = {'LOW': '−', 'MID': '', 'HIGH': '+'}
    if peer.get('axis_grade') not in letters or peer.get('position') not in positions:
        raise ValueError('M1比较对象没有可展示的当前档位')
    grade = letters[peer['axis_grade']] + positions[peer['position']]
    relation = '同轴参照'
    if peer['axis_grade'] == row['axis_grade']:
        relation = ('同档同位' if peer['position'] == row['position'] else
                    '同档' + {'LOW': '低位', 'MID': '中位', 'HIGH': '高位'}[peer['position']] + '参照')
    return {'name': peer['ruler_name'], 'grade': grade, 'relation': relation,
            'label': relation + ' · ' + peer['ruler_name'] + ' ' + grade, 'basis': basis,
            'href': 'index.html#person/' + quote(peer['ruler_id'], safe='') + '/profile/M1'}


def markdown_reading(row: dict, context: dict | None = None) -> list[str]:
    validate_public_reading(row)
    p = row['public_reading']
    letter = {'G0': 'E', 'G1': 'D', 'G2': 'C', 'G3': 'B', 'G4': 'A', 'G5': 'S'}[row['axis_grade']]
    grade = letter + {'LOW': '−', 'MID': '', 'HIGH': '+'}[row['position']]
    confidence = {'LOW': '低', 'MEDIUM': '中', 'HIGH': '高'}.get(row['confidence'], row['confidence'])
    lines = [f"**军事判断与统帅能力：{grade}**", '', f'判断把握：{confidence}。', '', f"**{p['headline']}**", '', p['summary'], '']
    archive = archive_projection(row, Path(__file__).resolve().parents[3], context) if p.get('career_review') or p.get('comparisons') else {}
    if archive.get('commander'):
        commander = archive['commander']
        archive_target = posixpath.relpath('reader/' + commander['href'], 'docs/评分结算/人物画像/M1')
        lines += [f"[{commander['label']}]({archive_target})", '']
    if p.get('career_review'):
        lines += ['#### 主要战事的本人作用', '']
        for item, projected in zip(p['career_review'], archive['career'], strict=True):
            lines += ['**' + item['title'] + '**：' + item['basis'], '']
            lines += ['<details><summary>相关战役与本人行动档案</summary>', '']
            for source in projected['links']:
                target = source.get('href') or source['ref']
                if target.startswith('military.html'):
                    target = posixpath.relpath('reader/' + target, 'docs/评分结算/人物画像/M1')
                elif target.startswith(('docs/', 'config/')):
                    target = posixpath.relpath(target, 'docs/评分结算/人物画像/M1')
                lines.append(f"- [{source['label']}]({target})")
            lines += ['', '</details>', '']
    for case in p['cases']:
        if 'text' in case:
            lines += [f"#### {case['title']}", '', *( [case['role_label'], ''] if case.get('role_label') else [] ), case['text'], '', '<details><summary>事例来源与正式归责依据</summary>', '']
        else:
            lines += [f"#### {case['title']}", '', '**本人行动**：' + case['action'], '',
                  '**结果与能力**：' + case['result'] + case['meaning'], '',
                  '**本人作用的边界**：' + case['boundary'], '',
                  '<details><summary>这件事的史料</summary>', '']
        for source in case['sources']:
            ref = source['ref']
            if ref.startswith(('docs/', 'config/')):
                path, separator, anchor = ref.partition('#')
                ref = posixpath.relpath(path, 'docs/评分结算/人物画像/M1') + (separator + anchor if separator else '')
            lines.append(f"- [{source['label']}]({ref})")
        lines += ['', '</details>', '']
    position_title = {'LOW': '为什么取低位（−）？', 'MID': '为什么取中位？', 'HIGH': '为什么取高位（+）？'}[row['position']]
    lines += [f'#### 为什么评为 {letter} 档？', '', p['grade_reason'], '',
              '#### ' + position_title, '', p['position_reason'], '',
              ('#### 当前等级的边界' if row['axis_grade'] == 'G5' else '#### 为什么没有进入更高档？'), '', p['higher_grade_limit'], '']
    if p.get('comparisons'):
        lines += ['#### 同轴比较', '']
        for item in archive['comparisons']:
            target = posixpath.relpath('reader/' + item['href'], 'docs/评分结算/人物画像/M1')
            lines += [f"[{item['label']}]({target})", '', item['basis'], '']
    if p.get('sources'):
        lines += ['<details><summary>正式归责与相关来源</summary>', '']
        for source in p['sources']:
            ref = source['ref']
            if ref.startswith(('docs/', 'config/')):
                path, separator, anchor = ref.partition('#')
                ref = posixpath.relpath(path, 'docs/评分结算/人物画像/M1') + (separator + anchor if separator else '')
            lines.append(f"- [{source['label']}]({ref})")
        lines += ['', '</details>', '']
    return lines
