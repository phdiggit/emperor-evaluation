"""Shared identity, period and entry projection; never changes adjudications."""
import json
import re
from html import escape, unescape
from urllib.parse import quote


def period_label(value):
    if value is None:
        return ''
    if isinstance(value, str):
        value = value.strip()
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return value
        if not isinstance(parsed, list):
            return value
        value = parsed
    if isinstance(value, list):
        if len(value) == 2 and all(type(v) is int for v in value):
            year = lambda n: f'前{abs(n)}' if n < 0 else str(n)
            return f'{year(value[0])}—{year(value[1])}年'
        if all(isinstance(v, list) and len(v) == 2 and all(type(n) is int for n in v) for v in value):
            return '；'.join(period_label(v) for v in value)
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def prepare_collections(collections, pool, impact):
    """Return normalized pages and links only to records actually present."""
    labels = {r['ruler_id']: r.get('identity_label', r['ruler_name'])
              for r in [*impact['records'], *impact.get('supplementary_records', [])]}
    aliases = {}
    for person in pool['records']:
        for key in {person['ruler_id'], person['ruler_name'], *person.get('source_item_ids', {}).values()} - {None}:
            if key in aliases and aliases[key]['ruler_id'] != person['ruler_id']:
                raise ValueError(f'Ambiguous collection identity: {key}')
            aliases[key] = person
    entries = {}
    output = {}
    for filename, (title, text) in collections.items():
        def identity(key):
            person = aliases.get(unescape(key))
            if not person:
                return None
            rid = person['ruler_id']
            if person['pool_status'] == 'INCLUDED':
                entry = dict(label=title, href=filename+'#'+quote(unescape(key), safe=''))
                if entry not in entries.setdefault(rid, []):
                    entries[rid].append(entry)
            return person
        # The first three civilization pages construct their cards from JSON.
        def payload(match):
            rows = json.loads(match[2])
            for row in rows:
                p = identity(row['ruler_id'])
                if p:
                    row['display_name'] = labels.get(p['ruler_id'], p['ruler_name'])
            return match[1]+json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c')+match[3]
        text = re.sub(r'(<script id="fourth-[abc]-data" type="application/json">)(.*?)(</script>)', payload, text, flags=re.S)
        def card(match):
            p = identity(match[2])
            if not p:
                return match[0]
            scope = '正式评价对象' if p['pool_status'] == 'INCLUDED' else '池外单项记录，不纳入综合榜'
            if match[0].startswith('<details'):
                return match[0][:-1]+f' data-collection-scope="{escape(scope)}">'
            return match[0]+f'<p class="collection-scope">{escape(scope)}</p>'
        text = re.sub(r'(<(?:article|details)\b[^>]*\bid=[\'"])([^\'"]+)([\'"][^>]*>)', card, text)
        text = re.sub(r'(<details\b[^>]*data-collection-scope="([^"]*)"[^>]*>.*?</summary>)',
                      lambda m: m[1]+f'<p class="collection-scope">{m[2]}</p>', text, flags=re.S)
        def heading(match):
            p = aliases.get(unescape(match[2]))
            return match[1]+escape(labels.get(p['ruler_id'],p['ruler_name']))+match[3] if p else match[0]
        text = re.sub(r'(<h2\b[^>]*>)([^<]+)(</h2>)', heading, text)
        # First-item cards identify the person in their self-link, above the question.
        text = re.sub(r'(<a href=[\'"]#[^\'"]+[\'"]>)([^<]+)(</a>)', heading, text)
        scope_note = '<p class="collection-scope">本页按本分项正式记录覆盖；是否已有总分、是否属于综合评价池分别标注，不以本页人数代表总榜人数。</p>'
        text = re.sub(r'(</h1>)', r'\1'+scope_note, text, count=1)
        output[filename] = text
    return output, entries
