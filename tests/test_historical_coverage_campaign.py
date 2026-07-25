from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import time

import pytest
import yaml

from emperor_v4.application.historical_coverage_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    CampaignContractError,
    CampaignRunner,
    CampaignState,
    ClaimedPhase,
    PHASE_CODES,
    PhaseExecutionResult,
    WORK_PACKAGE_SCHEMA_VERSION,
    WorkspaceCampaignHandlers,
    build_campaign_state,
    build_campaign_summary,
    main,
    run_workspace_campaign,
)
from emperor_v4.evaluation.i5b_candidate_retrieval_gate import (
    build_cross_rule_orphan_audit,
    validate_candidate_retrieval_gate,
)
from emperor_v4.evaluation.i5b_candidate_refreeze import build_candidate_refreeze
from emperor_v4.evaluation.i5b_appointment_projection_increment import (
    build_projection_increment,
)
from emperor_v4.evaluation.i5b_appointment_delegation_historical_scored_shadow import (
    build_appointment_historical_scored_shadow,
)
from emperor_v4.evaluation.i5b_formal_fact_acceptance import (
    build_formal_fact_acceptance,
    merge_formal_fact_acceptance,
)
from emperor_v4.evaluation.i5b_assertion_episode_trace import (
    build_assertion_episode_trace,
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
            "lease_seconds": 1200,
            "retry_delay_seconds": 0,
            "failure_policy": "fail_closed",
            "max_wall_clock_minutes": 15,
            "completion_reserve_seconds": 90,
            "max_network_requests": 10,
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


def write_workspace_packages(workspace, campaign_manifest):
    input_root = workspace / "inputs"
    input_root.mkdir(parents=True)
    reference = input_root / "reference.json"
    reference.write_text('{"status":"frozen"}\n', encoding="utf-8")
    state = build_campaign_state(campaign_manifest)
    for task in state.tasks.values():
        package_path = input_root / task.spec.ruler_code / f"{task.spec.rule_code}.json"
        package_path.parent.mkdir(parents=True, exist_ok=True)
        common = {"referenced_artifacts": ["inputs/reference.json"]}
        institution_status = "complete"
        orphan_audit = build_cross_rule_orphan_audit(
            target_rule_code=task.spec.rule_code,
            routed_passages=[],
            candidate_passage_refs=["SP-FIXTURE-001"],
        )
        retrieval_gate = {
            "schema_version": "i5b-candidate-retrieval-gate-v4",
            "rule_code": task.spec.rule_code.lower(),
            "input_versions": {
                "source_catalog_version": "catalog-v1",
                "source_cache_fingerprint": "cache-fingerprint-v1",
                "rule_semantics_version": "rule-v1",
                "retrieval_contract_version": "retrieval-v1",
                "scholarly_profile_version": "scholarly-profile-v1",
            },
            "trigger_reasons": ["initial_rule_requirement", "pre_closeout_audit"],
            "retrieval_lanes": {
                "person_event": {
                    "status": "complete",
                    "query_version": "person-event-v1",
                    "candidate_count": 1,
                    "judged_candidate_count": 1,
                    "unresolved_candidate_count": 0,
                },
                "institution_policy": {
                    "status": institution_status,
                    "query_version": "institution-policy-v1",
                    "candidate_count": 0,
                    "judged_candidate_count": 0,
                    "unresolved_candidate_count": 0,
                    "positive_query_count": 1,
                    "negative_query_count": 1,
                },
                "negative_counterexample": {
                    "status": "complete",
                    "query_version": "negative-v1",
                    "candidate_count": 0,
                    "judged_candidate_count": 0,
                    "unresolved_candidate_count": 0,
                },
                "cross_rule_orphan_audit": {
                    "status": "complete",
                    "query_version": "cross-rule-orphan-v1",
                    "candidate_count": 0,
                    "judged_candidate_count": 0,
                    "unresolved_candidate_count": 0,
                },
            },
            "disposition_audit": {
                "status": "complete",
                "candidate_count": 1,
                "judged_candidate_count": 1,
                "unresolved_candidate_count": 0,
            },
            "source_scope": {
                "chapter_inventory_frozen": True,
                "relevant_chapter_count": 1,
                "dispositioned_chapter_count": 1,
            },
            "cross_rule_orphan_audit": orphan_audit,
            "execution_audit": {
                "network_request_count": 0,
                "model_call_count": 0,
                "business_write_count": 0,
            },
            "scholar_guided_retrieval": {
                "status": "complete",
                "report_sha256": "a" * 64,
                "task_count": 1,
                "source_cache_routed_task_count": 1,
                "judge_bound_task_count": 1,
            },
            "human_freeze_accepted": True,
            "human_freeze_decision_ref": "HFD-FIXTURE-001",
        }
        payload = {
            "schema_version": WORK_PACKAGE_SCHEMA_VERSION,
            "ruler_code": task.spec.ruler_code,
            "rule_code": task.spec.rule_code,
            "input_version": task.spec.input_version,
            "phases": {
                "candidate_freeze": {
                    **common,
                    "candidate_count": 1,
                    "candidate_universe_frozen": True,
                    "retrieval_gate": retrieval_gate,
                },
                "source_recovery": {
                    **common,
                    "document_count": 1,
                    "passage_count": 1,
                    "assertion_draft_count": 1,
                    "source_cache_complete": True,
                },
                "acceptance": {
                    **common,
                    "accepted_unit_count": 1,
                    "accepted_assertion_count": 1,
                    "pending_blocking_review_unit_count": 0,
                },
                "persistence": {
                    **common,
                    "persistence_status": "verified_idempotent",
                    "idempotent_rerun_business_write_count": 0,
                    "formal_score_write": False,
                },
                "shadow_projection": {
                    **common,
                    "historical_coverage_status": "coverage_complete",
                    "formal_score": None,
                    "tier": None,
                    "ranking": None,
                },
            },
        }
        package_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return input_root


def test_185_by_five_manifest_expands_to_independent_stable_tasks() -> None:
    first = build_campaign_state(manifest(185))
    second = build_campaign_state(deepcopy(manifest(185)))

    assert len(first.tasks) == 925
    assert set(first.tasks) == set(second.tasks)
    assert len({task.spec.allowed_write_prefix for task in first.tasks.values()}) == 925
    assert all(len(task.spec.output_schemas) == 5 for task in first.tasks.values())
    assert all(task.phases["candidate_freeze"].status == "ready" for task in first.tasks.values())
    assert all(task.phases["source_recovery"].status == "blocked" for task in first.tasks.values())


def test_candidate_retrieval_gate_allows_observed_network_requests(
    tmp_path: Path,
) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    package_path = next(
        path for path in input_root.rglob("*.json") if path.name != "reference.json"
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))
    gate = package["phases"]["candidate_freeze"]["retrieval_gate"]
    gate["execution_audit"]["network_request_count"] = 3

    audit = validate_candidate_retrieval_gate(
        gate,
        rule_code=package["rule_code"],
    )

    assert audit["network_request_count"] == 3


