from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from emperor_v4.application.appointment_delegation_roster_runner import (
    RosterRunProfile,
    run_limited_factor_roster_shadow,
    run_persistent_limited_factor_roster_shadow,
)
from emperor_v4.application.talent_discovery_shadow_runner import (
    run_talent_discovery_shadow_manifest,
)


TALENT_DISCOVERY_ROSTER_PROFILE = RosterRunProfile(
    rule_code="talent_discovery",
    policy_version="talent-discovery-roster-offline-v1",
    report_status="talent_discovery_roster_shadow_complete",
    review_job_prefix="TD-REVIEW",
)


def run_talent_discovery_roster_shadow(
    manifest_path: Path | str,
    *,
    prior_record_path: Path | str | None = None,
    checkpoint: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    return run_limited_factor_roster_shadow(
        manifest_path,
        profile=TALENT_DISCOVERY_ROSTER_PROFILE,
        scored_runner=run_talent_discovery_shadow_manifest,
        prior_record_path=prior_record_path,
        checkpoint=checkpoint,
    )


def run_persistent_talent_discovery_roster_shadow(
    manifest_path: Path | str,
    state_path: Path | str,
    *,
    prior_record_path: Path | str | None = None,
    fail_after_stage: str | None = None,
) -> dict[str, Any]:
    return run_persistent_limited_factor_roster_shadow(
        manifest_path,
        state_path,
        profile=TALENT_DISCOVERY_ROSTER_PROFILE,
        roster_runner=run_talent_discovery_roster_shadow,
        prior_record_path=prior_record_path,
        fail_after_stage=fail_after_stage,
    )
