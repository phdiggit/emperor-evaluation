"""Read-only A-axis contract checks and deterministic reading views.

Person-level adjudications live exclusively in the formal JSON. This module
never chooses a package, changes a grade, or writes a formal score.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from math import floor
import json

from emperor_v4.evaluation.formal_json_store import load_json

BASE = Path('docs/评分结算/第四项文明与国家整合收益')
JSON_PATH = BASE / '01-第四项文明与国家整合收益正式结算.json'
A_PATH = BASE / '国家共同体与社会整合/01-皇帝A项正式结算.md'
TOTAL_PATH = BASE / '02-第四项文明与国家整合收益正式总榜.md'
POINTS = {0: (0, 0, 0), 1: (3, 4.5, 6), 2: (7.5, 9.5, 11.5),
          3: (13.5, 16, 18), 4: (19, 21, 22.5)}
BANDS = ('LOW', 'MID', 'HIGH')
LABELS = {'LOW': '低位', 'MID': '中位', 'HIGH': '高位',
          'POSITIVE': '正向', 'NEGATIVE': '负向', 'BALANCED': '正负相抵',
          'ELIGIBLE': '接受计分', 'REVOKED': '已撤销计分资格',
          'SIGNED_CIVILIZATION_ADJUSTMENT_READY': '已结算',
          'OBSERVED_OFFSETTING_OR_BALANCED_EFFECTS': '正负相抵',
          'NO_ELIGIBLE_CIVILIZATION_INCREMENT': '无合格增量',
          'NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW': '材料复核后无合格增量'}


def components(package):
    def level(value):
        if value is None:
            return 0
        if value not in ('R0', 'R1', 'R2', 'R3', 'R4'):
            raise ValueError(f'非法R级: {value}')
        return int(value[1:])
    if package.get('scoring_eligibility') == 'REVOKED':
        return 0, 0
    p, n = package.get('positive_component_level'), package.get('negative_component_level')
    if p is not None or n is not None:
        return level(p), level(n)
    strength = level(package.get('relative_change_level'))
    direction = package['direction']
    if direction not in ('POSITIVE', 'NEGATIVE'):
        raise ValueError(f"混合包缺少正负组件: {package['package_code']}")
    return (strength, 0) if direction == 'POSITIVE' else (0, strength)


def net_result(packages):
    eligible = [p for p in packages if p.get('scoring_eligibility') != 'REVOKED']
    if len(eligible) > 2:
        raise ValueError('A轴接受计分包超过两个')
    positives, negatives, hard = [], [], []
    for package in eligible:
        p, n = components(package)
        if p:
            positives.append(p)
        if n:
            negatives.append(n)
        if package.get('hard_negative_gate') == 'ACTIVE':
            if n < 2:
                raise ValueError(f"硬负向缺少R2以上负组件: {package['package_code']}")
            hard.append(n)
    def strength(values):
        return min(4, max(values) + (0.5 if len(values) > 1 else 0)) if values else 0
    p, n = strength(positives), strength(negatives)
    v = p - n
    grade = min(4, max(1, floor(abs(v)))) if v else 0
    protected = ((4 in positives and max(negatives, default=0) <= 1)
                 or (4 in negatives and max(positives, default=0) <= 1))
    if protected:
        grade = 4
    h = max(hard, default=0)
    if h and v < 0:
        grade = max(grade, h - 1)
    if h and v > 0:
        grade = min(grade, 5 - h)
    high_forbidden = bool((h and v > 0) or (protected and min(p, n) > 0))
    return {'P': p, 'N': n, 'H': h, 'grade': f'CIV{grade}',
            'direction': 'POSITIVE' if v > 0 else 'NEGATIVE' if v < 0 else 'BALANCED',
            'high_forbidden': high_forbidden}


def verify(root: Path, *, check_views=True):
    payload = load_json(root / JSON_PATH)
    packages = payload['accepted_packages']
    by_code = {p['package_code']: p for p in packages}
    errors = []
    if len(by_code) != len(packages):
        errors.append('影响包代码重复')
    ids = [r['ruler_id'] for r in payload['records']]
    if len(set(ids)) != len(ids):
        errors.append('人物ID重复')
    used = Counter()
    for row in payload['records']:
        axes = row['axis_results']
        if Counter(a['axis'] for a in axes) != Counter('ABC'):
            errors.append(f"{row['ruler_name']}: 三轴缺失或重复")
            continue
        a = next(a for a in axes if a['axis'] == 'A')
        refs = a['package_refs']
        if len(refs) != len(set(refs)) or any(c not in by_code for c in refs):
            errors.append(f"{row['ruler_name']}: 引用缺失或重复")
            continue
        selected = [by_code[c] for c in refs]
        for package in selected:
            used[package['package_code']] += 1
            if package['axis'] != 'A' or package['ruler_id'] != row['ruler_id']:
                errors.append(f"{row['ruler_name']}: 跨人或跨轴引用")
            if package.get('scoring_eligibility') != 'REVOKED':
                if package.get('source_coverage') == 'INSUFFICIENT' or not package.get('source_refs'):
                    errors.append(f"{row['ruler_name']}: 计分包证据门未闭合")
                if package.get('attribution_strength') in (None, '', 'POLITY_OR_RULER_PENDING'):
                    errors.append(f"{row['ruler_name']}: 归责未闭合")
        try:
            result = net_result(selected)
        except ValueError as exc:
            errors.append(f"{row['ruler_name']}: {exc}")
            continue
        eligible = [p for p in selected if p.get('scoring_eligibility') != 'REVOKED']
        if eligible:
            if a['magnitude_grade'] != result['grade'] or a['direction'] != result['direction']:
                errors.append(f"{row['ruler_name']}: 正负组件与轴级方向/幅度不一致")
            grade = int(result['grade'][3:])
            if grade:
                if a['band'] not in BANDS:
                    errors.append(f"{row['ruler_name']}: 带位非法")
                    continue
                expected = POINTS[grade][BANDS.index(a['band'])] * (1 if result['P'] > result['N'] else -1)
                if result['high_forbidden'] and a['band'] == 'HIGH':
                    errors.append(f"{row['ruler_name']}: 违反HIGH上限")
            else:
                expected = 0
            if a['signed_adjustment'] != expected:
                errors.append(f"{row['ruler_name']}: 档位与分值不一致")
        elif a['signed_adjustment'] != 0:
            errors.append(f"{row['ruler_name']}: 无接受包却有非零分")
        if row['fourth_item_signed_adjustment'] != sum(x['signed_adjustment'] for x in axes):
            errors.append(f"{row['ruler_name']}: 第四项合计不一致")
    for package in packages:
        if package['axis'] == 'A' and used[package['package_code']] != 1:
            errors.append(f"A包未被唯一引用: {package['package_code']}")
    ranked = sorted(payload['records'], key=lambda r: (-r['fourth_item_signed_adjustment'], r['ruler_id']))
    for row in ranked:
        expected = 1 + sum(r['fourth_item_signed_adjustment'] > row['fourth_item_signed_adjustment'] for r in ranked)
        if row['rank'] != expected:
            errors.append(f"{row['ruler_name']}: 总榜竞争排名不一致")
    if check_views:
        for path, text in render(payload).items():
            if not (root/path).exists() or (root/path).read_text(encoding='utf-8') != text:
                errors.append(f'阅读视图不同值: {path}')
    audit_path = payload.get('semantic_closure_audit', {}).get('path')
    if audit_path:
        audit = json.loads((root / BASE / audit_path).read_text(encoding='utf-8'))
        review = audit.get('a_axis_review', {})
        review_ids = [r['ruler_id'] for r in review.get('rulers', [])]
        if Counter(review_ids) != Counter(ids):
            errors.append('A轴全池复核矩阵缺人或重复')
        pending = sum(r['status'].startswith('PENDING') for r in review.get('rulers', []))
        if review.get('remaining_count') != pending:
            errors.append('A轴未决数与逐人状态不同值')
        if payload.get('status') != audit.get('status'):
            errors.append('正式入口与共享审计的语义状态分叉')
        if payload.get('status') == 'FORMAL_SEMANTIC_CLOSURE_COMPLETE':
            if pending or any(pair['status'].startswith('CHRONOLOGICAL_NEIGHBORS_ONLY')
                              for segment in audit['dynasty_curve_segments']
                              for pair in segment['adjacent_handoff_pairs']):
                errors.append('仍有待审或未经验证的交班，却宣称全池语义完成')
    if errors:
        raise ValueError('\n'.join(errors))
    gates = [payload.get(key, {}) for key in ('promotion_gate', 'coverage_completion_gate')]
    return {'status': 'PASS', 'scope': 'A_AXIS_CONTRACT_AND_READING_VIEW_COHERENCE',
            'ruler_count': len(ids), 'a_package_count': sum(p['axis'] == 'A' for p in packages),
            'semantic_review_complete': all(g and all(v is True for v in g.values()) for g in gates)}


def render(payload):
    def fmt(value):
        return f'{value:+g}' if value else '0'
    def clean(value):
        return str(value or '未单独记录').replace('|', '／').replace('\n', ' ')
    def label(value):
        return LABELS.get(value, value or '—')
    by_code = {p['package_code']: p for p in payload['accepted_packages']}
    rows = payload['records']
    gates = [payload.get(k, {}) for k in ('promotion_gate', 'coverage_completion_gate')]
    complete = all(g and all(v is True for v in g.values()) for g in gates)
    state = ('全池语义门已关闭。' if complete else '当前仍有语义复核事项；结构、公式和阅读视图同值不代表全池语义验收完成。')
    arows = [(r, next(a for a in r['axis_results'] if a['axis'] == 'A')) for r in rows]
    arows.sort(key=lambda item: (-item[1]['signed_adjustment'], item[0]['ruler_id']))
    lines = ['# 秦至清第四项A轴国家共同体与社会整合正式结算', '',
             '规则见[第四项规则与计分合同](../../../分项规则/第四项文明与国家整合收益/00-规则与计分合同.md)。', '',
             '本阅读版只读取正式 JSON；不以阅读视图反推人物裁决。', '', state, '',
             '本轴结算可归责的社会整合净收益；正向结构贡献与独立负向损害分别进入P、N，不是整合能力或历史声望排名。', '',
             f'共{len(rows)}人；正向{sum(a["signed_adjustment"]>0 for _,a in arows)}人，负向{sum(a["signed_adjustment"]<0 for _,a in arows)}人，零值{sum(a["signed_adjustment"]==0 for _,a in arows)}人。', '',
             '## 全榜', '', '| 排名 | 皇帝 | 政权 | 处置 | 相对档 | 带位 | 调整 |',
             '| ---: | --- | --- | --- | --- | --- | ---: |']
    ranks = {}
    for i, (r, a) in enumerate(arows, 1):
        rank = ranks.setdefault(a['signed_adjustment'], i)
        lines.append(f'| {rank} | {r["ruler_name"]} | {r["polity"]} | {label(a["disposition"])} | {a.get("magnitude_grade") or "—"} | {label(a.get("band"))} | {fmt(a["signed_adjustment"])} |')
    lines += ['', '## 触发人物与结算依据', '']
    for r, a in arows:
        if not a['package_refs']:
            continue
        lines += [f'### {r["ruler_name"]}（{fmt(a["signed_adjustment"])}；{a.get("magnitude_grade") or "无合格增量"}·{a.get("band") or "—"}）', '']
        result = net_result([by_code[c] for c in a['package_refs']])
        lines += [f'轴级净算：P={result["P"]:g}，N={result["N"]:g}，H={result["H"]}。处置：{label(a["disposition"])}。', '']
        for code in a['package_refs']:
            p = by_code[code]
            lines += [f'- **影响包 `{code}`**（{label(p.get("scoring_eligibility", "ELIGIBLE"))}）']
            fields = [('继承基线','inherited_baseline'),('本人变化','attributable_change'),('层级依据','relative_change_level_basis'),('覆盖','field_coverage'),('持续性与交班','durability_and_handoff'),('归责','attribution_strength')]
            for field_label, key in fields:
                lines.append(f'  - {field_label}：{clean(p.get(key))}')
            lines.append(f'  - 反证与限制：{clean(p.get("counterevidence", {}).get("summary"))}')
            lines.append(f'  - 硬负向门：{p.get("hard_negative_gate", "NONE")}；证据覆盖：{p.get("source_coverage")}。')
            lines.append('  - 史源：' + '；'.join(clean(s) for s in p.get('source_refs', [])))
            lines.append('')
    total = ['# 秦至清第四项文明与国家整合收益正式总榜', '',
             '> 机器真源为 `01-第四项文明与国家整合收益正式结算.json`；总调整为A、B、C三轴之和，按竞争排名列示。', '', state, '',
             f'共{len(rows)}人：正向{sum(r["fourth_item_signed_adjustment"]>0 for r in rows)}人、负向{sum(r["fourth_item_signed_adjustment"]<0 for r in rows)}人、零值{sum(r["fourth_item_signed_adjustment"]==0 for r in rows)}人。', '',
             '| 排名 | 皇帝 | 政权 | A 国家共同体与社会整合 | B 教育可及与人才流动 | C 文化知识生产传播与生态 | 第四项总调整 | 触发轴数 |',
             '| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in sorted(rows, key=lambda r: (-r['fourth_item_signed_adjustment'], r['ruler_id'])):
        scores = {a['axis']: a['signed_adjustment'] for a in r['axis_results']}
        total.append(f'| {r["rank"]} | {r["ruler_name"]} | {r["polity"]} | {fmt(scores["A"])} | {fmt(scores["B"])} | {fmt(scores["C"])} | **{fmt(r["fourth_item_signed_adjustment"])}** | {r["triggered_axis_count"]} |')
    return {A_PATH: '\n'.join(lines).rstrip()+'\n', TOTAL_PATH: '\n'.join(total)+'\n'}


def write_views(root: Path):
    verify(root, check_views=False)
    payload = load_json(root / JSON_PATH)
    for path, text in render(payload).items():
        (root/path).write_text(text, encoding='utf-8', newline='\n')
    return verify(root)
