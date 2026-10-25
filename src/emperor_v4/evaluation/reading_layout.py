"""Deterministic, lossless pagination of explicitly marked generated readings."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import posixpath
import re
from urllib.parse import quote, unquote, urlsplit

PERSON_END = '<!-- /reading-person -->'
PERSON_RE = re.compile(r'^<!-- reading-person:([\w-]+) -->\n(.*?)^<!-- /reading-person -->', re.M | re.S)
ANCHOR_RE = re.compile(r'<a\s+(?:id|name)=["\']([^"\']+)["\'][^>]*>')
PAGE_BYTES = 200_000
PAGE_LINES = 2500


def fragment_directory(path: str | Path) -> str:
    return str(Path(path).with_suffix('')).replace('\\', '/') + '-逐人阅读'


def is_reading_fragment(path: str, sources) -> bool:
    return any(path.startswith(fragment_directory(source) + '/') for source in sources)


def person_start(ruler_id: str) -> str:
    if not re.fullmatch(r'[\w-]+', ruler_id) or ruler_id.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError(f'阅读分片人物ID无效：{ruler_id}')
    return f'<!-- reading-person:{ruler_id} -->'


def _units(text: str) -> list[str]:
    """Keep fenced code, list items and complete HTML details together."""
    units, current = [], []
    depth, fence = 0, None
    for line in text.splitlines(keepends=True):
        if current and not depth and not fence and (not line.strip() or re.match(r'^(?:#{1,6} |[-*] |\d+\. )', line)):
            units.append(''.join(current)); current = []
        current.append(line)
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
        if not fence:
            depth += len(re.findall(r'<details(?:\s|>)', line)) - line.count('</details>')
            if depth < 0:
                raise ValueError('阅读正文含未配对的details标签')
    if fence or depth:
        raise ValueError('阅读正文含未闭合的代码块或details标签')
    if current:
        units.append(''.join(current))
    return units


def _pages(text: str) -> list[str]:
    pages, current = [], ''
    for unit in _units(text):
        combined = current + unit
        if current and (len(combined.encode('utf-8')) > PAGE_BYTES or combined.count('\n') > PAGE_LINES):
            pages.append(current); current = ''
        current += unit
    if current:
        pages.append(current)
    return pages


def relocate_links(text: str, source: str, destination: str, anchors=None, documents=None) -> str:
    """Move Markdown/HTML destinations, preserving queries and explicit anchors."""
    anchors, documents = anchors or {}, documents or {}

    def move(target):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith('/') or not target:
            return target
        old = posixpath.normpath(posixpath.join(posixpath.dirname(source), unquote(parsed.path))) if parsed.path else source
        new = anchors.get((old, unquote(parsed.fragment)), documents.get(old, old))
        if new == destination and not parsed.path:
            path = ''
        else:
            path = quote(posixpath.relpath(new, posixpath.dirname(destination)), safe='/~!$&\'*,;=:@-._')
        return path + ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')

    def inline(line):
        # Balanced parentheses allow original-book URLs containing parentheses.
        result, cursor = [], 0
        while (start := line.find('](', cursor)) >= 0:
            end, depth = start + 2, 1
            while end < len(line) and depth:
                if line[end] == '\\':
                    end += 2; continue
                depth += (line[end] == '(') - (line[end] == ')')
                end += 1
            if depth:
                break
            value = line[start + 2:end - 1]
            if value.startswith('<') and '>' in value:
                stop = value.index('>')
                rewritten = '<' + move(value[1:stop]) + value[stop:]
            else:
                match = re.match(r'(\S+)(.*)', value)
                rewritten = move(match[1]) + match[2] if match else value
            result += [line[cursor:start + 2], rewritten, ')']; cursor = end
        result.append(line[cursor:])
        line = ''.join(result)
        line = re.sub(r'((?:href|src)=["\'])([^"\']+)(["\'])', lambda m: m[1] + move(m[2]) + m[3], line)
        return re.sub(r'^(\s*\[[^\]]+\]:\s*)(\S+)', lambda m: m[1] + move(m[2]), line)

    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            lines.append(line)
        elif fence:
            lines.append(line)
        else:
            # Literal code and source identifiers are not navigation links.
            lines.append(''.join(part if i % 2 else inline(part)
                                 for i, part in enumerate(re.split(r'(`+[^`]*`+)', line))))
    return ''.join(lines)


def reading_files(path: str | Path, text: str) -> dict[str, str]:
    """Unmarked views stay unchanged; marked views become index + person files."""
    path = Path(path).as_posix()
    matches = list(PERSON_RE.finditer(text))
    if text.count('<!-- reading-person:') != len(matches) or text.count(PERSON_END) != len(matches):
        raise ValueError(f'阅读人物分片标记未闭合：{path}')
    if not matches:
        return {path: text}
    directory = fragment_directory(path)
    title = text.splitlines()[0].removeprefix('# ')
    people, index, cursor, root_anchors, section = OrderedDict(), [], 0, set(), []
    for match in matches:
        prefix = text[cursor:match.start()]
        index.append(prefix)
        rid, body = match[1], match[2]
        heading = re.search(r'^### (.+)$', body, re.M)
        if not heading:
            raise ValueError(f'人物分片缺少显式标题：{rid}')
        section = re.findall(r'^## (.+)$', prefix, re.M)[-1:] or section
        person = people.setdefault(rid, {'label': heading[1], 'body': ''})
        person['body'] += ('## ' + section[0] + '\n\n' if section else '') + body
        aliases = [f'person-{rid.lower()}', f'ruler_id={rid}', *ANCHOR_RE.findall(body)]
        for anchor in aliases:
            if anchor not in root_anchors:
                index.append(f'<a id="{anchor}"></a>\n\n'); root_anchors.add(anchor)
        href = quote(f'{Path(directory).name}/{rid}.md', safe='/')
        index.append(f'- [{heading[1]}]({href})\n')
        cursor = match.end()
    index.append(text[cursor:])
    result = {path: ''.join(index)}
    anchors = {}
    for rid, person in people.items():
        target = f'{directory}/{rid}.md'
        if target in result:
            raise ValueError(f'人物ID与阅读分页文件名冲突：{rid}')
        pages = _pages(person['body'])
        header = f'# {title} · {person["label"]}\n\n'
        if len(pages) == 1:
            result[target] = header + person['body']
        else:
            result[target] = header + '正文按连续章节分页，以下各页共同保留完整内容。\n\n'
            for i, page in enumerate(pages, 1):
                part = f'{directory}/{rid}-{i:02d}.md'
                if part in result or f'{rid}-{i:02d}' in people:
                    raise ValueError(f'人物ID与阅读分页文件名冲突：{part}')
                # Index links are authored relative to the original document until relocation.
                result[target] += f'- [正文第{i}页]({quote(Path(directory).name + "/" + Path(part).name, safe="/")})\n'
                directory_name = Path(directory).name
                navigation = [f'[人物目录]({quote(directory_name + "/" + rid + ".md", safe="/")})']
                for number, label in ((i - 1, '上一页'), (i + 1, '下一页')):
                    if 1 <= number <= len(pages):
                        navigation.append(f'[{label}]({quote(f"{directory_name}/{rid}-{number:02d}.md", safe="/")})')
                nav = ' · '.join(navigation)
                result[part] = header + f'正文第{i}/{len(pages)}页。\n\n' + nav + '\n\n' + page + '\n\n' + nav + '\n'
        for name in [n for n in result if n == target or n.startswith(f'{directory}/{rid}-')]:
            for anchor in ANCHOR_RE.findall(result[name]):
                anchors[(path, anchor)] = name
    # Relocate original relative sources and cross-person anchors after all targets are known.
    for name, content in list(result.items()):
        if name != path:
            navigation = f'\n\n[返回总览]({quote(Path(path).name, safe="")})\n'
            content += navigation
        result[name] = f'<!-- generated-reading: {path} -->\n' + relocate_links(content, path, name, anchors)
    return result


def synchronize(root: Path, files: dict[str, str], sources, *, check=False) -> list[str]:
    """Only remove obsolete fragments bearing this generator's exact ownership mark."""
    changed = [name for name, content in files.items()
               if not (root / name).is_file() or (root / name).read_bytes() != content.encode('utf-8')]
    stale = []
    for source in sources:
        directory = root / fragment_directory(source)
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'阅读分片目录越界：{directory}')
        marker = f'<!-- generated-reading: {Path(source).as_posix()} -->\n'.encode('utf-8')
        for target in directory.glob('*.md'):
            if target.is_symlink():
                raise ValueError(f'阅读分片不得为符号链接：{target}')
            name = target.relative_to(root).as_posix()
            with target.open('rb') as stream:
                owned = stream.readline().rstrip(b'\r\n') == marker.rstrip(b'\r\n')
            if name not in files and owned:
                stale.append(name)
    if check and (changed or stale):
        raise ValueError('Markdown派生阅读缺失或过期，请运行 python v4.py reading-views：' + '；'.join(changed + stale))
    if not check:
        for name in changed:
            target = root / name
            if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'阅读输出路径越界：{target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(files[name].encode('utf-8'))
        for name in stale:
            (root / name).unlink()
    return changed + stale


def check_reading(root: Path, path: str | Path, text: str) -> None:
    synchronize(root, reading_files(path, text), [path], check=True)


def write_reading(root: Path, path: str | Path, text: str) -> None:
    synchronize(root, reading_files(path, text), [path])
