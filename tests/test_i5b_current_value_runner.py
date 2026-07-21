from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from threading import Event, Lock
import time

import pytest

from emperor_v4.evaluation.historical_outcome_cluster import (
    cluster_semantic_fingerprint,
)
from emperor_v4.adapters.historical_entity_identity import HistoricalEntityResolver
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex, build_local_source_index
from emperor_v4.evaluation.current_source_pack_compiler import (
    SCHEMA_VERSION as SOURCE_PACK_INCREMENT_SCHEMA_VERSION,
    apply_source_pack_increment,
    compile_source_pack_increment,
)
from emperor_v4.evaluation.i5b_current_value_runner import (
    build_i5b_current_value,
    main as runner_main,
    render_scoring_detail_markdown,
)
from emperor_v4.eval import main as eval_main
from emperor_v4.runtime.emperor_rebuild import (
    RebuildLimits,
    _resolve_source_index,
    _run_with_model_anomaly_recovery,
)
from emperor_v4.runtime import (
    emperor_rebuild as emperor_rebuild_module,
    emperor_rebuild_queue,
    emperor_rebuild_worker,
)
from emperor_v4.runtime.emperor_neutral_scan import (
    NEUTRAL_EXTRACTION_POLICY_VERSION,
    _canonicalize_result,
    _digest as neutral_digest,
    build_backbone_event_signatures,
    build_event_directed_neutral_plan,
    build_ruler_neutral_plan,
    extract_current_neutral_materials,
    merge_dynasty_governance_current,
)
from emperor_v4.runtime.emperor_outcome_projection import (
    PROJECTION_POLICY_VERSION,
    project_current_outcomes,
)
from emperor_v4.runtime.structured_codex_runner import (
    ModelBatchAnomalyError,
    StructuredCodexRunner,
)


ROOT = Path(__file__).resolve().parents[1]


def test_structured_runner_timeout_terminates_tree_without_waiting_on_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HangingProcess:
        pid = 12345
        returncode = None

        def __init__(self) -> None:
            self.stdin = io.StringIO()
            self.stdout = io.StringIO()
            self.stderr = io.StringIO()
            self.communicate_calls = 0

        def communicate(self, **_kwargs: object) -> tuple[str, str]:
            self.communicate_calls += 1
            raise subprocess.TimeoutExpired("codex", 1)

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            self.returncode = -9

    process = HangingProcess()
    terminated: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(
        "emperor_v4.runtime.structured_codex_runner._terminate_process_tree",
        lambda value: terminated.append(value.pid),
    )
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=15,
        cwd=ROOT,
    )

    with pytest.raises(ModelBatchAnomalyError, match="熔断同批调用"):
        runner.run("test")

    assert terminated == [12345]
    assert process.communicate_calls >= 2


def test_emperor_rebuild_recovers_model_anomaly_with_fresh_smaller_runner() -> None:
    runners = []
    observed_batch_sizes = []

    class Runner:
        def __init__(self, number: int) -> None:
            self.number = number

    def runner_factory():
        runner = Runner(len(runners) + 1)
        runners.append(runner)
        return runner

    def operation(runner, batch_size: int):
        observed_batch_sizes.append(batch_size)
        if runner.number == 1:
            raise ModelBatchAnomalyError("测试异常")
        return "completed"

    result, recovery_count, final_batch_size = _run_with_model_anomaly_recovery(
        runner_factory=runner_factory,
        operation=operation,
        initial_batch_size=8,
    )

    assert result == "completed"
    assert recovery_count == 1
    assert final_batch_size == 4
    assert observed_batch_sizes == [8, 4]
    assert len(runners) == 2


def test_background_emperor_worker_exports_and_reuses_current_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = tmp_path / "LIUBANG-CALIBRATION.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": "emperor-rebuild-background-request-v1",
                "task_code": "LIUBANG-CALIBRATION",
                "ruler": "刘邦",
                "limits": {"wall_clock_seconds": 900},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        emperor_rebuild_worker,
        "rebuild_emperor",
        lambda **kwargs: calls.append(kwargs)
        or {
            "schema_version": "emperor-rebuild-v1",
            "status": "rebuilt_before_database_write",
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
    )

    arguments = {
        "request_path": request,
        "release_root": ROOT,
        "state_root": tmp_path / "state",
        "source_index_root": tmp_path / "indexes",
        "dynasty_governance_root": tmp_path / "governance",
    }
    first = emperor_rebuild_worker.run_background_request(**arguments)
    second = emperor_rebuild_worker.run_background_request(**arguments)

    assert first["status"] == "succeeded"
    assert first["reused"] is False
    assert second["status"] == "succeeded"
    assert second["reused"] is True
    assert len(calls) == 1
    assert calls[0]["source_index_path"] is None
    exports = Path(first["exports"])
    assert (exports / "scoring-detail.md").is_file()
    assert len(list((exports / "persons").glob("*.md"))) == 10

    copied_config = (
        tmp_path
        / "state/jobs/LIUBANG-CALIBRATION/workspace/config/project.yml"
    )
    copied_config.chmod(stat.S_IREAD)
    checkpoint_probe = (
        tmp_path
        / "state/jobs/LIUBANG-CALIBRATION/runtime/checkpoint/keep.txt"
    )
    checkpoint_probe.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_probe.write_text("audited checkpoint", encoding="utf-8")
    changed_request = json.loads(request.read_text(encoding="utf-8"))
    changed_request["limits"]["wall_clock_seconds"] = 899
    request.write_text(
        json.dumps(changed_request, ensure_ascii=False), encoding="utf-8"
    )
    third = emperor_rebuild_worker.run_background_request(**arguments)

    assert third["status"] == "succeeded"
    assert len(calls) == 2
    assert checkpoint_probe.read_text(encoding="utf-8") == "audited checkpoint"


def test_emperor_rebuild_does_not_require_preextracted_governance_works_in_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "config", workspace / "config")
    shutil.copytree(
        ROOT / "eval/i5b_current_value/李世民",
        workspace / "eval/i5b_current_value/李世民",
    )
    observed = {}

    def resolve(**kwargs):
        observed["required_works"] = kwargs["required_works"]
        raise RuntimeError("stop after index contract")

    monkeypatch.setattr(emperor_rebuild_module, "_resolve_source_index", resolve)
    with pytest.raises(RuntimeError, match="index contract"):
        emperor_rebuild_module.rebuild_emperor(
            workspace_root=workspace,
            ruler="李世民",
            source_index_path=None,
            source_index_root=tmp_path / "indexes",
            dynasty_governance_root=tmp_path / "governance",
            runtime_root=tmp_path / "runtime",
        )

    assert observed["required_works"] == ["資治通鑑", "舊唐書", "新唐書"]


def test_background_emperor_worker_marks_timeout_retryable_until_attempt_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = tmp_path / "RETRYABLE.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": "emperor-rebuild-background-request-v1",
                "task_code": "RETRYABLE",
                "ruler": "刘邦",
                "max_attempts": 2,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        emperor_rebuild_worker,
        "rebuild_emperor",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("model timeout")),
    )
    arguments = {
        "request_path": request,
        "release_root": ROOT,
        "state_root": tmp_path / "state",
        "source_index_root": tmp_path / "indexes",
        "dynasty_governance_root": tmp_path / "governance",
    }

    first = emperor_rebuild_worker.run_background_request(**arguments)
    second = emperor_rebuild_worker.run_background_request(**arguments)

    assert (first["attempt_count"], first["retryable"], first["terminal"]) == (
        1,
        True,
        False,
    )
    assert (second["attempt_count"], second["retryable"], second["terminal"]) == (
        2,
        False,
        True,
    )


