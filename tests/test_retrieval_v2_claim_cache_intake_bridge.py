from __future__ import annotations

import json

from scripts.dev import retrieval_v2_claim_cache_intake_bridge as tool
from scripts.dev import retrieval_v2_import_plan as import_plan


def chain() -> dict:
    return {
        "emperor_name": "刘邦",
        "members": [{"claim_key": "CLMK-1"}, {"claim_key": "CLMK-2"}, {"claim_key": "CLMK-3"}],
    }


def evidence(claim_key: str) -> dict:
    return {
        "claim_key": claim_key,
        "emperor_name": "刘邦",
        "object_name": "郦食其",
        "object_type": "person",
        "claim_type": "material_action",
        "claim_summary": f"刘邦任用郦食其 {claim_key}",
        "confidence": 0.8,
        "fact_payload": {"action_type": "任命"},
        "canonical_event_key": "EVT-1",
        "event_group_key": "EG-1",
        "evidence_key": f"EVD-{claim_key}",
        "slice_hash": f"SLH-{claim_key}",
        "document_code": "DOC-1",
        "raw_document_code": "DOC-1",
        "source_title": "史记",
        "source_url": "https://zh.wikisource.org/wiki/史记",
        "source_slice_ref": f"SLI-{claim_key}",
        "text_hash": "",
    }


def test_build_rows_creates_draft_materials_without_object_or_binding_rows(tmp_path) -> None:
    evidence_rows = [evidence(key) for key in ("CLMK-1", "CLMK-2", "CLMK-3")]
    rows = tool.build_rows(
        chains=[chain()],
        targets=[{"target_code": "TGT-I5B-LB", "emperor_name": "刘邦", "item_code": "I5B"}],
        evidence_rows=evidence_rows,
        full_texts={f"SLH-{key}": f"刘邦任用郦食其 {key}" for key in ("CLMK-1", "CLMK-2", "CLMK-3")},
    )
    tool.write_rows(tmp_path, rows)

    assert len(rows["source_packs"]) == 1
    assert len(rows["material_claims"]) == 3
    assert rows["primary_claim_rule_bindings"] == []
    assert rows["material_claims"][0]["claim_payload"]["cached_claim_key"] == "CLMK-1"
    assert rows["material_claims"][0]["claim_payload"]["cache_intake"]["object_identity_gate"] == "deferred_until_formal_binding"
    plan = import_plan.build_plan(normalized_root=tmp_path, lookup={"targets": {"TGT-I5B-LB": {}}})
    assert plan["blockers"] == []


def test_build_rows_rejects_preview_only_slice() -> None:
    try:
        tool.build_rows(
            chains=[chain()],
            targets=[{"target_code": "TGT-I5B-LB", "emperor_name": "刘邦", "item_code": "I5B"}],
            evidence_rows=[evidence(key) for key in ("CLMK-1", "CLMK-2", "CLMK-3")],
            full_texts={},
        )
    except tool.ClaimCacheIntakeBridgeError as exc:
        assert "missing full slice text" in str(exc)
    else:
        raise AssertionError("preview-only material must not enter staging")


def test_hydrate_full_texts_from_original_candidate_artifact(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "judge_result.final.json").write_text("{}", encoding="utf-8")
    candidate = {"document_code": "DOC-1", "slice_code": "SLI-1", "text": "刘邦任用郦食其"}
    slice_hash = tool.fs_cache.slice_hash_from_row(candidate)
    (run_dir / "candidates.final.json").write_text(json.dumps({"candidate_slices": [candidate]}, ensure_ascii=False), encoding="utf-8")

    texts = tool.hydrate_full_texts_from_raw_runs(
        [{"slice_hash": slice_hash, "raw_output_path": str(run_dir / "judge_result.final.json")}],
        full_texts={},
    )

    assert texts[slice_hash] == "刘邦任用郦食其"
