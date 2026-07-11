from scripts.dev import retrieval_v3_claim_object_binding_backfill as tool


def test_binding_plan_accepts_unique_and_fails_closed_for_ambiguous_names() -> None:
    report = tool.binding_plan(
        [
            {"claim_key": "A", "object_name": "安禄山", "object_id": 75},
            {"claim_key": "B", "object_name": "同名", "object_id": 1},
            {"claim_key": "B", "object_name": "同名", "object_id": 2},
            {"claim_key": "C", "object_name": "缺人", "object_id": None},
        ]
    )

    assert report["ready_count"] == 1
    assert report["updates"][0]["object_id"] == 75
    assert report["unresolved_by_status"] == {"ambiguous": 1, "unmatched": 1}
