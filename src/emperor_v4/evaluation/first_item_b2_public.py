"""Project the declared B2 reading prose and adjudicated component grades."""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlsplit

from emperor_v4.evaluation.first_item_public_outcomes import _parse_source_sections, SOURCE_MARKDOWN_PATH
from emperor_v4.evaluation.first_item_b1_cost_public import public_text

SOURCE = Path('docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/03-第一项B2创业组织与政治整合正式结算.md')
SCHEMA = 'first-item-b2-public-v1'
DIMENSIONS = (('并行执行', '多线并行'), ('团队能力覆盖与组织杠杆', '专业分工'), ('异质整合', '集团协作'))
LEVEL_LABELS = ('未形成', '有限辅助', '单一独立主责', '基本分工', '稳定多方分工', '体系化运行')
FIELDS = {'公开阅读问题':'public_question', '公开阅读正文':'public_story', '评价窗口':'public_window', '本人控制链':'public_control'}


def project_b2(fields: dict, *, method: str) -> dict:
    result = {target:public_text(fields.get(source), source) for source, target in FIELDS.items()}
    dimensions = []
    for field, label in DIMENSIONS:
        match = re.fullmatch(r'L([0-5])。(.*)', fields.get(field, ''))
        if not match:
            raise ValueError(f'B2档位或依据缺失：{field}')
        level = int(match[1])
        dimensions.append({'label':label, 'level':level, 'points':level * 2,
                           'basis':public_text(re.sub(r'(?<![A-Za-z0-9])L([0-5])(?![A-Za-z0-9])', lambda m:LEVEL_LABELS[int(m[1])], match[2]), field)})
    total = sum(row['points'] for row in dimensions)
    declared = re.match(r'(?:\*\*)?([\d.]+)/30', fields.get('B2结算',''))
    if not declared or float(declared[1]) != total:
        raise ValueError('B2公开分项与正式结算不同值')
    result.update(dimensions=dimensions, total_points=total, public_method=public_text(method, '公开计分说明'))
    return result


def load_first_item_b2_public(root: Path) -> dict:
    rows = _parse_source_sections(root / SOURCE)
    expected = _parse_source_sections(root / SOURCE_MARKDOWN_PATH)
    if not rows or set(rows) != set(expected):
        raise ValueError('B2阅读入口须完整覆盖当前第一项正式对象')
    text = (root / SOURCE).read_text(encoding='utf-8')
    match = re.search(r'^- \*\*公开计分说明\*\*：(.*)$', text.split('## 一、',1)[0], re.M)
    if not match:
        raise ValueError('B2缺少上游公开计分说明')
    projected = {}
    for name, fields in rows.items():
        record = project_b2(fields, method=match[1])
        refs = re.findall(r'\[[^\]]+\]\(([^)]+)\)', fields.get('材料来源',''))
        if not refs:
            raise ValueError(f'B2缺少证据引用：{name}')
        sources = [SOURCE.as_posix()]
        for ref in refs:
            parsed = urlsplit(ref)
            if parsed.scheme:
                if parsed.scheme != 'https' or not parsed.netloc:
                    raise ValueError(f'B2证据协议无效：{ref}')
                sources.append(ref)
            else:
                path = (root / SOURCE.parent / parsed.path).resolve()
                if not path.is_file() or not path.is_relative_to(root.resolve()):
                    raise ValueError(f'B2证据路径无效：{ref}')
                source = path.relative_to(root.resolve()).as_posix()
                sources.append(source + ('#'+parsed.fragment if parsed.fragment else ''))
        record['public_sources'] = list(dict.fromkeys(sources))
        projected[name] = record
    for field in ('public_question', 'public_story'):
        if len({r[field] for r in projected.values()}) != len(projected):
            raise ValueError(f'B2人物阅读入口重复：{field}')
    return projected


def verify_first_item_b2_public(root: Path) -> dict:
    records = load_first_item_b2_public(root)
    return {'status':'PASS', 'schema_version':SCHEMA, 'record_count':len(records)}
