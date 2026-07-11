from __future__ import annotations

from pathlib import Path

from scripts.dev import retrieval_v3_coverage_controller as tool
from scripts.dev import retrieval_v3_coverage_convergence as convergence


def claim(
    *,
    name: str = "测试对象",
    object_id: int | None = 7,
    action: str = "任命",
    domain: str = "主持修订法典",
    outcome: str = "修订完成并施行",
    groups: list[str] | None = None,
    updated_at: str = "2026-07-11T10:00:00+08:00",
) -> dict:
    group_keys = groups if groups is not None else ["CEG-1"]
    return {
        "emperor_name": "测试帝",
        "object_id": object_id,
        "object_name": name,
        "object_type": "臣僚",
        "active_claim_count": 1,
        "source_document_count": 1,
        "evidence_count": 1,
        "event_group_count": len(group_keys),
        "event_group_member_count": 1 if group_keys else 0,
        "event_group_keys": group_keys,
        "action_type": action,
        "fact_type": "appointment",
        "office_or_domain": domain,
        "outcome": outcome,
        "outcome_support": "positive",
        "claim_summary": f"{name}{domain}，{outcome}。",
        "fact_payload": {},
        "latest_claim_at": updated_at,
    }


def target(*, name: str = "测试对象", object_id: int = 7, aliases: list[str] | None = None) -> dict:
    return {
        "emperor_name": "测试帝",
        "object_id": object_id,
        "object_name": name,
        "canonical_name": name,
        "object_type": "臣僚",
        "names": aliases or [],
    }


def downstream(
    *,
    name: str = "测试对象",
    materials: int = 1,
    candidates: int = 1,
    bindings: int = 1,
    scoring_bindings: int = 1,
    factors: int = 1,
    updated_at: str = "2026-07-11T11:00:00+08:00",
) -> dict:
    return {
        "emperor_name": "测试帝",
        "object_name": name,
        "object_type": "臣僚",
        "material_claim_count": materials,
        "candidate_count": candidates,
        "unresolved_candidate_count": max(candidates - bindings, 0),
        "binding_count": bindings,
        "scoring_binding_count": scoring_bindings,
        "factor_judgment_count": factors,
        "latest_consumed_at": updated_at,
    }


def report(claims: list[dict], downstream_rows: list[dict], targets: list[dict]) -> dict:
    return tool.build_report(
        claim_rows=claims,
        downstream_rows=downstream_rows,
        target_rows=targets,
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
    )


def test_cache_only_mention_does_not_create_downstream_scoring_work() -> None:
    row = claim(action="记载", domain="", outcome="", groups=[])
    row["fact_type"] = "biography_context"
    row["outcome_support"] = "context_only"

    result = report([row], [], [target()])

    object_row = result["objects"][0]
    assert object_row["scoring_relevant"] is False
    assert [gap["gap_type"] for gap in object_row["gaps"]] == ["event_group_stale_or_missing"]


def test_ready_claim_chain_is_blocked_until_native_material_promotion() -> None:
    result = report([claim()], [], [target()])

    object_row = result["objects"][0]
    assert object_row["chain_ready"] is True
    assert object_row["coverage_status"] == "blocked"
    assert "material_claim_missing" in [gap["gap_type"] for gap in object_row["gaps"]]
    assert result["repair_plan"][0] == {"next_action": "promote_claim_cache_to_material", "object_count": 1}


def test_incomplete_downstream_chain_reports_candidate_binding_and_factor_gaps() -> None:
    candidate_gap = report([claim()], [downstream(candidates=0, bindings=0, scoring_bindings=0, factors=0)], [target()])
    binding_gap = report([claim()], [downstream(bindings=0, scoring_bindings=0, factors=0)], [target()])
    factor_gap = report([claim()], [downstream(factors=0)], [target()])

    assert "candidate_missing" in [item["gap_type"] for item in candidate_gap["objects"][0]["gaps"]]
    assert "binding_missing" in [item["gap_type"] for item in binding_gap["objects"][0]["gaps"]]
    assert "factorization_missing" in [item["gap_type"] for item in factor_gap["objects"][0]["gaps"]]


