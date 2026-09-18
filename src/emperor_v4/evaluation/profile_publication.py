"""Explicit terminal publication states, distinct from pending work and inapplicability."""

import re

CLOSED_NO_GRADE = "EVIDENCE_INSUFFICIENT_CLOSED"
FULL_LIFETIME_ATTRIBUTABLE_EVENTS = "FULL_LIFETIME_ATTRIBUTABLE_EVENTS"


def validate_m2_full_lifetime_scope(row: dict) -> None:
    """M2 evidence admission is causal and full-lifetime; actual_power_window is background only."""
    reviews = row.get("reviews") or {}
    negative_scope = reviews.get("negative_search_scope")
    if negative_scope is not None:
        if (FULL_LIFETIME_ATTRIBUTABLE_EVENTS not in negative_scope
                or "ACTUAL_POWER_WINDOW" in negative_scope):
            raise ValueError("M2 negative search must cover full-lifetime attributable events")

    anti_time_gate = re.compile(
        r"(?:不再参与升降档|不参与升降档|不作负证|不是扣分理由|"
        r"不以.{0,20}(?:窗口|任期|在位|亲政|主政).{0,12}(?:扣分|换算|降档|封顶)|"
        r"不得把actual_power_window当作证据截止线|不因.{0,20}actual_power_window.{0,12}排除)"
    )
    forbidden_time_gate_patterns = (
        r"(?:短|长|极短|太短|较短|偏短)(?:任期|在位期|窗口)",
        r"(?:任期|在位|亲政|主政|实际主政|实际统治|权力窗口).{0,14}"
        r"(?:仅|只有|太短|较短|偏短|不足|有限|足够长)",
        r"(?:[0-9一二三四五六七八九十百]+|二十余|三十余|四十余|五十余)年"
        r"(?:内|余|左右)?(?:的)?(?:任期|在位|亲政|主政|统治|窗口).{0,18}"
        r"(?:阻止|限制|不上|不进|封顶|压低|抬高|取G|稳居|足以)",
    )
    grading_text = "\n".join([
        str(row.get("grade_basis") or ""),
        str(row.get("position_basis") or ""),
        *[str(value) for value in row.get("limitations") or []],
    ])
    for sentence in (
        part.strip()
        for part in re.split(r"[。；\n]+", grading_text)
        if part.strip()
    ):
        if not anti_time_gate.search(sentence) and any(
            re.search(pattern, sentence) for pattern in forbidden_time_gate_patterns
        ):
            raise ValueError("M2 grade cannot be gated by tenure/window length")


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
            review.get('evidence_admission_scope') != FULL_LIFETIME_ATTRIBUTABLE_EVENTS or
            review.get('claim_scope') != 'REVIEWED_EVIDENCE_ONLY' or
            not row.get('limitations') or '未显示外交能力' not in row.get('typical_pattern', '')):
        raise ValueError('Final capability review requires full-lifetime attributable-event scope and limited publication')


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
