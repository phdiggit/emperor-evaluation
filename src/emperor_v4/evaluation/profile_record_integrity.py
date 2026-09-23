"""Current profile invariants, independent of historical adjudication reports."""
from collections import Counter


SCORES = {
    'G0': {'LOW': 2, 'MID': 7, 'HIGH': 12},
    'G1': {'LOW': 18, 'MID': 25, 'HIGH': 31},
    'G2': {'LOW': 38, 'MID': 45, 'HIGH': 51},
    'G3': {'LOW': 58, 'MID': 65, 'HIGH': 71},
    'G4': {'LOW': 77, 'MID': 82, 'HIGH': 87},
    'G5': {'LOW': 91, 'MID': 94, 'HIGH': 97},
}
ROLES = ('DIRECT_COMMAND', 'OPERATIONAL_COORDINATION', 'STRATEGIC_DIRECTION',
         'NOMINAL_AUTHORIZATION', 'ROLE_UNRESOLVED')


def verify_current_records(payload: dict) -> None:
    """Validate declared lineage and projections; never infer historical semantics."""
    records = payload['records']
    by_id = {r['ruler_id']: r for r in records}
    assert len(by_id) == len(records), 'duplicate ruler identity'
    assert payload['record_count'] == len(records)
    for r in records:
        label = f"{payload['axis_code']}:{r['ruler_name']}"
        assert r['radar_value'] == r['score_100'] == SCORES[r['axis_grade']][r['position']], label
        parents = r.get('parent_chains', [])
        ids = [p['parent_id'] for p in parents]
        assert len(ids) == len(set(ids)), f'{label}: duplicate parent id'
        if 'representative_parent_ids' in r:
            assert set(r['representative_parent_ids']) <= set(ids), f'{label}: detached representative parent'
        episode_refs = [p.get('capability_episode_ref', p['parent_id']) for p in parents]
        assert len(episode_refs) == len(set(episode_refs)), f'{label}: repeated capability episode'
        aliases = [a for p in parents for a in p.get('source_alias_parent_ids', [])]
        assert not set(aliases) & set(ids), f'{label}: alias is also scored'
        assert len(aliases) == len(set(aliases)), f'{label}: repeated parent alias'
        excluded = {p.get('source_parent_ref') for p in r.get('non_scoring_observations', [])}
        assert not set(ids) & excluded, f'{label}: excluded observation is still scored'
        for observation in r.get('non_scoring_observations', []):
            assert observation['reason'] and observation['source_refs'], f'{label}: untraceable disposition'
        relevance = r.get('axis_relevance_check', {})
        if 'scoring_parent_refs' in relevance:
            assert set(relevance['scoring_parent_refs']) == set(ids), f'{label}: stale scoring references'
        balance = r.get('directional_strength_balance_review', {})
        suppression = set(balance.get('suppression_parent_ids', []))
        assert suppression <= set(ids), f'{label}: stale suppression references'
        for p in parents:
            if p['parent_id'] in suppression:
                assert p['direction'] in ('NEGATIVE', 'MIXED_NEGATIVE', 'MIXED'), f'{label}: positive suppression parent'
            if 'intensity' in p and 'material_intensity' in p:
                assert p['intensity'] == p['material_intensity'], f'{label}: conflicting intensity'
        calibration = r.get('horizontal_calibration')
        if calibration:
            assert calibration['decision_basis'] and calibration['scores_used_as_formula'] is False, label
            assert len(calibration['comparators']) >= 2, f'{label}: no adjacent calibration'
            for c in calibration['comparators']:
                assert c['ruler_id'] in by_id and c['ruler_id'] != r['ruler_id'] and c['comparison'], label
        if payload['axis_code'] == 'M1':
            items = r.get('m1_role_projection', {}).get('items', [])
            refs = [p['capability_episode_ref'] for p in items]
            assert len(refs) == len(set(refs)), f'{label}: repeated military episode'
            dist = r['m1_role_distribution']
            assert dist['unique_episode_count'] == len(refs), f'{label}: stale role count'
            for role in ROLES:
                expected = {p['capability_episode_ref'] for p in items if p['m1_role_class'] == role}
                assert set(dist[role]['episode_refs']) == expected, f'{label}: stale role references'
                assert dist[role]['episode_count'] == len(expected), f'{label}: stale role subtotal'
            for p in items:
                assert p['m1_role_class'] in ROLES, label
                assert not (p['m1_role_class'] == 'NOMINAL_AUTHORIZATION' and
                            p.get('direction') in ('NEGATIVE', 'MIXED_NEGATIVE')), f'{label}: nominal role with accountable negative decision'
    summary = payload.get('summary', {})
    for key, field in (('grade_distribution', 'axis_grade'), ('position_distribution', 'position'),
                       ('evidence_level_distribution', 'axis_evidence_level'),
                       ('axis_evidence_distribution', 'axis_evidence_level'),
                       ('output_mode_distribution', 'output_mode'), ('confidence_distribution', 'confidence'),
                       ('score_status_distribution', 'score_status')):
        if key in summary:
            assert summary[key] == dict(Counter(r[field] for r in records)), f'stale {key}'
    if 'parent_count' in summary:
        assert summary['parent_count'] == sum(len(r.get('parent_chains', [])) for r in records)
