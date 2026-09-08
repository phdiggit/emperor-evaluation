"""Offline governance calculator, explicit-ruling verifier and component writer.

Historical judgments are supplied by the declared source, never inferred here.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


VERSION = "GOVERNANCE-STATE-RECOVERY-V4"
REVIEW_PATH = Path("config/second-item/governance-state-recovery-adjudications.json")
REVIEW_MARKDOWN_PATH = Path(
    "docs/评分结算/第二项治国净收益/财政民生/08-主态低谷与净恢复逐人裁决.md"
)
CURRENT_REVIEW_PATH = Path("config/second-item/c4-attribution-readjudications.json")
AXES = ("C1", "C2", "C3")
FORMAL_PATHS = {
    "C1": Path("docs/评分结算/第二项治国净收益/财政民生/01-C1正式结算.json"),
    "C2": Path("docs/评分结算/第二项治国净收益/财政民生/02-C2正式结算.json"),
    "C3": Path("docs/评分结算/第二项治国净收益/财政民生/03-C3正式结算.json"),
    "C4": Path("docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json"),
}

FIXED_POINTS = {
    "C1": (5.7, 17.1, 32.0, 54.9, 74.3, 80.0),
    "C2": (1.8, 7.0, 14.9, 23.6, 29.8, 35.0),
    "C3": (5.0, 16.0, 28.0, 40.0, 52.0, 60.0),
}
LOSS_RATES = {"L0": Decimal("0"), "L1": Decimal(".03"), "L2": Decimal(".07"), "L3": Decimal(".12")}
BOUNDARY = (0.6, 0.8, 1.0, 1.3, 1.6)
WEIGHTS = {"C1": 0.5, "C2": 0.2, "C3": 0.3}
RETIRED_STATE_REVIEW_FIELDS = (
    "review_remediation",
    "c1_reaudit",
    "c2_reaudit",
    "c3_reaudit",
    "old_settlement",
    "old_settlement_review",
    "military_cost_c1_review",
    "stability_stage_review",
    "persistence_review",
    "dynasty_curve_review",
    "inference_review",
)
_PROTECTED_TEXT_KEYS = {
    "book",
    "title",
    "source_title",
    "source_id",
    "source_file",
    "source_ref",
    "source_refs",
    "public_source_refs",
    "original_text",
    "verbatim_excerpt",
    "exact_quote",
    "quote",
}


def clean_retired_low_valley_references(value: Any, field_name: str = "") -> Any:
    """Remove retired K-mechanism wording without deriving a new L grade.

    Verbatim quotations and the one M3 historical-diagnostic field are kept
    byte-for-byte so evidence lineage is not rewritten as a score input.
    """
    if field_name in {"stability_class_diagnostic_only", "stability_k_basis"}:
        return value
    if isinstance(value, dict):
        return {
            key: clean_retired_low_valley_references(child, str(key))
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [clean_retired_low_valley_references(child, field_name) for child in value]
    if not isinstance(value, str):
        return value

    text = value
    if field_name == "verbatim_excerpt":
        text = text.replace("长期K承压", "长期压力承受")
        text = text.replace("K4只表示未再跨档，不构成奖励。", "历史低谷诊断仅表示未再跨档，不构成奖励。")
    if field_name in _PROTECTED_TEXT_KEYS:
        return text
    text = re.sub(r"C([123])[-/]K[0-5]", r"C\1低谷修正", text)
    text = re.sub(r"C([123])[-/]K\b", r"C\1低谷修正", text)
    text = re.sub(r"旧K[0-5]", "旧低谷标签", text)
    text = text.replace("历史低谷标签聚合门", "重复计入条件")
    text = text.replace("已废止的聚合门", "重复计入条件")
    text = text.replace("不固定使用终点权重", "不按终点状态单独加重低谷修正")
    text = text.replace("终点权重", "终点状态单独加重")
    text = text.replace("C1—C3正式K", "C1—C3历史稳定诊断")
    text = text.replace("正式K", "正式低谷诊断")
    text = text.replace("历史K", "历史稳定诊断")
    text = text.replace("旧K", "旧低谷诊断")
    text = text.replace("K折损", "低谷修正")
    text = text.replace("K消费", "低谷修正消费")
    text = text.replace("K扣", "低谷修正扣")
    text = text.replace("由K", "由低谷修正")
    text = text.replace("不计K", "不计低谷修正")
    text = text.replace("与K", "与低谷修正")
    text = text.replace("进入K", "进入低谷修正")
    text = re.sub(r"(?<![A-Za-z0-9_])K[0-5](?![A-Za-z0-9_])", "历史低谷标签", text)
    return re.sub(r"(?<![A-Za-z0-9_])K(?![A-Za-z0-9_])", "低谷修正", text)


def _band(band: int) -> int:
    if isinstance(band, bool) or not isinstance(band, int) or not 1 <= band <= 6:
        raise ValueError("State band must be an adjudicated integer from 1 to 6")
    return band


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal(".1"), rounding=ROUND_HALF_UP))


def band_number(label: str) -> int:
    """Convert a component label such as ``C1-4`` to its integer band."""

    try:
        axis, number = str(label).rsplit("-", 1)
        if axis not in AXES:
            raise ValueError
        return _band(int(number))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid governance state band: {label!r}") from exc


def band_label(axis: str, band: int) -> str:
    if axis not in AXES:
        raise ValueError(f"Unknown governance state axis: {axis}")
    return f"{axis}-{_band(band)}"


def state_score(axis: str, main: int, loss_grade: str) -> float:
    """Price an adjudicated main state and bounded loss; no terminal weighting."""
    _band(main)
    if axis not in FIXED_POINTS or loss_grade not in LOSS_RATES:
        raise ValueError("Unknown result axis or loss grade")
    points = FIXED_POINTS[axis]
    return _round(max(Decimal(str(points[0])), Decimal(str(points[main - 1]))
                      * (Decimal(1) - LOSS_RATES[loss_grade])))


def retained_recovery(
    baselines: dict[str, int], ends: dict[str, int], attribution: dict[str, float]
) -> dict[str, Any]:
    if any(set(values) != set(WEIGHTS) for values in (baselines, ends, attribution)):
        raise ValueError("Each recovery vector must contain exactly C1, C2, C3")
    raw = Decimal(0)
    axis_details: dict[str, dict[str, Any]] = {}
    for axis, weight in WEIGHTS.items():
        start, end = _band(baselines[axis]), _band(ends[axis])
        factor = attribution[axis]
        if isinstance(factor, bool) or factor not in (0, 0.5, 1):
            raise ValueError("Recovery attribution must be 0, .5 or 1")
        credit = (
            sum((Decimal(str(v)) for v in BOUNDARY[start - 1 : end - 1]), Decimal(0))
            if end > start
            else Decimal(0)
        )
        weighted = Decimal(str(weight)) * Decimal(str(factor)) * credit
        raw += weighted * 10
        axis_details[axis] = {
            "baseline_band": start,
            "end_band": end,
            "attribution_factor": factor,
            "boundary_credit": float(credit),
            "weighted_credit": float(weighted),
            "retained_increment": end > start,
        }
    quality = sum(Decimal(str(WEIGHTS[a])) * ends[a] for a in WEIGHTS)
    rounded_quality = int(quality.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    terminal_band = min(6, rounded_quality, min(ends.values()) + 1)
    cap = (7.9, 15.9, 24.9, 27, 27, 27)[terminal_band - 1]
    recovery = _round(min(Decimal(27), raw))
    return {
        "raw_recovery": float(raw),
        "recovery_score": recovery,
        "terminal_band": terminal_band,
        "terminal_cap": cap,
        "positive_retained": min(recovery, cap),
        "axis_details": axis_details,
    }


def _records(payload: dict[str, Any], key: str = "scores") -> list[dict[str, Any]]:
    rows = payload.get(key) or payload.get("records") or []
    if not isinstance(rows, list):
        raise ValueError(f"Formal payload collection is not a list: {key}")
    return rows


def _by_id(payload: dict[str, Any], key: str = "scores") -> dict[str, dict[str, Any]]:
    rows = _records(payload, key)
    result = {str(row.get("ruler_id")): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate ruler IDs in formal payload: {key}")
    return result


def _current_inputs(
    workspace_root: Path,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    formal = {
        axis: _by_id(load_json(workspace_root / path))
        for axis, path in FORMAL_PATHS.items()
    }
    review = load_json(workspace_root / CURRENT_REVIEW_PATH)
    current_rows = review.get("records") or []
    current = {str(row["ruler_id"]): row for row in current_rows}
    if len(current) != len(current_rows):
        raise ValueError("Current C4 attribution review contains duplicate ruler IDs")
    return formal, current


def _pool_ids(root: Path) -> set[str]:
    pool = load_json(root / 'config/common/canonical-ruler-pool.json')
    return {r['ruler_id'] for r in pool['records'] if r['pool_status'] == 'INCLUDED'}


def _deterioration(row: dict[str, Any]) -> float:
    factors = row['recovery']['deterioration_attribution_by_axis']
    if set(factors) != set(AXES) or any(isinstance(f, bool) or not isinstance(f, (int, float)) or not 0 <= f <= 1 for f in factors.values()):
        raise ValueError('Invalid axis-specific deterioration attribution')
    weighted = sum(Decimal(str(WEIGHTS[a])) * max(0, row['axes'][a]['s0_band'] - row['axes'][a]['end_band']) * Decimal(str(factors[a])) for a in AXES)
    return _round(min(Decimal(1), weighted / 2) * 13)


def _validate_loss_dimensions(loss: dict[str, Any]) -> None:
    strong = loss.get('strong_dimensions', [])
    if not isinstance(strong, list) or any(not isinstance(v, str) for v in strong) or len(strong) != len(set(strong)) or not set(strong) <= {'scope', 'duration', 'severity'}:
        raise ValueError('Invalid loss dimensions')
    if loss.get('grade') == 'L3' and ('severity' not in strong or not {'scope', 'duration'} & set(strong)):
        raise ValueError('L3 lacks severity and scope/duration')


def verify_governance_state_recovery_review(workspace_root: Path) -> dict[str, Any]:
    """Verify explicit rulings and consumers; never infer historical grades."""
    root = workspace_root.resolve()
    review = load_json(root / REVIEW_PATH)
    if review.get('schema_version') != 'governance-state-recovery-adjudications-v4' or review.get('version') != VERSION:
        raise ValueError('Invalid governance review schema/version')
    active = review.get('score_active')
    if not isinstance(active, bool):
        raise ValueError('score_active must be boolean')
    rows = review.get('records', [])
    expected = _pool_ids(root)
    actual = {r['ruler_id'] for r in rows}
    if actual != expected or len(rows) != len(expected) or review.get('record_count') != len(rows):
        raise ValueError('Governance review coverage differs from current canonical pool')
    formal, current = _current_inputs(root)
    if not expected <= set(current):
        raise ValueError('C4 attribution source does not cover the canonical pool')
    counts = {a: Counter() for a in AXES}
    for r in rows:
        rid = r['ruler_id']
        if r.get('review_status') != 'COMPLETE' or set(r.get('axes', {})) != set(AXES):
            raise ValueError(f'Incomplete governance review: {rid}')
        for a, s in r['axes'].items():
            if 'diagnostic_legacy_K' in s:
                raise ValueError(f'Retired historical diagnostic field remains: {rid} {a}')
            if rid not in formal[a] or formal[a][rid]['ruler_name'] != r['ruler_name']:
                raise ValueError(f'Missing or mismatched component identity: {rid} {a}')
            for key in ('s0', 'main', 'end'):
                if s.get(f'{key}_label') != band_label(a, s[f'{key}_band']):
                    raise ValueError(f'Invalid state anchor: {rid} {a} {key}')
            loss = s.get('loss_review', {})
            if any(key in s for key in ('low_band', 'low_label', 'v2_state_score')):
                raise ValueError(f'Retired scoring inputs remain: {rid} {a}')
            grade = loss.get('grade')
            if not loss.get('basis') or not loss.get('main_representativeness') or not loss.get('deduplication') or not loss.get('evidence_refs'):
                raise ValueError(f'Incomplete loss ruling: {rid} {a}')
            if loss.get('full_window_reviewed') is not True:
                raise ValueError(f'Recovery stage not reviewed: {rid} {a}')
            for ref in loss['evidence_refs']:
                target = re.sub(r':\d+(?:-\d+)?$', '', ref.split('#', 1)[0])
                if ref.startswith(('docs/', 'config/')) and not (root / target).is_file():
                    raise ValueError(f'Missing evidence reference: {rid} {a}: {ref}')
            try:
                _validate_loss_dimensions(loss)
            except ValueError as exc:
                raise ValueError(f'{exc}: {rid} {a}') from exc
            value = state_score(a, s['main_band'], grade)
            if s.get('state_score') != value:
                raise ValueError(f'State score mismatch: {rid} {a}')
            counts[a][grade] += 1
            if active:
                f = formal[a][rid]
                expected_anchors = {'S0': s['s0_label'], 'S_main': s['main_label'], 'S_end': s['end_label']}
                if f['score'] != value or f['main_band'] != s['main_label'] or f.get('loss_grade') != grade:
                    raise ValueError(f'Formal state score/grade drift: {rid} {a}')
                anchors = f['state_anchors']
                if any(anchors.get(k) != v for k, v in expected_anchors.items()) or 'S_low' in anchors:
                    raise ValueError(f'Formal anchors drift: {rid} {a}')
                if f.get('state_formula_version') != VERSION or f.get('state_adjudication', {}).get('loss_review') != loss:
                    raise ValueError(f'Formal ruling lineage drift: {rid} {a}')
                entry = current[rid]['entry_matrix'][a]
                if any(key in entry for key in ('K', 'K_role')):
                    raise ValueError(f'Retired C4 diagnostic field remains: {rid} {a}')
                old = entry['state_anchors']
                if old.get('S0') != s['s0_label'] or old.get('S_end') != s['end_label'] or old.get('S_main', old.get('S_avg')) != s['main_label']:
                    raise ValueError(f'C4 shared anchors drift: {rid} {a}')
        rec = r['recovery']
        base = {a: rec['baseline'][a]['band'] for a in AXES}
        ends = {a: rec['terminal'][a]['band'] for a in AXES}
        factors = {a: rec['attribution'][a]['factor'] for a in AXES}
        if ends != {a: r['axes'][a]['end_band'] for a in AXES}:
            raise ValueError(f'Recovery end drift: {rid}')
        for a in AXES:
            b = rec['baseline'][a]
            if not b.get('basis') or b['label'] != band_label(a, b['band']):
                raise ValueError(f'Incomplete recovery baseline: {rid} {a}')
            if b['band'] != r['axes'][a]['s0_band'] and b.get('source') != 'PRE_DAMAGE_COMPARABLE_STATE':
                raise ValueError(f'Unadjudicated pre-damage baseline: {rid} {a}')
            credit = rec['attribution'][a]
            if credit.get('grade') not in {'FULL', 'SHARED', 'NONE'} or credit.get('factor') != {'FULL': 1, 'SHARED': .5, 'NONE': 0}.get(credit.get('grade')):
                raise ValueError(f'Invalid recovery attribution: {rid} {a}')
            if factors[a] and ends[a] <= base[a]:
                raise ValueError(f'Recovery credit without increment: {rid} {a}')
        calculated = retained_recovery(base, ends, factors)
        if rec.get('calculation') != calculated or rec.get('deterioration_penalty') != _deterioration(r):
            raise ValueError(f'C4 calculation mismatch: {rid}')
        if active:
            c4 = formal['C4'][rid]
            value = _round(max(Decimal('-40'), min(Decimal(27), Decimal(str(calculated['positive_retained'])) - Decimal(str(rec['deterioration_penalty'])) - Decimal(str(c4['destructive_amplification_penalty'])))))
            if c4['score'] != value or c4['recovery_formula_version'] != VERSION or c4['recovery_score'] != calculated['recovery_score'] or c4['deterioration_penalty'] != rec['deterioration_penalty']:
                raise ValueError(f'Formal C4 drift: {rid}')
            for a in AXES:
                path = c4.get('deterioration_path_basis', {}).get(a, {})
                if path.get('reference_band') != r['axes'][a]['s0_label'] or path.get('end_band') != r['axes'][a]['end_label'] or path.get('attribution_factor') != rec['deterioration_attribution_by_axis'][a]:
                    raise ValueError(f'C4 deterioration lineage drift: {rid} {a}')
    return {'status': 'PASS', 'version': VERSION, 'score_active': active, 'record_count': len(rows), 'state_l_counts': {a: dict(v) for a,v in counts.items()}}


def _competition_ranks(rows: list[dict[str, Any]]) -> None:
    values = sorted((float(r['score']) for r in rows), reverse=True)
    for r in rows:
        r['rank'] = values.index(float(r['score'])) + 1


def _apply_state(row: dict[str, Any], state: dict[str, Any]) -> None:
    row['score'] = state['state_score']
    row['main_band'] = state['main_label']
    row['state_anchors'] = {'S0': state['s0_label'], 'S_main': state['main_label'], 'S_avg': state['main_label'], 'S_end': state['end_label']}
    for key in ('raw_state_band', 'formal_band'):
        if key in row:
            row[key] = state['main_label']
    row['adjudication_reason'] = state['evidence_basis']
    row['loss_grade'] = state['loss_review']['grade']
    row['stability_basis'] = state['loss_review']['basis']
    row['state_formula_version'] = VERSION
    # Historical K supports the independent M3 lineage; it no longer prices states.
    row['stability_diagnostic_role'] = 'M3_DIAGNOSTIC_ONLY_NOT_SCORE_ACTIVE'
    for key in RETIRED_STATE_REVIEW_FIELDS:
        row.pop(key, None)
    cleaned = clean_retired_low_valley_references(row)
    row.clear()
    row.update(cleaned)
    row.pop('v2_state_adjudication', None)
    row['state_adjudication'] = {'version': VERSION, 'review_ref': f'{REVIEW_PATH.as_posix()}#ruler_id={row["ruler_id"]}', 'loss_review': state['loss_review'], 'score': state['state_score']}


def _apply_c4(row: dict[str, Any], ruling: dict[str, Any]) -> None:
    rec = ruling['recovery']; cal = rec['calculation']
    row['recovery_score'] = row['gross_recovery_score'] = cal['recovery_score']
    row['positive_score_retained'] = cal['positive_retained']
    row['uncapped_positive_score'] = cal['raw_recovery']
    row['deterioration_penalty'] = rec['deterioration_penalty']
    factors = rec['deterioration_attribution_by_axis']
    weighted = sum(WEIGHTS[a] * max(0, ruling['axes'][a]['s0_band'] - ruling['axes'][a]['end_band']) * factors[a] for a in AXES)
    row['weighted_attributable_deterioration'] = round(weighted, 4)
    row['deterioration_path_basis'] = {
        a: {'reference_band': ruling['axes'][a]['s0_label'], 'end_band':ruling['axes'][a]['end_label'], 'raw_drop':max(0,ruling['axes'][a]['s0_band']-ruling['axes'][a]['end_band']), 'attribution_factor':factors[a], 'attributable_drop':max(0,ruling['axes'][a]['s0_band']-ruling['axes'][a]['end_band'])*factors[a], 'axis_weight':WEIGHTS[a]}
        for a in AXES
    }
    row['attribution_factor_role'] = 'LEGACY_SUMMARY_USE_AXIS_SPECIFIC_PATH'
    row['terminal_band'] = f'C4T-{cal["terminal_band"]}'
    row['terminal_cap'] = cal['terminal_cap']
    row['terminal_cap_applied'] = cal['positive_retained'] < cal['recovery_score']
    row['terminal_quality'] = sum(WEIGHTS[a] * rec['terminal'][a]['band'] for a in AXES)
    row['closed_recovery_axes'] = [a for a in AXES if rec['attribution'][a]['factor'] and rec['terminal'][a]['band'] > rec['baseline'][a]['band']]
    row['recovery_formula_version'] = VERSION
    row['difficulty_weighted_recovery_credit'] = row['weighted_net_recovery_delta'] = round(cal['raw_recovery'] / 10, 2)
    row['recovery_path_basis'] = {a: {'start_band':rec['baseline'][a]['label'], 'highest_achieved_band':rec['terminal'][a]['label'], 'linear_delta':max(0, rec['terminal'][a]['band']-rec['baseline'][a]['band']), 'boundary_difficulty_credit':cal['axis_details'][a]['boundary_credit'], 'axis_weight':WEIGHTS[a], 'attribution_factor':cal['axis_details'][a]['attribution_factor'], 'weighted_difficulty_credit':cal['axis_details'][a]['weighted_credit'], 'retained_increment':cal['axis_details'][a]['retained_increment']} for a in AXES}
    row['score'] = row['raw_score'] = _round(max(Decimal('-40'), min(Decimal(27), Decimal(str(cal['positive_retained']))-Decimal(str(rec['deterioration_penalty']))-Decimal(str(row['destructive_amplification_penalty'])))))
    for key in ('v2_recovery_attribution', 'v2_recovery_baseline_review', 'v2_state_recovery_adjudication'):
        row.pop(key, None)
    row['state_recovery_adjudication'] = {'version': VERSION, 'review_ref':f'{REVIEW_PATH.as_posix()}#ruler_id={row["ruler_id"]}', 'baseline': rec['baseline'], 'terminal': rec['terminal'], 'attribution': rec['attribution'], 'calculation':cal}
    row['recovery_and_absorption'] = f'按可比基线至交班保留增量计算净恢复{cal["positive_retained"]:.1f}/27；未保留峰值不计分。'
    row['handoff_state'] = '交班锚点为' + '/'.join(rec['terminal'][a]['label'] for a in AXES) + f'；终局{row["terminal_band"]}，正向上限{cal["terminal_cap"]:.1f}。'
    def current_text(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: current_text(v) for k,v in value.items()}
        if isinstance(value, list):
            return [current_text(v) for v in value]
        if isinstance(value, str):
            value = re.sub(r'可归责恶化另扣[\d.]+分', f'可归责恶化另扣{row["deterioration_penalty"]:.1f}分', value)
            value = re.sub(r'正向保留[\d.]+分', f'正向保留{row["positive_score_retained"]:.1f}分', value)
            return re.sub(r'C4净分-?[\d.]+', f'C4净分{row["score"]:.1f}', value)
        return value
    for key in ('adjudication_reason', 'public_adjudication', 'c4_attribution_readjudication', 'deterioration_curve_summary', 'negative_tail_adjudication_reason', 'attribution_readjudication_reason', 'behavior_and_attribution'):
        if key in row:
            row[key] = clean_retired_low_valley_references(current_text(row[key]), key)


def activate_governance_state_recovery(workspace_root: Path) -> dict[str, Any]:
    """Apply a complete, explicit pool ruling through the declared component writer."""
    root = workspace_root.resolve()
    review = load_json(root / REVIEW_PATH)
    if review.get('score_active') is not False:
        raise ValueError('Review must be inactive before uniform activation')
    verify_governance_state_recovery_review(root)
    by_id = {r['ruler_id']: r for r in review['records']}
    payloads = {a: load_json(root / p) for a,p in FORMAL_PATHS.items()}
    source = load_json(root / CURRENT_REVIEW_PATH)
    for a, payload in payloads.items():
        for row in _records(payload):
            if row['ruler_id'] not in by_id:
                continue
            r = by_id[row['ruler_id']]
            if a in AXES:
                _apply_state(row, r['axes'][a])
            else:
                _apply_c4(row, r)
        _competition_ranks(_records(payload))
        payload.pop('v2_activation', None)
        payload['status'] = 'FORMAL_GOVERNANCE_V4_ACTIVE'
        payload['formula'] = 'canonical pool: max(axis_floor, F(S_main)*(1-L_rate)), ROUND_HALF_UP(1)' if a in AXES else 'retained terminal recovery - attributable deterioration - residual DA'
        payload['governance_activation'] = {'version': VERSION, 'review_path':REVIEW_PATH.as_posix(), 'reviewed_record_count':len(by_id), 'out_of_scope_formal_record_count':len(_records(payload))-len(by_id)}
        if a == 'C4':
            payload['recovery_formula_version'] = VERSION
    for r in source['records']:
        ruling = by_id.get(r['ruler_id'])
        if not ruling:
            continue
        for a in AXES:
            s=ruling['axes'][a]; e=r['entry_matrix'][a]
            e['state_anchors']={'S0':s['s0_label'],'S_main':s['main_label'],'S_avg':s['main_label'],'S_end':s['end_label']}
            e['adjudication_reason']=s['evidence_basis']
            e['loss_grade']=s['loss_review']['grade']
            e['loss_review_ref']=f'{REVIEW_PATH.as_posix()}#ruler_id={r["ruler_id"]}&axis={a}'
            e.pop('K', None)
            e.pop('K_role', None)
        r['entry_matrix']['current_C4']['deterioration_penalty']=ruling['recovery']['deterioration_penalty']
        r['actual_power_window'] = ruling['actual_power_window']
        r['decision']['reason'] = re.sub(r'可归责恶化另扣[\d.]+分', f'可归责恶化另扣{ruling["recovery"]["deterioration_penalty"]:.1f}分', r['decision']['reason'])
    polities = load_ruler_polities(root)
    for a,p in FORMAL_PATHS.items():
        write_json(root / p, payloads[a], ruler_polities=polities)
    write_json(root / CURRENT_REVIEW_PATH, source)
    review['score_active']=True; review['status']='FORMAL_GOVERNANCE_V4_ACTIVE'
    review['activation']={'version':VERSION,'reviewed_record_count':len(by_id),'status':'ACTIVE'}
    write_json(root / REVIEW_PATH, review)
    write_component_readers(root)
    write_governance_state_recovery_markdown(root)
    return verify_governance_state_recovery_review(root)


def write_component_readers(workspace_root: Path) -> None:
    """Render current component values and ruling evidence, preserving JSON lineage."""
    root = workspace_root.resolve()
    for axis, rel in FORMAL_PATHS.items():
        payload = load_json(root / rel)
        rows = sorted(payload['scores'], key=lambda r: (r['rank'], r['ruler_id']))
        lines = [f'# {axis}财政民生正式结算', '', f'> 当前规范池采用{VERSION}。池外记录保留既有结果且不进入当前综合榜。', '']
        if axis in AXES:
            lines += ['| 人物 | 政权 | 全任曲线 S0→S_main→S_end | L有限修正 | 分数 |', '|---|---|---|---|---:|']
            for row in rows:
                s=row['state_anchors']
                curve='→'.join(str(s.get(k,s.get('S_avg',''))) for k in ('S0','S_main','S_end'))
                lines.append(f'| {row["ruler_name"]} | {row["polity"]} | {curve} | {row.get("loss_grade","池外既有裁决")} | **{row["score"]:.1f}** |')
        else:
            lines += ['| 排名 | 人物 | 政权 | 保留恢复 | 归责恶化 | DA | C4净分（恢复 - 可归责恶化 - DA） |', '|---:|---|---|---:|---:|---|---:|']
            for row in rows:
                lines.append(f'| {row["rank"]} | {row["ruler_name"]} | {row["polity"]} | {row["positive_score_retained"]:.1f} | {row["deterioration_penalty"]:.1f} | {row["destructive_amplification_grade"]}/{row["destructive_amplification_penalty"]:.1f} | **{row["score"]:.1f}** |')
        lines += ['', '## 逐人裁决', '']
        for row in rows:
            lines += [f'### {row["ruler_name"]}（{row["polity"]}）', '']
            if axis in AXES:
                s=row['state_anchors']
                lines += [f'- 结算：主档{row["main_band"]}；{row.get("loss_grade","池外既有裁决")}；计{row["score"]:.1f}/{FIXED_POINTS[axis][-1]:.0f}。', f'- 三锚：{s.get("S0")}→{s.get("S_main",s.get("S_avg"))}→{s.get("S_end")}。', f'- 主态与交班依据：{row["adjudication_reason"]}', f'- 低谷与去重：{row.get("stability_basis", "见正式JSON既有裁决。") }']
            else:
                lines += [f'- 结算：C4净分**{row["score"]:.1f}**；保留恢复{row["positive_score_retained"]:.1f}，归责恶化{row["deterioration_penalty"]:.1f}，{row["destructive_amplification_grade"]}扣{row["destructive_amplification_penalty"]:.1f}。', f'- 恢复：{row.get("recovery_and_absorption", "")}', f'- 行为与归责：{row["behavior_and_attribution"]}', f'- 交班：{row.get("handoff_state", "")}', f'- 去重：{row.get("active_civilian_cost_review",{}).get("absorbed_and_excluded_basis", "")}']
            materials=row.get('material_basis',[])
            if materials:
                lines.append('- 材料依据：')
                for m in materials:
                    if isinstance(m,dict):
                        lines.append('  - '+str(m.get('book',m.get('source','既有材料概述')))+'：'+str(clean_retired_low_valley_references(m.get('original_text',m.get('quote',m.get('basis',m.get('display_text','')))), 'material_basis')))
                    else:
                        lines.append('  - '+str(m))
            if row.get('state_adjudication'):
                lines.append('- 完整裁决与引用：[逐人源](../../../../config/second-item/governance-state-recovery-adjudications.json)。')
            lines.append('')
        (root/rel.with_suffix('.md')).write_text('\n'.join(lines),encoding='utf-8')


def refresh_supporting_projections(workspace_root: Path) -> None:
    """Synchronize ruling annotations and civilian-cost consumption references."""
    root = workspace_root.resolve()
    review = load_json(root / REVIEW_PATH)
    if review.get('score_active') is not True:
        raise ValueError('Supporting projections require an active uniform ruling')
    rulings = {r['ruler_id']:r for r in review['records']}
    payloads = {a:load_json(root/p) for a,p in FORMAL_PATHS.items()}
    for a in AXES:
        for row in payloads[a]['scores']:
            if row['ruler_id'] in rulings:
                _apply_state(row,rulings[row['ruler_id']]['axes'][a])
    audit_path = FORMAL_PATHS['C4'].with_name('06-主动民力成本去重审计.json')
    audit = load_json(root/audit_path)
    entries = {r['ruler_id']:r for r in audit['records']}
    for row in payloads['C4']['scores']:
        r = rulings.get(row['ruler_id'])
        if r is None:
            continue
        _apply_c4(row,r)
        cost = row['active_civilian_cost_review']
        basis = cost['absorbed_and_excluded_basis']
        basis = clean_retired_low_valley_references(re.split(r' V[34]消费核对：', basis, maxsplit=1)[0], 'absorbed_and_excluded_basis')
        basis += ' V4消费核对：'+'；'.join(a+' '+r['axes'][a]['loss_review']['deduplication'] for a in AXES)+' 既有DA只保留本审计所列独立供役、机会成本或其他残余对象；不按L扣分大小另加成本。'
        cost['absorbed_and_excluded_basis'] = basis
        entries[row['ruler_id']]['absorbed_and_excluded_basis'] = basis
    polities=load_ruler_polities(root)
    for a,p in FORMAL_PATHS.items():
        _competition_ranks(payloads[a]['scores'])
        write_json(root/p,payloads[a],ruler_polities=polities)
    audit = clean_retired_low_valley_references(audit)
    write_json(root/audit_path,audit)
    lines=['# 主动民力成本去重审计','', '本表按实际窗口、群体与后果支撑当前C4残余成本裁决。军资军粮等军事投入本体不重复转入DA；恢复期按L实际消费核对，不能一律豁免或把整个恢复链视为已经消费。','', '| 人物 | 证据模式 | DA | 独立民力依据 | 已消费与排除 |','|---|---|---|---|---|']
    for r in audit['records']:
        lines.append('| '+' | '.join(str(r[k]).replace('|','／').replace('\n',' ') for k in ('ruler_name','evidence_mode','final_grade','choice_and_civilian_basis','absorbed_and_excluded_basis'))+' |')
    (root/audit_path.with_suffix('.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_component_readers(root)
    write_governance_state_recovery_markdown(root)


def write_governance_state_recovery_markdown(workspace_root: Path) -> Path:
    root = workspace_root.resolve()
    review = load_json(root / REVIEW_PATH)
    verify_governance_state_recovery_review(root)
    lines=['# 主态低谷与净恢复逐人裁决', '', f'> 规则：{VERSION}；'+('当前正式结果。' if review['score_active'] else '待统一启用的裁决。'), '', f'覆盖当前规范池{len(review["records"])}人；L为低谷修正，历史稳定诊断仅作独立画像引用。', '', '| 人物 | C1主/交/L/分 | C2主/交/L/分 | C3主/交/L/分 | 保留恢复 |','|---|---|---|---|---:|']
    for r in review['records']:
        cells=[f'{r["axes"][a]["main_band"]}/{r["axes"][a]["end_band"]}/{r["axes"][a]["loss_review"]["grade"]}/{r["axes"][a]["state_score"]:.1f}' for a in AXES]
        lines.append('| '+r['ruler_name']+' | '+' | '.join(cells)+f' | {r["recovery"]["calculation"]["positive_retained"]:.1f} |')
    lines += ['', '## 逐轴依据', '']
    for r in review['records']:
        lines += [f'### {r["ruler_name"]}', '']
        for a in AXES:
            loss = r['axes'][a]['loss_review']
            lines.append(f'- {a} {loss["grade"]}：{loss["basis"]}')
        lines += [f'- 完整三锚、主态依据、恢复归责及史源见[逐人裁决源](../../../../config/second-item/governance-state-recovery-adjudications.json)。','']
    path=root / REVIEW_MARKDOWN_PATH
    path.write_text('\n'.join(lines),encoding='utf-8')
    return path
