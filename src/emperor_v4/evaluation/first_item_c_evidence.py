"""Resolve C's declared evidence directly against the public battle registry.

This module checks identities and source bindings. It neither infers personal
command from a reign nor derives a ruler's grade from battles or other profiles.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import yaml

from emperor_v4.evaluation.battle_registry_store import load_battle_registry

REGISTRY = Path('docs/公共成果/军事/01-战役登记.json')
DISPOSITIONS = {'采用', '同情境合并', '窗口外', '独立方向', '组织授权', '归责未闭', '史源冲突', '非战争取得', '同名异人', '行为责任'}
ACTOR_ALIASES = {'朱温': {'朱全忠'}, '完颜阿骨打': {'阿骨打', '金太祖'}, '完颜吴乞买': {'完颜晟', '吴乞买', '金太宗'},
                 '努尔哈赤': {'努尔哈齐'}, '刘龑': {'刘岩', '刘巖', '劉巖'}, '李存勖': {'李存勗', '唐庄宗'},
                 '铁木真': {'成吉思汗', '元太祖'}, '窝阔台': {'元太宗'}, '忽必烈': {'元世祖'},
                 '蒙哥': {'元宪宗'}, '皇太极': {'清太宗'}, '玄烨': {'康熙', '圣祖'},
                 '福临': {'顺治', '清世祖', '福臨', '顺治帝', '順治帝'}, '司马炎': {'晋武帝'},
                 '李元昊': {'元昊', '曩霄'}, '耶律阿保机': {'阿保机', '辽太祖'},
                 '刘崇': {'刘旻'}, '石敬瑭': {'石敬塘'}}


def _list(value: Any) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    return [row for row in value or [] if isinstance(row, dict)]


def load_evidence_index(root: Path) -> dict[str, Any]:
    config = yaml.safe_load((root / 'config/project.yml').read_text(encoding='utf-8'))
    registry = Path(config['retained_build_chain']['battle_registry'])
    declared = config['formal_settlements']['first_item']['c_public_projection']['evidence_registry']
    if registry.as_posix() != declared:
        raise ValueError('C证据入口与项目公共战役入口不一致')
    payload = load_battle_registry(root / registry)
    manifest = json.loads((root / registry).read_text(encoding='utf-8'))
    locations = {}
    for shard in manifest['shards']:
        path = registry.parent / shard['path']
        for row in json.loads((root / path).read_text(encoding='utf-8'))['records']:
            locations[row['war_event_id']] = path.as_posix()
    return {'records': {r['war_event_id']: r for r in payload['records']},
            'scope_notes': {r['scope_note_ref']: r for r in payload.get('person_military_scope_notes', [])},
            'locations': locations, 'registry_path': registry.as_posix()}


def resolve_binding(index: dict, binding: dict, *, person: str) -> dict:
    if binding.get('disposition') not in DISPOSITIONS or not binding.get('window_basis') or not binding.get('reason'):
        raise ValueError(f'C公共证据须声明窗口、采用处置与理由：{person}')
    kind, ref = binding.get('kind'), binding.get('ref')
    if kind == 'scope_note':
        row = index['scope_notes'].get(ref)
        if row is None or row.get('person') != person:
            raise ValueError(f'C公共范围证据不存在或人物不符：{person}/{ref}')
        if binding['disposition'] in {'采用', '同情境合并'}:
            raise ValueError('范围说明不能充当本人军事正向结果')
        source_refs = row.get('source_refs') or []
        label = row['context']
        facts = [('已证行动与范围', row.get('established_actions', ''))]
        public_source = index.get('registry_path', REGISTRY.as_posix()) + '#scope_note_ref=' + str(ref)
    else:
        parent = index['records'].get(binding.get('war_event_id'))
        if parent is None:
            raise ValueError(f'C引用不存在的公共战役：{binding.get("war_event_id")}')
        if kind == 'action':
            matches = [r for r in parent.get('personal_action_attributions', []) if r.get('evidence_ref') == ref and r.get('person') == person]
        elif kind == 'result':
            matches = [r for r in parent.get('person_command_results', [])
                       if ref in {r.get('person_command_result_ref'), r.get('result_ref'), r.get('capability_episode_ref')} and r.get('person', r.get('actor_name')) in {person, *ACTOR_ALIASES.get(person, set())}]
        elif kind == 'member':
            matches = [m for m in _list(parent.get('members')) if m.get('actor_ref') == ref]
            if matches and binding.get('actor_name') != matches[0].get('actor_name'):
                raise ValueError(f'C本人名称与公共成员不符：{person}/{ref}')
            if matches and matches[0].get('actor_name') not in {person, *ACTOR_ALIASES.get(person, set())}:
                raise ValueError(f'C不能将其他人物的公共成员转给本人：{person}/{ref}')
        else:
            raise ValueError(f'C公共证据类型未知：{kind}')
        if len(matches) != 1:
            raise ValueError(f'C公共本人证据缺失或不唯一：{person}/{binding.get("war_event_id")}/{ref}')
        row = matches[0]
        if kind == 'action' and binding['disposition'] in {'采用', '同情境合并'} and row.get('evidence_kind') == 'organization_only':
            raise ValueError('组织授权记录不能直接作为C军事解题消费')
        if binding['disposition'] in {'采用', '同情境合并'}:
            control = row.get('person_command_index') or row
            if kind == 'member' and (row.get('ruler_campaign_relation') == 'authorization_only' or control.get('consumption_mode') == 'none'):
                raise ValueError('仅授权或零消费的公共成员不能直接作为C军事解题')
            if control.get('capability_mode') == 'unresolved' or control.get('detail_status') == 'person_result_required':
                raise ValueError('公共本人角色未闭，不能直接采用为C军事证据')
            children = _list(row.get('person_command_result'))
            if 'SOURCE_CONFLICT' in str(row.get('causal_fault', '')) or any('SOURCE_CONFLICT' in str(c.get('causal_fault', '')) for c in children):
                raise ValueError('史源冲突不可作为确定的C正果或败责')
        source_refs = row.get('source_refs') or (row.get('person_command_index') or {}).get('source_refs') or parent.get('source_refs') or []
        label = row.get('canonical_label') or row.get('result_label') or parent['canonical_label']
        if kind == 'action':
            facts = [(label, row.get(key, '')) for key, label in
                     [('personal_role', '本人角色'), ('military_judgment', '判断与方案'),
                      ('implementation', '实施'), ('personal_result', '本人结果'), ('failure_and_limits', '败责与边界')]]
        else:
            facts = [('公共本人依据', row.get('basis') or (row.get('person_command_index') or {}).get('basis') or row.get('contribution_scope') or '')]
        for adverse in _list(parent.get('attributable_failures')):
            if adverse.get('actor_name') in {person, *ACTOR_ALIASES.get(person, set())} and adverse.get('basis'):
                facts.append(('原登记的本人不利或行为边界', adverse['basis']))
                source_refs = [*source_refs, *(adverse.get('source_refs') or [])]
        public_source = index.get('locations', {}).get(binding.get('war_event_id'), REGISTRY.as_posix()) + '#war_event_id=' + binding['war_event_id']
    if not source_refs:
        raise ValueError(f'C公共本人证据缺少史源：{person}/{ref}')
    if any('人物画像/' in str(source) or '/M1/' in str(source) for source in source_refs):
        raise ValueError('C公共证据不得以M1裁决反向充当史源')
    return {'label': label, 'disposition': binding['disposition'], 'window_basis': binding['window_basis'],
            'reason': binding['reason'], 'source_refs': list(dict.fromkeys(source_refs)),
            'war_event_id': binding.get('war_event_id'), 'ref': ref, 'kind': kind,
            'case_group': binding.get('case_group'), 'public_facts': [[label, value] for label, value in facts if value],
            'public_source': public_source}


def project_evidence(value: str, index: dict, *, person: str) -> list[dict]:
    try:
        bindings = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'C缺少显式公共战役证据绑定：{person}') from exc
    if not isinstance(bindings, list) or not bindings:
        raise ValueError(f'C须保留已核公共证据及其采用或排除依据：{person}')
    seen = set()
    rows = []
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError('C公共证据绑定必须是对象')
        key = (binding.get('war_event_id'), binding.get('kind'), binding.get('ref'))
        if key in seen:
            raise ValueError(f'C重复公共证据绑定：{person}/{key}')
        seen.add(key)
        rows.append(resolve_binding(index, binding, person=person))
    return rows


def declared_positive_values(index: dict, binding: dict) -> set[tuple[str, str, str]]:
    """Return only explicitly graded personal positive results, never parent guesses."""
    if binding['kind'] not in {'member', 'result'}:
        return set()
    parent = index['records'][binding['war_event_id']]
    if binding['kind'] == 'member':
        member = next(m for m in _list(parent.get('members')) if m['actor_ref'] == binding['ref'])
        rows = _list(member.get('person_command_result'))
        control = member.get('person_command_index') or {}
        if not rows:
            rows = [{'result_direction': control.get('result_direction'),
                     'result_tier': control.get('projected_result_tier'), 'combat_difficulty': control.get('projected_combat_difficulty'),
                     'capability_mode': control.get('capability_mode'), 'consumption_mode': control.get('consumption_mode')}]
    else:
        rows = [r for r in parent.get('person_command_results', [])
                if binding['ref'] in {r.get('person_command_result_ref'), r.get('result_ref'), r.get('capability_episode_ref')}]
        control = {}
    values = set()
    difficulties = {'D0': 'D', 'D1': 'C', 'D2': 'B', 'D3': 'A', 'D4': 'S', None: ''}
    for row in rows:
        if row.get('result_direction') != 'positive':
            continue
        result = row.get('result_tier', row.get('campaign_tier'))
        if not result:
            continue
        mode = row.get('capability_mode') or (row.get('military_capability_contribution') or {}).get('capability_mode') or control.get('capability_mode')
        role = '战略统筹' if mode == 'operational_design' or row.get('consumption_mode') == 'operational_result' else '前线作战'
        difficulty = '' if role == '战略统筹' else difficulties.get(row.get('combat_difficulty'))
        if difficulty is None:
            raise ValueError('公共个人结果难度枚举未知')
        values.add((role, result.replace('-', '−'), difficulty))
    return values