def test_unattended_emperor_queue_processes_one_request_and_skips_terminal_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "state"
    requests = state_root / "requests"
    requests.mkdir(parents=True)
    for task_code in ("A-TERMINAL", "B-PENDING", "C-PENDING"):
        (requests / f"{task_code}.json").write_text("{}", encoding="utf-8")
    terminal = state_root / "jobs/A-TERMINAL/result.json"
    terminal.parent.mkdir(parents=True)
    terminal.write_text(
        json.dumps({"status": "failed", "terminal": True}), encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(
        emperor_rebuild_queue,
        "run_background_request",
        lambda **kwargs: calls.append(kwargs["request_path"].stem)
        or {"status": "failed", "retryable": True},
    )

    result = emperor_rebuild_queue.run_queue_tick(
        release_root=ROOT,
        state_root=state_root,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    assert result == {
        "schema_version": "emperor-rebuild-background-queue-tick-v1",
        "status": "processed",
        "task_code": "B-PENDING",
        "job_status": "failed",
        "retryable": True,
    }
    assert calls == ["B-PENDING"]
    assert not (state_root / "queue.lock").exists()


def test_structured_runner_uses_twice_comparable_median_as_anomaly_limit() -> None:
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=120,
        cwd=ROOT,
    )
    runner._record_success(prompt_chars=6_000, elapsed_seconds=40)
    runner._record_success(prompt_chars=5_000, elapsed_seconds=50)

    assert runner._adaptive_timeout_seconds(5_500) == 90
    assert runner._adaptive_timeout_seconds(500) == 120


def test_structured_runner_stops_slow_peer_after_twice_normal_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema_version": "current-outcome-candidate-output-v1",
        "task_code": "TEST",
        "candidates": [],
        "rejections": [],
    }

    class TimedProcess:
        pid = 12345

        def __init__(self, output: Path) -> None:
            self.output = output
            self.returncode = None
            self.stdin = io.StringIO()
            self.stdout = io.StringIO()
            self.stderr = io.StringIO()
            self.started: float | None = None
            self.duration = 0.0
            self.label = ""

        def communicate(
            self, *, input: str | None = None, timeout: float = 0
        ) -> tuple[str, str]:
            if input is not None and self.started is None:
                self.label = input
                self.duration = 0.1 if "BATCH-AUTO-AAAA" in input else 2.0
                self.started = time.monotonic()
            if self.returncode is not None:
                return "", ""
            assert self.started is not None
            remaining = self.duration - (time.monotonic() - self.started)
            if remaining <= timeout:
                time.sleep(max(0.0, remaining))
                self.output.write_text(json.dumps(payload), encoding="utf-8")
                self.returncode = 0
                return "", ""
            time.sleep(timeout)
            raise subprocess.TimeoutExpired("codex", timeout)

        def poll(self):
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    processes: list[TimedProcess] = []

    def popen(command, **_kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        process = TimedProcess(output)
        processes.append(process)
        return process

    terminated: list[str] = []
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(
        "emperor_v4.runtime.structured_codex_runner._terminate_process_tree",
        lambda process: (terminated.append(process.label), process.kill()),
    )
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=10,
        cwd=ROOT,
    )

    started = time.monotonic()
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(runner.run, prompt)
            for prompt in ("BATCH-AUTO-AAAA", "BATCH-AUTO-BBBB")
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except ModelBatchAnomalyError as exc:
                errors.append(exc)

    assert time.monotonic() - started < 1.2
    assert len(errors) == 1
    assert terminated == ["BATCH-AUTO-BBBB"]
    assert "prompt_sha256=" in str(errors[0])
    assert "comparable_calls=1" in str(errors[0])
    assert "BATCH-AUTO-BBBB" in str(errors[0])


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_value_chain_is_complete_shadow_with_provisional_profiles(ruler: str) -> None:
    report = build_i5b_current_value(ROOT / "eval/i5b_current_value" / ruler / "source-pack.json")

    assert report["status"] == (
        "current_shadow_chain_complete_profile_values_provisional"
    )
    assert report["declarations"]["three_channel_materials_consumed"] is True
    assert report["declarations"]["linked_ruler_context_count"] > 0
    assert set(report["three_channel_input"]["channel_counts"]) == {
        "ruler_chronicle",
        "person_biography",
        "dynasty_governance",
    }
    assert report["declarations"]["episode_count"] > 0
    assert report["declarations"]["rule_evidence_unit_count"] > 0
    assert set(report["three_channel_disposition"]) == set(report["three_channel_input"]["channel_counts"])
    assert any(row["rule_code"] == "team_building" for row in report["rule_evidence_units"])
    assert report["declarations"]["database_write_count"] == 0
    assert report["declarations"]["formal_score_write_count"] == 0
    assert report["declarations"]["profile_material_coverage_complete"] is False
    assert report["declarations"]["profile_values_frozen"] is False
    assert report["declarations"]["profile_freeze_gate_passed"] is False
    assert report["declarations"]["formal_scoring_ready"] is False
    assert report["declarations"]["profile_member_with_open_gap_count"] == 0
    assert report["declarations"]["historical_outcome_cluster_count"] > 0
    assert report["declarations"]["campaign_outcome_count"] > 0
    assert report["declarations"]["governance_outcome_count"] > 0
    assert report["net_signal_status"] == "provisional_profile_inputs"
    assert all(
        row["value_status"] == "provisional_material_coverage_open"
        for row in report["profile_projection_review"]
    )
    assert all(not row["coverage_gaps"] for row in report["profile_projection_review"])
    assert report["declarations"]["score_45"] is None
    assert report["declarations"]["ranking"] is None
    assert report["net_signal"] == report["material_budget"]["summary"]["weighted_raw_signal"]
    assert {episode["episode_type"] for episode in report["episodes"]} >= {
        "ruler_person_governance_event", "campaign_outcome_chain", "governance_outcome_chain"
    }
    linked_episodes = [
        episode for episode in report["episodes"]
        if episode["lineage"].get("ruler_context_refs")
    ]
    assert linked_episodes
    assert all(
        any(link["relation"] == "corroborates" for link in episode["assertion_links"])
        for episode in linked_episodes
    )
    episode_member_refs = [
        member["member_ref"]
        for reu in report["rule_evidence_units"]
        for member in reu["members"]
        if member["member_type"] == "episode"
    ]
    assert len(episode_member_refs) > len(set(episode_member_refs))
    assert all(not any(key in episode for key in ("semantic_version", "evidence_version", "previous_status")) for episode in report["episodes"])


def test_current_li_shimin_corrections_follow_rule_documents() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    members = {row["person"]: row for row in pack["members"]}
    assert "long_term_stability" not in pack["team"]
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    team = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "team_building"
    )
    assert team["long_term_stability"] == "durable_multi_stage"
    assert team["functional_complementarity"] == "balanced_four"
    assert len(pack["team"]["stability_stages"]) == 3
    assert members["尉迟敬德"]["negative_talent_severity"] == "material"
    assert members["高士廉"]["negative_talent_severity"] == "material"
    assert members["尉迟敬德"]["profile_review"]["political_risk"]["evidence_refs"] == [
        "PFACT-LSM-YUCHI-COURT-ASSAULT"
    ]
    assert members["高士廉"]["profile_review"]["political_risk"]["evidence_refs"] == [
        "PFACT-LSM-GAOSHI-LIMITED-POWER-ABUSE"
    ]
    assert members["侯君集"]["profile_review"]["political_risk"]["evidence_refs"] == [
        "PFACT-LSM-HOUJUNJI-LOOTING-AND-CONSPIRACY"
    ]
    materials = {row["material_id"]: row for row in pack["materials"]}
    assert materials[
        "MAT-李世民-TT-ZHANGLIANG-WRONGFUL-EXECUTION-REVIEW-1"
    ]["factor_option_codes"]["target_fault_factor"] == "disputed_suspicion"
    assert materials["MAT-李世民-TT-WEIZHENG-CAREER-SUPPLEMENT-1"][
        "factor_option_codes"
    ]["expression_safety"] == "actively_protected_or_encouraged"
    institution = materials[
        "MAT-李世民-TT-ZHENGUAN-FORMAL-REMONSTRANCE-CHANNEL"
    ]
    assert institution["factor_option_codes"]["feedback_entry"] == (
        "institutionalized_feedback_entry"
    )
    assert len(institution["ruler_context_refs"]) >= 3
    assert all(
        row.get("public_power_effect") is True
        for row in pack["materials"]
        if row["rule_code"] == "anti_nepotism"
    )
    assert "MAT-李世民-AN-WEIZHENG-POSTHUMOUS-MARRIAGE" not in materials
    assert not any(
        row["rule_code"] == "appointment_delegation"
        and row["direction"] == "positive"
        for row in pack["materials"]
    )


def test_profile_and_outcome_changes_rebuild_downstream_materials(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    li_jing = next(
        row
        for row in payload["materials"]
        if row["material_id"] == "MAT-李世民-TD-LIJING-CROSS-BOUNDARY"
    )
    li_jing["factor_option_codes"]["talent_quality_factor"] = "top"
    li_jing["factor_values"]["talent_quality_factor"] = 1.45
    law = next(
        row
        for row in payload["outcome_registry"]["clusters"]
        if row["canonical_label"] == "贞观律令与刑罚体系修订"
    )
    law["payload"]["durable_cross_stage"] = False
    law["semantic_fingerprint"] = cluster_semantic_fingerprint(law)
    payload.pop("source_pack_sha256")
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = build_i5b_current_value(target)
    discovery = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "talent_discovery"
    )
    li_jing_result = next(
        row for row in discovery["settled_materials"] if row["subject"] == "李靖"
    )
    assert li_jing_result["factor_option_codes"]["talent_quality_factor"] == "historic"
    assert li_jing_result["factor_values"]["talent_quality_factor"] == "1.800000"
    appointment = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    law_rows = [
        row
        for row in appointment["settled_materials"]
        + appointment["supporting_only_materials"]
        if "贞观律令与刑罚体系修订" in row.get("fact", "")
    ]
    assert law_rows
    assert all(
        row["factor_option_codes"]["continuity_factor"] == "stable"
        for row in law_rows
    )


