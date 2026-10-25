"""Positive sovereign-result attribution; never a personal-command talent share."""
ATTRIBUTION_SCALE = {'EXCLUDED': 0, 'MIXED_SOURCES': 0.5, 'SOVEREIGN_AUTHORITY': 1}


def positive_source_refs(axis):
    structure = axis.get('within_band_structure_improvement') or {}
    steps = [s for s in axis.get('improvement_step_credits', []) if s['credit'] > 0]
    if not (steps or structure or axis.get('ceiling_progress_bonus') or axis.get('maintenance_bonus')):
        return set()
    refs = set(axis.get('attribution_source_refs') or [])
    for step in steps: refs.update(step.get('source_refs') or [])
    refs.update(structure.get('parent_cycle_refs') or [])
    if axis.get('ceiling_progress_bonus'): refs.update(axis.get('ceiling_progress_parent_cycle_refs') or [])
    if axis.get('maintenance_bonus'):
        gate = axis.get('low_position_resilience_gate') or axis.get('historic_maintenance_gate') or axis.get('maintenance_evidence_gate') or {}
        for field in ('pressure_refs', 'preservation_refs', 'continued_effectiveness_refs'):
            refs.update(gate.get(field) or [])
    return refs


def validate_attribution(record, credit):
    mode = record.get('attribution_mode')
    if mode not in ATTRIBUTION_SCALE or isinstance(credit, bool) or ATTRIBUTION_SCALE[mode] != credit:
        raise ValueError('A正向归属须为排除0、具名混合0.5或本人统治责任1')
    if mode == 'MIXED_SOURCES':
        if record.get('mixed_source_type') not in {'EXTERNAL_CHANGE','SHARED_POWER','CROSS_ITEM_EXCLUSION'} or not str(record.get('mixed_source_basis') or '').strip():
            raise ValueError('A混合归属须列具名外生、共同实权或排除成果，不能只写臣下执行')


def validate_shared_consequences(row, shared_refs):
    """Shared war/source identity neither proves nor forbids distinct effects."""
    if not shared_refs:
        return
    allocation = row.get('a_result_allocation') or {}
    if set(allocation.get('shared_source_refs', [])) != set(shared_refs):
        raise ValueError('A两轴共用来源须完整登记后果分配')
    units = [allocation.get(axis) or {} for axis in ('A1', 'A2')]
    for unit in units:
        if not all(isinstance(unit.get(k), str) and unit[k].strip() for k in ('result_id', 'consequence')):
            raise ValueError('A两轴须各有具体后果及结果标识')
    if units[0]['result_id'] == units[1]['result_id'] or units[0]['consequence'] == units[1]['consequence']:
        raise ValueError('同一后果不得在A1、A2换名重复计分')
