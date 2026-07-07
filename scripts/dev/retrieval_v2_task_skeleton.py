from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from scripts.dev.retrieval_v2_contracts import (
    coverage_matrix_template,
    secondary_rule_hints,
    source_strategy_template,
    unique_strings,
)


class RetrievalV2TaskSkeletonError(RuntimeError):
    pass


PROTECTED_TASK_KEYS = {
    "job_code",
    "target_code",
    "emperor_name",
    "item_code",
    "contract_code",
    "rule_code",
    "target_payload",
    "source_strategy",
    "coverage_matrix",
    "secondary_rule_candidates",
}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        payload = json.loads(value)
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def text_from(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def list_policy_codes(rows: Any, *keys: str) -> list[str]:
    result: list[str] = []
    for row in as_list(rows):
        if isinstance(row, Mapping):
            result.append(text_from(row, *keys))
        else:
            result.append(str(row or ""))
    return unique_strings(result)


def target_aliases_from_context(context: Mapping[str, Any]) -> list[str]:
    aliases: list[Any] = [context.get("emperor_name")]
    for raw_alias in as_list(context.get("target_aliases")):
        if isinstance(raw_alias, Mapping):
            aliases.append(raw_alias.get("alias"))
        else:
            aliases.append(raw_alias)
    intent_payload = as_mapping(context.get("intent_payload"))
    target_profile = as_mapping(intent_payload.get("target_profile"))
    aliases.extend(as_list(target_profile.get("aliases")))
    return unique_strings(aliases)


def target_titles_from_context(context: Mapping[str, Any]) -> list[str]:
    aliases: list[Any] = []
    for raw_alias in as_list(context.get("target_aliases")):
        if not isinstance(raw_alias, Mapping):
            continue
        alias_type = str(raw_alias.get("alias_type") or "").strip()
        if alias_type and alias_type != "name":
            aliases.append(raw_alias.get("alias"))
    intent_payload = as_mapping(context.get("intent_payload"))
    target_profile = as_mapping(intent_payload.get("target_profile"))
    aliases.extend(as_list(target_profile.get("must_check_titles")))
    return unique_strings(aliases)


def coverage_matrix_from_context(context: Mapping[str, Any]) -> dict[str, Any]:
    requirement = as_mapping(context.get("requirement_payload"))
    matrix = as_mapping(requirement.get("coverage_matrix"))
    if matrix.get("role_families"):
        return json.loads(stable_json(matrix))
    rule_code = text_from(context, "rule_code")
    return coverage_matrix_template(
        rule_code,
        material_policy_codes=list_policy_codes(context.get("material_policy_payload"), "policy_code"),
        predicate_options=list_policy_codes(context.get("predicate_policy_payload"), "predicate", "predicate_code"),
    )


def secondary_rule_candidates_from_matrix(matrix: Mapping[str, Any], rule_code: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in as_list(matrix.get("secondary_rule_hints")):
        if not isinstance(raw, Mapping):
            continue
        candidate_rule = text_from(raw, "rule_code", "code")
        if candidate_rule:
            row = {
                key: text_from(raw, key)
                for key in ("rule_code", "reason", "hint_status", "candidate_item_code")
                if text_from(raw, key)
            }
            row["rule_code"] = candidate_rule
            row["reason"] = row.get("reason") or "coverage matrix hint"
            rows.append(row)
    if not rows:
        rows.extend(secondary_rule_hints(rule_code))
    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        deduped.setdefault(row["rule_code"], row)
    return list(deduped.values())


def build_task_skeleton(context: Mapping[str, Any]) -> dict[str, Any]:
    rule_code = text_from(context, "rule_code")
    item_code = text_from(context, "item_code")
    target_code = text_from(context, "target_code")
    emperor_name = text_from(context, "emperor_name")
    contract_code = text_from(context, "contract_code")
    if not target_code or not emperor_name or not rule_code:
        raise RetrievalV2TaskSkeletonError("context requires target_code, emperor_name, and rule_code")
    matrix = coverage_matrix_from_context(context)
    material_policies = as_list(context.get("material_policy_payload"))
    predicate_options = as_list(context.get("predicate_policy_payload"))
    target_payload = as_mapping(context.get("target_payload"))
    source_strategy = source_strategy_template(rule_code, metadata=target_payload)
    return {
        "job_code": f"JOB-{item_code}-{target_code}-{rule_code}-CLEAN",
        "target_code": target_code,
        "emperor_name": emperor_name,
        "item_code": item_code,
        "contract_code": contract_code,
        "rule_code": rule_code,
        "target_payload": target_payload,
        "target_profile": {
            "primary_name": emperor_name,
            "aliases": target_aliases_from_context(context),
            "must_check_titles": target_titles_from_context(context),
        },
        "rule": {
            "rule_code": rule_code,
            "rule_label": text_from(context, "rule_label"),
            "coverage_matrix": matrix,
            "material_policy_codes": list_policy_codes(material_policies, "policy_code"),
            "predicate_options": list_policy_codes(predicate_options, "predicate", "predicate_code"),
        },
        "coverage_matrix": matrix,
        "source_strategy": source_strategy,
        "secondary_rule_candidates": secondary_rule_candidates_from_matrix(matrix, rule_code),
        "object_seeds": [],
        "source_documents": [],
        "search_plan": {
            "generated_by": "scripts/dev/retrieval_v2_task_skeleton.py",
            "needs_cli_discovery": True,
            "discovery_scope": "object_seeds_and_source_documents",
        },
        "generation_notes": [
            "stable task fields were generated by retrieval_v2_task_skeleton.py; Codex taskgen should only fill discovery fields"
        ],
        "clean_audit": {
            "skeleton_generated_by": "scripts/dev/retrieval_v2_task_skeleton.py",
            "forbid_old_source_packs": True,
            "forbid_old_object_pool_results": True,
            "forbid_old_judgement_outputs": True,
            "runtime_rule_doc_reads_forbidden": True,
        },
        "task_skeleton": {
            "schema_version": 1,
            "context_fingerprint": stable_fingerprint(
                {
                    "target_code": target_code,
                    "contract_code": contract_code,
                    "rule_code": rule_code,
                    "coverage_matrix": matrix,
                }
            ),
            "protected_keys": sorted(PROTECTED_TASK_KEYS),
        },
    }


def merge_target_profile(base: Mapping[str, Any], discovery: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(stable_json(base))
    incoming = as_mapping(discovery)
    result["primary_name"] = str(result.get("primary_name") or incoming.get("primary_name") or "").strip()
    result["aliases"] = unique_strings([*(result.get("aliases") or []), *(incoming.get("aliases") or [])])
    result["must_check_titles"] = unique_strings(
        [*(result.get("must_check_titles") or []), *(incoming.get("must_check_titles") or [])]
    )
    return result


def merge_rule(base: Mapping[str, Any], discovery: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(stable_json(base))
    incoming = as_mapping(discovery)
    for key, value in incoming.items():
        if key in {"rule_code", "rule_label", "coverage_matrix"}:
            continue
        if isinstance(value, list):
            result[key] = unique_strings([*(result.get(key) or []), *value])
        elif value not in (None, "", {}, []):
            result[key] = value
    return result


def merge_generation_notes(*values: Any) -> list[str]:
    notes: list[Any] = []
    for value in values:
        if isinstance(value, list):
            notes.extend(value)
        elif value:
            notes.append(value)
    return unique_strings(notes)


def merge_taskgen_discovery(skeleton: Mapping[str, Any], discovery: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(stable_json(skeleton))
    for key, value in discovery.items():
        if key in PROTECTED_TASK_KEYS:
            continue
        if key in {"target_profile", "rule"}:
            continue
        if key in {"object_seeds", "source_documents", "documents"}:
            continue
        if key == "generation_notes":
            continue
        if key == "clean_audit" and isinstance(value, Mapping):
            result["clean_audit"] = {**as_mapping(result.get("clean_audit")), **dict(value)}
            continue
        if value not in (None, "", {}, []):
            result[key] = value
    result["target_profile"] = merge_target_profile(
        as_mapping(result.get("target_profile")),
        as_mapping(discovery.get("target_profile")),
    )
    result["rule"] = merge_rule(as_mapping(result.get("rule")), as_mapping(discovery.get("rule")))
    result["object_seeds"] = as_list(discovery.get("object_seeds")) or as_list(skeleton.get("object_seeds"))
    result["source_documents"] = (
        as_list(discovery.get("source_documents"))
        or as_list(discovery.get("documents"))
        or as_list(skeleton.get("source_documents"))
    )
    result["generation_notes"] = merge_generation_notes(
        skeleton.get("generation_notes"),
        discovery.get("generation_notes"),
        "taskgen discovery merged into script-generated skeleton",
    )
    result["task_skeleton"] = {
        **as_mapping(skeleton.get("task_skeleton")),
        "discovery_fingerprint": stable_fingerprint(
            {
                "object_seeds": result["object_seeds"],
                "source_documents": result["source_documents"],
            }
        ),
    }
    return result


def validate_task_for_candidates(task: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if not as_list(task.get("object_seeds")):
        issues.append("object_seeds is empty")
    if not as_list(task.get("source_documents")):
        issues.append("source_documents is empty")
    matrix = as_mapping(task.get("coverage_matrix"))
    if not matrix.get("role_families"):
        issues.append("coverage_matrix.role_families is empty")
    profile = as_mapping(task.get("target_profile"))
    if not profile.get("primary_name"):
        issues.append("target_profile.primary_name is empty")
    return issues


def discovery_profile_from_task(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "generated_by": "scripts/dev/retrieval_v2_task_skeleton.py",
        "schema_version": 1,
        "emperor_name": task.get("emperor_name") or "",
        "item_code": task.get("item_code") or "",
        "rule_code": task.get("rule_code") or "",
        "target_profile": task.get("target_profile") or {},
        "object_seeds": task.get("object_seeds") or [],
        "source_documents": task.get("source_documents") or [],
        "generation_notes": task.get("generation_notes") or [],
        "profile_fingerprint": stable_fingerprint(
            {
                "emperor_name": task.get("emperor_name"),
                "rule_code": task.get("rule_code"),
                "object_seeds": task.get("object_seeds") or [],
                "source_documents": task.get("source_documents") or [],
            }
        ),
    }


def profile_matches_context(profile: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    emperor_name = text_from(profile, "emperor_name")
    if emperor_name and emperor_name != text_from(context, "emperor_name"):
        return False
    profile_rule = text_from(profile, "rule_code")
    return not profile_rule or profile_rule == text_from(context, "rule_code")


def discovery_prompt(context: Mapping[str, Any], skeleton: Mapping[str, Any], *, allow_search: bool = True) -> str:
    compact_context = {
        "target_code": context.get("target_code"),
        "emperor_name": context.get("emperor_name"),
        "item_code": context.get("item_code"),
        "contract_code": context.get("contract_code"),
        "intent_code": context.get("intent_code"),
        "rule_code": context.get("rule_code"),
        "rule_label": context.get("rule_label"),
        "material_policy_payload": context.get("material_policy_payload"),
        "predicate_policy_payload": context.get("predicate_policy_payload"),
        "requirement_payload": context.get("requirement_payload"),
        "target_aliases": context.get("target_aliases") or [],
    }
    search_instruction = (
        "只能使用下方契约和本轮公开 web search。\n"
        if allow_search
        else "本次 invocation 未开启 web search；只能使用下方契约、task skeleton 已预填的 source_documents/search_plan 和模型已有通用知识，不要声称执行了新的联网检索；source_documents 必须沿用 skeleton 已有条目，不要新增或改写 URL / wikisource_title。\n"
    )
    return (
        "你是 emperor-evaluation retrieval_v2 clean taskgen discovery worker。\n"
        "脚本已经生成 task skeleton；你不要重写稳定字段，不要降低覆盖矩阵要求，只补发现字段。\n"
        "禁止读取旧 source-packs、query profile、对象池、评分结果、旧判读结果、tmp 旧运行目录或记忆；"
        f"{search_instruction}"
        "史源优先使用 zh.wikisource.org 的正史、资治通鉴等原文页面；百科只可辅助定位对象和卷目，不可作为最终 source_document。\n"
        "必须遵守 source_strategy：先覆盖本纪/本传/通鉴等核心源页类型，对核心对象名用 source_hints 回源，不要用相邻朝代或同名前缀史书替代。\n"
        "必须按 coverage_matrix 覆盖对象族和正负方向；不得因为人物材料密集而降低标准。\n"
        "若 task skeleton 已包含 source_documents/search_plan.presearch_hits，优先基于这些本轮脚本预搜索结果补对象和缺口；"
        "若本次 Codex invocation 未开启 web search，不要编造额外检索结果。\n"
        "最终只输出 JSON 对象，不要 Markdown 代码块。只需包含：target_profile 可补别名、rule 可补 keywords/query_terms/outcome_terms、"
        "object_seeds、source_documents、search_plan、generation_notes、clean_audit。\n"
        "object_seeds 建议 10-18 个；I5B item-wide 可放宽到 14-26 个，必须使用瘦字段：name、object_type、aliases、role_families、directions、source_document_codes；"
        "item-wide 发现对象时优先保留具名执行者和共同受命者，遇到同击、从击、使、将兵、分兵、给兵、奉使、说降、制礼等信号，不要只留最有名的一人；"
        "别名最多 4 个且必须标 strength：strong/medium/weak；不要输出 discovery_rationale、why_seeded、scoring_role_hints 或长解释。\n"
        "source_documents 建议 6-12 条，字段只使用 document_code/title/wikisource_title/url/source_kind/why_selected；why_selected 不超过 28 个汉字。generation_notes 最多 3 条短句。\n"
        "脚本生成的 task skeleton：\n"
        f"{pretty_json(skeleton)}\n"
        "DB 契约上下文：\n"
        f"{pretty_json(compact_context)}"
    )
