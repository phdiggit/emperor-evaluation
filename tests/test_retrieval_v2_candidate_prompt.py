from __future__ import annotations

from scripts.dev import retrieval_v2_candidate_prompt as tool


def sample_candidates() -> dict:
    return {
        "task_identity": {"rule_code": "delegation", "emperor_name": "李渊"},
        "target_profile": {"primary_name": "李渊", "aliases": ["李渊", "高祖"]},
        "rule": {"rule_code": "delegation", "keywords": ["命"]},
        "coverage_matrix": {"rule_code": "delegation", "role_families": []},
        "secondary_rule_candidates": [{"rule_code": "team_building", "reason": "reuse"}],
        "object_seeds": [
            {
                "name": "李世民",
                "aliases": [{"alias": "秦王", "strength": "medium"}],
                "role_families": ["military_delegate"],
                "predicate_candidates": ["delegated_authority"],
                "source_document_codes": ["DOC-001"],
            }
        ],
        "source_documents": [
            {
                "document_code": "DOC-001",
                "title": "旧唐书/fixture",
                "source_kind": "primary_source",
                "text_chars": 100,
                "cache_status": "hit",
                "why_selected": "verbose discovery note should be trimmed from prompt payload",
            }
        ],
        "candidate_slices": [
            {
                "slice_code": "SLI-001",
                "document_code": "DOC-001",
                "object_name": "李世民",
                "locator": "chars:0-20",
                "matched_aliases": ["秦王"],
                "matched_rule_terms": ["命"],
                "matched_outcome_terms": [],
                "matched_role_families": ["military_delegate"],
                "score": 99,
                "weak_alias_only": False,
                "merged_from_slice_codes": ["SLI-RAW"],
                "text": "高祖命秦王为西讨元帅。",
            }
        ],
    }


def test_prompt_payload_preserves_candidate_context() -> None:
    payload = tool.prompt_payload(sample_candidates())

    assert payload["object_seeds"][0]["aliases"][0]["alias"] == "秦王"
    assert payload["source_documents"][0]["why_selected"]
    assert payload["candidate_slices"][0]["score"] == 99
    assert "secondary_candidate_routing_policy" not in payload


def test_prompt_payload_strips_candidate_debug_profile() -> None:
    candidates = sample_candidates()
    candidates["candidate_slices"][0]["slice_profile"] = {"has_full_delegation_chain": True}

    payload = tool.prompt_payload(candidates)

    assert "slice_profile" not in payload["candidate_slices"][0]
    assert payload["candidate_slices"][0]["text"] == "高祖命秦王为西讨元帅。"


def test_build_prompt_keeps_budget_contract() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "candidate_slices" in prompt
    assert "判读预算" in prompt
    assert "每个对象默认最多 2 个" in prompt
    assert "多个完整 delegation scoring 链" in prompt
    assert "不要让弱 review、future hint 或单纯履历材料占掉这些名额" in prompt
    assert "每条 claim 默认最多 3 个 secondary_binding_candidates" in prompt
    assert "低价值 review 不要为了填满规则而输出" in prompt
    assert "不要在 reason 里重复长篇解释" in prompt
    assert '"slice_code": "SLI-001"' in prompt
    assert "claim_summary 必须能被所列 source_slice_refs 的原文直接支撑" in prompt
    assert "不要把 A 片段的摘录挂到 B 事件 summary" in prompt
    assert "任何带 usable_for_scoring_cluster=true binding 的 claim 都不得使用 direction=mixed" in prompt
    assert "不要把不同事件链的正负材料合成 direction=mixed" in prompt
    assert "不要把“本片段不支撑某对象/某 rule”写成 context_claim" in prompt
    assert "授权任务 + 对应战果/反馈" in prompt
    assert "不要只概括为任职、督军或中枢职责履历" in prompt


def test_build_prompt_requires_concrete_harm_for_negative_disposition() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "处置结果，不能单独构成 negative claim" in prompt
    assert "同一候选材料同时证明被授权者在任内造成具体治理损害" in prompt
    assert "交消费侧结合人物画像判断" in prompt
    assert "如果本 shard 只是未见负向授权损害" in prompt
    assert "不要写 negative_undercoverage" in prompt
    assert "出现明确的治理损害、军政失败、人才结构损害或授权链条失控线索" in prompt


def test_build_prompt_requires_cross_rule_candidate_routing_policy() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "必须顺手为同一 claim 标出可复用的 secondary_binding_candidates" in prompt
    assert "I5B 当前正式候选限 delegation、appointment_trust、team_building、talent_discovery、tolerate_talent、anti_nepotism" in prompt
    assert "hint_status=future_rule_hint" in prompt
    assert "secondary candidate 只是后续复核线索" in prompt
    assert "tolerate_talent 正向必须直接体现容谏、保全能臣、维护表达安全、修复授权信用" in prompt
    assert "单纯任用、信任、团队成员、采纳一般计策，不能自动转成 tolerate_talent positive" in prompt
    assert "current_rule_candidate、future_rule_hint、rejected_or_context_only" in prompt
    assert "future_rule_hint 和 rejected_or_context_only 不得进入 factorization" in prompt
    assert '"candidate_payload": {' in prompt


