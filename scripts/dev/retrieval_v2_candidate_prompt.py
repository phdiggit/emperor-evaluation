from __future__ import annotations

import json
from typing import Any, Mapping

from scripts.dev import retrieval_v2_alias_pretag as alias_pretag
from scripts.dev import retrieval_v2_claim_quality as claim_quality
from scripts.dev import retrieval_v2_contracts as contracts


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def prompt_json(value: Any) -> str:
    return stable_json(value) + "\n"


def enum_text(values: tuple[str, ...]) -> str:
    return " / ".join(values)


PROMPT_CANDIDATE_SLICE_KEYS = (
    "slice_code",
    "document_code",
    "object_name",
    "locator",
    "score",
    "matched_aliases",
    "matched_rule_terms",
    "matched_outcome_terms",
    "matched_role_families",
    "text",
)

AD_IMPORTANCE_HINT_TEXT = enum_text(contracts.AD_IMPORTANCE_HINTS)
AD_EFFECT_HINT_TEXT = enum_text(contracts.AD_EFFECT_HINTS)
AD_CONTINUITY_HINT_TEXT = enum_text(contracts.AD_CONTINUITY_HINTS)
AD_HINT_CONFIDENCE_TEXT = enum_text(contracts.AD_HINT_CONFIDENCE_VALUES)
AD_UNCERTAINTY_FLAGS_TEXT = "、".join(contracts.AD_UNCERTAINTY_FLAGS)
AD_UNCERTAINTY_FLAGS_SCHEMA_TEXT = " | ".join(contracts.AD_UNCERTAINTY_FLAGS)
AD_FACTOR_HINT_SCHEMA_TEXT = (
    '"appointment_delegation_factor_hints": {'
    f'"importance_hint": "{AD_IMPORTANCE_HINT_TEXT.replace(" / ", " | ")}", '
    f'"effect_hint": "{AD_EFFECT_HINT_TEXT.replace(" / ", " | ")}", '
    f'"continuity_hint": "{AD_CONTINUITY_HINT_TEXT.replace(" / ", " | ")}", '
    f'"hint_confidence": {{"importance": "{AD_HINT_CONFIDENCE_TEXT.replace(" / ", " | ")}", '
    f'"effect": "{AD_HINT_CONFIDENCE_TEXT.replace(" / ", " | ")}", '
    f'"continuity": "{AD_HINT_CONFIDENCE_TEXT.replace(" / ", " | ")}"}}, '
    f'"uncertainty_flags": ["{AD_UNCERTAINTY_FLAGS_SCHEMA_TEXT}"]'
    "}"
)


CLAIM_EXTRACTION_ONLY_MODE = "claim_extraction_only"
CLAIM_EXTRACTOR_VERSION = "claim_extraction_only:v5_direction_free"


