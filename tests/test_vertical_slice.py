from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
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
    score_blind_holdout,
)
from emperor_v4.evaluation.source_gap import check_source_segmentation_repair_response


FIXTURES = Path(__file__).parent / "fixtures" / "episode_pilot_v1"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
    assert run["accuracy_metrics"]["autonomous_boundary_recall"] is None
    assert run["safety"] == {
        "gold_fields_detected": 0,
        "model_call_count": 0,
        "network_request_count": 0,
        "database_write_count": 0,
    }

    decisions = {
        packet["semantic_fingerprint"]: {
            "decision": "full_match",
            "gold_episode_codes": [f"SMOKE-{index}"],
        }
        for index, packet in enumerate(run["packets"], start=1)
    }
    score = score_blind_holdout(
        run,
        {
            "candidate_input_sha256": run["input_sha256"],
            "gold_episode_codes": ["SMOKE-1", "SMOKE-2", "SMOKE-3"],
            "candidate_decisions": decisions,
            "wrong_merge_fingerprints": [],
            "wrong_split_gold_episode_codes": [],
            "cross_ruler_contamination_count": 0,
        },
    )

    assert score["metrics"]["autonomous_boundary_recall"] == 1.0
    assert score["metrics"]["candidate_precision"] == 1.0
    assert score["accepted_metrics"]["accepted_recall"] is None
