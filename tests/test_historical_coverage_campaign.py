from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import threading

import pytest
import yaml

from emperor_v4.application.historical_coverage_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    CampaignContractError,
    CampaignRunner,
    CampaignState,
    PHASE_CODES,
    PhaseExecutionResult,
    build_campaign_state,
    build_campaign_summary,
    main,
)


RULES = (
    "APPOINTMENT_DELEGATION",
    "TALENT_DISCOVERY",
    "TOLERATE_TALENT",
    "ANTI_NEPOTISM",
    "TEAM_BUILDING",
)


def manifest(ruler_count: int = 2) -> dict:
    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_code": "I5B_HC_V1",
        "input_version": "campaign-input-v1",
        "expected_ruler_count": ruler_count,
        "rulers": [
            {"ruler_code": f"RULER_{index:03d}", "input_version": "roster-v1"}
            for index in range(1, ruler_count + 1)
        ],
        "rules": [
            {"rule_code": rule, "rule_version": "rule-v1"} for rule in RULES
        ],
        "artifact_root": "tmp/i5b_historical_coverage_campaign",
        "runtime": {
            "max_concurrency": 8,
            "max_attempts": 2,
            "lease_seconds": 30,
            "retry_delay_seconds": 0,
            "failure_policy": "fail_closed",
        },
        "phases": [
            {
                "code": code,
                "output_schema_version": f"i5b-{code}-artifact-v1",
                "max_concurrency": 4,
            }
            for code in PHASE_CODES
        ],
        "safety": {
            "offline": True,
            "report_only": True,
            "shadow_first": True,
            "formal_scoring": False,
            "ranking": False,
            "production_deployment": False,
        },
    }


def handlers(
    *, failure=None, calls=None, active=None, peak=None, barrier=None, model_calls=0
):
    calls = calls if calls is not None else []

    def handle(claim):
        calls.append((claim.task_code, claim.ruler_code, claim.rule_code, claim.phase_code))
        if active is not None and peak is not None:
            with active["lock"]:
                active["count"] += 1
                peak["value"] = max(peak["value"], active["count"])
        try:
            if barrier is not None:
                barrier.wait(timeout=5)
            if failure:
                failure(claim)
            return PhaseExecutionResult(
                payload={
                    "artifact_type": claim.phase_code,
                    "fixture_result": f"{claim.ruler_code}:{claim.rule_code}",
                },
                model_calls=model_calls,
            )
        finally:
            if active is not None and peak is not None:
                with active["lock"]:
                    active["count"] -= 1

    return {code: handle for code in PHASE_CODES}


def test_185_by_five_manifest_expands_to_independent_stable_tasks() -> None:
    first = build_campaign_state(manifest(185))
    second = build_campaign_state(deepcopy(manifest(185)))

    assert len(first.tasks) == 925
    assert set(first.tasks) == set(second.tasks)
    assert len({task.spec.allowed_write_prefix for task in first.tasks.values()}) == 925
    assert all(len(task.spec.output_schemas) == 5 for task in first.tasks.values())
    assert all(task.phases["candidate_freeze"].status == "ready" for task in first.tasks.values())
    assert all(task.phases["source_recovery"].status == "blocked" for task in first.tasks.values())


def test_cross_ruler_and_cross_rule_artifacts_are_isolated() -> None:
    state = build_campaign_state(manifest())
    runner = CampaignRunner(state, handlers=handlers())
    assert runner.run_to_quiescence(worker_id="fixture-worker") == 50

    paths = list(state.artifacts)
    assert len(paths) == 50
    for task in state.tasks.values():
        task_paths = [path for path in paths if path.startswith(task.spec.allowed_write_prefix)]
        assert len(task_paths) == 5
        assert all(
            state.artifacts[path]["ruler_code"] == task.spec.ruler_code
            and state.artifacts[path]["rule_code"] == task.spec.rule_code
            for path in task_paths
        )


def test_unchanged_rerun_is_zero_model_calls_and_zero_business_writes() -> None:
    state = build_campaign_state(manifest(1))
    calls = []
    runner = CampaignRunner(state, handlers=handlers(calls=calls, model_calls=1))
    runner.run_to_quiescence(worker_id="fixture-worker")
    checkpoint = state.checkpoint()
    restored = CampaignState.from_checkpoint(checkpoint)
    before_artifacts = deepcopy(restored.artifacts)
    before_model_calls = restored.model_call_count
    rerun_calls = []

    completed = CampaignRunner(
        restored, handlers=handlers(calls=rerun_calls)
    ).run_to_quiescence(worker_id="resume-worker")

    assert completed == 0
    assert rerun_calls == []
    assert restored.artifacts == before_artifacts
    assert restored.model_call_count == before_model_calls == 25
    assert restored.business_write_count == 0