def test_alias_name_merges_downstream_with_canonical_identity() -> None:
    result = report(
        [claim(name="李勣")],
        [downstream(name="李绩")],
        [target(name="李勣", aliases=["李绩", "徐世勣"])],
    )

    assert len(result["objects"]) == 1
    assert result["objects"][0]["object_id"] == 7
    assert result["objects"][0]["material_claim_count"] == 1


def test_new_claim_after_consumption_is_marked_stale() -> None:
    result = report(
        [claim(updated_at="2026-07-11T12:00:00+08:00")],
        [downstream(updated_at="2026-07-11T11:00:00+08:00")],
        [target()],
    )

    assert "consumption_stale" in [item["gap_type"] for item in result["objects"][0]["gaps"]]


def test_signals_from_different_event_groups_do_not_form_a_ready_chain() -> None:
    appointment = claim(action="任命", domain="", outcome="", groups=["CEG-A"])
    appointment["outcome_support"] = "unknown"
    result_claim = claim(action="记载", domain="", outcome="大破敌军", groups=["CEG-B"])
    result_claim["fact_type"] = "result"

    result = report([appointment, result_claim], [], [target()])

    assert result["objects"][0]["chain_ready"] is False
    assert "material_claim_missing" not in [item["gap_type"] for item in result["objects"][0]["gaps"]]


def test_same_name_with_two_object_ids_is_an_identity_conflict() -> None:
    result = report([claim(object_id=8)], [], [target(object_id=7)])

    assert len(result["objects"]) == 2
    assert all("identity_conflict" in [gap["gap_type"] for gap in row["gaps"]] for row in result["objects"])


def test_unclaimed_cached_source_slice_creates_extraction_coverage_gap() -> None:
    result = tool.build_report(
        claim_rows=[claim()],
        downstream_rows=[downstream()],
        target_rows=[target()],
        source_rows=[
            {
                "emperor_name": "测试帝",
                "object_id": 7,
                "object_name": "测试对象",
                "source_slice_count": 3,
                "claimed_source_slice_count": 2,
                "source_document_count": 2,
            }
        ],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
    )

    object_row = result["objects"][0]
    assert object_row["unclaimed_source_slice_count"] == 1
    assert "source_slice_unclaimed" in [gap["gap_type"] for gap in object_row["gaps"]]


def expected_event(*, outcome_terms: list[str] | None = None) -> dict:
    return {
        "event_inventory_code": "EEI-EAST-TURK",
        "emperor_name": "测试帝",
        "object_id": 7,
        "object_name": "测试对象",
        "event_label": "受命出征并灭东突厥",
        "importance": "major",
        "direction": "positive",
        "event_anchor_terms": ["东突厥", "颉利"],
        "duty_anchor_terms": ["行军总管", "出征"],
        "outcome_anchor_terms": outcome_terms or ["俘颉利", "灭东突厥"],
        "source_leads": [{"source_title": "旧唐书"}],
    }


def test_expected_major_event_requires_explicit_result_anchor_in_same_group() -> None:
    row = claim(action="任命行军总管", domain="出征东突厥", outcome="推进至阴山")
    row["claim_summary"] = "任命为行军总管，出征东突厥并推进至阴山。"
    result = tool.build_report(
        claim_rows=[row],
        downstream_rows=[downstream()],
        target_rows=[target()],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
        expected_events=[expected_event()],
    )

    object_row = result["objects"][0]
    assert object_row["expected_event_assessments"][0]["coverage_status"] == "partial"
    assert "historical_event_missing" in [gap["gap_type"] for gap in object_row["gaps"]]
    assert object_row["coverage_status"] == "blocked"


def test_expected_event_is_covered_only_when_all_facets_share_event_group() -> None:
    row = claim(action="任命行军总管", domain="出征东突厥", outcome="俘颉利，灭东突厥")
    row["claim_summary"] = "任命为行军总管，出征东突厥并追击颉利，最终俘颉利、灭东突厥。"
    result = tool.build_report(
        claim_rows=[row],
        downstream_rows=[downstream()],
        target_rows=[target()],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
        expected_events=[expected_event()],
    )

    object_row = result["objects"][0]
    assert object_row["covered_expected_event_count"] == 1
    assert object_row["expected_event_assessments"][0]["coverage_status"] == "covered"
    assert "historical_event_missing" not in [gap["gap_type"] for gap in object_row["gaps"]]


