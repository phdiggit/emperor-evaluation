"""Validate explicit M1 failure adjudications, never infer a historical grade."""

DECISIONS = {"PASS", "BLOCK_G5"}
TIER_BASES = {"PERSON_NEGATIVE_RESULT", "FAILURE_IMPACT_TIER", "UNSPLIT_MIXED", "PROCESS_ONLY"}


def verify_failure_aliases(records: list[dict]) -> None:
    """An explicitly merged parent cannot survive as another counted failure."""
    seen = set()
    for record in records:
        refs = [record["campaign_ref"], *record.get("source_alias_refs", [])]
        assert len(refs) == len(set(refs)) and not seen.intersection(refs), "duplicate source failure alias"
        seen.update(refs)


def verify_stability_review(row: dict) -> None:
    required = row["axis_grade"] == "G5" or (row["axis_grade"], row["position"]) == ("G4", "HIGH")
    review = row.get("m1_stability_review")
    if review is None:
        assert not required, f"missing M1 failure review: {row['ruler_id']}"
        return
    label = row["ruler_id"]
    assert review["schema_version"] == "m1-stability-review-v1", label
    assert review["published_grade"] == row["axis_grade"] and review["published_position"] == row["position"], f"stale M1 failure decision: {label}"
    assert review["decision"] in DECISIONS and review["basis"].strip(), label
    assert review["source_refs"] and review["reviewed_under_contract"] == "FORMAL-V1.3", label
    seen = set()
    blockers = []
    for case in review["cases"]:
        refs = [case["cycle_ref"], *case["alias_refs"]]
        assert len(refs) == len(set(refs)) and not seen.intersection(refs), f"duplicate M1 failure cycle: {label}"
        seen.update(refs)
        assert case["source_refs"] and case["tier_basis"] in TIER_BASES, label
        assert case["negative_tier"] in {None, "C", "B", "A", "S-", "S", "S+"}, label
        if case["tier_basis"] in {"UNSPLIT_MIXED", "PROCESS_ONLY"}:
            assert case["negative_tier"] is None, f"mixed parent copied as negative tier: {label}"
        for key in ("label", "consequence", "attribution", "feedback", "recovery", "residual_loss", "decision_basis"):
            assert case[key].strip(), f"missing M1 failure reasoning: {label}/{key}"
        assert case["effect"] in {"POSITION_LIMIT", "NO_CAPABILITY_PENALTY", "BLOCK_G5"}, label
        if case["effect"] == "BLOCK_G5":
            blockers.append(case)
            assert case["pattern_changing_basis"].strip(), f"missing pattern-changing evidence: {label}"
    assert (review["decision"] == "BLOCK_G5") == bool(blockers), f"M1 blocker/conclusion mismatch: {label}"
    assert not (blockers and row["axis_grade"] == "G5"), f"G5 with explicit failure blocker: {label}"
