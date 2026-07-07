from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_factorization_worklists import scope_predicate  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v2_intake_rows import stable_json  # noqa: E402
from scripts.dev.retrieval_v2_judgment_worklists import run_codex_tasks  # noqa: E402


DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_ITEM_CODE = "I5B"
REVIEW_SCOPES = ("active-targets", "accepted-packs")
OPEN_QUEUE_STATUSES = ("ready", "needs_review")
CLAIM_PASSAGE_REVIEW_KINDS = (
    "claim_passage_mismatch",
    "claim_passage_object_mismatch",
    "claim_passage_object_only_match",
)
PATCH_BEGIN = "PATCH_JSONL_BEGIN"
PATCH_END = "PATCH_JSONL_END"


class MaterialReviewTaskError(RuntimeError):
    pass


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise MaterialReviewTaskError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def resolve_repo_path(path_text: str) -> Path:
    raw = Path(path_text)
    return raw if raw.is_absolute() else ROOT / raw


def extract_patch_rows(message: str) -> list[dict[str, Any]]:
    body = message
    if PATCH_BEGIN in message and PATCH_END in message:
        body = message.split(PATCH_BEGIN, 1)[1].split(PATCH_END, 1)[0]
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise MaterialReviewTaskError(f"patch JSONL line {line_no} is invalid: {exc}") from exc
        if not isinstance(payload, dict) or not text(payload.get("review_code")):
            raise MaterialReviewTaskError(f"patch JSONL line {line_no} must be an object with review_code")
        rows.append(payload)
    if not rows:
        raise MaterialReviewTaskError("no JSONL patch rows found in last message")
    return rows


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> Iterable[list[Mapping[str, Any]]]:
    step = max(1, size)
    for index in range(0, len(rows), step):
        yield list(rows[index:index + step])


def task_code(rows: Sequence[Mapping[str, Any]]) -> str:
    return "MRT-" + stable_hash([row.get("workitem_code") for row in rows], length=16)


def workitem_code(review_code: str) -> str:
    return "MRW-" + stable_hash(review_code, length=16)


def trimmed_passage(passage: Mapping[str, Any], *, max_chars: int = 900) -> dict[str, Any]:
    raw_text = text(passage.get("raw_text"))
    return {
        "passage_code": text(passage.get("passage_code")),
        "document_code": text(passage.get("document_code")),
        "source_title": text(passage.get("source_title")),
        "title": text(passage.get("title")),
        "locator": text(passage.get("locator")),
        "raw_text": raw_text[:max_chars],
        "raw_text_truncated": len(raw_text) > max_chars,
    }


