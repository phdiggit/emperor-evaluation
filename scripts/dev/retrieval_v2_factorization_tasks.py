from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402


PROMPT_PASSAGE_LIMIT = 3
PROMPT_QUOTE_LIMIT = 900
PROMPT_PROFILE_LIST_LIMIT = 3
PATCH_FALLBACK_BEGIN = "PATCH_JSONL_BEGIN"
PATCH_FALLBACK_END = "PATCH_JSONL_END"


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def flatten_batch_materials(batch: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    materials: dict[str, dict[str, Any]] = {}
    for group in batch.get("groups") or []:
        if not isinstance(group, Mapping):
            continue
        for row in group.get("materials") or []:
            if not isinstance(row, Mapping):
                continue
            binding_code = text(row.get("binding_code"))
            if binding_code:
                materials[binding_code] = dict(row)
    return materials


def task_code(batch: Mapping[str, Any]) -> str:
    return "RV2F-" + stable_hash([batch.get("batch_id"), [row.get("binding_code") for row in flatten_batch_materials(batch).values()]], length=16)


def prompt_passage(row: Mapping[str, Any]) -> dict[str, Any]:
    quote = text(row.get("quote"))
    if len(quote) > PROMPT_QUOTE_LIMIT:
        quote = quote[:PROMPT_QUOTE_LIMIT] + "..."
    return {
        "source_title": text(row.get("source_title")),
        "title": text(row.get("title")),
        "locator": text(row.get("locator")),
        "quote": quote,
    }


def prompt_profile_rows(rows: Any, fields: Sequence[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in (rows or [])[:PROMPT_PROFILE_LIST_LIMIT]:
        if not isinstance(row, Mapping):
            continue
        result.append({field: text(row.get(field)) for field in fields if text(row.get(field))})
    return result


def prompt_material(row: Mapping[str, Any]) -> dict[str, Any]:
    obj = row.get("object") if isinstance(row.get("object"), Mapping) else {}
    claim = row.get("claim") if isinstance(row.get("claim"), Mapping) else {}
    template = row.get("factor_patch_template") if isinstance(row.get("factor_patch_template"), Mapping) else {}
    return {
        "binding_code": text(row.get("binding_code")),
        "emperor_name": text(row.get("emperor_name")),
        "target_code": text(row.get("target_code")),
        "rule_code": text(row.get("rule_code")),
        "direction": text(row.get("direction")),
        "object_role": text(row.get("object_role")),
        "predicate": text(row.get("predicate")),
        "confidence": text(row.get("binding_confidence")),
        "object": {
            "canonical_name": text(obj.get("canonical_name")),
            "object_type": text(obj.get("object_type")),
            "talent_grade": text(obj.get("talent_grade")),
            "talent_grade_basis": text(obj.get("talent_grade_basis"))[:160],
            "person_roles": prompt_profile_rows(obj.get("person_roles"), ("role_kind", "dynasty_label", "role_title")),
            "person_affiliations": prompt_profile_rows(obj.get("person_affiliations"), ("affiliation_kind", "dynasty_label", "polity_label", "affiliation_label")),
        },
        "claim": {
            "summary": text(claim.get("summary")),
            "source_passages": [prompt_passage(item) for item in (claim.get("source_passages") or [])[:PROMPT_PASSAGE_LIMIT] if isinstance(item, Mapping)],
        },
        "required_patch": {
            "binding_code": text(row.get("binding_code")),
            "target_action": "score | supporting_only | exclude",
            "side": template.get("side") or text(row.get("direction")),
            "factor_keys": list((template.get("factor_refs") or {}).keys()),
            "patch_note": "中文高信息判断",
        },
    }


def slim_batch_for_prompt(batch: Mapping[str, Any]) -> dict[str, Any]:
    factor_options: dict[str, list[dict[str, Any]]] = {}
    materials = list(flatten_batch_materials(batch).values())
    for material in materials:
        template = material.get("factor_patch_template") if isinstance(material.get("factor_patch_template"), Mapping) else {}
        candidates = template.get("factor_option_candidates") if isinstance(template.get("factor_option_candidates"), Mapping) else {}
        for factor_name, rows in candidates.items():
            key = text(factor_name)
            if key and key not in factor_options:
                factor_options[key] = [
                    {
                        "label": text(row.get("label")),
                        "value_num": text(row.get("value_num")),
                        "option_code": text(row.get("option_code")),
                    }
                    for row in rows
                    if isinstance(row, Mapping)
                ]
    return {
        "batch_id": text(batch.get("batch_id")),
        "material_count": len(materials),
        "factor_options_by_factor": dict(sorted(factor_options.items())),
        "materials": [prompt_material(row) for row in materials],
    }


def expected_output_contract(path: Path) -> dict[str, Any]:
    return {
        "kind": "jsonl_patch",
        "path": repo_relative(path),
        "fallback": "last_message_marked_block",
        "begin": PATCH_FALLBACK_BEGIN,
        "end": PATCH_FALLBACK_END,
    }


def resolve_repo_path(value: Any) -> Path:
    path = Path(text(value))
    if path.is_absolute():
        return path
    return ROOT / path


def patch_path_for_task(task: Mapping[str, Any]) -> Path:
    raw_patch_path = text(task.get("patch_path"))
    if raw_patch_path:
        return resolve_repo_path(raw_patch_path)
    outputs = task.get("expected_outputs") if isinstance(task.get("expected_outputs"), Sequence) else []
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        if text(output.get("kind")) == "jsonl_patch" and text(output.get("path")):
            return resolve_repo_path(output.get("path"))
    raise ValueError(f"task {text(task.get('task_code')) or '<unknown>'} is missing patch_path/expected_outputs")


def expected_output_contracts_path(task: Mapping[str, Any]) -> str:
    return repo_relative(patch_path_for_task(task))


def prompt_for_batch(*, batch: Mapping[str, Any], output_jsonl: Path) -> str:
    prompt_payload = slim_batch_for_prompt(batch)
    rule_codes = {
        text(material.get("rule_code"))
        for material in flatten_batch_materials(batch).values()
        if text(material.get("rule_code"))
    }
    skill_instruction = ""
    if "delegation" in rule_codes:
        skill_instruction = (
            "delegation 轻量校准：包内 direction 就是本轮 side，不重新判断正负；"
            "positive 行不得选择负值 `result_feedback`，negative 行不得选择正值 `result_feedback`；"
            "`authorization_intensity` 只看授权范围；`result_feedback` 只看本材料证明的授权任务结果，"
            "不得把后续撤权、诛废、猜忌、清洗、谋反/反叛、自疑聚兵或功臣不保直接当作 delegation 结果反馈。\n"
        )
    if "team_building" in rule_codes:
        skill_instruction += (
            "team_building 校准：`talent_quality_factor` 使用材料中已给出的人才等级预填值，不临场改等级；"
            "`role_complementarity_factor` 和 `long_term_stability_factor` 是同一皇帝团队级因子，"
            "同一 batch / target 内所有 `score` 行必须选择完全相同的这两个 label；"
            "team_building 的计分承载是皇帝对象池全部具体人才对象，不得因对象不是核心官职、核心将相或长期班底而 `exclude`；"
            "同一人物多条 team_building binding 默认只保留最能代表其团队职能的一条 `score`，其它写 `supporting_only`。\n"
        )
    if "talent_discovery" in rule_codes:
        skill_instruction += (
            "talent_discovery 校准：提拔、拔擢、擢用只有在 quote 显示对象此前低位、被埋没、未充分显名、"
            "异质来源、旧阵营，或存在破格识别、试用、荐举链条时，才可作为发现人才信号；"
            "普通升迁、已知重臣任命、单纯授权办事不得纳入发现人才，若只有任官而无发现性信号则 `exclude`。\n"
        )
    return (
        "# retrieval_v2 factorization task\n\n"
        "你是消费侧因子化判断子进程。不要修改代码、数据库或 schema；唯一允许写入的是指定 JSONL patch 文件。\n"
        "你可以只读查看仓库内已生成材料；不得执行破坏性命令。必须覆盖本 batch 的每一条 material。\n\n"
        + skill_instruction
        + f"- output_jsonl: `{repo_relative(output_jsonl)}`\n"
        "- target_action 只能是 `score`、`supporting_only` 或 `exclude`。\n"
        "- `score` 必须填写 side 和所有 factor_refs；factor_refs.*.label 必须严格使用 factor_options_by_factor 中的 label。\n"
        "- `score.side` 是最终入分方向，不是候选包 direction；所选 factor 数值乘积为负时必须填 `negative`，为正时必须填 `positive`。\n"
        "- `supporting_only` 表示材料有上下文价值但不单独入分；`exclude` 表示不应进入本 rule 计分；两者必须写 `side:null` 和 `factor_refs:{}`。\n"
        "- claim.summary 只作索引；因子取值只能使用 source_passages.quote 明示支持的事实，不得用 summary、历史常识或相邻未给出的上下文补齐战果、撤权、处置或履职结果。\n"
        "- delegation 的 `result_feedback` 只评价授权安排本身的任务收益或任务损害；撤权、诛废、猜忌、清洗、谋反/反叛、自疑聚兵、功臣不保等处置性材料，只有证明其是该授权安排的直接履职结果时才可入分，否则用 `supporting_only` 或 `exclude`。\n"
        "- 若藩王/重臣后续谋反、反叛或聚兵，quote 又把原因解释为同功者被杀、功臣安全恐惧、猜忌或政权安全压力，不得按 delegation 负向结果入分；改用 `supporting_only` 或 `exclude`。\n"
        "- `attribution_factor` 最高档只用于 quote 明示皇帝亲自判断且存在逆阻力/反常规取舍；普通诏命、任官、谕令、群体“某等”受命一般不超过“皇帝决策链清楚”。\n"
        "- 若 quote 未出现对象名或核心授权事实，必须 `exclude`；若 quote 只证明任命/授权但不证明结果，`result_feedback` 只能选“履职反馈较弱，不足以支撑高强度授权正证。”或对应弱档。\n"
        "- 同一 claim/object/side 拆成多个 role binding 时，默认最多保留一个 `score`：选择 quote 中最直接、结果闭环最强的职责入分；其它 role 若没有独立职责和独立结果闭环，必须 `supporting_only`，不要因为同人同段重复放大。\n"
        "- patch_note 必须是中文高信息判断，说明为什么 score/supporting_only/exclude；不要写模板句。\n\n"
        "输出要求：优先写入 output_jsonl；每行一个 JSON object，字段为 `binding_code`、`target_action`、`side`、`factor_refs`、`patch_note`。"
        f"如果写文件失败，就把完整 JSONL 放在最终回复的 `{PATCH_FALLBACK_BEGIN}` 和 `{PATCH_FALLBACK_END}` 标记之间，不要输出其它 Markdown。\n\n"
        "## Batch\n\n"
        "```json\n"
        + json.dumps(prompt_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )
