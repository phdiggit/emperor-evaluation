from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.dev import retrieval_v2_object_source_cache_worker as tool


def write_seed(path: Path) -> list[dict]:
    rows = [
        {
            "person_name": "汤和",
            "target_emperor": "朱元璋",
            "capture_profile": "personnel_political_wide",
            "aliases": ["汤鼎臣"],
        },
        {
            "person_name": "常遇春",
            "target_emperor": "朱元璋",
            "capture_profile": "personnel_political_wide",
            "aliases": [],
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return rows


def test_job_from_seed_builds_stable_queue_payload(tmp_path: Path) -> None:
    seed = tmp_path / "seed.jsonl"
    write_seed(seed)
    build_options = {"shard_size": 2, "pages_per_query": 1, "max_search_names": 1}

    first = tool.job_from_seed(
        seed_jsonl=seed,
        output_root=tmp_path / "out",
        page_cache_root=tmp_path / "pages",
        build_options=build_options,
    )
    second = tool.job_from_seed(
        seed_jsonl=seed,
        output_root=tmp_path / "out",
        page_cache_root=tmp_path / "pages",
        build_options=build_options,
    )

    assert first["job_code"] == second["job_code"]
    assert first["idem_key"] == second["idem_key"]
    assert first["emperor_name"] == "朱元璋"
    assert first["capture_profile"] == "personnel_political_wide"
    assert first["seed_count"] == 2
    assert first["job_payload"]["build_options"] == build_options


def test_job_plan_is_offline_and_does_not_claim(tmp_path: Path) -> None:
    job = {
        "job_code": "OSCACHE-001",
        "seed_jsonl_path": str(tmp_path / "seed.jsonl"),
        "output_root": str(tmp_path / "out"),
        "page_cache_root": str(tmp_path / "pages"),
        "seed_count": 2,
    }

    plan = tool.job_plan(job)

    assert plan["job_code"] == "OSCACHE-001"
    assert plan["seed_count"] == 2
    assert plan["execute_effect"] == "offline object source cache build-shards -> review-audit; no Codex, no consumption scoring"


def test_once_without_execute_fetches_but_does_not_claim(monkeypatch) -> None:
    called = {"claim": 0}

    def fake_fetch_next_ready_job(*, dsn: str):
        assert dsn == "postgres://example"
        return {
            "job_code": "OSCACHE-001",
            "seed_jsonl_path": "tmp/seed.jsonl",
            "output_root": "tmp/out",
            "page_cache_root": "tmp/pages",
            "seed_count": 1,
        }

    def fake_claim_ready_job(**_kwargs):
        called["claim"] += 1
        raise AssertionError("non-execute once must not take a DB lease")

    monkeypatch.setattr(tool, "fetch_next_ready_job", fake_fetch_next_ready_job)
    monkeypatch.setattr(tool, "claim_ready_job", fake_claim_ready_job)

    result = tool.once(dsn="postgres://example", worker_id="worker", execute=False)

    assert result["status"] == "planned"
    assert called["claim"] == 0


def test_execute_job_runs_build_and_review_without_codex(tmp_path: Path, monkeypatch) -> None:
    seed = tmp_path / "seed.jsonl"
    write_seed(seed)
    out = tmp_path / "out"
    calls: list[list[str]] = []

    def fake_object_cache_main(argv):
        calls.append(list(argv))
        if argv[0] == "build-shards":
            out.mkdir(parents=True, exist_ok=True)
            (out / "person_coverage.jsonl").write_text("{}\n{}\n", encoding="utf-8")
            (out / "source_documents.jsonl").write_text("{}\n{}\n{}\n", encoding="utf-8")
            (out / "mention_slices.jsonl").write_text("{}\n", encoding="utf-8")
            (out / "fetch_errors.jsonl").write_text("", encoding="utf-8")
            (out / "agent_review_queue.jsonl").write_text("{}\n", encoding="utf-8")
            (out / "shard_summary.json").write_text(
                json.dumps(
                    {
                        "totals": {
                            "persons": 2,
                            "source_documents": 3,
                            "mention_slices": 1,
                            "fetch_errors": 0,
                            "coverage_needs_agent_review": 1,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        elif argv[0] == "review-audit":
            review_json = Path(argv[argv.index("--output-json") + 1])
            review_json.write_text(json.dumps({"totals": {"review_rows": 1}}, ensure_ascii=False), encoding="utf-8")
            Path(argv[argv.index("--output-md") + 1]).write_text("# review\n", encoding="utf-8")
        else:
            raise AssertionError(argv)
        return 0

    monkeypatch.setattr(tool.object_cache, "main", fake_object_cache_main)

    result = tool.execute_job(
        job={
            "job_code": "OSCACHE-001",
            "seed_jsonl_path": str(seed),
            "output_root": str(out),
            "page_cache_root": str(tmp_path / "pages"),
            "job_payload": {"build_options": {"shard_size": 2, "request_delay": 0}},
        }
    )

    assert [call[0] for call in calls] == ["build-shards", "review-audit"]
    assert not any("codex" in " ".join(call).lower() for call in calls)
    assert result["counts"] == {
        "person_count": 2,
        "source_document_count": 3,
        "mention_slice_count": 1,
        "fetch_error_count": 0,
        "review_queue_count": 1,
    }


def test_execute_once_records_success(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params=None):
            if "insert into retrieval_v2.object_source_cache_job_runs" in sql:
                events.append(("create_run", params[0]))
            elif "update retrieval_v2.object_source_cache_job_runs" in sql:
                events.append(("finish_run", params[0]))
            elif "update retrieval_v2.object_source_cache_jobs" in sql:
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
            "job_code": "OSCACHE-001",
            "seed_jsonl_path": "tmp/seed.jsonl",
            "output_root": "tmp/out",
            "page_cache_root": "tmp/pages",
            "seed_count": 1,
            "job_payload": {"build_options": {}},
        },
    )
    monkeypatch.setattr(
        tool,
        "execute_job",
        lambda **_kwargs: {
            "counts": {
                "person_count": 1,
                "source_document_count": 2,
                "mention_slice_count": 3,
                "fetch_error_count": 0,
                "review_queue_count": 0,
            },
            "output_root": "tmp/out",
        },
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
        error_type="ObjectSourceCacheWorkerError",
        error_msg="build failed",
    )

    job_update_sql = statements[-1]
    assert "case when attempt_count >= max_attempts then 'failed' else 'retry_wait' end" in job_update_sql
    assert "::retrieval_v2.rv2_object_source_cache_job_status" in job_update_sql