def test_anti_nepotism_requires_public_power_effect(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    material = next(
        row for row in payload["materials"] if row["rule_code"] == "anti_nepotism"
    )
    material["public_power_effect"] = False
    payload.pop("source_pack_sha256")
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="公共权力作用 Gate"):
        build_i5b_current_value(target)


def test_current_long_term_stability_is_derived_from_stage_coverage() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    li_team = next(
        row for row in li["material_budget"]["rules"] if row["rule_code"] == "team_building"
    )
    liu_team = next(
        row for row in liu["material_budget"]["rules"] if row["rule_code"] == "team_building"
    )
    assert (li_team["long_term_stability"], li_team["long_term_stability_factor"]) == (
        "durable_multi_stage",
        "1.200000",
    )
    assert (liu_team["long_term_stability"], liu_team["long_term_stability_factor"]) == (
        "managed_turnover",
        "1.100000",
    )


def test_source_pack_hash_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][0]["fact_summary"] += "篡改"
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        build_i5b_current_value(target)


def test_duplicate_settlement_event_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][1]["settlement_event_key"] = payload["materials"][0][
        "independence_key"
    ]
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="重复结算事件"):
        build_i5b_current_value(target)


def test_profile_values_cannot_freeze_before_material_coverage(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["profile_projection_gate"]["material_coverage_complete"] = False
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="材料覆盖未闭合"):
        build_i5b_current_value(target)


def test_profile_values_rebuild_missing_grade_registry_links(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["profile_projection_gate"]["material_coverage_complete"] = True
    payload["members"][0]["profile_review"]["talent_grade"]["rule_alignment"]["outcome_refs"] = []
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = build_i5b_current_value(target)
    rebuilt = next(
        row
        for row in report["profile_projection_review"]
        if row["person_ref"] == payload["members"][0]["person_ref"]
    )
    assert rebuilt["talent_grade_rule_alignment"]["rule_path"]
    assert rebuilt["profile_evidence_refs"]["talent_grade"]


def test_appointment_importance_comes_from_responsibility_not_result_scale(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    law = next(
        row
        for row in payload["outcome_registry"]["clusters"]
        if row["canonical_label"] == "贞观律令与刑罚体系修订"
    )
    for member in law["members"]:
        if member["actor_kind"] == "person" and member["role_code"] == "lead":
            member["delegated_responsibility"]["scope"] = "major_affairs"
    law["semantic_fingerprint"] = cluster_semantic_fingerprint(law)
    payload.pop("source_pack_sha256")
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = build_i5b_current_value(target)
    appointment = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    rows = [
        row
        for bucket in ("settled_materials", "supporting_only_materials")
        for row in appointment[bucket]
        if "贞观律令与刑罚体系修订" in row.get("fact", "")
    ]
    assert rows
    assert {row["factor_option_codes"]["appointment_importance"] for row in rows} == {"major_affairs"}
    assert {row["factor_option_codes"]["appointment_effect"] for row in rows} == {"exceptional_success"}


def test_governance_support_is_selected_by_current_result_quality() -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    team_reu = next(
        row for row in report["rule_evidence_units"] if row["rule_code"] == "team_building"
    )
    selected = {
        row["outcome_ref"]
        for row in team_reu["payload"]["governance_dispositions"]
        if row["disposition"] == "selected_team_result_support"
    }
    selected_labels = {
        row["canonical_label"]
        for row in report["historical_outcome_clusters"]
        if row["outcome_ref"] in selected
    }
    assert "房玄龄长期主持中枢政务" in selected_labels
    assert "贡举中以文体轻薄黜落知名候选人" not in selected_labels
    disposition_by_label = {
        next(
            cluster["canonical_label"]
            for cluster in report["historical_outcome_clusters"]
            if cluster["outcome_ref"] == row["outcome_ref"]
        ): row["disposition"]
        for row in report["governance_dispositions"]
    }
    assert disposition_by_label["建立州县义仓并用于饥馑赈给"] == (
        "excluded_no_preserved_positive_result"
    )
    assert disposition_by_label["贞观律令与刑罚体系修订"] == (
        "selected_team_result_support"
    )
    assert disposition_by_label["建立并扩充多层官学网络"] == (
        "supporting_policy_context_not_i5b_team_score"
    )


def test_representative_ruler_policies_render_with_current_disposition() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_rendered = render_scoring_detail_markdown(li)
    assert "| 功臣世袭刺史 | 正向 |" in li_rendered
    assert "| 皇子出任地方实职 | 未计入 |" in li_rendered
    assert "建立州县义仓并用于饥馑赈给" in li_rendered
    assert "专业目标已实现，整体混合结果及跨领域代价另行结算" in li_rendered
    assert "## 治理成果登记" in li_rendered
    assert "## 战役登记" in li_rendered
    assert "OUTCOME-3BE9F931EFCF2E191FE6" in li_rendered
    assert "李靖奇袭定襄破东突厥" in li_rendered
    assert any(
        row["canonical_label"] == "李勣攻克平壤平定高句丽"
        for row in li["historical_outcome_clusters"]
    )
    assert not any(
        row["canonical_label"] == "李勣攻克平壤平定高句丽"
        for row in li["historical_outcome_clusters"]
        if row["outcome_ref"] in set(li["ruler_historical_outcome_refs"])
    )
    appointment = next(
        row
        for row in li["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    assert not any(
        "李勣攻克平壤平定高句丽" in row.get("fact", "")
        for bucket in ("settled_materials", "supporting_only_materials")
        for row in appointment[bucket]
    )
    assert "魏徵家族婚约 | 负向" not in li_rendered
    assert "李靖临刑获救入幕、魏徵跨东宫转化" not in li_rendered

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    policy_contexts = {
        next(
            cluster["canonical_label"]
            for cluster in liu["historical_outcome_clusters"]
            if cluster["outcome_ref"] == row["outcome_ref"]
        )
        for row in liu["governance_dispositions"]
        if row["disposition"] == "supporting_policy_context_not_i5b_team_score"
    }
    assert policy_contexts == {"汉初约法轻租与财政节用", "疑狱逐级上报程序"}


def test_representative_military_materials_keep_three_channel_lineage() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_contexts = set(li["linked_ruler_context_refs"])
    assert "NMAT-900F470DB8A079C3F11F" in li_contexts
    assert "NMAT-2830CE53C58D4AF38E77" in li_contexts

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    appointment = next(
        row for row in liu["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    appointment_rows = [
        row
        for key in ("settled_materials", "supporting_only_materials")
        for row in appointment[key]
    ]
    positive_effects = {"normal_success", "major_success", "exceptional_success"}
    assert all(
        row["material_id"].startswith("MAT-AUTO-AD-")
        for row in appointment_rows
        if row["factor_option_codes"]["appointment_effect"] in positive_effects
    )
    assert any("周勃平定楚汉后方与燕代叛乱" in row["fact"] for row in appointment_rows)
    zhou_bo = next(
        row for row in liu["profile_projection_review"] if row["person"] == "周勃"
    )
    assert zhou_bo["candidate_negative_talent_severity"] == "serious"
    assert set(zhou_bo["profile_evidence_refs"]["political_risk"]) == {
        "PFACT-B16F3241641256A60A24",
        "PFACT-41CE7721509571B8E874",
    }


def test_current_value_cli_writes_only_current_result(tmp_path: Path) -> None:
    assert eval_main([
        "i5b-current-value",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(ROOT),
        "--output-dir",
        str(tmp_path),
    ]) == 0
    assert (tmp_path / "result.json").is_file()
    assert (tmp_path / "result.md").is_file()
    report = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    result_markdown = (tmp_path / "result.md").read_text(encoding="utf-8")
    assert result_markdown == render_scoring_detail_markdown(report)
    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |" in result_markdown
    assert "## 各臣子 Episode" not in result_markdown


def test_emperor_rebuild_limits_reject_runaway_concurrency() -> None:
    with pytest.raises(ValueError, match="史料召回并发"):
        RebuildLimits(source_workers=17)
    with pytest.raises(ValueError, match="导出并发"):
        RebuildLimits(export_workers=9)


def test_emperor_rebuild_resolves_current_index_from_runtime_root(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "current" / "source.sqlite3"
    built = build_local_source_index(
        [
            {
                "page_title": "甲书/卷1",
                "work_title": "甲书",
                "source_url": "local:1",
                "revision_ref": "1",
                "raw_text": "甲书人物治理事实",
            },
            {
                "page_title": "乙书/卷1",
                "work_title": "乙书",
                "source_url": "local:2",
                "revision_ref": "1",
                "raw_text": "乙书人物战役事实",
            },
        ],
        index_path,
    )
    source_pack = {
        "facts": [
            {"source_page": "甲书/卷1"},
            {"source_page": "乙书/卷1"},
        ]
    }

    resolved = _resolve_source_index(
        source_pack=source_pack,
        source_index_path=None,
        source_index_root=tmp_path,
    )

    assert resolved.identity == built["index_identity"]


def test_emperor_rebuild_index_resolution_requires_configured_backbone(
    tmp_path: Path,
) -> None:
    partial_path = tmp_path / "partial/source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": f"甲书/卷{position}",
                "work_title": "甲书",
                "source_url": f"local:partial:{position}",
                "revision_ref": "1",
                "raw_text": "甲书人物治理事实",
            }
            for position in range(3)
        ],
        partial_path,
    )
    complete_path = tmp_path / "complete/source.sqlite3"
    complete = build_local_source_index(
        [
            {
                "page_title": "甲书/卷1",
                "work_title": "甲书",
                "source_url": "local:complete:1",
                "revision_ref": "1",
                "raw_text": "甲书人物治理事实",
            },
            {
                "page_title": "编年书/卷1",
                "work_title": "编年书",
                "source_url": "local:complete:2",
                "revision_ref": "1",
                "raw_text": "编年书人物治理事实",
            },
        ],
        complete_path,
    )

    resolved = _resolve_source_index(
        source_pack={"facts": [{"source_page": "甲书/卷1"}]},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("编年书",),
    )

    assert resolved.identity == complete["index_identity"]


def test_emperor_rebuild_index_resolution_ignores_preextracted_governance_work(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "current/source.sqlite3"
    built = build_local_source_index(
        [
            {
                "page_title": "编年书/卷1",
                "work_title": "编年书",
                "source_url": "local:chronicle",
                "revision_ref": "1",
                "raw_text": "编年人物治理事实",
            }
        ],
        index_path,
    )

    resolved = _resolve_source_index(
        source_pack={"facts": [{"source_page": "政书/卷1"}]},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("编年书",),
        preextracted_works=("政书",),
    )

    assert resolved.identity == built["index_identity"]


def test_emperor_rebuild_index_resolution_compares_normalized_work_names(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "current/source.sqlite3"
    built = build_local_source_index(
        [
            {
                "page_title": "资治通鉴/卷1",
                "work_title": "资治通鉴",
                "source_url": "local:chronicle",
                "revision_ref": "1",
                "raw_text": "编年人物治理事实",
            }
        ],
        index_path,
    )

    resolved = _resolve_source_index(
        source_pack={"facts": []},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("資治通鑑",),
    )

    assert resolved.identity == built["index_identity"]


def test_neutral_result_canonicalization_only_binds_owned_facts_and_layout_quotes() -> None:
    batch = {
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "revision_ref": "1",
        "segments": [
            {
                "segment_ref": "SEG-1",
                "text": "甲\n乙",
                "subject_refs": ["PER-1"],
            }
        ],
    }
    result = {
        "schema_version": "shared-neutral-extraction-output-v1",
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "revision_ref": "1",
        "segment_count": 1,
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "reason": "raw",
                "facts": [
                    {
                        "fact_id": "F1",
                        "exact_quote": "甲乙",
                        "actors": [
                            {
                                "canonical_name": "人物甲",
                                "subject_ref": None,
                                "role": "executor",
                            }
                        ],
                    },
                    {
                        "fact_id": "F2",
                        "exact_quote": "甲",
                        "actors": [
                            {
                                "canonical_name": "旁人",
                                "subject_ref": "PER-WRONG",
                                "role": "executor",
                            }
                        ],
                    },
                ],
            }
        ],
        "limitations": [],
    }

    repaired = _canonicalize_result(
        batch, result, subject_ref_by_name={"人物甲": "PER-1"}
    )

    facts = repaired["segment_reviews"][0]["facts"]
    assert [row["fact_id"] for row in facts] == ["F1"]
    assert facts[0]["exact_quote"] == "甲\n乙"
    assert facts[0]["actors"][0]["subject_ref"] == "PER-1"


def test_historical_identity_resolver_prevents_lijing_liji_suffix_misbinding() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    liji = resolver.entity_for_name("李勣")
    lijing = resolver.entity_for_name("李靖")

    resolved = resolver.resolve(
        "勣", allowed_subject_refs=[liji.person_ref, lijing.person_ref]
    )

    assert resolved.status == "resolved"
    assert resolved.canonical_name == "李勣"
    assert "徐世勣" in resolver.recall_terms("李勣")
    assert "勣" not in resolver.recall_terms("李勣")
    assert resolver.resolve(
        "靖", allowed_subject_refs=[liji.person_ref, lijing.person_ref]
    ).canonical_name == "李靖"
    assert resolver.resolve(
        "静", allowed_subject_refs=[liji.person_ref, lijing.person_ref]
    ).status == "unresolved"

    batch = {
        "segments": [
            {
                "segment_ref": "S1",
                "text": "勣率兵平定其地。",
                "subject_refs": [liji.person_ref, lijing.person_ref],
            }
        ]
    }
    result = {
        "segment_reviews": [
            {
                "segment_ref": "S1",
                "decision": "accept",
                "reason": "raw",
                "facts": [
                    {
                        "exact_quote": "勣率兵平定其地。",
                        "actors": [
                            {
                                "source_name": "勣",
                                "canonical_name": "李靖",
                                "subject_ref": lijing.person_ref,
                                "role": "executor",
                            }
                        ],
                    }
                ],
            }
        ],
        "limitations": [],
    }
    repaired = _canonicalize_result(
        batch,
        result,
        subject_ref_by_name={"李靖": lijing.person_ref, "李勣": liji.person_ref},
        identity_resolver=resolver,
    )
    actor = repaired["segment_reviews"][0]["facts"][0]["actors"][0]
    assert actor["canonical_name"] == "李勣"
    assert actor["subject_ref"] == liji.person_ref


def test_neutral_plan_scans_whole_biography_by_event_unit_and_uses_small_context(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷67",
                "work_title": "舊唐書",
                "source_url": "local:67",
                "revision_ref": "1",
                "raw_text": (
                    "==李靖==\n李靖少有文武材略。\n\n"
                    "四年，靖陳十策以圖蕭銑，高祖從之。孝恭未更戎旅，三軍之任一以委靖。\n\n"
                    "六年，靖平輔公祏，江南遂定。"
                ),
            }
        ],
        index_path,
    )
    minimal_pack = {
        "ruler": source_pack["ruler"],
        "ruler_ref": source_pack["ruler_ref"],
        "members": [
            next(row for row in source_pack["members"] if row["person"] == "李靖")
        ],
    }
    plan = build_ruler_neutral_plan(
        source_pack=minimal_pack,
        source_index=LocalSourceTextIndex(index_path),
        inventory={
            "subjects": [{"subject": "李靖", "pages": ["舊唐書/卷67"]}]
        },
        identity_resolver=resolver,
    )

    segments = plan["page_batches"][0]["segments"]
    combined = "".join(row["initial_text"] for row in segments)
    assert "靖陳十策以圖蕭銑" in combined
    assert "靖平輔公祏" in combined
    assert all(len(row["initial_text"]) <= 420 for row in segments)


