from __future__ import annotations

import argparse
from collections import Counter
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


OUTPUT_SCHEMA_VERSION = "dynasty-neutral-material-atomization-output-v1"
PREPARATION_SCHEMA_VERSION = "dynasty-neutral-material-atomization-preparation-v1"
AUDIT_SCHEMA_VERSION = "dynasty-neutral-material-atomization-audit-v1"


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


def _review_inputs(settlement: Mapping[str, object]) -> list[dict[str, object]]:
    if settlement.get("status") != "accepted_shadow":
        raise ValueError("settlement 未达到 accepted_shadow")
    materials = {
        str(row.get("material_ref") or ""): row
        for row in settlement.get("materials") or ()
        if isinstance(row, Mapping)
    }
    rows = []
    for review in settlement.get("review_queue") or ():
        if not isinstance(review, Mapping) or review.get("review_reason") != (
            "mixed_chain_partial_overlap_requires_atomization"
        ):
            continue
        candidate_key = str(review.get("candidate_chain_key") or "")
        matches = [
            row
            for row in materials.values()
            if candidate_key in tuple(row.get("candidate_chain_keys") or ())
        ]
        if len(matches) != 1:
            raise ValueError("待拆分 candidate 未唯一映射 material")
        material = matches[0]
        candidate_variants = [
            row
            for row in material.get("fact_variants") or ()
            if isinstance(row, Mapping)
            and row.get("source_kind") == "candidate"
            and row.get("chain_key") == candidate_key
        ]
        if len(candidate_variants) != 1:
            raise ValueError("待拆分 candidate variant 不唯一")
        candidate = candidate_variants[0]["chain"]
        evidence = [dict(row) for row in candidate.get("evidence") or ()]
        quote_refs = [str(row.get("quote_ref") or "") for row in evidence]
        if any(not value for value in quote_refs) or len(quote_refs) != len(set(quote_refs)):
            raise ValueError("待拆分 candidate quote_ref 缺失或重复")
        baseline_keys = [str(value) for value in review.get("possible_baseline_chain_keys") or ()]
        baseline_variants = [
            row
            for row in material.get("fact_variants") or ()
            if isinstance(row, Mapping)
            and row.get("source_kind") == "baseline"
            and row.get("chain_key") in baseline_keys
        ]
        if {str(row.get("chain_key") or "") for row in baseline_variants} != set(baseline_keys):
            raise ValueError("待拆分 baseline variant 覆盖不完整")
        rows.append(
            {
                "candidate_chain_key": candidate_key,
                "candidate": candidate,
                "baseline_variants": baseline_variants,
                "allowed_actor_names": sorted(
                    str(row.get("name") or "")
                    for row in candidate.get("actors") or ()
                    if str(row.get("name") or "")
                ),
                "allowed_quote_refs": quote_refs,
                "allowed_baseline_chain_keys": baseline_keys,
            }
        )
    if not rows:
        raise ValueError("settlement 没有待原子化 mixed_chain")
    return sorted(rows, key=lambda row: str(row["candidate_chain_key"]))


