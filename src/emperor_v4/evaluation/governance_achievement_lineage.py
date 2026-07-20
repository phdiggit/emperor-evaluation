from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4

from emperor_v4.adapters.structured_output_contract import (
    validate_codex_output_schema,
    validate_payload_against_schema,
)
from emperor_v4.evaluation.governance_achievement_registry import (
    validate_governance_achievement_registry,
)


OUTPUT_SCHEMA_VERSION = "governance-achievement-lineage-output-v1"
PREPARATION_SCHEMA_VERSION = "governance-achievement-lineage-preparation-v1"
AUDIT_SCHEMA_VERSION = "governance-achievement-lineage-audit-v1"
POLICY_VERSION = "governance-achievement-lineage-refinement-v2"
BROAD_LINEAGE_LIMITATION = (
    "存在多事实上游组件；当前保留组件级完整史源，正式接受前需细化本成果的逐事实引用子集。"
)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    _atomic_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _fact_rows(
    component_refs: Sequence[str],
    components: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = []
    seen = set()
    for component_ref in component_refs:
        for fact in components[component_ref]["facts"]:
            fact_ref = str(fact["fact_ref"])
            if not fact_ref or fact_ref in seen:
                continue
            seen.add(fact_ref)
            rows.append(
                {
                    "fact_ref": fact_ref,
                    "component_ref": component_ref,
                    "title": fact["title"],
                    "period": fact["period"],
                    "action": fact["action"],
                    "implementation": fact["implementation"],
                    "observable_result": fact["observable_result"],
                    "actors": [
                        {
                            "canonical_name": actor["canonical_name"],
                            "responsibility_role": actor["responsibility_role"],
                            "role_basis": actor["role_basis"],
                        }
                        for actor in fact["actors"]
                    ],
                    "source_refs": fact["source_refs"],
                }
            )
    return rows


def prepare_governance_achievement_lineage(
    achievement_audit: Mapping[str, object],
    candidate_preparation: Mapping[str, object],
    *,
    output_root: Path,
    output_schema_path: Path,
) -> dict[str, object]:
    if achievement_audit.get("status") != "accepted_shadow":
        raise ValueError("governance achievement audit 未达到 accepted_shadow")
    if candidate_preparation.get("schema_version") != (
        "governance-achievement-candidate-preparation-v1"
    ):
        raise ValueError("candidate preparation 版本不支持")
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    queue = achievement_audit.get("lineage_refinement_queue") or ()
    if not queue:
        raise ValueError("没有待细化的治理成果 lineage")
    achievements = {
        str(row["achievement_ref"]): row
        for row in achievement_audit["registry"]["achievements"]
    }
    items = []
    for queued in queue:
        key = str(queued["independent_governance_key"])
        matches = [
            row
            for row in achievements.values()
            if row["independent_governance_key"] == key
        ]
        if len(matches) != 1:
            raise ValueError("lineage queue 未唯一映射 achievement")
        achievement = matches[0]
        broad_component_refs = {str(value) for value in queued["component_refs"]}
        component_refs = [str(value) for value in achievement["neutral_fact_refs"]]
        if not broad_component_refs <= set(component_refs):
            raise ValueError("lineage queue 组件不属于 achievement")
        facts = _fact_rows(component_refs, candidate_preparation["components"])
        if not facts:
            raise ValueError("lineage refinement 缺少允许事实")
        items.append(
            {
                "achievement_ref": achievement["achievement_ref"],
                "achievement": {
                    "canonical_label": achievement["canonical_label"],
                    "domain": achievement["domain"],
                    "period": achievement["period"],
                    "observable_result": achievement["observable_result"],
                    "participants": achievement["participants"],
                    "ruler_links": achievement["ruler_links"],
                },
                "component_refs": component_refs,
                "allowed_facts": facts,
            }
        )
    fingerprint = sha256(
        json.dumps([POLICY_VERSION, items], ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()[:16].upper()
    task_code = f"GOVACH-LINEAGE-{fingerprint}"
    prompt = f"""EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS
TOOLS: FORBIDDEN
REPOSITORY_READ: FORBIDDEN
OUTPUT: JSON_ONLY

你只负责把治理成果精确绑定到已经允许的中性 fact_refs。不得联网、补史实、修改成果内容、人物归责、尺度、方向或分数。

规则：
1. 每个 achievement_ref 必须且只能出现一次。
2. fact_refs 只能选该项 allowed_facts 中直接支持 achievement 的事实；相同组件中的其他制度、案件、时期或结果不得因共享史源而附带进入。
3. 每个 component_ref 必须二选一：至少选择其中一个直接支持的 fact_ref，或将该组件列入 unsupported_component_refs。不得为了覆盖组件而选择仅仅“接近”的事实。
4. 选择足以支持行动、实现结果和人物归责的最小事实集合；同一事实的跨书变体可以同时保留，但无新增支持的信息不必凑数。
5. unsupported_component_refs 只能列本成果的 component_refs，且不得与已选 fact 所属组件重叠；后置审计器会剔除这些不支持组件。
6. 不输出 source refs。后置审计器会从 fact_refs 确定性派生逐字史源。

固定身份：
- schema_version: {OUTPUT_SCHEMA_VERSION}
- task_code: {task_code}

只输出严格符合 JSON Schema 的一个对象。

INPUT
{json.dumps(items, ensure_ascii=False, sort_keys=True)}
"""
    prompt_path = output_root / "prompt.md"
    result_path = output_root / "result.json"
    event_path = output_root / "events.jsonl"
    _atomic_text(prompt_path, prompt)
    task = {
        "task_code": task_code,
        "prompt_path": str(prompt_path.resolve()),
        "last_message_path": str(result_path.resolve()),
        "log_path": str(event_path.resolve()),
        "permission_profile": "review-only",
        "argv": [
            "codex",
            "exec",
            "--output-schema",
            str(output_schema_path.resolve()),
            "-",
        ],
    }
    _atomic_text(
        output_root / "task.jsonl",
        json.dumps(task, ensure_ascii=False, sort_keys=True) + "\n",
    )
    preparation = {
        "schema_version": PREPARATION_SCHEMA_VERSION,
        "task_code": task_code,
        "items": {str(row["achievement_ref"]): row for row in items},
        "output_schema_path": str(output_schema_path.resolve()),
    }
    _atomic_json(output_root / "preparation.json", preparation)
    return preparation


def audit_governance_achievement_lineage(
    achievement_audit: Mapping[str, object],
    candidate_preparation: Mapping[str, object],
    lineage_preparation: Mapping[str, object],
    payload: Mapping[str, object],
    *,
    output_schema_path: Path,
    registry_schema_path: Path,
) -> dict[str, object]:
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    validate_payload_against_schema(payload, schema)
    if payload["task_code"] != lineage_preparation["task_code"]:
        raise ValueError("lineage task_code 不匹配")
    expected = set(lineage_preparation["items"])
    actual = [str(row["achievement_ref"]) for row in payload["selections"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("lineage achievement 覆盖不唯一")
    selections = {}
    unsupported_total = 0
    for row in payload["selections"]:
        achievement_ref = str(row["achievement_ref"])
        item = lineage_preparation["items"][achievement_ref]
        allowed = {str(fact["fact_ref"]): fact for fact in item["allowed_facts"]}
        selected = [str(value) for value in row["fact_refs"]]
        if len(selected) != len(set(selected)) or not set(selected) <= set(allowed):
            raise ValueError("lineage fact_refs 越界或重复")
        selected_components = {str(allowed[ref]["component_ref"]) for ref in selected}
        unsupported = [str(value) for value in row["unsupported_component_refs"]]
        if len(unsupported) != len(set(unsupported)) or not set(unsupported) <= set(
            item["component_refs"]
        ):
            raise ValueError("lineage unsupported_component_refs 越界或重复")
        if selected_components & set(unsupported):
            raise ValueError("lineage 同一组件不得同时选择和标记不支持")
        if selected_components | set(unsupported) != set(item["component_refs"]):
            raise ValueError("lineage 未完整裁决 achievement 的全部组件")
        unsupported_total += len(unsupported)
        selections[achievement_ref] = selected

    refined = []
    refined_count = 0
    for achievement in achievement_audit["registry"]["achievements"]:
        achievement_ref = str(achievement["achievement_ref"])
        if achievement_ref in selections:
            fact_refs = selections[achievement_ref]
            item = lineage_preparation["items"][achievement_ref]
            fact_by_ref = {
                str(row["fact_ref"]): row for row in item["allowed_facts"]
            }
            source_refs = sorted(
                {str(ref) for fact_ref in fact_refs for ref in fact_by_ref[fact_ref]["source_refs"]}
            )
            refined_count += 1
        else:
            component_refs = [str(value) for value in achievement["neutral_fact_refs"]]
            facts = _fact_rows(component_refs, candidate_preparation["components"])
            if len(facts) != len(component_refs):
                raise ValueError("非队列成果不是一组件一事实，无法确定性收窄 lineage")
            fact_refs = [str(row["fact_ref"]) for row in facts]
            source_refs = sorted(
                {str(ref) for row in facts for ref in row["source_refs"]}
            )
        refined.append(
            {
                **dict(achievement),
                "neutral_fact_refs": fact_refs,
                "source_refs": source_refs,
                "limitations": [
                    str(value)
                    for value in achievement["limitations"]
                    if value != BROAD_LINEAGE_LIMITATION
                ],
            }
        )
    registry = {
        **dict(achievement_audit["registry"]),
        "achievements": refined,
    }
    validation = validate_governance_achievement_registry(
        registry, schema_path=registry_schema_path
    )
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "accepted_shadow",
        "task_code": payload["task_code"],
        "achievement_count": len(refined),
        "lineage_refinement_applied_count": refined_count,
        "lineage_refinement_remaining_count": 0,
        "unsupported_component_count": unsupported_total,
        "registry": registry,
        "registry_validation": validation,
        "limitations": payload["limitations"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="治理成果逐事实 lineage 异常细化")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--achievement-audit", type=Path, required=True)
    prepare.add_argument("--candidate-preparation", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--output-schema", type=Path, required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--achievement-audit", type=Path, required=True)
    audit.add_argument("--candidate-preparation", type=Path, required=True)
    audit.add_argument("--lineage-preparation", type=Path, required=True)
    audit.add_argument("--result", type=Path, required=True)
    audit.add_argument("--output-schema", type=Path, required=True)
    audit.add_argument("--registry-schema", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    achievement_audit = json.loads(args.achievement_audit.read_text(encoding="utf-8"))
    candidate_preparation = json.loads(
        args.candidate_preparation.read_text(encoding="utf-8")
    )
    if args.command == "prepare":
        report = prepare_governance_achievement_lineage(
            achievement_audit,
            candidate_preparation,
            output_root=args.output_root,
            output_schema_path=args.output_schema,
        )
    else:
        report = audit_governance_achievement_lineage(
            achievement_audit,
            candidate_preparation,
            json.loads(args.lineage_preparation.read_text(encoding="utf-8")),
            json.loads(args.result.read_text(encoding="utf-8")),
            output_schema_path=args.output_schema,
            registry_schema_path=args.registry_schema,
        )
        _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
