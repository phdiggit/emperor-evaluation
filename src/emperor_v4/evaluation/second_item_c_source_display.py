"""Bibliographic display for second-item materials, separate from lineage."""

import re
from urllib.parse import unquote, urlsplit


_URL = re.compile(r'https?://[^\s；，。）》<>]+')
_INTERNAL_TITLE = re.compile(r'共享通读卡正文|财政民生卡|固定文本及通读总结|固定通读页|(?:非战役)?通读总结')
_VOLUME_TITLE = re.compile(r'^([^/《》]+)/卷0*(\d+)([上下]?)$')
_TRANSCRIPTION_OFFSET = re.compile(r'，?原文字符\s*\d+[—–-]\d+|^第\d+行(?:起|[—–-]\d+行)?$')
_WORK_VOLUME = re.compile(r'^docs/史料通读产物/.+/([^/]+)/volume-(\d+)[^/]*$')
_FIELD = re.compile(r'^[a-z][a-z_0-9]*(?:\s*/\s*(?:[a-z][a-z_0-9]*|\d+))*$')
_REGISTER = re.compile(r'^(?:SRC-[A-Z0-9-]+|volume-\d+:P\d+|[LP]\d+)$', re.I)
_MACHINE_PATH = re.compile(r'\.(?:jsonl?|ndjson)(?:$|[:/])', re.I)
_INTERNAL_LOCATOR = re.compile(r'(?:通读定位\s*)?\bSRC-[A-Z0-9-]+\b|卷\d+通读总结第\d+节|'
                               r'(?<![A-Z0-9_])[LP]\d{3,}(?:[—–-][LP]\d{3,})?(?:[、，,]\s*)?', re.I)
_SUMMARY_REGISTER = r'(?:SRC-[A-Z0-9-]+|[PL]\d{4})(?:[-—–][PL]\d{4})?'
_REGISTER_LIST = rf'[、，,\s]*`?{_SUMMARY_REGISTER}`?(?:[、，,\s]*`?{_SUMMARY_REGISTER}`?)*'


def display_project_summary(text):
    """Remove transcription identifiers from editorial summaries only."""
    text = re.sub(rf'(?:原文|通读)?定位[：:]\s*[-—–]?{_REGISTER_LIST}(?:[。.]|$)', '', text)
    text = re.sub(rf'[（(]{_REGISTER_LIST}[）)]', '', text)
    return re.sub(_REGISTER_LIST, '', text).replace('NO_MACRO_ANCHOR', '不足以确认整体状态').strip()