def test_event_directed_plan_uses_backbone_signature_to_target_other_works(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    ruler = source_pack["ruler"]
    member = next(row for row in source_pack["members"] if row["person"] == "李靖")
    minimal_pack = {
        "ruler": ruler,
        "ruler_ref": source_pack["ruler_ref"],
        "members": [member],
    }
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=minimal_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷193",
                "work_title": "資治通鑑",
                "source_url": "local:backbone",
                "revision_ref": "1",
                "raw_text": "貞觀四年，李靖統兵討伐突厥，平定其地。",
            },
            {
                "page_title": "資治通鑑/卷005",
                "work_title": "資治通鑑",
                "source_url": "local:ancient-qin",
                "revision_ref": "0",
                "raw_text": "秦王用范睢之謀，使五大夫綰伐魏。",
            },
            {
                "page_title": "舊唐書/卷67",
                "work_title": "舊唐書",
                "source_url": "local:old",
                "revision_ref": "2",
                "raw_text": "==李靖==\n貞觀四年，李靖統兵討伐突厥，平定其地。\n\n李靖少有文武材略。",
            },
            {
                "page_title": "新唐書/卷93",
                "work_title": "新唐書",
                "source_url": "local:new",
                "revision_ref": "3",
                "raw_text": "李靖討伐突厥，平定其地，遂班師。",
            },
            {
                "page_title": "貞觀政要/卷01",
                "work_title": "貞觀政要",
                "source_url": "local:supplement",
                "revision_ref": "4",
                "raw_text": "太宗命李靖討伐突厥，既而平定其地。",
            },
        ],
        index_path,
    )
    index = LocalSourceTextIndex(index_path)
    assert [
        page.page_title
        for page in index.iter_pages(
            works=["舊唐書"], page_titles=["舊唐書/卷67"]
        )
    ] == ["舊唐書/卷67"]
    assert list(index.iter_pages(works=["舊唐書"], page_titles=[])) == []
    assert {
        page.page_title
        for page in index.iter_pages_matching_terms(
            works=["舊唐書", "新唐書"], terms=["李靖"]
        )
    } == {"舊唐書/卷67", "新唐書/卷93"}
    backbone_plan = build_ruler_neutral_plan(
        source_pack=minimal_pack,
        source_index=index,
        inventory={
            "subjects": [
                {
                    "subject": ruler,
                    "pages": ["資治通鑑/卷005", "資治通鑑/卷193"],
                },
                {"subject": "李靖", "pages": ["資治通鑑/卷193"]},
            ]
        },
        identity_resolver=resolver,
        allowed_works=["資治通鑑"],
        allowed_page_ranges={"資治通鑑": [184, 199]},
    )
    assert {row["page_title"] for row in backbone_plan["page_batches"]} == {
        "資治通鑑/卷193"
    }
    segment = backbone_plan["page_batches"][0]["segments"][0]
    fact = {
        "fact_ref": "NEUTRALFACT-1",
        "segment_ref": segment["segment_ref"],
        "segment_text_sha256": segment["text_sha256"],
        "page_title": "資治通鑑/卷193",
        "work_title": "資治通鑑",
        "revision_ref": "1",
        "exact_quote": "貞觀四年，李靖統兵討伐突厥，平定其地。",
        "action_summary": "李靖统兵讨伐突厥。",
        "result": "平定其地。",
        "actors": [
            {
                "canonical_name": "李靖",
                "subject_ref": member["person_ref"],
                "role": "executor",
            }
        ],
    }
    backbone_materials = {"fanout": {"facts": [fact]}}

    signatures = build_backbone_event_signatures(
        backbone_plan=backbone_plan,
        backbone_materials=backbone_materials,
        identity_resolver=resolver,
    )
    assert len(signatures) == 1
    assert signatures[0]["chronology_anchors"] == ["贞观四年"]
    assert signatures[0]["subject_bindings"][0]["canonical_name"] == "李靖"
    assert signatures[0]["backbone_quotes"][0]["revision_ref"] == "1"

    directed = build_event_directed_neutral_plan(
        backbone_plan=backbone_plan,
        backbone_materials=backbone_materials,
        source_index=index,
        identity_resolver=resolver,
        backsource_works=["舊唐書", "新唐書"],
        supplement_works=["貞觀政要"],
    )
    targeted = [
        segment
        for batch in directed["page_batches"]
        for segment in batch["segments"]
        if segment.get("source_role")
    ]
    assert {row["source_role"] for row in targeted} == {"backsource", "supplement"}
    assert {batch["work_title"] for batch in directed["page_batches"]} == {
        "資治通鑑",
        "舊唐書",
        "新唐書",
        "貞觀政要",
    }
    assert all("李靖" in row["initial_text"] for row in targeted)
    assert len(directed["target_segment_event_bindings"]) == len(targeted)


