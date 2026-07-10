from __future__ import annotations

from scripts.dev import retrieval_v2_claim_candidate_triage as tool


def sample_candidates() -> dict:
    return {
        "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {"slice_code": "SLI-001", "object_name": "胡惟庸", "document_code": "DOC-001", "text": "胡惟庸伏诛，夷三族。", "matched_outcome_terms": ["伏诛"]},
            {"slice_code": "SLI-002", "object_name": "胡惟庸", "document_code": "DOC-001", "text": "胡惟庸伏诛，夷三族。", "matched_outcome_terms": ["伏诛"]},
            {"slice_code": "SLI-003", "object_name": "胡惟庸", "document_code": "DOC-002", "text": "云奇告变，胡惟庸谋反。"},
            {"slice_code": "SLI-004", "object_name": "蓝玉", "document_code": "DOC-003", "text": "蓝玉以谋反伏诛。"},
        ],
    }


def test_build_prompt_limits_deepseek_to_duplicate_suggestion_contract() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "不是事实裁判" in prompt
    assert "不判断 claim、人物归属、正负向、证据强度或切片优先级" in prompt
    assert "不同 source document、不同事件、不同时间、不同 outcome" in prompt
    assert '"slice_code":"SLI-001"' in prompt


def test_triage_defers_verified_near_duplicate_and_keeps_audit(monkeypatch) -> None:
    monkeypatch.setattr(
        tool.llm_providers,
        "run_deepseek_chat",
        lambda **_kwargs: {
            "payload": {
                "decisions": [
                    {"slice_code": "SLI-001", "duplicate_of": "", "reason": "代表切片"},
                    {"slice_code": "SLI-002", "duplicate_of": "SLI-001", "reason": "同文重复"},
                    {"slice_code": "SLI-003", "duplicate_of": "", "reason": "不同文献"},
                    {"slice_code": "SLI-004", "duplicate_of": "", "reason": "不同对象"},
                ]
            },
            "usage": {"input_tokens": 200, "output_tokens": 80},
            "elapsed_seconds": 0.3,
        },
    )

    selected, report = tool.triage_candidates(
        sample_candidates(),
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=None,
        timeout_seconds=30,
        thinking="disabled",
        max_tokens=1024,
        duplicate_text_similarity=0.72,
    )

    assert [row["slice_code"] for row in selected["candidate_slices"]] == ["SLI-001", "SLI-003", "SLI-004"]
    assert report["status"] == "succeeded"
    assert report["deferred_slice_count"] == 1
    assert report["deferred_slices"][0]["slice_code"] == "SLI-002"
    assert report["deferred_slices"][0]["defer_reason"] == "verified_near_duplicate"
    assert report["usage"]["input_tokens"] == 200


def test_invalid_deepseek_response_falls_back_without_dropping_slices(monkeypatch) -> None:
    monkeypatch.setattr(
        tool.llm_providers,
        "run_deepseek_chat",
        lambda **_kwargs: {"payload": {"decisions": [{"slice_code": "SLI-001", "duplicate_of": ""}]}, "usage": {}},
    )

    selected, report = tool.triage_candidates(
        sample_candidates(),
        provider="deepseek",
        model=None,
        api_key_env="DEEPSEEK_API_KEY",
        base_url=None,
        timeout_seconds=30,
        thinking="disabled",
        max_tokens=None,
        duplicate_text_similarity=0.72,
    )

    assert [row["slice_code"] for row in selected["candidate_slices"]] == ["SLI-001", "SLI-002", "SLI-003", "SLI-004"]
    assert report["status"] == "invalid_response_fallback"
    assert "missing_decision:SLI-002" in report["validation_errors"]


def test_triage_never_defers_distinct_event_in_same_document() -> None:
    decisions = {
        "SLI-001": {"duplicate_of": "", "reason": "代表"},
        "SLI-002": {"duplicate_of": "SLI-001", "reason": "错误建议"},
        "SLI-003": {"duplicate_of": "", "reason": "不同文献"},
        "SLI-004": {"duplicate_of": "", "reason": "不同对象"},
    }

    candidates = sample_candidates()
    candidates["candidate_slices"][1]["text"] = "云奇告变，胡惟庸谋反。"
    candidates["candidate_slices"][1]["matched_outcome_terms"] = ["告变"]
    selected, report = tool.select_prompt_candidates(candidates, decisions, duplicate_text_similarity=0.72)

    assert [row["slice_code"] for row in selected["candidate_slices"]] == ["SLI-001", "SLI-002", "SLI-003", "SLI-004"]
    assert report["deferred_slice_count"] == 0


def test_triage_rejects_invalid_duplicate_similarity() -> None:
    try:
        tool.triage_candidates(
            sample_candidates(),
            provider="none",
            model=None,
            api_key_env="DEEPSEEK_API_KEY",
            base_url=None,
            timeout_seconds=30,
            thinking="disabled",
            max_tokens=None,
            duplicate_text_similarity=0,
        )
    except tool.ClaimCandidateTriageError as exc:
        assert "in (0, 1]" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid prompt budget to fail")
