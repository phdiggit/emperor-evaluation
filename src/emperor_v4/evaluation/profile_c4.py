"""C4 current JSON validation and deterministic reader projection; never adjudicates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = Path('docs/评分结算/皇帝人物画像/C4')
JSON_PATH = DIRECTORY / '01-C4治理架构与制度设计正式结算.json'
MARKDOWN_PATH = JSON_PATH.with_suffix('.md')
PROJECTION = {'G0': (2, 7, 12), 'G1': (18, 25, 31), 'G2': (38, 45, 51),
              'G3': (58, 65, 71), 'G4': (77, 82, 87), 'G5': (91, 94, 97)}


def validate_decision(row: dict[str, Any]) -> None:
    if row['applicability']['status'] == 'NOT_APPLICABLE':
        if any(row[key] is not None for key in ('axis_grade', 'position', 'score_100', 'radar_value')):
            raise ValueError('C4不适用不得给档或投零分')
        if not row['applicability']['basis']:
            raise ValueError('C4不适用必须说明依据')
        return
    value = PROJECTION[row['axis_grade']][('LOW', 'MID', 'HIGH').index(row['position'])]
    if row['score_100'] != value or row['radar_value'] != value:
        raise ValueError('C4档位与固定投影不同值')
    if row['axis_evidence_level'] not in ('E1', 'E2', 'E3'):
        raise ValueError('C4未完成最低证据门')
    if row['axis_grade'] == 'G5':
        review = row.get('architecture_review', {})
        if review.get('magnitude') != 'AM4' or not review.get('basis') or not review.get('independence_policy'):
            raise ValueError('C4 G5缺架构量级及独立性复核')


def _grade(row: dict[str, Any]) -> str:
    return 'NOT_APPLICABLE' if row['axis_grade'] is None else f"{row['axis_grade']}-{row['position']}"


def render(payload: dict[str, Any]) -> str:
    lines = ['# C4 治理架构与制度设计能力正式结算', '',
             '> 独立人物画像轴，不进入五项总榜，不设画像总分或轴内排名。正式JSON为唯一当前档位真源。', '',
             '## 阅读说明', '',
             '按雷达值降序、同值按稳定人物ID排列，不适用列末尾并留空，不换成零分。代表父链仅作节选，完整证据、史源及归责见JSON。', '',
             '## 全池结算表', '',
             '| 人物 | 档位 | 雷达值 | 证据 | 典型模式 |', '|---|---|---:|---|---|']
    for row in payload['records']:
        value = '—' if row['radar_value'] is None else str(row['radar_value'])
        pattern = row['typical_pattern'].replace('|', '／').replace('\n', ' ')
        lines.append(f"| {row['ruler_name']} | {_grade(row)} | {value} | {row['axis_evidence_level']} | {pattern} |")
    lines.extend(['', '## 逐人裁决依据'])
    for row in payload['records']:
        lines.extend(['', f"### {row['ruler_name']}（{row['ruler_id']}）", '',
                      f"- 结算：**{_grade(row)}**；雷达值：{row['radar_value'] if row['radar_value'] is not None else '不适用'}；{row['axis_evidence_level']} / {row['confidence']}。",
                      f"- 实际权力窗口：{row['actual_power_window']}。",
                      f"- **主模式**：{row['typical_pattern']}",
                      f"- **裁档理由**：{row['grade_basis']}",
                      f"- 档内定位：{row['position_basis']}",
                      f"- **限制**：{'；'.join(row['limitations'])}"])
        if row.get('architecture_review'):
            lines.extend(['', '#### 架构量级复核', '', row['architecture_review']['basis'].replace('**限制**', '**结构下沿**')])
        parents = {p['parent_id']: p for p in row['parent_chains']}
        for parent_id in row['representative_parent_ids']:
            parent = parents[parent_id]
            body = parent['mechanism']
            if len(body) > 360:
                body = body[:360] + '……（节选，完整内容见正式JSON）'
            lines.extend(['', f"- 代表父链：**{parent['title']}**：{body}"])
        lines.extend(['', '- 来源：' + '；'.join(f'`{ref}`' for ref in row['source_refs'])])
    return '\n'.join(lines) + '\n'


def verify(root: Path = ROOT) -> dict[str, Any]:
    payload = load_json(root / JSON_PATH)
    pool = {r['ruler_id']: r for r in load_json(root / 'config/common/canonical-ruler-pool.json')['records'] if r['pool_status'] == 'INCLUDED'}
    records = payload['records']
    if len(records) != len(pool) or {r['ruler_id'] for r in records} != set(pool) or payload['record_count'] != len(records):
        raise ValueError('C4规范池覆盖不一致')
    expected_order = sorted(records, key=lambda row: (-(row['radar_value'] if row['radar_value'] is not None else -1), row['ruler_id']))
    if records != expected_order:
        raise ValueError('C4展示顺序不符合声明')
    if any(payload[key] for key in ('profile_total_enabled', 'profile_ranking_enabled', 'composite_ranking_write', 'database_write')):
        raise ValueError('C4不得生成画像总分、排名或写入综合榜')
    evidence = load_json(root / DIRECTORY / '02-C4裁决依据.json')['records']
    by_evidence = {e['evidence_id']: e for e in evidence}
    source_cache: dict[str, set[tuple[str, str]]] = {}

    def source_pairs(value: Any) -> set[tuple[str, str]]:
        if isinstance(value, dict):
            pairs = {(key, item) for key, item in value.items() if isinstance(item, str)}
            for item in value.values():
                if isinstance(item, (dict, list)):
                    pairs.update(source_pairs(item))
            return pairs
        if isinstance(value, list):
            pairs = set()
            for item in value:
                pairs.update(source_pairs(item))
            return pairs
        return set()
    for row in records:
        validate_decision(row)
        person = pool[row['ruler_id']]
        for key in ('ruler_name', 'polity', 'actual_power_window'):
            if row[key] != person[key]:
                raise ValueError(f'C4规范身份或窗口不同值: {row["ruler_id"]}/{key}')
        if row['task_code'] != 'PROFILE-C4-' + row['ruler_id']:
            raise ValueError('C4任务ID不稳定')
        parents = row['parent_chains']
        ids = {p['parent_id'] for p in parents}
        if len(ids) != len(parents) or not set(row['representative_parent_ids']) <= ids or not parents:
            raise ValueError('C4父链或代表链无效')
        if not row['grade_basis'] or not row['position_basis'] or not row['limitations']:
            raise ValueError('C4裁决依据不完整')
        for ref in row['source_refs'] + [ref for p in parents for ref in p['source_refs']]:
            file, _, anchor = ref.partition('#')
            if not (root / file).is_file():
                raise ValueError(f'C4来源不存在: {ref}')
            if anchor.startswith('evidence_id='):
                item = by_evidence.get(anchor.removeprefix('evidence_id='))
                if item is None or item['ruler_id'] != row['ruler_id'] or not item['historical_source_descriptions']:
                    raise ValueError(f'C4证据身份或史源未闭合: {ref}')
            elif '=' in anchor:
                if file not in source_cache:
                    source_cache[file] = source_pairs(load_json(root / file))
                key, value = anchor.split('=', 1)
                if (key, value) not in source_cache[file]:
                    raise ValueError(f'C4来源锚未定位: {ref}')
            elif anchor.startswith('L') and anchor[1:].isdigit():
                if not 1 <= int(anchor[1:]) <= len((root / file).read_text(encoding='utf-8').splitlines()):
                    raise ValueError(f'C4来源行号越界: {ref}')
    outside = load_json(root / DIRECTORY / '03-C4池外裁决保留.json')['records']
    if {r['ruler_id'] for r in outside} & set(pool):
        raise ValueError('C4池外裁决混入正式池')
    if (root / MARKDOWN_PATH).read_text(encoding='utf-8') != render(payload):
        raise ValueError('C4 JSON与阅读视图不同值')
    return {'status': 'PASS', 'record_count': len(records), 'applicable_count': sum(r['axis_grade'] is not None for r in records), 'outside_pool_preserved': len(outside), 'scope': '身份、规范窗口、固定投影、父链来源和阅读同值；不以结构检查替代用户裁决的历史语义判断。'}
