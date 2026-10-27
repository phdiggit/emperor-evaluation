"""C4 current JSON validation and deterministic reader projection; never adjudicates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = Path('docs/评分结算/人物画像/C4')
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
        if review.get('magnitude') != 'AM4' or not review.get('basis') or not review.get('integrated_architecture_policy'):
            raise ValueError('C4 G5缺一体化架构量级复核')


def _grade(row: dict[str, Any]) -> str:
    return 'NOT_APPLICABLE' if row['axis_grade'] is None else f"{row['axis_grade']}-{row['position']}"


def _text(value: Any) -> str:
    if isinstance(value, list):
        return '\n'.join(f'- {_text(item)}' for item in value)
    if isinstance(value, dict):
        return '\n'.join(f'- {key}：{_text(item)}' for key, item in value.items())
    return str(value or '')


def render(payload: dict[str, Any]) -> str:
    lines = ['# C4 治理架构与制度设计能力正式结算', '',
             '> 独立人物画像轴。正式JSON为唯一当前档位真源。', '',
             '## 阅读说明', '',
             '按雷达值降序、同值按稳定人物ID排列，不适用列末尾并留空，不换成零分。下文展开全部现行制度过程及适用边界；条目数不等于独立设计数，整合设计的部件不重复计数。完整结构化记录见JSON。', '',
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
                      f"- **主模式**：{row['typical_pattern']}",
                      f"- **适用范围**：{row['applicability']['basis']}",
                      f"- **裁档理由**：{row['grade_basis']}",
                      f"- 档内定位：{row['position_basis']}",
                      f"- **反例与判断边界**：{row['counterpattern']}",
                      f"- **限制**：{'；'.join(row['limitations'])}"])
        if row.get('evidence_assessment_basis'):
            lines.append(f"- 材料覆盖：{row['evidence_assessment_basis']}")
        if row.get('architecture_review'):
            lines.extend(['', '#### 架构量级复核', '', row['architecture_review']['basis'].replace('**限制**', '**结构下沿**')])
        for parent in row['parent_chains']:
            lines.extend(['', f"#### {parent['title']}", '', parent['mechanism']])
            shown = {parent['mechanism']}
            for key, label in (
                ('structural_problem', '原有问题'), ('constraints', '当时的约束'),
                ('feasible_choice', '可行选择'), ('personal_choice', '本人选择'),
                ('interfaces', '职责与规则变化'), ('operation', '实际运行'),
                ('feedback', '运行反馈'), ('revision', '后续修订'),
                ('validation_boundary', '采用边界'),
            ):
                value = _text(parent.get(key))
                if value and value not in shown:
                    lines.extend(['', f'**{label}**：{value}'])
                    shown.add(value)
            lines.extend(['', f"- 正式方向：{parent['direction']}；归责：{parent['attribution']}"])
            if parent.get('consumption_status'):
                lines.append(f"- 材料用途：{parent['consumption_status']}")
            for source in parent.get('source_review', []):
                lines.extend(['', f"- 所读史源：[{source['source_title']}]({source['source_url']})"])
                for key, label in (('passage_locator', '段落定位'), ('adopted_fact', '采用事实'),
                                   ('counterevidence', '反证与限定'), ('limitation', '采用范围')):
                    if source.get(key):
                        lines.append(f"- {label}：{source[key]}")
            if parent.get('historical_source_descriptions'):
                lines.extend(['', '来源说明：' + '；'.join(parent['historical_source_descriptions'])])
            refs = list(dict.fromkeys(parent['source_refs'] + parent.get('direct_process_refs', [])))
            lines.extend(['', '- 过程依据：' + '；'.join(f'`{ref}`' for ref in refs)])
        if row.get('horizontal_calibration'):
            lines.extend(['', '#### 同轴比较', '', row['horizontal_calibration']['decision_basis']])
            for item in row['horizontal_calibration']['comparators']:
                lines.append(f"- `{item['ruler_id']}`：{item['comparison']}")
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
        for key in ('ruler_name', 'polity'):
            if row[key] != person[key]:
                raise ValueError(f'C4规范身份不同值: {row["ruler_id"]}/{key}')
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
    return {'status': 'PASS', 'record_count': len(records), 'applicable_count': sum(r['axis_grade'] is not None for r in records), 'outside_pool_preserved': len(outside), 'scope': '身份、固定投影、父链来源和阅读同值。'}
