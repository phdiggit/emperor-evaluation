from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import alias_script_variants, unique_strings
from scripts.dev.retrieval_v2_source_candidates import alias_entries, object_seed_name


MECHANICAL_ALIAS_GAP_TYPES = {"alias_missing"}
CLI_ALIAS_GAP_TYPES = {"weak_alias_noise"}
QUOTE_PATTERN = re.compile(r"[“\"'「『]([^”\"'」』]{1,12})[”\"'」』]")


class RetrievalV2AliasRefinerError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RetrievalV2AliasRefinerError(f"expected object JSON: {path}")
    return payload


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, pretty_json(dict(payload)))


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def iter_coverage_gaps(*payloads: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        for raw_gap in payload.get("coverage_gaps") or []:
            if isinstance(raw_gap, Mapping):
                rows.append(dict(raw_gap))
    deduped: dict[str, dict[str, Any]] = {}
    for gap in rows:
        if str(gap.get("gap_type") or "") in MECHANICAL_ALIAS_GAP_TYPES | CLI_ALIAS_GAP_TYPES:
            key = stable_fingerprint(
                [
                    gap.get("gap_type"),
                    normalize_alias(str(gap.get("object_name") or "")),
                ]
            )
        else:
            key = stable_fingerprint(
                [
                    gap.get("gap_type"),
                    gap.get("object_name"),
                    gap.get("family_code"),
                    gap.get("diagnosis"),
                    gap.get("recommended_action"),
                ]
            )
        if key not in deduped:
            deduped[key] = gap
            continue
        existing = deduped[key]
        existing["diagnosis"] = " / ".join(unique_strings([existing.get("diagnosis"), gap.get("diagnosis")]))
        existing["recommended_action"] = " / ".join(
            unique_strings([existing.get("recommended_action"), gap.get("recommended_action")])
        )
    return list(deduped.values())


def object_seed_index(task: Mapping[str, Any]) -> dict[str, int]:
    index: dict[str, int] = {}
    for pos, raw_seed in enumerate(task.get("object_seeds") or []):
        if not isinstance(raw_seed, Mapping):
            continue
        aliases = alias_entries(raw_seed)
        seed_name = object_seed_name(raw_seed)
        for value in [seed_name, *(row["alias"] for row in aliases)]:
            norm = normalize_alias(value)
            if norm:
                index.setdefault(norm, pos)
    return index


def existing_aliases(seed: Mapping[str, Any]) -> set[str]:
    values: list[Any] = [object_seed_name(seed)]
    for raw_alias in seed.get("aliases") or []:
        if isinstance(raw_alias, Mapping):
            values.append(raw_alias.get("alias") or raw_alias.get("text") or raw_alias.get("name"))
        else:
            values.append(raw_alias)
    return {normalize_alias(value) for value in values if normalize_alias(str(value or ""))}


def quoted_aliases(*texts: Any) -> list[str]:
    result: list[str] = []
    for text in texts:
        for match in QUOTE_PATTERN.finditer(str(text or "")):
            value = match.group(1).strip()
            if value:
                result.append(value)
    return unique_strings(result)


def mechanical_aliases_for_gap(gap: Mapping[str, Any]) -> list[str]:
    object_name = str(gap.get("object_name") or "").strip()
    values: list[str] = []
    if object_name:
        values.extend(alias_script_variants(object_name))
    values.extend(quoted_aliases(gap.get("diagnosis"), gap.get("recommended_action")))
    return unique_strings(values)


def classify_gap(gap: Mapping[str, Any], auto_aliases: Sequence[str]) -> str:
    gap_type = str(gap.get("gap_type") or "").strip()
    if gap_type in CLI_ALIAS_GAP_TYPES:
        return "needs_cli_alias_refiner"
    if auto_aliases and gap_type in MECHANICAL_ALIAS_GAP_TYPES:
        return "apply_aliases"
    if auto_aliases:
        return "propose_aliases"
    return "needs_cli_alias_refiner"


def build_alias_patches(task: Mapping[str, Any], *gap_payloads: Mapping[str, Any]) -> list[dict[str, Any]]:
    seeds = [seed for seed in task.get("object_seeds") or [] if isinstance(seed, Mapping)]
    seed_index = object_seed_index(task)
    patches: list[dict[str, Any]] = []
    for gap in iter_coverage_gaps(*gap_payloads):
        gap_type = str(gap.get("gap_type") or "").strip()
        if gap_type not in MECHANICAL_ALIAS_GAP_TYPES | CLI_ALIAS_GAP_TYPES:
            continue
        object_name = str(gap.get("object_name") or "").strip()
        seed_pos = seed_index.get(normalize_alias(object_name)) if object_name else None
        seed = seeds[seed_pos] if seed_pos is not None and seed_pos < len(seeds) else {}
        existing = existing_aliases(seed) if seed else set()
        auto_aliases = [
            alias
            for alias in mechanical_aliases_for_gap(gap)
            if alias and normalize_alias(alias) not in existing
        ]
        action = classify_gap(gap, auto_aliases)
        patches.append(
            {
                "patch_id": f"ALIAS-{stable_fingerprint([object_name, gap_type, gap.get('diagnosis')])[:12].upper()}",
                "object_name": object_name,
                "seed_index": seed_pos,
                "gap_type": gap_type,
                "family_code": gap.get("family_code") or "",
                "target_action": action,
                "added_aliases": [
                    {
                        "alias": alias,
                        "strength": "strong",
                        "source": "mechanical_alias_expansion",
                    }
                    for alias in auto_aliases
                ],
                "existing_aliases": sorted(existing),
                "diagnosis": gap.get("diagnosis") or "",
                "recommended_action": gap.get("recommended_action") or "",
            }
        )
    return patches


def apply_alias_patches(task: Mapping[str, Any], patches: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    updated = json.loads(stable_json(task))
    seeds = updated.setdefault("object_seeds", [])
    if not isinstance(seeds, list):
        raise RetrievalV2AliasRefinerError("task.object_seeds must be a list")

    for patch in patches:
        aliases = [row for row in patch.get("added_aliases") or [] if isinstance(row, Mapping)]
        if not aliases or str(patch.get("target_action")) not in {"apply_aliases", "propose_aliases"}:
            continue
        seed_pos = patch.get("seed_index")
        if not isinstance(seed_pos, int) or seed_pos < 0 or seed_pos >= len(seeds):
            object_name = str(patch.get("object_name") or "").strip()
            if not object_name:
                continue
            seeds.append({"name": object_name, "aliases": []})
            seed_pos = len(seeds) - 1
        seed = seeds[seed_pos]
        if not isinstance(seed, dict):
            continue
        seed_aliases = seed.setdefault("aliases", [])
        if not isinstance(seed_aliases, list):
            seed_aliases = []
            seed["aliases"] = seed_aliases
        current = existing_aliases(seed)
        for alias_row in aliases:
            alias = str(alias_row.get("alias") or "").strip()
            if not alias or normalize_alias(alias) in current:
                continue
            seed_aliases.append(
                {
                    "alias": alias,
                    "strength": str(alias_row.get("strength") or "strong"),
                    "source": str(alias_row.get("source") or "mechanical_alias_expansion"),
                }
            )
            current.add(normalize_alias(alias))

    updated["alias_refinement"] = {
        "generated_by": "scripts/dev/retrieval_v2_alias_refiner.py",
        "patch_count": len(patches),
        "applied_alias_count": sum(len(patch.get("added_aliases") or []) for patch in patches),
        "patch_fingerprint": stable_fingerprint(patches),
    }
    return updated


def build_cli_prompt(task: Mapping[str, Any], patches: Sequence[Mapping[str, Any]]) -> str:
    unresolved = [
        patch
        for patch in patches
        if patch.get("target_action") == "needs_cli_alias_refiner"
    ]
    payload = {
        "task_identity": {
            key: task.get(key)
            for key in ("job_code", "target_code", "emperor_name", "item_code", "contract_code", "rule_code")
            if key in task
        },
        "target_profile": task.get("target_profile") or {},
        "object_seeds": task.get("object_seeds") or [],
        "unresolved_alias_patches": unresolved,
    }
    return (
        "你是 emperor-evaluation retrieval_v2 alias-refiner worker。\n"
        "本轮只处理别名补强，不抽取事实，不写数据库，不修改文件。可以联网检索公开史源或权威索引来判断称谓、官职、封号、字、异体是否指向同一对象。\n"
        "禁止读取旧 source-packs、旧对象池、旧评分结果和旧判读结果。最终只输出 JSON 对象，不要 Markdown 代码块。\n"
        "输出结构：{\"alias_patches\":[{\"object_name\":\"...\",\"aliases\":[{\"alias\":\"...\",\"strength\":\"strong | medium | weak\",\"reason\":\"...\",\"confidence\":0.0}],\"source_notes\":[\"...\"]}],\"blocked\":[]}\n"
        "输入 JSON：\n"
        f"{pretty_json(payload)}"
    )


def build_refinement_payload(
    *,
    task_path: Path,
    task: Mapping[str, Any],
    candidates: Mapping[str, Any] | None,
    judge_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    gap_payloads = [payload for payload in (candidates, judge_result) if payload]
    patches = build_alias_patches(task, *gap_payloads)
    return {
        "generated_by": "scripts/dev/retrieval_v2_alias_refiner.py",
        "schema_version": 1,
        "source_task": str(task_path),
        "source_candidates": str(candidates.get("_path")) if candidates and candidates.get("_path") else None,
        "source_judge_result": str(judge_result.get("_path")) if judge_result and judge_result.get("_path") else None,
        "patches": patches,
        "stats": {
            "gap_count": sum(len(payload.get("coverage_gaps") or []) for payload in gap_payloads),
            "patch_count": len(patches),
            "apply_alias_patch_count": sum(1 for patch in patches if patch.get("target_action") == "apply_aliases"),
            "cli_alias_refiner_count": sum(1 for patch in patches if patch.get("target_action") == "needs_cli_alias_refiner"),
            "added_alias_count": sum(len(patch.get("added_aliases") or []) for patch in patches),
        },
    }


def load_optional_payload(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = load_json(path)
    payload["_path"] = str(path)
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate retrieval_v2 alias refinement patches from coverage gaps.")
    parser.add_argument("--task", type=Path, required=True, help="Clean task envelope JSON.")
    parser.add_argument("--candidates", type=Path, help="Candidate builder JSON with coverage_gaps.")
    parser.add_argument("--judge-result", type=Path, help="Judge result JSON with coverage_gaps.")
    parser.add_argument("--output-patch", type=Path, required=True, help="Alias refinement patch JSON output.")
    parser.add_argument("--output-task", type=Path, help="Optional patched task JSON output.")
    parser.add_argument("--prompt-output", type=Path, help="Optional Codex CLI alias-refiner prompt for non-mechanical gaps.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    task = load_json(args.task)
    candidates = load_optional_payload(args.candidates)
    judge_result = load_optional_payload(args.judge_result)
    payload = build_refinement_payload(
        task_path=args.task,
        task=task,
        candidates=candidates,
        judge_result=judge_result,
    )
    atomic_write_json(args.output_patch, payload)
    if args.output_task is not None:
        atomic_write_json(args.output_task, apply_alias_patches(task, payload["patches"]))
    if args.prompt_output is not None:
        atomic_write_text(args.prompt_output, build_cli_prompt(task, payload["patches"]))
    print(
        pretty_json(
            {
                "ok": True,
                "output_patch": str(args.output_patch),
                "output_task": str(args.output_task) if args.output_task else None,
                "prompt_output": str(args.prompt_output) if args.prompt_output else None,
                "stats": payload["stats"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RetrievalV2AliasRefinerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
