from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_calibration_report as tool
from scripts.dev import retrieval_v2_claim_cache


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def candidate_slice(code: str, *, object_name: str = "汤和", text: str = "帝命汤和守常州。") -> dict:
    return {
        "slice_code": code,
        "document_code": "DOC-001",
        "object_name": object_name,
        "text": text,
    }


def write_run(
    root: Path,
    *,
    name: str = "朱元璋",
    claims: list[dict] | None = None,
    candidate_slices: list[dict] | None = None,
    status: str = "succeeded",
    judge_shard_count: int = 0,
    usage: dict | None = None,
    coverage_gaps: list[dict] | None = None,
) -> dict:
    person_dir = root / "TGT-I5B"
    candidate_slices = candidate_slices or [candidate_slice("SLI-001")]
    claims = claims or [
        {
            "claim_code": "CLM-001",
            "object_name": candidate_slices[0]["object_name"],
            "direction": "positive",
            "claim_summary": "朱元璋命汤和守常州。",
        }
    ]
    judge = {
        "status": status,
        "claims": claims,
        "primary_bindings": [],
        "coverage_gaps": coverage_gaps or [],
    }
    candidates = {
        "task_identity": {"emperor_name": name, "rule_code": "i5b_item_wide"},
        "stats": {"candidate_slices": len(candidate_slices)},
        "candidate_slices": candidate_slices,
        "coverage": {"objects_without_slices": []},
        "coverage_gaps": [],
    }
    write_json(person_dir / "judge_result.final.json", judge)
    write_json(person_dir / "candidates.final.json", candidates)
    cache_plan = {
        "cache_root": "",
        "candidates_path": str(person_dir / "candidates.final.json"),
        "candidate_slice_count": len(candidate_slices),
        "cached_slice_count": len(candidate_slices),
        "uncovered_slice_count": 0,
        "cached_claim_key_count": len(claims),
        "by_object": {candidate_slices[0]["object_name"]: {"cached": len(candidate_slices), "total": len(candidate_slices)}},
    }
    summary = {
        "ok": True,
        "run_root": str(root),
        "elapsed_seconds": 0.2,
        "pipeline_elapsed_seconds": 0.2,
        "cli_elapsed_seconds": 0.3,
        "total_elapsed_seconds": 0.3,
        "clean_policy": {"judge_mode": "claim_extraction_only"},
        "totals": {
            "candidate_slices": len(candidate_slices),
            "claim_count": len(claims),
            "judge_coverage_gap_count": len(coverage_gaps or []),
            "usage": usage or {},
        },
        "people": [
            {
                "name": name,
                "target_code": "TGT-I5B",
                "rule_code": "i5b_item_wide",
                "judge_status": status,
                "candidate_slices": len(candidate_slices),
                "claim_count": len(claims),
                "judge_coverage_gap_count": len(coverage_gaps or []),
                "candidate_coverage_gap_count": 0,
                "judge_shard_count": judge_shard_count,
                "judge_elapsed_seconds": 0.0 if judge_shard_count == 0 else 12.0,
                "judge_usage": usage or {},
                "object_seed_count": 1,
                "source_document_count": 1,
                "objects_without_slices": [],
                "rounds": [
                    {
                        "claim_cache_plan": cache_plan,
                        "judge_shard_count": judge_shard_count,
                        "judge_status": status,
                    }
                ],
                "files": {
                    "final_judge_result": str(person_dir / "judge_result.final.json"),
                    "final_candidates": str(person_dir / "candidates.final.json"),
                },
            }
        ],
    }
    write_json(root / "summary.json", summary)
    (root / "run_events.jsonl").write_text(
        json.dumps({"event": "pipeline_done", "elapsed_seconds": 0.2}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def write_claim_cache(cache_root: Path, source_slice: dict) -> None:
    slice_hash = retrieval_v2_claim_cache.slice_hash_from_row(source_slice)
    retrieval_v2_claim_cache.write_jsonl(
        cache_root / "claims.jsonl",
        [
            {
                "claim_key": "CLMK-001",
                "emperor_name": "朱元璋",
                "object_name": source_slice["object_name"],
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": "朱元璋命汤和守常州。",
                "direction": "positive",
                "action_type": "授权",
                "fact_payload": {},
            }
        ],
    )
    retrieval_v2_claim_cache.write_jsonl(
        cache_root / "claim_evidence.jsonl",
        [{"evidence_key": "EVD-001", "claim_key": "CLMK-001", "slice_hash": slice_hash, "object_name": source_slice["object_name"]}],
    )
    retrieval_v2_claim_cache.write_jsonl(
        cache_root / "source_slices.jsonl",
        [{"slice_hash": slice_hash, "object_name": source_slice["object_name"], "source_slice_ref": source_slice["slice_code"]}],
    )


def test_calibration_report_summarizes_cache_hit_and_no_alerts(tmp_path: Path) -> None:
    source_slice = candidate_slice("SLI-001")
    run_root = tmp_path / "run"
    cache_root = tmp_path / "cache"
    write_run(run_root, candidate_slices=[source_slice])
    write_claim_cache(cache_root, source_slice)

    report = tool.build_report(run_root=run_root, claim_cache_root=cache_root)

    assert report["totals"]["claim_count"] == 1
    assert report["people"][0]["claim_cache"]["hit_ratio"] == 1.0
    assert report["claim_cache_inventory"]["candidate_plan"]["uncovered_slice_count"] == 0
    assert report["alerts"] == []


def test_calibration_report_flags_judge_and_uncovered_cache_tail(tmp_path: Path) -> None:
    source_slice = candidate_slice("SLI-001")
    drift_slice = candidate_slice("SLI-002", object_name="常遇春", text="帝命常遇春进兵。")
    run_root = tmp_path / "run"
    cache_root = tmp_path / "cache"
    summary = write_run(
        run_root,
        candidate_slices=[source_slice, drift_slice],
        judge_shard_count=2,
        usage={"input_tokens": 100, "output_tokens": 20},
        coverage_gaps=[{"gap_type": "claim_cache_low_hit_ratio"}],
    )
    summary["people"][0]["rounds"][0]["claim_cache_plan"]["cached_slice_count"] = 1
    summary["people"][0]["rounds"][0]["claim_cache_plan"]["uncovered_slice_count"] = 1
    write_json(run_root / "summary.json", summary)
    write_claim_cache(cache_root, source_slice)

    report = tool.build_report(run_root=run_root, claim_cache_root=cache_root)

    alert_codes = {row["code"] for row in report["alerts"]}
    assert "judge_ran" in alert_codes
    assert "judge_gaps_present" in alert_codes
    assert "claim_cache_uncovered_slices" in alert_codes
    assert report["people"][0]["usage"]["input_tokens"] == 100


def test_calibration_report_embeds_quality_gate_delta(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    write_run(
        baseline,
        claims=[{"claim_code": "CLM-001", "object_name": "汤和", "direction": "positive"}],
        candidate_slices=[candidate_slice("SLI-001")],
    )
    write_run(
        candidate,
        claims=[{"claim_code": "CLM-001", "object_name": "李文忠", "direction": "positive"}],
        candidate_slices=[candidate_slice("SLI-002", object_name="李文忠")],
    )

    report = tool.build_report(run_root=candidate, baseline_run_root=baseline)

    assert report["quality_gate"]["ok"] is False
    assert any(row["code"] == "object_coverage_regressed" for row in report["alerts"])


def test_calibration_report_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    write_run(run_root)

    assert tool.main(["--run-root", str(run_root), "--output-json", str(output_json), "--output-md", str(output_md)]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["report_type"] == "retrieval_v2_calibration_report"
    assert "retrieval_v2 calibration report" in output_md.read_text(encoding="utf-8")
