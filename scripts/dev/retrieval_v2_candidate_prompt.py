from __future__ import annotations

import json
from typing import Any, Mapping

from scripts.dev import retrieval_v2_contracts as contracts


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


PROMPT_CANDIDATE_SLICE_KEYS = (
    "slice_code",
    "document_code",
    "object_name",
    "matched_aliases",
    "matched_alias_strengths",
    "matched_rule_terms",
    "matched_outcome_terms",
    "matched_target_aliases",
    "matched_role_families",
    "weak_alias_only",
    "locator",
    "score",
    "text",
    "merged_from_slice_codes",
    "merged_slice_count",
)


def prompt_candidate_slices(candidates: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in candidates.get("candidate_slices") or []:
        if not isinstance(row, Mapping):
            continue
        rows.append({key: row[key] for key in PROMPT_CANDIDATE_SLICE_KEYS if key in row})
    return rows


def prompt_payload(candidates: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_identity": candidates.get("task_identity") or {},
        "target_profile": candidates.get("target_profile") or {},
        "rule": candidates.get("rule") or {},
        "coverage_matrix": candidates.get("coverage_matrix") or {},
        "secondary_rule_candidates": candidates.get("secondary_rule_candidates") or [],
        "object_seeds": candidates.get("object_seeds") or [],
        "source_documents": candidates.get("source_documents") or [],
        "fetch_errors": candidates.get("fetch_errors") or [],
        "candidate_slices": prompt_candidate_slices(candidates),
        "coverage": candidates.get("coverage") or {},
        "coverage_gaps": candidates.get("coverage_gaps") or [],
    }


def candidate_route_lanes_text() -> str:
    rows = []
    for row in contracts.PERSONNEL_POLITICAL_ROUTE_LANES:
        rows.append(
            f"{row['candidate_item_code']} {row['candidate_lane']} "
            f"({row['hint_status']}): {row['description']}"
        )
    return "；".join(rows)


def build_prompt(candidates: Mapping[str, Any]) -> str:
    payload = prompt_payload(candidates)
    task_identity = payload.get("task_identity") if isinstance(payload.get("task_identity"), Mapping) else {}
    coverage_matrix = payload.get("coverage_matrix") if isinstance(payload.get("coverage_matrix"), Mapping) else {}
    target_rule_code = str(task_identity.get("rule_code") or coverage_matrix.get("rule_code") or "target_rule")
    capture_mode = str(task_identity.get("capture_mode") or "").strip()
    capture_profile = str(task_identity.get("capture_profile") or "").strip()
    shadow_instruction = ""
    binding_instruction = (
        f"任务目标：生成可消费的 material_claims 和 {target_rule_code} primary_bindings；同时列出可复用到副 rule 的 secondary_binding_candidates。"
    )
    primary_bindings_schema = (
        f'  "primary_bindings": [{{"claim_code": "CLM-...", "rule_code": "{target_rule_code}", "predicate": "...", "direction": "positive | negative | neutral", "object_role": "...", "usable_for_object_payload": true, "usable_for_scoring_cluster": true, "confidence": 0.0, "binding_note": "..."}}],\n'
    )
    if capture_mode == "i5b_wide_shadow":
        shadow_instruction = (
            "本轮是 I5B-wide shadow pilot：目标是评估宽抓宽标的 claim 原子化、secondary candidates 质量、token/耗时和重复减少效果。"
            "输出不要作为正式消费源；不要为了追求全覆盖而扩大到泛泛人物传记摘要，仍然只保留可被 I5B 任人用人相关 rule 复核的原子材料。"
            "优先覆盖材料类型：任命、荐举、信任、授权、团队、容才、疑忌、亲私、结党、撤权、处置、权臣/军头失控。"
            "每条 claim 都要尽量给出 primary binding 与 secondary_binding_candidates 的边界说明，便于消费端窄入分。\n\n"
        )
    elif capture_mode == "i5b_item_wide_shadow":
        target_rule_code = "i5b_item_wide"
        shadow_instruction = (
            "本轮是 I5B item-wide shadow pilot：目标不是改造某个 delegation 包，而是构造覆盖整个 I5B 任人用人主题的宽材料池。"
            "输出不要作为正式消费源；不要围绕单一 rule 的 primary binding 组织材料。"
            "claim 应覆盖当前 I5B formal rules 可复核的材料类型：合理授权、任命/委任/信任/误任、对象池全部人才对象与团队职能、荐举/识别/拔擢人才、"
            "保全/容忍/复用/疑忌/处置人才、亲私/近臣/朋党/结党/纳贿/专擅/谮害。"
            "power_control、political_character 只作为 future_rule_hint。"
            "每条 claim 的消费入口是 secondary_binding_candidates；primary_bindings 在本模式下必须为空数组，避免伪装成某个单 rule 的正式包。\n\n"
        )
        binding_instruction = (
            "任务目标：生成 I5B item-wide material_claims，并为每条 claim 标出可复核的 claim_rule_binding_candidates。"
            "本模式下 primary_bindings 必须为空数组；所有正式 rule 归属都写入 secondary_binding_candidates，消费端再窄验晋升。"
        )
        primary_bindings_schema = '  "primary_bindings": [],\n'
    elif capture_mode == contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE or capture_profile == contracts.PERSONNEL_POLITICAL_WIDE_PROFILE:
        target_rule_code = "i5b_item_wide"
        shadow_instruction = (
            "本轮是 personnel_political_wide shadow pilot：目标是构造可复用的人事政治宽包，先正式覆盖 I5B B/C/D/E 候选，"
            "并为 I5C、I5D、I5E、I6、I3、I7 输出 future hints。输出不要作为正式消费源；不要把 future hint 伪装成当前入分结论。"
            f"每条 claim 的 fact_payload 必须使用 fact_schema={contracts.POLITICAL_ACTION_FACT_SCHEMA}；"
            "secondary_binding_candidates 必须显式写 candidate_item_code、candidate_lane、hint_status、direction、required_facts_present。"
            "hint_status 只能是 current_rule_candidate、future_rule_hint、rejected_or_context_only；"
            "只有 current_rule_candidate 才可能被消费端窄验晋升，future_rule_hint 和 rejected_or_context_only 不进入 factorization。"
            f"跨项候选路由表 {contracts.CANDIDATE_ROUTE_TABLE_VERSION}：{candidate_route_lanes_text()}。\n\n"
        )
        binding_instruction = (
            "任务目标：生成 personnel_political_wide material_claims，并为每条 claim 标出当前 I5B 正式候选或跨项 future hint。"
            "本模式下 primary_bindings 必须为空数组；所有候选归属都写入 secondary_binding_candidates，消费端再窄验晋升。"
        )
        primary_bindings_schema = '  "primary_bindings": [],\n'
    return (
        "你是 emperor-evaluation 项目的 retrieval_v2 抓包判读 worker。本轮脚本已经完成源页抓取、缓存、别名命中和候选片段切片；"
        "你不要联网，不要使用记忆，不要读取旧结果文件，不要修改文件，不要写数据库，只根据本轮输入里的 candidate_slices 判读。\n\n"
        f"{shadow_instruction}"
        f"{binding_instruction}"
        "一个 claim 可服务多个 rule，但必须拆成独立 binding。"
        "如果候选片段不足，不要补写事实，沿用或补充 coverage_gaps。"
        "如果同一事实同时有授权和失败、撤权或负面后果，不要直接输出可消费的 mixed claim，必须拆成授权事实与结果/撤权/失误事实；"
        "任何带 usable_for_scoring_cluster=true binding 的 claim 都不得使用 direction=mixed。"
        "I5B item-wide shadow 中，即使只有 secondary_binding_candidates 或 future_rule_hint，也不要把不同事件链的正负材料合成 direction=mixed；"
        "应拆成多条 positive / negative / neutral 原子 claim。无法拆分时不要输出可计分 binding，改写 coverage_gaps 或标为 needs_review 且不可自动入库。\n\n"
        "负向 delegation 的硬门槛：伏诛、被废、被杀、罢免、削权、撤权、下狱等处置结果，不能单独构成 negative claim 或 revoked_or_failed_delegate 可计分 binding。"
        "只有同一候选材料同时证明被授权者在任内造成具体治理损害、军政任务失败、人才结构损害或授权链条失控，才可标 negative 并设 usable_for_scoring_cluster=true。"
        "否则将处置事实标为 neutral/context_claim 或不可计分 binding，并在 notes/binding_note 写明交消费侧结合人物画像判断。\n\n"
        "coverage_gaps 必须是后续可执行的补抓/补判任务：如果本 shard 只是未见负向授权损害，或仅见处置结果但不足以证明任内损害，不要写 negative_undercoverage。"
        "只有候选材料出现明确的治理损害、军政失败、人才结构损害或授权链条失控线索，但缺少足够原文闭环时，才写 negative_undercoverage。\n\n"
        "跨 rule 候选：你已经在读史料上下文，必须顺手为同一 claim 标出可复用的 secondary_binding_candidates。"
        "I5B 当前正式候选限 delegation、appointment_trust、team_building、talent_discovery、tolerate_talent、anti_nepotism；"
        "I5C power_control、I5D political_character、I5E cognition_learning、I6 key_decision、I3 military_frontier_result、I7 historical_debt "
        "只能作为 future hint，必须在 candidate_payload 或 reason 中明确 hint_status=future_rule_hint。"
        "secondary candidate 只是后续复核线索，不是候选 rule 的入分结论；处置性材料尤其不能自动推成 tolerate_talent 或 delegation 负向结论。"
        "tolerate_talent 正向必须直接体现容谏、保全能臣、维护表达安全、修复授权信用，或对被谗毁/被疑/品行攻击人才的保护；"
        "单纯任用、信任、团队成员、采纳一般计策，不能自动转成 tolerate_talent positive。"
        "personnel_political_wide 中必须把每个候选分成三态：current_rule_candidate、future_rule_hint、rejected_or_context_only；"
        "future_rule_hint 和 rejected_or_context_only 不得进入 factorization。\n\n"
        "delegation scoring candidate 硬协议：只有材料同时满足“授权/任命/权责配置、具名被授权者、具体任务或职责、同链条履职结果”四项时，"
        "才允许输出 rule_code=delegation 且 candidate_payload.scoring_candidate=true、usable_for_scoring_cluster=true。"
        "candidate_payload.delegation_chain 必须写 has_authorization_or_office、has_named_delegate、has_task_or_responsibility、has_same_chain_outcome 四个布尔值；"
        "只要任一项为 false，就可以保留 delegation review/supporting candidate，但必须写 scoring_candidate=false 或 usable_for_scoring_cluster=false。"
        "candidate_payload.candidate_role 必须使用消费侧 object_role：delegated_actor、authority_recipient、authority_revoked_target、misdelegated_actor。"
        "细分领域放 candidate_payload.delegation_domain，可用 military / civil / fiscal / frontier / strategic / institutional。"
        "same_chain_outcome_summary 用一句话说明同链条结果。三杰总评、单纯采纳计策、处置/诱执/撤权结局、人物画像材料，不得标 delegation usable_for_scoring_cluster=true；"
        "应路由到 appointment_trust / team_building / tolerate_talent / future hint，或作为 delegation review candidate。\n\n"
        "delegation 召回优先级：同一对象同时存在“封王/任官/总评”与“给兵、给金、遣使、命将、授权任务并有战果/治理结果”时，"
        "优先抽取后者作为 scoring candidate；前者只作 appointment_trust、team_building 或 delegation review/supporting。"
        "如果每对象 claim 预算不足，先丢弃较弱的封王/任官 review claim，也不要丢弃给兵/给金/遣使/命将后的同链条收益 claim。"
        "说降或归附后分兵、给兵、与俱收兵、会战、破敌、定地，属于高优先级 delegation 正向链。"
        "后续反叛、被诛、被废等负向处置不得挤掉同对象更早的正向授权收益链；正向授权链和后续政治风险必须拆成不同 claim。"
        "如果同一片段中多个具名被授权者共同承担同一任务且共享同一结果，例如 A、B、C 同击某地并定其地，"
        "不要只把 B/C 藏在 A 的 claim_summary 里；对可作为消费对象的具名 delegate 分别输出原子 claim。"
        "如果因为 object_seeds 缺失、source_slice_refs 不足或预算限制无法拆出某个具名 delegate，必须写 coverage_gaps，"
        "gap_type=predicate_missing 或 alias_missing，object_name 填未拆出的具名对象，diagnosis 说明它被埋在共同任务链中，recommended_action 写补对象/补源后重判。\n\n"
        "personnel_political_wide / I5B-wide 事实骨架：每条 material_claim 尽量补充 fact_payload、evidence_spans、claim_completeness，"
        "这些字段只记录抓包端读原文时已经明确看到的事实结构，不是最终 factor label 或入分结论。"
        f"fact_payload 使用 {contracts.POLITICAL_ACTION_FACT_SCHEMA} 字段：fact_schema、actor、object、action_type、event_scope、office_or_domain、"
        "outcome、cost_or_damage、time_context、source_span_refs、confidence、completeness。"
        "fact_schema 必须等于 political_action_v1；source_span_refs 必须引用本 claim 的 source_slice_refs 或 evidence_spans；"
        "completeness 至少写 has_actor、has_object、has_action、has_outcome、same_event_chain、needs_source_extension。"
        "action_type 可用 任命 / 授权 / 荐举 / 保全 / 处置 / 结党 / 收权 / 纳谏 / 拒谏 / 战役 / 制度高压 / 其他；"
        "event_scope 可用 中枢 / 军事 / 地方 / 边疆 / 财政 / 监察 / 宗室 / 外戚 / 民生 / 其他。"
        "evidence_spans 使用短原文 span，不要求精确字符 offset；每个 span 写 span_type、source_slice_ref、text，"
        "span_type 只能是 action / object / outcome / reason / institution / context。"
        "evidence_spans.text 必须是对应 source_slice_ref 原文中的连续短句或短语，不要用省略号、括号补充、白话改写或跨句拼接。"
        "claim_completeness 使用 has_action_span、has_object_span、has_outcome_span、outcome_same_event_chain、needs_source_extension。"
        "如果没有结果反馈，就把 has_outcome_span=false，不要为了完整而臆造 outcome；如果 action 和 outcome 不在同一事件链，outcome_same_event_chain=false。\n\n"
        "为节省 token，最终 JSON 默认不要复述 documents/passages；每条 claim 必须填写 source_slice_refs，runner 会按 slice_code 自动生成 passages 和 source_passage_refs。"
        "claim_summary 必须能被所列 source_slice_refs 的原文直接支撑；不要把 A 片段的摘录挂到 B 事件 summary。"
        "如果一个 summary 需要多个不同事实片段才能成立，拆成多个原子 claim，或把不确定部分放入 notes/coverage_gaps。"
        "不要把“本片段不支撑某对象/某 rule”写成 context_claim；这类不足只写 coverage_gaps。"
        "context_claim 只保留可被后续对象画像或跨 rule 复用的正向背景事实。"
        "军事 delegation 尤其要优先抽取“授权任务 + 对应战果/反馈”的闭环 claim；"
        "如果同一切片中可见命某人北征、取某地、破某军等结果，不要只概括为任职、督军或中枢职责履历。"
        "除非你发现候选切片定位本身有错误，不要输出 documents/passages 明细。claim_summary、binding_note 和 gap diagnosis 都保持短句。\n\n"
        "判读预算：candidate_slices 是候选证据，不是逐条生成 claim 的清单。"
        "同一对象、同一谓词、同一方向、同一事实类型的多个切片必须合并成一个 claim，并把最多 3 个最强 slice_code 放入 source_slice_refs。"
        "每个对象默认最多 2 个可消费 material_claim；只有同时存在清晰正向与负向、或授权事实与撤权/失败事实必须拆分时才允许超过 2 个。"
        "如果同一对象存在多个完整 delegation scoring 链，优先保留最多 2 条完整 scoring 链；不要让弱 review、future hint 或单纯履历材料占掉这些名额。"
        "每条 claim 默认最多 3 个 secondary_binding_candidates；只保留最可复核的 rule 候选，低价值 review 不要为了填满规则而输出。"
        "secondary_binding_candidates.reason、binding_note、notes 都写短句；能用 candidate_payload 结构表达的链条状态，不要在 reason 里重复长篇解释。"
        "不要为了每个官职、每场战役或每个相近片段各写一个 claim；选择最能支撑规则覆盖矩阵的代表事实。\n\n"
        "输入 JSON：\n"
        f"{pretty_json(payload)}\n"
        "最终回复必须只输出一个 JSON 对象，不要 Markdown 代码块，不要解释性前后文。JSON 结构如下；documents/passages 可省略或置空：\n"
        "{\n"
        '  "job_code": "...",\n'
        '  "status": "succeeded | needs_refinement | blocked",\n'
        '  "documents": [],\n'
        '  "passages": [],\n'
        '  "claims": [{"claim_code": "CLM-...", "emperor_name": "...", "object_name": "...", "object_type": "person | event | group | mechanism", "claim_kind": "material_claim | context_claim | counter_claim", "claim_summary": "...", "direction": "positive | negative | neutral | mixed", "confidence": 0.0, "source_slice_refs": ["SLI-..."], "fact_payload": {"fact_schema": "political_action_v1", "actor": "...", "object": "...", "action_type": "任命 | 授权 | 荐举 | 保全 | 处置 | 结党 | 收权 | 纳谏 | 拒谏 | 战役 | 制度高压 | 其他", "event_scope": "中枢 | 军事 | 地方 | 边疆 | 财政 | 监察 | 宗室 | 外戚 | 民生 | 其他", "office_or_domain": "...", "outcome": "...", "cost_or_damage": "...", "time_context": "...", "source_span_refs": ["SLI-..."], "confidence": 0.0, "completeness": {"has_actor": true, "has_object": true, "has_action": true, "has_outcome": false, "same_event_chain": false, "needs_source_extension": false}}, "evidence_spans": [{"span_type": "action | object | outcome | reason | institution | context", "source_slice_ref": "SLI-...", "text": "..."}], "claim_completeness": {"has_action_span": true, "has_object_span": true, "has_outcome_span": false, "outcome_same_event_chain": false, "needs_source_extension": false}, "notes": "..."}],\n'
        + primary_bindings_schema
        + '  "secondary_binding_candidates": [{"claim_code": "CLM-...", "rule_code": "delegation | appointment_trust | team_building | talent_discovery | tolerate_talent | anti_nepotism | power_control | political_character | cognition_learning | key_decision | military_frontier_result | historical_debt", "candidate_item_code": "I5B | I5C | I5D | I5E | I6 | I3 | I7", "candidate_lane": "delegation | appointment_trust | team_building | talent_discovery | tolerate_talent | anti_nepotism | power_control | political_character | cognition_learning | key_decision | military_frontier_result | historical_debt", "hint_status": "current_rule_candidate | future_rule_hint | rejected_or_context_only", "direction": "positive | negative | neutral", "required_facts_present": ["actor", "object", "action_type", "source_span_refs"], "reason": "...", "confidence": 0.0, "candidate_payload": {"scoring_candidate": true, "usable_for_scoring_cluster": true, "delegation_chain": {"has_authorization_or_office": true, "has_named_delegate": true, "has_task_or_responsibility": true, "has_same_chain_outcome": true}, "candidate_role": "delegated_actor | authority_recipient | authority_revoked_target | misdelegated_actor", "delegation_domain": "military | civil | fiscal | frontier | strategic | institutional", "same_chain_outcome_summary": "...", "hint_status": "current_rule_candidate"}}],\n'
        '  "coverage_matrix": {"rule_code": "...", "role_families": [{"family_code": "...", "candidate_slice_count": 0, "accepted_claim_count": 0, "objects_checked": ["..."], "gaps": []}]},\n'
        '  "coverage": {"ready_for_object_pool": false, "checked_objects": ["..."], "missing_core_objects": ["..."], "positive_claim_count": 0, "negative_claim_count": 0, "alias_coverage_note": "..."},\n'
        '  "coverage_gaps": [{"gap_type": "source_missing | predicate_missing | needs_primary_source | alias_missing | civil_undercoverage | negative_undercoverage | weak_alias_noise | fetch_error | true_lack | other", "object_name": "...", "family_code": "...", "diagnosis": "...", "recommended_action": "..."}]\n'
        "}\n"
    )
