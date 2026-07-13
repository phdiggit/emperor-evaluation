from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_limited_factor_shadow_manifest,
)
from emperor_v4.evaluation.talent_discovery_scoring import (
    PROFILE,
    evaluate_judgment,
    score_judgment,
    validate_scored_demo_manifest,
)


def run_talent_discovery_shadow(manifest_path: Path | str) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    return run_talent_discovery_shadow_manifest(manifest, path)


def run_talent_discovery_shadow_manifest(
    manifest: Mapping[str, Any],
    manifest_path: Path | str,
    *,
    prior_report: Mapping[str, Any] | None = None,
    rebuild_unit_refs: set[str] | None = None,
) -> dict[str, Any]:
    return run_limited_factor_shadow_manifest(
        manifest,
        manifest_path,
        profile=PROFILE,
        manifest_validator=validate_scored_demo_manifest,
        judgment_evaluator=evaluate_judgment,
        judgment_scorer=score_judgment,
        prior_report=prior_report,
        rebuild_unit_refs=rebuild_unit_refs,
    )