def prepare_atomization(
    settlement: Mapping[str, object],
    *,
    output_root: Path,
    output_schema_path: Path,
) -> dict[str, object]:
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    rows = _review_inputs(settlement)
    fingerprint = sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16].upper()
    task_code = f"DYNGOV-ATOMIZE-{fingerprint}"
    model_rows = []
    for row in rows:
        candidate = dict(row["candidate"])
        model_rows.append(
            {
                "candidate_chain_key": row["candidate_chain_key"],
                "candidate": candidate,
                "baseline_variants": row["baseline_variants"],
                "allowed_actor_names": row["allowed_actor_names"],
                "allowed_quote_refs": row["allowed_quote_refs"],
                "allowed_baseline_chain_keys": row["allowed_baseline_chain_keys"],
            }
        )
    prompt = f"""EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS
TOOLS: FORBIDDEN
REPOSITORY_READ: FORBIDDEN
OUTPUT: JSON_ONLY

你是朝代制度史中性事实链的原子化器。INPUT 中每条 candidate 已通过逐字引文审计，但把多个可独立发生、独立归责或独立投影的事项合成了 mixed_chain。只允许依据 INPUT 拆分，不得调用工具、补充外部史实、评分或判断人才等级。

要求：
1. 每条 candidate 必须拆成至少2个 atom；每个 atom 只表达一个能够独立成立的行动—实施—结果链。仅因时间连续、同一领域或同段记载，不能合并不同税种、案件、政策或执行阶段。
2. evidence_refs 只能引用该 candidate 的 allowed_quote_refs，且全部 allowed_quote_refs 至少被一个 atom 使用。一个长引文若同时支持两个事实，可以复用；不得改写逐字引文本身。
3. actors 只能使用 allowed_actor_names。没有获准人物时保持空数组，不得把机构、皇帝称谓或推测人物新建为 actor。actor 的 evidence_refs 必须属于该 atom。
4. operation_status 不得为 mixed_chain。未知字段写空字符串或 unclear，不得用制度目的冒充 observable_result。
5. 逐 atom 比较 baseline_variants：只有确属同一事项才用 same_fact_restatement 或 same_fact_enrichment 并绑定 allowed_baseline_chain_keys；其余为 new_fact；证据不足为 uncertain。不同事项不能因同领域而绑定。
6. atom_local_key 在每条 candidate 内按 atom-1、atom-2 顺序唯一。不要输出规则、方向、分数、Episode 或人物功劳等级。

固定身份：
- schema_version: {OUTPUT_SCHEMA_VERSION}
- task_code: {task_code}

只输出严格符合传入 JSON Schema 的一个 JSON object。

INPUT
{json.dumps(model_rows, ensure_ascii=False, sort_keys=True)}
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
        "candidate_chain_keys": [str(row["candidate_chain_key"]) for row in rows],
        "allowed_quote_refs_by_candidate": {
            str(row["candidate_chain_key"]): row["allowed_quote_refs"] for row in rows
        },
        "allowed_actor_names_by_candidate": {
            str(row["candidate_chain_key"]): row["allowed_actor_names"] for row in rows
        },
        "allowed_baseline_keys_by_candidate": {
            str(row["candidate_chain_key"]): row["allowed_baseline_chain_keys"] for row in rows
        },
        "candidate_chains": {
            str(row["candidate_chain_key"]): row["candidate"] for row in rows
        },
        "output_schema_path": str(output_schema_path.resolve()),
        "historical_episode_writes": 0,
        "rule_evidence_unit_writes": 0,
        "score_writes": 0,
    }
    _atomic_json(output_root / "preparation.json", preparation)
    return preparation


def audit_atomization(
    preparation: Mapping[str, object],
    payload: Mapping[str, object],
    *,
    output_schema_path: Path,
) -> dict[str, object]:
    if preparation.get("schema_version") != PREPARATION_SCHEMA_VERSION:
        raise ValueError("atomization preparation 版本不支持")
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    validate_payload_against_schema(payload, schema)
    if payload["task_code"] != preparation["task_code"]:
        raise ValueError("atomization task_code 不匹配")
    expected = set(preparation["candidate_chain_keys"])
    actual = [str(row["candidate_chain_key"]) for row in payload["items"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("atomization candidate 覆盖不唯一")
    audited_atoms = []
    classification_counts = Counter()
    for item in payload["items"]:
        candidate_key = str(item["candidate_chain_key"])
        source_chain = preparation["candidate_chains"][candidate_key]
        evidence_by_ref = {
            str(row["quote_ref"]): row for row in source_chain["evidence"]
        }
        allowed_quotes = set(preparation["allowed_quote_refs_by_candidate"][candidate_key])
        allowed_actors = set(preparation["allowed_actor_names_by_candidate"][candidate_key])
        allowed_baselines = set(preparation["allowed_baseline_keys_by_candidate"][candidate_key])
        local_keys = [str(atom["atom_local_key"]) for atom in item["atoms"]]
        if len(local_keys) != len(set(local_keys)):
            raise ValueError("atom_local_key 重复")
        covered_quotes = set()
        for atom in item["atoms"]:
            evidence_refs = list(atom["evidence_refs"])
            if len(evidence_refs) != len(set(evidence_refs)):
                raise ValueError("atom evidence_refs 重复")
            if not set(evidence_refs) <= allowed_quotes:
                raise ValueError("atom evidence_refs 越界")
            covered_quotes.update(evidence_refs)
            actor_names = [str(row["name"]) for row in atom["actors"]]
            if len(actor_names) != len(set(actor_names)) or not set(actor_names) <= allowed_actors:
                raise ValueError("atom actor 缺失、重复或越界")
            for actor in atom["actors"]:
                actor_refs = list(actor["evidence_refs"])
                if len(actor_refs) != len(set(actor_refs)) or not set(actor_refs) <= set(evidence_refs):
                    raise ValueError("atom actor evidence_refs 越界或重复")
            baseline_keys = list(atom["baseline_chain_keys"])
            if len(baseline_keys) != len(set(baseline_keys)) or not set(baseline_keys) <= allowed_baselines:
                raise ValueError("atom baseline_chain_keys 越界或重复")
            classification = str(atom["classification"])
            if classification == "new_fact" and baseline_keys:
                raise ValueError("atom new_fact 不得绑定 baseline")
            if classification in {"same_fact_restatement", "same_fact_enrichment"} and not baseline_keys:
                raise ValueError("atom 同事实分类必须绑定 baseline")
            classification_counts[classification] += 1
            identity = json.dumps(
                [candidate_key, atom["atom_local_key"], evidence_refs, atom["action"]],
                ensure_ascii=False,
                sort_keys=True,
            )
            atom_ref = "DNATOM-" + sha256(identity.encode("utf-8")).hexdigest()[:20].upper()
            audited_atoms.append(
                {
                    "atom_ref": atom_ref,
                    "source_candidate_chain_key": candidate_key,
                    "domain": source_chain["domain"],
                    **dict(atom),
                    "evidence": [dict(evidence_by_ref[ref]) for ref in evidence_refs],
                    "episode_projection_status": "pending_person_and_window_resolution",
                }
            )
        if covered_quotes != allowed_quotes:
            raise ValueError("atomization 未覆盖 candidate 全部逐字引文")
    audited_atoms.sort(key=lambda row: str(row["atom_ref"]))
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "accepted_shadow",
        "task_code": preparation["task_code"],
        "candidate_count": len(expected),
        "atom_count": len(audited_atoms),
        "classification_counts": dict(sorted(classification_counts.items())),
        "atoms": audited_atoms,
        "limitations": payload["limitations"],
        "historical_episode_writes": 0,
        "rule_evidence_unit_writes": 0,
        "score_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="朝代制度史复合中性材料原子化")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--settlement", type=Path, required=True)
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
        report = prepare_atomization(
            json.loads(args.settlement.read_text(encoding="utf-8")),
            output_root=args.output_root,
            output_schema_path=args.output_schema,
        )
    else:
        report = audit_atomization(
            json.loads(args.preparation.read_text(encoding="utf-8")),
            json.loads(args.result.read_text(encoding="utf-8")),
            output_schema_path=args.output_schema,
        )
        _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
