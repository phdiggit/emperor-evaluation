from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.factor_observation_agent import (
    build_factor_observation_batch_plan,
    build_factor_observation_worklist,
    build_factor_observation_qualification_gold,
    evaluate_factor_observation_qualification,
    merge_factor_observation_batch_responses,
)


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    return payload


def run_factor_observation_worklist(source_manifest_path: Path) -> dict[str, Any]:
    return build_factor_observation_worklist(_load(source_manifest_path))


def run_factor_observation_qualification_gold(
    worklist_path: Path,
    parity_gold_manifest_path: Path,
    source_manifest_path: Path,
    *,
    sample_role: str = "open_development",
) -> dict[str, Any]:
    return build_factor_observation_qualification_gold(
        _load(worklist_path),
        _load(parity_gold_manifest_path),
        _load(source_manifest_path),
        sample_role=sample_role,
    )


def run_factor_observation_batch_plan(
    source_manifest_path: Path,
    *,
    max_units_per_batch: int = 4,
    max_workers: int = 4,
) -> dict[str, Any]:
    return build_factor_observation_batch_plan(
        _load(source_manifest_path),
        max_units_per_batch=max_units_per_batch,
        max_workers=max_workers,
    )


def run_factor_observation_batch_merge(
    batch_plan_path: Path,
    response_paths: tuple[Path, ...],
    source_manifest_path: Path,
) -> dict[str, Any]:
    return merge_factor_observation_batch_responses(
        _load(batch_plan_path),
        tuple(_load(path) for path in response_paths),
        _load(source_manifest_path),
    )


def run_factor_observation_qualification(
    worklist_path: Path,
    response_path: Path,
    gold_manifest_path: Path,
    source_manifest_path: Path,
) -> dict[str, Any]:
    return evaluate_factor_observation_qualification(
        _load(worklist_path),
        _load(response_path),
        _load(gold_manifest_path),
        _load(source_manifest_path),
    )
