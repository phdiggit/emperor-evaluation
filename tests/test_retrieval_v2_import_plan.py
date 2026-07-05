from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_import_plan as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_fixture(root: Path, review_root: Path | None = None, *, missing_passage_ref: bool = False, bad_candidate_direction: bool = False) -> dict[str, str]:
    pack = "SPK-I5B-LH-DELEGATION-ABC"
    target = "TGT-I5B-LH"
    doc = f"{pack}::DOC-001"
    passage = f"{pack}::PAS-001"
    claim = f"{pack}::CLM-001"
    binding = f"{pack}::BND-001"
    candidate = f"{pack}::CRBC-001"
    source_passage_refs = [f"{pack}::PAS-MISSING"] if missing_passage_ref else [passage]
    write_jsonl(
        root / "source_packs.jsonl",
        [
            {
                "source_pack_code": pack,
                "target_code": target,
                "emperor_name": "刘恒",
                "item_code": "I5B",
                "rule_code": "delegation",
                "run_root": "tmp/run",
                "run_dir": "tmp/run/TGT-I5B-LH_delegation",
                "manifest_payload": {"accepted": True},
            }
        ],
    )
    write_jsonl(root / "source_pack_artifacts.jsonl", [{"source_pack_code": pack, "kind": "judge", "path": "judge.json"}])
    write_jsonl(
        root / "source_documents.jsonl",
        [
            {
                "source_pack_code": pack,
                "document_code": doc,
                "raw_document_code": "DOC-001",
                "title": "史記/卷102",
                "source_title": "史記",
            }
        ],
    )
    write_jsonl(
        root / "source_passages.jsonl",
        [
            {
                "source_pack_code": pack,
                "document_code": doc,
                "passage_code": passage,
                "raw_passage_code": "PAS-001",
                "locator": "chars:1-20",
                "raw_text": "上令冯唐持节赦魏尚。",
                "quote_hash": "abc",
            }
        ],
    )
    write_jsonl(
        root / "material_claims.jsonl",
        [
            {
                "source_pack_code": pack,
                "claim_code": claim,
                "raw_claim_code": "CLM-001",
                "emperor_name": "刘恒",
                "object_name": "冯唐",
                "object_type": "person",
                "claim_summary": "文帝遣冯唐持节赦魏尚。",
                "direction": "positive",
                "source_passage_refs": source_passage_refs,
            }
        ],
    )
    write_jsonl(
        root / "primary_claim_rule_bindings.jsonl",
        [
            {
                "source_pack_code": pack,
                "binding_code": binding,
                "raw_binding_code": "BND-001",
                "claim_code": claim,
                "rule_code": "delegation",
                "predicate": "delegated_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
            }
        ],
    )
    write_jsonl(
        root / "claim_rule_binding_candidates.jsonl",
        [
            {
                "source_pack_code": pack,
                "candidate_code": candidate,
                "claim_code": claim,
                "source_item_code": "I5B",
                "source_rule_code": "delegation",
                "candidate_item_code": "",
                "candidate_rule_code": "team_building",
                "candidate_direction": "sideways" if bad_candidate_direction else "",
                "reason": "同一事实也可提示团队建设。",
            }
        ],
    )
    write_jsonl(root / "coverage_gap_events.jsonl", [{"idem_key": "gap-1", "source_pack_code": pack, "target_code": target, "rule_code": "delegation"}])
    if review_root is not None:
        write_jsonl(
            review_root / "object_resolution_worklist.jsonl",
            [
                {
                    "object_resolution_code": "ORW-001",
                    "emperor_name": "刘恒",
                    "item_code": "I5B",
                    "object_group_key": "冯唐",
                    "canonical_name_candidate": "冯唐",
                    "object_types": ["person"],
                    "review_status": "candidate_new_or_existing",
                    "review_reasons": ["single_person_like_name"],
                    "source_pack_codes": [pack],
                }
            ],
        )
        write_jsonl(
            review_root / "material_review_worklist.jsonl",
            [
                {
                    "material_review_code": "MRW-001",
                    "review_status": "needs_review",
                    "review_flags": ["low_confidence"],
                    "claim_code": claim,
                    "binding_code": binding,
                }
            ],
        )
    return {"pack": pack, "target": target, "claim": claim, "binding": binding}


def test_build_plan_creates_dry_run_operations(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized"
    review = tmp_path / "review"
    write_fixture(normalized, review)

    payload = tool.build_plan(normalized_root=normalized, review_root=review)

    assert payload["ok"] is True
    assert payload["write_db"] is False
    assert payload["totals"]["blockers"] == 0
    assert payload["operation_counts"]["retrieval_v2.source_packs"] == 1
    assert payload["operation_counts"]["retrieval_v2.claim_source_passages"] == 1
    assert payload["operation_counts"]["retrieval_v2.object_resolution_queue"] == 1
    assert payload["operation_counts"]["retrieval_v2.material_review_queue"] == 1
    assert payload["deferred"]["objects"] == 1
    assert payload["review_queue"]["queued_material_reviews"] == 1


def test_build_plan_blocks_missing_passage_refs(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized, missing_passage_ref=True)

    payload = tool.build_plan(normalized_root=normalized)

    assert payload["ok"] is False
    assert any(item["code"] == "missing_source_passage_ref" for item in payload["blockers"])


def test_build_plan_blocks_invalid_candidate_direction(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized, bad_candidate_direction=True)

    payload = tool.build_plan(normalized_root=normalized)

    assert payload["ok"] is False
    assert any(item["code"] == "invalid_direction" for item in payload["blockers"])


def test_build_plan_blocks_duplicate_raw_document_code_per_pack(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized)
    rows = [
        json.loads(line)
        for line in (normalized / "source_documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    duplicate = dict(rows[0])
    duplicate["document_code"] = duplicate["document_code"] + "-ALT"
    duplicate["title"] = "資治通鑑/卷013"
    rows.append(duplicate)
    write_jsonl(normalized / "source_documents.jsonl", rows)

    payload = tool.build_plan(normalized_root=normalized)

    assert payload["ok"] is False
    assert any(item["code"] == "duplicate_raw_document_code" for item in payload["blockers"])


def test_build_plan_db_lookup_blocks_missing_target(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized"
    write_fixture(normalized)

    payload = tool.build_plan(normalized_root=normalized, lookup={"targets": {}, "contract_rules": {}})

    assert payload["ok"] is False
    assert any(item["code"] == "missing_target" for item in payload["blockers"])


def test_main_writes_plan_and_markdown(tmp_path: Path, capsys) -> None:
    normalized = tmp_path / "normalized"
    review = tmp_path / "review"
    write_fixture(normalized, review)
    output_json = tmp_path / "plan.json"
    output_md = tmp_path / "plan.md"

    assert tool.main([
        "plan",
        "--normalized-root",
        str(normalized),
        "--review-root",
        str(review),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["ok"] is True
    assert "retrieval_v2 import dry-run plan" in output_md.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["ok"] is True
