from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_unseeded_actor_discovery import stable_code, text  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


PATCH_BEGIN = "PATCH_JSONL_BEGIN"
PATCH_END = "PATCH_JSONL_END"


class ActorReviewTaskError(ValueError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise ActorReviewTaskError(f"{path}:{line_no}: expected object")
        rows.append(dict(payload))
    return rows


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    step = max(1, int(size))
    return [list(rows[index:index + step]) for index in range(0, len(rows), step)]


def prompt_for_task(task_code: str, workitems: Sequence[Mapping[str, Any]], output_jsonl: Path) -> str:
    example = {
        "candidate_code": "UAC-...",
        "review_verdict": "source_refine",
        "is_person_name": True,
        "is_same_reign_actor": True,
        "has_appointment_or_authorization_signal": True,
        "has_harm_or_failure_signal": False,
        "has_disposition_only": True,
        "recommended_action": "run_object_source_refiner",
        "evidence_window_hashes": ["UAW-..."],
        "review_note": "原文明确称其为本朝皇帝所任人物，但当前只有获罪线索，应补抓本传和同期本纪。",
    }
    return (
        "# retrieval_v3 unseeded actor review\n\n"
        "你只复核 source-driven actor discovery，不做历史评价、负向计分、factorization 或对象入库。"
        "禁止联网，禁止使用记忆或史学常识，禁止读取旧结果；只依据 workitem 的 evidence_windows。\n"
        "逐条判断 observed_name 是否确为人物名、原文是否把该人物放在目标皇帝的任用/处置语境中，以及当前窗口是实际损害还是只有处置线索。\n"
        "review_verdict 只能是 source_refine、reject_name、needs_context。"
        "source_refine 只表示值得补抓该人物本传与同朝本纪，不表示负向事实成立。\n"
        "若只有获罪、伏诛、免官、下狱而没有任内损害，has_disposition_only=true、has_harm_or_failure_signal=false。"
        "不能因为人物后来获罪就推断皇帝错任。\n"
        "recommended_action 必须与 verdict 对应：run_object_source_refiner、reject_name、needs_context。"
        "evidence_window_hashes 只能引用输入中实际存在的 window_hash。review_note 用一句中文说明依据。\n"
        f"唯一允许写入的文件是 `{output_jsonl.as_posix()}`；不要修改仓库或数据库。\n\n"
        f"task_code: {task_code}\n"
        "输出优先写入指定 JSONL，每行一个对象且每个 candidate_code 恰好一行。"
        f"若无法写文件，最终回复只能输出 {PATCH_BEGIN}/{PATCH_END} 包住的完整 JSONL。\n\n"
        f"{PATCH_BEGIN}\n{json.dumps(example, ensure_ascii=False, sort_keys=True)}\n{PATCH_END}\n\n"
        "## Workitems\n\n"
        "```json\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def write_outputs(workitems: Sequence[Mapping[str, Any]], output_root: Path, *, batch_size: int) -> dict[str, Any]:
    runtime = agent_runtime_config.resolve_agent_stage("v3_unseeded_actor_review")
    output_root.mkdir(parents=True, exist_ok=True)
    clean_rows = [dict(row) for row in workitems if text(row.get("candidate_code"))]
    tasks: list[dict[str, Any]] = []
    for batch_index, batch in enumerate(chunks(clean_rows, batch_size), start=1):
        task_code = stable_code("UAR-", [row.get("candidate_code") for row in batch])
        prompt_path = output_root / "prompts" / f"{task_code}.md"
        patch_path = output_root / "patches" / f"{task_code}.jsonl"
        last_message_path = output_root / "logs" / f"{task_code}.last.md"
        log_path = output_root / "logs" / f"{task_code}.jsonl"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task_code, batch, patch_path), encoding="utf-8", newline="\n")
        tasks.append(
            {
                "task_code": task_code,
                "task_kind": "retrieval_v3_unseeded_actor_review",
                "batch_index": batch_index,
                "workitem_codes": [text(row.get("candidate_code")) for row in batch],
                "prompt_path": str(prompt_path),
                "last_message_path": str(last_message_path),
                "log_path": str(log_path),
                "expected_outputs": [
                    {
                        "kind": "jsonl_patch",
                        "path": str(patch_path),
                        "fallback": "last_message_marked_block",
                        "begin": PATCH_BEGIN,
                        "end": PATCH_END,
                    }
                ],
                "argv": agent_runtime_config.codex_task_argv("v3_unseeded_actor_review"),
            }
        )
    tasks_path = output_root / "codex_tasks.jsonl"
    tasks_path.write_text("".join(stable_json(task) + "\n" for task in tasks), encoding="utf-8", newline="\n")
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_unseeded_actor_review_tasks.py",
        "input_workitem_count": len(workitems),
        "reviewable_workitem_count": len(clean_rows),
        "task_count": len(tasks),
        "batch_size": max(1, int(batch_size)),
        "agent_runtime": runtime,
        "tasks_jsonl": str(tasks_path),
        "write_db": False,
        "scoring_allowed": False,
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate finite unseeded-actor review tasks; no DB writes.")
    parser.add_argument("--workitems-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-size", type=int)
    args = parser.parse_args(argv)
    runtime = agent_runtime_config.resolve_agent_stage("v3_unseeded_actor_review")
    summary = write_outputs(
        read_jsonl(args.workitems_jsonl),
        args.output_root,
        batch_size=max(1, int(args.batch_size or runtime["batch_size"])),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
