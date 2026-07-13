from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from emperor_v4.adapters import (
    WikisourcePageSnapshot,
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
    adapt_source_cache_v2_response,
    read_wikisource_snapshot,
    write_wikisource_snapshot,
)
from emperor_v4.application.reconcile_episode import reconcile_episode_candidates
from emperor_v4.evaluation.assertion_handoff import (
    check_assertion_gap_repair_chain,
    check_assertion_repair_response,
)
from emperor_v4.evaluation.episode_pilot import evaluate_episode_pilot
from emperor_v4.evaluation.reconciliation_review import (
    build_reconciliation_review_package,
)
from emperor_v4.evaluation.oracle_acceptance import (
    build_oracle_assisted_acceptance_package,
)
from emperor_v4.evaluation.blind_holdout import (
    run_blind_holdout,
    run_blind_holdout_with_semantic_review,
    score_blind_holdout,
)
from emperor_v4.evaluation.boundary_score import score_boundary_graph
from emperor_v4.evaluation.boundary_review import build_boundary_review_plan
from emperor_v4.evaluation.graph_holdout import (
    draft_rule_evidence_units_payload,
    score_graph_blind_holdout,
    validate_boundary_review_freeze,
)
from emperor_v4.evaluation.qualification import (
    QualificationThresholds,
    evaluate_candidate_recall_upper_bound,
    evaluate_downstream_development_qualification,
    evaluate_historical_coverage,
    evaluate_rule_coverage,
    evaluate_source_assertion_qualification,
    evaluate_source_development_sets,
)
from emperor_v4.evaluation.relation_review import (
    build_relation_review_plan,
    materialize_relation_review,
    revise_relation_gold_from_audit,
)
from emperor_v4.evaluation.source_gap import check_source_segmentation_repair_response
from emperor_v4.evaluation.source_development import (
    materialize_source_development_from_blind_input,
    materialize_source_development_input,
)
from emperor_v4.contracts.source import text_content_hash
from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_appointment_delegation_shadow,
)
from emperor_v4.application.appointment_delegation_shadow_diff import (
    run_appointment_delegation_shadow_diff,
)
from emperor_v4.application.appointment_delegation_roster_runner import (
    run_appointment_delegation_roster_shadow,
)
from emperor_v4.application.talent_discovery_shadow_runner import (
    run_talent_discovery_shadow,
)
from emperor_v4.application.talent_discovery_roster_runner import (
    run_talent_discovery_roster_shadow,
)
from emperor_v4.application.source_cache_service import (
    SourceCacheIdempotencyConflict,
    ensure_source_cache,
)
from emperor_v4.adapters.source_cache_wikisource import (
    WikisourceSourceMaterialProvider,
)
from emperor_v4.persistence.source_cache import InMemorySourceCacheRepository
from emperor_v4.runtime.source_cache import load_source_cache_request, run_fixture_ensure
from emperor_v4.runtime.source_cache_shadow import run_wikisource_shadow
from emperor_v4.eval import main as eval_main
from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash
from emperor_v4.evaluation.rule_evidence_shadow import (
    RULE_EVIDENCE_SHADOW_POLICY_VERSION,
    RULE_EVIDENCE_SHADOW_SCHEMA_VERSION,
    build_rule_evidence_shadow_worklist,
    materialize_rule_evidence_shadow,
)
from emperor_v4.evaluation.projection_judgment_shadow import (
    JUDGMENT_SHADOW_POLICY_VERSION,
    JUDGMENT_SHADOW_SCHEMA_VERSION,
    PROJECTION_SHADOW_POLICY_VERSION,
    build_projection_shadow_worklist,
    materialize_judgment_shadow_review,
)
from emperor_v4.evaluation.judgment_source_gap import (
    SOURCE_GAP_POLICY_VERSION,
    SOURCE_GAP_SCHEMA_VERSION,
    build_judgment_source_gap_worklist,
    materialize_source_gap_inventory,
)
from emperor_v4.evaluation.source_gap_input_gate import (
    INPUT_GATE_POLICY_VERSION,
    INPUT_GATE_SCHEMA_VERSION,
    build_source_gap_input_gate_worklist,
    materialize_source_gap_input_gate,
)


