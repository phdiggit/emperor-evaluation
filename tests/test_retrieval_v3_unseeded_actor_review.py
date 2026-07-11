from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_unseeded_actor_review_consumer as consumer
from scripts.dev import retrieval_v3_unseeded_actor_review_tasks as tasks


def workitem(code: str = "UAC-001", *, stage: str = "appointment_disposition_lead", actor_scope: str = "official_or_other") -> dict:
    return {
        "candidate_code": code,
        "emperor_name": "朱元璋",
        "target_period": "明",
        "target_period_candidates": ["明"],
        "source_hints": ["明史", "明實錄"],
        "observed_name": "测试人物",
        "resolved_object_id": None,
        "resolved_canonical_name": "",
        "discovery_status": "unresolved_name_candidate",
        "actor_scope": actor_scope,
        "reference_aliases": ["鲁王"] if actor_scope == "royal_clan" else [],
        "lead_stages": [stage],
        "evidence_windows": [
            {
                "window_hash": "UAW-001",
                "passage_code": "PAS-001",
                "window": "太祖所任测试人物获罪。",
                "appointment_signals": ["所任"],
                "harm_signals": [],
                "disposition_signals": ["获罪"],
            }
        ],
        "scoring_allowed": False,
    }


def patch(code: str = "UAC-001", *, verdict: str = "source_refine") -> dict:
    return {
        "candidate_code": code,
        "review_verdict": verdict,
        "is_person_name": True,
        "is_same_reign_actor": True,
        "has_appointment_or_authorization_signal": True,
        "has_harm_or_failure_signal": False,
        "has_disposition_only": True,
        "recommended_action": consumer.VERDICT_ACTIONS[verdict],
        "evidence_window_hashes": ["UAW-001"],
        "review_note": "原文只证明本朝任用与获罪，值得补抓本传但不能直接计负分。",
    }


def test_task_generator_writes_finite_file_only_contract(tmp_path: Path) -> None:
    summary = tasks.write_outputs([workitem()], tmp_path, batch_size=8)
    task = json.loads((tmp_path / "codex_tasks.jsonl").read_text(encoding="utf-8"))
    prompt = Path(task["prompt_path"]).read_text(encoding="utf-8")

    assert summary["task_count"] == 1
    assert task["expected_outputs"][0]["kind"] == "jsonl_patch"
    assert task["expected_outputs"][0]["fallback"] == "last_message_marked_block"
    assert "source_refine、reject_name、needs_context" in prompt
    assert "不能因为人物后来获罪就推断皇帝错任" in prompt
    assert "禁止联网" in prompt


def test_consumer_accepts_source_refine_and_emits_non_scoring_seed() -> None:
    reviewed = consumer.validate_review_package([workitem()], [patch()])
    seeds = consumer.source_refiner_rows(reviewed)

    assert len(seeds) == 1
    assert seeds[0]["name"] == "测试人物"
    assert seeds[0]["target_emperors"] == ["朱元璋"]
    assert seeds[0]["period"] == "明"
    assert seeds[0]["source_hints"] == ["明史", "明實錄"]
    assert seeds[0]["priority"] == 20
    assert seeds[0]["write_db"] is False
    assert seeds[0]["scoring_allowed"] is False
    assert seeds[0]["required_chain"]["disposition_alone_is_not_scoring"] is True


def test_consumer_rejects_disposition_only_claimed_as_harm() -> None:
    row = patch()
    row["has_harm_or_failure_signal"] = True

    with pytest.raises(consumer.ActorReviewConsumerError, match="disposition-only"):
        consumer.validate_patch(row)


def test_consumer_requires_complete_exact_patch_set() -> None:
    with pytest.raises(consumer.ActorReviewConsumerError, match="missing review patches"):
        consumer.validate_review_package([workitem()], [])
    with pytest.raises(consumer.ActorReviewConsumerError, match="unknown review patches"):
        consumer.validate_review_package([workitem()], [patch(), patch("UAC-OTHER")])


def test_consumer_rejects_unknown_evidence_hash() -> None:
    row = patch()
    row["evidence_window_hashes"] = ["UAW-UNKNOWN"]

    with pytest.raises(consumer.ActorReviewConsumerError, match="not in workitem"):
        consumer.validate_review_package([workitem()], [row])


def test_consumer_fails_closed_when_source_context_is_missing() -> None:
    item = workitem()
    item["target_period"] = ""
    item["source_hints"] = []
    reviewed = consumer.validate_review_package([item], [patch()])

    with pytest.raises(consumer.ActorReviewConsumerError, match="deterministic target_period"):
        consumer.source_refiner_rows(reviewed)


def test_consumer_routes_royal_clan_to_shared_source_chain_and_jifeilu() -> None:
    item = workitem(actor_scope="royal_clan")
    item["observed_name"] = "朱檀"
    reviewed = consumer.validate_review_package([item], [patch()])

    seed = consumer.source_refiner_rows(reviewed)[0]

    assert seed["actor_scope"] == "royal_clan"
    assert seed["object_search_scopes"] == ["person", "royal_clan"]
    assert seed["aliases"] == ["鲁王"]
    assert seed["required_chain"]["royal_clan_power_or_fief"] is True
    assert seed["source_document_hints"] == [
        {
            "title": "御制纪非录",
            "source_title": "御制纪非录",
            "locator": "御制纪非录正文 宗室条 朱檀 鲁王",
            "url": consumer.JIFEILU_URL,
            "source_kind": "public_ocr_page",
            "fetch_mode": "url",
            "ocr_text_policy": "site_result_accepted",
            "ocr_aliases": ["魚王", "鱼王"],
            "section_start_aliases": ["魚王", "鱼王"],
        }
    ]
    assert seed["source_target_refs"] == ["明史 宗室 藩王 朱檀", "明實錄 宗室 藩王 朱檀"]
