from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
)
from emperor_v4.application.reconcile_episode import reconcile_episode_candidates
from emperor_v4.evaluation.assertion_handoff import check_assertion_repair_response
from emperor_v4.evaluation.episode_pilot import evaluate_episode_pilot
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
    report = evaluate_episode_pilot(
        root / "eval" / "episode_pilot_v1.yml",
        FIXTURES,
        root / "eval" / "episode_pilot_v1_linkage.yml",
        FIXTURES / "source-cache-supplement-response.json",
        FIXTURES / "claim-extractor-supplement-response.json",
        FIXTURES / "source-cache-segmentation-repair-response.json",
        FIXTURES / "claim-extractor-repair-response.json",
        root / "eval" / "episode_pilot_v1_assertion_gold_coverage.yml",
    )

    assert source_repair["status"] == "passed"
    assert source_repair["network_fetch_count"] == 0
    assert assertion_repair["status"] == "passed"
    assert assertion_repair["used_passage_count"] == assertion_repair["input_passage_count"]
    assert report["assertion_boundary_coverage"]["full_boundary_support_count"] == 8
    assert report["assertion_boundary_coverage"]["partial_boundary_support_count"] == 6
    assert report["assertion_boundary_coverage"]["no_boundary_support_count"] == 1
    assert report["lineage_assisted_reconciliation"]["candidate_packet_count"] == 15
    assert report["lineage_assisted_reconciliation"]["supported_boundary_packet_count"] == 14
    assert report["lineage_assisted_reconciliation"]["unassigned_new_assertion_count"] == 0
    assert report["lineage_assisted_reconciliation"]["all_packets_proposed"] is True
    assert report["episode_recall"]["full_match_episode_count"] == 0
