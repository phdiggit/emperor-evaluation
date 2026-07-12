from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_candidate_review_worklist import PATCH_BEGIN, PATCH_END, stable_json, text  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


class ContextReviewTaskError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise ContextReviewTaskError(f"{path}:{line_no}: expected object")
        rows.append(dict(payload))
    return rows


def reviewable(item: Mapping[str, Any]) -> bool:
    return text(item.get("next_action")) == "context_review"


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    size = max(1, size)
    return [list(rows[index:index + size]) for index in range(0, len(rows), size)]


def prompt_for_task(task_code: str, workitems: Sequence[Mapping[str, Any]]) -> str:
    return (
        "# retrieval_v3 needs_context review\n\n"
        "只依据每条 workitem 给出的 current_source_passages 与 context_passages 复核 appointment_delegation。"
        "禁止联网、禁止写库、禁止改代码、禁止使用史学常识补齐事实。\n"
        "context_passages 只是同一 source document 的候选补充段落，必须逐条引用 evidence_passage_codes。\n"
        "如果补充段落已补齐任用/授权、具名对象、职责，且 result/feedback 或 continuity/reuse 至少一项成立，可改为 accepted_candidate；"
        "否则在 supporting_only、rejected、needs_context 中选择。只有仍需定向 source-pack 补抓时才保留 needs_context。\n"
        "identity_gate 只能原样复述输入值；不得因为身份状态直接否定材料事实。\n"
        "candidate_role 只能用既有有限枚举或空字符串；direction 只能是 positive 或 negative。\n\n"
        f"task_code: {task_code}\n"
        "输出只能是 PATCH_JSONL_BEGIN/END 包住的 JSONL；每行对应一个 review_code。\n\n"
        f"{PATCH_BEGIN}\n"
        + json.dumps(
            {
                "review_code": "CRW-...",
                "review_verdict": "accepted_candidate",
                "review_note": "",
                "required_facts": {
                    "has_appointment_or_authorization": True,
                    "has_named_actor": True,
                    "has_task_or_responsibility": True,
                    "has_result_or_feedback": False,
                    "has_continuity_or_reuse": True,
                },
                "candidate_role": "",
                "direction": "positive",
                "scoring_candidate": True,
                "usable_for_scoring_cluster": True,
                "identity_gate": "identity_pending",
                "evidence_passage_codes": ["PAS-..."],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + f"\n{PATCH_END}\n\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
    )


def write_outputs(workitems: Sequence[Mapping[str, Any]], output_root: Path, *, batch_size: int) -> dict[str, Any]:
    runtime = agent_runtime_config.resolve_agent_stage("v3_context_review")
    output_root.mkdir(parents=True, exist_ok=True)
    eligible = [dict(item) for item in workitems if reviewable(item)]
    deferred = [dict(item) for item in workitems if not reviewable(item)]
    tasks = []
    for batch_index, batch in enumerate(chunks(eligible, batch_size), start=1):
        task_code = "CTX-" + hashlib.sha256(stable_json([item.get("review_code") for item in batch]).encode("utf-8")).hexdigest()[:16].upper()
        prompt_path = output_root / "prompts" / f"{task_code}.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task_code, batch), encoding="utf-8")
        tasks.append({
            "task_code": task_code,
            "task_kind": "retrieval_v3_needs_context_review",
            "batch_index": batch_index,
            "workitem_codes": [text(item.get("workitem_code")) for item in batch],
            "prompt_path": str(prompt_path),
            "patch_path": str(output_root / "patches" / f"{task_code}.jsonl"),
            "last_message_path": str(output_root / "logs" / f"{task_code}.last.md"),
            "log_path": str(output_root / "logs" / f"{task_code}.jsonl"),
            "argv": agent_runtime_config.codex_task_argv("v3_context_review"),
        })
    (output_root / "context_review_workitems.jsonl").write_text(
        "".join(stable_json(item) + "\n" for item in eligible), encoding="utf-8"
    )
    (output_root / "deferred_source_fetch_workitems.jsonl").write_text(
        "".join(stable_json(item) + "\n" for item in deferred), encoding="utf-8"
    )
    (output_root / "codex_tasks.jsonl").write_text(
        "".join(stable_json(task) + "\n" for task in tasks), encoding="utf-8"
    )
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_context_review_tasks.py",
        "input_needs_context_count": len(workitems),
        "context_review_candidate_count": len(eligible),
        "deferred_source_fetch_count": len(deferred),
        "task_count": len(tasks),
        "batch_size": batch_size,
        "agent_runtime": runtime,
        "legacy_data_reads": False,
        "write_db": False,
    }
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate narrow second-review Codex tasks from v3 needs_context workitems.")
    parser.add_argument("--workitems-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-size", type=int)
    args = parser.parse_args(argv)
    runtime = agent_runtime_config.resolve_agent_stage("v3_context_review")
    summary = write_outputs(
        read_jsonl(args.workitems_jsonl),
        args.output_root,
        batch_size=max(1, int(args.batch_size or runtime["batch_size"])),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
