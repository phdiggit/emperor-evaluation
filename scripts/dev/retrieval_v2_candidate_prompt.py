from __future__ import annotations

import json
from typing import Any, Mapping


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


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
        "candidate_slices": candidates.get("candidate_slices") or [],
        "coverage": candidates.get("coverage") or {},
        "coverage_gaps": candidates.get("coverage_gaps") or [],
    }


def build_prompt(candidates: Mapping[str, Any]) -> str:
    payload = prompt_payload(candidates)
    task_identity = payload.get("task_identity") if isinstance(payload.get("task_identity"), Mapping) else {}
    coverage_matrix = payload.get("coverage_matrix") if isinstance(payload.get("coverage_matrix"), Mapping) else {}
    target_rule_code = str(task_identity.get("rule_code") or coverage_matrix.get("rule_code") or "target_rule")
    return (
        "你是 emperor-evaluation 项目的 retrieval_v2 抓包判读 worker。本轮脚本已经完成源页抓取、缓存、别名命中和候选片段切片；"
        "你不要联网，不要使用记忆，不要读取旧结果文件，不要修改文件，不要写数据库，只根据本轮输入里的 candidate_slices 判读。\n\n"
        f"任务目标：生成可消费的 material_claims 和 {target_rule_code} primary_bindings；同时列出可复用到副 rule 的 secondary_binding_candidates。"
        "一个 claim 可服务多个 rule，但必须拆成独立 binding。"
        "如果候选片段不足，不要补写事实，沿用或补充 coverage_gaps。"
        "如果同一事实同时有授权和失败、撤权或负面后果，不要直接输出可消费的 mixed claim，必须拆成授权事实与结果/撤权/失误事实；无法拆分时标为 needs_review 且不可自动入库。\n\n"
        "负向 delegation 的硬门槛：伏诛、被废、被杀、罢免、削权、撤权、下狱等处置结果，不能单独构成 negative claim 或 revoked_or_failed_delegate 可计分 binding。"
        "只有同一候选材料同时证明被授权者在任内造成具体治理损害、军政任务失败、人才结构损害或授权链条失控，才可标 negative 并设 usable_for_scoring_cluster=true。"
        "否则将处置事实标为 neutral/context_claim 或不可计分 binding，并在 notes/binding_note 写明交消费侧结合人物画像判断。\n\n"
        "为节省 token，最终 JSON 默认不要复述 documents/passages；每条 claim 必须填写 source_slice_refs，runner 会按 slice_code 自动生成 passages 和 source_passage_refs。"
        "除非你发现候选切片定位本身有错误，不要输出 documents/passages 明细。claim_summary、binding_note 和 gap diagnosis 都保持短句。\n\n"
        "判读预算：candidate_slices 是候选证据，不是逐条生成 claim 的清单。"
        "同一对象、同一谓词、同一方向、同一事实类型的多个切片必须合并成一个 claim，并把最多 3 个最强 slice_code 放入 source_slice_refs。"
        "每个对象默认最多 2 个可消费 material_claim；只有同时存在清晰正向与负向、或授权事实与撤权/失败事实必须拆分时才允许超过 2 个。"
        "不要为了每个官职、每场战役或每个相近片段各写一个 claim；选择最能支撑规则覆盖矩阵的代表事实。\n\n"
        "输入 JSON：\n"
        f"{pretty_json(payload)}\n"
        "最终回复必须只输出一个 JSON 对象，不要 Markdown 代码块，不要解释性前后文。JSON 结构如下；documents/passages 可省略或置空：\n"
        "{\n"
        '  "job_code": "...",\n'
        '  "status": "succeeded | needs_refinement | blocked",\n'
        '  "documents": [],\n'
        '  "passages": [],\n'
        '  "claims": [{"claim_code": "CLM-...", "emperor_name": "...", "object_name": "...", "object_type": "person | event | group | mechanism", "claim_kind": "material_claim | context_claim | counter_claim", "claim_summary": "...", "direction": "positive | negative | neutral | mixed", "confidence": 0.0, "source_slice_refs": ["SLI-..."], "notes": "..."}],\n'
        f'  "primary_bindings": [{{"claim_code": "CLM-...", "rule_code": "{target_rule_code}", "predicate": "...", "direction": "positive | negative | neutral", "object_role": "...", "usable_for_object_payload": true, "usable_for_scoring_cluster": true, "confidence": 0.0, "binding_note": "..."}}],\n'
        '  "secondary_binding_candidates": [{"claim_code": "CLM-...", "rule_code": "appointment_trust | team_building | tolerate_talent | ...", "reason": "...", "confidence": 0.0}],\n'
        '  "coverage_matrix": {"rule_code": "...", "role_families": [{"family_code": "...", "candidate_slice_count": 0, "accepted_claim_count": 0, "objects_checked": ["..."], "gaps": []}]},\n'
        '  "coverage": {"ready_for_object_pool": false, "checked_objects": ["..."], "missing_core_objects": ["..."], "positive_claim_count": 0, "negative_claim_count": 0, "alias_coverage_note": "..."},\n'
        '  "coverage_gaps": [{"gap_type": "source_missing | predicate_missing | needs_primary_source | alias_missing | civil_undercoverage | negative_undercoverage | weak_alias_noise | fetch_error | true_lack | other", "object_name": "...", "family_code": "...", "diagnosis": "...", "recommended_action": "..."}]\n'
        "}\n"
    )