def test_dynasty_governance_current_is_filtered_and_merged_without_model() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    subject_ref_by_name = {
        str(source_pack["ruler"]): str(source_pack["ruler_ref"]),
        **{
            str(row["person"]): str(row["person_ref"])
            for row in source_pack.get("members") or ()
        },
    }
    neutral = {
        "schema_version": "current-neutral-materials-v1",
        "fanout": {
            "facts": [],
            "person_fanout": [],
            "event_groups": [],
            "fact_count": 0,
            "person_count": 0,
        },
    }
    current = {
        "schema_version": "dynasty-governance-current-v1",
        "status": "quality_accepted_shadow",
        "dynasty": "唐",
        "dynasty_token": "TANG",
        "input_fingerprint": "DYNASTY-CURRENT-1",
        "source_index_identity": "INDEX-1",
        "chains": [
            {
                "chain_key": "zhenguan-law",
                "title": "贞观修律",
                "domain": "law_and_adjudication",
                "period": "贞观年间",
                "action": "太宗授权修订法律。",
                "implementation": "法律完成修订。",
                "observable_result": "新律颁行。",
                "operation_status": "implemented",
                "temporal_scope": "long_term_pattern",
                "actors": [
                    {
                        "name": "太宗",
                        "responsibility_role": "lead",
                        "contribution_phases": ["authorized"],
                        "role_basis": "原文记载太宗授权。",
                        "quote_refs": ["Q-1"],
                    }
                ],
                "evidence": [
                    {
                        "quote_ref": "Q-1",
                        "page_title": "貞觀政要/卷08",
                        "revision_ref": "1",
                        "exact_quote": "太宗授权修订法律并颁行天下。",
                    }
                ],
                "uncertainty": "",
            },
            {
                **{
                    "chain_key": "gaozong-law",
                    "title": "高宗修律",
                    "domain": "law_and_adjudication",
                    "period": "永徽年间",
                    "action": "修订法律。",
                    "implementation": "完成修订。",
                    "observable_result": "新律颁行。",
                    "operation_status": "implemented",
                    "temporal_scope": "long_term_pattern",
                    "actors": [],
                    "evidence": [],
                    "uncertainty": "",
                }
            },
        ],
    }

    merged = merge_dynasty_governance_current(
        neutral_materials=neutral,
        current=current,
        expected_dynasty_token="TANG",
        expected_source_index_identity="INDEX-1",
        period_terms=["贞观"],
        identity_resolver=resolver,
        subject_ref_by_name=subject_ref_by_name,
        event_signatures=[
            {
                "event_ref": "EVENT-TONGJIAN-LAW",
                "subject_bindings": [
                    {
                        "subject_ref": source_pack["ruler_ref"],
                        "canonical_name": "李世民",
                    }
                ],
                "chronology_anchors": ["贞观"],
                "location_anchors": [],
                "action_anchors": [],
                "result_anchors": [],
                "quote_anchors": [],
                "backbone_quotes": [
                    {"exact_quote": "太宗授权修订法律并颁行天下。"}
                ],
            }
        ],
    )
    repeated = merge_dynasty_governance_current(
        neutral_materials=merged,
        current=current,
        expected_dynasty_token="TANG",
        expected_source_index_identity="INDEX-1",
        period_terms=["贞观"],
        identity_resolver=resolver,
        subject_ref_by_name=subject_ref_by_name,
        event_signatures=[
            {
                "event_ref": "EVENT-TONGJIAN-LAW",
                "subject_bindings": [
                    {
                        "subject_ref": source_pack["ruler_ref"],
                        "canonical_name": "李世民",
                    }
                ],
                "chronology_anchors": ["贞观"],
                "location_anchors": [],
                "action_anchors": [],
                "result_anchors": [],
                "quote_anchors": [],
                "backbone_quotes": [
                    {"exact_quote": "太宗授权修订法律并颁行天下。"}
                ],
            }
        ],
    )

    assert repeated == merged
    assert merged["dynasty_governance_current"] == {
        "dynasty_token": "TANG",
        "input_fingerprint": "DYNASTY-CURRENT-1",
        "source_index_identity": "INDEX-1",
        "selected_chain_count": 1,
        "aligned_to_backbone_chain_count": 1,
        "fact_count": 1,
        "model_call_count": 0,
    }
    fact = merged["fanout"]["facts"][0]
    assert fact["source_role"] == "dynasty_governance"
    assert fact["actors"][0]["canonical_name"] == "李世民"
    assert fact["actors"][0]["role"] == "authorizer"
    assert fact["outcome_candidate_status"] == "ambiguous"
    assert fact["event_refs"] == ["EVENT-TONGJIAN-LAW"]

    with pytest.raises(ValueError, match="索引版本不一致"):
        merge_dynasty_governance_current(
            neutral_materials=neutral,
            current=current,
            expected_dynasty_token="TANG",
            expected_source_index_identity="INDEX-2",
            period_terms=["贞观"],
            identity_resolver=resolver,
            subject_ref_by_name=subject_ref_by_name,
        )


