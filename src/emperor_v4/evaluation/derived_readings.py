"""Rebuild explicitly selected reading views without rewriting adjudications."""
from __future__ import annotations

from pathlib import Path
import yaml

from .formal_json_store import json_read_session, load_json

PROFILE_AXES = ('M1', 'C3', 'C5')


def view_sources(root: Path) -> dict[str, tuple[str, str]]:
    """Only fully reproducible, non-evidence Markdown views belong here."""
    from .fourth_item_a import AXIS_PATHS, JSON_PATH
    from .second_item_d1_d3_public import D1_PATH, D3_PATH
    from .third_fourth_item_public import THIRD_C_PATH

    project = yaml.safe_load((root / 'config/project.yml').read_text(encoding='utf-8'))
    impact = project['historical_impact_assessment']
    views = {impact['markdown']: ('impact', impact['json'])}
    for axis in PROFILE_AXES:
        entry = project['profile_assessment']['settled_axes'][axis]
        views[entry['markdown']] = ('profile', entry['json'])
    views[AXIS_PATHS['B'].as_posix()] = ('fourth.B', JSON_PATH.as_posix())
    views[THIRD_C_PATH.with_suffix('.md').as_posix()] = ('third.C', THIRD_C_PATH.as_posix())
    for axis, path in (('D1', D1_PATH), ('D3', D3_PATH)):
        views[path.with_suffix('.md').as_posix()] = (axis, path.as_posix())
    for name in views:
        path = Path(name)
        if (path.is_absolute() or '..' in path.parts or path.suffix != '.md'
                or not name.startswith('docs/评分结算/') or '第一项' in name
                or not (root / path).resolve().is_relative_to(root.resolve())):
            raise ValueError(f'派生阅读路径越界或指向第一项真源：{name}')
    return views


@json_read_session()
def render_views(root: Path, paths=None) -> dict[str, str]:
    specs = view_sources(root)
    selected = set(specs) if paths is None else set(paths)
    if not selected <= specs.keys():
        raise ValueError(f'未登记的派生阅读视图：{sorted(selected - specs.keys())}')
    rendered = {}
    for path, (kind, source) in specs.items():
        if path not in selected:
            continue
        payload = load_json(root / source)
        if kind == 'impact':
            from .historical_impact import render
            text = render(payload)
        elif kind == 'profile':
            from .profile_markdown import render_profile_markdown
            text = render_profile_markdown(payload, workspace_root=root)
        elif kind == 'third.C':
            from .five_dynasties_third_item import _render_formal_markdown
            from .third_item_c_contract_reading import load_context
            text = _render_formal_markdown('C', payload['records'], c_review_context=load_context(root))
        elif kind == 'fourth.B':
            from .fourth_item_a import _render_axis
            text = _render_axis(payload, 'B')[Path(path)]
        else:
            from .second_item_d1_d3_public import render_public_markdown
            text = render_public_markdown(payload, kind)
        rendered[path] = text
    return rendered


def run(root: Path, *, check: bool = False) -> dict:
    # Render every selected view before writing any output; never run settlements.
    views = render_views(root)
    changed = [name for name, text in views.items()
               if not (root / name).is_file() or (root / name).read_bytes() != text.encode('utf-8')]
    if check and changed:
        raise ValueError('派生阅读缺失或过期，请运行 python v4.py reading-views：' + '；'.join(changed))
    if not check:
        for name in changed:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(views[name], encoding='utf-8', newline='\n')
    return {'status': 'PASS' if check else 'WRITTEN', 'view_count': len(views), 'updated': changed}
