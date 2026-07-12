from pathlib import Path

from scripts.dev import retrieval_v3_person_profile_worker as worker


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/migrations/20260712_retrieval_v3_person_profile_jobs.sql").read_text(encoding="utf-8")


def test_profile_job_migration_backfills_existing_incomplete_profiles() -> None:
    assert "create table if not exists retrieval_v3.person_profile_jobs" in SQL
    assert "claim_pending_authority" in SQL
    assert "talent_evaluable" in SQL
    assert "enqueue_person_profile_job" in SQL
    assert "after insert or update of readiness_status" in SQL


def test_extract_fallback_writes_marked_jsonl(tmp_path: Path) -> None:
    last = tmp_path / "last.md"
    patch = tmp_path / "patch.jsonl"
    last.write_text(
        "before\nPATCH_JSONL_BEGIN\n{\"task_kind\":\"person_talent_grade\"}\nPATCH_JSONL_END\nafter\n",
        encoding="utf-8",
    )
    assert worker.extract_fallback(last, patch)
    assert '"person_talent_grade"' in patch.read_text(encoding="utf-8")


def test_execute_task_enables_web_search(monkeypatch, tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    patch = tmp_path / "patch.jsonl"
    last = tmp_path / "last.md"
    prompt.write_text("review", encoding="utf-8")
    patch.write_text("{}\n", encoding="utf-8")
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return type("Done", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(worker.subprocess, "run", fake_run)
    result = worker.execute_task(
        {
            "task_code": "T",
            "prompt_path": str(prompt),
            "patch_path": str(patch),
            "last_message_path": str(last),
            "argv": ["codex", "exec", "-"],
        },
        timeout_seconds=10,
    )
    assert "--search" in seen["argv"]
    assert result["patch_exists"] is True


def test_main_uses_injected_environment_without_env_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(worker, "resolve_dsn", lambda _name: "postgresql://injected")
    monkeypatch.setattr(worker, "run_once", lambda **_kwargs: {"status": "idle"})
    assert worker.main(["--output-root", str(tmp_path)]) == 0
