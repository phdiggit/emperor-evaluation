from __future__ import annotations

from scripts.dev import retrieval_v2_claim_candidate_triage as tool


def sample_candidates() -> dict:
    return {
        "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {"slice_code": "SLI-001", "object_name": "胡惟庸", "document_code": "DOC-001", "text": "胡惟庸伏诛，夷三族。"},
            {"slice_code": "SLI-002", "object_name": "胡惟庸", "document_code": "DOC-001", "text": "胡惟庸案的重复叙述。"},
            {"slice_code": "SLI-003", "object_name": "胡惟庸", "document_code": "DOC-002", "text": "云奇告变，胡惟庸谋反。"},
            {"slice_code": "SLI-004", "object_name": "蓝玉", "document_code": "DOC-003", "text": "蓝玉以谋反伏诛。"},
        ],
    }


def test_build_prompt_limits_deepseek_to_ranking_contract() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "不是事实裁判" in prompt
    assert "不判断 claim 是否成立、人物归属、正负向或证据强度" in prompt
    assert '"slice_code":"SLI-001"' in prompt


def test_triage_selects_prompt_budget_and_keeps_deferred_auditable(monkeypatch) -> None:
    monkeypatch.setattr(
        tool.llm_providers,
        "run_deepseek_chat",
        lambda **_kwargs: {
            "payload": {
                "decisions": [
                    {"slice_code": "SLI-001", "priority": "high", "duplicate_of": "", "reason": "直接事件"},
                    {"slice_code": "SLI-002", "priority": "low", "duplicate_of": "SLI-001", "reason": "重复"},
                    {"slice_code": "SLI-003", "priority": "medium", "duplicate_of": "", "reason": "补充"},
                    {"slice_code": "SLI-004", "priority": "high", "duplicate_of": "", "reason": "直接事件"},
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
        max_slices_per_object=2,
    )

    assert [row["slice_code"] for row in selected["candidate_slices"]] == ["SLI-001", "SLI-003", "SLI-004"]
    assert report["status"] == "succeeded"
    assert report["deferred_slice_count"] == 1
    assert report["deferred_slices"][0]["slice_code"] == "SLI-002"
    assert report["deferred_slices"][0]["defer_reason"] == "prompt_budget"
    assert report["usage"]["input_tokens"] == 200


def test_invalid_deepseek_response_falls_back_without_dropping_slices(monkeypatch) -> None:
    monkeypatch.setattr(
        tool.llm_providers,
        "run_deepseek_chat",
        lambda **_kwargs: {"payload": {"decisions": [{"slice_code": "SLI-001", "priority": "high"}]}, "usage": {}},
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
        max_slices_per_object=2,
    )

    assert [row["slice_code"] for row in selected["candidate_slices"]] == ["SLI-001", "SLI-002", "SLI-003", "SLI-004"]
    assert report["status"] == "invalid_response_fallback"
    assert "missing_decision:SLI-002" in report["validation_errors"]


def test_prompt_budget_never_defers_high_priority_slice() -> None:
    decisions = {
        "SLI-001": {"priority": "high", "duplicate_of": "", "reason": "事件一"},
        "SLI-002": {"priority": "high", "duplicate_of": "", "reason": "事件二"},
        "SLI-003": {"priority": "high", "duplicate_of": "", "reason": "事件三"},
        "SLI-004": {"priority": "low", "duplicate_of": "", "reason": "普通材料"},
    }

    candidates = sample_candidates()
    candidates["candidate_slices"][3]["object_name"] = "胡惟庸"
    selected, report = tool.select_prompt_candidates(candidates, decisions, max_slices_per_object=2)

    assert [row["slice_code"] for row in selected["candidate_slices"]] == ["SLI-001", "SLI-002", "SLI-003"]
    assert report["deferred_slices"][0]["slice_code"] == "SLI-004"


def test_triage_rejects_non_positive_prompt_budget() -> None:
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
            max_slices_per_object=0,
        )
    except tool.ClaimCandidateTriageError as exc:
        assert "at least 1" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid prompt budget to fail")