def test_campaign_enforces_shared_per_ruler_network_budget(tmp_path: Path) -> None:
    state = build_campaign_state(manifest(1))
    handler = WorkspaceCampaignHandlers(
        state,
        workspace_root=tmp_path,
        input_root=tmp_path,
    )

    handler._reserve_network_requests(ruler_code="RULER_001", requested_count=6)
    handler._reconcile_network_reservation(
        ruler_code="RULER_001",
        reserved_count=6,
        actual_count=4,
    )
    handler._reserve_network_requests(ruler_code="RULER_001", requested_count=6)

    with pytest.raises(CampaignContractError, match="联网请求预算已耗尽"):
        handler._reserve_network_requests(
            ruler_code="RULER_001",
            requested_count=1,
        )
    restored = CampaignState.from_checkpoint(state.checkpoint())
    assert restored.ruler_network_request_count == {"RULER_001": 10}


def test_campaign_online_source_cache_observes_actual_network_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = build_campaign_state(manifest(1))
    task = next(iter(state.tasks.values()))
    claim = ClaimedPhase(
        task_code=task.spec.task_code,
        ruler_code=task.spec.ruler_code,
        rule_code=task.spec.rule_code,
        phase_code="source_recovery",
        run_id="RUN-ONLINE-1",
        attempt_number=1,
        input_version=task.spec.input_version,
        input_fingerprint=task.spec.input_fingerprint,
        allowed_write_prefix=task.spec.allowed_write_prefix,
        output_schema_version=task.spec.output_schemas["source_recovery"],
    )
    request_path = tmp_path / "inputs" / "request.yml"
    plan_path = tmp_path / "inputs" / "plan.yml"
    request_path.parent.mkdir(parents=True)
    request_path.write_text("request_id: test\n", encoding="utf-8")
    plan_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "provider": "wikisource_revision_plan",
                "subject_ref": "PER-1",
                "sections": [
                    {"page_code": "page-1"},
                    {"page_code": "page-2"},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    observed = []

    def fake_online_ensure(**kwargs):
        observed.append(kwargs)
        return {
            "response": {
                "status": "succeeded",
                "documents": [{"document_cache_id": "DOC-1"}],
                "passages": [{"passage_id": "PASSAGE-1"}],
                "output_fingerprint": "f" * 64,
            },
            "runtime_audit": {
                "cache_hit": len(observed) > 1,
                "network_request_count": 1 if len(observed) == 1 else 0,
                "model_call_count": 0,
            },
        }

    monkeypatch.setattr(
        "emperor_v4.runtime.source_cache.run_wikisource_ensure",
        fake_online_ensure,
    )
    handler = WorkspaceCampaignHandlers(
        state,
        workspace_root=tmp_path,
        input_root=tmp_path / "inputs",
    )
    job = {
        "source_request_ref": "inputs/request.yml",
        "source_plan_ref": "inputs/plan.yml",
    }

    first_response, first_audit = handler._run_source_cache_job(
        claim,
        job,
        job_index=0,
    )
    second_response, second_audit = handler._run_source_cache_job(
        claim,
        job,
        job_index=0,
    )

    assert first_response["status"] == second_response["status"] == "succeeded"
    assert first_audit["network_request_count"] == 1
    assert second_audit["network_request_count"] == 0
    assert state.ruler_network_request_count == {"RULER_001": 1}
    assert len(observed) == 2


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


def test_ruler_run_wall_clock_budget_stops_new_claims_across_all_rules() -> None:
    campaign_manifest = manifest(1)
    campaign_manifest["runtime"]["max_concurrency"] = 1
    for phase in campaign_manifest["phases"]:
        phase["max_concurrency"] = 1
    state = build_campaign_state(campaign_manifest)
    started_at = datetime(2026, 7, 16, tzinfo=timezone.utc)
    now = [started_at]

    def consume_budget(claim):
        now[0] = started_at + timedelta(minutes=15)
        return PhaseExecutionResult(
            payload={"artifact_type": claim.phase_code, "fixture_result": "bounded"}
        )

    runner = CampaignRunner(
        state,
        handlers={code: consume_budget for code in PHASE_CODES},
        clock=lambda: now[0],
        ruler_wall_clock_minutes=15,
    )

    assert runner.run_phase("candidate_freeze", worker_id="budget-worker") == 0
    assert runner.budget_exhausted is True
    assert runner.exhausted_ruler_codes == {"RULER_001"}
    statuses = [
        task.phases["candidate_freeze"].status for task in state.tasks.values()
    ]
    assert statuses.count("succeeded") == 0
    assert statuses.count("ready") == 5
    checkpoint = state.checkpoint()
    assert checkpoint["wall_clock_budget"]["ruler_started_at"]["RULER_001"] == (
        started_at.isoformat()
    )
    assert checkpoint["wall_clock_budget"]["ruler_deadlines"]["RULER_001"] == (
        started_at + timedelta(minutes=15)
    ).isoformat()

    restored = CampaignState.from_checkpoint(checkpoint)
    resumed_calls = []
    resumed = CampaignRunner(
        restored,
        handlers=handlers(calls=resumed_calls),
        clock=lambda: now[0],
        ruler_wall_clock_minutes=15,
    )
    assert resumed.run_phase("candidate_freeze", worker_id="resume-worker") == 0
    assert resumed_calls == []
    assert restored.ruler_deadlines["RULER_001"] == started_at + timedelta(minutes=15)


def test_non_cooperative_handler_does_not_hold_runner_past_hard_deadline() -> None:
    campaign_manifest = manifest(1)
    campaign_manifest["runtime"]["max_concurrency"] = 1
    for phase in campaign_manifest["phases"]:
        phase["max_concurrency"] = 1
    state = build_campaign_state(campaign_manifest)
    handler_finished = threading.Event()

    def blocks_past_deadline(claim):
        try:
            time.sleep(0.2)
            return PhaseExecutionResult(
                payload={"artifact_type": claim.phase_code, "fixture_result": "late"}
            )
        finally:
            handler_finished.set()

    runner = CampaignRunner(
        state,
        handlers={code: blocks_past_deadline for code in PHASE_CODES},
        ruler_wall_clock_seconds=0.05,
    )
    started = time.monotonic()
    completed = runner.run_phase("candidate_freeze", worker_id="deadline-worker")
    elapsed = time.monotonic() - started

    assert completed == 0
    assert elapsed < 0.15
    assert runner.budget_exhausted is True
    assert all(
        task.phases["candidate_freeze"].status == "ready"
        for task in state.tasks.values()
    )
    assert all(
        task.phases["candidate_freeze"].last_error
        == "wall_clock_budget_exhausted:hard_deadline_reached_while_handler_running"
        for task in state.tasks.values()
        if task.phases["candidate_freeze"].attempt_count
    )
    assert handler_finished.wait(timeout=1)
    assert not state.artifacts


def test_completion_reserve_stops_new_claims_and_keeps_finished_result() -> None:
    campaign_manifest = manifest(1)
    campaign_manifest["runtime"]["max_concurrency"] = 1
    for phase in campaign_manifest["phases"]:
        phase["max_concurrency"] = 1
    state = build_campaign_state(campaign_manifest)
    started_at = datetime(2026, 7, 16, tzinfo=timezone.utc)
    now = [started_at]

    def reaches_reserve(claim):
        now[0] = started_at + timedelta(minutes=13, seconds=30)
        return PhaseExecutionResult(
            payload={"artifact_type": claim.phase_code, "fixture_result": "on-time"}
        )

    runner = CampaignRunner(
        state,
        handlers={code: reaches_reserve for code in PHASE_CODES},
        clock=lambda: now[0],
        ruler_wall_clock_minutes=15,
        completion_reserve_seconds=90,
    )

    assert runner.run_phase("candidate_freeze", worker_id="reserve-worker") == 1
    assert runner.budget_exhausted is True
    statuses = [
        task.phases["candidate_freeze"].status for task in state.tasks.values()
    ]
    assert statuses.count("succeeded") == 1
    assert statuses.count("ready") == 4
    assert len(state.artifacts) == 1


def test_campaign_rejects_completion_reserve_that_consumes_whole_budget() -> None:
    campaign_manifest = manifest(1)
    campaign_manifest["runtime"]["completion_reserve_seconds"] = 900
    with pytest.raises(CampaignContractError, match="completion_reserve_seconds"):
        build_campaign_state(campaign_manifest)


def test_campaign_rejects_tracked_phase_artifact_root() -> None:
    campaign_manifest = manifest(1)
    campaign_manifest["artifact_root"] = "eval/i5b_historical_coverage/campaign"
    with pytest.raises(CampaignContractError, match="tmp"):
        build_campaign_state(campaign_manifest)


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
    now += timedelta(seconds=1201)
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
    with pytest.raises(CampaignContractError, match="report-only/shadow-first"):
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


def test_workspace_campaign_writes_artifacts_checkpoint_and_zero_work_resume(tmp_path) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    checkpoint = tmp_path / "checkpoint.json"
    summary = tmp_path / "summary.json"

    first = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=checkpoint,
        summary_path=summary,
        worker_id="workspace-worker",
    )
    artifact_files = list(
        (tmp_path / "tmp/i5b_historical_coverage_campaign").rglob("*.json")
    )
    assert first["completed_phase_count"] == 25
    assert first["summary_gate_status"] == "passed"
    assert first["model_call_count"] == 0
    assert first["business_write_count"] == 0
    assert first["max_wall_clock_minutes"] == 15
    assert first["completion_reserve_seconds"] == 90
    assert first["wall_clock_budget_exhausted"] is False
    assert len(artifact_files) == 25

    second = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=checkpoint,
        summary_path=summary,
        worker_id="resume-worker",
        resume=True,
    )
    assert second["completed_phase_count"] == 0
    assert second["summary_gate_status"] == "passed"
    assert json.loads(summary.read_text(encoding="utf-8"))["gate"]["status"] == "passed"


