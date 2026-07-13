from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path

import yaml
import pytest

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import EpisodeParticipant
from emperor_v4.domain.episode import build_episode_packet, group_episode_candidates
from emperor_v4.domain.versioning import apply_episode_revision
from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_appointment_delegation_shadow,
    run_appointment_delegation_shadow_manifest,
)
from emperor_v4.application.appointment_delegation_shadow_diff import (
    run_appointment_delegation_shadow_diff,
)
from emperor_v4.application.appointment_delegation_roster_runner import (
    run_appointment_delegation_roster_shadow,
)
from emperor_v4.evaluation.appointment_delegation_scoring import (
    evaluate_judgment,
)
from emperor_v4.evaluation.projection_judgment_shadow import (
    JUDGMENT_SHADOW_POLICY_VERSION,
    JUDGMENT_SHADOW_SCHEMA_VERSION,
    PROJECTION_SHADOW_POLICY_VERSION,
    build_projection_shadow_worklist,
)
from emperor_v4.evaluation.projection_readiness_rerun import (
    build_incremental_projection_rerun_worklist,
    materialize_incremental_judgment_rerun,
)
from emperor_v4.evaluation.rule_evidence_delta import (
    apply_rule_evidence_shadow_delta,
)


SCORED_DEMO = (
    Path(__file__).parents[1]
    / "eval"
    / "appointment_delegation_scored_demo"
    / "manifest.yml"
)
SHADOW_DIFF_REQUEST = SCORED_DEMO.parent / "shadow_diff_request.yml"
ROSTER_DEMO = SCORED_DEMO.parents[1] / "appointment_delegation_roster_demo"
ROSTER_MANIFEST = ROSTER_DEMO / "manifest.yml"
ROSTER_REPORT = ROSTER_DEMO / "report.json"


def _assertion(code: str, passage: str, *, domain: str = "军务") -> AssertionDraft:
    return AssertionDraft(
        assertion_code=code,
        source_passage_ref=passage,
        assertion_type="event_fact",
        subject="李世民",
        predicate="任命",
        object="李靖",
        time_expression="贞观三年",
        location_expression=None,
        qualifiers={
            "evaluation_context": "李世民",
            "candidate_participant_roles": (("李世民", "ruler"), ("李靖", "commander")),
            "episode_type": "appointment_delegation",
            "office_or_domain": domain,
            "outcome": "成功",
        },
        polarity="asserted",
        source_attribution={"document_code": f"D-{passage}"},
        candidate_episode_key=None,
        confidence=0.9,
    )


def _packet(*assertions: AssertionDraft):
    return build_episode_packet(group_episode_candidates(assertions)[0])


def test_unchanged_rerun_requires_no_write_or_model_call():
    current = _packet(_assertion("A-1", "P-1"))

    decision = apply_episode_revision(current, current)

    assert decision.packet is current
    assert not decision.write_required
    assert not decision.model_call_required


def test_scored_shadow_rerun_is_hash_stable_and_factor_change_invalidates_judgment():
    first = run_appointment_delegation_shadow(SCORED_DEMO)
    second = run_appointment_delegation_shadow(
        Path("eval/appointment_delegation_scored_demo/manifest.yml")
    )

    assert first == second
    assert first["report_sha256"] == second["report_sha256"]
    assert first["summary"]["model_call_count"] == 0
    assert first["summary"]["database_write_count"] == 0

    manifest = yaml.safe_load(SCORED_DEMO.read_text(encoding="utf-8"))
    unit = deepcopy(manifest["rule_evidence_units"][0])
    unit["factor_observations"]["feedback_handling"]["value"] = "mixed_signal"
    episodes = {row["episode_ref"]: row for row in manifest["historical_episodes"]}
    assertions = {row["assertion_ref"]: row for row in manifest["assertions"]}
    changed = evaluate_judgment(unit, episodes, assertions)

    original = next(
        row
        for row in first["judgments"]
        if row["rule_evidence_unit_ref"] == unit["unit_ref"]
    )
    assert changed["judgment_id"] != original["judgment_id"]