def prompt_candidate_slices(candidates: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    requested_owner = alias_pretag.candidate_requested_owner(candidates)
    resolver = alias_pretag.load_alias_resolver()
    source_titles = {
        str(row.get("document_code") or ""): str(row.get("title") or row.get("source_title") or "")
        for row in candidates.get("source_documents") or []
        if isinstance(row, Mapping) and str(row.get("document_code") or "")
    }
    for row in candidates.get("candidate_slices") or []:
        if not isinstance(row, Mapping):
            continue
        payload = {key: row[key] for key in PROMPT_CANDIDATE_SLICE_KEYS if key in row}
        object_cache = claim_quality.object_cache_row(row)
        if object_cache.get("section_heading"):
            payload["section_heading"] = object_cache.get("section_heading")
        if object_cache.get("quality_flags"):
            payload["quality_flags"] = object_cache.get("quality_flags")
        eligibility = claim_quality.slice_claim_eligibility(row)
        risk_flags = eligibility.get("risk_flags") or []
        if risk_flags:
            payload["slice_risk_flags"] = risk_flags
        if risk_flags or not eligibility.get("claim_eligible", True):
            payload["slice_claim_eligibility"] = eligibility
        alias_mentions = alias_pretag.slice_alias_mentions(
            {**row, "source_title": row.get("source_title") or source_titles.get(str(row.get("document_code") or ""), "")},
            requested_owner_name=requested_owner,
            resolver=resolver,
            only_prompt_relevant=True,
        )
        if alias_mentions:
            payload["alias_mentions"] = alias_mentions
        rows.append(payload)
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
        "source_ref_policy": claim_quality.source_ref_policy(candidates),
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


def build_claim_extraction_prompt(candidates: Mapping[str, Any]) -> str:
    payload = prompt_payload(candidates)
    task_identity = payload.get("task_identity") if isinstance(payload.get("task_identity"), Mapping) else {}
    capture_profile = str(task_identity.get("capture_profile") or "").strip()
    profile_note = (
        "本轮仍属于 personnel_political_wide 的第一阶段，只抽取可复用政治行动 claim；不做 rule 路由、AD scoring、factor hints 或 future hints。\n"
        if capture_profile == contracts.PERSONNEL_POLITICAL_WIDE_PROFILE
        else "本轮只抽取 claim；不做 rule 路由、factor hints 或 future hints。\n"
    )
    return (
        "你是 emperor-evaluation 项目的 retrieval_v2 claim 抽取 worker。本轮脚本已经完成源页抓取、缓存、别名命中和候选片段切片；"
        "你不要联网，不要使用记忆，不要读取旧结果文件，不要修改文件，不要写数据库，只根据本轮输入里的 candidate_slices 抽取事实。\n\n"
        f"{profile_note}"
        "目标：只生成 material_claims/context_claims/counter_claims，要求事实原子化、对象明确、动作明确、source_slice_refs 可复核。"
        "不要输出 primary_bindings，不要输出 secondary_binding_candidates，不要判断 appointment_delegation scoring，不要写 candidate_payload。"
        "如果同一对象有多条独立任务链，优先拆成多条 claim；如果预算不足但源片段已召回，写 object_claim_undercoverage，"
        "queue=claim_budget_refinement，recommended_action=raise_claim_budget_or_split_object_claims，do_not_add_recall_terms=true。"
        "如果当前源片段不足以支撑事实闭环，写 source_missing/source_gap，不要臆造 claim。\n\n"
        "claim_summary 必须能被所列 source_slice_refs 的原文直接支撑；不要把 A 片段的摘录挂到 B 事件 summary。"
        "如输入含 source_ref_policy，只能从该对象 allowed_source_refs_by_object 中取 refs；runner 会拒收跨对象 refs。"
        "如 candidate_slices[].alias_mentions 给出 deterministic resolved_owner_name，说明该片段中的皇帝别名已由本地别名表机械解析；"
        "若 claim 主行为人/actor 是该别名，claim.emperor_name 必须写 resolved_owner_name，不要绑到本轮 target emperor。"
        "输出要极简：不要输出 notes，不要输出 source_passage_refs，不要输出 claim_completeness；"
        "每条 claim 保留 fact_payload 和最多 2 条 evidence_spans 即可，这些字段只记录原文已经明确看到的事实结构。"
        f"fact_payload 使用 {contracts.POLITICAL_ACTION_FACT_SCHEMA} 字段：fact_schema、actor、object、action_type、event_scope、office_or_domain、"
        "outcome、cost_or_damage、time_context、source_span_refs、confidence、completeness。"
        "fact_schema 必须等于 political_action_v1；source_span_refs 必须引用本 claim 的 source_slice_refs 或 evidence_spans。"
        "evidence_spans.text 必须是对应 source_slice_ref 原文中的连续短句或短语，每条 text 尽量不超过 12 个汉字；优先 action/object/outcome。"
        "如果没有同链条结果反馈，就把 has_outcome=false / has_outcome_span=false，不要为了完整而臆造 outcome。"
        "claim 不输出 direction；如果同一材料包含不同事实链，拆成多条 claim，无法拆分时说明到 coverage_gaps。"
        "最终 JSON 默认不要复述 documents/passages，runner 会按 slice_code 自动生成 passages。\n\n"
        "claim-only 抽取预算：本阶段是 claim cache 构建，不是最终消费包压缩。"
        "不要把一个对象压缩成少数代表性 claim；要按独立事件链、职责域和结果反馈拆分。"
        "同一对象同一事件链的连续切片可合并成一个 claim，并把最多 3 个最强 slice_code 放入 source_slice_refs；"
        "但不同任命/授权、不同战役、不同边疆或中枢任务、不同处置/失控/评价事实必须拆成多条 claim。"
        "经验目标：每对象 1-3 个 slices 通常抽 1-3 条；4-7 个 slices 通常抽 3-5 条；"
        "8 个及以上 slices 的重要对象通常抽 5-8 条，除非事实确实高度重复。"
        "如果因为输出预算仍无法拆完，必须在 object_claim_undercoverage 中点明未拆事实类型和建议提高 claim 预算；"
        "不要只输出“最有名”或最容易摘要的三条。\n\n"
        "输入 JSON：\n"
        f"{prompt_json(payload)}\n"
        "最终回复必须只输出一个 JSON 对象，不要 Markdown 代码块，不要解释性前后文。JSON 结构如下：\n"
        "{\n"
        '  "job_code": "...",\n'
        '  "status": "succeeded | needs_refinement | blocked",\n'
        '  "documents": [],\n'
        '  "passages": [],\n'
        '  "claims": [{"claim_code": "CLM-...", "emperor_name": "...", "object_name": "...", "object_type": "person | event | group | mechanism", "claim_kind": "material_claim | context_claim | counter_claim", "claim_summary": "...", "confidence": 0.0, "source_slice_refs": ["SLI-..."], "fact_payload": {"fact_schema": "political_action_v1", "actor": "...", "object": "...", "action_type": "任命 | 授权 | 荐举 | 保全 | 处置 | 结党 | 收权 | 纳谏 | 拒谏 | 战役 | 制度高压 | 其他", "event_scope": "中枢 | 军事 | 地方 | 边疆 | 财政 | 监察 | 宗室 | 外戚 | 民生 | 其他", "office_or_domain": "...", "outcome": "...", "cost_or_damage": "...", "time_context": "...", "source_span_refs": ["SLI-..."], "confidence": 0.0, "completeness": {"has_actor": true, "has_object": true, "has_action": true, "has_outcome": false, "same_event_chain": false, "needs_source_extension": false}}, "evidence_spans": [{"span_type": "action | object | outcome | reason | institution | context", "source_slice_ref": "SLI-...", "text": "..."}]}],\n'
        '  "primary_bindings": [],\n'
        '  "secondary_binding_candidates": [],\n'
        '  "coverage_matrix": {"rule_code": "...", "role_families": [{"family_code": "...", "candidate_slice_count": 0, "accepted_claim_count": 0, "objects_checked": ["..."], "gaps": []}]},\n'
        '  "coverage": {"ready_for_object_pool": false, "checked_objects": ["..."], "missing_core_objects": ["..."], "claim_count": 0, "alias_coverage_note": "claim_extraction_only"},\n'
        '  "coverage_gaps": [{"gap_type": "source_missing | object_claim_undercoverage | predicate_missing | needs_primary_source | alias_missing | fetch_error | true_lack | other", "object_name": "...", "family_code": "...", "queue": "source_pack_refinement | claim_budget_refinement | ...", "diagnosis": "...", "recommended_action": "run_object_source_refiner | raise_claim_budget_or_split_object_claims | ...", "do_not_add_recall_terms": true}]\n'
        "}\n"
    )


def build_prompt(candidates: Mapping[str, Any]) -> str:
    payload = prompt_payload(candidates)
    task_identity = payload.get("task_identity") if isinstance(payload.get("task_identity"), Mapping) else {}
    if str(task_identity.get("judge_mode") or "").strip() == CLAIM_EXTRACTION_ONLY_MODE:
        return build_claim_extraction_prompt(candidates)
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
            "本轮是 I5B item-wide shadow pilot：目标是构造覆盖整个 I5B 任人用人主题的宽材料池。"
            "输出不要作为正式消费源；不要围绕单一 rule 的 primary binding 组织材料。"
            "claim 应覆盖当前 I5B formal rules 可复核的材料类型：任用授权质量、对象池全部人才对象与团队职能、荐举/识别/拔擢人才、"
            "保全/容忍/复用/疑忌/处置人才、亲私/近臣/朋党/结党/纳贿/专擅/谮害。"
            "I5C 权力控制四 lane、political_character 只作为 future_rule_hint。"
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
        "如果同一事实同时有授权和失败、撤权或负面后果，必须拆成授权事实与结果/撤权/失误事实；"
        "I5B item-wide shadow 中，即使只有 secondary_binding_candidates 或 future_rule_hint，也不要把不同事件链合成一个 claim；"
        "应拆成多条原子 claim。无法拆分时不要输出可计分 binding，改写 coverage_gaps 或标为 needs_review 且不可自动入库。\n\n"
        "负向 appointment_delegation 的硬门槛：伏诛、被废、被杀、罢免、削权、撤权、下狱等处置结果，不能单独构成 negative claim 或 revoked_or_failed_delegate 可计分 binding。"
        "只有同一候选材料同时证明被授权者在任内造成具体治理损害、军政任务失败、人才结构损害或授权链条失控，才可标 negative 并设 usable_for_scoring_cluster=true。"
        "否则将处置事实标为 neutral/context_claim 或不可计分 binding，并在 notes/binding_note 写明交消费侧结合人物画像判断。\n\n"
        "coverage_gaps 必须是后续可执行的补抓/补判任务：如果本 shard 只是未见负向授权损害，或仅见处置结果但不足以证明任内损害，不要写 negative_undercoverage。"
        "只有候选材料出现明确的治理损害、军政失败、人才结构损害或授权链条失控线索，但缺少足够原文闭环时，才写 negative_undercoverage。\n\n"
        "跨 rule 候选：你已经在读史料上下文，必须顺手为同一 claim 标出可复用的 secondary_binding_candidates。"
        "I5B 固定只有五个正式候选 rule：talent_discovery、appointment_delegation、team_building、tolerate_talent、anti_nepotism；"
        "旧 appointment_trust / delegation 兼容口径已放弃，任用、授权、复用、信任、职责结果反馈统一路由到 appointment_delegation。"
        "I5C 已有权力控制草案 lane：central_military_power_control、regional_clan_power_control、inner_favorite_power_control、institutional_constraint_correction；"
        "在本 shadow 抓包中默认作为 future/current candidate 线索输出，不直接判因子档位或入分。"
        "I5D political_character、I5E cognition_learning、I6 key_decision、I3 military_frontier_result、I7 historical_debt "
        "只能作为 future hint，必须在 candidate_payload 或 reason 中明确 hint_status=future_rule_hint。"
        "secondary candidate 只是后续复核线索，不是候选 rule 的入分结论；处置性材料尤其不能自动推成 tolerate_talent 或 appointment_delegation 负向结论。"
        "tolerate_talent 正向必须直接体现容谏、保全能臣、维护表达安全、修复授权信用，或对被谗毁/被疑/品行攻击人才的保护；"
        "单纯任用、信任、团队成员、采纳一般计策，不能自动转成 tolerate_talent positive。"
        "team_building 按皇帝对象池整体聚合；抓包候选阶段不要因为对象不是核心官职、核心将相或长期班底就排除，"
        "对象弱贡献、负贡献或 supporting_only 交给消费端窄验。\n\n"
        "不要手写 candidate_payload.personnel_profile 或 power_control_profile；runner 会按 claim.fact_payload 本地补齐，避免重复输出。"
        "如果确有无法从 fact_payload 推导的简短角色信息，可写 candidate_role、appointment_delegation_domain 或 same_chain_outcome_summary。"
        "personnel_political_wide 中必须把每个候选分成三态：current_rule_candidate、future_rule_hint、rejected_or_context_only；"
        "future_rule_hint 和 rejected_or_context_only 不得进入 factorization。\n\n"
        "appointment_delegation 覆盖皇帝对对象的任用、委任、信任、授权、托付、采纳、实际职责交付，以及这些安排的结果反馈和持续复用情况。"
        "正向候选包括任命、拜授、任用、起用、擢用、封授、授职，委任、托付、使其主事、令其将兵/治政/守地/筹饷/议策，"
        "明确信任、倚重、从其计、采纳其策、以为心腹/腹心，实质授权以及任用授权后的正向结果、职责履行、持续复用或岗位匹配反馈。"
        "负向候选包括错任、误用、偏信、任非其人，授权对象不匹配、授权后造成明确失败或损害，信任/授权判断明显失误，"
        "以及不当撤权、反复猜忌导致已授权安排失效且材料能直接指向任用授权质量问题的事实。\n\n"
        "appointment_delegation scoring candidate 硬协议：只有材料同时满足“任命/授权/权责配置、具名任用授权对象、具体任务或职责、同链条结果反馈或持续复用”时，"
        "才允许输出 rule_code=appointment_delegation 且 candidate_payload.scoring_candidate=true、usable_for_scoring_cluster=true。"
        "candidate_payload.appointment_delegation_chain 必须写 has_appointment_or_authorization、has_named_actor、has_task_or_responsibility、has_result_or_feedback、has_continuity_or_reuse 五个布尔值；"
        "前三项必须为 true，且 has_result_or_feedback 或 has_continuity_or_reuse 至少一项为 true，才可设 scoring_candidate=true。"
        "不满足时可以保留 appointment_delegation review/supporting candidate，但必须写 scoring_candidate=false 或 usable_for_scoring_cluster=false。"
        "candidate_payload.candidate_role 必须使用：appointed_actor、entrusted_actor、delegated_actor、strategic_advisor、military_commander、civil_official、"
        "misappointed_actor、misdelegated_actor、misentrusted_actor、authority_revoked_target。"
        "细分领域放 candidate_payload.appointment_delegation_domain，可用 military / civil / fiscal / frontier / strategic / institutional。"
        "same_chain_outcome_summary 用一句话说明同链条结果。三杰总评、单纯采纳计策、处置/诱执/撤权结局、人物画像材料，不得标 appointment_delegation usable_for_scoring_cluster=true；"
        "应路由到 team_building / tolerate_talent / future hint，或作为 appointment_delegation review candidate。\n\n"
        "appointment_delegation factor hint shadow：只对 rule_code=appointment_delegation、candidate_lane=I5B.appointment_delegation、"
        "scoring_candidate=true、usable_for_scoring_cluster=true 且 direction=positive/negative 的候选，"
        "可在 candidate_payload.appointment_delegation_factor_hints 输出有限枚举预填建议；direction=neutral 不得输出该 hint。"
        "hint 不是正式 factor label，不写数值，不写自由文本评分理由，不替消费端裁判；材料不足就写 unknown 或低置信，不要硬猜。"
        "字段值必须遵守最终 JSON schema 中的有限枚举。"
        "importance 可按岗位/任务层级相对积极判断；continuity 保守；effect 最保守，strong_success、major_bad、structural_bad 必须有同链条结果闭合。"
        "处置、诛废、谋反、功臣不保材料，只有能证明这是任用授权安排的直接履职后果，才给负向 effect；"
        "否则 effect_hint=unknown 或低置信，并加 negative_causality_needs_review。\n\n"
        "appointment_delegation 判读选择：source candidate 层已负责召回和补源；你只从输入片段中优先选择完整“授权/职责 + 同链条结果/复用”的代表事实。"
        "弱任官履历、总评、后续处置或政治风险不得挤掉更早的完整授权收益链；正向授权链和后续风险必须拆成不同 claim。"
        "同一对象有多条完整强链时，优先拆出出征、留守、镇守、督军、提督、平乱、防边、财政/行政专任等可独立闭合的任务链；"
        "不要只保留最早、最有名或最容易摘要的一条代表性材料。"
        "同一任务链里有多个具名 delegate 时，对可消费对象分别输出原子 claim；预算或对象缺失导致无法拆出时写 object_claim_undercoverage coverage_gaps。"
        "只有确认为谓词词表缺失或别名缺失时，才写 predicate_missing / alias_missing。\n\n"
        "personnel_political_wide 通用对象覆盖门禁：如果同一核心对象在 source passages、object biography 或 annals cross-check 中出现多条可复用 political_action_v1 事实，"
        "不得只输出一条代表性 claim。遇到任命/授权/委任/留守/镇守/总制/提督/出使/采纳/保全/处置/纠偏/约束/撤权/惩戒/平乱/出征/防边，"
        "且同时具备具体任务、职责、制度或事件，并出现结果、代价、持续复用、权力变化或治理反馈时，应尽量拆成独立原子 claim，分别路由到对应 candidate lane。"
        "若源片段已经召回、但预算不足或共同任务链中多个对象未能全部拆出，必须写 coverage_gap："
        "gap_type=object_claim_undercoverage，queue=claim_budget_refinement，recommended_action=raise_claim_budget_or_split_object_claims，do_not_add_recall_terms=true。"
        "如果源片段已经召回但对象没有被拆成 claim，这是 claim 原子化/对象覆盖问题，不要优先处理成新增召回词。"
        "只有本传/本纪线索显示核心对象仍有未拆事实、但当前 source passages/object biography/annals cross-check 没有召回可验证原文时，"
        "才写 gap_type=source_missing，queue=source_pack_refinement，recommended_action=run_object_source_refiner。"
        "如果当前只召回本纪处置线、谋反/伏诛/废官/废制度等结局线，缺少对象本传中的任用、宠任、专擅、职责滥用和直接后果链，"
        "不要硬写 appointment_delegation 负向 scoring candidate；写 source_missing/source_gap 或保留不可计分 review/context，诊断说明需要补本传授权滥用链。\n\n"
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
        "如输入含 source_ref_policy，只能从该对象 allowed_source_refs_by_object 中取 refs；runner 会拒收跨对象 refs。"
        "如 candidate_slices[].alias_mentions 给出 deterministic resolved_owner_name，说明该片段中的皇帝别名已由本地别名表机械解析；"
        "若 claim 主行为人/actor 是该别名，claim.emperor_name 必须写 resolved_owner_name，不要绑到本轮 target emperor。"
        "如果一个 summary 需要多个不同事实片段才能成立，拆成多个原子 claim，或把不确定部分放入 notes/coverage_gaps。"
        "不要把“本片段不支撑某对象/某 rule”写成 context_claim；这类不足只写 coverage_gaps。"
        "context_claim 只保留可被后续对象画像或跨 rule 复用的正向背景事实。"
        "除非你发现候选切片定位本身有错误，不要输出 documents/passages 明细。claim_summary、binding_note 和 gap diagnosis 都保持短句。\n\n"
        "判读预算：candidate_slices 是候选证据，不是逐条生成 claim 的清单。"
        "同一对象、同一谓词、同一事实类型、同一事件链的多个切片必须合并成一个 claim，并把最多 3 个最强 slice_code 放入 source_slice_refs。"
        "每个对象默认最多 2 个可消费 material_claim；只有同时存在授权事实与撤权/失败事实，或事实链明显不同，"
        "或 personnel_political_wide 核心对象存在多条可复用 political_action_v1 事实时才允许超过 2 个。"
        "如果同一对象存在多个完整 appointment_delegation scoring 链，优先保留最多 2 条完整 scoring 链；不要让弱 review、future hint 或单纯履历材料占掉这些名额。"
        "同一对象的第 3 条及以后完整强链可不全量展开；只有材料类型、方向、职责域或结果反馈相对独立时，才在 object_claim_undercoverage 中点明未拆事实类型和应提高 claim 预算/拆分对象 claim。"
        "核心对象超过预算而未拆出的事实必须进入 object_claim_undercoverage coverage_gaps，而不是静默丢弃。"
        "每条 claim 默认最多 2 个 secondary_binding_candidates；优先保留 current_rule_candidate，尤其是 appointment_delegation scoring candidate。"
        "同一 claim 的 future_rule_hint 最多 1 个，且只在确有独立可复核价值时输出；低价值 review 不要为了填满规则而输出。"
        "secondary_binding_candidates.reason、binding_note、notes 都写短句；能用 candidate_payload 结构表达的链条状态，不要在 reason 里重复长篇解释。"
        "不要为了每个官职、每场战役或每个相近片段各写一个 claim；选择最能支撑规则覆盖矩阵的代表事实。\n\n"
        "输入 JSON：\n"
        f"{prompt_json(payload)}\n"
        "最终回复必须只输出一个 JSON 对象，不要 Markdown 代码块，不要解释性前后文。JSON 结构如下；documents/passages 可省略或置空：\n"
        "{\n"
        '  "job_code": "...",\n'
        '  "status": "succeeded | needs_refinement | blocked",\n'
        '  "documents": [],\n'
        '  "passages": [],\n'
        '  "claims": [{"claim_code": "CLM-...", "emperor_name": "...", "object_name": "...", "object_type": "person | event | group | mechanism", "claim_kind": "material_claim | context_claim | counter_claim", "claim_summary": "...", "confidence": 0.0, "source_slice_refs": ["SLI-..."], "fact_payload": {"fact_schema": "political_action_v1", "actor": "...", "object": "...", "action_type": "任命 | 授权 | 荐举 | 保全 | 处置 | 结党 | 收权 | 纳谏 | 拒谏 | 战役 | 制度高压 | 其他", "event_scope": "中枢 | 军事 | 地方 | 边疆 | 财政 | 监察 | 宗室 | 外戚 | 民生 | 其他", "office_or_domain": "...", "outcome": "...", "cost_or_damage": "...", "time_context": "...", "source_span_refs": ["SLI-..."], "confidence": 0.0, "completeness": {"has_actor": true, "has_object": true, "has_action": true, "has_outcome": false, "same_event_chain": false, "needs_source_extension": false}}, "evidence_spans": [{"span_type": "action | object | outcome | reason | institution | context", "source_slice_ref": "SLI-...", "text": "..."}], "claim_completeness": {"has_action_span": true, "has_object_span": true, "has_outcome_span": false, "outcome_same_event_chain": false, "needs_source_extension": false}, "notes": "..."}],\n'
        + primary_bindings_schema
        + '  "secondary_binding_candidates": [{"claim_code": "CLM-...", "rule_code": "talent_discovery | appointment_delegation | team_building | tolerate_talent | anti_nepotism | central_military_power_control | regional_clan_power_control | inner_favorite_power_control | institutional_constraint_correction | political_character | cognition_learning | key_decision | military_frontier_result | historical_debt", "candidate_item_code": "I5B | I5C | I5D | I5E | I6 | I3 | I7", "candidate_lane": "I5B.appointment_delegation | team_building | talent_discovery | tolerate_talent | anti_nepotism | central_military_power_control | regional_clan_power_control | inner_favorite_power_control | institutional_constraint_correction | political_character | cognition_learning | key_decision | military_frontier_result | historical_debt", "hint_status": "current_rule_candidate | future_rule_hint | rejected_or_context_only", "direction": "positive | negative | neutral", "required_facts_present": ["actor", "object", "action_type", "source_span_refs"], "reason": "...", "confidence": 0.0, "candidate_payload": {"scoring_candidate": true, "usable_for_scoring_cluster": true, "appointment_delegation_chain": {"has_appointment_or_authorization": true, "has_named_actor": true, "has_task_or_responsibility": true, "has_result_or_feedback": true, "has_continuity_or_reuse": false}, '
        + AD_FACTOR_HINT_SCHEMA_TEXT
        + ', "candidate_role": "appointed_actor | entrusted_actor | delegated_actor | strategic_advisor | military_commander | civil_official | misappointed_actor | misdelegated_actor | misentrusted_actor | authority_revoked_target", "appointment_delegation_domain": "military | civil | fiscal | frontier | strategic | institutional", "same_chain_outcome_summary": "...", "hint_status": "current_rule_candidate"}}],\n'
        '  "coverage_matrix": {"rule_code": "...", "role_families": [{"family_code": "...", "candidate_slice_count": 0, "accepted_claim_count": 0, "objects_checked": ["..."], "gaps": []}]},\n'
        '  "coverage": {"ready_for_object_pool": false, "checked_objects": ["..."], "missing_core_objects": ["..."], "claim_count": 0, "alias_coverage_note": "..."},\n'
        '  "coverage_gaps": [{"gap_type": "source_missing | object_claim_undercoverage | predicate_missing | needs_primary_source | alias_missing | civil_undercoverage | negative_undercoverage | weak_alias_noise | fetch_error | true_lack | other", "object_name": "...", "family_code": "...", "queue": "source_pack_refinement | claim_budget_refinement | ...", "diagnosis": "...", "recommended_action": "run_object_source_refiner | raise_claim_budget_or_split_object_claims | ...", "do_not_add_recall_terms": true}]\n'
        "}\n"
    )
