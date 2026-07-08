from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_cache as claim_cache
from scripts.dev import retrieval_v2_claim_cache_review_patch as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_candidates() -> dict:
    return {
        "candidate_slices": [
            {
                "slice_code": "SLI-001",
                "document_code": "DOC-001",
                "object_name": "汤和",
                "text": "太祖命汤和守常州，常州安辑。",
            },
            {
                "slice_code": "SLI-002",
                "document_code": "DOC-002",
                "object_name": "汤和",
                "text": "太祖又命汤和巡视海防。",
            },
        ]
    }


def sample_claim() -> dict:
    return {
        "claim_code": "CLM-001",
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": "朱元璋命汤和镇守常州。",
        "direction": "positive",
        "confidence": 0.9,
        "source_slice_refs": ["SLI-001", "SLI-002"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "朱元璋",
            "object": "汤和",
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "outcome": "守常州",
            "time_context": "洪武初",
            "source_span_refs": ["SLI-001", "SLI-002"],
            "confidence": 0.9,
        },
        "evidence_spans": [
            {"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"},
            {"span_type": "context", "source_slice_ref": "SLI-002", "text": "命汤和巡视海防"},
        ],
    }


def write_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "run"
    person_dir = run_root / "TGT-I5B-ZYZ"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(candidates_path, sample_candidates())
    write_json(judge_path, {"status": "succeeded", "claims": [sample_claim()]})
    write_json(
        run_root / "summary.json",
        {
            "elapsed_seconds": 1.0,
            "clean_policy": {"extractor_version": "claim_extraction_only:test"},
            "people": [
                {
                    "name": "朱元璋",
                    "files": {
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ],
        },
    )
    return run_root


def write_patch(path: Path, *, claim_key: str, evidence_key: str) -> None:
    rows = [
        {
            "patch_type": "claim_update",
            "claim_key": claim_key,
            "direction": "neutral",
            "action_type": "处置",
            "scope_role": "review_required",
            "review_note": "人工复核后改为中性处置材料。",
        },
        {
            "patch_type": "evidence_drop",
            "evidence_key": evidence_key,
            "reason": "该证据只作上下文，不直接支撑 claim。",
        },
    ]
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_review_patch_dry_run_does_not_write_cache(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    claim_cache.import_run(write_run(tmp_path), cache_root)
    claim = claim_cache.read_jsonl(cache_root / "claims.jsonl")[0]
    evidence = claim_cache.read_jsonl(cache_root / "claim_evidence.jsonl")
    patch_path = tmp_path / "patch.jsonl"
    write_patch(patch_path, claim_key=claim["claim_key"], evidence_key=evidence[0]["evidence_key"])

    report = tool.apply_review_patch(
        cache_root=cache_root,
        patch_rows=tool.read_jsonl(patch_path),
        patch_code="PATCH-TEST",
        execute=False,
        sync_pg=False,
        env_file=None,
        dsn_env=tool.DEFAULT_DSN_ENV,
    )

    assert report["ok"] is True
    assert report["write_files"] is False
    assert report["cache_report"]["counts_after"]["evidence"] == 1
    claims_after = claim_cache.read_jsonl(cache_root / "claims.jsonl")
    evidence_after = claim_cache.read_jsonl(cache_root / "claim_evidence.jsonl")
    assert claims_after[0]["direction"] == "positive"
    assert len(evidence_after) == 2


def test_review_patch_execute_updates_claim_and_drops_evidence(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    claim_cache.import_run(write_run(tmp_path), cache_root)
    claim = claim_cache.read_jsonl(cache_root / "claims.jsonl")[0]
    evidence = claim_cache.read_jsonl(cache_root / "claim_evidence.jsonl")
    patch_path = tmp_path / "patch.jsonl"
    write_patch(patch_path, claim_key=claim["claim_key"], evidence_key=evidence[0]["evidence_key"])

    report = tool.apply_review_patch(
        cache_root=cache_root,
        patch_rows=tool.read_jsonl(patch_path),
        patch_code="PATCH-TEST",
        execute=True,
        sync_pg=False,
        env_file=None,
        dsn_env=tool.DEFAULT_DSN_ENV,
    )

    claims_after = claim_cache.read_jsonl(cache_root / "claims.jsonl")
    evidence_after = claim_cache.read_jsonl(cache_root / "claim_evidence.jsonl")
    slices_after = claim_cache.read_jsonl(cache_root / "source_slices.jsonl")
    fact = claims_after[0]["fact_payload"]

    assert report["ok"] is True
    assert report["write_files"] is True
    assert report["cache_report"]["backup_dir"]
    assert claims_after[0]["direction"] == "neutral"
    assert claims_after[0]["action_type"] == "处置"
    assert fact["direction"] == "neutral"
    assert fact["action_type"] == "处置"
    assert fact["manual_reviews"][-1]["scope_role"] == "review_required"
    assert len(evidence_after) == 1
    assert len(slices_after) == 1
    assert evidence_after[0]["evidence_key"] != evidence[0]["evidence_key"]


def test_review_patch_reports_missing_targets(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    claim_cache.import_run(write_run(tmp_path), cache_root)
    rows = [
        {"patch_type": "claim_update", "claim_key": "CLMK-MISSING", "direction": "neutral"},
        {"patch_type": "evidence_drop", "evidence_key": "EVD-MISSING"},
    ]

    report = tool.apply_review_patch(
        cache_root=cache_root,
        patch_rows=rows,
        patch_code="PATCH-TEST",
        execute=True,
        sync_pg=False,
        env_file=None,
        dsn_env=tool.DEFAULT_DSN_ENV,
    )

    assert report["ok"] is False
    assert report["write_files"] is False
    assert {issue["issue_code"] for issue in report["cache_report"]["issues"]} == {"claim_not_found", "evidence_not_found"}