def test_seeded_invalid_neutral_segment_retries_without_fresh_page_group(
    tmp_path: Path,
) -> None:
    segment = {
        "segment_ref": "SEG-1",
        "start_offset": 0,
        "end_offset": 4,
        "text": "甲乙人物",
        "text_sha256": hashlib.sha256("甲乙人物".encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
    }
    batch = {
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    def fact(quote: str) -> dict:
        return {
            "fact_id": "F1",
            "exact_quote": quote,
            "fact_kind": "institutional_action",
            "action_summary": "人物实施事项",
            "actors": [
                {
                    "source_name": "人物",
                    "canonical_name": "人物",
                    "subject_ref": "PER-1",
                    "role": "executor",
                    "responsibility_strength": "primary",
                    "attribution_basis": "原文直载",
                }
            ],
            "implementation_status": "implemented",
            "result": "事项完成",
            "legacy_status": "not_shown",
            "legacy_basis": "",
                "projection_eligibility": "direct_neutral_fact",
                "outcome_candidate_status": "clear_candidate",
                "outcome_candidate_reason": "行动、结果和责任明确。",
                "uncertainty": "",
        }

    current_result = {
        "schema_version": "shared-neutral-extraction-output-v1",
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "revision_ref": "1",
        "segment_count": 1,
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "facts": [fact("不存在")],
                "reason": "raw",
            }
        ],
        "limitations": [],
    }

    class Runner:
        def run(self, prompt: str):
            input_batch = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])[0]
            compact_fact = fact("甲乙人物")
            for key in (
                "fact_id", "legacy_status", "legacy_basis", "projection_eligibility"
            ):
                compact_fact.pop(key)
            compact_fact["segment_ref"] = input_batch["segments"][0]["segment_ref"]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": input_batch["batch_ref"],
                            "facts": [compact_fact],
                            "context_requests": [],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    output = extract_current_neutral_materials(
        plan=plan,
        current={
            "batch_fingerprints": {
                "BATCH-1": neutral_digest(
                    {
                        "batch": batch,
                        "extraction_policy": NEUTRAL_EXTRACTION_POLICY_VERSION,
                    }
                )
            },
            "batch_results": [current_result],
        },
        runner=Runner(),
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=3,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 1
    assert (tmp_path / "checkpoint/BATCH-1.json").is_file()


def test_neutral_segment_reuse_survives_batch_regrouping(tmp_path: Path) -> None:
    segment = {
        "segment_ref": "SEG-STABLE",
        "start_offset": 0,
        "end_offset": 4,
        "text": "人物无事",
        "initial_text": "人物无事",
        "text_sha256": hashlib.sha256("人物无事".encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    new_batch = {
        "batch_ref": "BATCH-NEW",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-NEW",
        "page_batches": [new_batch],
    }
    current = {
        "batch_fingerprints": {"BATCH-OLD": "OLD"},
        "batch_results": [
            {
                "schema_version": "shared-neutral-extraction-output-v1",
                "batch_ref": "BATCH-OLD",
                "page_title": "史书/卷1",
                "revision_ref": "1",
                "segment_count": 1,
                "segment_reviews": [
                    {
                        "segment_ref": "SEG-STABLE",
                        "decision": "reject",
                        "context_status": "sufficient",
                        "facts": [],
                        "reason": "无直接中性事实。",
                    }
                ],
                "limitations": [],
            }
        ],
    }

    class NoCallRunner:
        def run(self, _prompt: str):
            raise AssertionError("稳定 segment 不应因 batch 重排重新调用模型")

    output = extract_current_neutral_materials(
        plan=plan,
        current=current,
        runner=NoCallRunner(),
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert output["model_call_count"] == 0
    assert output["batch_results"][0]["batch_ref"] == "BATCH-NEW"
    assert output["fanout"]["fact_count"] == 0


def test_compact_sparse_output_can_omit_an_empty_batch(tmp_path: Path) -> None:
    def batch(index: int) -> dict:
        text = f"人物无事{index}"
        return {
            "batch_ref": f"BATCH-{index}",
            "page_title": f"史书/卷{index}",
            "work_title": "史书",
            "source_url": f"local:{index}",
            "revision_ref": str(index),
            "segments": [
                {
                    "segment_ref": f"SEG-{index}",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "text": text,
                    "initial_text": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "subject_refs": ["PER-1"],
                    "subject_names": ["人物"],
                    "spans": [],
                }
            ],
        }

    batches = [batch(1), batch(2)]
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": batches,
    }

    class SparseRunner:
        def __init__(self) -> None:
            self.calls = 0
            self.input_batches = []

        def run(self, prompt: str):
            self.calls += 1
            self.input_batches = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [],
                },
                {},
            )

    runner = SparseRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=5,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 0
    assert len(output["batch_results"]) == 2
    assert runner.input_batches[0]["subject_bindings"] == [
        {"aliases": [], "canonical_name": "人物", "subject_ref": "PER-1"}
    ]
    assert runner.input_batches[0]["segments"][0]["subject_refs"] == ["PER-1"]
    assert "subject_bindings" not in runner.input_batches[0]["segments"][0]
    assert "text_sha256" not in runner.input_batches[0]["segments"][0]


def test_neutral_scan_finishes_one_canary_before_parallel_fanout(
    tmp_path: Path,
) -> None:
    batches = []
    for index in range(3):
        text = f"人物无事{index}"
        batches.append(
            {
                "batch_ref": f"BATCH-CANARY-{index}",
                "page_title": f"史书/卷{index}",
                "work_title": "史书",
                "source_url": f"local:{index}",
                "revision_ref": str(index),
                "segments": [
                    {
                        "segment_ref": f"SEG-CANARY-{index}",
                        "start_offset": 0,
                        "end_offset": len(text),
                        "text": text,
                        "initial_text": text,
                        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "subject_refs": ["PER-1"],
                        "subject_names": ["人物"],
                        "spans": [],
                    }
                ],
            }
        )
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-CANARY",
        "page_batches": batches,
    }

    class CanaryRunner:
        def __init__(self) -> None:
            self.calls = 0
            self.lock = Lock()
            self.later_started = Event()
            self.fanout_started_before_canary_finished = False

        def run(self, _prompt: str):
            with self.lock:
                call_index = self.calls
                self.calls += 1
            if call_index == 0:
                if self.later_started.wait(0.1):
                    self.fanout_started_before_canary_finished = True
            else:
                self.later_started.set()
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [],
                },
                {},
            )

    runner = CanaryRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=3,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=1,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 3
    assert runner.fanout_started_before_canary_finished is False
    assert output["model_call_count"] == 3


def test_neutral_scan_propagates_model_anomaly_without_segment_fallback(
    tmp_path: Path,
) -> None:
    text = "人物完成事项。"
    batch = {
        "batch_ref": "BATCH-ANOMALY",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [
            {
                "segment_ref": "SEG-ANOMALY",
                "start_offset": 0,
                "end_offset": len(text),
                "text": text,
                "initial_text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "subject_refs": ["PER-1"],
                "subject_names": ["人物"],
                "spans": [],
            }
        ],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class AnomalyRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            raise ModelBatchAnomalyError("测试异常子进程")

    runner = AnomalyRunner()
    with pytest.raises(ModelBatchAnomalyError, match="测试异常子进程"):
        extract_current_neutral_materials(
            plan=plan,
            current=None,
            runner=runner,
            max_workers=1,
            checkpoint_dir=tmp_path / "checkpoint",
            subject_ref_by_name={"人物": "PER-1"},
        )

    assert runner.calls == 1
    assert not (tmp_path / "checkpoint/_segments").exists()


def test_compact_rows_route_by_segment_ref_despite_bad_batch_refs(tmp_path: Path) -> None:
    def make_batch(index: int) -> dict:
        text = f"人物完成事项{index}。"
        return {
            "batch_ref": f"BATCH-{index}",
            "page_title": f"史书/卷{index}",
            "work_title": "史书",
            "source_url": f"local:{index}",
            "revision_ref": str(index),
            "segments": [
                {
                    "segment_ref": f"SEG-{index}",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "text": text,
                    "initial_text": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "subject_refs": ["PER-1"],
                    "subject_names": ["人物"],
                    "spans": [],
                }
            ],
        }

    batches = [make_batch(1), make_batch(2)]
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": batches,
    }

    def compact_fact(index: int) -> dict:
        return {
            "segment_ref": f"SEG-{index}",
            "exact_quote": f"人物完成事项{index}。",
            "fact_kind": "institutional_action",
            "action_summary": f"完成事项{index}",
            "actors": [
                {
                    "source_name": "人物",
                    "canonical_name": "人物",
                    "subject_ref": "PER-1",
                    "role": "executor",
                    "responsibility_strength": "primary",
                    "attribution_basis": "原文直载",
                }
            ],
            "implementation_status": "implemented",
            "result": "事项完成",
            "outcome_candidate_status": "clear_candidate",
            "outcome_candidate_reason": "行动和结果明确。",
            "uncertainty": "",
        }

    class BadContainerRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": "UNKNOWN",
                            "facts": [compact_fact(1)],
                            "context_requests": [],
                            "limitations": [],
                        },
                        {
                            "batch_ref": "UNKNOWN",
                            "facts": [compact_fact(2)],
                            "context_requests": [],
                            "limitations": [],
                        },
                    ],
                },
                {},
            )

    runner = BadContainerRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=5,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 2


def test_directed_hits_send_full_context_without_serial_expansion(tmp_path: Path) -> None:
    text = "前文人物行事后文"
    segment = {
        "segment_ref": "SEG-DIRECTED",
        "source_role": "backsource",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_start_offset": 2,
        "initial_end_offset": 6,
        "initial_text": text[2:6],
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    batch = {
        "batch_ref": "BATCH-DIRECTED",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class ContextRunner:
        def __init__(self) -> None:
            self.calls = 0
            self.visible_text = ""

        def run(self, prompt: str):
            self.calls += 1
            input_batch = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])[0]
            self.visible_text = input_batch["segments"][0]["text"]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": input_batch["batch_ref"],
                            "facts": [],
                            "context_requests": [
                                {
                                    "segment_ref": "SEG-DIRECTED",
                                    "context_status": "need_both",
                                }
                            ],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    runner = ContextRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.visible_text == text
    assert runner.calls == 1
    assert output["model_call_count"] == 1


