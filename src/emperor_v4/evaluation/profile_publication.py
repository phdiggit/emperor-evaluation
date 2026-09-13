"""Explicit terminal publication states, distinct from pending work and inapplicability."""

CLOSED_NO_GRADE = "EVIDENCE_INSUFFICIENT_CLOSED"


def validate_final_capability_review(row: dict) -> None:
    """Keep a final no-demonstration classification distinct from proven failure."""
    scoring = [p for p in row.get('parent_chains', []) if p.get('consumption_status') == 'SCORING_PARENT']
    terminal = row.get('assessment_basis') == 'NO_DEMONSTRATED_CAPABILITY'
    if not terminal:
        if not scoring:
            raise ValueError('M2 grade needs a scoring decision or explicit final capability review')
        return
    if scoring:
        raise ValueError('Observed diplomatic decisions cannot be classified as no demonstrated capability')
    expected = {'axis_grade': 'G0', 'position': 'MID', 'score_100': 7, 'radar_value': 7,
                'axis_evidence_level': 'E1', 'confidence': 'LOW', 'output_mode': 'EPISODE_TAG',
                'score_status': 'EVIDENCE_LIMITED', 'adjudication_state': 'FORMAL_CURRENT',
                'display_point_only': False}
    review = row.get('final_capability_review', {})
    if (any(row.get(k) != v for k, v in expected.items()) or
            not all(review.get(k) for k in ('actual_window', 'direct_review', 'indirect_review',
                                           'exclusion_basis', 'source_refs', 'conclusion')) or
            review.get('claim_scope') != 'REVIEWED_EVIDENCE_ONLY' or
            not row.get('limitations') or '未显示外交能力' not in row.get('typical_pattern', '')):
        raise ValueError('Final capability review requires its evidence scope and limited publication')


def validate_bounded_diplomatic_grade(row: dict) -> None:
    """A bounded grade needs an observed decision, never a missing-data default."""
    parents = [p for p in row.get('parent_chains', []) if p.get('bounded_adjudication')]
    if not parents:
        return
    projection = {'E1': ('LOW', 'EPISODE_TAG'), 'E2': ('MEDIUM', 'BOUNDED_PROFILE')}
    evidence = row.get('axis_evidence_level')
    if (evidence not in projection or
            (row.get('confidence'), row.get('output_mode')) != projection[evidence] or
            row.get('score_status') != 'EVIDENCE_LIMITED' or
            not row.get('limitations') or not row.get('position_basis') or
            row.get('adjudication_state') != 'FORMAL_CURRENT'):
        raise ValueError('Bounded M2 grade must retain evidence limits and publication state')
    scoring = set(row.get('axis_relevance_check', {}).get('scoring_parent_refs', []))
    for parent in parents:
        if (parent.get('consumption_status') != 'SCORING_PARENT' or
                parent.get('parent_id') not in scoring or
                parent.get('membership_relative_to_evaluated_ruler') != 'EXTERNAL_TO_EVALUATED_RULER' or
                parent.get('counterparty_condition_authenticity') != 'VERIFIED_EXTERNAL' or
                not all(parent.get(k) for k in ('source_refs', 'cycle_basis', 'attribution_basis', 'actual_window'))):
            raise ValueError('Bounded M2 grade lacks an attributable external decision')


def is_closed_no_grade(row: dict) -> bool:
    return row.get("adjudication_state") == CLOSED_NO_GRADE


def validate_closed_no_grade(row: dict, axis: str) -> None:
    values = ("axis_grade", "position", "score_100", "radar_value")
    if axis != "M2" or not is_closed_no_grade(row) or any(k not in row or row[k] is not None for k in values):
        raise ValueError("No-grade closure requires an explicit M2 terminal state and null grade values")
    if (row.get("output_mode") != "NO_GRADE" or row.get("score_status") != "EVIDENCE_INSUFFICIENT"
            or row.get("display_point_only") is not False or row.get("formal_status") != "FORMAL_CURRENT"
            or not row.get("grade_basis") or not row.get("position_basis")
            or not all(row.get("no_grade_closure", {}).get(k) for k in ("review_scope", "evidence_gap", "reopen_condition"))):
        raise ValueError("No-grade closure must retain its scope, gap, and reopening condition")
    if not any(p.get("source_refs") for p in row.get("parent_chains", row.get("parents", []))):
        raise ValueError("No-grade closure must retain source references")
