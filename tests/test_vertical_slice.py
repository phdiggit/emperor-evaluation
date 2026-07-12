from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
)
from emperor_v4.application.reconcile_episode import reconcile_episode_candidates


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