def fetch_material_review_rows(
    cur: Any,
    *,
    item_code: str,
    scope: str,
    review_kinds: Sequence[str],
    target_names: Sequence[str],
    target_codes: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        with passage_agg as (
            select
                csp.claim_id,
                jsonb_agg(
                    jsonb_build_object(
                        'passage_code', spg.passage_code,
                        'document_code', sd.document_code,
                        'source_title', sd.source_title,
                        'title', sd.title,
                        'locator', coalesce(nullif(spg.locator, ''), sd.locator),
                        'raw_text', spg.raw_text
                    )
                    order by csp.id
                ) as source_passages
              from retrieval_v2.claim_source_passages csp
              join retrieval_v2.source_passages spg on spg.id = csp.source_passage_id
              join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
             group by csp.claim_id
        )
        select
            mrq.id as review_id,
            mrq.review_code,
            mrq.review_kind,
            mrq.queue_status::text as queue_status,
            mrq.priority,
            mrq.diagnosis,
            mrq.recommended_action,
            mrq.review_payload,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            sp.pack_code as source_pack_code,
            mc.id as claim_id,
            mc.claim_code,
            mc.raw_claim_code,
            mc.object_name,
            mc.object_type::text as object_type,
            mc.direction::text as claim_direction,
            mc.claim_summary,
            coalesce(pa.source_passages, '[]'::jsonb) as source_passages,
            (
                select count(*) from retrieval_v2.claim_rule_binding_candidates c
                 where c.claim_id = mc.id
            )::int as candidate_count,
            (
                select count(*) from retrieval_v2.claim_rule_binding_candidates c
                 where c.claim_id = mc.id and c.resolved_binding_id is not null
            )::int as resolved_candidate_count,
            (
                select count(*) from retrieval_v2.claim_rule_binding_factor_judgments j
                 where j.claim_id = mc.id and j.review_status = 'accepted'
            )::int as factor_judgment_count,
            (
                select count(*) from retrieval_v2.claim_rule_binding_material_scores ms
                 where ms.claim_id = mc.id
            )::int as material_score_count
          from retrieval_v2.material_review_queue mrq
          join retrieval_v2.material_claims mc on mc.id = mrq.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join passage_agg pa on pa.claim_id = mc.id
         where mrq.queue_status = any(%s::retrieval_v2.rv2_queue_status[])
           and mrq.review_kind = any(%s::text[])
           and (%s = '' or rt.item_code = %s)
           and {scope_predicate(scope)}
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.target_code = any(%s::text[]))
         order by mrq.priority, rt.emperor_name, mrq.id
         limit case when %s > 0 then %s else 2147483647 end
        """,
        (
            list(OPEN_QUEUE_STATUSES),
            list(review_kinds),
            item_code,
            item_code,
            list(target_names),
            list(target_names),
            list(target_codes),
            list(target_codes),
            limit,
            limit,
        ),
    )
    return [dict(row) for row in cur.fetchall()]


def review_item(row: Mapping[str, Any]) -> dict[str, Any]:
    review_payload = row.get("review_payload") if isinstance(row.get("review_payload"), Mapping) else {}
    downstream = {
        "candidate_count": int(row.get("candidate_count") or 0),
        "resolved_candidate_count": int(row.get("resolved_candidate_count") or 0),
        "factor_judgment_count": int(row.get("factor_judgment_count") or 0),
        "material_score_count": int(row.get("material_score_count") or 0),
    }
    code = workitem_code(text(row.get("review_code")))
    return {
        "workitem_code": code,
        "review_code": text(row.get("review_code")),
        "priority": int(row.get("priority") or 0),
        "review_kind": text(row.get("review_kind")),
        "queue_status": text(row.get("queue_status")),
        "subject": {
            "target_code": text(row.get("target_code")),
            "emperor_name": text(row.get("emperor_name")),
            "item_code": text(row.get("item_code")),
            "source_pack_code": text(row.get("source_pack_code")),
            "claim_id": int(row.get("claim_id") or 0),
            "claim_code": text(row.get("claim_code")),
            "raw_claim_code": text(row.get("raw_claim_code")),
            "object_name": text(row.get("object_name")),
            "object_type": text(row.get("object_type")),
            "claim_direction": text(row.get("claim_direction")),
        },
        "claim_summary": text(row.get("claim_summary")),
        "diagnosis": text(row.get("diagnosis")),
        "recommended_action": text(row.get("recommended_action")),
        "audit_issue": {
            "issue_code": text(review_payload.get("issue_code")),
            "issue_message": text(review_payload.get("issue_message")),
            "source": text(review_payload.get("source")),
        },
        "downstream": downstream,
        "source_passages": [
            trimmed_passage(passage)
            for passage in row.get("source_passages") or []
            if isinstance(passage, Mapping)
        ],
        "required_patch": {
            "review_code": text(row.get("review_code")),
            "queue_status": "",
            "review_note": "",
            "review_payload_patch": {
                "claim_passage_review": {
                    "verdict": "",
                    "basis": "",
                    "passage_codes": [],
                }
            },
        },
    }


def build_workitems(*, dsn: str, item_code: str, scope: str, review_kinds: Sequence[str], target_names: Sequence[str], target_codes: Sequence[str], limit: int) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            rows = fetch_material_review_rows(
                cur,
                item_code=item_code,
                scope=scope,
                review_kinds=review_kinds,
                target_names=target_names,
                target_codes=target_codes,
                limit=limit,
            )
    return [review_item(row) for row in rows]


def prompt_for_task(*, task: Mapping[str, Any], workitems: Sequence[Mapping[str, Any]], patch_path: Path) -> str:
    return (
        "# retrieval_v2 material review task\n\n"
        "你是消费侧材料复核子进程。禁止运行任何命令，禁止执行 git status，禁止读取任务外文件，禁止修改代码、数据库或 schema。\n"
        "只判断 claim_summary 是否被本任务给出的 source_passages 直接支撑；不要联网，不要补史料，不要重判 positive/negative，不要判断 rule 归属或因子取值。\n\n"
        f"- task_code: `{task.get('task_code', '')}`\n"
        f"- patch_path: `{repo_relative(patch_path)}`\n\n"
        "每个 workitem 必须输出一行 JSON object，字段使用 `required_patch` 模板：\n"
        "- `verdict=supported` 且 `queue_status=resolved`：passage 原文能直接支撑 summary，或者只是繁简/古今词面导致的启发式误报。\n"
        "- `verdict=unsupported` 且 `queue_status=blocked`：当前 passage 明显不支撑 summary，继续阻断自动晋升、因子化和入分。\n"
        "- `verdict=needs_context` 且 `queue_status=needs_review`：当前 passage 可能截断或上下文不足，需要抓包侧补判。\n"
        "`review_note` 必须是高信息量中文，至少说明支持或不支持的具体依据；`passage_codes` 填实际判断依据的 passage_code。\n"
        "可以尝试写入 patch_path；但无论文件写入是否成功，最终消息都必须只包含下列标记包住的完整 JSONL，不要附加解释：\n\n"
        f"{PATCH_BEGIN}\n"
        "{\"review_code\":\"...\",\"queue_status\":\"blocked\",\"review_note\":\"...\",\"review_payload_patch\":{\"claim_passage_review\":{\"verdict\":\"unsupported\",\"basis\":\"...\",\"passage_codes\":[\"...\"]}}}\n"
        f"{PATCH_END}\n\n"
        "## Workitems\n\n"
        "```json\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def build_codex_tasks(workitems: Sequence[Mapping[str, Any]], *, output_root: Path, batch_size: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for batch_index, batch in enumerate(chunks(workitems, batch_size), start=1):
        code = task_code(batch)
        prompt_path = output_root / "prompts" / f"{code}.md"
        patch_path = output_root / "patches" / f"{code}.jsonl"
        last_message_path = output_root / "logs" / f"{code}.last.md"
        log_path = output_root / "logs" / f"{code}.jsonl"
        task = {
            "task_code": code,
            "task_kind": "claim_passage_material_review",
            "batch_index": batch_index,
            "workitem_codes": [text(row.get("workitem_code")) for row in batch],
            "review_codes": [text(row.get("review_code")) for row in batch],
            "prompt_path": repo_relative(prompt_path),
            "patch_path": repo_relative(patch_path),
            "last_message_path": repo_relative(last_message_path),
            "log_path": repo_relative(log_path),
            "argv": [
                "codex",
                "exec",
                "-C",
                str(ROOT),
                "--dangerously-bypass-approvals-and-sandbox",
                "--output-last-message",
                str(last_message_path),
                "--json",
                "-",
            ],
        }
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task=task, workitems=batch, patch_path=patch_path), encoding="utf-8")
        tasks.append(task)
    return tasks


def render_markdown(*, workitems: Sequence[Mapping[str, Any]], tasks: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 material review tasks",
        "",
        f"- total_workitems: `{summary['totals']['workitems']}`",
        f"- codex_tasks: `{summary['totals']['codex_tasks']}`",
        "",
        "## Counts",
        "",
        "| kind | count |",
        "| --- | ---: |",
    ]
    for kind, count in summary["counts_by_review_kind"].items():
        lines.append(f"| `{kind}` | {count} |")
    lines.extend(["", "## Codex Tasks", "", "| task | workitems | patch |", "| --- | ---: | --- |"])
    for task in tasks:
        lines.append(f"| `{task['task_code']}` | {len(task['workitem_codes'])} | `{task['patch_path']}` |")
    if workitems:
        lines.extend(["", "## Workitems", ""])
        for item in workitems[:160]:
            subject = item.get("subject") if isinstance(item.get("subject"), Mapping) else {}
            lines.append(
                f"- `{item.get('review_code')}` `{item.get('review_kind')}` "
                f"{subject.get('emperor_name')} / {subject.get('object_name')}: {item.get('claim_summary')}"
            )
        if len(workitems) > 160:
            lines.append(f"- ... {len(workitems) - 160} more")
    return "\n".join(lines).rstrip() + "\n"


def write_worklist_outputs(*, output_root: Path, workitems: Sequence[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    tasks = build_codex_tasks(workitems, output_root=output_root, batch_size=batch_size)
    workitems_path = output_root / "material_review_workitems.jsonl"
    tasks_path = output_root / "codex_tasks.jsonl"
    summary_path = output_root / "material_review_summary.json"
    md_path = output_root / "material_review_worklist.md"
    write_jsonl(workitems_path, workitems)
    write_jsonl(tasks_path, tasks)
    kind_counts = Counter(text(row.get("review_kind")) for row in workitems)
    target_counts = Counter(text((row.get("subject") or {}).get("emperor_name")) for row in workitems)
    downstream_impacted = sum(
        1
        for row in workitems
        if any(int((row.get("downstream") or {}).get(key) or 0) for key in ("resolved_candidate_count", "factor_judgment_count", "material_score_count"))
    )
    summary = {
        "generated_by": "scripts/dev/retrieval_v2_material_review_tasks.py",
        "totals": {
            "workitems": len(workitems),
            "codex_tasks": len(tasks),
            "downstream_impacted_workitems": downstream_impacted,
        },
        "counts_by_review_kind": dict(sorted(kind_counts.items())),
        "counts_by_target": dict(sorted(target_counts.items())),
        "files": {
            "workitems": repo_relative(workitems_path),
            "codex_tasks": repo_relative(tasks_path),
            "markdown": repo_relative(md_path),
        },
    }
    write_json(summary_path, summary)
    md_path.write_text(render_markdown(workitems=workitems, tasks=tasks, summary=summary), encoding="utf-8")
    return summary


def collect_patch_outputs(*, tasks_jsonl: Path, output_json: Path | None, overwrite: bool) -> dict[str, Any]:
    tasks = read_jsonl(tasks_jsonl)
    rows_collected = 0
    files_written = 0
    files_existing = 0
    failures: list[dict[str, str]] = []
    details: list[dict[str, Any]] = []
    for task in tasks:
        task_code_text = text(task.get("task_code"))
        patch_path = resolve_repo_path(text(task.get("patch_path")))
        last_message_path = resolve_repo_path(text(task.get("last_message_path")))
        if patch_path.exists() and not overwrite:
            files_existing += 1
            details.append({"task_code": task_code_text, "status": "existing", "patch_path": repo_relative(patch_path)})
            continue
        if not last_message_path.exists():
            failures.append({"task_code": task_code_text, "reason": "last_message_missing", "path": repo_relative(last_message_path)})
            continue
        try:
            rows = extract_patch_rows(last_message_path.read_text(encoding="utf-8"))
        except MaterialReviewTaskError as exc:
            failures.append({"task_code": task_code_text, "reason": str(exc), "path": repo_relative(last_message_path)})
            continue
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")
        rows_collected += len(rows)
        files_written += 1
        details.append(
            {
                "task_code": task_code_text,
                "status": "written",
                "rows": len(rows),
                "patch_path": repo_relative(patch_path),
            }
        )
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_material_review_tasks.py",
        "command": "collect-patches",
        "ok": not failures,
        "totals": {
            "tasks": len(tasks),
            "files_written": files_written,
            "files_existing": files_existing,
            "rows_collected": rows_collected,
            "failures": len(failures),
        },
        "failures": failures,
        "details": details,
    }
    if output_json is not None:
        write_json(output_json, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Codex review tasks for retrieval_v2 material_review_queue claim/passage issues.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worklist = subparsers.add_parser("worklist", help="Build DB-backed material review workitems and Codex task prompts.")
    worklist.add_argument("--env-file", type=Path)
    worklist.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    worklist.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    worklist.add_argument("--scope", choices=REVIEW_SCOPES, default="accepted-packs")
    worklist.add_argument("--review-kind", action="append", choices=CLAIM_PASSAGE_REVIEW_KINDS, default=[])
    worklist.add_argument("--target-name", action="append", default=[])
    worklist.add_argument("--target-code", action="append", default=[])
    worklist.add_argument("--limit", type=int, default=0)
    worklist.add_argument("--batch-size", type=int, default=8)
    worklist.add_argument("--output-root", type=Path, required=True)

    run_plan = subparsers.add_parser("run-plan", help="Run or start Codex CLI tasks from codex_tasks.jsonl.")
    run_plan.add_argument("--tasks-jsonl", type=Path, required=True)
    run_plan.add_argument("--execute", action="store_true")
    run_plan.add_argument("--background", action="store_true")
    run_plan.add_argument("--limit", type=int, default=0)
    run_plan.add_argument("--output", type=Path)
    run_plan.add_argument("--agent-output-root", type=Path)
    run_plan.add_argument("--codex-win-bin", default="codex-win")
    run_plan.add_argument("--max-workers", type=int, default=4)
    run_plan.add_argument("--timeout-seconds", type=int, default=1800)
    run_plan.add_argument("--sandbox-profile", choices=("read-only", "local-write", "bypass"), default="local-write")
    run_plan.add_argument("--respect-task-argv", action="store_true")
    run_plan.add_argument("--search", action="store_true")

    collect = subparsers.add_parser("collect-patches", help="Collect JSONL patch rows from Codex last-message files.")
    collect.add_argument("--tasks-jsonl", type=Path, required=True)
    collect.add_argument("--output-json", type=Path)
    collect.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "worklist":
        load_env_file(args.env_file)
        dsn = resolve_dsn(args.dsn_env)
        workitems = build_workitems(
            dsn=dsn,
            item_code=args.item_code,
            scope=args.scope,
            review_kinds=args.review_kind or CLAIM_PASSAGE_REVIEW_KINDS,
            target_names=args.target_name,
            target_codes=args.target_code,
            limit=max(0, args.limit),
        )
        summary = write_worklist_outputs(output_root=args.output_root, workitems=workitems, batch_size=args.batch_size)
        print(json.dumps({"output_root": str(args.output_root), "totals": summary["totals"], "counts_by_target": summary["counts_by_target"]}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "run-plan":
        payload = run_codex_tasks(
            tasks_path=args.tasks_jsonl,
            execute=args.execute,
            background=args.background,
            limit=max(0, args.limit),
            output=args.output,
            agent_output_root=args.agent_output_root,
            codex_win_bin=args.codex_win_bin,
            max_workers=args.max_workers,
            timeout_seconds=args.timeout_seconds,
            sandbox_profile=args.sandbox_profile,
            respect_task_argv=args.respect_task_argv,
            search=args.search,
        )
        return 0 if payload["returncode"] == 0 and payload["totals"].get("failed", 0) == 0 else 1
    if args.command == "collect-patches":
        payload = collect_patch_outputs(tasks_jsonl=args.tasks_jsonl, output_json=args.output_json, overwrite=args.overwrite)
        print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ok"] else 1
    raise MaterialReviewTaskError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
