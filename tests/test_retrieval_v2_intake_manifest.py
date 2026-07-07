from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v2_intake_manifest as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_person_run(
    root: Path,
    *,
    name: str,
    target_code: str,
    status: str = "succeeded",
    anomaly_blocks: int | None = 0,
) -> dict:
    run_dir = root / f"{target_code}_appointment_delegation"
    task_path = run_dir / "task.final.json"
    candidates_path = run_dir / "candidates.final.json"
    judge_path = run_dir / "judge_result.final.json"
    write_json(
        task_path,
        {
            "target_code": target_code,
            "emperor_name": name,
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
        },
    )
    write_json(
        candidates_path,
        {
            "coverage": {"objects_without_slices": ["冯唐"]},
            "coverage_gaps": [{"gap_type": "source_missing", "object_name": "冯唐"}],
            "fetch_errors": [],
        },
    )
    write_json(
        judge_path,
        {
            "status": status,
            "documents": [{"document_code": "DOC-001"}],
            "passages": [{"passage_code": "PAS-001"}],
            "claims": [{"claim_code": "CLM-001", "object_name": "冯唐"}],
            "primary_bindings": [{"claim_code": "CLM-001", "rule_code": "appointment_delegation"}],
            "secondary_binding_candidates": [{"claim_code": "CLM-001", "rule_code": "team_building"}],
            "coverage_gaps": [{"gap_type": "predicate_missing", "object_name": "冯唐"}],
        },
    )
    return {
        "name": name,
        "judge_status": status,
        "judge_anomaly_block_count": anomaly_blocks,
        "candidate_slices": 12,
        "files": {
            "final_task": str(task_path),
            "final_candidates": str(candidates_path),
            "final_judge_result": str(judge_path),
        },
    }


def test_build_manifest_accepts_only_gate_passing_people(tmp_path: Path) -> None:
    run = tmp_path / "run"
    accepted = write_person_run(run, name="刘恒", target_code="TGT-I5B-LH")
    rejected = write_person_run(
        run,
        name="刘庄",
        target_code="TGT-I5B-LZ",
        status="succeeded",
        anomaly_blocks=None,
    )
    summary_path = run / "summary.json"
    write_json(summary_path, {"people": [accepted, rejected]})

    manifest = tool.build_manifest(summary_paths=[summary_path])

    assert manifest["totals"]["accepted"] == 1
    assert manifest["totals"]["rejected"] == 1
    package = manifest["packages"][0]
    assert package["emperor_name"] == "刘恒"
    assert package["source_pack_code"].startswith("SPK-I5B-LH-APPOINTMENT-DELEGATION-")
    assert package["counts"]["claims"] == 1
    assert package["counts"]["primary_bindings"] == 1
    assert package["counts"]["secondary_binding_candidates"] == 1
    assert package["counts"]["judge_coverage_gaps"] == 1
    assert package["objects_without_slices"] == ["冯唐"]
    assert manifest["rejected_packages"][0]["acceptance_issues"] == ["judge_anomaly_block_count_not_zero"]


def test_build_manifest_blocks_duplicate_accepted_package(tmp_path: Path) -> None:
    first = tmp_path / "run-a"
    second = tmp_path / "run-b"
    first_summary = first / "summary.json"
    second_summary = second / "summary.json"
    write_json(first_summary, {"people": [write_person_run(first, name="刘恒", target_code="TGT-I5B-LH")]})
    write_json(second_summary, {"people": [write_person_run(second, name="刘恒", target_code="TGT-I5B-LH")]})

    with pytest.raises(tool.IntakeManifestError, match="duplicate accepted package"):
        tool.build_manifest(summary_paths=[first_summary, second_summary])


def test_main_writes_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    summary_path = run / "summary.json"
    write_json(summary_path, {"people": [write_person_run(run, name="刘恒", target_code="TGT-I5B-LH")]})
    output = tmp_path / "out" / "intake_manifest.json"

    assert tool.main(["build", "--summary", str(summary_path), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["totals"]["accepted"] == 1
    assert json.loads(capsys.readouterr().out)["totals"]["accepted"] == 1
