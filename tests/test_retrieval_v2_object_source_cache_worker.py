from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.dev import retrieval_v2_object_source_cache_worker as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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


def write_object_cache(cache_root: Path) -> None:
    write_jsonl(
        cache_root / "source_documents.jsonl",
        [
            {
                "document_cache_code": "OSD-TH",
                "person_cache_code": "PSC-TH",
                "person_name": "汤和",
                "source_title": "明史/卷126",
                "source_url": "https://example.test/mingshi126",
                "source_role": "object_biography",
                "source_shape": "object_biography_candidate",
            },
            {
                "document_cache_code": "OSD-CYC",
                "person_cache_code": "PSC-CYC",
                "person_name": "常遇春",
                "source_title": "明史/卷125",
                "source_url": "https://example.test/mingshi125",
                "source_role": "object_biography",
                "source_shape": "object_biography_candidate",
            },
            {
                "document_cache_code": "OSD-ZYZ",
                "person_cache_code": "PSC-ZYZ",
                "person_name": "朱元璋",
                "source_title": "明史/卷1",
                "source_url": "https://example.test/mingshi1",
                "source_role": "emperor_context",
                "source_shape": "emperor_context_candidate",
            },
            {
                "document_cache_code": "OSD-DY",
                "person_cache_code": "PSC-DY",
                "person_name": "邓愈",
                "source_title": "明史/卷126",
                "source_url": "https://example.test/mingshi126-dy",
                "source_role": "object_biography",
                "source_shape": "object_biography_candidate",
            },
            {
                "document_cache_code": "OSD-ZL",
                "person_cache_code": "PSC-ZL",
                "person_name": "张良",
                "source_title": "史记/卷55",
                "source_url": "https://example.test/shiji55",
                "source_role": "object_mention",
                "source_shape": "object_mention_candidate",
            },
        ],
    )
    write_jsonl(
        cache_root / "person_coverage.jsonl",
        [
            {"person_name": "汤和", "mention_slice_count": 2},
            {"person_name": "常遇春", "mention_slice_count": 1},
            {"person_name": "朱元璋", "mention_slice_count": 1},
            {"person_name": "邓愈", "mention_slice_count": 2},
            {"person_name": "张良", "mention_slice_count": 2},
        ],
    )
    write_jsonl(
        cache_root / "mention_slices.jsonl",
        [
            {
                "slice_cache_code": "OSS-TH-1",
                "document_cache_code": "OSD-TH",
                "person_cache_code": "PSC-TH",
                "person_name": "汤和",
                "source_title": "明史/卷126",
                "source_role": "object_biography",
                "locator": "chars:0-80",
                "matched_aliases": ["汤和"],
                "raw_text": "太祖命汤和守常州，汤和安辑军民。",
            },
            {
                "slice_cache_code": "OSS-TH-2",
                "document_cache_code": "OSD-TH",
                "person_cache_code": "PSC-TH",
                "person_name": "汤和",
                "source_title": "明史/卷126",
                "source_role": "object_biography",
                "locator": "chars:80-160",
                "matched_aliases": ["汤和"],
                "raw_text": "汤和后镇海上，严戢士卒。",
            },
            {
                "slice_cache_code": "OSS-CYC-1",
                "document_cache_code": "OSD-CYC",
                "person_cache_code": "PSC-CYC",
                "person_name": "常遇春",
                "source_title": "明史/卷125",
                "source_role": "object_biography",
                "locator": "chars:0-80",
                "matched_aliases": ["常遇春"],
                "raw_text": "常遇春从太祖渡江，屡破敌军。",
            },
            {
                "slice_cache_code": "OSS-ZYZ-1",
                "document_cache_code": "OSD-ZYZ",
                "person_cache_code": "PSC-ZYZ",
                "person_name": "朱元璋",
                "source_title": "明史/卷1",
                "source_role": "emperor_context",
                "locator": "chars:0-80",
                "matched_aliases": ["朱元璋"],
                "raw_text": "太祖起兵濠州，诸将从之。",
            },
            {
                "slice_cache_code": "OSS-DY-1",
                "document_cache_code": "OSD-DY",
                "person_cache_code": "PSC-DY",
                "person_name": "邓愈",
                "source_title": "明史/卷126",
                "source_role": "object_biography",
                "locator": "chars:0-80",
                "matched_aliases": ["邓愈"],
                "raw_text": "邓愈从征吐蕃，克敌有功。",
            },
            {
                "slice_cache_code": "OSS-DY-2",
                "document_cache_code": "OSD-DY",
                "person_cache_code": "PSC-DY",
                "person_name": "邓愈",
                "source_title": "明史/卷126",
                "source_role": "object_biography",
                "locator": "chars:80-160",
                "matched_aliases": ["邓愈"],
                "raw_text": "邓愈镇守边疆，军令严明。",
            },
            {
                "slice_cache_code": "OSS-ZL-1",
                "document_cache_code": "OSD-ZL",
                "person_cache_code": "PSC-ZL",
                "person_name": "张良",
                "source_title": "史记/卷55",
                "source_role": "object_mention",
                "locator": "chars:0-80",
                "matched_aliases": ["张良"],
                "raw_text": "张良数从汉王谋议。",
            },
            {
                "slice_cache_code": "OSS-ZL-2",
                "document_cache_code": "OSD-ZL",
                "person_cache_code": "PSC-ZL",
                "person_name": "张良",
                "source_title": "史记/卷55",
                "source_role": "object_mention",
                "locator": "chars:80-160",
                "matched_aliases": ["张良"],
                "raw_text": "张良劝汉王还军。",
            },
        ],
    )


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