FIXTURES = Path(__file__).parent / "fixtures" / "episode_pilot_v1"
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
TALENT_DEMO = SCORED_DEMO.parents[1] / "talent_discovery_scored_demo" / "manifest.yml"
TALENT_ROSTER_DEMO = SCORED_DEMO.parents[1] / "talent_discovery_roster_demo"
TALENT_ROSTER_MANIFEST = TALENT_ROSTER_DEMO / "manifest.yml"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_appointment_delegation_scored_shadow_vertical_slice(tmp_path: Path, monkeypatch):
    report = run_appointment_delegation_shadow(SCORED_DEMO)

    assert report["status"] == "appointment_delegation_scored_shadow_ready"
    assert report["summary"]["ruler_count"] == 3
    assert report["summary"]["rule_evidence_unit_count"] == 4
    assert report["summary"]["score_contribution_count"] == 4
    assert report["summary"]["duplicate_consumption_episode_refs"] == []
    assert {row["ruler"] for row in report["ruler_aggregates"]} == {
        "李世民",
        "刘邦",
        "朱元璋",
    }
    assert all(len(row["factor_values"]) == 4 for row in report["judgments"])
    assert all(
        row["duplicate_settlement_check"] == "passed"
        for row in report["score_contributions"]
    )
    assert report["side_effect_audit"] == {
        "offline": True,
        "report_only": True,
        "model_call_count": 0,
        "database_write_count": 0,
        "formal_acceptance_performed": False,
    }
    assert report["lineage"]["source_passages"]
    assert report["lineage"]["assertions"]
    assert report["lineage"]["historical_episodes"]
    unsigned_report = dict(report)
    stored_hash = unsigned_report.pop("report_sha256")
    assert stored_hash == canonical_hash(unsigned_report)

    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-shadow",
            "--manifest",
            str(SCORED_DEMO),
            "--output",
            str(output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_talent_discovery_reuses_scored_shadow_vertical_slice(
    tmp_path: Path, monkeypatch
):
    report = run_talent_discovery_shadow(TALENT_DEMO)

    assert report["status"] == "talent_discovery_scored_shadow_ready"
    assert report["summary"]["rule_evidence_unit_count"] == 4
    assert report["summary"]["score_contribution_count"] == 2
    assert report["summary"]["blocked_unit_count"] == 0
    assert report["summary"]["duplicate_consumption_episode_refs"] == []
    by_person = {row["person"]: row for row in report["judgments"]}
    assert by_person["陈平"]["direction"] == "positive"
    assert by_person["魏徵"]["direction"] == "positive"
    assert by_person["韩信"]["direction"] == "neutral_context"
    assert by_person["蓝玉"]["direction"] == "neutral_context"
    assert {row["person"] for row in report["score_contributions"]} == {
        "陈平",
        "魏徵",
    }
    assert all(
        row["primary_settlement_rule"] == "talent_discovery"
        and row["supporting_only_rules"] == ["appointment_delegation"]
        and row["duplicate_settlement_check"] == "passed"
        for row in report["score_contributions"]
    )

    output = tmp_path / "talent-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "talent-discovery-shadow",
            "--manifest",
            str(TALENT_DEMO),
            "--output",
            str(output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_talent_discovery_reuses_roster_incremental_entry(
    tmp_path: Path, monkeypatch
):
    report = run_talent_discovery_roster_shadow(TALENT_ROSTER_MANIFEST)

    assert report["status"] == "talent_discovery_roster_shadow_complete"
    assert report["stages"]["claim_extractor_adapter"] == {
        "status": "cache_hit",
        "snapshot_count": 6,
        "assertion_count": 91,
    }
    assert report["scored_report"]["summary"]["score_contribution_count"] == 2
    assert report["side_effect_audit"] == {
        "offline": True,
        "service_call_count": 0,
        "model_call_count": 0,
        "database_write_count": 0,
        "formal_acceptance_performed": False,
    }

    output = tmp_path / "talent-roster.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "talent-discovery-roster-shadow",
            "--manifest",
            str(TALENT_ROSTER_MANIFEST),
            "--output",
            str(output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_appointment_delegation_shadow_diff_is_local_and_review_only(
    tmp_path: Path, monkeypatch
):
    report = run_appointment_delegation_shadow_diff(SHADOW_DIFF_REQUEST)

    assert report["status"] == "appointment_delegation_shadow_diff_ready_for_human_review"
    assert report["summary"]["changed_judgment_count"] == 1
    assert report["summary"]["exactly_reused_judgment_count"] == 3
    assert report["summary"]["changed_score_contribution_count"] == 1
    assert report["summary"]["exactly_reused_score_contribution_count"] == 3
    assert report["summary"]["unexpected_invalidation_count"] == 0
    assert report["changed_units"][0]["rule_evidence_unit_ref"] == (
        "REU-LB-HANXIN-QI-AUTHORITY-v1"
    )
    assert report["changed_units"][0]["factor_value_changes"] == {
        "authority_clarity": {"before": "positive", "after": "mixed"}
    }
    assert report["review_gate"] == {
        "comparison_integrity_passed": True,
        "human_factor_review_required": True,
        "human_formula_review_required": True,
        "formal_acceptance_performed": False,
        "formal_scoring_enabled": False,
    }
    assert report["side_effect_audit"]["database_write_count"] == 0

    output = tmp_path / "shadow-diff-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-shadow-diff",
            "--request",
            str(SHADOW_DIFF_REQUEST),
            "--output",
            str(output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_appointment_delegation_roster_shadow_runs_service_adapters_to_score(
    tmp_path: Path, monkeypatch
):
    report = run_appointment_delegation_roster_shadow(ROSTER_MANIFEST)

    assert report["status"] == "appointment_delegation_roster_shadow_complete"
    assert report["cache_mode"] == "ensure"
    assert report["stages"]["source_cache_adapter"]["status"] == "cache_hit"
    assert report["stages"]["claim_extractor_adapter"]["assertion_count"] == 87
    assert report["stages"]["episode_kernel"]["candidate_packet_count"] == 78
    assert report["stages"]["scored_shadow"] == {
        "status": "appointment_delegation_scored_shadow_ready",
        "rebuilt_count": 4,
        "reused_count": 0,
    }
    assert report["scored_report"]["summary"]["ruler_count"] == 3
    assert report["scored_report"]["summary"]["score_contribution_count"] == 4
    assert len(report["delta"]["delta_episode_refs"]) == 6
    assert report["slow_review_job_count"] == 0
    assert report["slow_review_jobs"] == []
    hanxin = next(
        row for row in report["scored_report"]["judgments"] if row["person"] == "韩信"
    )
    assert hanxin["factor_values"]["authority_clarity"] == "positive"
    assert hanxin["direction"] == "positive"
    assert report["side_effect_audit"] == {
        "offline": True,
        "service_call_count": 0,
        "model_call_count": 0,
        "database_write_count": 0,
        "formal_acceptance_performed": False,
    }

    output = tmp_path / "roster-report.json"
    state = tmp_path / "roster-state.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-roster-shadow",
            "--manifest",
            str(ROSTER_MANIFEST),
            "--prior-record",
            str(ROSTER_REPORT),
            "--state",
            str(state),
            "--output",
            str(output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["status"] == "completed"
    assert all(row["status"] == "reused" for row in persisted["people"].values())
    assert all(row["episode_refs"] for row in persisted["people"].values())


def test_g3_shadow_evidence_to_input_gate_vertical_invariants():
    def episode(ref: str, action: str) -> dict:
        return {
            "episode_ref": ref,
            "focal_person_ref": "PER-1",
            "action": action,
            "assertions": [
                {
                    "assertion_ref": f"AST-{ref}",
                    "subject": "皇帝甲",
                    "source_passage_ref": f"SP-{ref}",
                }
            ],
        }

    left = episode("EP-1", "任命")
    right = episode("EP-2", "授权")
    scoring_worklist = {
        "task_code": "G3R-CONSOLIDATED",
        "worklist_sha256": "fixture",
        "tasks": [
            {
                "candidate_code": "C-1",
                "dataset_code": "vertical-fixture",
                "left": left,
                "right": right,
            }
        ],
    }
    scoring_final = {
        "status": "minimum_sufficient_relation_slice_passed",
        "task_code": scoring_worklist["task_code"],
        "minimum_sufficient_gate_passed": True,
        "unresolved_count": 0,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "database_write_count": 0,
        "scoring_relation_proposals": [
            {
                "scoring_relation_proposal_id": "SRP-1",
                "from_episode_version_ref": "EP-1@v1",
                "to_episode_version_ref": "EP-2@v1",
                "relation_family": "authority_change",
                "relation_direction": "expand",
                "scope_match": "same_authority_domain",
                "fine_type": "appointment_to_delegation",
                "fine_type_status": "resolved",
                "lineage": {"candidate_code": "C-1"},
            }
        ],
        "scoring_arc_memberships": [],
    }
    evidence_worklist = build_rule_evidence_shadow_worklist(
        scoring_worklist, scoring_final
    )
    component = evidence_worklist["components"][0]
    evidence_response = {
        "status": "rule_evidence_shadow_reviews_complete",
        "task_code": evidence_worklist["task_code"],
        "worklist_sha256": evidence_worklist["worklist_sha256"],
        "rule_evidence_shadow_policy_version": RULE_EVIDENCE_SHADOW_POLICY_VERSION,
        "output_schema_version": RULE_EVIDENCE_SHADOW_SCHEMA_VERSION,
        "reviewer": "vertical-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_rule_evidence_accessed": False,
        "formal_acceptance_performed": False,
        "judgment_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "component_code": component["component_code"],
                "applicability": "applicable",
                "reason": "任命与授权形成最小评分弧。",
                "ruler_ref": "皇帝甲",
                "person_ref": "PER-1",
                "decision_arc_family": "appointment_to_mandate",
                "episode_member_roles": {
                    "EP-1@v1": "initial_appointment",
                    "EP-2@v1": "delegation",
                },
                "included_link_refs": ["SRP-1"],
                "evidence_assertion_refs": ["AST-EP-1", "AST-EP-2"],
                "question_readiness": {
                    "delegation_quality": "ready",
                    "supervision_quality": "ready",
                    "correction_timeliness": "not_applicable",
                    "net_effect": "evidence_gap",
                },
            }
        ],
    }
    evidence_final = materialize_rule_evidence_shadow(
        evidence_worklist, evidence_response
    )
    assert evidence_final["draft_unit_count"] == 1
    assert evidence_final["duplicate_consumption_episode_refs"] == []

    missing_evidence = json.loads(json.dumps(evidence_response, ensure_ascii=False))
    missing_evidence["results"][0]["evidence_assertion_refs"].pop()
    with pytest.raises(ValueError, match="覆盖每个 Episode"):
        materialize_rule_evidence_shadow(evidence_worklist, missing_evidence)

    projection_worklist = build_projection_shadow_worklist(evidence_final)
    projection = projection_worklist["projections"][0]
    blocked_response = {
        "status": "judgment_shadow_reviews_complete",
        "task_code": projection_worklist["task_code"],
        "worklist_sha256": projection_worklist["worklist_sha256"],
        "projection_shadow_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
        "judgment_shadow_policy_version": JUDGMENT_SHADOW_POLICY_VERSION,
        "output_schema_version": JUDGMENT_SHADOW_SCHEMA_VERSION,
        "reviewer": "vertical-reviewer",
        "reviewed_without_forbidden_inputs": True,
        "gold_accessed": False,
        "old_judgment_accessed": False,
        "formal_acceptance_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "projection_code": projection["projection_code"],
                "review_disposition": "blocked_evidence",
                "shadow_direction": None,
                "review_reason": "净效果证据不足。",
                "observations": {
                    "person_task_fit": {
                        "value": "positive_signal",
                        "reason": "任命适配。",
                        "evidence_assertion_refs": ["AST-EP-1"],
                    },
                    "authority_clarity": {
                        "value": "positive_signal",
                        "reason": "授权明确。",
                        "evidence_assertion_refs": ["AST-EP-2"],
                    },
                    "feedback_handling": {
                        "value": "not_applicable",
                        "reason": "当前弧无纠错动作。",
                        "evidence_assertion_refs": [],
                    },
                    "attributable_outcome": {
                        "value": "evidence_gap",
                        "reason": "缺少结果证据。",
                        "evidence_assertion_refs": [],
                    },
                },
            }
        ],
    }
    readiness_final = materialize_judgment_shadow_review(
        projection_worklist, blocked_response
    )
    assert readiness_final["blocked_evidence_count"] == 1
    assert readiness_final["judgment_shadow_candidate_count"] == 0

    illegal_direction = json.loads(json.dumps(blocked_response, ensure_ascii=False))
    illegal_direction["results"][0]["review_disposition"] = "judgment_shadow_ready"
    illegal_direction["results"][0]["shadow_direction"] = "positive"
    with pytest.raises(ValueError, match="evidence_gap"):
        materialize_judgment_shadow_review(
            projection_worklist, illegal_direction
        )

    readiness_handoff = dict(readiness_final)
    readiness_handoff["status"] = "judgment_shadow_readiness_passed"
    readiness_handoff["shadow_gate_passed"] = True
    gap_worklist = build_judgment_source_gap_worklist(
        projection_worklist, blocked_response, readiness_handoff
    )
    gap = gap_worklist["gap_requests"][0]
    assert gap["open_observation_dimensions"] == ["attributable_outcome"]
    inventory_response = {
        "status": "judgment_source_gap_inventory_complete",
        "task_code": gap_worklist["task_code"],
        "worklist_sha256": gap_worklist["worklist_sha256"],
        "source_gap_policy_version": SOURCE_GAP_POLICY_VERSION,
        "output_schema_version": SOURCE_GAP_SCHEMA_VERSION,
        "reviewer": "vertical-reviewer",
        "inventory_only": True,
        "inventory_sources": ["eval/source-v2/input.json"],
        "gold_accessed": False,
        "old_relation_accessed": False,
        "old_judgment_accessed": False,
        "external_fetch_performed": False,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "gap_code": gap["gap_code"],
                "resolution_kind": "existing_episode_candidate",
                "addressed_observation_dimensions": ["attributable_outcome"],
                "addressed_readiness_questions": ["net_effect"],
                "candidate_episode_refs": ["EP-RESULT@v1"],
                "existing_assertion_refs": ["AST-RESULT"],
                "source_passage_refs": ["SP-RESULT"],
                "proposed_assertion_summary": None,
                "follow_up_gate": "episode_arc_review",
                "reason": "现有结果 Episode 可进入评分弧审查。",
                "stop_condition": "找到直接结果后停止。",
            }
        ],
    }
    inventory_final = materialize_source_gap_inventory(
        gap_worklist, inventory_response
    )
    assert inventory_final["readiness_rerun_authorized"] is False

    forbidden_inventory = json.loads(
        json.dumps(inventory_response, ensure_ascii=False)
    )
    forbidden_inventory["inventory_sources"] = ["eval/historical_gold.json"]
    with pytest.raises(ValueError, match="禁止范围"):
        materialize_source_gap_inventory(gap_worklist, forbidden_inventory)

    gate_worklist = build_source_gap_input_gate_worklist(
        gap_worklist, inventory_response, inventory_final
    )
    gate_response = {
        "status": "source_gap_input_gate_reviews_complete",
        "task_code": gate_worklist["task_code"],
        "worklist_sha256": gate_worklist["worklist_sha256"],
        "input_gate_policy_version": INPUT_GATE_POLICY_VERSION,
        "output_schema_version": INPUT_GATE_SCHEMA_VERSION,
        "reviewer": "vertical-reviewer",
        "proposal_only": True,
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "judgment_performed": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "results": [
            {
                "gap_code": gap["gap_code"],
                "disposition": "accepted_for_shadow_delta",
                "reason": "结果 Episode 与当前任用弧一致。",
                "boundary_disposition": "episode_arc_member",
                "episode_arc_review": {
                    "decision": "same_scoring_arc",
                    "candidate_episode_ref": "EP-RESULT@v1",
                    "evidence_assertion_refs": ["AST-RESULT"],
                    "source_passage_refs": ["SP-RESULT"],
                },
                "source_passage_snapshot": None,
                "candidate_source_passage": None,
                "candidate_assertion": None,
                "proposed_episode_ref": None,
                "member_role": "outcome",
            }
        ],
    }
    gate_final = materialize_source_gap_input_gate(
        gate_worklist, gate_response
    )
    assert gate_final["status"] == "source_gap_input_gate_passed_for_shadow_delta"
    assert gate_final["shadow_delta_authorized"] is True
    assert gate_final["database_write_count"] == gate_final["score_count"] == 0


