from __future__ import annotations

from scripts.dev import retrieval_v3_person_identity_audit as tool


def row(object_id: int, name: str, status: str = "active") -> dict:
    return {"object_id": object_id, "canonical_name": name, "identity_status": status}


def test_stage_identity_with_single_base_is_auto_merge_ready() -> None:
    report = tool.identity_candidates([row(94, "年羹尧"), row(95, "年羹尧早期任用")])
    candidate = report["candidates"][0]
    assert candidate["status"] == "auto_merge_ready"
    assert candidate["canonical_candidates"] == [94]
    assert candidate["merge_object_ids"] == [95]


def test_stage_identity_without_base_fails_closed() -> None:
    report = tool.identity_candidates([row(95, "年羹尧早期任用")])
    assert report["candidates"][0]["status"] == "missing_canonical"


def test_exact_active_duplicates_require_review() -> None:
    report = tool.identity_candidates([row(1, "王珪"), row(2, "王珪")])
    assert report["candidates"][0]["candidate_type"] == "exact_name_duplicate"
    assert report["candidates"][0]["status"] == "needs_review"


def test_merged_stage_shell_is_not_reported() -> None:
    report = tool.identity_candidates([row(94, "年羹尧"), row(95, "年羹尧早期任用", "merged")])
    assert report["candidate_group_count"] == 0
