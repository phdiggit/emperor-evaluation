from __future__ import annotations

from dataclasses import replace

import pytest

from emperor_v4.application.core_shadow_runner import run_core_shadow_sync
from emperor_v4.contracts.episode import AssertionLink
from emperor_v4.persistence import CoreRegistryBatch, InMemoryCoreRegistry
from test_g3a_core_registry import _assertion, _initial_batch, _packet, _passage


ANCHOR_A = "anchor-a"
ANCHOR_B = "anchor-b"


def _two_episode_batch() -> CoreRegistryBatch:
    initial = _initial_batch()
    first = initial.episodes[0]
    second = replace(
        _packet(("A-1", "SP-1"), responsibility="财政"),
        episode_id="EP-2",
        semantic_fingerprint="semantic-2",
        action="任命财政官",
    )
    return replace(
        initial,
        episodes=(first, second),
        episode_dispositions=(),
        episode_identity_anchors={"EP-1": ANCHOR_A, "EP-2": ANCHOR_B},
    )


def test_sync_runner_unchanged_rerun_is_zero_write_and_zero_model_call() -> None:
    registry = InMemoryCoreRegistry()
    batch = _two_episode_batch()

    first = run_core_shadow_sync(registry, batch)
    second = run_core_shadow_sync(registry, batch)

    assert first.new_identity_anchors == (ANCHOR_A, ANCHOR_B)
    assert second.unchanged_identity_anchors == (ANCHOR_A, ANCHOR_B)
    assert second.business_write_count == 0
    assert second.model_call_count == 0


def test_sync_runner_semantic_change_only_revises_target_identity() -> None:
    registry = InMemoryCoreRegistry()
    initial = _two_episode_batch()
    run_core_shadow_sync(registry, initial)
    changed_a = replace(
        initial.episodes[0],
        episode_id="EP-OBSERVED-NEW-ID",
        responsibility="财政与军务",
        semantic_fingerprint="semantic-a-v2",
    )
    observed = CoreRegistryBatch(
        episodes=(changed_a, initial.episodes[1]),
        episode_identity_anchors={
            changed_a.episode_id: ANCHOR_A,
            initial.episodes[1].episode_id: ANCHOR_B,
        },
    )

    result = run_core_shadow_sync(registry, observed)
    active = registry.active_packets_by_identity((ANCHOR_A, ANCHOR_B))

    assert result.semantic_revision_anchors == (ANCHOR_A,)
    assert result.unchanged_identity_anchors == (ANCHOR_B,)
    assert result.write_result.table_writes["historical_episode_versions"] == 1
    assert result.write_result.table_writes["episode_participants"] == 2
    assert active[ANCHOR_A].episode_id == "EP-1"
    assert active[ANCHOR_A].semantic_version == 2
    assert active[ANCHOR_B].semantic_version == 1


def test_sync_runner_evidence_change_does_not_duplicate_participants() -> None:
    registry = InMemoryCoreRegistry()
    initial = _two_episode_batch()
    run_core_shadow_sync(registry, initial)
    passage = _passage("SP-2", "又命某仍掌军务", 20)
    assertion = _assertion("A-2", passage.passage_cache_id)
    changed_a = replace(
        initial.episodes[0],
        assertion_links=initial.episodes[0].assertion_links
        + (
            AssertionLink(
                assertion_ref="A-2",
                source_passage_ref="SP-2",
                relation="supports",
                supported_fields=("identity", "action", "responsibility"),
            ),
        ),
    )
    observed = CoreRegistryBatch(
        source_passages=(passage,),
        assertions=(assertion,),
        episodes=(changed_a, initial.episodes[1]),
        episode_identity_anchors={"EP-1": ANCHOR_A, "EP-2": ANCHOR_B},
    )

    result = run_core_shadow_sync(registry, observed)
    active = registry.active_packets_by_identity((ANCHOR_A, ANCHOR_B))

    assert result.evidence_revision_anchors == (ANCHOR_A,)
    assert result.unchanged_identity_anchors == (ANCHOR_B,)
    assert result.write_result.table_writes["historical_episode_versions"] == 1
    assert result.write_result.table_writes["episode_participants"] == 0
    assert active[ANCHOR_A].semantic_version == 1
    assert active[ANCHOR_A].evidence_version == 2


def test_global_input_provenance_change_does_not_fan_out_episode_versions() -> None:
    registry = InMemoryCoreRegistry()
    initial = _two_episode_batch()
    run_core_shadow_sync(registry, initial)
    observed_episodes = tuple(
        replace(
            packet,
            provenance={**packet.provenance, "input_hash": "new-global-input-hash"},
        )
        for packet in initial.episodes
    )

    result = run_core_shadow_sync(
        registry,
        CoreRegistryBatch(
            episodes=observed_episodes,
            episode_identity_anchors=initial.episode_identity_anchors,
        ),
    )

    assert result.unchanged_identity_anchors == (ANCHOR_A, ANCHOR_B)
    assert result.business_write_count == 0
    assert registry.counts()["historical_episode_versions"] == 2


def test_failed_sync_batch_rolls_back_and_valid_retry_succeeds() -> None:
    registry = InMemoryCoreRegistry()
    initial = _two_episode_batch()
    run_core_shadow_sync(registry, initial)
    before = dict(registry.counts())
    invalid = replace(
        initial.episodes[0],
        assertion_links=(
            AssertionLink(
                assertion_ref="A-MISSING",
                source_passage_ref="SP-MISSING",
                relation="supports",
                supported_fields=("identity", "action"),
            ),
        ),
    )

    with pytest.raises(ValueError, match="lineage"):
        run_core_shadow_sync(
            registry,
            CoreRegistryBatch(
                episodes=(invalid,),
                episode_identity_anchors={invalid.episode_id: ANCHOR_A},
            ),
        )
    assert registry.counts() == before

    valid = replace(initial.episodes[0], responsibility="修订职责")
    result = run_core_shadow_sync(
        registry,
        CoreRegistryBatch(
            episodes=(valid,),
            episode_identity_anchors={valid.episode_id: ANCHOR_A},
        ),
    )
    assert result.semantic_revision_anchors == (ANCHOR_A,)
    assert result.write_result.table_writes["historical_episode_versions"] == 1
