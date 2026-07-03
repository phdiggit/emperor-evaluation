from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_query_profile_refiner_daemon as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_refiner_daemon_once_writes_status_and_refinement_reports(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles.jsonl"
    write_jsonl(
        profile_path,
        [
            {
                "person": "甲",
                "query_profile_id": "QRY-A",
                "source_group": "historical_seed",
                "source_targets": ["旧唐书"],
                "object_layers": {"core_positive_objects": ["张三"], "negative_or_reversal_objects": []},
                "query_bundles": ["甲 张三 旧唐书 任用"],
            }
        ],
    )
    pack = tmp_path / "packs" / "pack-a"
    write_json(pack / "manifest.json", {"schema_version": 1, "status": "complete", "person": "甲"})
    write_json(
        pack / "fetch_report.json",
        {
            "person": "甲",
            "status": "complete",
            "written_pages": 1,
            "excerpts": 0,
            "errors": [],
            "object_coverage": {"objects_without_page_hits": [], "objects_without_excerpts": ["张三"]},
        },
    )
    write_jsonl(pack / "src_docs.jsonl", [{"page_title": "舊唐書/卷1", "object_names": ["张三"]}])
    output_dir = tmp_path / "reports"

    status = tool.run_once(
        profile_path=profile_path,
        all_list=tmp_path / "missing.yml",
        source_pack_root=tmp_path / "packs",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        output_dir=output_dir,
        target_statuses=["fetched_needs_profile_work"],
        max_queries_per_object=3,
    )

    assert status["status"] == "ok"
    assert status["workflow_code"] == "I5B"
    assert (output_dir / "i5b_source_pack_status.json").exists()
    refinement = json.loads((output_dir / "i5b_query_profile_refinements.json").read_text(encoding="utf-8"))
    assert refinement["workflow_code"] == "I5B"
    assert refinement["totals"]["persons"] == 1
    assert refinement["totals"]["object_refinements"] == 1


def test_refiner_daemon_uses_workflow_code_for_output_stems(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"

    status = tool.run_once(
        profile_path=tmp_path / "missing-profiles.jsonl",
        all_list=tmp_path / "missing.yml",
        source_pack_root=tmp_path / "packs",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        output_dir=output_dir,
        workflow_code="I5A",
        target_statuses=["fetched_needs_profile_work"],
        max_queries_per_object=3,
    )

    assert status["workflow_code"] == "I5A"
    assert (output_dir / "i5a_source_pack_status.json").exists()
    assert (output_dir / "i5a_source_pack_status.md").exists()
    assert (output_dir / "i5a_query_profile_refinements.json").exists()
    assert (output_dir / "i5a_query_profile_refinements.md").exists()
    assert (output_dir / "i5a_query_profile_refiner_daemon.status.json").exists()
    assert not (output_dir / "i5b_query_profile_refinements.json").exists()
