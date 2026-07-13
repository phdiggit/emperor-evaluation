from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

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
    run_blind_holdout_with_semantic_review,
    score_blind_holdout,
)
from emperor_v4.evaluation.boundary_score import score_boundary_graph
from emperor_v4.evaluation.graph_holdout import (
    draft_rule_evidence_units_payload,
    score_graph_blind_holdout,
    validate_boundary_review_freeze,
)
from emperor_v4.evaluation.source_gap import check_source_segmentation_repair_response


FIXTURES = Path(__file__).parent / "fixtures" / "episode_pilot_v1"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