def test_claim_plan_builds_uncovered_candidates_without_db(tmp_path: Path, monkeypatch) -> None:
    cache_root = tmp_path / "object_cache"
    write_object_cache(cache_root)
    called = {"resolve_dsn": 0, "enqueue": 0}

    def fake_resolve_dsn(_env):
        called["resolve_dsn"] += 1
        raise AssertionError("dry-run claim-plan must not resolve a DSN")

    def fake_enqueue_job(**_kwargs):
        called["enqueue"] += 1
        raise AssertionError("dry-run claim-plan must not enqueue")

    monkeypatch.setattr(tool, "resolve_dsn", fake_resolve_dsn)
    monkeypatch.setattr(tool.claim_worker, "enqueue_job", fake_enqueue_job)

    assert tool.main(
        [
            "claim-plan",
            "--cache-root",
            str(cache_root),
            "--claim-cache-root",
            str(tmp_path / "claim_cache"),
            "--output-candidates",
            str(tmp_path / "claim_candidates.json"),
            "--output-uncovered-candidates",
            str(tmp_path / "claim_candidates.uncovered.json"),
            "--emperor-name",
            "朱元璋",
            "--target-code",
            "TGT-ZYZ",
            "--max-slices-per-person",
            "1",
            "--output-json",
            str(tmp_path / "claim_plan.json"),
        ]
    ) == 0

    plan = json.loads((tmp_path / "claim_plan.json").read_text(encoding="utf-8"))
    candidates = json.loads((tmp_path / "claim_candidates.json").read_text(encoding="utf-8"))
    uncovered = json.loads((tmp_path / "claim_candidates.uncovered.json").read_text(encoding="utf-8"))

    assert called == {"resolve_dsn": 0, "enqueue": 0}
    assert plan["uncovered_slice_count"] == 4
    assert candidates["task_identity"]["judge_mode"] == "claim_extraction_only"
    assert candidates["task_identity"]["emperor_name"] == "朱元璋"
    assert {row["object_name"] for row in candidates["candidate_slices"]} == {"汤和", "常遇春", "邓愈", "张良"}
    assert candidates["claim_plan_audit"]["excluded_object_names"] == ["朱元璋"]
    assert candidates["claim_plan_audit"]["object_count"] == 4
    assert candidates["claim_plan_audit"]["by_object"]["汤和"]["has_biography_source"] is True
    assert candidates["claim_plan_audit"]["by_object"]["张良"]["has_biography_source"] is False
    assert candidates["claim_plan_audit"]["source_shape_counts"] == {"object_biography_candidate": 3, "object_mention_candidate": 1}
    assert uncovered["candidate_slices"] == candidates["candidate_slices"]


