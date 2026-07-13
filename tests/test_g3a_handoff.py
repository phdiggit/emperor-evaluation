from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.application.core_registry_handoff import (
    build_g3a_core_registry_batch,
)
from emperor_v4.persistence import InMemoryCoreRegistry


ROOT = Path(__file__).parents[1]
DATASETS = (
    "g2_6k0_g2_6i_source_v2_development",
    "g2_6k0_g2_6j_source_v2_development",
)


def _payloads(dataset: str) -> tuple[dict, dict]:
    base = ROOT / "eval" / dataset
    blind_input = json.loads((base / "input.json").read_text(encoding="utf-8"))
    review = yaml.safe_load((base / "boundary_review.yml").read_text(encoding="utf-8"))
    return blind_input, review


@pytest.mark.parametrize("dataset", DATASETS)
def test_g3a_handoff_contains_only_core_objects(dataset: str) -> None:
    batch = build_g3a_core_registry_batch(*_payloads(dataset))

    assert batch.source_documents
    assert batch.source_passages
    assert batch.assertions
    assert batch.episodes
    assert batch.episode_dispositions
    assert batch.review_artifacts
    assert batch.boundary_cache_entries
    assert all(item.status == "proposed" for item in batch.review_artifacts)
    assert all(item.artifact_type == "boundary_review" for item in batch.review_artifacts)
    assert not hasattr(batch, "episode_relations")
    assert not hasattr(batch, "rule_evidence_units")


@pytest.mark.parametrize("dataset", DATASETS)
def test_g3a_handoff_is_idempotent_in_reference_registry(dataset: str) -> None:
    batch = build_g3a_core_registry_batch(*_payloads(dataset))
    registry = InMemoryCoreRegistry()

    first = registry.apply(batch)
    second = registry.apply(batch)

    assert first.business_write_count > 0
    assert second.business_write_count == 0
    assert second.model_call_count == 0
