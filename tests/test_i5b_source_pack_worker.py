from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.dev import i5b_source_pack_worker as tool


def sample_config(tmp_path: Path) -> tool.WorkerConfig:
    return tool.WorkerConfig(
        python="python3",
        fetcher_script=tmp_path / "i5b_source_pack_fetcher.py",
        profile=tmp_path / "profiles.jsonl",
        source_pack_root=tmp_path / "source-packs",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        workflow_code="I5B",
        source_scope="I5B offline source pack",
        poll_seconds=15,
    )


def test_build_command_forwards_workflow_and_job_options(tmp_path: Path) -> None:
    config = sample_config(tmp_path)
    output_dir = tmp_path / "out"
    cmd = tool.build_command(
        {
            "person": "武则天",
            "workflow_code": "I5A",
            "source_scope": "I5A source pack",
            "include_adjacent": True,
            "max_queries_per_object": 6,
            "no_cache": True,
        },
        config,
        output_dir,
    )

    assert cmd[:2] == ["python3", str(tmp_path / "i5b_source_pack_fetcher.py")]
    assert cmd[cmd.index("--profile") + 1] == str(tmp_path / "profiles.jsonl")
    assert cmd[cmd.index("--person") + 1] == "武则天"
    assert cmd[cmd.index("--workflow-code") + 1] == "I5A"
    assert cmd[cmd.index("--source-scope") + 1] == "I5A source pack"
    assert cmd[cmd.index("--output-dir") + 1] == str(output_dir)
    assert cmd[cmd.index("--max-queries-per-object") + 1] == "6"
    assert "--include-adjacent" in cmd
    assert "--no-cache" in cmd
    assert "--candidate-discovery" in cmd


def test_process_job_writes_status_and_moves_done(tmp_path: Path, monkeypatch) -> None:
    config = sample_config(tmp_path)
    config.jobs_dir.mkdir()
    config.logs_dir.mkdir()
    config.source_pack_root.mkdir()
    job_path = config.jobs_dir / "job.json"
    job_path.write_text(
        json.dumps({"person": "武则天", "workflow_code": "I5B", "output_name": "wuzetian"}, ensure_ascii=False),
        encoding="utf-8",
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0)

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    tool.process_job(job_path, config)

    assert not job_path.exists()
    assert (config.jobs_dir / "job.json.done").exists()
    status = json.loads((config.logs_dir / "job.json.status.json").read_text(encoding="utf-8"))
    assert status["status"] == "complete"
    assert status["workflow_code"] == "I5B"
    assert status["person"] == "武则天"
    assert status["output_dir"] == str(config.source_pack_root / "wuzetian")
