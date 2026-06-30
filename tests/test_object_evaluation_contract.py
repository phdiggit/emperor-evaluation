from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "object_evaluation_b2_examples.jsonl"

OBJECT_CLASSES = {
    "person",
    "team",
    "event_case",
    "mechanism",
    "institution",
    "policy",
    "relationship",
    "source_statement",
}
OUTCOMES = {
    "objectized",
    "adjacent_only",
    "no_stable_object",
    "unresolved_lead",
    "excluded_from_subitem",
}
OEVAL_REQUIRED = {
    "oeval_id",
    "obj_id",
    "src_ids",
    "sp_ids",
    "clus_ids",
    "class",
    "category",
    "relation",
    "polarity",
    "strength",
    "relevance",
    "directness",
    "scale",
    "structurality",
    "confidence",
    "residual",
    "eligible",
}
OBJECT_ALLOWED = {
    "row_type",
    "outcome",
    "obj_id",
    "class",
    "category",
    "label",
    "src_ids",
    "sp_ids",
}
PROCESSING_ALLOWED = {
    "row_type",
    "outcome",
    "src_ids",
    "sp_ids",
    "clus_ids",
    "category",
    "relation",
    "residual",
    "eligible",
}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_b2_fixture_keeps_compact_object_evaluation_fields() -> None:
    rows = read_jsonl(FIXTURE)
    object_ids = {
        str(row["obj_id"])
        for row in rows
        if row.get("row_type") == "object"
    }

    assert object_ids

    for row in rows:
        assert row["outcome"] in OUTCOMES

        if row["row_type"] == "object":
            assert set(row) <= OBJECT_ALLOWED
            assert row["obj_id"] in object_ids
            assert row["class"] in OBJECT_CLASSES
            assert row["outcome"] == "objectized"
            assert isinstance(row["src_ids"], list)
            assert isinstance(row["sp_ids"], list)
            assert "polarity" not in row
            assert "strength" not in row
            assert "eligible" not in row
            continue

        if row["row_type"] == "object_evaluation":
            assert set(row) == OEVAL_REQUIRED | {"row_type", "outcome"}
            assert row["outcome"] == "objectized"
            assert row["obj_id"] in object_ids
            assert row["class"] in OBJECT_CLASSES
            assert row["polarity"] in {"positive", "negative"}
            assert row["strength"] in {1, 2, 3, 4}
            assert isinstance(row["src_ids"], list) and row["src_ids"]
            assert isinstance(row["sp_ids"], list) and row["sp_ids"]
            assert isinstance(row["clus_ids"], list)
            assert isinstance(row["eligible"], bool)
            continue

        if row["row_type"] == "processing_outcome":
            assert set(row) <= PROCESSING_ALLOWED
            assert row["outcome"] == "adjacent_only"
            assert row["eligible"] is False
            assert "obj_id" not in row
            assert "oeval_id" not in row
            continue

        raise AssertionError(f"unexpected row_type: {row['row_type']}")


def test_b2_fixture_covers_required_migration_examples() -> None:
    rows = read_jsonl(FIXTURE)
    labels = {
        str(row["label"])
        for row in rows
        if row.get("row_type") == "object"
    }
    relations = {
        str(row["relation"])
        for row in rows
        if row.get("row_type") == "object_evaluation"
    }
    categories = {
        str(row["category"])
        for row in rows
        if row.get("row_type") == "object_evaluation"
    }

    assert {"虞世基", "不可谏/无一言谏诤", "周亚夫", "晁错", "丙吉荐才链"} <= labels
    assert {
        "专典机密授权",
        "反馈壅蔽",
        "将相授权专任",
        "功臣旧臣处置",
        "荐才链识人拔擢",
    } <= relations
    assert {"授权专任", "容谏纳言", "功臣旧臣处置", "识人拔擢"} <= categories
    assert any(row.get("outcome") == "adjacent_only" for row in rows)
