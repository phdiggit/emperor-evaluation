from __future__ import annotations

from scripts.dev import retrieval_v2_candidate_prompt as tool


def sample_candidates() -> dict:
    return {
        "task_identity": {"rule_code": "appointment_delegation", "emperor_name": "李渊"},
        "target_profile": {"primary_name": "李渊", "aliases": ["李渊", "高祖"]},
        "rule": {"rule_code": "appointment_delegation", "keywords": ["命"]},
        "coverage_matrix": {"rule_code": "appointment_delegation", "role_families": []},
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
                "matched_conditional_recall_terms": ["谋反"],
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
    assert payload["candidate_slices"][0]["matched_aliases"] == ["秦王"]
    assert payload["candidate_slices"][0]["matched_rule_terms"] == ["命"]
    assert "matched_conditional_recall_terms" not in payload["candidate_slices"][0]
    assert "merged_from_slice_codes" not in payload["candidate_slices"][0]
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
    assert "多个完整 appointment_delegation scoring 链" in prompt
    assert "不要让弱 review、future hint 或单纯履历材料占掉这些名额" in prompt
    assert "核心对象超过预算而未拆出的事实必须进入 object_claim_undercoverage coverage_gaps" in prompt
    assert "每条 claim 默认最多 2 个 secondary_binding_candidates" in prompt
    assert "同一 claim 的 future_rule_hint 最多 1 个" in prompt
    assert "优先保留 current_rule_candidate" in prompt
    assert "低价值 review 不要为了填满规则而输出" in prompt
    assert "不要在 reason 里重复长篇解释" in prompt
    assert '"slice_code":"SLI-001"' in prompt
    assert '"slice_code": "SLI-001"' not in prompt
    assert "claim_summary 必须能被所列 source_slice_refs 的原文直接支撑" in prompt
    assert "不要把 A 片段的摘录挂到 B 事件 summary" in prompt
    assert "任何带 usable_for_scoring_cluster=true binding 的 claim 都不得使用 direction=mixed" in prompt
    assert "不要把不同事件链的正负材料合成 direction=mixed" in prompt
    assert "不要把“本片段不支撑某对象/某 rule”写成 context_claim" in prompt
    assert "优先选择完整“授权/职责 + 同链条结果/复用”的代表事实" in prompt
    assert "source candidate 层已负责召回和补源" in prompt
    assert "出征、留守、镇守、督军、提督、平乱、防边" in prompt
    assert "不要只保留最早、最有名或最容易摘要的一条代表性材料" in prompt
    assert "预算或对象缺失导致无法拆出时写 object_claim_undercoverage coverage_gaps" in prompt
    assert "只有确认为谓词词表缺失或别名缺失时" in prompt
    assert "personnel_political_wide 通用对象覆盖门禁" in prompt
    assert "不得只输出一条代表性 claim" in prompt
    assert "gap_type=object_claim_undercoverage" in prompt
    assert "queue=claim_budget_refinement" in prompt
    assert "recommended_action=raise_claim_budget_or_split_object_claims" in prompt
    assert "gap_type=source_missing" in prompt
    assert "queue=source_pack_refinement" in prompt
    assert "do_not_add_recall_terms=true" in prompt
    assert "claim 原子化/对象覆盖问题" in prompt
    assert "同一对象的第 3 条及以后完整强链" in prompt
    assert "应提高 claim 预算/拆分对象 claim" in prompt


def test_build_prompt_can_extract_claims_only() -> None:
    candidates = sample_candidates()
    candidates["task_identity"]["judge_mode"] = tool.CLAIM_EXTRACTION_ONLY_MODE
    candidates["task_identity"]["capture_profile"] = "personnel_political_wide"

    prompt = tool.build_prompt(candidates)

    assert "只抽取可复用政治行动 claim" in prompt
    assert "不要输出 primary_bindings" in prompt
    assert "不要输出 secondary_binding_candidates" in prompt
    assert "不要输出 notes" in prompt
    assert "不要输出 source_passage_refs" in prompt
    assert "不要输出 claim_completeness" in prompt
    assert "direction 不要使用 mixed" in prompt
    assert '"primary_bindings": []' in prompt
    assert '"secondary_binding_candidates": []' in prompt
    assert '"direction": "positive | negative | neutral"' in prompt
    assert '"claim_completeness": {' not in prompt
    assert '"notes":' not in prompt
    assert '"source_passage_refs":' not in prompt
    assert "object_claim_undercoverage" in prompt
    assert "raise_claim_budget_or_split_object_claims" in prompt
    assert "appointment_delegation scoring candidate 硬协议" not in prompt
    assert "不要写 candidate_payload" in prompt
    assert '"candidate_payload": {' not in prompt
    assert "本阶段是 claim cache 构建，不是最终消费包压缩" in prompt
    assert "不要把一个对象压缩成少数代表性 claim" in prompt
    assert "8 个及以上 slices 的重要对象通常抽 5-8 条" in prompt
    assert "不同任命/授权、不同战役、不同边疆或中枢任务" in prompt
    assert "不要只输出“最有名”或最容易摘要的三条" in prompt
    assert "选择能支撑后续规则复核的代表性原子事实" not in prompt


def test_build_prompt_requires_concrete_harm_for_negative_disposition() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "处置结果，不能单独构成 negative claim" in prompt
    assert "同一候选材料同时证明被授权者在任内造成具体治理损害" in prompt
    assert "交消费侧结合人物画像判断" in prompt
    assert "如果本 shard 只是未见负向授权损害" in prompt
    assert "不要写 negative_undercoverage" in prompt
    assert "出现明确的治理损害、军政失败、人才结构损害或授权链条失控线索" in prompt
    assert "只召回本纪处置线、谋反/伏诛/废官/废制度等结局线" in prompt
    assert "不要硬写 appointment_delegation 负向 scoring candidate" in prompt
    assert "需要补本传授权滥用链" in prompt


def test_build_prompt_requires_cross_rule_candidate_routing_policy() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "必须顺手为同一 claim 标出可复用的 secondary_binding_candidates" in prompt
    assert "I5B 固定只有五个正式候选 rule" in prompt
    assert "talent_discovery、appointment_delegation、team_building、tolerate_talent、anti_nepotism" in prompt
    assert "旧 appointment_trust / delegation 兼容口径已放弃" in prompt
    assert '"rule_code": "appointment_trust' not in prompt
    assert '"candidate_lane": "I5B.delegation' not in prompt
    assert "I5C 已有权力控制草案 lane" in prompt
    assert "central_military_power_control" in prompt
    assert "regional_clan_power_control" in prompt
    assert "inner_favorite_power_control" in prompt
    assert "institutional_constraint_correction" in prompt
    assert "hint_status=future_rule_hint" in prompt
    assert "secondary candidate 只是后续复核线索" in prompt
    assert "tolerate_talent 正向必须直接体现容谏、保全能臣、维护表达安全、修复授权信用" in prompt
    assert "单纯任用、信任、团队成员、采纳一般计策，不能自动转成 tolerate_talent positive" in prompt
    assert "team_building 按皇帝对象池整体聚合" in prompt
    assert "对象弱贡献、负贡献或 supporting_only 交给消费端窄验" in prompt
    assert "不要手写 candidate_payload.personnel_profile 或 power_control_profile" in prompt
    assert "runner 会按 claim.fact_payload 本地补齐" in prompt
    assert '"personnel_profile": {' not in prompt
    assert '"power_control_profile": {' not in prompt
    assert "current_rule_candidate、future_rule_hint、rejected_or_context_only" in prompt
    assert "future_rule_hint 和 rejected_or_context_only 不得进入 factorization" in prompt
    assert '"candidate_payload": {' in prompt


def test_build_prompt_requires_appointment_delegation_scoring_candidate_contract() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "appointment_delegation scoring candidate 硬协议" in prompt
    assert "has_appointment_or_authorization" in prompt
    assert "has_named_actor" in prompt
    assert "has_task_or_responsibility" in prompt
    assert "has_result_or_feedback" in prompt
    assert "has_continuity_or_reuse" in prompt
    assert "appointed_actor" in prompt
    assert "misentrusted_actor" in prompt
    assert "candidate_payload.candidate_role 必须使用" in prompt
    assert "appointment_delegation_domain" in prompt
    assert "same_chain_outcome_summary" in prompt
    assert "三杰总评" in prompt
    assert "appointment_delegation factor hint shadow" in prompt
    assert "appointment_delegation_factor_hints" in prompt
    assert "importance_hint" in prompt
    assert "state_level_long_term" in prompt
    assert "effect_hint" in prompt
    assert "structural_bad" in prompt
    assert "continuity_hint" in prompt
    assert "long_multi_stage" in prompt
    assert "hint 不是正式 factor label，不写数值" in prompt
    assert "direction=neutral 不得输出该 hint" in prompt
    assert "negative_causality_needs_review" in prompt
    assert "appointment_delegation 判读选择" in prompt
    assert "弱任官履历、总评、后续处置或政治风险不得挤掉更早的完整授权收益链" in prompt
    assert "同一任务链里有多个具名 delegate" in prompt
    assert "object_claim_undercoverage coverage_gaps" in prompt
    assert "谓词词表缺失或别名缺失" in prompt
    assert '"rule_code": "talent_discovery | appointment_delegation | team_building' in prompt
    assert '"candidate_lane": "I5B.appointment_delegation' in prompt


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
    assert '"gap_type": "source_missing | object_claim_undercoverage' in prompt
    assert '"queue": "source_pack_refinement | claim_budget_refinement | ..."' in prompt
    assert '"recommended_action": "run_object_source_refiner | raise_claim_budget_or_split_object_claims | ..."' in prompt


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
    assert "任用授权质量" in prompt
    assert "覆盖整个 I5B 任人用人主题的宽材料池" in prompt
    assert "primary_bindings 必须为空数组" in prompt
    assert '"primary_bindings": []' in prompt
    assert "所有正式 rule 归属都写入 secondary_binding_candidates" in prompt


def test_build_prompt_personnel_political_wide_uses_route_table_and_fact_schema() -> None:
    candidates = sample_candidates()
    candidates["task_identity"]["capture_mode"] = "personnel_political_wide_shadow"
    candidates["task_identity"]["capture_profile"] = "personnel_political_wide"
    candidates["task_identity"]["fact_schema"] = "political_action_v1"
    candidates["task_identity"]["candidate_route_table_version"] = "personnel_political_v0_2"

    prompt = tool.build_prompt(candidates)

    assert "personnel_political_wide shadow pilot" in prompt
    assert "fact_schema=political_action_v1" in prompt
    assert "personnel_political_v0_2" in prompt
    assert "candidate_item_code" in prompt
    assert "candidate_lane" in prompt
    assert "required_facts_present" in prompt
    assert "current_rule_candidate" in prompt
    assert "future_rule_hint" in prompt
    assert "rejected_or_context_only" in prompt
    assert "I5C 已有权力控制草案 lane" in prompt
    assert "central_military_power_control" in prompt
    assert "regional_clan_power_control" in prompt
    assert "inner_favorite_power_control" in prompt
    assert "institutional_constraint_correction" in prompt
    assert "I5D political_character" in prompt
    assert "I5E cognition_learning" in prompt
    assert "I6 key_decision" in prompt
    assert "I3 military_frontier_result" in prompt
    assert "I7 historical_debt" in prompt
    assert '"primary_bindings": []' in prompt