def test_successful_workspace_campaign_deletes_ephemeral_runtime_artifacts(
    tmp_path: Path,
) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    checkpoint = tmp_path / "tmp/i5b_historical_coverage/run/checkpoint.json"
    summary = tmp_path / "logs/i5b_historical_coverage/latest-summary.json"

    execution = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=checkpoint,
        summary_path=summary,
        worker_id="workspace-worker",
        cleanup_on_success=True,
    )

    assert execution["summary_gate_status"] == "passed"
    assert execution["runtime_artifacts_cleaned"] is True
    assert checkpoint.exists() is False
    assert list((tmp_path / "tmp/i5b_historical_coverage_campaign").rglob("*.json")) == []
    assert summary.is_file()


def test_workspace_campaign_resume_rejects_manifest_drift_and_tampered_artifact(tmp_path) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    checkpoint = tmp_path / "checkpoint.json"
    summary = tmp_path / "summary.json"
    run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=checkpoint,
        summary_path=summary,
        worker_id="workspace-worker",
    )

    drifted = deepcopy(campaign_manifest)
    drifted["input_version"] = "campaign-input-v2"
    with pytest.raises(CampaignContractError, match="checkpoint 与 manifest 不匹配"):
        run_workspace_campaign(
            manifest=drifted,
            workspace_root=tmp_path,
            input_root=input_root,
            checkpoint_path=checkpoint,
            summary_path=summary,
            worker_id="resume-worker",
            resume=True,
        )

    artifact = next(
        (tmp_path / "tmp/i5b_historical_coverage_campaign").rglob("*.json")
    )
    artifact.write_text('{"status":"tampered"}\n', encoding="utf-8")
    with pytest.raises(CampaignContractError, match="checkpoint artifact 被篡改"):
        run_workspace_campaign(
            manifest=campaign_manifest,
            workspace_root=tmp_path,
            input_root=input_root,
            checkpoint_path=checkpoint,
            summary_path=summary,
            worker_id="resume-worker",
            resume=True,
        )


