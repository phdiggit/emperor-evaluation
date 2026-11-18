"""Deterministic civilian-harm accounting; historical rulings are authored inputs.

Each formal record declares adoption or an explicit legacy baseline. Numerical
validation never infers an unadjudicated price or historical attribution.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

AXES = ('C1', 'C2', 'C3')
WEIGHTS = {'C1': Decimal('.5'), 'C2': Decimal('.2'), 'C3': Decimal('.3')}
BASELINE_STATES = {'BASELINE_RETAINED', 'UNRESOLVED', 'NOT_READY'}
FORMAL_VERSION = 'C4-CIVILIAN-HARM-V2'


def is_adopted(row: Mapping) -> bool:
    return row.get('civilian_harm_adjudication', {}).get('status') == 'ADOPTED'


def formal_calculation(row: Mapping, ruling: Mapping | None = None,
                       recovery: Any = None, deterioration: Any = None, *, scenario: bool = False) -> dict:
    """Read the declared mechanism; never turn an unadjudicated price into zero."""
    r = row['positive_score_retained'] if recovery is None else recovery
    e = row['deterioration_penalty'] if deterioration is None else deterioration
    if not is_adopted(row):
        p = row['destructive_amplification_penalty']
        return {'R':r, 'E_before':e, 'E_remaining':e, 'P':None,
                'legacy_DA':p, 'C_state_L':0.0, 'C_E':0.0,
                'C4':legacy_c4_score(r,e,p)}
    judgment = row['civilian_harm_adjudication']
    actual = judgment['actual_states']
    paths = row['deterioration_path_basis']
    if ruling is not None:
        actual = {a:{'main_band':ruling['axes'][a]['main_band'],
                     'loss_grade':ruling['axes'][a]['loss_review']['grade']} for a in AXES}
        paths = {a:{'raw_drop':max(0,ruling['axes'][a]['s0_band']-ruling['axes'][a]['end_band']),
                    'attribution_factor':ruling['recovery']['deterioration_attribution_by_axis'][a]} for a in AXES}
    references=judgment['state_references']
    removed=judgment['E_removed_steps']
    if scenario:
        from .governance_state_recovery import state_score
        references={a:(ref if state_score(a,ref['main_band'],ref['loss_grade']) >= state_score(a,actual[a]['main_band'],actual[a]['loss_grade']) else actual[a]) for a,ref in references.items()}
        removed={a:min(n,paths[a]['raw_drop']) for a,n in removed.items()}
    return calculate_harm(recovery=r, price=judgment['price'], actual=actual,
                          references=references, paths=paths, removed=removed)


def formal_net_line(row: Mapping) -> str:
    if is_adopted(row):
        c = formal_calculation(row)
        return (f"保留恢复 +{c['R']:g}分 − 剩余恶化 {c['E_remaining']:g}分"
                f" − 损害总价 {c['P']:g}分 + 已计回补 {c['C_state_L']:g}分 = 净调整 {row['score']:+.1f}分。")
    return (f"保留恢复 +{row['positive_score_retained']:g}分 − 本人恶化 {row['deterioration_penalty']:g}分"
            f" − 独立额外成本 {row['destructive_amplification_penalty']:g}分 = 净调整 {row['score']:+.1f}分。")


def mechanism_label(row: Mapping) -> str:
    judgment = row.get('civilian_harm_adjudication')
    if judgment is None:
        return row['destructive_amplification_grade']
    if is_adopted(row):
        return '损害总价P' + str(int(number(judgment['price']) / Decimal('4.5')))
    return {'BASELINE_RETAINED':'新制未定稿，保留旧制', 'UNRESOLVED':'新制未裁，保留旧制',
            'NOT_READY':'未就绪，保留旧制', 'OUTSIDE_POOL':'池外保留旧制'}[judgment['status']]


def refresh_current_summary(row: dict) -> None:
    """Refresh current summaries without changing the retained DA evidence."""
    if 'civilian_harm_adjudication' not in row:
        return
    row['public_adjudication'] = formal_net_line(row)
    row['public_basis_version'] = FORMAL_VERSION
    pattern = row.get('typical_pattern')
    if isinstance(pattern, dict) and pattern.get('status') == 'STRUCTURED_C4_FORMAL':
        for field in ('recovery_score', 'positive_score_retained', 'closed_recovery_axes'):
            pattern[field] = row[field].copy() if isinstance(row[field], list) else row[field]


def validate_formal(row: Mapping, root=None) -> None:
    """Validate current authored groups and numerical accounting, not historical truth."""
    j = row.get('civilian_harm_adjudication')
    if not isinstance(j,dict) or j.get('version') != FORMAL_VERSION:
        raise ValueError('Missing current civilian-harm ruling')
    if j.get('status') not in {'ADOPTED',*BASELINE_STATES,'OUTSIDE_POOL'}:
        raise ValueError('Invalid civilian-harm status')
    if not is_adopted(row):
        if j.get('price') is not None or j.get('state_references') or j.get('E_removed_steps'):
            raise ValueError('Unadjudicated harm cannot create prices or refunds')
    else:
        if number(j['price']) == 0 and (j['state_references'] or j['E_removed_steps']):
            raise ValueError('Zero admitted harm cannot create a refund')
        for field in ('group_id','scope_basis','price_basis','state_credit_basis','E_basis','R_basis'):
            if not isinstance(j.get(field),str) or not j[field].strip():
                raise ValueError(f'Missing civilian-harm {field}')
        refs=j.get('source_refs')
        if not isinstance(refs,list) or not refs:
            raise ValueError('Missing civilian-harm sources')
        for ref in refs:
            if not isinstance(ref,str) or not ref.startswith(('docs/','config/','http://','https://')) or '.tmp' in ref:
                raise ValueError('Nonpermanent civilian-harm source')
            if root is not None and ref.startswith(('docs/','config/')):
                import re
                path=re.sub(r':\d+(?:-\d+)?$','',ref.split('#')[0])
                if not (root/path).is_file():
                    raise ValueError(f'Missing civilian-harm source: {ref}')
        if set(j.get('state_bindings',{})) != set(j['state_references']) or set(j.get('E_bindings',{})) != set(j['E_removed_steps']):
            raise ValueError('Missing civilian-harm ledger explanation')
        if j.get('military_inputs_excluded') is not True or j.get('same_consequence_multiple_refunds') is not False:
            raise ValueError('Unresolved military or cross-axis double charge')
    c = formal_calculation(row)
    if row['score'] != c['C4'] or row['raw_score'] != c['C4']:
        raise ValueError('Civilian-harm score drift')
    if is_adopted(row) and row.get('civilian_harm_calculation') != c:
        raise ValueError('Civilian-harm calculation projection drift')
    if 'public_adjudication' in row and row['public_adjudication'] != formal_net_line(row):
        raise ValueError('Civilian-harm public summary drift')
    pattern = row.get('typical_pattern')
    if isinstance(pattern, dict) and pattern.get('status') == 'STRUCTURED_C4_FORMAL':
        for field in ('recovery_score', 'positive_score_retained', 'closed_recovery_axes'):
            if pattern.get(field) != row.get(field):
                raise ValueError('Civilian-harm recovery summary drift: ' + field)


def number(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError('Expected a finite number')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Expected a finite number') from exc
    if not result.is_finite():
        raise ValueError('Expected a finite number')
    return result


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal('.1'), rounding=ROUND_HALF_UP)


def legacy_c4_score(recovery: Any, deterioration: Any, penalty: Any) -> float:
    """Residual-cost formula for explicit legacy baselines, shared by consumers."""
    value = number(recovery) - number(deterioration) - number(penalty)
    return float(rounded(max(Decimal(-40), min(Decimal(27), value))))


def remaining_deterioration(paths: Mapping, removed: Mapping) -> Decimal:
    """Remove authored raw boundaries, then combine, cap and round once."""
    if set(paths) != set(AXES) or not set(removed) <= set(AXES):
        raise ValueError('Invalid deterioration axes')
    value = Decimal(0)
    for axis in AXES:
        path = paths[axis]
        drop, count = path['raw_drop'], removed.get(axis, 0)
        if type(drop) is not int or not 0 <= drop <= 5:
            raise ValueError('Invalid actual decline')
        if type(count) is not int or not 0 <= count <= drop:
            raise ValueError('Removal exceeds actual decline')
        factor = number(path['attribution_factor'])
        if not 0 <= factor <= 1:
            raise ValueError('Invalid deterioration attribution')
        value += WEIGHTS[axis] * factor * (drop-count)
    return rounded(min(Decimal(1), value/2) * 13)


def state_credit(actual: Mapping, references: Mapping) -> tuple[Decimal, list]:
    """Reprice a single combined main-state/L reference on each axis."""
    # Local import keeps the legacy calculator usable by governance itself.
    from .governance_state_recovery import state_score
    if set(actual) != set(AXES) or not set(references) <= set(AXES):
        raise ValueError('Invalid state axes')
    total, details = Decimal(0), []
    for axis in AXES:
        current = actual[axis]
        original = number(state_score(axis, current['main_band'], current['loss_grade']))
        if 'score' in current and number(current['score']) != original:
            raise ValueError('Actual state score drift')
        if axis not in references:
            continue
        ref = references[axis]
        target = number(state_score(axis, ref['main_band'], ref['loss_grade']))
        credit = target-original
        if credit < 0:
            raise ValueError('Negative state credit')
        total += credit
        details.append({'axis':axis, 'actual_score':float(original),
                        'reference_score':float(target), 'credit':float(credit)})
    return total, details


def calculate_harm(*, recovery: Any, price: Any, actual: Mapping,
                   references: Mapping, paths: Mapping, removed: Mapping) -> dict:
    """Calculate an already adjudicated candidate, without a C4 clamp.

    This low-level function checks numerical constraints, not admission or
    source adequacy. Use validate_candidate for authored migration records.
    """
    r, p = number(recovery), number(price)
    if not 0 <= r <= 27:
        raise ValueError('Invalid retained recovery')
    if p not in {Decimal('4.5')*i for i in range(7)}:
        raise ValueError('Price outside the seven bands')
    c, details = state_credit(actual, references)
    before = remaining_deterioration(paths, {})
    after = remaining_deterioration(paths, removed)
    result = r-after-p+c
    return {'R':float(r), 'P':float(p), 'E_before':float(before),
            'E_remaining':float(after), 'C_state_L':float(c),
            'C_E':float(before-after), 'C4':float(rounded(result)),
            'state_credit_details':details}


def validate_candidate(record: Mapping) -> dict | None:
    """Validate explicit draft provenance and ledger bindings, never adopt it.

    Outcome IDs distinguish actual consequences, not citations. Semantic
    adequacy and truth of those authored distinctions still require review.
    """
    state = record.get('migration_state')
    if state in BASELINE_STATES:
        if record.get('price') is not None or record.get('calculation_input') is not None:
            raise ValueError('Baseline/unresolved records cannot carry a new price')
        return None
    if state != 'PRICED_CANDIDATE':
        raise ValueError('Unknown migration state')
    outcomes = record.get('outcomes', [])
    ids = [x.get('id') for x in outcomes]
    if any(not isinstance(x,str) or not x.strip() for x in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Invalid or duplicate outcome ID')
    modes = set()
    for outcome in outcomes:
        for field in ('scope', 'consequence', 'attribution', 'allocation'):
            if not isinstance(outcome.get(field), str) or not outcome[field].strip():
                raise ValueError(f'Missing outcome {field}')
        mode = outcome.get('evidence_mode')
        if mode not in {'DIRECT','INFERRED'}:
            raise ValueError('Invalid admitted evidence mode')
        modes.add(mode)
        refs = outcome.get('source_refs')
        if not isinstance(refs,list) or not refs:
            raise ValueError('Missing source references')
        for ref in refs:
            if (not isinstance(ref,str) or not ref.startswith(('docs/','config/','https://','http://'))
                    or '.tmp' in ref or '..' in ref.split('/') or '\\' in ref):
                raise ValueError('Invalid permanent source reference')
    p = number(record.get('price'))
    if (p > 0) != bool(outcomes):
        raise ValueError('Price and admitted scope disagree')
    if modes == {'INFERRED'} and p != Decimal('4.5'):
        raise ValueError('Inferred-only scope exceeds the conservative price')
    if not isinstance(record.get('price_basis'),str) or not record['price_basis'].strip():
        raise ValueError('Missing price basis')
    inputs = record['calculation_input']
    if number(inputs['price']) != p:
        raise ValueError('Conflicting prices')
    for field, ledger in [('references','state_bindings'), ('removed','E_bindings')]:
        values, bindings = inputs[field], record.get(ledger,{})
        if set(values) != set(bindings):
            raise ValueError('Missing ledger binding')
        consumed = set()
        for axis, binding in bindings.items():
            linked = binding.get('outcome_ids', [])
            if (not isinstance(linked,list) or not linked or len(set(linked)) != len(linked)
                    or not set(linked) <= set(ids)):
                raise ValueError('Unknown or duplicate ledger outcome')
            if consumed & set(linked):
                raise ValueError('Same consequence refunded on multiple axes')
            consumed.update(linked)
            if not isinstance(binding.get('basis'),str) or not binding['basis'].strip():
                raise ValueError('Missing ledger basis')
    return calculate_harm(**inputs)