def test_unverifiable_compact_quote_is_rejected_without_model_retry(tmp_path: Path) -> None:
    text = "人物完成其事。"
    segment = {
        "segment_ref": "SEG-QUOTE",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    batch = {
        "batch_ref": "BATCH-QUOTE",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class QuoteRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, prompt: str):
            self.calls += 1
            input_batch = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])[0]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": input_batch["batch_ref"],
                            "facts": [
                                {
                                    "segment_ref": "SEG-QUOTE",
                                    "exact_quote": "人物圆满完成了此事",
                                    "fact_kind": "institutional_action",
                                    "action_summary": "人物完成事项",
                                    "actors": [
                                        {
                                            "source_name": "人物",
                                            "canonical_name": "人物",
                                            "subject_ref": "PER-1",
                                            "role": "executor",
                                            "responsibility_strength": "primary",
                                            "attribution_basis": "原文直载",
                                        }
                                    ],
                                    "implementation_status": "implemented",
                                    "result": "事项完成",
                                    "outcome_candidate_status": "clear_candidate",
                                    "outcome_candidate_reason": "行动和结果明确。",
                                    "uncertainty": "",
                                }
                            ],
                            "context_requests": [],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    runner = QuoteRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 0
    assert output["batch_results"][0]["limitations"] == [
        "引文重试后仍无法逐字回指的事实已拒绝接纳。"
    ]


def test_invalid_duplicate_facts_are_rejected_without_model_retry(tmp_path: Path) -> None:
    text = "人物完成其事。"
    segment = {
        "segment_ref": "SEG-DUPLICATE",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    batch = {
        "batch_ref": "BATCH-DUPLICATE",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }
    fact = {
        "segment_ref": "SEG-DUPLICATE",
        "exact_quote": text,
        "fact_kind": "institutional_action",
        "action_summary": "人物完成事项",
        "actors": [
            {
                "source_name": "人物",
                "canonical_name": "人物",
                "subject_ref": "PER-1",
                "role": "executor",
                "responsibility_strength": "primary",
                "attribution_basis": "原文直载",
            }
        ],
        "implementation_status": "implemented",
        "result": "事项完成",
        "outcome_candidate_status": "clear_candidate",
        "outcome_candidate_reason": "行动和结果明确。",
        "uncertainty": "",
    }

    class DuplicateRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": "BATCH-DUPLICATE",
                            "facts": [fact, fact],
                            "context_requests": [],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    runner = DuplicateRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 0
    assert "未通过中性事实合同的片段已确定性拒绝接纳。" in output[
        "batch_results"
    ][0]["limitations"]


def test_strict_quote_retry_rejects_only_unverifiable_fact() -> None:
    batch = {
        "segments": [
            {
                "segment_ref": "SEG-1",
                "text": "可回指原文",
                "subject_refs": ["PER-1"],
            }
        ]
    }
    result = {
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "reason": "raw",
                "facts": [
                    {
                        "exact_quote": "模型改写引文",
                        "actors": [
                            {
                                "canonical_name": "人物",
                                "subject_ref": "PER-1",
                                "role": "executor",
                            }
                        ],
                    }
                ],
            }
        ],
        "limitations": [],
    }

    repaired = _canonicalize_result(
        batch,
        result,
        subject_ref_by_name={"人物": "PER-1"},
        drop_unverifiable_quotes=True,
    )

    assert repaired["segment_reviews"][0]["decision"] == "reject"
    assert repaired["segment_reviews"][0]["facts"] == []
    assert "引文重试后仍无法逐字回指" in repaired["limitations"][0]


def test_outcome_projection_makes_zero_model_calls_for_settled_quotes(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    exact_quote = source_pack["facts"][0]["assertions"][0]["exact_quote"]
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    neutral = {
        "fanout": {
            "facts": [
                {
                    "projection_eligibility": "direct_neutral_fact",
                    "exact_quote": exact_quote,
                    "implementation_status": "implemented",
                    "result": "已有结果",
                    "fact_kind": "institutional_action",
                }
            ]
        }
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials=neutral,
        source_index=None,  # settled path never dereferences the index
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,  # settled path never invokes a model
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False


def test_outcome_projection_keeps_accepted_dispositions_across_runner_changes(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    fact = {
        "fact_ref": "NEUTRALFACT-STABLE-PROJECTION",
        "segment_ref": "SEG-STABLE-PROJECTION",
        "page_title": "测试史书/卷1",
        "revision_ref": "1",
        "exact_quote": "已经验收且不应因调度变化重跑的独立引文。",
        "projection_eligibility": "direct_neutral_fact",
        "implementation_status": "implemented",
        "result": "已有验收结论",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "ambiguous",
    }
    policy_fingerprint = hashlib.sha256(
        json.dumps(
            {"projection_policy": PROJECTION_POLICY_VERSION},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    class ChangedRunner:
        policy_fingerprint = "new-model-or-scheduler"

        def run(self, _prompt: str):
            raise AssertionError("已验收 disposition 不得因 runner 变化重跑")

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={
            "fanout": {"facts": [fact]},
            "outcome_projection": {
                "policy_fingerprint": policy_fingerprint,
                "dispositions": [
                    {
                        "fact_ref": fact["fact_ref"],
                        "decision": "rejected",
                        "reason": "已验收为非独立成果。",
                    }
                ],
            },
        },
        source_index=None,
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=ChangedRunner(),
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False
    assert outcome["policy_fingerprint"] == policy_fingerprint


def test_outcome_projection_keeps_cross_source_event_atomic(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())

    class RejectingRunner:
        policy_fingerprint = "test-policy"

        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        def run(self, prompt: str) -> tuple[dict, str]:
            facts = json.loads(prompt.split("INPUT_FACTS:\n", 1)[1])
            self.calls.append(facts)
            task_code = re.search(r"task_code=(OUTCOME-AUTO-[A-F0-9]+)", prompt)
            assert task_code is not None
            return (
                {
                    "schema_version": "current-outcome-candidate-output-v1",
                    "task_code": task_code.group(1),
                    "candidates": [],
                    "rejections": [
                        {"segment_ref": fact["segment_ref"], "reason": "测试拒绝"}
                        for fact in facts
                    ],
                },
                "",
            )

    facts = [
        {
            "fact_ref": f"NEUTRALFACT-{index}",
            "segment_ref": f"SEG-{index}",
            "page_title": f"史书/卷{index}",
            "revision_ref": str(index),
            "exact_quote": f"同一事件独立史源引文{index}",
            "projection_eligibility": "direct_neutral_fact",
            "implementation_status": "implemented",
            "result": "形成可观察结果",
            "fact_kind": "institutional_action",
            "outcome_candidate_status": "clear_candidate",
            "event_refs": ["EVENT-SAME"],
        }
        for index in (1, 2)
    ]
    facts[0]["source_url"] = "local:must-not-enter-model-prompt"
    facts[0]["segment_text_sha256"] = "redundant-hash"
    runner = RejectingRunner()
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "测试",
            }
        ],
        index_path,
    )
    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": facts}},
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=runner,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        facts_per_call=1,
    )

    assert len(runner.calls) == 1
    assert {row["event_refs"][0] for row in runner.calls[0]} == {"EVENT-SAME"}
    assert "source_url" not in runner.calls[0][0]
    assert "segment_text_sha256" not in runner.calls[0][0]
    assert outcome["model_call_count"] == 1


def test_outcome_projection_finishes_one_canary_before_parallel_fanout(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "人物完成新的治理事项。",
            }
        ],
        index_path,
    )

    class CanaryRunner:
        policy_fingerprint = "test-canary-policy"

        def __init__(self) -> None:
            self.calls = 0
            self.lock = Lock()
            self.later_started = Event()
            self.fanout_started_before_canary_finished = False

        def run(self, prompt: str):
            with self.lock:
                call_index = self.calls
                self.calls += 1
            if call_index == 0:
                if self.later_started.wait(0.1):
                    self.fanout_started_before_canary_finished = True
            else:
                self.later_started.set()
            facts = json.loads(prompt.split("INPUT_FACTS:\n", 1)[1])
            task_code = re.search(r"task_code=(OUTCOME-AUTO-[A-F0-9]+)", prompt)
            assert task_code is not None
            return (
                {
                    "schema_version": "current-outcome-candidate-output-v1",
                    "task_code": task_code.group(1),
                    "candidates": [],
                    "rejections": [
                        {"segment_ref": fact["segment_ref"], "reason": "测试拒绝"}
                        for fact in facts
                    ],
                },
                {},
            )

    facts = [
        {
            "fact_ref": f"NEUTRALFACT-CANARY-{index}",
            "segment_ref": f"SEG-CANARY-{index}",
            "page_title": "史书/卷1",
            "revision_ref": "1",
            "exact_quote": "人物完成新的治理事项。",
            "projection_eligibility": "direct_neutral_fact",
            "implementation_status": "implemented",
            "result": f"形成结果{index}",
            "fact_kind": "institutional_action",
            "outcome_candidate_status": "ambiguous",
            "event_refs": [f"EVENT-CANARY-{index}"],
        }
        for index in range(3)
    ]
    runner = CanaryRunner()
    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": facts}},
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=runner,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=3,
        facts_per_call=1,
    )

    assert runner.calls == 3
    assert runner.fanout_started_before_canary_finished is False
    assert outcome["model_call_count"] == 3