def test_shadow_diff_fails_closed_when_expected_invalidation_drifts(tmp_path: Path):
    request = yaml.safe_load(SHADOW_DIFF_REQUEST.read_text(encoding="utf-8"))
    request["baseline_manifest_path"] = str(SCORED_DEMO.resolve())
    request["expected_changed_unit_refs"] = ["REU-LSM-WEIZHENG-APPOINTMENT-v1"]
    request_path = tmp_path / "shadow-diff.yml"
    request_path.write_text(
        yaml.safe_dump(request, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="实际失效单元"):
        run_appointment_delegation_shadow_diff(request_path)


def test_roster_no_change_rerun_exactly_reuses_persistent_record():
    prior = json.loads(ROSTER_REPORT.read_text(encoding="utf-8"))
    rerun = run_appointment_delegation_roster_shadow(
        ROSTER_MANIFEST, prior_record_path=ROSTER_REPORT
    )

    assert rerun == prior
    assert rerun["run_record_sha256"] == prior["run_record_sha256"]
    assert rerun["side_effect_audit"]["service_call_count"] == 0
    assert rerun["side_effect_audit"]["model_call_count"] == 0
    assert rerun["side_effect_audit"]["database_write_count"] == 0


def test_scored_runner_rebuilds_one_unit_and_exactly_reuses_three():
    baseline = run_appointment_delegation_shadow(SCORED_DEMO)
    manifest = yaml.safe_load(SCORED_DEMO.read_text(encoding="utf-8"))
    unit = next(
        row
        for row in manifest["rule_evidence_units"]
        if row["unit_ref"] == "REU-LB-HANXIN-QI-AUTHORITY-v1"
    )
    unit["factor_observations"]["authority_clarity"]["value"] = "mixed_signal"
    candidate = run_appointment_delegation_shadow_manifest(
        manifest,
        SCORED_DEMO,
        prior_report=baseline,
        rebuild_unit_refs={unit["unit_ref"]},
    )

    assert candidate["summary"]["judgment_cache_hit_count"] == 3
    baseline_by_unit = {
        row["rule_evidence_unit_ref"]: row for row in baseline["judgments"]
    }
    candidate_by_unit = {
        row["rule_evidence_unit_ref"]: row for row in candidate["judgments"]
    }
    assert candidate_by_unit[unit["unit_ref"]] != baseline_by_unit[unit["unit_ref"]]
    assert all(
        candidate_by_unit[ref] == baseline_by_unit[ref]
        for ref in set(baseline_by_unit) - {unit["unit_ref"]}
    )


def _g3_versioned_unit(code: str, fingerprint: str, *, gap: bool) -> dict:
    return {
        "unit_code": code,
        "rule_code": "appointment_delegation",
        "rule_version": "appointment-delegation-v1-shadow",
        "aggregation_policy_version": "minimum-sufficient-scoring-arc-v1",
        "evaluation_context": "versioning-fixture",
        "semantic_fingerprint": fingerprint,
        "semantic_version": 1,
        "evidence_version": 1,
        "members": [
            {
                "member_ref": f"EP-{code}@v1",
                "member_type": "episode",
                "member_role": "delegation",
            }
        ],
        "aggregation_reason": "versioning fixture",
        "status": "draft",
        "lineage": {"component_code": f"COMP-{code}"},
        "provenance": {"policy_version": "fixture"},
        "ruler_ref": "皇帝甲",
        "person_ref": f"PER-{code}",
        "decision_arc_family": "appointment_feedback_correction",
        "included_link_refs": [f"SRP-{code}"],
        "scoring_arc_only_refs": [],
        "evidence_assertion_refs": [f"AST-{code}"],
        "question_readiness": {
            "delegation_quality": "ready",
            "supervision_quality": "ready",
            "correction_timeliness": "ready",
            "net_effect": "evidence_gap" if gap else "ready",
        },
    }


def _g3_delta_inputs() -> tuple[dict, dict, dict]:
    base = {
        "status": "rule_evidence_unit_shadow_ready",
        "task_code": "G3C-CONSOLIDATED",
        "shadow_gate_passed": True,
        "draft_unit_count": 2,
        "unresolved_component_count": 0,
        "duplicate_consumption_episode_refs": [],
        "formal_acceptance_performed": False,
        "formal_rule_evidence_unit_count": 0,
        "formal_projection_count": 0,
        "judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
        "rule_evidence_unit_drafts": [
            _g3_versioned_unit("RUE-GAP", "a" * 64, gap=True),
            _g3_versioned_unit("RUE-STABLE", "b" * 64, gap=False),
        ],
    }
    worklist = {
        "task_code": "G3F-CONSOLIDATED",
        "tasks": [
            {
                "gap_code": "JSG-1",
                "input_ref": "RUE-GAP",
                "current_episode_refs": ["EP-RUE-GAP@v1"],
                "open_readiness_questions": ["net_effect"],
            }
        ],
    }
    final = {
        "status": "source_gap_input_gate_passed_for_shadow_delta",
        "task_code": worklist["task_code"],
        "shadow_delta_authorized": True,
        "readiness_rerun_authorized": False,
        "accepted_shadow_delta_count": 1,
        "unresolved_count": 0,
        "rejected_count": 0,
        "formal_acceptance_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
        "accepted_shadow_deltas": [
            {
                "gap_code": "JSG-1",
                "boundary_disposition": "context_for_rule_evidence_unit",
                "candidate_assertion": {
                    "assertion_code": "AST-CONTEXT",
                    "source_passage_ref": "SP-CONTEXT",
                },
                "member_role": "context",
            }
        ],
    }
    return base, worklist, final


def test_rule_evidence_delta_invalidates_only_changed_unit_and_preserves_side_effects():
    base, worklist, final = _g3_delta_inputs()
    stable_before = deepcopy(base["rule_evidence_unit_drafts"][1])

    result = apply_rule_evidence_shadow_delta(base, worklist, final)

    changed = next(
        row for row in result["rule_evidence_unit_drafts"] if row["unit_code"] == "RUE-GAP"
    )
    stable = next(
        row
        for row in result["rule_evidence_unit_drafts"]
        if row["unit_code"] == "RUE-STABLE"
    )
    assert changed["unit_code"] == "RUE-GAP"
    assert changed["semantic_version"] == changed["evidence_version"] == 2
    assert changed["semantic_fingerprint"] != "a" * 64
    assert changed["question_readiness"]["net_effect"] == "ready"
    assert stable == stable_before
    assert result["projection_rebuild_unit_refs"] == ["RUE-GAP"]
    assert result["database_write_count"] == result["score_count"] == 0


@pytest.mark.parametrize("failure", ["non_gap", "duplicate_delta"])
def test_rule_evidence_delta_fails_closed_on_invalid_scope(failure: str):
    base, worklist, final = _g3_delta_inputs()
    if failure == "non_gap":
        base["rule_evidence_unit_drafts"][0]["question_readiness"][
            "net_effect"
        ] = "ready"
        match = "非 gap readiness"
    else:
        second_task = deepcopy(worklist["tasks"][0])
        second_task["gap_code"] = "JSG-2"
        worklist["tasks"].append(second_task)
        second_delta = deepcopy(final["accepted_shadow_deltas"][0])
        second_delta["gap_code"] = "JSG-2"
        second_delta["candidate_assertion"] = {
            "assertion_code": "AST-CONTEXT-2",
            "source_passage_ref": "SP-CONTEXT-2",
        }
        final["accepted_shadow_deltas"].append(second_delta)
        final["accepted_shadow_delta_count"] = 2
        match = "重复更新"

    with pytest.raises(ValueError, match=match):
        apply_rule_evidence_shadow_delta(base, worklist, final)


def _g3_judgment_row(projection: dict) -> dict:
    assertion_ref = projection["projection_payload"]["evidence_assertion_refs"][0]
    observation = {
        "value": "positive_signal",
        "reason": "versioning fixture",
        "evidence_assertion_refs": [assertion_ref],
    }
    return {
        "projection_code": projection["projection_code"],
        "review_disposition": "judgment_shadow_ready",
        "shadow_direction": "positive",
        "review_reason": "四项 readiness 完整。",
        "observations": {
            name: deepcopy(observation)
            for name in (
                "person_task_fit",
                "authority_clarity",
                "feedback_handling",
                "attributable_outcome",
            )
        },
    }


def _g3_judgment_response(worklist: dict, rows: list[dict]) -> dict:
    return {
        "status": "judgment_shadow_reviews_complete",
        "task_code": worklist["task_code"],
        "worklist_sha256": worklist["worklist_sha256"],
        "projection_shadow_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
        "judgment_shadow_policy_version": JUDGMENT_SHADOW_POLICY_VERSION,
        "output_schema_version": JUDGMENT_SHADOW_SCHEMA_VERSION,
        "reviewer": "versioning-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_judgment_accessed": False,
        "formal_acceptance_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": rows,
    }


def test_projection_rerun_rebuilds_delta_and_exactly_reuses_stable_judgment():
    base, worklist, final = _g3_delta_inputs()
    prior = build_projection_shadow_worklist(base)
    delta = apply_rule_evidence_shadow_delta(base, worklist, final)
    rerun = build_incremental_projection_rerun_worklist(prior, delta)
    prior_rows = [_g3_judgment_row(row) for row in prior["projections"]]
    current_rows = []
    for projection in rerun["projections"]:
        reused = next(
            (
                row
                for row in prior_rows
                if row["projection_code"] == projection["projection_code"]
            ),
            None,
        )
        current_rows.append(deepcopy(reused) if reused else _g3_judgment_row(projection))

    result = materialize_incremental_judgment_rerun(
        rerun,
        _g3_judgment_response(rerun, current_rows),
        _g3_judgment_response(prior, prior_rows),
    )

    assert rerun["rebuilt_projection_count"] == 1
    assert rerun["reused_projection_count"] == 1
    assert result["rejudged_projection_count"] == 1
    assert result["reused_judgment_count"] == 1
    assert result["all_projection_readiness_passed"] is True

    reused_row = next(
        row
        for row in current_rows
        if row["projection_code"] in rerun["reused_projection_codes"]
    )
    reused_row["review_reason"] = "mutated"
    with pytest.raises(ValueError, match="逐字段复用"):
        materialize_incremental_judgment_rerun(
            rerun,
            _g3_judgment_response(rerun, current_rows),
            _g3_judgment_response(prior, prior_rows),
        )


def test_synonymous_evidence_only_increments_evidence_version():
    current = _packet(_assertion("A-1", "P-1"))
    observed = _packet(_assertion("A-1", "P-1"), _assertion("A-2", "P-2"))

    decision = apply_episode_revision(current, observed)

    assert decision.packet.episode_id == current.episode_id
    assert decision.packet.semantic_version == current.semantic_version
    assert decision.packet.evidence_version == current.evidence_version + 1
    assert not decision.judgment_invalidation_required


def test_responsibility_change_increments_semantic_version_and_invalidates():
    current = _packet(_assertion("A-1", "P-1"))
    observed = _packet(_assertion("A-2", "P-2", domain="财政"))

    decision = apply_episode_revision(current, observed)

    assert decision.packet.episode_id == current.episode_id
    assert decision.packet.semantic_version == current.semantic_version + 1
    assert decision.judgment_invalidation_required


def test_conflicting_evidence_only_increments_evidence_but_requires_review():
    support = _assertion("A-1", "P-1")
    current = _packet(support)
    dispute = replace(_assertion("A-2", "P-2"), polarity="disputed")
    observed = _packet(support, dispute)

    decision = apply_episode_revision(current, observed)

    assert not decision.semantic_changed
    assert decision.packet.evidence_version == current.evidence_version + 1
    assert decision.packet.episode_status == "needs_evidence_review"
    assert decision.judgment_invalidation_required


def test_outcome_change_is_semantic_even_when_fingerprint_is_unchanged():
    current = _packet(_assertion("A-1", "P-1"))
    observed = replace(current, outcome=("失败",))

    decision = apply_episode_revision(current, observed)

    assert decision.semantic_changed
    assert decision.packet.semantic_version == current.semantic_version + 1
    assert decision.judgment_invalidation_required


def test_completeness_change_is_semantic():
    current = _packet(_assertion("A-1", "P-1"))
    observed = replace(
        current,
        completeness={**current.completeness, "outcome": "conflicted"},
    )

    assert apply_episode_revision(current, observed).semantic_changed


def test_participant_role_status_change_is_semantic():
    current = _packet(_assertion("A-1", "P-1"))
    observed = replace(
        current,
        participants=tuple(
            EpisodeParticipant(item.person_ref, item.role_codes, "resolved")
            for item in current.participants
        ),
    )

    assert apply_episode_revision(current, observed).semantic_changed


def test_supported_fields_or_evidence_status_change_is_evidence_revision():
    current = _packet(_assertion("A-1", "P-1"))
    changed_link = replace(
        current.assertion_links[0],
        supported_fields=("action",),
        evidence_status="accepted",
    )
    observed = replace(current, assertion_links=(changed_link,))

    decision = apply_episode_revision(current, observed)

    assert not decision.semantic_changed
    assert decision.evidence_changed
    assert decision.packet.evidence_version == current.evidence_version + 1


def test_uncertainty_change_is_evidence_revision():
    current = _packet(_assertion("A-1", "P-1"))
    observed = replace(current, uncertainties=("时间待核",))

    decision = apply_episode_revision(current, observed)

    assert decision.evidence_changed
    assert decision.write_required
