from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_expected_event_repair_plan as tool
from scripts.dev import retrieval_v2_claim_plan_quality as claim_plan_quality


def reconciliation(decision: str, *, ref: str = "OSS-1") -> dict:
    return {
        "decision": decision,
        "event_inventory_code": f"EEI-{decision}",
        "emperor_name": "李世民",
        "object_id": 7,
        "object_name": "李靖",
        "event_label": "目标事件",
        "importance": "major",
        "source_slice_refs": [ref] if decision == "reextract_cached_source" else [],
        "claim_keys": ["CLMK-1"],
        "group_keys": ["CEG-1", "CEG-2"],
        "missing_facets": [],
        "review_note": "有限修复。",
    }


def test_build_repair_plan_keeps_only_reconciled_slices_and_docs() -> None:
    plan = tool.build_repair_plan(
        [reconciliation("reextract_cached_source"), reconciliation("rebuild_event_group")],
        source_documents=[
            {"document_cache_code": "DOC-1"},
            {"document_cache_code": "DOC-OTHER"},
        ],
        mention_slices=[
            {"slice_cache_code": "OSS-1", "document_cache_code": "DOC-1", "person_name": "李靖", "raw_text": "目标"},
            {"slice_cache_code": "OSS-OTHER", "document_cache_code": "DOC-OTHER", "person_name": "李靖", "raw_text": "无关"},
        ],
        person_seeds=[{"name": "李靖"}, {"name": "房玄龄"}],
        person_coverage=[{"person_name": "李靖"}, {"person_name": "房玄龄"}],
    )

    assert [row["slice_cache_code"] for row in plan["mention_slices"]] == ["OSS-1"]
    assert [row["document_cache_code"] for row in plan["source_documents"]] == ["DOC-1"]
    assert plan["mention_slices"][0]["expected_event_repair"]["event_inventory_codes"] == ["EEI-reextract_cached_source"]
    assert plan["report"]["reextract_event_count"] == 1
    assert plan["report"]["rebuild_event_group_count"] == 1
    assert plan["report"]["new_source_fetch_allowed"] is False


def test_missing_reconciled_slice_is_rejected() -> None:
    with pytest.raises(tool.ExpectedEventRepairPlanError, match="missing from cache"):
        tool.build_repair_plan(
            [reconciliation("reextract_cached_source", ref="OSS-MISSING")],
            source_documents=[],
            mention_slices=[],
            person_seeds=[],
            person_coverage=[],
        )


def test_reconciliation_approval_can_bypass_only_wrong_section_for_direct_alias() -> None:
    candidate = {
        "text": "命李𪟝为朔方行军总管，大破薛延陀。",
        "object_name": "李绩",
        "matched_aliases": ["李𪟝"],
        "object_source_cache": {
            "section_heading": "贞观十五年",
            "source_shape": "object_biography_candidate",
            "slice_kind": "expected_event_repair",
        },
    }

    assert claim_plan_quality.claim_candidate_quality_flags(candidate) == ["wrong_person_section"]
    assert claim_plan_quality.is_claim_candidate_slice_eligible(candidate) is True


def test_reconciliation_approval_requires_target_alias_in_slice() -> None:
    candidate = {
        "text": "他人受命出征。",
        "object_name": "李绩",
        "matched_aliases": ["李𪟝"],
        "object_source_cache": {
            "section_heading": "贞观十五年",
            "source_shape": "object_biography_candidate",
            "slice_kind": "expected_event_repair",
        },
    }

    assert claim_plan_quality.is_claim_candidate_slice_eligible(candidate) is False


def test_tool_is_report_only_and_does_not_use_legacy_contract_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")
    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source
    assert "insert into" not in source.lower()
    assert "new_source_fetch_allowed" in source
