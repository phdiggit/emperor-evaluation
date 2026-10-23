"""Deterministic compact standard JSON for repository files, not JSONL."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any


def json_text(value: Any) -> str:
    """Preserve data/order and literal text; keep collection entries on lines."""
    def compact(item: Any) -> str:
        return json.dumps(item, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

    def container(item: Any, *, collections: bool = False) -> str:
        if isinstance(item, list):
            if not item:
                return '[]'
            return '[\n' + ',\n'.join(compact(row) for row in item) + '\n]'
        if isinstance(item, dict):
            if not item:
                return '{}'
            fields = []
            for key, child in item.items():
                if isinstance(child, list) and child and all(isinstance(row, dict) for row in child):
                    encoded = container(child)
                elif key == 'collections' and isinstance(child, dict):
                    encoded = container(child, collections=True)
                elif collections and isinstance(child, dict):
                    encoded = container(child)
                else:
                    encoded = compact(child)
                # Match json.dumps' conversion of numeric/bool/null mapping keys.
                json_key = key if isinstance(key, str) else next(iter(json.loads(compact({key: None}))))
                fields.append(compact(json_key) + ':' + encoded)
            return '{\n' + ',\n'.join(fields) + '\n}'
        return compact(item)

    return container(value) + '\n'


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'JSON包含重复字段，不能无损格式化：{key}')
        result[key] = value
    return result


def format_repository(root: Path, *, check: bool = False) -> dict:
    """Format Git-managed JSON and existing reader outputs; ignore local scratch."""
    root = root.resolve()
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '*.json'], cwd=root,
    ).decode('utf-8').split('\0')
    paths = {root / name for name in names if name}
    paths.update((root / 'reader/data').rglob('*.json'))
    identity = root / 'reader/source-revision.json'
    if identity.is_file():
        paths.add(identity)
    pending = []
    before = after = count = 0
    for path in sorted(paths):
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'JSON路径越界或为符号链接：{path}')
        raw = path.read_bytes()
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique_pairs)
        content = json_text(value).encode('utf-8')
        before += len(raw); after += len(content); count += 1
        if raw != content:
            pending.append((path, content))
    if not check:
        for path, content in pending:
            temporary = path.with_name('.' + path.name + '.format-tmp')
            temporary.write_bytes(content)
            temporary.replace(path)
    return {'status': 'PASS' if not pending or not check else 'OUTDATED', 'file_count': count,
            'changed_count': len(pending), 'bytes_before': before, 'bytes_after': after}