def test_claim_plan_can_include_target_emperor_object_when_requested(tmp_path: Path) -> None:
    cache_root = tmp_path / "object_cache"
    write_object_cache(cache_root)

    result = tool.plan_claim_extraction_from_cache(
        cache_root=cache_root,
        claim_cache_root=tmp_path / "claim_cache",
        output_candidates=tmp_path / "claim_candidates.json",
        output_uncovered_candidates=tmp_path / "claim_candidates.uncovered.json",
        emperor_name="朱元璋",
        target_code="TGT-ZYZ",
        include_target_emperor_object=True,
        max_slices_per_person=1,
    )
    candidates = json.loads((tmp_path / "claim_candidates.json").read_text(encoding="utf-8"))

    assert result["claim_plan_audit"]["excluded_object_names"] == []
    assert {row["object_name"] for row in candidates["candidate_slices"]} == {"朱元璋", "汤和", "常遇春", "邓愈", "张良"}
    assert candidates["claim_plan_audit"]["source_shape_counts"] == {
        "emperor_context_candidate": 1,
        "object_biography_candidate": 3,
        "object_mention_candidate": 1,
    }


def test_claim_plan_pilot_selects_high_value_small_batch(tmp_path: Path) -> None:
    cache_root = tmp_path / "object_cache"
    write_object_cache(cache_root)

    result = tool.plan_claim_extraction_from_cache(
        cache_root=cache_root,
        claim_cache_root=tmp_path / "claim_cache",
        output_candidates=tmp_path / "claim_candidates.json",
        output_uncovered_candidates=tmp_path / "claim_candidates.uncovered.json",
        emperor_name="朱元璋",
        target_code="TGT-ZYZ",
        max_slices_per_person=2,
        selection_profile="pilot",
        pilot_object_limit=2,
        pilot_slices_per_object=1,
    )
    candidates = json.loads((tmp_path / "claim_candidates.json").read_text(encoding="utf-8"))
    selection = candidates["claim_plan_audit"]["selection"]

    assert result["candidate_slice_count"] == 2
    assert selection["selection_profile"] == "pilot"
    assert selection["selected_objects"] == ["汤和", "邓愈"]
    assert "张良" in selection["dropped_objects"]
    assert {row["object_name"] for row in candidates["candidate_slices"]} == {"汤和", "邓愈"}
    assert candidates["stats"]["pre_selection_candidate_slices"] == 7
    assert candidates["stats"]["candidate_slices"] == 2


def test_claim_plan_pilot_uses_profile_signals_jsonl(tmp_path: Path) -> None:
    cache_root = tmp_path / "object_cache"
    write_object_cache(cache_root)
    signals = tmp_path / "profile_signals.jsonl"
    write_jsonl(
        signals,
        [
            {"person_name": "张良", "object_type": "strategist", "importance_tier": "core"},
            {"person_name": "常遇春", "object_type": "general", "importance_tier": "important"},
        ],
    )

    result = tool.plan_claim_extraction_from_cache(
        cache_root=cache_root,
        claim_cache_root=tmp_path / "claim_cache",
        output_candidates=tmp_path / "claim_candidates.json",
        output_uncovered_candidates=tmp_path / "claim_candidates.uncovered.json",
        emperor_name="朱元璋",
        target_code="TGT-ZYZ",
        max_slices_per_person=2,
        selection_profile="pilot",
        pilot_object_limit=2,
        pilot_slices_per_object=1,
        pilot_profile_signals_path=signals,
    )
    candidates = json.loads((tmp_path / "claim_candidates.json").read_text(encoding="utf-8"))
    selection = result["claim_plan_audit"]["selection"]

    assert selection["selected_objects"] == ["张良", "常遇春"]
    assert {row["object_name"] for row in candidates["candidate_slices"]} == {"张良", "常遇春"}
    assert result["claim_plan_audit"]["by_object"]["张良"]["profile_signal_score"] == 115
    assert result["claim_plan_audit"]["by_object"]["张良"]["has_biography_source"] is False


