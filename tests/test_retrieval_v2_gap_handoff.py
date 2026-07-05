from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_gap_handoff as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_events_from_summary_routes_clean_gaps_and_anomalies(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    person_dir = run_root / "TGT-I5B-LH_delegation"
    task_path = person_dir / "task.final.json"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    summary_path = run_root / "summary.json"
    write_json(
        task_path,
        {
            "target_code": "TGT-I5B-LH",
            "emperor_name": "刘恒",
            "item_code": "I5B",
            "rule_code": "delegation",
            "source_pack_code": "SPK-LH-DELEGATION",
        },
    )
    write_json(
        candidates_path,
        {
            "coverage": {"objects_without_slices": ["冯唐"]},
            "coverage_gaps": [
                {
                    "gap_type": "alias_missing",
                    "family_code": "civil_delegate",
                    "object_name": "季布",
                    "predicate": "任用",
                    "diagnosis": "needs alias",
                }
            ],
            "fetch_errors": [
                {
                    "document_code": "DOC-102",
                    "title": "史記/卷102",
                    "diagnosis": "temporary fetch failure",
                }
            ],
        },
    )
    write_json(
        judge_path,
        {
            "status": "succeeded",
            "claims": [
                {
                    "claim_code": "CLM-1",
                    "object_name": "晁错",
                    "direction": "mixed",
                }
            ],
            "primary_bindings": [
                {
                    "claim_code": "CLM-1",
                    "direction": "positive",
                    "usable_for_scoring_cluster": True,
                }
            ],
            "coverage_gaps": [
                {
                    "gap_type": "negative_undercoverage",
                    "family_code": "revoked_or_failed_delegate",
                    "object_name": "灌婴",
                    "diagnosis": "negative side missing",
                }
            ],
        },
    )
    write_json(
        summary_path,
        {
            "people": [
                {
                    "name": "刘恒",
                    "files": {
                        "final_task": str(task_path),
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ]
        },
    )

    events = tool.events_from_summary(summary_path)
    keys = {(row["source"], row["gap_type"], row["queue"], row["object_name"]) for row in events}

    assert ("objects_without_slices", "source_missing", "source_pack_refinement", "冯唐") in keys
    assert ("candidate_coverage_gap", "alias_missing", "source_pack_refinement", "季布") in keys
    assert ("fetch_error", "fetch_error", "source_pack_refinement", "史記/卷102") in keys
    assert ("judge_coverage_gap", "negative_undercoverage", "source_pack_refinement", "灌婴") in keys
    assert ("judge_anomaly", "mixed_claim_not_split", "codex_review", "晁错") in keys
    assert all(row["status"] == "ready" for row in events)
    assert any(
        row["idem_key"] == "TGT-I5B-LH|delegation|SPK-LH-DELEGATION|alias_missing|civil_delegate|季布|任用"
        for row in events
    )


def test_events_from_summary_derives_source_pack_fallback_for_idem_key(tmp_path: Path) -> None:
    run_root = tmp_path / "run_without_pack"
    person_dir = run_root / "TGT-I5B-YZ_delegation"
    task_path = person_dir / "task.final.json"
    candidates_path = person_dir / "candidates.final.json"
    summary_path = run_root / "summary.json"
    write_json(
        task_path,
        {
            "target_code": "TGT-I5B-YZ",
            "emperor_name": "嬴政",
            "item_code": "I5B",
            "rule_code": "delegation",
        },
    )
    write_json(candidates_path, {"coverage": {"objects_without_slices": ["屠睢"]}})
    write_json(
        summary_path,
        {
            "people": [
                {
                    "name": "嬴政",
                    "files": {
                        "final_task": str(task_path),
                        "final_candidates": str(candidates_path),
                    },
                }
            ]
        },
    )

    events = tool.events_from_summary(summary_path)

    assert len(events) == 1
    event = events[0]
    assert event["source_pack_code"].startswith("RUN-")
    assert event["source_pack_code"] in event["idem_key"]
    assert event["idem_key"] != "TGT-I5B-YZ|delegation||source_missing||屠睢|"


def test_upsert_gap_events_preserves_existing_lifecycle_status(monkeypatch) -> None:
    executed_sql: list[str] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=None):
            executed_sql.append(sql)

        def fetchone(self):
            return {"target_id": 1, "contract_rule_id": 2, "source_pack_id": None}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

    class FakePsycopg:
        @staticmethod
        def connect(dsn, row_factory=None):
            return FakeConnection()

    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg, object()))
    event = {
        "event_code": "CGE-TEST",
        "idem_key": "TGT|delegation|RUN-1|source_missing||屠睢|",
        "target_code": "TGT",
        "rule_code": "delegation",
        "source_pack_code": "RUN-1",
        "gap_type": "source_missing",
        "queue": "source_pack_refinement",
        "diagnosis": "missing source",
        "recommended_action": "refine",
        "priority": 50,
    }

    assert tool.upsert_gap_events(dsn="postgres://example", events=[event]) == 1

    upsert_sql = next(sql for sql in executed_sql if "insert into retrieval_v2.coverage_gap_events" in sql)
    assert "'ready'" in upsert_sql
    assert "status = case" not in upsert_sql
    assert "else 'ready'" not in upsert_sql


def test_gap_handoff_sql_does_not_revive_existing_lifecycle_status() -> None:
    script = Path(tool.__file__).read_text(encoding="utf-8")

    assert "else 'ready'" not in script


def test_job_from_event_maps_source_refinement_and_codex_review() -> None:
    source_event = {
        "idem_key": "TGT|delegation||alias_missing|civil_delegate|季布|任用",
        "queue": "source_pack_refinement",
        "gap_type": "alias_missing",
        "priority": 50,
    }
    review_event = {
        "idem_key": "TGT|delegation||mixed_claim_not_split||晁错|",
        "queue": "codex_review",
        "gap_type": "mixed_claim_not_split",
        "priority": 40,
    }

    source_job = tool.job_from_event(source_event)
    review_job = tool.job_from_event(review_event)

    assert source_job is not None
    assert source_job["kind"] == "codex_source_pack_refine"
    assert source_job["payload"]["action"] == "alias_refine"
    assert review_job is not None
    assert review_job["kind"] == "codex_material_review"
    assert review_job["payload"]["action"] == "split_or_mark_material_claim"
