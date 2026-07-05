from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_intake_manifest
from scripts.dev import retrieval_v2_intake_rows as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_manifest_fixture(tmp_path: Path, *, duplicate_passage: bool = False) -> Path:
    run = tmp_path / "run"
    person_dir = run / "TGT-I5B-LH_delegation"
    task = person_dir / "task.final.json"
    candidates = person_dir / "candidates.final.json"
    judge = person_dir / "judge_result.final.json"
    summary = run / "summary.json"
    write_json(task, {"target_code": "TGT-I5B-LH", "emperor_name": "刘恒", "item_code": "I5B", "rule_code": "delegation"})
    write_json(
        candidates,
        {
            "coverage": {"objects_without_slices": ["冯唐"]},
            "coverage_gaps": [{"gap_type": "alias_missing", "object_name": "冯唐"}],
            "fetch_errors": [{"title": "史記/卷102", "diagnosis": "timeout"}],
        },
    )
    passages = [
        {
            "passage_code": "PAS-001",
            "document_code": "DOC-001",
            "locator": "chars:1-20",
            "quote": "上令冯唐持节赦魏尚。",
        }
    ]
    source_passage_refs = ["PAS-001"]
    if duplicate_passage:
        passages.append(
            {
                "passage_code": "PAS-002",
                "document_code": "DOC-001",
                "locator": "chars:1-20",
                "quote": "上令冯唐持节赦魏尚。",
            }
        )
        source_passage_refs = ["PAS-002", "PAS-001"]
    write_json(
        judge,
        {
            "status": "succeeded",
            "documents": [{"document_code": "DOC-001", "title": "史記/卷102", "source_kind": "wikisource_page"}],
            "passages": passages,
            "claims": [
                {
                    "claim_code": "CLM-001",
                    "emperor_name": "刘恒",
                    "object_name": "冯唐",
                    "direction": "positive",
                    "claim_summary": "文帝遣冯唐持节赦魏尚。",
                    "source_passage_refs": source_passage_refs,
                }
            ],
            "primary_bindings": [
                {
                    "claim_code": "CLM-001",
                    "rule_code": "delegation",
                    "predicate": "delegated_authority",
                    "direction": "positive",
                    "object_role": "civil_delegate",
                    "usable_for_object_payload": True,
                    "usable_for_scoring_cluster": True,
                }
            ],
            "secondary_binding_candidates": [{"claim_code": "CLM-001", "rule_code": "team_building", "reason": "shared"}],
            "coverage_gaps": [
                {"gap_type": "negative_undercoverage", "object_name": "冯唐"},
                {"gap_type": "negative_undercoverage", "object_name": "冯唐"},
            ],
        },
    )
    write_json(
        summary,
        {
            "people": [
                {
                    "name": "刘恒",
                    "judge_status": "succeeded",
                    "judge_anomaly_block_count": 0,
                    "files": {
                        "final_task": str(task),
                        "final_candidates": str(candidates),
                        "final_judge_result": str(judge),
                    },
                }
            ]
        },
    )
    manifest = retrieval_v2_intake_manifest.build_manifest(summary_paths=[summary])
    manifest_path = tmp_path / "intake_manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path


def test_build_rows_namespaces_codes_and_preserves_refs(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)

    rows = tool.build_rows(manifest_path)

    pack_code = rows["source_packs"][0]["source_pack_code"]
    assert rows["source_documents"][0]["document_code"] == f"{pack_code}::DOC-001"
    assert rows["source_passages"][0]["passage_code"] == f"{pack_code}::PAS-001"
    assert rows["source_passages"][0]["document_code"] == f"{pack_code}::DOC-001"
    assert rows["material_claims"][0]["claim_code"] == f"{pack_code}::CLM-001"
    assert rows["material_claims"][0]["source_passage_refs"] == [f"{pack_code}::PAS-001"]
    assert rows["primary_claim_rule_bindings"][0]["claim_code"] == f"{pack_code}::CLM-001"
    assert rows["secondary_binding_candidates"][0]["claim_code"] == f"{pack_code}::CLM-001"
    assert rows["claim_rule_binding_candidates"][0]["claim_code"] == f"{pack_code}::CLM-001"
    assert rows["claim_rule_binding_candidates"][0]["source_item_code"] == "I5B"
    assert rows["claim_rule_binding_candidates"][0]["source_rule_code"] == "delegation"
    assert rows["claim_rule_binding_candidates"][0]["candidate_item_code"] == ""
    assert rows["claim_rule_binding_candidates"][0]["candidate_rule_code"] == "team_building"
    assert rows["claim_rule_binding_candidates"][0]["review_status"] == "pending"


