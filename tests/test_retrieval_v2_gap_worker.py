from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.dev import retrieval_v2_gap_worker as tool


def source_job(*, code: str, gap_type: str, object_name: str, task: str = "tmp/run/TGT/task.final.json") -> dict:
    return {
        "job_code": code,
        "kind": "codex_source_pack_refine",
        "payload": {
            "action": "source_pack_refine",
            "gap_event": {
                "event_code": code.replace("JOB", "CGE"),
                "target_code": "TGT-I5B-LH",
                "emperor_name": "刘恒",
                "item_code": "I5B",
                "rule_code": "delegation",
                "source_pack_code": "SPK-LH-DELEGATION",
                "gap_type": gap_type,
                "object_name": object_name,
                "artifact_paths": {"task": task},
            },
        },
    }


def review_job() -> dict:
    return {
        "job_code": "JOB-REVIEW",
        "kind": "codex_material_review",
        "payload": {
            "action": "split_or_mark_material_claim",
            "gap_event": {
                "event_code": "CGE-REVIEW",
                "target_code": "TGT-I5B-LH",
                "emperor_name": "刘恒",
                "item_code": "I5B",
                "rule_code": "delegation",
                "source_pack_code": "SPK-LH-DELEGATION",
                "gap_type": "mixed_claim_not_split",
                "object_name": "晁错",
                "artifact_paths": {"task": "tmp/run/TGT/task.final.json"},
            },
        },
    }


def test_plan_groups_source_jobs_by_task_and_defaults_to_candidate_only() -> None:
    plan = tool.plan_from_jobs(
        [
            source_job(code="JOB-1", gap_type="predicate_missing", object_name="薄昭"),
            source_job(code="JOB-2", gap_type="negative_undercoverage", object_name="灌婴"),
        ],
        worker_run_root=Path("tmp/retrieval_v2_clean_runs/gap_worker_test"),
    )

    assert plan["totals"] == {"jobs": 2, "entries": 1, "executable_entries": 1, "review_entries": 0}
    entry = plan["entries"][0]
    argv = entry["argv"]
    assert entry["job_codes"] == ["JOB-1", "JOB-2"]
    assert entry["objects"] == ["薄昭", "灌婴"]
    assert "--task" in argv
    assert "--skip-judge" in argv
    assert argv[argv.index("--candidate-source-refine-rounds") + 1] == "1"
    assert argv[argv.index("--candidate-source-refine-max-objects") + 1] == "2"
    refine_object_values = [
        argv[index + 1] for index, value in enumerate(argv) if value == "--candidate-source-refine-object"
    ]
    assert refine_object_values == ["薄昭", "灌婴"]


def test_plan_marks_material_review_jobs_non_executable() -> None:
    plan = tool.plan_from_jobs([review_job()])

    assert plan["totals"]["review_entries"] == 1
    entry = plan["entries"][0]
    assert entry["entry_type"] == "codex_material_review"
    assert entry["executable"] is False
    assert entry["argv"] == []


def test_plan_sets_alias_round_for_alias_missing() -> None:
    plan = tool.plan_from_jobs([source_job(code="JOB-ALIAS", gap_type="alias_missing", object_name="季布")])

    argv = plan["entries"][0]["argv"]
    assert argv[argv.index("--max-alias-refine-rounds") + 1] == "1"
    assert argv[argv.index("--candidate-source-refine-rounds") + 1] == "0"


def test_run_plan_without_execute_only_reports_planned() -> None:
    plan = tool.plan_from_jobs([source_job(code="JOB-1", gap_type="predicate_missing", object_name="薄昭")])

    result = tool.run_plan(plan, execute=False)

    assert result["totals"]["planned"] == 1
    assert result["totals"]["failed"] == 0


def test_run_plan_updates_db_lifecycle_when_dsn_is_set(monkeypatch) -> None:
    updates: list[tuple[str, tuple[str, ...]]] = []
    event_updates: list[tuple[str, tuple[str, ...]]] = []

    def fake_update_job_statuses(*, dsn: str, job_codes, status: str, worker_id: str, error: str = "") -> int:
        assert dsn == "postgres://example"
        assert worker_id == "test-worker"
        updates.append((status, tuple(job_codes)))
        return len(job_codes)

    def fake_update_gap_events_for_jobs(*, dsn: str, job_codes, status: str) -> int:
        assert dsn == "postgres://example"
        event_updates.append((status, tuple(job_codes)))
        return len(job_codes)

    monkeypatch.setattr(tool, "update_job_statuses", fake_update_job_statuses)
    monkeypatch.setattr(tool, "update_gap_events_for_jobs", fake_update_gap_events_for_jobs)
    monkeypatch.setattr(tool.subprocess, "run", lambda argv, cwd: SimpleNamespace(returncode=0))
    plan = tool.plan_from_jobs([source_job(code="JOB-1", gap_type="predicate_missing", object_name="薄昭")])

    result = tool.run_plan(plan, execute=True, db_dsn="postgres://example", worker_id="test-worker")

    assert result["totals"]["succeeded"] == 1
    assert updates == [("running", ("JOB-1",)), ("succeeded", ("JOB-1",))]
    assert event_updates == [("running", ("JOB-1",)), ("resolved", ("JOB-1",))]
    assert result["results"][0]["db_running_count"] == 1
    assert result["results"][0]["db_done_count"] == 1
    assert result["results"][0]["db_event_running_count"] == 1
    assert result["results"][0]["db_event_done_count"] == 1


def test_main_builds_plan_from_jobs_jsonl(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.jsonl"
    jobs_path.write_text(json.dumps(source_job(code="JOB-1", gap_type="predicate_missing", object_name="薄昭")) + "\n")
    output = tmp_path / "plan.json"

    assert tool.main(["plan", "--jobs-jsonl", str(jobs_path), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["totals"]["executable_entries"] == 1


def test_main_builds_plan_from_events_jsonl(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    event = source_job(code="JOB-1", gap_type="predicate_missing", object_name="薄昭")["payload"]["gap_event"]
    event["event_code"] = "CGE-1"
    event["idem_key"] = "TGT|delegation|SPK|predicate_missing||薄昭|"
    event["queue"] = "source_pack_refinement"
    events_path.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    output = tmp_path / "plan.json"

    assert tool.main(["plan", "--events-jsonl", str(events_path), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["totals"]["jobs"] == 1
    assert payload["totals"]["executable_entries"] == 1