def test_missing_expected_event_becomes_read_only_source_refinement_workitem() -> None:
    row = claim(action="任命行军总管", domain="出征东突厥", outcome="推进至阴山")
    row["claim_summary"] = "任命为行军总管，出征东突厥并推进至阴山。"
    result = tool.build_report(
        claim_rows=[row],
        downstream_rows=[downstream()],
        target_rows=[target()],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
        expected_events=[expected_event()],
    )

    workitem = tool.build_source_refinement_worklist(result)[0]
    assert workitem["event_inventory_code"] == "EEI-EAST-TURK"
    assert workitem["missing_facets"] == ["event_anchor", "outcome"]
    assert workitem["priority"] == 20
    assert workitem["next_stage"] == "object_source_cache_then_claim_extraction"
    assert workitem["scoring_allowed"] is False


def test_no_relevant_event_assessment_is_not_treated_as_unassessed() -> None:
    assessment = {
        "record_type": "object_assessment",
        "emperor_name": "测试帝",
        "object_name": "测试对象",
        "inventory_verdict": "no_relevant_events",
    }
    result = tool.build_report(
        claim_rows=[claim()],
        downstream_rows=[downstream()],
        target_rows=[target()],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
        expected_events=[assessment],
    )

    object_row = result["objects"][0]
    assert object_row["historical_event_coverage_status"] == "assessed_no_relevant_events"
    assert object_row["expected_event_count"] == 0
    assert result["inventory_object_assessment_count"] == 1


def test_controller_is_read_only_and_does_not_connect_legacy_contract_tables() -> None:
    result = report([claim()], [downstream()], [target()])
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert result["write_db"] is False
    assert result["mode"] == "read_only_source_to_score_coverage"
    assert result["historical_event_coverage_status"] == "unassessed_without_expected_event_inventory"
    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source
    assert "insert into" not in source.lower()


def test_repair_verification_overrides_mechanical_event_status_and_preserves_history() -> None:
    reports = [
        {
            "gate_mode": "initial_actionability",
            "results": [{"event_inventory_code": "EEI-EAST-TURK", "decision": "reextract_cached_source"}],
        },
        {
            "gate_mode": "repair_verification",
            "results": [{"event_inventory_code": "EEI-EAST-TURK", "decision": "rebuild_event_group"}],
        },
    ]
    result = tool.build_report(
        claim_rows=[claim(action="任命行军总管", domain="出征东突厥", outcome="推进至阴山")],
        downstream_rows=[downstream()],
        target_rows=[target()],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
        expected_events=[expected_event()],
        reconciliation_reports=reports,
    )

    event = result["objects"][0]["expected_event_assessments"][0]
    assert event["mechanical_coverage_status"] == "partial"
    assert event["coverage_status"] == "covered"
    assert event["reconciliation_attempt_count"] == 2
    assert event["reconciliation_previous_decisions"] == ["reextract_cached_source"]
    assert result["verified_expected_event_count"] == 1


def test_gap_router_is_report_only_and_stable() -> None:
    result = tool.build_report(
        claim_rows=[claim()],
        downstream_rows=[],
        target_rows=[target()],
        schema_name="retrieval_v3",
        item_code="I5B",
        rule_code="appointment_delegation",
        emperors=["测试帝"],
    )

    first = tool.build_gap_router(result)
    second = tool.build_gap_router(result)
    assert first == second
    assert first[0]["idempotency_key"].startswith("CGR-")
    assert all(row["write_job"] is False and row["write_db"] is False for row in first)


def test_repair_ledger_detects_unchanged_retry_without_writing_jobs() -> None:
    result = report([claim()], [], [target()])
    first = convergence.build_repair_ledger(result)
    second = convergence.build_repair_ledger(result, first)

    assert second[0]["attempt_count"] == 2
    assert second[0]["previous_decision"] == second[0]["current_decision"]
    assert second[0]["progress_observed"] is False
    assert second[0]["convergence_state"] == "no_progress"
    assert second[0]["write_job"] is False