def test_build_rows_dedupes_passages_by_document_locator_quote(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path, duplicate_passage=True)

    rows = tool.build_rows(manifest_path)

    pack_code = rows["source_packs"][0]["source_pack_code"]
    assert len(rows["source_passages"]) == 1
    assert rows["source_passages"][0]["passage_code"] == f"{pack_code}::PAS-001"
    assert rows["source_passages"][0]["deduped_raw_passage_codes"] == ["PAS-002"]
    assert rows["material_claims"][0]["source_passage_refs"] == [f"{pack_code}::PAS-001"]


def test_build_rows_disambiguates_duplicate_document_codes(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    judge_path = tmp_path / "run" / "TGT-I5B-LH_delegation" / "judge_result.final.json"
    judge = json.loads(judge_path.read_text(encoding="utf-8"))
    judge["documents"] = [
        {"document_code": "DOC-001", "title": "漢書/卷001", "source_kind": "wikisource_page"},
        {"document_code": "DOC-001", "title": "資治通鑑/卷013", "source_kind": "wikisource_page"},
    ]
    write_json(judge_path, judge)

    rows = tool.build_rows(manifest_path)

    pack_code = rows["source_packs"][0]["source_pack_code"]
    document_codes = [row["document_code"] for row in rows["source_documents"]]
    raw_document_codes = [row["raw_document_code"] for row in rows["source_documents"]]
    assert len(document_codes) == len(set(document_codes))
    assert len(raw_document_codes) == len(set(raw_document_codes))
    assert document_codes[-1] == f"{pack_code}::DOC-001"
    assert document_codes[0].startswith(f"{pack_code}::DOC-001--ALT-")
    assert raw_document_codes[-1] == "DOC-001"
    assert raw_document_codes[0].startswith("DOC-001--ALT-")
    assert rows["source_documents"][0]["original_raw_document_code"] == "DOC-001"
    assert rows["source_passages"][0]["document_code"] == f"{pack_code}::DOC-001"


def test_build_rows_preserves_claim_and_binding_review_status(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    judge_path = tmp_path / "run" / "TGT-I5B-LH_delegation" / "judge_result.final.json"
    judge = json.loads(judge_path.read_text(encoding="utf-8"))
    judge["claims"][0]["review_status"] = "needs_review"
    judge["primary_bindings"][0]["review_status"] = "needs_review"
    write_json(judge_path, judge)

    rows = tool.build_rows(manifest_path)

    assert rows["material_claims"][0]["review_status"] == "needs_review"
    assert rows["primary_claim_rule_bindings"][0]["review_status"] == "needs_review"


def test_build_rows_emits_gap_events_with_source_pack_code(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)

    rows = tool.build_rows(manifest_path)
    gaps = rows["coverage_gap_events"]
    keys = {(row["source"], row["gap_type"], row["queue"], row["object_name"]) for row in gaps}

    assert ("objects_without_slices", "source_missing", "source_pack_refinement", "冯唐") in keys
    assert ("candidate_coverage_gap", "alias_missing", "source_pack_refinement", "冯唐") in keys
    assert ("fetch_error", "fetch_error", "source_pack_refinement", "史記/卷102") in keys
    assert ("judge_coverage_gap", "negative_undercoverage", "source_pack_refinement", "冯唐") in keys
    assert all(row["source_pack_code"] == rows["source_packs"][0]["source_pack_code"] for row in gaps)
    assert len({row["idem_key"] for row in gaps}) == len(gaps)


def test_main_writes_jsonl_rowset(tmp_path: Path, capsys) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    output_root = tmp_path / "rows"

    assert tool.main(["build", "--manifest", str(manifest_path), "--output-root", str(output_root)]) == 0

    assert (output_root / "material_claims.jsonl").exists()
    summary = json.loads((output_root / "normalized_summary.json").read_text(encoding="utf-8"))
    assert summary["totals"]["material_claims"] == 1
    assert json.loads(capsys.readouterr().out)["totals"]["source_packs"] == 1
