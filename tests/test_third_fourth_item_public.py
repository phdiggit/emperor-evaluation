from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.third_fourth_item_public import (
    PUBLIC_FORBIDDEN_RE,
    verify_public_projection,
)


ROOT = Path(__file__).resolve().parents[1]


def test_third_fourth_public_projection_covers_the_current_pool_without_score_drift():
    report = verify_public_projection(ROOT)

    assert report["status"] == "PASS"
    assert report["third_item"]["record_count"] == report["fourth_item"]["record_count"]
    assert report["third_item"]["source_record_counts"]["total"] == report["third_item"]["record_count"]
    assert report["fourth_item"]["package_count"] > 0


def test_reader_consumes_explicit_public_evidence_for_third_and_fourth_items():
    projected = []
    for path in (ROOT / "reader/data/people").glob("*.json"):
        detail = json.loads(path.read_text(encoding="utf-8"))
        groups = ((detail.get("record") or {}).get("net") or {}).get("component_details", {})
        for group in ("strategic", "military", "civilization"):
            projected.extend(
                item for item in groups.get(group, [])
                if item.get("reader_kind") == "judgment"
            )

    assert projected
    for item in projected:
        evidence = item.get("reader_public_evidence_items")
        assert item.get("public_component_label")
        assert item.get("reader_summary")
        assert isinstance(evidence, list) and evidence
        assert evidence == item["public_evidence_items"]
        assert "reader_full_basis" not in item
        for entry in evidence:
            for field in ("public_label", "public_role", "public_basis", "public_boundary"):
                assert not PUBLIC_FORBIDDEN_RE.search(entry[field])


def test_reader_translation_helpers_are_formatters_only_for_third_and_fourth_public_text():
    for name in ("reader/home-interactions.js", "reader/person-readability.js"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "replace(/\\bML" not in text
        assert "replace(/\\bCIV" not in text
        assert "replace(/\\bDA" not in text
