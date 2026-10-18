"""Project explicit C3 person bindings from the current military talent registry."""
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import quote
import json

from .talent_registry_store import load_talent_registry, talent_profiles_by_ref

NOTE = ('四档看不同将领在本任任务中的实际执行与协同，不要求人人达到顶级。'
        '五档另须至少两名历史级或顶级统帅，各有本任A级及以上显著正向成果；'
        '生涯档位不代替本任成果，对手、其他任期或统治者本人不能充作本任部将资格。')
LABELS = {'historic': '历史级', 'top': '顶级', 'elite': '精英级', 'important': '重要级',
          'capable': '有力级', 'usable': '可用级', 'ordinary': '普通级'}
SIGNIFICANT = {'A', 'S-', 'S', 'S+'}


@lru_cache(maxsize=2)
def _profiles_for_version(version):
    return talent_profiles_by_ref(load_talent_registry(Path(version[0])))


def current_profiles():
    path = Path(__file__).resolve().parents[3] / 'docs/公共成果/军事/02-武将人才等级.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    version = (str(path), path.stat().st_mtime_ns, tuple(
        (entry['path'], (path.parent / entry['path']).stat().st_mtime_ns)
        for entry in manifest['shards']))
    return _profiles_for_version(version)


def commander_projection(row, profiles=None):
    bindings = row.get('public_reading', {}).get('axes', {}).get('C3', {}).get('commander_links', [])
    if not bindings:
        return {'note': NOTE, 'entries': []}
    profiles = current_profiles() if profiles is None else profiles
    gate = row.get('c5_axis_gate') or {}
    deliveries = {x['profile_ref']: x for x in gate.get('C3_top_commander_deliveries', [])}
    entries = []
    seen = set()
    for binding in bindings:
        mention = binding['name_in_text']
        refs = binding.get('profile_refs', [])
        if not refs:
            entries.append(dict(name=mention, profile_ref=None, grade=None, grade_label='档案待核',
                archive_href='military.html#search=' + quote(mention, safe=''),
                qualification_status='UNLINKED', qualification_text='尚未确认对应的人才档案，不据此认定其人才层级较低。',
                own_window_results=[], grade_note=''))
            continue
        for ref in refs:
            if ref not in profiles:
                raise ValueError('C3将领链接未指向现行人才档案：' + ref)
            profile = profiles[ref]
            if (binding.get('identity_status') != 'PENDING'
                    and mention not in [profile['person'], *profile.get('name_aliases', [])]):
                raise ValueError('C3正文姓名与所链接人才档案身份不符')
            canonical = profile['profile_ref']
            if canonical in seen:
                raise ValueError('C3同一将领档案重复列入')
            seen.add(canonical)
            grade = profile['military_grade']
            if grade not in LABELS:
                raise ValueError('C3将领档位缺少公开名称')
            adopted = deliveries.get(ref) or deliveries.get(canonical) or {}
            results_by_ref = {a['campaign_ref']: a for a in profile.get('consumed_achievements', [])}
            owned = (adopted.get('subject_ruler_id') == row.get('ruler_id')
                     and bool(adopted.get('own_window_basis')))
            results = [dict(campaign_ref=a['campaign_ref'], label=a['canonical_label'],
                            tier=a['campaign_tier'], difficulty=a.get('combat_difficulty'))
                       for result_ref in adopted.get('achievement_refs', [])
                       if owned and (a := results_by_ref.get(result_ref))
                       and a.get('campaign_tier') in SIGNIFICANT and a.get('result_direction') == 'positive']
            if binding.get('identity_status') == 'PENDING':
                status, text = 'IDENTITY_PENDING', '同名或异名身份尚待核准，不据此计入五档资格。'
            elif binding.get('ruler_self') or profile['person'] == row.get('ruler_name'):
                status, text = 'RULER_SELF', '统治者本人，不计作自己的部将资格。'
            elif binding.get('opponent_or_context'):
                status, text = 'OPPONENT_OR_CONTEXT', '本段作为对手或任务背景提及，不计作本任部将资格。'
            elif grade not in {'top', 'historic'}:
                status, text = 'BELOW_FIVE_TALENT_GATE', '未达五档人才档位门；本任实际执行仍按具体战事评价。'
            elif results:
                status, text = 'OWN_WINDOW_SIGNIFICANT_RESULTS', '人才档位达标，本任显著正向成果已核准。'
            else:
                status, text = 'OWN_WINDOW_NOT_BOUND', '人才档位达标；此处尚未列明合格的本任成果，不能只凭生涯档位计入五档资格。'
            entries.append(dict(name=profile['person'], name_in_text=mention, profile_ref=canonical,
                dynasty=profile.get('dynasty', ''), grade=grade, grade_label=LABELS[grade],
                archive_href='military.html#commander=' + quote(canonical, safe=''),
                qualification_status=status, qualification_text=text, own_window_results=results,
                grade_note='现有证据下限' if profile.get('grade_status') == 'evidence_lower_bound' else ''))
    return {'note': NOTE, 'entries': entries}


def commander_html(data):
    lines = ['<section class="third-c-commanders"><h5>将领档位与本任成果</h5>',
             '<p class="meta">' + escape(data['note']) + '</p>']
    if not data['entries']:
        lines.append('<p class="meta">本段未列具体将领；执行过程见下方战事材料。'
                     '<a href="military.html">浏览军事人才档案 ↗</a></p>')
    else:
        lines.append('<ul>')
        for entry in data['entries']:
            title = entry['name'] + ' · ' + entry['grade_label']
            if entry['grade_note']:
                title += '（' + entry['grade_note'] + '）'
            if entry['qualification_status'] == 'IDENTITY_PENDING':
                title += ' · ' + entry.get('dynasty', '')
            lines.append('<li><a href="' + escape(entry['archive_href'], quote=True)
                         + '">' + escape(title) + ' ↗</a><p class="meta">'
                         + escape(entry['qualification_text']) + '</p>')
            if entry['own_window_results']:
                lines.append('<details><summary>本任已核准的显著成果</summary><ul>')
                for result in entry['own_window_results']:
                    lines.append('<li>' + escape(result['label'] + ' · ' + result['tier']) + '</li>')
                lines.append('</ul></details>')
            lines.append('</li>')
        lines.append('</ul>')
    return ''.join(lines + ['</section>'])
