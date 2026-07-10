from scripts.dev import retrieval_v3_context_review_tasks as tool


def item(code: str, *, has_context: bool) -> dict:
    return {
        "workitem_code": f"CTX-{code}",
        "review_code": code,
        "next_action": "context_review" if has_context else "targeted_v3_source_pack_fetch",
        "context_passages": [{"passage_code": "PAS-X", "raw_text": "命魏徵。"}] if has_context else [],
    }


def test_reviewable_requires_context_passages() -> None:
    assert tool.reviewable(item("CRW-A", has_context=True)) is True
    assert tool.reviewable(item("CRW-B", has_context=False)) is False


def test_write_outputs_generates_tasks_only_for_context_candidates(tmp_path) -> None:
    summary = tool.write_outputs(
        [item("CRW-A", has_context=True), item("CRW-B", has_context=False)],
        tmp_path,
        batch_size=1,
    )
    assert summary["context_review_candidate_count"] == 1
    assert summary["deferred_source_fetch_count"] == 1
    assert summary["task_count"] == 1
    assert '"task_kind":"retrieval_v3_needs_context_review"' in (tmp_path / "codex_tasks.jsonl").read_text(encoding="utf-8")
    assert '"review_code":"CRW-B"' in (tmp_path / "deferred_source_fetch_workitems.jsonl").read_text(encoding="utf-8")