def test_workspace_handler_fails_closed_on_blocking_acceptance(tmp_path) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    package_path = next(input_root.rglob("*.json"))
    if package_path.name == "reference.json":
        package_path = next(path for path in input_root.rglob("*.json") if path.name != "reference.json")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["phases"]["acceptance"]["pending_blocking_review_unit_count"] = 1
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    execution = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=tmp_path / "checkpoint.json",
        summary_path=tmp_path / "summary.json",
        worker_id="workspace-worker",
    )
    assert execution["summary_gate_status"] == "failed_closed"
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert any(
        row["phases"]["acceptance"]["status"] == "failed"
        for row in checkpoint["tasks"]
    )


def test_workspace_handler_fails_closed_before_freeze_on_unresolved_orphan(
    tmp_path: Path,
) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    package_path = next(
        path
        for path in input_root.rglob("*.json")
        if path.name == "TALENT_DISCOVERY.json"
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))
    audit = package["phases"]["candidate_freeze"]["retrieval_gate"][
        "cross_rule_orphan_audit"
    ]
    audit["unresolved_orphan_count"] = 1
    audit["unresolved_orphans"] = [
        {
            "passage_ref": "SP-WEIZHENG-DISCOVERY",
            "accepted_rules": ["appointment_delegation"],
            "eligible_rules": ["appointment_delegation", "talent_discovery"],
            "reason": "eligible_cross_rule_passage_missing_candidate_binding",
        }
    ]
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    execution = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=tmp_path / "checkpoint.json",
        summary_path=tmp_path / "summary.json",
        worker_id="workspace-worker",
    )

    assert execution["summary_gate_status"] == "failed_closed"
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    failed = next(
        row
        for row in checkpoint["tasks"]
        if row["spec"]["rule_code"] == "TALENT_DISCOVERY"
    )
    assert failed["phases"]["candidate_freeze"]["status"] == "failed"
    assert all(
        failed["phases"][phase]["status"] == "blocked_upstream_failed"
        for phase in PHASE_CODES[1:]
    )