def test_convergence_separates_mechanical_complete_from_unassessed_history() -> None:
    result = report([claim()], [downstream()], [target()])
    ledger = convergence.build_repair_ledger(result)
    convergence.apply_convergence(result, ledger)

    object_row = result["objects"][0]
    assert object_row["mechanical_coverage_status"] == "complete"
    assert object_row["convergence_state"] == "unassessed"
    assert result["mechanical_coverage_counts"] == {"complete": 1}
    assert result["convergence_counts"] == {"unassessed": 1}


def test_verified_expected_events_reach_verified_convergence() -> None:
    reports = [{
        "gate_mode": "repair_verification",
        "results": [{"event_inventory_code": "EEI-EAST-TURK", "decision": "already_covered"}],
    }]
    result = tool.build_report(
        claim_rows=[claim()], downstream_rows=[downstream()], target_rows=[target()],
        schema_name="retrieval_v3", item_code="I5B", rule_code="appointment_delegation",
        emperors=["测试帝"], expected_events=[expected_event()], reconciliation_reports=reports,
    )
    ledger = convergence.build_repair_ledger(result)
    convergence.apply_convergence(result, ledger)

    assert result["objects"][0]["convergence_state"] == "verified"


def test_identity_review_is_terminal_in_repair_ledger() -> None:
    result = report([claim(object_id=8)], [], [target(object_id=7)])
    ledger = convergence.build_repair_ledger(result)

    identity_routes = [row for row in ledger if row["next_action"] == "identity_review"]
    assert identity_routes
    assert all(row["terminal"] is True and row["retryable"] is False for row in identity_routes)
    assert all(row["convergence_state"] == "terminal_review" for row in identity_routes)
    convergence.apply_convergence(result, ledger)
    assert all(row["convergence_state"] == "terminal_review" for row in result["objects"])


def test_consumer_handoff_holds_stalled_and_terminal_routes() -> None:
    result = report([claim(object_id=8)], [], [target(object_id=7)])
    first = convergence.build_repair_ledger(result)
    second = convergence.build_repair_ledger(result, first)
    handoff = convergence.build_consumer_handoffs(second)

    assert handoff["write_job"] is False
    assert handoff["write_db"] is False
    assert handoff["counts"]["terminal_manual_review"] >= 1
    assert handoff["counts"]["held_no_progress"] >= 1
    assert not any(row["dispatch_allowed"] for row in handoff["handoffs"])


def test_event_group_rebuild_is_ready_only_for_report_handoff() -> None:
    reports = [{
        "gate_mode": "repair_verification",
        "results": [{"event_inventory_code": "EEI-EAST-TURK", "decision": "rebuild_event_group"}],
    }]
    result = tool.build_report(
        claim_rows=[claim()], downstream_rows=[downstream()], target_rows=[target()],
        schema_name="retrieval_v3", item_code="I5B", rule_code="appointment_delegation",
        emperors=["测试帝"], expected_events=[expected_event()], reconciliation_reports=reports,
    )
    handoff = convergence.build_consumer_handoffs(convergence.build_repair_ledger(result))
    rebuild = [row for row in handoff["handoffs"] if row["consumer_stage"] == "event_group_rebuild"]

    assert rebuild and rebuild[0]["dispatch_state"] == "ready_report_only"
    assert rebuild[0]["dispatch_allowed"] is True
    assert rebuild[0]["write_job"] is False and rebuild[0]["write_db"] is False


def test_convergence_delta_reports_new_resolved_stalled_and_regressed() -> None:
    previous = [
        {"idempotency_key": "A", "current_decision": "old", "next_action": "claim_extraction", "terminal": False},
        {"idempotency_key": "B", "current_decision": "open", "next_action": "binding", "terminal": False},
        {"idempotency_key": "C", "current_decision": "done", "next_action": "factorization", "terminal": False},
    ]
    current = [
        {"idempotency_key": "A", "current_decision": "old", "next_action": "claim_extraction", "convergence_state": "no_progress", "terminal": False},
        {"idempotency_key": "B", "current_decision": "review", "next_action": "identity_review", "terminal": True},
        {"idempotency_key": "D", "current_decision": "new", "next_action": "source_refinement", "terminal": False},
    ]
    delta = convergence.build_convergence_delta(current, previous)

    assert delta["counts"] == {
        "new_gap": 1,
        "regressed_to_terminal": 1,
        "resolved_gap": 1,
        "stalled": 1,
    }
    assert delta["write_job"] is False and delta["write_db"] is False
