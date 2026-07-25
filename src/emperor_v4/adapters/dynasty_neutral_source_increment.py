from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Mapping, Sequence
from uuid import uuid4

from emperor_v4.adapters.structured_output_contract import (
    validate_codex_output_schema,
    validate_payload_against_schema,
)


OUTPUT_SCHEMA_VERSION = "dynasty-neutral-source-increment-output-v1"
PREPARATION_SCHEMA_VERSION = "dynasty-neutral-source-increment-preparation-v1"
AUDIT_SCHEMA_VERSION = "dynasty-neutral-source-increment-audit-v1"
_TEXT_TOKEN = re.compile(r"[\w\u3400-\u9fff]+")


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


def _chain_text(chain: Mapping[str, object]) -> str:
    actors = " ".join(str(row.get("name") or "") for row in chain.get("actors") or ())
    return " ".join(
        str(chain.get(key) or "")
        for key in (
            "title",
            "period",
            "action",
            "implementation",
            "observable_result",
            "cost_or_burden",
        )
    ) + " " + actors


def _grams(value: str) -> set[str]:
    compact = "".join(_TEXT_TOKEN.findall(value.lower()))
    return {compact[index : index + 2] for index in range(max(0, len(compact) - 1))}


def _actor_names(chain: Mapping[str, object]) -> set[str]:
    return {
        str(row.get("name") or "")
        for row in chain.get("actors") or ()
        if str(row.get("name") or "")
    }


def _compact_chain(
    chain: Mapping[str, object], *, candidate: bool
) -> dict[str, object]:
    keys = [
        "chain_key",
        "title",
        "domain",
        "period",
        "action",
        "implementation",
        "observable_result",
        "cost_or_burden",
    ]
    if candidate:
        keys.extend(
            (
                "affected_groups",
                "operation_status",
                "temporal_scope",
                "geographic_scope",
            )
        )
    compact = {key: chain.get(key) for key in keys}
    compact["actors"] = [
        {
            key: row.get(key)
            for key in ("name", "responsibility_role", "contribution_phases")
        }
        for row in chain.get("actors") or ()
    ]
    return compact


def _candidate_baselines(
    candidate: Mapping[str, object],
    baseline_chains: Sequence[Mapping[str, object]],
    *,
    limit: int = 5,
) -> list[Mapping[str, object]]:
    candidate_grams = _grams(_chain_text(candidate))
    candidate_actors = _actor_names(candidate)
    scored = []
    for baseline in baseline_chains:
        baseline_grams = _grams(_chain_text(baseline))
        union = candidate_grams | baseline_grams
        lexical = len(candidate_grams & baseline_grams) / len(union) if union else 0.0
        domain_bonus = 0.18 if baseline.get("domain") == candidate.get("domain") else 0.0
        actor_bonus = 0.3 if candidate_actors & _actor_names(baseline) else 0.0
        scored.append((lexical + domain_bonus + actor_bonus, baseline))
    return [row for _, row in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]


def _audit_chains(audit: Mapping[str, object], label: str) -> list[Mapping[str, object]]:
    if audit.get("status") != "accepted_shadow" or audit.get("failures"):
        raise ValueError(f"{label} audit 未达到 accepted_shadow")
    chains = [row for row in audit.get("chains") or () if isinstance(row, Mapping)]
    if not chains:
        raise ValueError(f"{label} audit 缺少 chains")
    keys = [str(row.get("chain_key") or "") for row in chains]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{label} chain_key 缺失或重复")
    return chains


