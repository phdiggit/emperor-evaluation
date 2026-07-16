from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest
import yaml

from emperor_v4.evaluation.i5b_candidate_retrieval_gate import (
    build_cross_rule_orphan_audit,
    validate_candidate_retrieval_gate,
)
from emperor_v4.evaluation.i5b_scholar_guided_retrieval import (
    apply_scholar_guided_judge_decisions,
    build_scholar_guided_judge_intake,
    build_scholar_guided_retrieval_report,
)
from emperor_v4.evaluation.i5b_scholar_source_cache import (
    run_scholar_source_cache_shadow,
)
from emperor_v4.adapters.wikisource import WikisourcePageSnapshot
from emperor_v4.runtime.source_cache import source_cache_request_from_mapping


ROOT = Path(__file__).resolve().parents[1]
MECHANISM = ROOT / "config/i5b-scholar-guided-retrieval.yml"
TASK = ROOT / (
    "eval/i5b_source_ingestion/"
    "team_building_lishimin_scholar_guided_retrieval_v1.yml"
)
def test_lishimin_scholar_guided_cases_cover_all_rules_and_go_to_source_cache() -> None:
    report = build_scholar_guided_retrieval_report(
        mechanism_contract_path=MECHANISM, task_contract_path=TASK
    )
    assert report["report_sha256"] == build_scholar_guided_retrieval_report(
        mechanism_contract_path=MECHANISM, task_contract_path=TASK
    )["report_sha256"]
    assert report["summary"]["case_count"] == 10
    assert report["summary"]["mandatory_trigger_count"] == 9
    assert all(report["summary"]["rule_task_counts"].values())
    assert all(
        row["next_gate"] == "versioned_source_cache_then_candidate_judge"
        and row["disposition"] == "candidate_only"
        and set(row["search_directions"]) == {"positive", "negative"}
        and row["primary_source_locators"]
        and row["source_cache_request"]["mode"] == "ensure"
        and row["source_cache_request"]["idempotency_key"].startswith(
            "source-cache:v4:scholar-guided:"
        )
        for row in report["source_cache_tasks"]
    )
    assert all(
        source_cache_request_from_mapping(row["source_cache_request"]).request_id
        for row in report["source_cache_tasks"]
    )
    assert {
        hint
        for row in report["source_cache_tasks"]
        for hint in row["source_cache_request"]["source_hints"]
    } == {
        "貞觀政要/卷02",
        "貞觀政要/卷03",
        "貞觀政要/卷07",
        "舊唐書/卷21",
    }
    intake = build_scholar_guided_judge_intake(report)
    assert intake["summary"]["item_count"] > report["summary"]["case_count"]
    assert all(
        row["status"] == "awaiting_versioned_source_cache"
        and row["judge_may_accept_scholarship_as_fact"] is False
        for row in intake["items"]
    )
    assert report["declarations"]["scholarship_is_formal_fact"] is False
    assert report["declarations"]["formal_score"] is None

def test_rule_mechanisms_are_not_remonstrance_predicates_for_every_rule() -> None:
    mechanism = yaml.safe_load(MECHANISM.read_text(encoding="utf-8"))
    profiles = mechanism["rule_mechanisms"]
    assert "expression_or_professional_independence" in profiles["tolerate_talent"][
        "mechanism_predicates"
    ]
    assert "expression_or_professional_independence" not in profiles[
        "appointment_delegation"
    ]["mechanism_predicates"]
    assert profiles["appointment_delegation"]["mechanism_predicates"] == [
        "ruler_commission",
        "authority_boundary",
        "actual_operation",
        "attributable_result",
    ]