def _external_source(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    return (
        parsed.scheme in {'http', 'https'} and host
        and not any(host == domain or host.endswith('.' + domain)
                    for domain in ('github.com', 'githubusercontent.com', 'github.io'))
        and not is_machine_source(url)
    )


def is_machine_source(ref):
    return bool(_MACHINE_PATH.search(unquote(urlsplit(ref).path)))


def project_source_title(ref):
    """Retain the work and volume for project transcriptions, without file labels."""
    path = ref.partition('#')[0]
    if volume := _WORK_VOLUME.fullmatch(path):
        return f'《{volume[1]}》卷{int(volume[2])}'
    name = path.rsplit('/', 1)[-1]
    title = re.sub(r'^\d+-|\.(?:jsonl?|md)$|(?:非战役)?通读总结', '', name)
    return title if re.search(r'[\u3400-\u9fff]', title) else ''


def validate_source_excerpts(excerpts, axis):
    if not isinstance(excerpts, list):
        raise ValueError(f"{axis}原典须按段登记")
    for excerpt in excerpts:
        if (not isinstance(excerpt, dict) or set(excerpt) != {"label", "url", "context", "quote"}
                or not all(isinstance(value, str) and value.strip() for value in excerpt.values())):
            raise ValueError(f"{axis}原典须含卷篇、链接、上下文和原文")
        if not _external_source(excerpt["url"]):
            raise ValueError(f"{axis}原典链接无效")
    return excerpts


def bibliographic_source(ref):
    """Project citation metadata without turning repository references into links."""
    titles = []
    title = ref.get('public_source_title', ref['source_title'])
    for part in title.split('；'):
        part = part.strip()
        match = _WORK_VOLUME.fullmatch(part)
        if match:
            work, volume = match.groups()
            part = f'《{work}》卷{int(volume)}'
        elif (part.startswith(('docs/', 'config/', 'archive/', 'volume-', 'http://', 'https://'))
              or _FIELD.fullmatch(part) or _REGISTER.fullmatch(part) or is_machine_source(part)):
            continue
        part = _INTERNAL_TITLE.sub('', part).strip(' ·')
        match = _VOLUME_TITLE.fullmatch(part)
        if match:
            work, volume, subdivision = match.groups()
            part = f'《{work}》卷{int(volume)}{subdivision}'
        if part and part not in titles and part not in {'本轴既有取证记录', '正式材料登记', '既有史料登记', '所引史料'}:
            titles.append(part)

    locator = ref.get('public_source_locator', ref['source_locator'])
    urls = [ref.get('public_source_url', ref.get('source_url', '')),
            *ref.get('public_parallel_source_urls', []), *_URL.findall(locator)]
    locator = _URL.sub('', locator)
    details = []
    for part in locator.split('；'):
        if part.strip() == title.strip():
            continue
        part = re.sub(r'^(?:固定修订|修订号)\s*\d+[，、]\s*', '', part.strip())
        part = _TRANSCRIPTION_OFFSET.sub('', _INTERNAL_LOCATOR.sub('', _INTERNAL_TITLE.sub('', part))).strip(' ·：，、')
        if (part and part not in {'原文', '史源'} and not part.startswith('volume-') and not _FIELD.fullmatch(part)
                and not _REGISTER.fullmatch(part) and '固定审计所定位' not in part
                and not part.startswith(('docs/', 'config/', 'archive/')) and not is_machine_source(part)):
            details.append(part)

    return {
        'source_title': '；'.join(titles),
        'source_locator': '；'.join(details),
        'source_urls': list(dict.fromkeys(url for url in urls if url and _external_source(url))),
    }


def reading_source(ref):
    """Project C material, with explicit public excerpts where available."""
    kind = ref['source_kind']
    if kind.startswith('裁决依据'):
        kind = '项目裁决依据'
    elif kind == '原记录史料摘要' or ref['source_title'] == '本轴既有取证记录':
        kind = '项目史料摘要'
    elif kind == '原记录所引材料':
        kind = '所引材料'
    elif _FIELD.fullmatch(kind) or _REGISTER.fullmatch(kind):
        kind = '所引材料'
    passages = [dict(passage, url=passage['url'] if _external_source(passage['url']) else '')
                for passage in ref.get('public_source_passages', [])]
    excerpt = ref.get('public_excerpt', ref['exact_quote'])
    if 'public_excerpt' not in ref and kind not in {'史料原文'}:
        excerpt = display_project_summary(excerpt)
    return {
        **bibliographic_source(ref),
        'source_kind': kind,
        'source_context': ref.get('public_source_context', ''),
        **({'passages': passages} if passages else {}),
        'exact_quote': excerpt,
    }


def material_excerpts(refs):
    """Keep the authored passages from every binding in a display group."""
    excerpts = []
    for raw in refs:
        ref = reading_source(raw)
        if ref.get('passages'):
            excerpts.extend(ref['passages'])
        elif raw.get('public_excerpt'):
            excerpts.append(dict(title=ref['source_title'], url='', text=ref['exact_quote']))
    unique = []
    for passage in excerpts:
        if passage not in unique:
            unique.append(passage)
    primary = reading_source(refs[0])
    if not primary.get('passages') and all(p['text'] != primary['exact_quote'] for p in unique):
        unique.insert(0, dict(title='', url='', text=primary['exact_quote']))
    return unique