def prepare_comparison(
    baseline_audit: Mapping[str, object],
    candidate_audit: Mapping[str, object],
    *,
    output_root: Path,
    output_schema_path: Path,
) -> dict[str, object]:
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    baseline = _audit_chains(baseline_audit, "baseline")
    candidate = _audit_chains(candidate_audit, "candidate")
    rows = []
    allowed_by_candidate = {}
    for chain in candidate:
        recalled = _candidate_baselines(chain, baseline)
        candidate_key = str(chain["chain_key"])
        allowed_by_candidate[candidate_key] = [str(row["chain_key"]) for row in recalled]
        rows.append(
            {
                "candidate": _compact_chain(chain, candidate=True),
                "baseline_candidates": [
                    _compact_chain(row, candidate=False) for row in recalled
                ],
            }
        )
    fingerprint = sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16].upper()
    task_code = f"DYNGOV-INCREMENT-{fingerprint}"
    prompt = f"""EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS
TOOLS: FORBIDDEN
REPOSITORY_READ: FORBIDDEN
OUTPUT: JSON_ONLY

你是朝代制度史中性材料的跨书增量比较器。只比较 INPUT 中已经分别通过史源回指验收的事实链；不得调用工具、读取仓库、使用外部知识、修改史实或进行评分。

逐一覆盖每条 candidate，判断它相对列出的 baseline_candidates 属于：
- same_fact_restatement：同一事项且除独立史源佐证外，没有实质新增事实；
- same_fact_enrichment：同一事项，但新增实施、结果、成本、人物责任、范围或时间信息；
- new_fact：baseline candidates 中不存在同一事项；
- uncertain：现有摘要不足以可靠判断。

baseline_chain_keys 只列真正同一事项的 baseline chain_key，不得因为同领域就关联。new_fact 时必须为空；uncertain 可列疑似同一事项，也可为空。added_dimensions 只列 candidate 实际新增的维度：same_fact_restatement 只能列 independent_source_attestation；same_fact_enrichment 必须至少列一个 independent_source_attestation 以外的实质维度；new_fact 不得列 independent_source_attestation；uncertain 必须为空。不要把措辞更详细当作事实新增。每条 candidate 必须且只能出现一次。

固定身份：
- schema_version: {OUTPUT_SCHEMA_VERSION}
- task_code: {task_code}
- baseline_count: {len(baseline)}
- candidate_count: {len(candidate)}

只输出严格符合传入 JSON Schema 的一个 JSON object。

INPUT
{json.dumps(rows, ensure_ascii=False, sort_keys=True)}
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
    report = {
        "schema_version": PREPARATION_SCHEMA_VERSION,
        "task_code": task_code,
        "baseline_count": len(baseline),
        "candidate_count": len(candidate),
        "candidate_chain_keys": [str(row["chain_key"]) for row in candidate],
        "baseline_chain_keys": [str(row["chain_key"]) for row in baseline],
        "allowed_baselines_by_candidate": allowed_by_candidate,
        "output_schema_path": str(output_schema_path.resolve()),
        "formal_writes": 0,
        "score_writes": 0,
    }
    _atomic_json(output_root / "preparation.json", report)
    return report


def audit_comparison(
    preparation: Mapping[str, object],
    payload: Mapping[str, object],
    *,
    output_schema_path: Path,
) -> dict[str, object]:
    if preparation.get("schema_version") != PREPARATION_SCHEMA_VERSION:
        raise ValueError("source increment preparation 版本不支持")
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    validate_payload_against_schema(payload, schema)
    for key in ("task_code", "baseline_count", "candidate_count"):
        if payload[key] != preparation[key]:
            raise ValueError(f"source increment {key} 不匹配")
    expected = set(preparation["candidate_chain_keys"])
    comparisons = payload["comparisons"]
    actual = [row["candidate_chain_key"] for row in comparisons]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("source increment candidate 覆盖不唯一")
    allowed = preparation["allowed_baselines_by_candidate"]
    for row in comparisons:
        baseline_keys = row["baseline_chain_keys"]
        if len(baseline_keys) != len(set(baseline_keys)):
            raise ValueError("source increment baseline_chain_keys 重复")
        if not set(baseline_keys) <= set(allowed[row["candidate_chain_key"]]):
            raise ValueError("source increment baseline_chain_keys 越界")
        dimensions = row["added_dimensions"]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("source increment added_dimensions 重复")
        classification = row["classification"]
        if classification == "new_fact" and baseline_keys:
            raise ValueError("new_fact 不得绑定 baseline chain")
        if classification in {"same_fact_restatement", "same_fact_enrichment"} and not baseline_keys:
            raise ValueError("同一事实分类必须绑定 baseline chain")
        dimension_set = set(dimensions)
        if classification == "same_fact_restatement" and dimension_set != {
            "independent_source_attestation"
        }:
            raise ValueError("same_fact_restatement 只能增加独立史源佐证")
        if classification == "same_fact_enrichment" and not (
            dimension_set - {"independent_source_attestation"}
        ):
            raise ValueError("same_fact_enrichment 缺少实质新增维度")
        if classification == "new_fact" and "independent_source_attestation" in dimension_set:
            raise ValueError("new_fact 不得声明独立史源佐证")
        if classification == "uncertain" and dimensions:
            raise ValueError("uncertain 不得提前声明新增维度")
    counts = Counter(row["classification"] for row in comparisons)
    dimension_counts = Counter(
        dimension for row in comparisons for dimension in row["added_dimensions"]
    )
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "accepted_shadow",
        "task_code": preparation["task_code"],
        "baseline_count": preparation["baseline_count"],
        "candidate_count": preparation["candidate_count"],
        "classification_counts": dict(sorted(counts.items())),
        "added_dimension_counts": dict(sorted(dimension_counts.items())),
        "comparisons": comparisons,
        "limitations": payload["limitations"],
        "formal_writes": 0,
        "score_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="朝代制度史跨书增量比较")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--baseline-audit", type=Path, required=True)
    prepare.add_argument("--candidate-audit", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--output-schema", type=Path, required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--preparation", type=Path, required=True)
    audit.add_argument("--result", type=Path, required=True)
    audit.add_argument("--output-schema", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        report = prepare_comparison(
            json.loads(args.baseline_audit.read_text(encoding="utf-8")),
            json.loads(args.candidate_audit.read_text(encoding="utf-8")),
            output_root=args.output_root,
            output_schema_path=args.output_schema,
        )
    else:
        report = audit_comparison(
            json.loads(args.preparation.read_text(encoding="utf-8")),
            json.loads(args.result.read_text(encoding="utf-8")),
            output_schema_path=args.output_schema,
        )
        _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
