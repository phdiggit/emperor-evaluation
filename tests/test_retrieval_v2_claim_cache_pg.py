from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_cache as fs_tool
from scripts.dev import retrieval_v2_claim_cache_pg as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_cache(cache_root: Path) -> None:
    slice_hash = fs_tool.slice_hash_from_row(
        {
            "slice_code": "SLI-001",
            "document_code": "DOC-001",
            "object_name": "汤和",
            "text": "帝命汤和守常州，常州安辑。",
        }
    )
    claim = {
        "claim_key": "CLMK-001",
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "object_type": "person",
        "direction": "positive",
        "claim_summary": "朱元璋命汤和镇守常州。",
        "confidence": 0.9,
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "朱元璋",
            "object": "汤和",
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "outcome": "常州安辑",
            "time_context": "洪武初",
        },
        "first_run_code": "RUN-001",
        "last_run_code": "RUN-001",
        "raw_output_path": "/tmp/judge_result.final.json",
        "extractor_version": "claim_extraction_only",
        "status": "active",
        "seen_count": 2,
    }
    source_slice = {
        "slice_hash": slice_hash,
        "object_name": "汤和",
        "document_code": "DOC-001",
        "source_slice_ref": "SLI-001",
        "slice_text_preview": "帝命汤和守常州，常州安辑。",
        "first_run_code": "RUN-001",
        "seen_count": 2,
    }
    evidence = {
        "evidence_key": "EVD-001",
        "claim_key": "CLMK-001",
        "slice_hash": slice_hash,
        "source_slice_ref": "SLI-001",
        "document_code": "DOC-001",
        "object_name": "汤和",
        "span_payload": {"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"},
        "slice_text_preview": "帝命汤和守常州，常州安辑。",
        "raw_output_path": "/tmp/judge_result.final.json",
        "first_run_code": "RUN-001",
    }
    write_jsonl(cache_root / "claims.jsonl", [claim])
    write_jsonl(cache_root / "source_slices.jsonl", [source_slice])
    write_jsonl(cache_root / "claim_evidence.jsonl", [evidence])
    write_jsonl(cache_root / "import_runs.jsonl", [{"run_code": "RUN-001", "claim_key_count": 1}])


def test_prepared_cache_rows_maps_filesystem_cache_to_pg_shape(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)

    rows = tool.prepared_cache_rows(cache_root)

    assert tool.row_counts(rows) == {
        "claim_cache": 1,
        "claim_source_slices": 1,
        "claim_evidence": 1,
        "import_runs": 1,
    }
    assert rows["claims"][0]["claim_type"] == "material_action"
    assert rows["claims"][0]["fact_schema"] == "political_action_v1"
    assert rows["claims"][0]["action_type"] == "授权"
    assert rows["claims"][0]["seen_count"] == 2
    assert rows["source_slices"][0]["text_hash"]
    assert rows["claim_evidence"][0]["support_level"] == "direct"
    assert rows["claim_evidence"][0]["quote_preview"] == "命汤和守常州"
    assert tool.validate_prepared_rows(rows) == []


def test_validate_prepared_rows_reports_broken_evidence(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)
    write_jsonl(
        cache_root / "claim_evidence.jsonl",
        [
            {
                "evidence_key": "EVD-BAD",
                "claim_key": "CLMK-MISSING",
                "slice_hash": "SLH-MISSING",
            }
        ],
    )

    rows = tool.prepared_cache_rows(cache_root)
    issues = tool.validate_prepared_rows(rows)

    assert {issue["kind"] for issue in issues} == {"evidence_missing_claim", "evidence_missing_slice"}


def test_object_inventory_counts_directions_and_actions(tmp_path: Path) -> None:
    cache_root = tmp_path / "claim_cache"
    write_cache(cache_root)

    inventory = tool.object_inventory(tool.prepared_cache_rows(cache_root))

    assert inventory["汤和"]["claim_count"] == 1
    assert inventory["汤和"]["direction_counts"] == {"positive": 1}
    assert inventory["汤和"]["action_type_counts"] == {"授权": 1}


def test_claim_cache_pg_sql_stays_in_cache_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    rendered = tool.schema_cursor
    assert rendered
    assert tool.DEFAULT_DSN_ENV == "EMPEROR_EVAL_RETRIEVAL_V3_DSN"
    assert tool.DEFAULT_PG_SCHEMA == "retrieval_v3"
    assert "retrieval_v2.claim_cache" in source
    assert "retrieval_v2.claim_source_slices" in source
    assert "retrieval_v2.claim_evidence" in source
    assert "insert into retrieval_v2.claim_rule_bindings" not in source
    assert "insert into retrieval_v2.target_rule_score_clusters" not in source