def test_graph_materializer_accepts_v28_isolated_review_freeze_metadata():
    blind_input = {"dataset_code": "STRICT", "assertions": []}
    rendered = json.dumps(
        blind_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    input_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    review = {
        "status": "boundary_reviews_complete",
        "input_canonical_sha256": input_hash,
        "reviewed_without_historical_gold_or_candidates": True,
    }

    validate_boundary_review_freeze(blind_input, review)

    review["input_canonical_sha256"] = "wrong"
    with pytest.raises(ValueError, match="input hash"):
        validate_boundary_review_freeze(blind_input, review)


def _source_protocol_smoke_payload() -> dict:
    passages = []
    assertions = []
    for index in range(1, 17):
        passage_ref = f"SMOKE-P{index:02d}"
        mode = "atomic_component" if index <= 12 else "context_only"
        raw_text = f"协议场景原文{index}。"
        passages.append(
            {
                "passage_code": passage_ref,
                "document_code": "SMOKE-D1",
                "locator": f"卷一:{(index - 1) * 20}",
                "raw_text": raw_text,
                "context_before": "",
                "context_after": "",
                "content_hash": text_content_hash(raw_text),
                "selection_reason": ["protocol_smoke"],
                "contract_version": "source-cache-contract-v2",
                "content_version": "document-v1",
                "section_id": "卷一",
                "section_heading": "协议冒烟",
                "span_start": (index - 1) * 20,
                "span_end": (index - 1) * 20 + len(raw_text),
                "passage_kind": "atomic" if index <= 12 else "context",
                "linked_passages": [],
                "window_policy_version": "smoke-v2",
            }
        )
        assertions.append(
            {
                "assertion_code": f"SMOKE-A{index:02d}",
                "source_passage_ref": passage_ref,
                "passage_support": {
                    "support_mode": mode,
                    "assertion_semantic_key": f"smoke-{index}",
                    "supported_fields": (
                        ["identity", "action"] if index <= 12 else ["context"]
                    ),
                },
            }
        )
    return {
        "dataset_code": "source_protocol_smoke_v2",
        "scenario_codes": [
            "section_span",
            "linked_lineage",
            "equivalent_evidence",
            "atomic_component",
            "context_only",
            "episode_boundary",
            "historical_relation",
            "rule_score_schema",
        ],
        "source_passages": passages,
        "assertions": assertions,
    }


def test_eight_scenario_source_to_rule_score_protocol_smoke_is_offline_and_typed():
    payload = _source_protocol_smoke_payload()
    source_report = evaluate_source_assertion_qualification(payload)
    assert len(payload["scenario_codes"]) == 8
    assert source_report["status"] == "qualified_for_boundary"

    assertion_refs = [f"SMOKE-A{index:02d}" for index in range(1, 13)]
    episode_groups = []
    assertion_cursor = 0
    for index in range(1, 9):
        width = 2 if index <= 4 else 1
        refs = assertion_refs[assertion_cursor:assertion_cursor + width]
        assertion_cursor += width
        episode_groups.append(
            {
                "local_episode_code": f"EP-{index}",
                "evaluation_context": f"RULER-{(index + 1) // 2}",
                "core_assertion_refs": refs,
                "assertion_links": [
                    {
                        "assertion_ref": ref,
                        "source_passage_ref": ref.replace("A", "P"),
                    }
                    for ref in refs
                ],
                "action": "任命" if index % 2 else "战役结果",
            }
        )
    relations = [
        {
            "relation_id": f"REL-{index}",
            "from_episode": f"EP-{index * 2 - 1}",
            "to_episode": f"EP-{index * 2}",
            "relation_type": "outcome_of",
        }
        for index in range(1, 5)
    ]
    graph = {
        "input_sha256": "protocol-smoke-input",
        "input_assertion_refs": [f"SMOKE-A{index:02d}" for index in range(1, 17)],
        "episode_groups": episode_groups,
        "relations": relations,
        "assertion_dispositions": [
            {
                "assertion_ref": f"SMOKE-A{index:02d}",
                "disposition": "primary" if index <= 12 else "context_only",
            }
            for index in range(1, 17)
        ],
    }
    rule_candidates = draft_rule_evidence_units_payload(graph)
    assert len(rule_candidates["rule_evidence_units"]) == 4

    historical_gold = {
        "status": "frozen",
        "frozen_without_candidate_or_review_access": True,
        "candidate_input_sha256": graph["input_sha256"],
        "gold_episodes": [
            {
                "gold_episode_code": row["local_episode_code"].replace("EP", "GOLD-EP"),
                "evaluation_context": row["evaluation_context"],
                "expected_assertion_refs": row["core_assertion_refs"],
            }
            for row in episode_groups
        ],
        "gold_relations": [
            {
                "gold_relation_code": row["relation_id"].replace("REL", "GOLD-REL"),
                "from_episode": row["from_episode"].replace("EP", "GOLD-EP"),
                "to_episode": row["to_episode"].replace("EP", "GOLD-EP"),
                "relation_type": row["relation_type"],
            }
            for row in relations
        ],
        "gold_assertion_dispositions": graph["assertion_dispositions"],
        "catastrophic_must_not_merge_pairs": [],
    }
    candidate_units = rule_candidates["rule_evidence_units"]
    rule_gold = {
        "status": "frozen",
        "frozen_without_candidate_or_review_access": True,
        "candidate_input_sha256": graph["input_sha256"],
        "gold_rule_evidence_units": [
            {
                "gold_rule_unit_code": f"GOLD-UNIT-{index}",
                "episode_refs": [
                    ref.replace("EP", "GOLD-EP")
                    for ref in unit["episode_refs"]
                ],
                "relation_refs": [
                    ref.replace("REL", "GOLD-REL")
                    for ref in unit["relation_refs"]
                ],
            }
            for index, unit in enumerate(candidate_units, start=1)
        ],
    }
    score = score_graph_blind_holdout(
        graph,
        historical_gold,
        rule_candidates,
        rule_gold,
        {
            "unchanged_rerun_model_calls": 0,
            "changed_unit_affects_other_unit_count": 0,
        },
    )
    assert score["schema_version"] == 1
    assert score["release_gate_passed"] is True
    assert score["g3_authorized"] is True


def test_g26i_and_g26j_open_development_sets_stop_before_boundary():
    root = Path(__file__).parents[1]
    payloads = {
        code: json.loads(
            (root / "eval" / code / "input.json").read_text(encoding="utf-8")
        )
        for code in ("g2_6i_graph_blind_v1", "g2_6j_graph_blind_v1")
    }
    report = evaluate_source_development_sets(payloads)

    assert report["status"] == "development_blocked_before_boundary"
    assert report["decision"] == {
        "can_start_boundary": False,
        "stop_code": "STOP_BEFORE_BOUNDARY",
        "new_blind_holdout_authorized": False,
        "downstream_reviewers_started": False,
    }
    assert set(report["summary"]["blocked_dataset_codes"]) == set(payloads)
    assert all(
        item["stages"]["S1_source_passage"]["source_contract_v2_coverage"] == 0
        for item in report["reports"].values()
    )


def test_qualification_early_stops_sparse_relation_rule_and_recall_inputs():
    thresholds = QualificationThresholds(
        gold_episode_minimum=2,
        gold_relation_minimum=1,
        gold_rule_evidence_unit_minimum=1,
    )
    relation = evaluate_historical_coverage(
        {"gold_episodes": [{}, {}], "gold_relations": []},
        thresholds=thresholds,
    )
    rule = evaluate_rule_coverage(
        {"gold_rule_evidence_units": []},
        thresholds=thresholds,
    )
    recall = evaluate_candidate_recall_upper_bound(
        candidate_episode_count=8,
        gold_episode_count=10,
    )

    assert relation["decision"]["stop_code"] == "COVERAGE_INELIGIBLE_FOR_RELATION"
    assert rule["decision"]["stop_code"] == "COVERAGE_INELIGIBLE_FOR_RULE"
    assert recall["decision"]["stop_code"] == "STOP_BEFORE_RULE_GOLD"


def test_downstream_development_qualification_preserves_sequential_gates():
    thresholds = QualificationThresholds(
        gold_episode_minimum=2,
        gold_relation_minimum=1,
        gold_rule_evidence_unit_minimum=1,
    )
    graph = {
        "dataset_code": "development-fixture",
        "episode_groups": [{"episode": "E1"}, {"episode": "E2"}],
    }
    historical_gold = {
        "gold_episodes": [{"episode": "G1"}, {"episode": "G2"}],
        "gold_relations": [{"relation": "R1"}],
    }
    rule_gold = {"gold_rule_evidence_units": [{"unit": "U1"}]}
    passing_boundary_score = {
        "episode_metrics": {
            "exact_episode_recall": 1.0,
            "exact_candidate_precision": 1.0,
            "passage_lineage_completeness": 1.0,
            "primary_assertion_disposition_coverage": 1.0,
            "catastrophic_wrong_merge_count": 0,
            "cross_ruler_contamination_count": 0,
            "unresolved_assertion_rate": 0.0,
        },
        "relation_metrics": {
            "strict_relation_precision": 1.0,
            "strict_relation_recall": 1.0,
        },
    }

    qualified = evaluate_downstream_development_qualification(
        graph,
        historical_gold,
        rule_gold,
        thresholds=thresholds,
        boundary_score=passing_boundary_score,
    )
    pending = evaluate_downstream_development_qualification(
        graph,
        historical_gold,
        thresholds=thresholds,
        boundary_score=passing_boundary_score,
    )
    stopped = evaluate_downstream_development_qualification(
        {"dataset_code": "development-fixture", "episode_groups": []},
        historical_gold,
        rule_gold,
        thresholds=thresholds,
    )

    assert qualified["status"] == "development_downstream_qualified"
    assert qualified["decision"]["postgresql_g3_authorized"] is False
    assert pending["status"] == "rule_gold_pending"
    assert stopped["status"] == "stopped_before_rule_gold"
    assert stopped["stages"]["S5_rule_evidence_unit_coverage"] is None

    failed_quality = evaluate_downstream_development_qualification(
        graph,
        historical_gold,
        rule_gold,
        thresholds=thresholds,
        boundary_score={
            "episode_metrics": {
                **passing_boundary_score["episode_metrics"],
                "exact_candidate_precision": 0.5,
            }
        },
    )
    assert failed_quality["status"] == "boundary_quality_failed_before_rule_gold"
    assert failed_quality["decision"]["stop_code"] == (
        "BOUNDARY_QUALITY_BELOW_MINIMUM"
    )
    assert failed_quality["stages"]["S5_rule_evidence_unit_coverage"] is None

    failed_relation = evaluate_downstream_development_qualification(
        graph,
        historical_gold,
        rule_gold,
        thresholds=thresholds,
        boundary_score={
            **passing_boundary_score,
            "relation_metrics": {
                "strict_relation_precision": 0.5,
                "strict_relation_recall": 0.5,
            },
        },
    )
    assert failed_relation["status"] == "relation_quality_failed_before_rule_gold"
    assert failed_relation["decision"]["stop_code"] == (
        "RELATION_QUALITY_BELOW_MINIMUM"
    )
    assert failed_relation["stages"]["S5_rule_evidence_unit_coverage"] is None


def test_relation_review_reconciles_cross_boundary_units_without_gold_fields():
    blind_input = {
        "dataset_code": "relation-development",
        "assertions": [
            {
                "assertion_code": f"A{index}",
                "subject": f"P{index}",
                "predicate": predicate,
                "object": responsibility,
                "time_expression": f"T{index}",
                "source_passage_ref": f"SP{index}",
                "qualifiers": {
                    "claim_summary": f"P{index}{predicate}{responsibility}",
                    "responsibility_family": family,
                },
            }
            for index, (predicate, responsibility, family) in enumerate(
                (
                    ("任命", "丞相", "civil_governance"),
                    ("辞任", "丞相", "civil_governance"),
                    ("任命", "统兵", "military_command"),
                ),
                start=1,
            )
        ],
        "source_passages": [
            {
                "passage_code": f"SP{index}",
                "document_code": "D1",
                "section_heading": "本纪",
                "locator": f"L{index}",
                "raw_text": f"原文{index}",
            }
            for index in range(1, 4)
        ],
        "collection_provenance": {"gold_accessed": False},
    }
    graph = {
        "dataset_code": "relation-development",
        "input_sha256": hashlib.sha256(
            json.dumps(
                blind_input,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "status": "blind_episode_graph_proposed",
        "episode_groups": [
            {
                "local_episode_code": "E1",
                "evaluation_context": "R1",
                "focal_person_ref": "P1",
                "focal_roles": ["office_holder"],
                "responsibility_family": "civil_governance",
                "core_assertion_refs": ["A1"],
                "assertion_links": [
                    {"assertion_ref": "A1", "source_passage_ref": "SP1"}
                ],
                "action": "任命",
                "responsibility": "丞相",
                "semantic_fingerprint": "F1",
            },
            {
                "local_episode_code": "E2",
                "evaluation_context": "R1",
                "focal_person_ref": "P1",
                "focal_roles": ["office_holder"],
                "responsibility_family": "civil_governance",
                "core_assertion_refs": ["A2"],
                "assertion_links": [
                    {"assertion_ref": "A2", "source_passage_ref": "SP2"}
                ],
                "action": "辞任",
                "responsibility": "丞相",
                "semantic_fingerprint": "F2",
            },
            {
                "local_episode_code": "E3",
                "evaluation_context": "R2",
                "focal_person_ref": "P2",
                "focal_roles": ["commander"],
                "responsibility_family": "military_command",
                "core_assertion_refs": ["A3"],
                "assertion_links": [
                    {"assertion_ref": "A3", "source_passage_ref": "SP3"}
                ],
                "action": "任命",
                "responsibility": "统兵",
                "semantic_fingerprint": "F3",
            },
        ],
        "assertion_dispositions": [
            {"assertion_ref": "A1", "disposition": "core_of_episode"},
            {"assertion_ref": "A2", "disposition": "core_of_episode"},
            {"assertion_ref": "A3", "disposition": "core_of_episode"},
        ],
        "relations": [],
        "safety": {"database_write_count": 0},
    }
    plan = build_relation_review_plan(graph, blind_input)
    assert plan["review_evidence_sha256"]
    assert plan["relation_semantic_policy"]["type_precedence"][0][
        "relation_type"
    ] == "revokes"
    assert any(
        summary["evidence"]["source_passages"][0]["raw_text"] == "原文1"
        for unit in plan["review_units"]
        for summary in unit["episode_summaries"]
        if summary["episode_ref"] == "E1"
    )
    first = next(unit for unit in plan["review_units"] if unit["pair_count"] == 1)
    second = next(unit for unit in plan["review_units"] if unit["pair_count"] == 0)
    review = {
        "status": "relation_reviews_complete",
        "candidate_episode_basis_sha256": plan["candidate_episode_basis_sha256"],
        "review_evidence_sha256": plan["review_evidence_sha256"],
        "relation_policy_version": plan["relation_policy_version"],
        "output_schema_version": plan["output_schema_version"],
        "reviewed_without_historical_gold_or_score": True,
        "dataset_code": "relation-development",
        "review_unit_count": 2,
        "pair_count": 1,
        "related_pair_count": 1,
        "unresolved_pair_count": 0,
        "review_results": [
            {
                "review_unit_ref": first["review_unit_code"],
                "cache_key": first["cache_key"],
                "relation_policy_version": plan["relation_policy_version"],
                "output_schema_version": plan["output_schema_version"],
                "relations": [
                    {
                        "from_episode_ref": "E1",
                        "to_episode_ref": "E2",
                        "relation_type": "revokes",
                        "evidence_assertion_refs": ["A1", "A2"],
                        "confidence": 0.9,
                    }
                ],
                "pair_dispositions": [
                    {
                        "left_episode_ref": "E1",
                        "right_episode_ref": "E2",
                        "decision": "related",
                        "relation_type": "revokes",
                        "reason": "任命后辞任",
                    }
                ],
            },
            {
                "review_unit_ref": second["review_unit_code"],
                "cache_key": second["cache_key"],
                "relation_policy_version": plan["relation_policy_version"],
                "output_schema_version": plan["output_schema_version"],
                "relations": [],
                "pair_dispositions": [],
            },
        ],
    }

    result = materialize_relation_review(graph, review, blind_input)

    assert result["status"] == "relation_graph_review_materialized"
    assert result["relations"][0]["relation_type"] == "revokes"
    assert result["formal_episode_relations"][0]["evidence_links"] == [
        {
            "assertion_ref": "A1",
            "source_passage_ref": "SP1",
            "evidence_status": "draft",
        },
        {
            "assertion_ref": "A2",
            "source_passage_ref": "SP2",
            "evidence_status": "draft",
        },
    ]
    assert result["safety"]["gold_fields_detected"] == 0

    pair_dispositions = review["review_results"][0]["pair_dispositions"]
    review["review_results"][0]["pair_dispositions"] = []
    with pytest.raises(ValueError, match="完整且唯一处置"):
        materialize_relation_review(graph, review, blind_input)

    review["review_results"][0]["relations"] = []
    review["related_pair_count"] = 0
    review["unresolved_pair_count"] = 1
    review["review_results"][0]["pair_dispositions"] = [
        {
            **pair_dispositions[0],
            "decision": "unresolved",
            "relation_type": None,
        }
    ]
    with pytest.raises(ValueError, match="unresolved pair"):
        materialize_relation_review(graph, review, blind_input)

    blind_input["collection_provenance"]["gold_accessed"] = True
    with pytest.raises(ValueError, match="禁止字段"):
        build_relation_review_plan(graph, blind_input)


def test_relation_gold_revision_requires_complete_isolated_audit():
    historical_gold = {
        "dataset_code": "relation-development",
        "status": "frozen",
        "gold_relation_count": 2,
        "gold_episodes": [
            {"gold_episode_code": "G1", "core_assertion_refs": ["A1"]},
            {"gold_episode_code": "G2", "core_assertion_refs": ["A2"]},
            {"gold_episode_code": "G3", "core_assertion_refs": ["A3"]},
        ],
        "gold_relations": [
            {
                "gold_relation_code": "R1",
                "from_episode": "G1",
                "to_episode": "G2",
                "relation_type": "continues",
            },
            {
                "gold_relation_code": "R2",
                "from_episode": "G2",
                "to_episode": "G3",
                "relation_type": "causal_followup",
            },
        ],
    }
    audit = {
        "status": "relation_gold_ontology_audit_complete",
        "relation_policy_version": "episode-relation-policy-v2",
        "reviewed_without_candidate_or_score": True,
        "dataset_code": "relation-development",
        "relation_count": 2,
        "decision_counts": {
            "supported_as_declared": 0,
            "supported_with_different_type": 1,
            "unsupported_direct_relation": 1,
            "insufficient_endpoint_evidence": 0,
        },
        "audit_results": [
            {
                "gold_relation_code": "R1",
                "from_episode": "G1",
                "to_episode": "G2",
                "declared_relation_type": "continues",
                "audit_decision": "supported_with_different_type",
                "recommended_relation_type": "renews_authority",
                "evidence_assertion_refs": ["A1", "A2"],
                "reason": "同一责任主体获得后续实质续权。",
            },
            {
                "gold_relation_code": "R2",
                "from_episode": "G2",
                "to_episode": "G3",
                "declared_relation_type": "causal_followup",
                "audit_decision": "unsupported_direct_relation",
                "recommended_relation_type": None,
                "evidence_assertion_refs": ["A2", "A3"],
                "reason": "只有时间相邻，没有直接关系证据。",
            },
        ],
    }

    revised = revise_relation_gold_from_audit(historical_gold, audit)

    assert revised["status"] == "frozen_relation_gold_v2_open_development"
    assert revised["gold_relation_count"] == 1
    assert revised["gold_relations"][0]["relation_type"] == "renews_authority"
    assert revised["relation_gold_revision"]["formal_blind_qualification"] is False

    audit["candidate_relation_code"] = "LEAK"
    with pytest.raises(ValueError, match="candidate/score 泄漏"):
        revise_relation_gold_from_audit(historical_gold, audit)


def test_frozen_v3_outputs_form_auditable_episode_candidate_slice_offline():
    source = adapt_source_cache_snapshot(_fixture("source-cache-response.json"))
    assertions = adapt_claim_extractor_snapshot(_fixture("claim-extractor-response.json"))
    packets = reconcile_episode_candidates(assertions)

    source_slice_ids = {passage.passage_cache_id for passage in source.passages}
    assertion_codes = {assertion.assertion_code for assertion in assertions}
    linked_codes = {
        link.assertion_ref for packet in packets for link in packet.assertion_links
    }

    assert len(assertions) == 46
    assert packets
    assert linked_codes == assertion_codes
    assert all(packet.lineage == {"origin": "created"} for packet in packets)
    assert all(packet.provenance["builder"] == "deterministic_episode_kernel_v1" for packet in packets)
    assert all(
        assertion.source_attribution["source_slice_ref"] in source_slice_ids
        for assertion in assertions
    )


def test_shadow_repairs_improve_assertion_support_without_claiming_episode_recall():
    root = Path(__file__).parents[1]
    source_repair = check_source_segmentation_repair_response(
        root / "eval" / "episode_pilot_v1_source_segmentation_repair.yml",
        root / "eval" / "episode_pilot_v1_source_segmentation_repair_execution.yml",
        FIXTURES / "source-cache-segmentation-repair-response.json",
    )
    assertion_repair = check_assertion_repair_response(
        root / "eval" / "episode_pilot_v1_assertion_repair.yml",
        root / "eval" / "episode_pilot_v1_assertion_repair_execution.yml",
        FIXTURES / "claim-extractor-repair-response.json",
    )
    gap_repair = check_assertion_gap_repair_chain(
        (
            root / "eval" / "episode_pilot_v1_assertion_gap_repair.yml",
            root / "eval" / "episode_pilot_v1_assertion_gap_repair2.yml",
        ),
        (
            root / "eval" / "episode_pilot_v1_assertion_gap_repair_execution.yml",
            root / "eval" / "episode_pilot_v1_assertion_gap_repair2_execution.yml",
        ),
        (
            FIXTURES / "claim-extractor-gap-repair-response.json",
            FIXTURES / "claim-extractor-gap-repair2-response.json",
        ),
    )
    report = evaluate_episode_pilot(
        root / "eval" / "episode_pilot_v1.yml",
        FIXTURES,
        root / "eval" / "episode_pilot_v1_linkage.yml",
        FIXTURES / "source-cache-supplement-response.json",
        FIXTURES / "claim-extractor-supplement-response.json",
        FIXTURES / "source-cache-segmentation-repair-response.json",
        FIXTURES / "claim-extractor-repair-response.json",
        FIXTURES / "source-cache-segmentation-gap-repair-response.json",
        FIXTURES / "claim-extractor-gap-repair-response.json",
        FIXTURES / "claim-extractor-gap-repair2-response.json",
        root / "eval" / "episode_pilot_v1_assertion_gold_coverage.yml",
    )
    review_package = build_reconciliation_review_package(
        root / "eval" / "episode_pilot_v1.yml",
        root / "eval" / "episode_pilot_v1_review.yml",
        report,
    )
    oracle_acceptance = build_oracle_assisted_acceptance_package(
        root / "eval" / "episode_pilot_v1.yml",
        root / "eval" / "episode_pilot_v1_reconciliation_review_package.json",
        root / "eval" / "episode_pilot_v1_identity_resolution.yml",
        root / "eval" / "episode_pilot_v1_oracle_assisted_decisions.yml",
    )

    assert source_repair["status"] == "passed"
    assert source_repair["network_fetch_count"] == 0
    assert assertion_repair["status"] == "passed"
    assert assertion_repair["used_passage_count"] == assertion_repair["input_passage_count"]
    assert gap_repair["status"] == "passed_with_recorded_refinement"
    assert gap_repair["used_passage_count"] == gap_repair["input_passage_count"] == 8
    assert gap_repair["model_call_count"] == 4
    assert report["assertion_boundary_coverage"]["full_boundary_support_count"] == 15
    assert report["assertion_boundary_coverage"]["partial_boundary_support_count"] == 0
    assert report["assertion_boundary_coverage"]["no_boundary_support_count"] == 0
    assert report["lineage_assisted_reconciliation"]["candidate_packet_count"] == 15
    assert report["lineage_assisted_reconciliation"]["supported_boundary_packet_count"] == 15
    assert report["lineage_assisted_reconciliation"]["unassigned_new_assertion_count"] == 0
    assert report["lineage_assisted_reconciliation"]["all_packets_proposed"] is True
    assert len(report["lineage_assisted_reconciliation"]["packet_assessments"]) == 15
    assert report["lineage_assisted_reconciliation"][
        "human_review_gate_ready_packet_count"
    ] == 15
    assert report["lineage_assisted_reconciliation"][
        "complete_expected_participant_packet_count"
    ] == 15
    assert report["stage_failure_attribution"] == {
        "status": "review_ready",
        "source_discovery_missing_document_count": 0,
        "source_segmentation_confirmed_miss_count": 0,
        "source_segmentation_gap_repaired_count": 1,
        "assertion_extractor_wrong_event_selection_count": 0,
        "identity_participant_underextraction_count": 0,
        "assertion_chain_incomplete_count": 0,
        "reconciler_unassigned_new_assertion_count": 0,
        "projection_gate_pending_packet_count": 0,
        "diagnostic_notes": [
            "房玄龄错误选择已由定向补抽修复；原 passage 无需重新切片。",
            "魏徵初授窗口已从 V3 retained page cache 补切，网络请求为零。",
            "参与者缺口与断言链缺口允许重叠，不能相加作为失败总数。",
            "所有 packet 仍为 proposed，规则投影尚未执行。",
        ],
    }
    assert report["episode_recall"] == {
        "status": "not_computable_oracle_contaminated",
        "value": None,
        "reason": "当前 candidate grouping 与 acceptance 使用 Gold boundary/linkage。",
    }
    assert report["accepted_episode_precision"]["value"] is None
    assert report["merge_split"]["status"] == "not_measured_requires_blind_holdout"
    assert report["oracle_contaminated_linkage_diagnostic"][
        "full_match_episode_count"
    ] == 0
    assert review_package["status"] == "pending_human_review"
    assert review_package["summary"] == {
        "frozen_episode_count": 15,
        "packet_count": 15,
        "full_assertion_support_count": 15,
        "passage_lineage_complete_count": 15,
        "identity_review_required_count": 15,
        "unexpected_participant_candidate_packet_count": 7,
        "evidence_review_required_count": 2,
        "acceptance_ready_count": 0,
        "human_decision_pending_count": 15,
    }
    assert all(item["current_status"] == "proposed" for item in review_package["items"])
    assert all(item["human_decision"] == "pending" for item in review_package["items"])
    assert oracle_acceptance["status"] == "conditional_pass"
    assert oracle_acceptance["g2_status"] == "reopen_required"
    assert oracle_acceptance["summary"] == {
        "gold_episode_count": 15,
        "oracle_assisted_candidate_packet_count": 15,
        "oracle_uncertainty_candidate_count": 2,
        "accuracy_metrics_status": "not_computable_oracle_contaminated",
        "semantic_fingerprint_collision_count": 0,
        "canonical_identity_count": 17,
        "candidate_resolved_participant_count": 37,
        "draft_assertion_link_count": 49,
        "missing_passage_lineage_count": 0,
        "production_write_count": 0,
        "rule_projection_count": 0,
    }
    assert all(oracle_acceptance["constructability_checks"].values())
    assert all(
        participant["role_status"] == "candidate_resolved"
        for packet in oracle_acceptance["packets"]
        for participant in packet["participants"]
    )
    assert all(
        link["evidence_status"] == "draft"
        for packet in oracle_acceptance["packets"]
        for link in packet["assertion_links"]
    )


def test_blind_holdout_run_is_gold_isolated_and_scored_only_afterward():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    run = run_blind_holdout(blind_input)

    assert run["status"] == "blind_candidates_proposed"
    assert run["candidate_packet_count"] == 3
    assert run["input_source_passage_count"] == 4
    assert run["accuracy_metrics"]["autonomous_boundary_recall"] is None
    assert run["safety"] == {
        "gold_fields_detected": 0,
        "model_call_count": 0,
        "network_request_count": 0,
        "database_write_count": 0,
    }

    gold_episodes = [
        {
            "gold_episode_code": f"SMOKE-{index}",
            "evaluation_context": packet["evaluation_context"],
            "expected_assertion_refs": [
                link["assertion_ref"] for link in packet["assertion_links"]
            ],
            "required_source_passage_refs": [
                link["source_passage_ref"] for link in packet["assertion_links"]
            ],
        }
        for index, packet in enumerate(run["packets"], start=1)
    ]
    score = score_blind_holdout(
        run,
        {
            "status": "frozen",
            "frozen_without_candidate_access": True,
            "candidate_input_sha256": run["input_sha256"],
            "gold_episodes": gold_episodes,
            "catastrophic_must_not_merge_pairs": [],
        },
    )

    assert score["metrics"]["autonomous_boundary_recall"] == 1.0
    assert score["metrics"]["candidate_precision"] == 1.0
    assert score["metrics"]["pairwise_same_episode_precision"] == 1.0
    assert score["metrics"]["pairwise_same_episode_recall"] == 1.0
    assert score["metrics"]["safe_fragment_count"] == 0
    assert score["metrics"]["catastrophic_wrong_merge_count"] == 0
    assert score["accepted_metrics"]["accepted_recall"] is None


def test_blind_scorer_rejects_candidate_decision_based_gold():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    run = run_blind_holdout(blind_input)

    with pytest.raises(ValueError, match="candidate_decisions"):
        score_blind_holdout(
            run,
            {
                "status": "frozen",
                "frozen_without_candidate_access": True,
                "candidate_input_sha256": run["input_sha256"],
                "candidate_decisions": {},
                "gold_episodes": [{"gold_episode_code": "GOLD-1"}],
            },
        )

def test_blind_scorer_measures_wrong_merge_and_catastrophic_pair_from_frozen_gold():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    run = run_blind_holdout(blind_input)
    merged_packet = next(
        packet for packet in run["packets"] if len(packet["assertion_links"]) == 2
    )
    refs = [link["assertion_ref"] for link in merged_packet["assertion_links"]]
    gold = {
        "status": "frozen",
        "frozen_without_candidate_access": True,
        "candidate_input_sha256": run["input_sha256"],
        "gold_episodes": [
            {
                "gold_episode_code": "GOLD-A",
                "evaluation_context": merged_packet["evaluation_context"],
                "expected_assertion_refs": [refs[0]],
            },
            {
                "gold_episode_code": "GOLD-B",
                "evaluation_context": merged_packet["evaluation_context"],
                "expected_assertion_refs": [refs[1]],
            },
        ],
        "catastrophic_must_not_merge_pairs": [["GOLD-A", "GOLD-B"]],
    }

    score = score_blind_holdout(run, gold)

    assert score["metrics"]["wrong_merge_count"] == 1
    assert score["metrics"]["catastrophic_wrong_merge_count"] == 1
    assert score["metrics"]["autonomous_boundary_recall"] == 0.0


def test_blind_scorer_attributes_source_only_gold_miss_to_assertion_layer():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    run = run_blind_holdout(blind_input)
    first_packet = run["packets"][0]
    gold = {
        "status": "frozen",
        "frozen_without_candidate_access": True,
        "candidate_input_sha256": run["input_sha256"],
        "gold_episodes": [
            {
                "gold_episode_code": "GOLD-MATCH",
                "evaluation_context": first_packet["evaluation_context"],
                "expected_assertion_refs": [
                    link["assertion_ref"] for link in first_packet["assertion_links"]
                ],
            },
            {
                "gold_episode_code": "GOLD-SOURCE-ONLY",
                "evaluation_context": "李治",
                "expected_assertion_refs": [],
                "required_source_passage_refs": ["BLIND-P1"],
            },
        ],
        "catastrophic_must_not_merge_pairs": [],
    }

    score = score_blind_holdout(run, gold)

    assert score["metrics"]["autonomous_boundary_recall"] == 0.5
    assert score["diagnostics"]["assertion_layer_miss_gold_episode_codes"] == [
        "GOLD-SOURCE-ONLY"
    ]


def test_blind_holdout_rejects_missing_source_passage_lineage():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    blind_input["source_passages"] = blind_input["source_passages"][:-1]

    with pytest.raises(ValueError, match="passage lineage 不存在"):
        run_blind_holdout(blind_input)


def test_semantic_review_is_gold_isolated_cached_and_review_id_neutral():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    input_hash = run_blind_holdout(blind_input)["input_sha256"]

    def review(prefix: str) -> dict:
        return {
            "schema_version": 1,
            "review_code": "SMOKE-REVIEW",
            "status": "completed_before_gold_opened",
            "blind_input_sha256": input_hash,
            "reviewed_without_gold_access": True,
            "reviewed_by": "test-reviewer",
            "model_call_count": 1,
            "cache_key": "smoke-cache-v1",
            "review_groups": [
                {
                    "review_group_code": f"{prefix}-MERGE",
                    "recommendation": "merge",
                    "assertion_refs": ["BLIND-A1", "BLIND-A2"],
                    "confidence": 0.8,
                    "merge_split_rationale": "同一授权与结果链",
                    "identity_blockers": ["待核同名人物"],
                    "evidence_conflicts": ["结果措辞冲突"],
                },
                {
                    "review_group_code": f"{prefix}-A3",
                    "recommendation": "keep_separate",
                    "assertion_refs": ["BLIND-A3"],
                },
                {
                    "review_group_code": f"{prefix}-A4",
                    "recommendation": "keep_separate",
                    "assertion_refs": ["BLIND-A4"],
                },
            ],
            "unassigned_assertion_refs": [],
        }

    first = run_blind_holdout_with_semantic_review(blind_input, review("FIRST"))
    renamed = run_blind_holdout_with_semantic_review(blind_input, review("RENAMED"))
    cached = run_blind_holdout_with_semantic_review(
        blind_input, review("FIRST"), review_cache_hit=True
    )

    assert first["candidate_packet_count"] == 3
    assert first["safety"]["model_call_count"] == 1
    assert cached["safety"]["model_call_count"] == 0
    assert first["semantic_review"]["cache_hit"] is False
    assert cached["semantic_review"]["cache_hit"] is True
    reviewed_packet = next(
        packet
        for packet in first["packets"]
        if len(packet["assertion_links"]) == 2
    )
    assert reviewed_packet["merge_split_rationale"]["review_decisions"][0][
        "rationale"
    ] == "同一授权与结果链"
    assert reviewed_packet["identity_blockers"] == ["待核同名人物"]
    assert reviewed_packet["conflicts"] == ["结果措辞冲突"]
    assert len(first["human_review_worklist"]) == 1
    assert {
        packet["semantic_fingerprint"] for packet in first["packets"]
    } == {
        packet["semantic_fingerprint"] for packet in renamed["packets"]
    }


def test_semantic_review_rejects_gold_fields():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    review = {
        "status": "completed_before_gold_opened",
        "reviewed_without_gold_access": True,
        "blind_input_sha256": run_blind_holdout(blind_input)["input_sha256"],
        "gold_boundary": "forbidden",
    }

    with pytest.raises(ValueError, match="Gold/oracle"):
        run_blind_holdout_with_semantic_review(blind_input, review)


def test_boundary_scorer_distinguishes_safe_fragments_from_wrong_merge():
    candidate = {
        "episode_groups": [
            {"local_episode_code": "C1", "core_assertion_refs": ["A1", "A2"]},
            {"local_episode_code": "C2", "core_assertion_refs": ["A3"]},
            {"local_episode_code": "C3", "core_assertion_refs": ["A4"]},
        ],
        "relations": [
            {
                "from_episode": "C2",
                "to_episode": "C3",
                "relation_type": "revokes",
            }
        ],
    }
    gold = {
        "gold_episodes": [
            {"gold_episode_code": "G1", "expected_assertion_refs": ["A1", "A2"]},
            {"gold_episode_code": "G2", "expected_assertion_refs": ["A3", "A4"]},
        ],
        "gold_relations": [],
        "catastrophic_must_not_merge_pairs": [["G1", "G2"]],
    }

    score = score_boundary_graph(candidate, gold)

    assert score["episode_metrics"]["exact_episode_recall"] == 0.5
    assert score["episode_metrics"]["exact_candidate_precision"] == pytest.approx(
        1 / 3
    )
    assert score["episode_metrics"]["pairwise_same_episode_precision"] == 1.0
    assert score["episode_metrics"]["pairwise_same_episode_recall"] == 0.5
    assert score["episode_metrics"]["safe_fragment_count"] == 2
    assert score["episode_metrics"]["wrong_merge_count"] == 0


def test_boundary_scorer_measures_relation_graph_separately():
    episodes = [
        {"local_episode_code": "E1", "core_assertion_refs": ["A1"]},
        {"local_episode_code": "E2", "core_assertion_refs": ["A2"]},
    ]
    gold_episodes = [
        {"gold_episode_code": "G1", "expected_assertion_refs": ["A1"]},
        {"gold_episode_code": "G2", "expected_assertion_refs": ["A2"]},
    ]
    candidate = {
        "episode_groups": episodes,
        "relations": [
            {
                "from_episode": "E1",
                "to_episode": "E2",
                "relation_type": "causal_followup",
            }
        ],
    }
    gold = {
        "gold_episodes": gold_episodes,
        "gold_relations": [
            {
                "from_episode": "G1",
                "to_episode": "G2",
                "relation_type": "causal_followup",
            }
        ],
    }

    score = score_boundary_graph(candidate, gold)

    assert score["relation_metrics"]["strict_relation_precision"] == 1.0
    assert score["relation_metrics"]["strict_relation_recall"] == 1.0
    assert score["relation_metrics"]["causal_responsibility_preservation"] == 1.0


def test_boundary_scorer_reports_gate_lineage_disposition_and_cross_ruler_metrics():
    candidate = {
        "episode_groups": [
            {
                "local_episode_code": "C1",
                "evaluation_context": "per-ruler",
                "core_assertion_refs": ["A1"],
                "assertion_links": [
                    {"assertion_ref": "A1", "source_passage_ref": "P1"}
                ],
            },
            {
                "local_episode_code": "C2",
                "evaluation_context": "per-ruler",
                "core_assertion_refs": ["A2"],
                "assertion_links": [],
            },
        ],
        "input_assertion_refs": ["A1", "A2", "A3"],
        "assertion_dispositions": [
            {"assertion_ref": "A1", "disposition": "core_of_episode"},
            {"assertion_ref": "A2", "disposition": "core_of_episode"},
            {"assertion_ref": "A3", "disposition": "unresolved"},
        ],
        "relations": [],
    }
    gold = {
        "gold_episodes": [
            {
                "gold_episode_code": "G1",
                "evaluation_context": "PER-RULER",
                "expected_assertion_refs": ["A1"],
            },
            {
                "gold_episode_code": "G2",
                "evaluation_context": "PER-OTHER-RULER",
                "expected_assertion_refs": ["A2"],
            },
        ],
        "gold_relations": [],
    }

    score = score_boundary_graph(candidate, gold)

    assert score["episode_metrics"]["cross_ruler_contamination_count"] == 1
    assert score["episode_metrics"]["passage_lineage_completeness"] == 0.5
    assert score["episode_metrics"][
        "primary_assertion_disposition_coverage"
    ] == 1.0
    assert score["episode_metrics"]["unresolved_assertion_rate"] == pytest.approx(
        1 / 3
    )


def test_boundary_scorer_keeps_strict_and_endpoint_aligned_relation_metrics():
    candidate = {
        "episode_groups": [
            {"local_episode_code": "C1", "core_assertion_refs": ["A1"]},
            {"local_episode_code": "C2", "core_assertion_refs": ["A3"]},
        ],
        "relations": [
            {
                "from_episode": "C1",
                "to_episode": "C2",
                "relation_type": "causal_followup",
            }
        ],
    }
    gold = {
        "gold_episodes": [
            {"gold_episode_code": "G1", "expected_assertion_refs": ["A1", "A2"]},
            {"gold_episode_code": "G2", "expected_assertion_refs": ["A3", "A4"]},
        ],
        "gold_relations": [
            {
                "from_episode": "G1",
                "to_episode": "G2",
                "relation_type": "causal_followup",
            }
        ],
    }

    score = score_boundary_graph(candidate, gold)

    assert score["relation_metrics"]["strict_relation_precision"] == 0.0
    assert score["relation_metrics"]["strict_relation_recall"] == 0.0
    assert score["relation_metrics"]["endpoint_aligned_relation_precision"] == 1.0
    assert score["relation_metrics"]["endpoint_aligned_relation_recall"] == 1.0


def test_missing_location_is_non_blocking_for_appointment_episode():
    blind_input = json.loads(
        (Path(__file__).parent / "fixtures" / "blind_contract_smoke.json").read_text(
            encoding="utf-8"
        )
    )
    for assertion in blind_input["assertions"]:
        assertion["ambiguity_flags"] = ["missing_location_expression"]
        assertion["location_expression"] = None

    run = run_blind_holdout(blind_input)

    assert all(
        issue["severity"] == "informational"
        for packet in run["packets"]
        for issue in packet["ambiguity_issues"]
    )
    assert all(not packet["human_review_required"] for packet in run["packets"])


def test_rule_evidence_draft_uses_connected_delegation_graph_only_once():
    graph = {
        "input_sha256": "HASH",
        "episode_groups": [
            {
                "local_episode_code": "E1",
                "evaluation_context": "PER-RULER",
                "action": "任命",
            },
            {
                "local_episode_code": "E2",
                "evaluation_context": "PER-RULER",
                "action": "战役",
            },
            {
                "local_episode_code": "E3",
                "evaluation_context": "PER-RULER",
                "action": "其他",
            },
        ],
        "relations": [
            {
                "relation_id": "R1",
                "from_episode": "E1",
                "to_episode": "E2",
                "relation_type": "outcome_of",
            }
        ],
    }

    result = draft_rule_evidence_units_payload(graph)

    assert len(result["rule_evidence_units"]) == 1
    assert set(result["rule_evidence_units"][0]["episode_refs"]) == {"E1", "E2"}
    assert result["duplicate_consumption_episode_refs"] == []


def test_rule_evidence_draft_does_not_join_career_only_promotion_relation():
    graph = {
        "input_sha256": "HASH",
        "episode_groups": [
            {
                "local_episode_code": "E1",
                "evaluation_context": "PER-RULER",
                "action": "任命",
            },
            {
                "local_episode_code": "E2",
                "evaluation_context": "PER-RULER",
                "action": "任命",
            },
        ],
        "relations": [
            {
                "relation_id": "R1",
                "from_episode": "E1",
                "to_episode": "E2",
                "relation_type": "promotion_after",
            }
        ],
    }

    result = draft_rule_evidence_units_payload(graph)

    assert len(result["rule_evidence_units"]) == 2
    assert all(len(item["episode_refs"]) == 1 for item in result["rule_evidence_units"])


def test_graph_blind_score_gates_episode_relation_rule_and_runtime_together():
    episode_groups = [
        {
            "local_episode_code": "E1",
            "evaluation_context": "PER-RULER",
            "core_assertion_refs": ["A1", "A2"],
            "assertion_links": [
                {"assertion_ref": "A1", "source_passage_ref": "P1"},
                {"assertion_ref": "A2", "source_passage_ref": "P2"},
            ],
        },
        {
            "local_episode_code": "E2",
            "evaluation_context": "PER-RULER",
            "core_assertion_refs": ["A3", "A4"],
            "assertion_links": [
                {"assertion_ref": "A3", "source_passage_ref": "P3"},
                {"assertion_ref": "A4", "source_passage_ref": "P4"},
            ],
        },
    ]
    graph = {
        "input_sha256": "HASH",
        "episode_groups": episode_groups,
        "input_assertion_refs": ["A1", "A2", "A3", "A4"],
        "assertion_dispositions": [
            {"assertion_ref": ref, "disposition": "core_of_episode"}
            for ref in ("A1", "A2", "A3", "A4")
        ],
        "relations": [
            {
                "relation_id": "R1",
                "from_episode": "E1",
                "to_episode": "E2",
                "relation_type": "outcome_of",
            }
        ],
    }
    historical_gold = {
        "status": "frozen",
        "candidate_input_sha256": "HASH",
        "frozen_without_candidate_or_review_access": True,
        "gold_episodes": [
            {
                "gold_episode_code": "G1",
                "evaluation_context": "PER-RULER",
                "expected_assertion_refs": ["A1", "A2"],
            },
            {
                "gold_episode_code": "G2",
                "evaluation_context": "PER-RULER",
                "expected_assertion_refs": ["A3", "A4"],
            },
        ],
        "gold_relations": [
            {
                "gold_relation_code": "GR1",
                "from_episode": "G1",
                "to_episode": "G2",
                "relation_type": "outcome_of",
            }
        ],
        "gold_assertion_dispositions": [
            {"assertion_ref": ref, "disposition": "core_of_episode"}
            for ref in ("A1", "A2", "A3", "A4")
        ],
        "catastrophic_must_not_merge_pairs": [],
    }
    rule_candidates = {
        "rule_evidence_units": [
            {"unit_code": "U1", "episode_refs": ["E1", "E2"], "relation_refs": ["R1"]}
        ],
        "duplicate_consumption_episode_refs": [],
    }
    rule_gold = {
        "status": "frozen",
        "candidate_input_sha256": "HASH",
        "frozen_without_candidate_or_review_access": True,
        "gold_rule_evidence_units": [
            {"gold_rule_unit_code": "GU1", "episode_refs": ["G1", "G2"], "relation_refs": ["GR1"]}
        ],
    }

    score = score_graph_blind_holdout(
        graph,
        historical_gold,
        rule_candidates,
        rule_gold,
        {"unchanged_rerun_model_calls": 0, "changed_unit_affects_other_unit_count": 0},
    )

    assert score["release_gate_passed"] is True
    assert score["rule_evidence_metrics"]["exact_rule_unit_recall"] == 1.0

    missing_rule_units = score_graph_blind_holdout(
        graph,
        historical_gold,
        {"rule_evidence_units": [], "duplicate_consumption_episode_refs": []},
        rule_gold,
        {"unchanged_rerun_model_calls": 0, "changed_unit_affects_other_unit_count": 0},
    )

    assert missing_rule_units["release_gate_passed"] is False
    assert missing_rule_units["g3_authorized"] is False


def _source_development_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    raw_text = "== 蒙恬 ==\n二世又遣使者之陽周，令蒙恬曰守邊。蒙恬受詔，後有戰果。"
    snapshot_dir = tmp_path / "snapshots"
    write_wikisource_snapshot(
        WikisourcePageSnapshot(
            page_code="shiji-088",
            requested_title="史記/卷088",
            canonical_title="史記/卷088",
            canonical_url="https://zh.wikisource.org/wiki/example",
            revision_id=1965690,
            revision_timestamp="2020-09-26T14:20:00Z",
            retrieved_at="2026-07-13T00:00:00+00:00",
            raw_text=raw_text,
            content_hash=text_content_hash(raw_text),
        ),
        snapshot_dir / "shiji-088.json",
    )
    manifest = {
        "status": "open_development_source_recovery",
        "dataset_code": "source-development-fixture",
        "window_policy_version": "fixture-v1",
        "sentence_radius_before": 0,
        "sentence_radius_after": 0,
        "context_chars_before": 20,
        "context_chars_after": 20,
        "source_pages": [
            {
                "page_code": "shiji-088",
                "page_title": "史記/卷088",
                "expected_revision_id": 1965690,
                "section_id": "meng-tian",
                "section_heading": "蒙恬",
                "work_identity": "史記",
                "edition_identity": "Wikisource revision 1965690",
                "source_role": "primary_text",
            }
        ],
        "passages": [
            {
                "claim_code": "CLAIM-1",
                "page_code": "shiji-088",
                "anchor_start": "二世又遣使者之陽周",
                "anchor_end": "後有戰果",
                "passage_kind": "atomic",
                "selection_reason": ["open_development_claim_recovery"],
                "supported_fields": [
                    "identity",
                    "action",
                    "responsibility",
                    "outcome",
                ],
            }
        ],
    }
    manifest_path = tmp_path / "manifest.yml"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    claim_snapshot = {
        "people": [
            {
                "ruler": "秦二世",
                "payload": {
                    "claims": [
                        {
                            "claim_code": "CLAIM-1",
                            "emperor_name": "秦二世",
                            "object_name": "蒙恬",
                            "claim_summary": "二世命蒙恬守边并形成结果链。",
                            "confidence": 0.9,
                            "source_passage_refs": ["LEGACY-PASSAGE"],
                            "fact_payload": {
                                "actor": "秦二世",
                                "action_type": "delegation",
                                "object": "蒙恬",
                                "fact_schema": "appointment_delegation",
                                "responsibility_family": "military_command",
                                "outcome": "形成战果",
                            },
                        }
                    ]
                },
            }
        ],
        "canonical_people": [],
    }
    return manifest_path, snapshot_dir, claim_snapshot


def test_source_development_materializer_builds_qualified_v2_input(tmp_path: Path):
    manifest_path, snapshot_dir, claim_snapshot = _source_development_fixture(tmp_path)

    payload = materialize_source_development_input(
        manifest_path=manifest_path,
        claim_snapshot=claim_snapshot,
        snapshot_dir=snapshot_dir,
    )
    report = evaluate_source_development_sets({"fixture": payload})

    assert payload["source_cache_contract"] == "source-cache-contract-v2"
    assert payload["assertion_input_contract"] == "passage-scoped-assertion-v2"
    assert len(payload["source_documents"]) == 1
    assert len(payload["source_passages"]) == 1
    assert len(payload["assertions"]) == 1
    assert payload["assertions"][0]["source_passage_ref"] == payload[
        "source_passages"
    ][0]["passage_code"]
    assert payload["assertions"][0]["extraction_provenance"]["claim_key"] == "CLAIM-1"
    assert report["reports"]["fixture"]["stages"]["S1_source_passage"]["passed"]
    assert report["reports"]["fixture"]["stages"]["S2_assertion"]["passed"]
    assert build_boundary_review_plan(payload)["review_unit_count"] == 1
    assert "episode_code" not in json.dumps(payload, ensure_ascii=False)


def test_source_development_materializer_rejects_nested_oracle_fields(tmp_path: Path):
    manifest_path, snapshot_dir, claim_snapshot = _source_development_fixture(tmp_path)
    claim_snapshot["people"][0]["payload"]["claims"][0]["gold_linkage"] = "GOLD-1"

    with pytest.raises(ValueError, match="Gold/boundary"):
        materialize_source_development_input(
            manifest_path=manifest_path,
            claim_snapshot=claim_snapshot,
            snapshot_dir=snapshot_dir,
        )


def test_v4_source_cache_fixture_runner_ensures_and_exactly_reuses_response(
    tmp_path: Path,
):
    repo_root = Path(__file__).parents[1]
    request_path = repo_root / "eval/source_cache_v4_demo/request.yml"
    plan_path = repo_root / "eval/source_cache_v4_demo/fixture_plan.yml"
    state_path = tmp_path / "source-cache-state.json"
    release_sha = "a" * 40

    first = run_fixture_ensure(
        request_path=request_path,
        fixture_plan_path=plan_path,
        state_path=state_path,
        service_release_sha=release_sha,
        repo_root=repo_root,
    )
    second = run_fixture_ensure(
        request_path=request_path,
        fixture_plan_path=plan_path,
        state_path=state_path,
        service_release_sha=release_sha,
        repo_root=repo_root,
    )

    assert first["response"]["contract"] == "source-cache-contract-v2"
    assert first["response"]["status"] == "succeeded"
    assert len(first["response"]["documents"]) == 1
    assert len(first["response"]["passages"]) == 3
    assert len(adapt_source_cache_v2_response(first["response"]).passages) == 3
    assert first["runtime_audit"] == {
        "cache_hit": False,
        "exact_response_reused": False,
        "provider_call_count": 1,
        "shadow_state_write_count": 1,
        "network_request_count": 0,
        "database_write_count": 0,
        "model_call_count": 0,
    }
    assert second["response"] == first["response"]
    assert second["runtime_audit"]["cache_hit"] is True
    assert second["runtime_audit"]["exact_response_reused"] is True
    assert second["runtime_audit"]["provider_call_count"] == 0
    assert second["runtime_audit"]["shadow_state_write_count"] == 0
    serialized = json.dumps(first["response"], ensure_ascii=False).lower()
    assert "assertion" not in serialized
    assert "episode" not in serialized
    assert "judgment" not in serialized
    assert "score" not in serialized


def test_v4_source_cache_rejects_same_idempotency_key_with_changed_input(
    tmp_path: Path,
):
    repo_root = Path(__file__).parents[1]
    original = yaml.safe_load(
        (repo_root / "eval/source_cache_v4_demo/request.yml").read_text(
            encoding="utf-8"
        )
    )
    first_path = tmp_path / "first.yml"
    changed_path = tmp_path / "changed.yml"
    first_path.write_text(
        yaml.safe_dump(original, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    original["source_policy_version"] = "changed-policy"
    changed_path.write_text(
        yaml.safe_dump(original, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    state_path = tmp_path / "state.json"
    plan_path = repo_root / "eval/source_cache_v4_demo/fixture_plan.yml"
    run_fixture_ensure(
        request_path=first_path,
        fixture_plan_path=plan_path,
        state_path=state_path,
        service_release_sha="b" * 40,
        repo_root=repo_root,
    )

    with pytest.raises(SourceCacheIdempotencyConflict, match="不同有效输入"):
        run_fixture_ensure(
            request_path=changed_path,
            fixture_plan_path=plan_path,
            state_path=state_path,
            service_release_sha="b" * 40,
            repo_root=repo_root,
        )


def test_v4_source_cache_refresh_retains_old_revision_and_creates_new_identity(
    tmp_path: Path,
):
    repo_root = Path(__file__).parents[1]
    request = load_source_cache_request(
        repo_root / "eval/source_cache_v4_demo/request.yml"
    )
    plan = yaml.safe_load(
        (repo_root / "eval/source_cache_v4_demo/fixture_plan.yml").read_text(
            encoding="utf-8"
        )
    )
    plan["sections"][0]["expected_revision_id"] = None
    plan_path = tmp_path / "refresh-plan.yml"
    plan_path.write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    snapshot = read_wikisource_snapshot(
        repo_root
        / "tests/fixtures/source_cache_v4/weizheng_jiutangshu_snapshot.json"
    )
    refreshed_text = snapshot.raw_text + "\n测试刷新版本追加原文。"
    refreshed_snapshot = replace(
        snapshot,
        revision_id=snapshot.revision_id + 1,
        revision_timestamp="2026-07-14T00:00:00Z",
        retrieved_at="2026-07-14T00:01:00+00:00",
        raw_text=refreshed_text,
        content_hash=hashlib.sha256(refreshed_text.encode("utf-8")).hexdigest(),
    )
    repository = InMemorySourceCacheRepository()
    first = ensure_source_cache(
        request,
        provider=WikisourceSourceMaterialProvider(
            plan_path=plan_path,
            fetch=lambda **_: snapshot,
        ),
        repository=repository,
        service_release_sha="c" * 40,
    )
    refresh_request = replace(
        request,
        request_id="SRC-V4-WEIZHENG-REFRESH-002",
        idempotency_key="source-cache:v4:weizheng:jiutangshu:refresh:v2",
        mode="refresh",
    )
    refreshed = ensure_source_cache(
        refresh_request,
        provider=WikisourceSourceMaterialProvider(
            plan_path=plan_path,
            fetch=lambda **_: refreshed_snapshot,
        ),
        repository=repository,
        service_release_sha="c" * 40,
    )

    first_document = first.response["documents"][0]
    refreshed_document = refreshed.response["documents"][0]
    assert first_document["document_cache_id"] != refreshed_document["document_cache_id"]
    assert first_document["content_hash"] != refreshed_document["content_hash"]
    assert repository.get(request.idempotency_key).response == first.response
    assert repository.get(refresh_request.idempotency_key).response == refreshed.response
    first_passage = first.response["passages"][0]
    refreshed_passage = refreshed.response["passages"][0]
    assert repository.get_revision(
        first_passage["document_id"], first_passage["content_version"]
    ).raw_text == snapshot.raw_text
    assert repository.get_revision(
        refreshed_passage["document_id"], refreshed_passage["content_version"]
    ).raw_text == refreshed_text
    assert refreshed.response["provenance"]["request_mode"] == "refresh"


def test_v4_wikisource_adapter_shadow_matches_frozen_revision_without_db(
    tmp_path: Path,
):
    repo_root = Path(__file__).parents[1]
    request_path = repo_root / "eval/source_cache_v4_demo/request.yml"
    plan_path = repo_root / "eval/source_cache_v4_demo/fixture_plan.yml"
    release_sha = "d" * 40
    baseline = run_fixture_ensure(
        request_path=request_path,
        fixture_plan_path=plan_path,
        state_path=tmp_path / "state.json",
        service_release_sha=release_sha,
        repo_root=repo_root,
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(baseline, ensure_ascii=False),
        encoding="utf-8",
    )
    snapshot = read_wikisource_snapshot(
        repo_root
        / "tests/fixtures/source_cache_v4/weizheng_jiutangshu_snapshot.json"
    )

    report = run_wikisource_shadow(
        request_path=request_path,
        plan_path=plan_path,
        baseline_report_path=baseline_path,
        service_release_sha=release_sha,
        fetch=lambda **_: snapshot,
    )

    assert report["status"] == "source_cache_wikisource_shadow_match"
    assert report["comparison"]["matched"] is True
    assert report["runtime_audit"]["network_request_count"] == 1
    assert report["runtime_audit"]["database_write_count"] == 0


def test_source_development_rebind_reuses_identical_passage_span(tmp_path: Path):
    manifest_path, snapshot_dir, _ = _source_development_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    second = dict(manifest["passages"][0])
    second["claim_code"] = "CLAIM-2"
    second["selection_reason"] = ["duplicate_semantic_source_span"]
    manifest["passages"].append(second)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    def assertion(code: str, claim: str, passage: str) -> dict:
        return {
            "assertion_code": code,
            "source_passage_ref": passage,
            "assertion_type": "event_fact",
            "subject": "秦二世",
            "predicate": "delegation",
            "object": "蒙恬",
            "time_expression": None,
            "location_expression": None,
            "qualifiers": {
                "evaluation_context": "PER-QIN-ERSHI",
                "evaluation_context_name": "秦二世",
                "episode_type": "appointment_delegation",
                "responsibility_family": "military_command",
                "office_or_domain": "边防",
                "normalized_time": {},
                "outcome": "形成战果",
                "claim_summary": "二世命蒙恬守边。",
            },
            "polarity": "asserted",
            "source_attribution": {
                "document_code": "LEGACY-DOC",
                "source_slice_ref": passage,
            },
            "confidence": 0.9,
            "ambiguity_flags": [],
            "extraction_provenance": {
                "origin": "legacy",
                "claim_key": claim,
            },
        }

    payload = materialize_source_development_from_blind_input(
        manifest_path=manifest_path,
        blind_input={
            "dataset_code": "legacy-fixture",
            "canonical_people": [],
            "assertions": [
                assertion("A-1", "CLAIM-1", "OLD-P-1"),
                assertion("A-2", "CLAIM-1", "OLD-P-2"),
                assertion("A-3", "CLAIM-2", "OLD-P-3"),
            ],
        },
        snapshot_dir=snapshot_dir,
    )
    report = evaluate_source_development_sets({"fixture": payload})

    assert len(payload["source_passages"]) == 1
    assert len(payload["assertions"]) == 3
    assert len({item["assertion_code"] for item in payload["assertions"]}) == 3
    assert len({item["source_passage_ref"] for item in payload["assertions"]}) == 1
    assert {
        "claim:CLAIM-1",
        "claim:CLAIM-2",
    }.issubset(payload["source_passages"][0]["selection_reason"])
    assert report["reports"]["fixture"]["stages"]["S1_source_passage"]["passed"]
    assert report["reports"]["fixture"]["stages"]["S2_assertion"]["passed"]
def test_source_cache_worker_is_idempotent_and_terminal_jobs_are_not_reclaimed() -> None:
    from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
    from emperor_v4.persistence.source_cache_jobs import InMemorySourceCacheJobRepository

    repository = InMemorySourceCacheJobRepository()
    payload = {"request_id": "REQ-1", "source_hints": ("舊唐書/卷71",)}
    assert repository.enqueue(
        job_id="SCJ-1", idempotency_key="source-cache:job:1",
        input_fingerprint="input-1", policy_version="policy-v1",
        request_payload=payload,
    ) == 1
    assert repository.enqueue(
        job_id="SCJ-DUPLICATE", idempotency_key="source-cache:job:1",
        input_fingerprint="input-1", policy_version="policy-v1",
        request_payload=payload,
    ) == 0
    calls = []

    def handler(request):
        calls.append(request)
        return {"output_fingerprint": "output-1", "status": "succeeded"}

    first = run_source_cache_worker_once(
        repository, worker_id="worker-a", handler=handler,
    )
    second = run_source_cache_worker_once(
        repository, worker_id="worker-a", handler=handler,
    )
    assert first.status == "succeeded"
    assert second.status == "idle"
    assert calls == [payload]
    assert repository.jobs["source-cache:job:1"].status == "succeeded"


def test_source_cache_worker_recovers_expired_lease_before_retry() -> None:
    from datetime import datetime, timedelta, timezone

    from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
    from emperor_v4.persistence.source_cache_jobs import InMemorySourceCacheJobRepository

    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    repository = InMemorySourceCacheJobRepository(clock=lambda: now)
    repository.enqueue(
        job_id="SCJ-LEASE", idempotency_key="source-cache:lease",
        input_fingerprint="input-lease", policy_version="policy-v1",
        request_payload={"request_id": "REQ-LEASE"},
    )
    claimed = repository.claim(worker_id="dead-worker", lease_seconds=10)
    assert claimed is not None
    now += timedelta(seconds=11)
    calls = []
    tick = run_source_cache_worker_once(
        repository, worker_id="recovery-worker",
        handler=lambda request: calls.append(request) or {"output_fingerprint": "recovered"},
    )
    assert tick.status == "succeeded"
    assert tick.recovered_lease_count == 1
    assert claimed.attempt_number == 1
    assert repository.jobs["source-cache:lease"].attempt_count == 2
    assert len(calls) == 1


def test_source_cache_worker_retries_then_fails_at_max_attempts() -> None:
    from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
    from emperor_v4.persistence.source_cache_jobs import InMemorySourceCacheJobRepository

    repository = InMemorySourceCacheJobRepository()
    repository.enqueue(
        job_id="SCJ-FAIL", idempotency_key="source-cache:fail",
        input_fingerprint="input-fail", policy_version="policy-v1",
        request_payload={"request_id": "REQ-FAIL"}, max_attempts=2,
    )

    def fail(_request):
        raise RuntimeError("provider unavailable")

    first = run_source_cache_worker_once(
        repository, worker_id="worker-a", handler=fail, retry_delay_seconds=0,
    )
    second = run_source_cache_worker_once(
        repository, worker_id="worker-a", handler=fail, retry_delay_seconds=0,
    )
    third = run_source_cache_worker_once(
        repository, worker_id="worker-a", handler=fail, retry_delay_seconds=0,
    )
    assert (first.status, second.status, third.status) == ("retry_wait", "failed", "idle")


def test_source_cache_job_idempotency_conflict_fails_closed() -> None:
    import pytest

    from emperor_v4.persistence.source_cache_jobs import InMemorySourceCacheJobRepository

    repository = InMemorySourceCacheJobRepository()
    repository.enqueue(
        job_id="SCJ-1", idempotency_key="source-cache:same",
        input_fingerprint="input-1", policy_version="policy-v1",
        request_payload={"request_id": "REQ-1"},
    )
    with pytest.raises(ValueError, match="不同输入"):
        repository.enqueue(
            job_id="SCJ-2", idempotency_key="source-cache:same",
            input_fingerprint="input-2", policy_version="policy-v1",
            request_payload={"request_id": "REQ-2"},
        )
def test_claim_extractor_v2_fixture_application_is_exactly_reusable() -> None:
    import json
    from pathlib import Path

    from emperor_v4.adapters.claim_extraction_profile import load_claim_extraction_profile
    from emperor_v4.adapters.claim_extractor_frozen import FrozenClaimExtractionProvider
    from emperor_v4.application.claim_extractor_service import ensure_claim_extraction
    from emperor_v4.persistence.claim_extractor import InMemoryClaimExtractionRepository
    from emperor_v4.runtime.claim_extractor import request_from_frozen_snapshot

    root = Path(__file__).parents[1]
    snapshot_path = root / "tests/fixtures/episode_pilot_v1/claim-extractor-talent-discovery-response.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    request = request_from_frozen_snapshot(
        snapshot, profile_code="talent_discovery_chain_v1",
        request_id="CLX-V4-WEIZHENG-001", idempotency_key="claim-extraction:v4:weizheng:talent:v1",
        requested_at="2026-07-14T20:00:00+08:00",
    )
    profile = load_claim_extraction_profile(root / "config/claim-extraction-profiles.yml", request.profile_code)
    repository = InMemoryClaimExtractionRepository()
    provider = FrozenClaimExtractionProvider(snapshot_path)
    first = ensure_claim_extraction(
        request, profile=profile, provider=provider, repository=repository,
        service_release_sha="a" * 40,
    )
    second = ensure_claim_extraction(
        request, profile=profile, provider=provider, repository=repository,
        service_release_sha="a" * 40,
    )
    assert len(first.response["assertions"]) == 4
    assert all(row["passage_support"]["support_mode"] == "single_passage" for row in first.response["assertions"])
    assert (first.cache_hit, first.provider_call_count, first.model_call_count) == (False, 1, 0)
    assert (second.cache_hit, second.provider_call_count, second.repository_write_count) == (True, 0, 0)
    assert second.response == first.response


def test_claim_extractor_v2_rejects_missing_passage_support() -> None:
    import json
    from pathlib import Path

    import pytest

    from emperor_v4.adapters.claim_extraction_profile import load_claim_extraction_profile
    from emperor_v4.application.claim_extractor_service import ClaimExtractionBatch, ensure_claim_extraction
    from emperor_v4.persistence.claim_extractor import InMemoryClaimExtractionRepository
    from emperor_v4.runtime.claim_extractor import request_from_frozen_snapshot
    from emperor_v4.adapters.claim_extractor import adapt_claim_extractor_snapshot

    root = Path(__file__).parents[1]
    snapshot = json.loads((root / "tests/fixtures/episode_pilot_v1/claim-extractor-talent-discovery-response.json").read_text(encoding="utf-8"))
    request = request_from_frozen_snapshot(snapshot, profile_code="talent_discovery_chain_v1", request_id="REQ", idempotency_key="KEY", requested_at="NOW")
    profile = load_claim_extraction_profile(root / "config/claim-extraction-profiles.yml", request.profile_code)

    class LegacyProvider:
        def extract(self, _payload):
            return ClaimExtractionBatch(adapt_claim_extractor_snapshot(snapshot), "legacy", 0)

    with pytest.raises(ValueError, match="缺少 PassageSupport"):
        ensure_claim_extraction(request, profile=profile, provider=LegacyProvider(), repository=InMemoryClaimExtractionRepository(), service_release_sha="b" * 40)
