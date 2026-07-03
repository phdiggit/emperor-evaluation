from __future__ import annotations

import argparse
from pathlib import Path

from scripts.dev import i5b_source_pack_runtime_supervisor as tool


def test_supervisor_builds_independent_worker_and_refiner_commands(tmp_path: Path) -> None:
    args = argparse.Namespace(
        python="python3",
        worker_script=tmp_path / "source-pack-worker.py",
        refiner_script=tmp_path / "i5b_query_profile_refiner_daemon.py",
        profile=tmp_path / "profiles.jsonl",
        all_list=tmp_path / "all.yml",
        source_pack_root=tmp_path / "source-packs",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        workflow_code="I5B",
        refiner_output_dir=tmp_path / "reports",
        refiner_interval_seconds=60,
        max_queries_per_object=5,
        fetch_max_queries_per_object=4,
        include_adjacent=False,
        pipeline_script=None,
    )

    specs = tool.build_child_specs(args)

    assert [spec.name for spec in specs] == ["source-pack-worker", "query-profile-refiner"]
    assert specs[0].cmd == ["python3", str(tmp_path / "source-pack-worker.py")]
    assert str(tmp_path / "i5b_query_profile_refiner_daemon.py") in specs[1].cmd
    assert "--workflow-code" in specs[1].cmd
    assert "I5B" in specs[1].cmd
    assert "--output-dir" in specs[1].cmd
    assert str(tmp_path / "reports") in specs[1].cmd
    assert "--include-adjacent" not in specs[1].cmd


def test_supervisor_can_add_pipeline_child_when_enabled(tmp_path: Path) -> None:
    args = argparse.Namespace(
        python="python3",
        worker_script=tmp_path / "source-pack-worker.py",
        refiner_script=tmp_path / "i5b_query_profile_refiner_daemon.py",
        pipeline_script=tmp_path / "i5b_source_pack_pipeline_daemon.py",
        profile=tmp_path / "profiles.jsonl",
        all_list=tmp_path / "all.yml",
        source_pack_root=tmp_path / "source-packs",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        workflow_code="I5A",
        refiner_output_dir=tmp_path / "reports",
        refiner_interval_seconds=60,
        max_queries_per_object=5,
        fetch_max_queries_per_object=4,
        include_adjacent=True,
        pipeline_output_dir=tmp_path / "reports",
        pipeline_interval_seconds=60,
        pipeline_max_jobs_per_run=8,
        pipeline_max_refine_rounds_per_person=2,
        pipeline_submit_prepared=False,
        pipeline_submit_refinements=True,
    )

    specs = tool.build_child_specs(args)

    assert [spec.name for spec in specs] == ["source-pack-worker", "query-profile-refiner", "source-pack-pipeline"]
    assert "--workflow-code" in specs[1].cmd
    assert "I5A" in specs[1].cmd
    assert str(tmp_path / "i5b_source_pack_pipeline_daemon.py") in specs[2].cmd
    assert "--submit-refinements" in specs[2].cmd
    assert "--include-adjacent" in specs[2].cmd
    assert "--workflow-code" in specs[2].cmd
    assert "I5A" in specs[2].cmd
    assert "--max-jobs-per-run" in specs[2].cmd
    assert "--max-refine-rounds-per-person" in specs[2].cmd