def test_scholar_source_cache_shadow_is_bounded_and_exactly_reused(
    tmp_path: Path,
) -> None:
    report = build_scholar_guided_retrieval_report(
        mechanism_contract_path=MECHANISM, task_contract_path=TASK
    )
    page_passages: dict[str, list[dict]] = {}
    for task in report["source_cache_tasks"]:
        for locator in task["primary_source_locators"]:
            passages = locator.get("source_cache_passages") or []
            if not passages:
                continue
            title = unquote(
                urlparse(locator["canonical_url"]).path.removeprefix("/wiki/")
            )
            page_passages.setdefault(title, []).extend(passages)

    fetch_count = 0

    def fake_fetch(*, page_code, page_title, expected_revision_id=None):
        nonlocal fetch_count
        fetch_count += 1
        raw_text = "\n".join(
            passage["anchor_start"] + "正文" + passage["anchor_end"]
            for passage in page_passages[page_title]
        )
        return WikisourcePageSnapshot(
            page_code=page_code,
            requested_title=page_title,
            canonical_title=page_title,
            canonical_url=f"https://zh.wikisource.org/wiki/{page_title}",
            revision_id=7,
            revision_timestamp="2026-07-16T00:00:00Z",
            retrieved_at="2026-07-16T00:00:01Z",
            raw_text=raw_text,
            content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    first = run_scholar_source_cache_shadow(
        report=report,
        output_dir=tmp_path,
        service_release_sha="0" * 40,
        fetch=fake_fetch,
    )
    assert first["runtime_audit"]["planned_task_count"] == 10
    assert first["runtime_audit"]["unique_page_count"] == 4
    assert first["runtime_audit"]["network_request_count"] == 4
    assert first["runtime_audit"]["database_write_count"] == 0
    assert first["runtime_audit"]["model_call_count"] == 0
    assert len(first["response"]["passages"]) == 11
    assert first["response"]["unresolved_tasks"] == []
    intake = build_scholar_guided_judge_intake(
        report, source_cache_response=first["response"]
    )
    assert intake["summary"]["ready_for_candidate_judge_count"] == 13
    assert intake["summary"]["awaiting_source_cache_count"] == 0

    second = run_scholar_source_cache_shadow(
        report=report,
        output_dir=tmp_path,
        service_release_sha="0" * 40,
        fetch=fake_fetch,
    )
    assert fetch_count == 4
    assert second["current_run_audit"] == {
        "exact_response_reused": True,
        "network_request_count": 0,
        "shadow_state_write_count": 0,
        "database_write_count": 0,
        "model_call_count": 0,
    }


def test_scholar_judge_decisions_are_version_bound_and_complete() -> None:
    report = build_scholar_guided_retrieval_report(
        mechanism_contract_path=MECHANISM, task_contract_path=TASK
    )
    passages = [
        {
            "passage_id": f"SP-{task['case_ref']}",
            "source_cache_task_code": task["task_code"],
            "selection_reason": task["required_source_cache_selection_keys"],
        }
        for task in report["source_cache_tasks"]
        if task["case_ref"] != "SGR-LSM-ZHENGUAN-RITES"
    ]
    intake = build_scholar_guided_judge_intake(
        report, source_cache_response={"passages": passages}
    )
    ready = [row for row in intake["items"] if row["status"].startswith("ready_")]
    decisions = {
        "schema_version": "i5b-scholar-guided-judge-decisions-v1",
        "intake_report_sha256": intake["report_sha256"],
        "reviewer": "test",
        "reviewed_at": "2026-07-16T00:00:00+08:00",
        "decisions": [
            {
                "intake_ref": row["intake_ref"],
                "disposition": "accepted_new_candidate",
                "effect_direction": "positive",
                "settlement_eligible": True,
                "duplicate_of": None,
                "rationale": "测试完整裁决",
            }
            for row in ready
        ],
    }
    judged = apply_scholar_guided_judge_decisions(intake, decisions)
    assert judged["summary"]["judged_candidate_count"] == 12
    assert judged["summary"]["awaiting_source_cache_count"] == 1
    assert judged["summary"]["settlement_eligible_candidate_count"] == 12

    decisions["intake_report_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="版本不一致"):
        apply_scholar_guided_judge_decisions(intake, decisions)


def _gate() -> dict:
    orphan = build_cross_rule_orphan_audit(
        target_rule_code="team_building",
        routed_passages=[],
        candidate_passage_refs=[],
    )
    lane = {
        "status": "complete",
        "query_version": "v1",
        "candidate_count": 1,
        "judged_candidate_count": 1,
        "unresolved_candidate_count": 0,
    }
    return {
        "schema_version": "i5b-candidate-retrieval-gate-v4",
        "rule_code": "team_building",
        "input_versions": {
            "source_catalog_version": "v1",
            "source_cache_fingerprint": "cache-v1",
            "rule_semantics_version": "rule-v1",
            "retrieval_contract_version": "retrieval-v1",
            "scholarly_profile_version": "profiles-v1",
        },
        "trigger_reasons": ["initial_rule_requirement", "pre_closeout_audit"],
        "retrieval_lanes": {
            "person_event": deepcopy(lane),
            "institution_policy": {
                **deepcopy(lane),
                "positive_query_count": 1,
                "negative_query_count": 1,
            },
            "negative_counterexample": deepcopy(lane),
            "cross_rule_orphan_audit": deepcopy(lane),
        },
        "scholar_guided_retrieval": {
            "status": "complete",
            "report_sha256": "b" * 64,
            "task_count": 2,
            "source_cache_routed_task_count": 2,
            "judge_bound_task_count": 2,
        },
        "delegated_harm_audit": {
            "status": "complete",
            "report_sha256": "c" * 64,
            "reviewed_incident_count": 1,
            "unresolved_incident_count": 0,
            "cross_rule_duplicate_count": 0,
        },
        "disposition_audit": {
            "status": "complete",
            "candidate_count": 4,
            "judged_candidate_count": 4,
            "unresolved_candidate_count": 0,
        },
        "source_scope": {
            "chapter_inventory_frozen": True,
            "relevant_chapter_count": 1,
            "dispositioned_chapter_count": 1,
        },
        "cross_rule_orphan_audit": orphan,
        "execution_audit": {
            "network_request_count": 0,
            "model_call_count": 0,
            "business_write_count": 0,
        },
        "human_freeze_accepted": True,
        "human_freeze_decision_ref": "HFD-TEST",
    }


def test_candidate_freeze_requires_scholar_tasks_bound_to_source_cache_and_judge() -> None:
    validated = validate_candidate_retrieval_gate(_gate(), rule_code="team_building")
    assert validated["scholar_guided_retrieval_status"] == "complete"

    broken = _gate()
    broken["scholar_guided_retrieval"]["judge_bound_task_count"] = 1
    with pytest.raises(ValueError, match="Source Cache 与 Judge"):
        validate_candidate_retrieval_gate(broken, rule_code="team_building")
