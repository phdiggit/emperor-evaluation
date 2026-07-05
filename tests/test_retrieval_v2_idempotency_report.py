from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_idempotency_report as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_normalized_fixture(root: Path, *, duplicate_binding: bool = False) -> None:
    pack = "SPK-I5B-LH-DELEGATION-ABC"
    claim = f"{pack}::CLM-001"
    binding = {
        "source_pack_code": pack,
        "binding_code": f"{pack}::BND-001",
        "claim_code": claim,
        "rule_code": "delegation",
        "predicate": "delegated_authority",
        "direction": "positive",
        "object_role": "civil_delegate",
    }
    write_jsonl(root / "source_packs.jsonl", [{"source_pack_code": pack}])
    write_jsonl(root / "source_pack_artifacts.jsonl", [{"source_pack_code": pack, "kind": "judge", "path": "judge.json"}])
    write_jsonl(root / "source_documents.jsonl", [{"source_pack_code": pack, "document_code": f"{pack}::DOC-001", "raw_document_code": "DOC-001"}])
    write_jsonl(root / "source_passages.jsonl", [{"source_pack_code": pack, "passage_code": f"{pack}::PAS-001", "raw_passage_code": "PAS-001", "document_code": f"{pack}::DOC-001", "locator": "1", "quote_hash": "abc"}])
    write_jsonl(root / "material_claims.jsonl", [{"source_pack_code": pack, "claim_code": claim, "raw_claim_code": "CLM-001", "emperor_name": "刘恒", "item_code": "I5B", "object_name": "冯唐", "direction": "positive", "claim_summary": "文帝遣冯唐。"}])
    bindings = [binding, {**binding, "binding_code": f"{pack}::BND-002"}] if duplicate_binding else [binding]
    write_jsonl(root / "primary_claim_rule_bindings.jsonl", bindings)
    write_jsonl(root / "claim_rule_binding_candidates.jsonl", [{"source_pack_code": pack, "candidate_code": f"{pack}::CRBC-001", "claim_code": claim, "source_rule_code": "delegation", "candidate_item_code": "", "candidate_rule_code": "team_building", "reason": "shared"}])
    write_jsonl(root / "secondary_binding_candidates.jsonl", [])
    write_jsonl(root / "coverage_gap_events.jsonl", [{"idem_key": "gap-1"}])


def test_report_passes_unique_rows(tmp_path: Path) -> None:
    write_normalized_fixture(tmp_path)

    payload = tool.build_report(normalized_root=tmp_path)

    assert payload["ok"] is True
    assert payload["totals"]["blocks"] == 0
    assert payload["tables"]["primary_claim_rule_bindings"]["duplicate_natural_keys"]["claim_rule_predicate_direction_role"]["count"] == 0


def test_report_blocks_duplicate_binding_natural_key(tmp_path: Path) -> None:
    write_normalized_fixture(tmp_path, duplicate_binding=True)

    payload = tool.build_report(normalized_root=tmp_path)

    assert payload["ok"] is False
    assert any(issue["code"] == "duplicate_claim_rule_predicate_direction_role" for issue in payload["blocks"])


def test_main_writes_report_and_schema_draft(tmp_path: Path, capsys) -> None:
    normalized = tmp_path / "normalized"
    write_normalized_fixture(normalized)
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    schema = tmp_path / "schema.md"

    assert tool.main([
        "report",
        "--normalized-root",
        str(normalized),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
        "--schema-draft",
        str(schema),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["ok"] is True
    schema_text = schema.read_text(encoding="utf-8")
    assert "claim_rule_binding_candidates" in schema_text
    assert "所有表和字段必须写数据库注释" in schema_text
    assert "说明字段只保存信息熵高" in schema_text
    assert "优先使用 PostgreSQL enum type" in schema_text
    assert json.loads(capsys.readouterr().out)["ok"] is True
