from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.dev import retrieval_v2_claim_extraction_worker as tool
from scripts.dev import retrieval_v2_candidate_prompt


def write_candidates(path: Path) -> dict:
    payload = {
        "task_identity": {
            "emperor_name": "朱元璋",
            "target_code": "TGT-ZYZ",
            "rule_code": "i5b_item_wide",
            "capture_profile": "personnel_political_wide",
        },
        "target_profile": {"primary_name": "朱元璋"},
        "rule": {"rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-001",
                "document_code": "DOC-001",
                "object_name": "汤和",
                "text": "帝命汤和守常州，常州安辑。",
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def test_job_from_candidates_builds_stable_queue_payload(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.uncovered.json"
    write_candidates(candidates_path)

    first = tool.job_from_candidates(
        candidates_path=candidates_path,
        cache_root=tmp_path / "claim_cache",
        run_root=tmp_path / "runs",
    )
    second = tool.job_from_candidates(
        candidates_path=candidates_path,
        cache_root=tmp_path / "claim_cache",
        run_root=tmp_path / "runs",
    )

    assert first["job_code"] == second["job_code"]
    assert first["idem_key"] == second["idem_key"]
    assert first["emperor_name"] == "朱元璋"
    assert first["target_code"] == "TGT-ZYZ"
    assert first["rule_code"] == "i5b_item_wide"
    assert first["uncovered_slice_count"] == 1
    assert first["job_payload"]["slice_count"] == 1


def test_job_plan_resolves_paths_without_consumption_actions(tmp_path: Path) -> None:
    job = {
        "job_code": "CLMEXT-001",
        "idem_key": "idem",
        "candidate_payload_path": str(tmp_path / "candidates.json"),
        "run_root": str(tmp_path / "runs" / "job"),
        "cache_root": str(tmp_path / "claim_cache"),
        "uncovered_slice_count": 3,
    }

    plan = tool.job_plan(job)

    assert plan["job_code"] == "CLMEXT-001"
    assert plan["uncovered_slice_count"] == 3
    assert plan["execute_effect"] == "claim-only judge -> filesystem claim cache -> optional PG claim cache"


def test_once_without_execute_fetches_but_does_not_claim(monkeypatch) -> None:
    called = {"claim": 0}

    def fake_fetch_next_ready_job(*, dsn: str):
        assert dsn == "postgres://example"
        return {
            "job_code": "CLMEXT-001",
            "idem_key": "idem",
            "candidate_payload_path": "tmp/candidates.json",
            "run_root": "tmp/run",
            "cache_root": "tmp/cache",
            "uncovered_slice_count": 1,
        }

    def fake_claim_ready_job(**_kwargs):
        called["claim"] += 1
        raise AssertionError("non-execute once must not take a DB lease")

    monkeypatch.setattr(tool, "fetch_next_ready_job", fake_fetch_next_ready_job)
    monkeypatch.setattr(tool, "claim_ready_job", fake_claim_ready_job)

    result = tool.once(dsn="postgres://example", worker_id="worker", execute=False)

    assert result["status"] == "planned"
    assert called["claim"] == 0


def test_write_mini_run_artifacts_is_import_run_compatible(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.json"
    candidates = write_candidates(candidates_path)
    run_root = tmp_path / "run"
    judge_payload = {
        "status": "succeeded",
        "claims": [
            {
                "claim_code": "CLM-001",
                "emperor_name": "朱元璋",
                "object_name": "汤和",
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": "朱元璋命汤和镇守常州。",
                "direction": "positive",
                "source_slice_refs": ["SLI-001"],
                "fact_payload": {"fact_schema": "political_action_v1", "actor": "朱元璋", "object": "汤和", "action_type": "授权"},
                "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"}],
            }
        ],
    }

    summary = tool.write_mini_run_artifacts(
        job={
            "target_code": "TGT-ZYZ",
            "rule_code": "i5b_item_wide",
            "emperor_name": "朱元璋",
            "capture_profile": "personnel_political_wide",
            "idem_key": "idem",
        },
        candidates=candidates,
        judge_payload=judge_payload,
        judge_result={"elapsed_seconds": 0.1, "usage": {"input_tokens": 10, "output_tokens": 5}},
        run_root=run_root,
    )

    assert summary["totals"]["claim_count"] == 1
    assert (run_root / "summary.json").exists()
    assert summary["people"][0]["files"]["final_candidates"].endswith("candidates.final.json")
    assert summary["clean_policy"]["judge_mode"] == retrieval_v2_candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE
    assert summary["clean_policy"]["extractor_version"] == retrieval_v2_candidate_prompt.CLAIM_EXTRACTOR_VERSION


def test_execute_job_runs_claim_only_and_imports_cache(tmp_path: Path, monkeypatch) -> None:
    candidates_path = tmp_path / "candidates.json"
    write_candidates(candidates_path)
    calls: list[str] = []

    def fake_run_judge(**kwargs):
        assert kwargs["judge_mode"] == retrieval_v2_candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE
        calls.append("judge")
        return {
            "payload": {
                "status": "succeeded",
                "claims": [
                    {
                        "claim_code": "CLM-001",
                        "emperor_name": "朱元璋",
                        "object_name": "汤和",
                        "object_type": "person",
                        "claim_kind": "material_claim",
                        "claim_summary": "朱元璋命汤和镇守常州。",
                        "direction": "positive",
                        "source_slice_refs": ["SLI-001"],
                        "fact_payload": {
                            "fact_schema": "political_action_v1",
                            "actor": "朱元璋",
                            "object": "汤和",
                            "action_type": "授权",
                        },
                        "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"}],
                    }
                ],
            },
            "elapsed_seconds": 0.2,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    def fake_import_run(run_root: Path, cache_root: Path):
        assert (run_root / "summary.json").exists()
        calls.append("fs_import")
        return {"total_cached_claims": 1}

    monkeypatch.setattr(tool.clean_runner, "run_judge", fake_run_judge)
    monkeypatch.setattr(tool.fs_cache, "import_run", fake_import_run)

    result = tool.execute_job(
        job={
            "job_code": "CLMEXT-001",
            "idem_key": "idem",
            "target_code": "TGT-ZYZ",
            "rule_code": "i5b_item_wide",
            "emperor_name": "朱元璋",
            "candidate_payload_path": str(candidates_path),
            "run_root": str(tmp_path / "run"),
            "cache_root": str(tmp_path / "cache"),
        },
        codex_bin="codex",
        judge_timeout_seconds=30,
        judge_shard_size=4,
        judge_shard_workers=1,
        import_pg=False,
        dsn_env="EMPEROR_EVAL_RETRIEVAL_V2_DSN",
    )

    assert calls == ["judge", "fs_import"]
    assert result["claim_count"] == 1
    assert result["pg_import"] is None


def test_execute_once_records_success(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params=None):
            if "insert into retrieval_v2.claim_extraction_job_runs" in sql:
                events.append(("create_run", params[0]))
            elif "update retrieval_v2.claim_extraction_job_runs" in sql:
                events.append(("finish_run", params[0]))
            elif "update retrieval_v2.claim_extraction_jobs" in sql:
                events.append(("finish_job", ""))

        def fetchone(self):
            return {"id": 7}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            events.append(("commit", ""))

    def fake_import_psycopg():
        return SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConn()), dict

    monkeypatch.setattr(tool, "import_psycopg", fake_import_psycopg)
    monkeypatch.setattr(
        tool,
        "claim_ready_job",
        lambda **_kwargs: {
            "id": 5,
            "job_code": "CLMEXT-001",
            "idem_key": "idem",
            "candidate_payload_path": "tmp/candidates.json",
            "run_root": "tmp/run",
            "cache_root": "tmp/cache",
            "uncovered_slice_count": 1,
        },
    )
    monkeypatch.setattr(
        tool,
        "execute_job",
        lambda **_kwargs: {"claim_count": 2, "usage": {"input_tokens": 1}, "run_root": "tmp/run"},
    )

    result = tool.once(dsn="postgres://example", worker_id="worker", execute=True)

    assert result["status"] == "succeeded"
    assert events[0][0] == "create_run"
    assert ("finish_run", "succeeded") in events
    assert ("finish_job", "") in events


def test_finish_job_run_failure_casts_status_case_to_enum() -> None:
    statements: list[str] = []

    class FakeCursor:
        def execute(self, sql, params=None):
            statements.append(sql)

    tool.finish_job_run(
        FakeCursor(),
        run_id=7,
        job_id=5,
        status="failed",
        error_type="FileNotFoundError",
        error_msg="codex not found",
    )

    job_update_sql = statements[-1]
    assert "case when attempt_count >= max_attempts then 'failed' else 'retry_wait' end" in job_update_sql
    assert "::retrieval_v2.rv2_claim_extraction_job_status" in job_update_sql
