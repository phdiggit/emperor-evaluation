from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_unseeded_actor_discovery import stable_code, text  # noqa: E402
from scripts.dev.retrieval_v3_unseeded_actor_review_tasks import PATCH_BEGIN, PATCH_END, read_jsonl, stable_json  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


class NegativeChainTaskError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise NegativeChainTaskError(f"{path}: expected object")
    return dict(payload)


def claim_refs(claim: Mapping[str, Any]) -> list[str]:
    return [text(value) for value in claim.get("source_slice_refs") or [] if text(value)]


def build_chain_workitems(
    actor_rows: Sequence[Mapping[str, Any]],
    claim_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    claims_by_actor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claim_payload.get("claims") or []:
        if isinstance(claim, Mapping) and text(claim.get("object_name")):
            claims_by_actor[text(claim.get("object_name"))].append(dict(claim))

    rejected_by_actor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_gate = claim_payload.get("_target_emperor_gate") if isinstance(claim_payload.get("_target_emperor_gate"), Mapping) else {}
    for rejection in target_gate.get("rejected_claims") or []:
        if not isinstance(rejection, Mapping) or not isinstance(rejection.get("claim"), Mapping):
            continue
        claim = dict(rejection["claim"])
        actor = text(claim.get("object_name"))
        if actor:
            rejected_by_actor[actor].append({**dict(rejection), "claim": claim})

    passages = {
        text(row.get("slice_code")): dict(row)
        for row in claim_payload.get("passages") or []
        if isinstance(row, Mapping) and text(row.get("slice_code"))
    }
    workitems: list[dict[str, Any]] = []
    for actor_row in actor_rows:
        actor = text(actor_row.get("name") or actor_row.get("observed_name"))
        if not actor:
            continue
        accepted = claims_by_actor.get(actor, [])
        rejected = rejected_by_actor.get(actor, [])
        refs = list(dict.fromkeys(
            ref
            for claim in [*accepted, *(row["claim"] for row in rejected)]
            for ref in claim_refs(claim)
        ))
        evidence = [passages[ref] for ref in refs if ref in passages]
        target_emperors = [text(value) for value in actor_row.get("target_emperors") or [] if text(value)]
        workitems.append(
            {
                "workitem_code": stable_code("UANCW-", actor_row.get("discovery_candidate_code"), actor),
                "discovery_candidate_code": actor_row.get("discovery_candidate_code"),
                "target_emperor": target_emperors[0] if len(target_emperors) == 1 else "",
                "actor_name": actor,
                "accepted_claims": accepted,
                "cross_target_rejections": rejected,
                "source_slices": evidence,
                "allowed_claim_codes": [text(row.get("claim_code")) for row in accepted if text(row.get("claim_code"))],
                "allowed_cross_target_claim_codes": [
                    text(row["claim"].get("claim_code")) for row in rejected if text(row["claim"].get("claim_code"))
                ],
                "allowed_source_slice_refs": refs,
                "discovery_evidence": actor_row.get("discovery_evidence") or [],
                "required_chain": actor_row.get("required_chain") or {},
                "write_db": False,
                "scoring_allowed": False,
            }
        )
    return workitems


def prompt_for_task(task_code: str, workitems: Sequence[Mapping[str, Any]], output_jsonl: Path) -> str:
    example = {
        "actor_name": "示例人物",
        "target_emperor": "示例皇帝",
        "review_verdict": "needs_source_refine",
        "has_appointment_or_authorization": False,
        "has_task_or_responsibility": True,
        "has_same_chain_harm_or_failure": True,
        "has_disposition_only": False,
        "appointment_claim_codes": [],
        "harm_claim_codes": ["CLM-..."],
        "supporting_claim_codes": [],
        "source_slice_refs": ["OSS-..."],
        "recommended_action": "run_object_source_refiner",
        "review_note": "已有任内损害线索，但缺少目标皇帝任用或授权的直接链条。",
    }
    return (
        "# retrieval_v3 unseeded actor negative-chain review\n\n"
        "你只审查目标皇帝 appointment_delegation 的负向事实链，不做因子赋值、binding、计分或数据库写入。"
        "禁止联网、禁止使用记忆或史学常识，只能使用 workitem 中的 claims、source_slices 和 discovery_evidence。\n"
        "每个 actor_name 恰好输出一行。review_verdict 只能是 negative_chain_ready、supporting_only、"
        "disposition_only、needs_source_refine、source_identity_mismatch。\n"
        "negative_chain_ready 必须同时有：目标皇帝对该人物的任用/授权、明确职责或任务、同一任用链上的实际损害或失败；"
        "后来获罪、免官、贬谪、赐死本身不能当作损害。不同皇帝、不同同名人物的事实不得串链。\n"
        "appointment_claim_codes 可以为空，但仅限 discovery_evidence 已直接给出目标皇帝任用/授权；这种情况仍选 negative_chain_ready，"
        "后续由 consumer 标记 claim_refinement_required，禁止直接 binding。\n"
        "若材料只有处置而没有任内损害，选 disposition_only；若有损害但缺任用/授权闭环，选 needs_source_refine；"
        "若检索命中显式属于其他皇帝的同名人物，选 source_identity_mismatch。\n"
        "recommended_action 必须对应：emit_negative_candidate、retain_supporting_only、retain_disposition_only、"
        "run_object_source_refiner、refine_identity_specific_sources。所有 claim_code 和 source_slice_ref 必须来自该 workitem 的允许列表。\n"
        f"唯一允许写入 `{output_jsonl.as_posix()}`；不要修改仓库或数据库。task_code: {task_code}\n"
        f"若无法写文件，最终回复只能输出 {PATCH_BEGIN}/{PATCH_END} 包住的完整 JSONL。\n\n"
        f"{PATCH_BEGIN}\n{json.dumps(example, ensure_ascii=False, sort_keys=True)}\n{PATCH_END}\n\n"
        "## Workitems\n\n```json\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def write_outputs(workitems: Sequence[Mapping[str, Any]], output_root: Path, *, batch_size: int) -> dict[str, Any]:
    runtime = agent_runtime_config.resolve_agent_stage("v3_negative_chain_review")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "workitems.jsonl").write_text(
        "".join(stable_json(dict(row)) + "\n" for row in workitems), encoding="utf-8", newline="\n"
    )
    tasks: list[dict[str, Any]] = []
    step = max(1, int(batch_size))
    for index in range(0, len(workitems), step):
        batch = list(workitems[index:index + step])
        task_code = stable_code("UANCR-", [row.get("workitem_code") for row in batch])
        prompt_path = output_root / "prompts" / f"{task_code}.md"
        patch_path = output_root / "patches" / f"{task_code}.jsonl"
        last_path = output_root / "logs" / f"{task_code}.last.md"
        event_path = output_root / "logs" / f"{task_code}.jsonl"
        for path in (prompt_path, patch_path, last_path, event_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task_code, batch, patch_path), encoding="utf-8", newline="\n")
        tasks.append(
            {
                "task_code": task_code,
                "task_kind": "retrieval_v3_unseeded_actor_negative_chain_review",
                "prompt_path": str(prompt_path),
                "last_message_path": str(last_path),
                "log_path": str(event_path),
                "expected_outputs": [{
                    "kind": "jsonl_patch",
                    "path": str(patch_path),
                    "fallback": "last_message_marked_block",
                    "begin": PATCH_BEGIN,
                    "end": PATCH_END,
                }],
                "argv": agent_runtime_config.codex_task_argv("v3_negative_chain_review"),
            }
        )
    tasks_path = output_root / "codex_tasks.jsonl"
    tasks_path.write_text("".join(stable_json(row) + "\n" for row in tasks), encoding="utf-8", newline="\n")
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_unseeded_actor_negative_chain_tasks.py",
        "workitem_count": len(workitems),
        "task_count": len(tasks),
        "model": runtime["model"],
        "reasoning_effort": runtime["reasoning_effort"],
        "agent_runtime": runtime,
        "write_db": False,
        "scoring_allowed": False,
        "tasks_jsonl": str(tasks_path),
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate finite Luna tasks for unseeded-actor negative-chain review.")
    parser.add_argument("--actor-workitems-jsonl", type=Path, required=True)
    parser.add_argument("--claim-result-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-size", type=int)
    args = parser.parse_args(argv)
    workitems = build_chain_workitems(read_jsonl(args.actor_workitems_jsonl), read_json(args.claim_result_json))
    runtime = agent_runtime_config.resolve_agent_stage("v3_negative_chain_review")
    summary = write_outputs(workitems, args.output_root, batch_size=int(args.batch_size or runtime["batch_size"]))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
