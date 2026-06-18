from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUERY_PROFILE_BATCH_PATH = ROOT / "data" / "query_profile_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
SEARCH_LOG_BATCH_PATH = ROOT / "data" / "search_log_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def test_expanded_pilot_batch1_query_profiles_are_intake_only() -> None:
    rows = load_jsonl(QUERY_PROFILE_BATCH_PATH)

    assert len(rows) == 4
    assert {row["status"] for row in rows} == {"batch_pending_merge"}
    assert {row["person"] for row in rows} == {"雍正", "赵匡胤", "嬴政", "武则天"}
    for row in rows:
        assert row["profile_scope"] == "person_level"
        assert row["profile_role"] == "person_level_query_profile"
        assert row["subitem"] == "第五项B"
        assert "score" not in row
        assert "rank" not in row


def test_expanded_pilot_batch1_search_logs_are_leads_only() -> None:
    rows = load_jsonl(SEARCH_LOG_BATCH_PATH)

    assert len(rows) == 8
    assert {row["status"] for row in rows} == {"lead_needs_source_review"}
    assert {row["person"] for row in rows} == {"雍正", "赵匡胤", "嬴政", "武则天"}
    for row in rows:
        assert row["subitem"] == "第五项B"
        assert row["linked_source_ids"] == []
        assert row["linked_evidence_ids"] == []
        assert "score" not in row
        assert "rank" not in row