def test_build_prompt_requires_delegation_scoring_candidate_contract() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "delegation scoring candidate 硬协议" in prompt
    assert "has_authorization_or_office" in prompt
    assert "has_named_delegate" in prompt
    assert "has_task_or_responsibility" in prompt
    assert "has_same_chain_outcome" in prompt
    assert "candidate_payload.candidate_role 必须使用消费侧 object_role" in prompt
    assert "delegation_domain" in prompt
    assert "same_chain_outcome_summary" in prompt
    assert "三杰总评" in prompt
    assert "delegation 召回优先级" in prompt
    assert "给兵、给金、遣使、命将、授权任务并有战果/治理结果" in prompt
    assert "先丢弃较弱的封王/任官 review claim" in prompt
    assert "说降或归附后分兵、给兵、与俱收兵、会战、破敌、定地" in prompt
    assert "后续反叛、被诛、被废等负向处置不得挤掉同对象更早的正向授权收益链" in prompt
    assert "不要只把 B/C 藏在 A 的 claim_summary 里" in prompt
    assert "object_name 填未拆出的具名对象" in prompt
    assert "补对象/补源后重判" in prompt
    assert '"rule_code": "delegation | appointment_trust' in prompt


def test_build_prompt_requests_item_wide_fact_structure() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "personnel_political_wide / I5B-wide 事实骨架" in prompt
    assert "fact_payload 使用 political_action_v1 字段" in prompt
    assert "fact_schema、actor、object、action_type、event_scope、office_or_domain" in prompt
    assert "source_span_refs、confidence、completeness" in prompt
    assert "evidence_spans 使用短原文 span" in prompt
    assert "span_type 只能是 action / object / outcome / reason / institution / context" in prompt
    assert "evidence_spans.text 必须是对应 source_slice_ref 原文中的连续短句或短语" in prompt
    assert "不要用省略号、括号补充、白话改写或跨句拼接" in prompt
    assert "claim_completeness 使用 has_action_span" in prompt
    assert '"fact_schema": "political_action_v1"' in prompt
    assert '"source_span_refs": [' in prompt
    assert '"fact_payload": {' in prompt
    assert '"evidence_spans": [' in prompt
    assert '"claim_completeness": {' in prompt


def test_build_prompt_marks_i5b_wide_shadow_pilot_not_formal_consumption() -> None:
    candidates = sample_candidates()
    candidates["task_identity"]["capture_mode"] = "i5b_wide_shadow"

    prompt = tool.build_prompt(candidates)

    assert "I5B-wide shadow pilot" in prompt
    assert "不要作为正式消费源" in prompt
    assert "claim 原子化、secondary candidates 质量、token/耗时和重复减少效果" in prompt
    assert "任命、荐举、信任、授权、团队、容才、疑忌、亲私、结党、撤权、处置、权臣/军头失控" in prompt
    assert "便于消费端窄入分" in prompt


def test_build_prompt_item_wide_shadow_uses_rule_candidates_not_primary_bindings() -> None:
    candidates = sample_candidates()
    candidates["task_identity"]["capture_mode"] = "i5b_item_wide_shadow"

    prompt = tool.build_prompt(candidates)

    assert "I5B item-wide shadow pilot" in prompt
    assert "不是改造某个 delegation 包" in prompt
    assert "覆盖整个 I5B 任人用人主题的宽材料池" in prompt
    assert "primary_bindings 必须为空数组" in prompt
    assert '"primary_bindings": []' in prompt
    assert "所有正式 rule 归属都写入 secondary_binding_candidates" in prompt


def test_build_prompt_personnel_political_wide_uses_route_table_and_fact_schema() -> None:
    candidates = sample_candidates()
    candidates["task_identity"]["capture_mode"] = "personnel_political_wide_shadow"
    candidates["task_identity"]["capture_profile"] = "personnel_political_wide"
    candidates["task_identity"]["fact_schema"] = "political_action_v1"
    candidates["task_identity"]["candidate_route_table_version"] = "personnel_political_v0_1"

    prompt = tool.build_prompt(candidates)

    assert "personnel_political_wide shadow pilot" in prompt
    assert "fact_schema=political_action_v1" in prompt
    assert "personnel_political_v0_1" in prompt
    assert "candidate_item_code" in prompt
    assert "candidate_lane" in prompt
    assert "required_facts_present" in prompt
    assert "current_rule_candidate" in prompt
    assert "future_rule_hint" in prompt
    assert "rejected_or_context_only" in prompt
    assert "I5C power_control" in prompt
    assert "I5D political_character" in prompt
    assert "I5E cognition_learning" in prompt
    assert "I6 key_decision" in prompt
    assert "I3 military_frontier_result" in prompt
    assert "I7 historical_debt" in prompt
    assert '"primary_bindings": []' in prompt