def test_workspace_handler_fails_closed_before_freeze_on_unjudged_candidate(
    tmp_path: Path,
) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    package_path = next(
        path for path in input_root.rglob("*.json") if path.name == "TALENT_DISCOVERY.json"
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))
    gate = package["phases"]["candidate_freeze"]["retrieval_gate"]
    gate["retrieval_lanes"]["person_event"]["judged_candidate_count"] = 0
    gate["retrieval_lanes"]["person_event"]["unresolved_candidate_count"] = 1
    gate["disposition_audit"]["judged_candidate_count"] = 0
    gate["disposition_audit"]["unresolved_candidate_count"] = 1
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    execution = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=tmp_path / "checkpoint.json",
        summary_path=tmp_path / "summary.json",
        worker_id="workspace-worker",
    )
    assert execution["summary_gate_status"] == "failed_closed"


def test_workspace_handler_rejects_empty_completed_source_cache(tmp_path: Path) -> None:
    campaign_manifest = manifest(1)
    input_root = write_workspace_packages(tmp_path, campaign_manifest)
    package_path = next(
        path for path in input_root.rglob("*.json") if path.name == "TALENT_DISCOVERY.json"
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["phases"]["source_recovery"]["document_count"] = 0
    package["phases"]["source_recovery"]["passage_count"] = 0
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    execution = run_workspace_campaign(
        manifest=campaign_manifest,
        workspace_root=tmp_path,
        input_root=input_root,
        checkpoint_path=tmp_path / "checkpoint.json",
        summary_path=tmp_path / "summary.json",
        worker_id="workspace-worker",
    )
    assert execution["summary_gate_status"] == "failed_closed"


def test_candidate_refreeze_requires_exact_pending_closure() -> None:
    inventory = {
        "candidate_inventory": [
            {"event_group_key": "CEG-1", "final_disposition": "advance_to_source_rebind"}
        ]
    }
    decisions = {
        "schema_version": "i5b-candidate-refreeze-decisions-v1",
        "decision_ref": "HFD-1",
        "decisions": [
            {
                "event_group_key": "CEG-1",
                "final_disposition": "accepted_new_formal_episode",
                "judge_rationale": "完整回源后人工接受。",
                "source_passage_refs": ["SP-1"],
            }
        ],
    }
    frozen = build_candidate_refreeze(inventory=inventory, decisions=decisions)
    assert frozen["historical_coverage_complete"] is True
    assert frozen["refreeze"]["unresolved_candidate_count"] == 0
    with pytest.raises(ValueError, match="do not close pending inventory"):
        build_candidate_refreeze(
            inventory=inventory,
            decisions={**decisions, "decisions": []},
        )


def test_projection_increment_requires_reviewed_formal_unit_and_complete_factors() -> None:
    formal = {
        "units": [
            {
                "formal_acceptance_basis": "CEG-1",
                "projection_disposition": "projected",
                "unit_ref": "REU-1",
                "assertion_drafts": [{"assertion_code": "AST-1"}],
            }
        ]
    }
    decision = {
        "schema_version": "i5b-appointment-projection-decisions-v1",
        "input_version": "projection-v1",
        "units": [
            {
                "candidate_code": "CEG-1",
                "material_code": "MAT-1",
                "object_ref": "PER-1",
                "person": "甲",
                "reason": "人工冻结接受。",
                "factor_options": {
                    "appointment_effect": "normal_success",
                    "appointment_importance": "major_affairs",
                    "attribution_factor": "direct",
                    "context_factor": "core_mechanism_direct",
                    "continuity_factor": "stable",
                    "source_factor": "complete_direct_chain",
                },
            }
        ],
    }
    projected = build_projection_increment(
        base={"units": []}, formal_acceptance=formal, decisions=decision
    )
    assert projected["units"][0]["unit_ref"] == "REU-1"
    assert set(projected["units"][0]["factor_materials"][0]["factors"]) == {
        "appointment_effect",
        "appointment_importance",
        "attribution_factor",
        "context_factor",
        "continuity_factor",
        "source_factor",
    }


def test_formal_acceptance_merge_rejects_duplicate_units() -> None:
    base = {
        "schema_version": "formal-v1",
        "profile_code": "I5B",
        "rule_code": "appointment_delegation",
        "ruler": "李世民",
        "scope": {"start": 626, "end": 649},
        "units": [{"unit_ref": "REU-1", "assertion_drafts": []}],
        "summary": {},
    }
    with pytest.raises(ValueError, match="duplicates unit_ref"):
        merge_formal_fact_acceptance(base=base, increment=deepcopy(base))


def test_appointment_shadow_traces_formal_unit_without_auto_projection() -> None:
    unit_ref = "REU-TEST-INSUFFICIENT-PROJECTION"
    formal = {
        "profile_code": "appointment_delegation_chain_v1",
        "scope": {"ruler_ref": "PER-V4-LISHIMIN"},
        "summary": {"pending_blocking_review_unit_count": 0},
        "declarations": {"formal_fact_acceptance": True},
        "units": [
        {
            "unit_ref": unit_ref,
            "subject": "测试对象",
            "assertion_drafts": [
                    {
                        "assertion_code": "AST-TEST-INSUFFICIENT",
                        "assertion_type": "event_fact",
                        "event_node_ref": "EVN-TEST-INSUFFICIENT",
                        "source_passage_ref": "SP-TEST-INSUFFICIENT",
                        "subject": "李世民",
                        "predicate": "正式事实已接受",
                        "object": "测试对象",
                        "time_expression": "贞观初",
                        "location_expression": None,
                        "qualifiers": {
                            "candidate_focal_person_refs": ["PER-TEST-OBJECT"],
                            "evaluation_context": "PER-V4-LISHIMIN",
                            "episode_type": "political_action",
                            "outcome": "形成可核验结果",
                        },
                        "polarity": "asserted",
                        "source_attribution": {},
                        "confidence": 1.0,
                        "passage_support": {
                            "support_mode": "single_passage",
                            "assertion_semantic_key": "ASK-TEST-INSUFFICIENT",
                            "binding_provenance": {},
                            "supported_fields": ["identity", "action"]
                        },
                    "ambiguity_flags": [],
                    "remaining_uncertainties": [],
                }
            ],
            "review_disposition": "formally_accepted",
            "remaining_uncertainties": [],
        }
        ],
    }
    projection = {
        "schema_version": "i5b-appointment-delegation-historical-projection-input-v1",
        "status": "human_frozen_historical_closeout_input",
        "rule_code": "appointment_delegation",
        "units": [
        {
            "unit_ref": unit_ref,
            "ruler": "李世民",
            "person": "测试对象",
            "side": "positive",
            "status": "insufficient_projection",
            "object_ref": "PER-TEST-OBJECT",
            "canonical_event_group": "EVN-TEST-INSUFFICIENT",
            "projection_basis": "只验证正式事实 trace，不自动生成因子材料。",
            "missing_inputs": ["human_frozen_factor_materials"],
        }
        ],
    }
    report = build_appointment_historical_scored_shadow(
        projection_payload=projection,
        formal_acceptance=formal,
    )
    assert report["summary"]["insufficient_projection_count"] == 1
    assert report["insufficient_projections"][0]["unit_ref"] == unit_ref
    assert report["summary"]["judgment_count"] == 0


def test_formal_episode_identity_is_neutral_across_rule_projections() -> None:
    assertion = {
        "assertion_code": "AST-NEUTRAL-EPISODE",
        "assertion_type": "event_fact",
        "event_node_ref": "EVN-NEUTRAL-EPISODE",
        "source_passage_ref": "SP-NEUTRAL-EPISODE",
        "subject": "李世民",
        "predicate": "任命并授权",
        "object": "房玄龄主持中枢政务",
        "time_expression": "贞观元年",
        "location_expression": None,
        "qualifiers": {
            "candidate_focal_person_refs": ["PER-FANG-XUANLING"],
            "evaluation_context": "PER-LI-SHIMIN",
            "episode_type": "political_action",
            "office_or_domain": "中枢政务",
            "outcome": "中枢政务持续运转",
        },
        "polarity": "asserted",
        "source_attribution": {},
        "confidence": 1.0,
        "passage_support": {
            "support_mode": "single_passage",
            "assertion_semantic_key": "ASK-NEUTRAL-EPISODE",
            "binding_provenance": {},
            "supported_fields": ["identity", "action", "outcome"],
        },
        "ambiguity_flags": [],
    }

    def run(rule_code: str) -> dict:
        unit_ref = f"REU-{rule_code}"
        return build_assertion_episode_trace(
            rule_code=rule_code,
            trace_units=[
                {
                    "unit_ref": unit_ref,
                    "side": "positive",
                    "projection_basis": "同一历史事实的规则投影",
                }
            ],
            assertion_payload={
                "schema_version": "i5b-formal-fact-acceptance-v3",
                "profile_code": f"{rule_code}_chain_v1",
                "scope": {"ruler_ref": "PER-LI-SHIMIN"},
                "summary": {"pending_blocking_review_unit_count": 0},
                "declarations": {"formal_fact_acceptance": True},
                "units": [
                    {
                        "unit_ref": unit_ref,
                        "assertion_drafts": [deepcopy(assertion)],
                        "review_disposition": "formally_accepted",
                    }
                ],
                "report_sha256": "accepted-facts-v3",
            },
        )

    appointment = run("appointment_delegation")
    team = run("team_building")
    appointment_episode = appointment["episodes"][0]
    team_episode = team["episodes"][0]
    assert appointment_episode["episode_id"] == team_episode["episode_id"]
    assert appointment_episode["episode_type"] == "political_action"
    assert appointment_episode["provenance"]["builder"] == "deterministic_episode_kernel_v1"
    assert "unit_ref" not in appointment_episode["lineage"]
    assert appointment["rule_evidence_units"][0]["rule_code"] == "appointment_delegation"
    assert team["rule_evidence_units"][0]["rule_code"] == "team_building"


def test_formal_episode_merges_distinct_rule_hints_for_same_neutral_fact() -> None:
    assertions = []
    for suffix in ("A", "B"):
        assertions.append(
            {
                "assertion_code": f"AST-SAME-FACT-{suffix}",
                "assertion_type": "event_fact",
                "event_node_ref": f"EVN-RULE-HINT-{suffix}",
                "source_passage_ref": f"SP-SAME-FACT-{suffix}",
                "subject": "李世民",
                "predicate": "任命并授权",
                "object": "房玄龄主持中枢政务",
                "time_expression": "贞观元年",
                "location_expression": None,
                "qualifiers": {
                    "candidate_focal_person_refs": ["PER-FANG-XUANLING"],
                    "evaluation_context": "PER-LI-SHIMIN",
                    "episode_type": "political_action",
                    "office_or_domain": "中枢政务",
                    "outcome": "中枢政务持续运转",
                },
                "polarity": "asserted",
                "source_attribution": {},
                "confidence": 1.0,
                "passage_support": {
                    "support_mode": "single_passage",
                    "assertion_semantic_key": f"ASK-SAME-FACT-{suffix}",
                    "binding_provenance": {},
                    "supported_fields": ["identity", "action", "outcome"],
                },
                "ambiguity_flags": [],
            }
        )
    units = [
        {
            "unit_ref": f"UNIT-{suffix}",
            "assertion_drafts": [assertion],
            "review_disposition": "formally_accepted",
        }
        for suffix, assertion in zip(("A", "B"), assertions, strict=True)
    ]
    report = build_assertion_episode_trace(
        rule_code="appointment_delegation",
        trace_units=[
            {
                "unit_ref": f"UNIT-{suffix}",
                "side": "positive",
                "projection_basis": "同一史实的不同规则边界提示",
            }
            for suffix in ("A", "B")
        ],
        assertion_payload={
            "schema_version": "i5b-formal-fact-acceptance-v3",
            "profile_code": "appointment_delegation_chain_v1",
            "scope": {"ruler_ref": "PER-LI-SHIMIN"},
            "summary": {"pending_blocking_review_unit_count": 0},
            "declarations": {"formal_fact_acceptance": True},
            "units": units,
            "report_sha256": "same-neutral-fact-v3",
        },
    )

    assert report["episode_count"] == 1
    assert len(report["episodes"][0]["assertion_links"]) == 2
    episode_refs = {
        next(
            member["member_ref"]
            for member in unit["members"]
            if member["member_type"] == "episode"
        )
        for unit in report["rule_evidence_units"]
    }
    assert episode_refs == {report["episodes"][0]["episode_id"]}


def test_formal_fact_acceptance_emits_neutral_assertion_contract() -> None:
    report = build_formal_fact_acceptance(
        reviewed_assertions={
            "profile_code": "appointment_delegation_chain_v1",
            "scope": {
                "rule_code": "appointment_delegation",
                "ruler": "李世民",
                "ruler_ref": "PER-LI-SHIMIN",
            },
            "summary": {"pending_blocking_review_unit_count": 0},
            "units": [],
            "report_sha256": "reviewed",
        },
        acceptance_decisions={
            "rule_code": "appointment_delegation",
            "ruler": "李世民",
            "existing_assertion_decisions": [],
            "accepted_assertions": [
                {
                    "assertion_code": "AST-NEUTRAL-ACCEPTANCE",
                    "decision": "accept",
                    "event_node_ref": "EVN-NEUTRAL-ACCEPTANCE",
                    "candidate_code": "CANDIDATE-NEUTRAL-ACCEPTANCE",
                    "passage_id": "SP-NEUTRAL-ACCEPTANCE",
                    "predicate": "任命并授权",
                    "object": "房玄龄主持中枢政务",
                    "outcome": "中枢政务持续运转",
                    "quoted_text": "任以政事",
                    "subject": "李世民",
                }
            ],
            "accepted_candidate_groups": [
                {
                    "candidate_code": "CANDIDATE-NEUTRAL-ACCEPTANCE",
                    "assertion_refs": ["AST-NEUTRAL-ACCEPTANCE"],
                    "minimum_sufficient_event_nodes": [
                        {"event_node_ref": "EVN-NEUTRAL-ACCEPTANCE"}
                    ],
                    "factor_support": {"importance": "critical"},
                }
            ],
            "report_sha256": "decisions",
        },
        unit_specs={
            "CANDIDATE-NEUTRAL-ACCEPTANCE": {
                "unit_ref": "REU-NEUTRAL-ACCEPTANCE",
                "subject": "房玄龄",
                "candidate_focal_person_refs": ["PER-FANG-XUANLING"],
                "projection_disposition": "eligible",
                "source_work": "旧唐书",
                "time_expression": "贞观元年",
                "office_or_domain": "中枢政务",
            }
        },
    )
    qualifiers = report["units"][0]["assertion_drafts"][0]["qualifiers"]
    assert qualifiers["evaluation_context"] == "PER-V4-737E2C4D60AC"
    assert qualifiers["episode_type"] == "political_action"
    assert qualifiers["outcome"] == "中枢政务持续运转"
    assert qualifiers["candidate_participant_roles"] == [
        ["PER-V4-737E2C4D60AC", "ruler"],
        ["PER-V4-C37ED24688F5", "focal_person"],
    ]
    assert "factor_support" not in qualifiers