def test_claim_plan_cli_priority_object_overrides_mechanical_order(tmp_path: Path) -> None:
    cache_root = tmp_path / "object_cache"
    write_object_cache(cache_root)

    assert tool.main(
        [
            "claim-plan",
            "--cache-root",
            str(cache_root),
            "--claim-cache-root",
            str(tmp_path / "claim_cache"),
            "--output-candidates",
            str(tmp_path / "claim_candidates.json"),
            "--output-uncovered-candidates",
            str(tmp_path / "claim_candidates.uncovered.json"),
            "--emperor-name",
            "朱元璋",
            "--selection-profile",
            "pilot",
            "--pilot-object-limit",
            "1",
            "--pilot-slices-per-object",
            "1",
            "--pilot-priority-object",
            "张良",
            "--output-json",
            str(tmp_path / "claim_plan.json"),
        ]
    ) == 0
    plan = json.loads((tmp_path / "claim_plan.json").read_text(encoding="utf-8"))
    candidates = json.loads((tmp_path / "claim_candidates.json").read_text(encoding="utf-8"))

    assert plan["claim_plan_audit"]["selection"]["selected_objects"] == ["张良"]
    assert candidates["candidate_slices"][0]["object_name"] == "张良"
    assert plan["claim_plan_audit"]["by_object"]["张良"]["profile_signal_reasons"] == [
        "priority_score=100",
        "manual_priority",
    ]


def test_claim_plan_can_enqueue_claim_job_without_running_judge(tmp_path: Path, monkeypatch) -> None:
    cache_root = tmp_path / "object_cache"
    write_object_cache(cache_root)
    calls: list[str] = []

    def fake_job_from_candidates(**kwargs):
        calls.append("job_from_candidates")
        assert kwargs["candidates_path"].name == "claim_candidates.uncovered.json"
        assert kwargs["cache_root"] == tmp_path / "claim_cache"
        return {"job_code": "CLMEXT-TEST", "idem_key": "idem", "uncovered_slice_count": 3}

    def fake_enqueue_job(*, dsn: str, job: dict):
        calls.append("enqueue_job")
        assert dsn == "postgres://example"
        assert job["job_code"] == "CLMEXT-TEST"
        return {"job_id": 9, "job_code": job["job_code"], "idem_key": job["idem_key"]}

    def fake_execute_job(**_kwargs):
        raise AssertionError("claim-plan must not execute claim judge")

    monkeypatch.setattr(tool.claim_worker, "job_from_candidates", fake_job_from_candidates)
    monkeypatch.setattr(tool.claim_worker, "enqueue_job", fake_enqueue_job)
    monkeypatch.setattr(tool.claim_worker, "execute_job", fake_execute_job)

    result = tool.plan_claim_extraction_from_cache(
        cache_root=cache_root,
        claim_cache_root=tmp_path / "claim_cache",
        output_candidates=tmp_path / "claim_candidates.json",
        output_uncovered_candidates=tmp_path / "claim_candidates.uncovered.json",
        emperor_name="朱元璋",
        target_code="TGT-ZYZ",
        enqueue_claim_job=True,
        dsn="postgres://example",
    )

    assert calls == ["job_from_candidates", "enqueue_job"]
    assert result["enqueue"] == {"job_id": 9, "job_code": "CLMEXT-TEST", "idem_key": "idem"}
    assert result["claim_job"]["job_code"] == "CLMEXT-TEST"


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
