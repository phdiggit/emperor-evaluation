"""Fourth-item command facade; evidence components are not scoring inputs."""
from .fourth_item_results import (
    BASE, JSON_PATH, TOTAL_PATH, AXIS_NAMES, AXIS_PATHS, POINTS, BANDS,
    verify, render, write_views,
)
A_PATH = AXIS_PATHS['A']


def _render_axis(payload, axis):
    views = render(payload)
    return {AXIS_PATHS[axis]: views[AXIS_PATHS[axis]], TOTAL_PATH: views[TOTAL_PATH]}

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