def test_one_task_failure_fails_closed_without_blocking_other_tasks() -> None:
    state = build_campaign_state(manifest())

    def fail_one(claim):
        if claim.ruler_code == "RULER_001" and claim.rule_code == "TALENT_DISCOVERY":
            raise ValueError("fixture contract failure")

    runner = CampaignRunner(state, handlers=handlers(failure=fail_one))
    runner.run_to_quiescence(worker_id="fixture-worker")
    failed = next(
        task
        for task in state.tasks.values()
        if task.spec.ruler_code == "RULER_001"
        and task.spec.rule_code == "TALENT_DISCOVERY"
    )

    assert failed.status == "failed_closed"
    assert failed.phases["candidate_freeze"].status == "failed"
    assert all(
        failed.phases[code].status == "blocked_upstream_failed"
        for code in PHASE_CODES[1:]
    )
    assert sum(task.status == "succeeded" for task in state.tasks.values()) == 9


def test_retry_lease_recovery_and_checkpoint_resume() -> None:
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    state = build_campaign_state(manifest(1))
    runner = CampaignRunner(
        state, handlers=handlers(), clock=lambda: now
    )
    claim = runner._claim_batch("candidate_freeze", "dead-worker", 1)[0]
    assert state.tasks[claim.task_code].phases[claim.phase_code].status == "running"

    checkpoint = state.checkpoint()
    restored = CampaignState.from_checkpoint(checkpoint)
    now += timedelta(seconds=31)
    resumed = CampaignRunner(restored, handlers=handlers(), clock=lambda: now)

    assert resumed.recover_expired_leases() == 1
    assert resumed.run_to_quiescence(worker_id="resume-worker") == 25
    recovered_task = restored.tasks[claim.task_code]
    assert recovered_task.phases["candidate_freeze"].attempt_count == 2
    assert all(task.status == "succeeded" for task in restored.tasks.values())


def test_retryable_failure_stops_at_max_attempts() -> None:
    state = build_campaign_state(manifest(1))

    def unavailable(claim):
        if claim.ruler_code == "RULER_001" and claim.rule_code == "ANTI_NEPOTISM":
            raise RuntimeError("fixture provider unavailable")

    runner = CampaignRunner(state, handlers=handlers(failure=unavailable))
    runner.run_to_quiescence(worker_id="fixture-worker")
    task = next(
        item for item in state.tasks.values() if item.spec.rule_code == "ANTI_NEPOTISM"
    )
    assert task.phases["candidate_freeze"].attempt_count == 2
    assert task.status == "failed_closed"


def test_summary_consumes_only_successful_contract_valid_shadow_artifacts() -> None:
    state = build_campaign_state(manifest(1))
    CampaignRunner(state, handlers=handlers()).run_to_quiescence(
        worker_id="fixture-worker"
    )
    tasks = sorted(state.tasks.values(), key=lambda row: row.spec.rule_code)
    tampered = tasks[0]
    path = tampered.phases["shadow_projection"].artifact_path
    state.artifacts[path] = {**state.artifacts[path], "status": "copied_by_hand"}
    pending = tasks[1]
    pending.phases["shadow_projection"].status = "failed"

    summary = build_campaign_summary(state)

    assert summary["gate"]["status"] == "failed_closed"
    assert summary["gate"]["formal_scoring_open"] is False
    assert len(summary["consumed_successful_results"]) == 3
    assert {row["task_code"] for row in summary["rejected_results"]} == {
        tampered.spec.task_code,
        pending.spec.task_code,
    }


def test_report_only_contract_rejects_business_writes_and_unsafe_manifest() -> None:
    state = build_campaign_state(manifest(1))

    def writes_business_state(claim):
        return PhaseExecutionResult(
            payload={"artifact_type": claim.phase_code}, business_writes=1
        )

    runner = CampaignRunner(
        state, handlers={code: writes_business_state for code in PHASE_CODES}
    )
    runner.run_phase("candidate_freeze", worker_id="fixture-worker")
    assert all(
        task.phases["candidate_freeze"].status == "failed"
        for task in state.tasks.values()
    )
    assert state.business_write_count == 0

    unsafe = manifest(1)
    unsafe["safety"]["formal_scoring"] = True
    with pytest.raises(CampaignContractError, match="offline/report-only/shadow-first"):
        build_campaign_state(unsafe)


def test_phase_concurrency_never_exceeds_manifest_limit() -> None:
    state = build_campaign_state(manifest(4))
    active = {"count": 0, "lock": threading.Lock()}
    peak = {"value": 0}
    barrier = threading.Barrier(4)
    runner = CampaignRunner(
        state, handlers=handlers(active=active, peak=peak, barrier=barrier)
    )
    runner.run_phase("candidate_freeze", worker_id="fixture-worker")
    assert peak["value"] == 4


def test_manifest_cli_writes_structured_plan_report(tmp_path) -> None:
    manifest_path = tmp_path / "campaign.yml"
    output_path = tmp_path / "plan.json"
    manifest_path.write_text(
        yaml.safe_dump(manifest(185), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    assert main(["--manifest", str(manifest_path), "--output", str(output_path)]) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert report["task_count"] == 925
    assert report["phase_work_item_count"] == 4625
    assert report["artifact_envelope_schema"]["additionalProperties"] is False
    assert all(
        row["failure_recovery"]["checkpoint_resume"] is True
        for row in report["tasks"]
    )