def test_outcome_projection_propagates_model_anomaly_without_split(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "人物完成新的治理事项。",
            }
        ],
        index_path,
    )

    class AnomalyRunner:
        policy_fingerprint = "test-policy"

        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            raise ModelBatchAnomalyError("成果投影异常子进程")

    runner = AnomalyRunner()
    neutral = {
        "fanout": {
            "facts": [
                {
                    "fact_ref": "NEUTRALFACT-ANOMALY",
                    "segment_ref": "SEG-ANOMALY",
                    "page_title": "史书/卷1",
                    "revision_ref": "1",
                    "exact_quote": "人物完成新的治理事项。",
                    "projection_eligibility": "direct_neutral_fact",
                    "implementation_status": "implemented",
                    "result": "形成新的可观察结果",
                    "fact_kind": "institutional_action",
                    "outcome_candidate_status": "clear_candidate",
                    "event_refs": ["EVENT-ANOMALY"],
                }
            ]
        }
    }

    with pytest.raises(ModelBatchAnomalyError, match="成果投影异常子进程"):
        project_current_outcomes(
            source_pack_path=target,
            neutral_materials=neutral,
            source_index=LocalSourceTextIndex(index_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
            runner=runner,
            checkpoint_dir=tmp_path / "checkpoint",
            workspace_root=ROOT,
            max_workers=1,
        )

    assert runner.calls == 1


def test_current_source_pack_increment_is_validated_and_idempotent(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    increment = {
        "schema_version": SOURCE_PACK_INCREMENT_SCHEMA_VERSION,
        "ruler": "李世民",
        "facts": [],
        "outcomes": [],
    }
    compiled = compile_source_pack_increment(payload, increment)
    assert compiled == payload
    target = tmp_path / "source-pack.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    assert apply_source_pack_increment(
        target, increment, workspace_root=ROOT
    ) is False

    conflicting = dict(payload["facts"][0])
    conflicting["neutral_summary"] = "冲突内容"
    with pytest.raises(ValueError, match="record_ref 冲突"):
        compile_source_pack_increment(
            payload,
            {**increment, "facts": [conflicting]},
        )


def test_direct_runner_uses_the_same_markdown_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_json = tmp_path / "result.json"
    output_markdown = tmp_path / "result.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "i5b_current_value_runner",
            "--source-pack",
            str(ROOT / "eval/i5b_current_value/刘邦/source-pack.json"),
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
    )

    assert runner_main() == 0
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert output_markdown.read_text(encoding="utf-8") == (
        render_scoring_detail_markdown(report)
    )


def test_i5b_run_uses_current_ruler_catalog_and_can_export_detail(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source_dir = workspace / "eval/current/ruler"
    source_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    (source_dir / "source-pack.json").write_bytes(source.read_bytes())
    config_dir = workspace / "config"
    config_dir.mkdir()
    (config_dir / "project.yml").write_text(
        """i5b_current_value:
  rulers:
    刘邦:
      source_pack: eval/current/ruler/source-pack.json
      result: eval/current/ruler/result.json
""",
        encoding="utf-8",
    )
    detail = tmp_path / "detail.md"

    assert eval_main([
        "i5b-run",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(workspace),
        "--detail-output",
        str(detail),
    ]) == 0
    assert (source_dir / "result.json").is_file()
    assert (source_dir / "result.md").is_file()
    assert "未计分支持材料" in detail.read_text(encoding="utf-8")


def test_i5b_run_rejects_unconfigured_ruler(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "project.yml").write_text(
        "i5b_current_value:\n  rulers: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="尚未进入当前 I5B 运行目录"):
        eval_main([
            "i5b-run",
            "--ruler",
            "unknown",
            "--workspace-root",
            str(tmp_path),
        ])


def test_current_scoring_detail_export_uses_factor_values_for_unscored_materials(
    tmp_path: Path,
) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    rendered = render_scoring_detail_markdown(report)

    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |" in rendered
    assert "### 未计分支持材料" in rendered
    assert "| 对象 | 判定 | 因子取值 | 事实 |" in rendered
    assert "| 对象 | 判定 | 说明 | 事实 |" not in rendered
    assert "识才方向 1.000000" in rendered
    assert "材料分低于当前" not in rendered
    team = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "team_building"
    )
    assert all(row["political_risk"].get("basis") for row in team["negative_members"])
    assert all(row["political_risk"]["basis"] in rendered for row in team["negative_members"])

    output = tmp_path / "scoring-detail.md"
    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "李世民",
        "--workspace-root",
        str(ROOT),
        "--output",
        str(output),
    ]) == 0
    assert output.read_text(encoding="utf-8") == rendered


def test_scoring_detail_can_filter_one_person(tmp_path: Path) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    rendered = render_scoring_detail_markdown(report, person="周勃")

    assert "# 刘邦 / 周勃第五项B材料预算计分验证" in rendered
    assert "## 当前人物画像" in rendered
    assert "人才等级确立理由" in rendered
    assert "规则对应" in rendered
    assert "登记支撑" in rendered
    assert "config/talent-grade-v11-domain-equivalent-historic.yml#top_fallback" in rendered
    assert "## 人才等级成果登记" in rendered
    assert "campaign" in rendered
    assert "serious" in rendered
    assert "屠马邑" in rendered
    assert "屠浑都存在地名与人名断句争议" in rendered
    assert "## HistoricalEpisode" in rendered
    assert "英布 |" not in rendered
    episode_ids = report["episode_index_by_person"]["周勃"]
    assert len(episode_ids) == len(set(episode_ids))
    outcome_ids = [value for value in episode_ids if value.startswith("EP-OUTCOME-")]
    assert len(outcome_ids) == 1
    assert rendered.count(outcome_ids[0]) == 1

    output = tmp_path / "zhou-bo.md"
    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "刘邦",
        "--person",
        "周勃",
        "--workspace-root",
        str(ROOT),
        "--output",
        str(output),
    ]) == 0
    assert output.read_text(encoding="utf-8") == rendered

    with pytest.raises(ValueError, match="不存在臣子"):
        render_scoring_detail_markdown(report, person="不存在")


@pytest.mark.parametrize(
    ("ruler", "person", "relative_output"),
    [
        ("李世民", None, Path("tmp/i5b_scoring_detail/李世民/scoring-detail.md")),
        ("刘邦", "周勃", Path("tmp/i5b_scoring_detail/刘邦/persons/周勃.md")),
    ],
)
def test_scoring_detail_output_is_optional(
    tmp_path: Path,
    ruler: str,
    person: str | None,
    relative_output: Path,
) -> None:
    workspace = tmp_path / "workspace"
    current_dir = workspace / "eval/i5b_current_value" / ruler
    current_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    (current_dir / "source-pack.json").write_bytes(source.read_bytes())
    argv = [
        "i5b-scoring-detail",
        "--ruler",
        ruler,
        "--workspace-root",
        str(workspace),
    ]
    if person:
        argv.extend(("--person", person))

    assert eval_main(argv) == 0
    output = workspace / relative_output
    assert output.is_file()
    assert output.read_text(encoding="utf-8") == render_scoring_detail_markdown(
        build_i5b_current_value(source), person=person
    )


def test_default_detail_export_rebuilds_from_source_pack_not_stale_result(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    current_dir = workspace / "eval/i5b_current_value/刘邦"
    current_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    (current_dir / "source-pack.json").write_bytes(source.read_bytes())
    (current_dir / "result.json").write_text(
        '{"ruler":"刘邦","stale":true}', encoding="utf-8"
    )
    output = tmp_path / "han-xin.md"

    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "刘邦",
        "--person",
        "韩信",
        "--workspace-root",
        str(workspace),
        "--output",
        str(output),
    ]) == 0
    assert "# 刘邦 / 韩信第五项B材料预算计分验证" in output.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_signals_do_not_exceed_theoretical_envelopes(ruler: str) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    )
    diagnostic = report["material_budget"]["amplitude_diagnostic"]

    for rule in report["material_budget"]["rules"]:
        code = rule["rule_code"]
        assert Decimal(rule["positive_signal"]) <= Decimal(
            diagnostic["theoretical_positive_envelope"][code]
        )
        assert Decimal(rule["negative_signal"]) <= Decimal(
            diagnostic["theoretical_negative_envelope"][code]
        )
