from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from scripts.dev import retrieval_v2_task_skeleton as task_skeleton


class RetrievalV2BatchTaskgenError(RuntimeError):
    pass


def _compact_context(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_code": context.get("target_code"),
        "emperor_name": context.get("emperor_name"),
        "intent_code": context.get("intent_code"),
        "target_aliases": context.get("target_aliases") or [],
    }


def _shared_contract(contexts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not contexts:
        raise RetrievalV2BatchTaskgenError("batch taskgen requires at least one context")
    first = contexts[0]
    return {
        "item_code": first.get("item_code"),
        "contract_code": first.get("contract_code"),
        "rule_code": first.get("rule_code"),
        "rule_label": first.get("rule_label"),
        "material_policy_payload": first.get("material_policy_payload"),
        "predicate_policy_payload": first.get("predicate_policy_payload"),
        "requirement_payload": first.get("requirement_payload"),
    }


def build_batch_discovery_prompt(
    items: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    *,
    allow_search: bool = True,
) -> str:
    contexts = [context for context, _skeleton in items]
    targets = []
    for context, skeleton in items:
        targets.append(
            {
                "context": _compact_context(context),
                "target_profile_skeleton": skeleton.get("target_profile") or {},
                "rule_skeleton": skeleton.get("rule") or {},
                "coverage_matrix": skeleton.get("coverage_matrix") or {},
                "source_strategy": skeleton.get("source_strategy") or {},
                "secondary_rule_candidates": skeleton.get("secondary_rule_candidates") or [],
            }
        )
    payload = {"shared_rule_contract": _shared_contract(contexts), "targets": targets}
    search_instruction = (
        "只能使用下方契约和本轮公开 web search。\n"
        if allow_search
        else "本次 invocation 未开启 web search；只能使用下方契约、目标 skeleton 和模型已有通用知识，不要声称执行了新的联网检索。\n"
    )
    return (
        "你是 emperor-evaluation retrieval_v2 clean batch taskgen discovery worker。\n"
        "本轮一次处理多个皇帝，但每个皇帝必须独立产出 discovery；不要互相借用旧结论，也不要降低任一目标的覆盖矩阵要求。\n"
        "禁止读取旧 source-packs、query profile、对象池、评分结果、旧判读结果、tmp 旧运行目录或记忆；"
        f"{search_instruction}"
        "史源优先使用 zh.wikisource.org 的正史、资治通鉴等原文页面；百科只可辅助定位对象和卷目，不可作为最终 source_document。\n"
        "必须遵守每个目标的 source_strategy：覆盖本纪/本传/通鉴等核心源页类型，用 source_hints 回源，不要用相邻朝代或同名前缀史书替代。\n"
        "最终只输出 JSON 对象，不要 Markdown 代码块。格式必须是 {\"targets\":[...]}。\n"
        "每个 targets[] 条目必须包含 target_code、emperor_name、target_profile、rule、object_seeds、source_documents、search_plan、generation_notes、clean_audit。\n"
        "object_seeds 建议 10-18 个；I5B item-wide 可放宽到 14-26 个，必须使用瘦字段：name、object_type、aliases、role_families、directions、source_document_codes；"
        "item-wide 发现对象时优先保留具名执行者和共同受命者，遇到同击、从击、使、将兵、分兵、给兵、奉使、说降、制礼等信号，不要只留最有名的一人；"
        "别名最多 4 个且必须标 strength：strong/medium/weak；不要输出 discovery_rationale、why_seeded、scoring_role_hints 或长解释。\n"
        "source_documents 建议 6-12 条，字段只使用 document_code/title/wikisource_title/url/source_kind/why_selected；why_selected 不超过 28 个汉字。generation_notes 最多 3 条短句。\n"
        "共享规则契约和目标 skeleton：\n"
        f"{task_skeleton.pretty_json(payload)}"
    )


def target_discoveries_from_payload(
    payload: Mapping[str, Any],
    *,
    expected_targets: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    rows = payload.get("targets") or payload.get("discoveries") or []
    if not isinstance(rows, list):
        raise RetrievalV2BatchTaskgenError("batch taskgen output must contain a targets list")
    by_code: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        discovery = dict(row)
        target_code = str(discovery.get("target_code") or "").strip()
        emperor_name = str(discovery.get("emperor_name") or "").strip()
        if target_code:
            by_code[target_code] = discovery
        if emperor_name:
            by_name[emperor_name] = discovery
    result: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for context in expected_targets:
        target_code = str(context.get("target_code") or "").strip()
        emperor_name = str(context.get("emperor_name") or "").strip()
        discovery = by_code.get(target_code) or by_name.get(emperor_name)
        if discovery is None:
            missing.append(emperor_name or target_code)
            continue
        result[target_code] = discovery
    if missing:
        raise RetrievalV2BatchTaskgenError(f"batch taskgen missing targets: {missing}")
    return result


def split_usage(usage: Mapping[str, Any], *, count: int, index: int) -> dict[str, int]:
    if count <= 0:
        return {}
    result: dict[str, int] = {}
    for key, value in usage.items():
        if not isinstance(value, int):
            continue
        base = value // count
        remainder = value % count
        result[key] = base + (1 if index < remainder else 0)
    return result


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
