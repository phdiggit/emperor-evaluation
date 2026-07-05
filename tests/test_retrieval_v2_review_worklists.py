from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_review_worklists as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_normalized_fixture(root: Path) -> None:
    pack_code = "SPK-I5B-LH-DELEGATION-ABC"
    claim_code = f"{pack_code}::CLM-001"
    passage_code = f"{pack_code}::PAS-001"
    binding_code = f"{pack_code}::BND-001"
    write_jsonl(root / "source_packs.jsonl", [{"source_pack_code": pack_code, "emperor_name": "刘恒"}])
    write_jsonl(
        root / "source_passages.jsonl",
        [
            {
                "source_pack_code": pack_code,
                "passage_code": passage_code,
                "document_code": f"{pack_code}::DOC-001",
                "locator": "chars:1-20",
                "raw_text": "上令冯唐持节赦魏尚。",
            }
        ],
    )
    write_jsonl(
        root / "material_claims.jsonl",
        [
            {
                "source_pack_code": pack_code,
                "claim_code": claim_code,
                "emperor_name": "刘恒",
                "item_code": "I5B",
                "object_name": "冯唐",
                "object_type": "person",
                "direction": "positive",
                "claim_summary": "文帝遣冯唐持节赦魏尚。",
                "confidence": 0.9,
                "source_passage_refs": [passage_code],
            },
            {
                "source_pack_code": pack_code,
                "claim_code": f"{pack_code}::CLM-002",
                "emperor_name": "刘恒",
                "item_code": "I5B",
                "object_name": "馮唐",
                "object_type": "person",
                "direction": "positive",
                "claim_summary": "同一对象繁体写法。",
                "confidence": 0.9,
                "source_passage_refs": [passage_code],
            },
        ],
    )
    write_jsonl(
        root / "primary_claim_rule_bindings.jsonl",
        [
            {
                "source_pack_code": pack_code,
                "binding_code": binding_code,
                "claim_code": claim_code,
                "rule_code": "delegation",
                "predicate": "delegated_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "confidence": 0.9,
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
            },
            {
                "source_pack_code": pack_code,
                "binding_code": f"{pack_code}::BND-002",
                "claim_code": f"{pack_code}::CLM-002",
                "rule_code": "delegation",
                "predicate": "",
                "direction": "positive",
                "object_role": "civil_delegate",
                "confidence": 0.9,
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": False,
            },
        ],
    )
    candidate = {
        "source_pack_code": pack_code,
        "candidate_code": f"{pack_code}::CRBC-001",
        "binding_code": f"{pack_code}::CRBC-001",
        "claim_code": claim_code,
        "source_item_code": "I5B",
        "source_rule_code": "delegation",
        "candidate_item_code": "",
        "candidate_rule_code": "team_building",
        "confidence": 0.8,
        "reason": "shared context",
    }
    write_jsonl(root / "secondary_binding_candidates.jsonl", [candidate])
    write_jsonl(
        root / "claim_rule_binding_candidates.jsonl",
        [
            candidate
        ],
    )
    write_jsonl(root / "coverage_gap_events.jsonl", [])


def test_build_object_resolution_worklist_groups_script_variants(tmp_path: Path) -> None:
    write_normalized_fixture(tmp_path)

    payload = tool.build_worklists(tmp_path)
    objects = payload["object_resolution_worklist"]

    assert len(objects) == 1
    assert objects[0]["observed_names"] == ["冯唐", "馮唐"]
    assert "multiple_observed_names" in objects[0]["review_reasons"]
    assert {"冯唐", "馮唐"} <= set(objects[0]["script_variant_candidates"])


def test_build_material_review_worklist_flags_missing_predicate(tmp_path: Path) -> None:
    write_normalized_fixture(tmp_path)

    payload = tool.build_worklists(tmp_path)
    materials = payload["material_review_worklist"]

    assert materials[0]["review_status"] == "ready_for_object_payload"
    assert materials[0]["secondary_rule_candidates"][0]["candidate_rule_code"] == "team_building"
    assert materials[0]["secondary_rule_candidates"][0]["source_rule_code"] == "delegation"
    assert materials[1]["review_status"] == "needs_review"
    assert "missing_predicate" in materials[1]["review_flags"]
    assert payload["summary"]["totals"]["ready_for_object_payload"] == 1
    assert payload["summary"]["totals"]["material_needs_review"] == 1


def test_main_writes_worklists(tmp_path: Path, capsys) -> None:
    normalized = tmp_path / "normalized"
    output = tmp_path / "worklists"
    write_normalized_fixture(normalized)

    assert tool.main(["build", "--normalized-root", str(normalized), "--output-root", str(output)]) == 0

    assert (output / "object_resolution_worklist.jsonl").exists()
    assert (output / "material_review_worklist.jsonl").exists()
    summary = json.loads((output / "worklist_summary.json").read_text(encoding="utf-8"))
    assert summary["totals"]["material_review_items"] == 2
    assert json.loads(capsys.readouterr().out)["totals"]["object_resolution_items"] == 1
