from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_cache as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_claim(summary: str = "朱元璋命汤和镇守常州。") -> dict:
    return {
        "claim_code": "CLM-001",
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": summary,
        "direction": "positive",
        "confidence": 0.9,
        "source_slice_refs": ["SLI-001"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "朱元璋",
            "object": "汤和",
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "outcome": "守常州",
            "time_context": "洪武初",
            "source_span_refs": ["SLI-001"],
            "confidence": 0.9,
            "completeness": {
                "has_actor": True,
                "has_object": True,
                "has_action": True,
                "has_outcome": True,
                "same_event_chain": True,
                "needs_source_extension": False,
            },
        },
        "evidence_spans": [
            {"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"},
            {"span_type": "outcome", "source_slice_ref": "SLI-001", "text": "常州安辑"},
        ],
    }


def sample_candidates() -> dict:
    return {
        "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-001",
                "document_code": "DOC-001",
                "object_name": "汤和",
                "text": "帝命汤和守常州，常州安辑。",
            },
            {
                "slice_code": "SLI-002",
                "document_code": "DOC-001",
                "object_name": "常遇春",
                "text": "帝命常遇春进兵。",
            },
        ],
    }


def write_run(tmp_path: Path, *, claim: dict | None = None) -> Path:
    run_root = tmp_path / "run"
    person_dir = run_root / "TGT-I5B-ZYZ"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(candidates_path, sample_candidates())
    write_json(
        judge_path,
        {
            "status": "succeeded",
            "claims": [claim or sample_claim()],
            "primary_bindings": [],
            "secondary_binding_candidates": [],
        },
    )
    write_json(
        run_root / "summary.json",
        {
            "elapsed_seconds": 1.0,
            "targets": ["朱元璋"],
            "clean_policy": {"judge_mode": "claim_extraction_only"},
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


def test_claim_key_is_stable_for_same_fact_payload() -> None:
    first = tool.claim_key(sample_claim())
    second = tool.claim_key({**sample_claim("白话摘要不同。"), "claim_code": "CLM-OTHER"})

    assert first != second
    assert first == tool.claim_key(sample_claim())


def test_import_run_dedupes_claims_slices_and_evidence(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"

    first = tool.import_run(run_root, cache_root)
    second = tool.import_run(run_root, cache_root)

    assert first["stats"]["new_claim_count"] == 1
    assert first["stats"]["new_slice_count"] == 1
    assert first["stats"]["new_evidence_count"] == 2
    assert second["stats"]["duplicate_claim_count"] == 1
    assert second["total_cached_claims"] == 1
    assert len(tool.read_jsonl(cache_root / "claims.jsonl")) == 1
    assert len(tool.read_jsonl(cache_root / "source_slices.jsonl")) == 1


def test_plan_candidates_reports_cached_and_uncovered_slices(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates_path = run_root / "TGT-I5B-ZYZ" / "candidates.final.json"
    uncovered_path = tmp_path / "uncovered_candidates.json"

    report = tool.plan_candidates(candidates_path, cache_root, uncovered_path)
    uncovered = json.loads(uncovered_path.read_text(encoding="utf-8"))

    assert report["candidate_slice_count"] == 2
    assert report["cached_slice_count"] == 1
    assert report["uncovered_slice_count"] == 1
    assert report["by_object"]["汤和"]["cached"] == 1
    assert report["by_object"]["常遇春"]["uncovered"] == 1
    assert [row["slice_code"] for row in uncovered["candidate_slices"]] == ["SLI-002"]


def test_cache_inventory_reports_objects_and_candidate_plan(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates_path = run_root / "TGT-I5B-ZYZ" / "candidates.final.json"

    report = tool.cache_inventory(cache_root, candidates_path)

    assert report["totals"]["claim_count"] == 1
    assert report["totals"]["slice_count"] == 1
    assert report["totals"]["object_count"] == 1
    assert report["by_object"]["汤和"]["claim_count"] == 1
    assert report["by_object"]["汤和"]["direction_counts"] == {"positive": 1}
    assert report["candidate_plan"]["cached_slice_count"] == 1
    assert report["candidate_plan"]["uncovered_slice_count"] == 1
    assert "cached_claim_keys" not in report["candidate_plan"]


def test_emit_pg_schema_contains_hot_index_tables() -> None:
    assert "retrieval_v2.claim_cache" in tool.PGSQL_SCHEMA_DRAFT
    assert "retrieval_v2.claim_evidence" in tool.PGSQL_SCHEMA_DRAFT
    assert "retrieval_v2.claim_route_cache" in tool.PGSQL_SCHEMA_DRAFT


def test_emit_pg_schema_command_returns_success(capsys) -> None:
    assert tool.main(["emit-pg-schema"]) == 0
    assert "retrieval_v2.claim_cache" in capsys.readouterr().out


def test_inventory_command_returns_success(tmp_path: Path, capsys) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)

    assert tool.main(["inventory", "--cache-root", str(cache_root), "--sample-limit", "0"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"]["claim_count"] == 1
    assert payload["by_object"]["汤和"]["sample_claims"] == []
