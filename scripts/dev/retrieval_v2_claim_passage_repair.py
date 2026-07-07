from __future__ import annotations

import argparse
import hashlib
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
from scripts.dev.retrieval_v2_import_plan import json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v2_intake_rows import stable_json  # noqa: E402
from scripts.dev.retrieval_v2_judgment_worklists import run_codex_tasks  # noqa: E402
from scripts.dev.retrieval_v2_material_review_tasks import PATCH_BEGIN, PATCH_END, extract_patch_rows  # noqa: E402

DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_ITEM_CODE = "I5B"
DEFAULT_REVIEW_KINDS = (
    "claim_passage_mismatch",
    "claim_passage_object_mismatch",
    "claim_passage_object_only_match",
)
DEFAULT_QUEUE_STATUSES = ("blocked", "needs_review")
REPAIR_ACTIONS = {"relink", "rewrite", "drop_claim", "block_claim", "needs_source_refine"}
PATCH_QUEUE_STATUSES = {"resolved", "blocked", "needs_review"}
DISPOSITION_NEGATIVE_TERMS = (
    "伏诛", "被诛", "诛族", "被废", "废为", "撤", "罢", "免", "削职",
    "处斩", "坐谴", "谋反", "反叛", "被杀", "杀死", "诛杀", "赐死", "圈禁",
)
class ClaimPassageRepairError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict): raise ClaimPassageRepairError(f"{path}: expected JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict): raise ClaimPassageRepairError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")


def resolve_repo_path(path_text: str) -> Path:
    raw = Path(path_text)
    return raw if raw.is_absolute() else ROOT / raw


def trimmed(value: Any, *, max_chars: int) -> str:
    raw = text(value)
    return raw if len(raw) <= max_chars else raw[: max_chars - 1] + "..."


def cjk_chars(value: str) -> set[str]:
    return {char for char in value if "\u4e00" <= char <= "\u9fff"}


def quote_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def fetch_repair_rows(cur: Any, *, item_code: str, scope: str, review_kinds: Sequence[str], queue_statuses: Sequence[str], target_names: Sequence[str], target_codes: Sequence[str], limit: int) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        with passage_agg as (
            select
                csp.claim_id,
                jsonb_agg(
                    jsonb_build_object(
                        'passage_id', spg.id,
                        'passage_code', spg.passage_code,
                        'raw_passage_code', spg.raw_passage_code,
                        'document_code', sd.document_code,
                        'raw_document_code', sd.raw_document_code,
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
        ),
        artifact_agg as (
            select
                source_pack_id,
                jsonb_object_agg(artifact_kind, artifact_path) as artifacts
              from retrieval_v2.source_pack_artifacts
             group by source_pack_id
        )
        select
            mrq.id as review_id,
            mrq.review_code,
            mrq.review_kind,
            mrq.queue_status::text as queue_status,
            mrq.review_note,
            mrq.review_payload,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            sp.id as source_pack_id,
            sp.pack_code as source_pack_code,
            sp.pack_root,
            coalesce(aa.artifacts, '{{}}'::jsonb) as artifacts,
            mc.id as claim_id,
            mc.claim_code,
            mc.raw_claim_code,
            mc.object_name,
            mc.object_type::text as object_type,
            mc.direction::text as claim_direction,
            mc.claim_summary,
            mc.claim_payload,
            coalesce(pa.source_passages, '[]'::jsonb) as source_passages
          from retrieval_v2.material_review_queue mrq
          join retrieval_v2.material_claims mc on mc.id = mrq.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join passage_agg pa on pa.claim_id = mc.id
          left join artifact_agg aa on aa.source_pack_id = sp.id
         where mrq.review_kind = any(%s::text[])
           and mrq.queue_status = any(%s::retrieval_v2.rv2_queue_status[])
           and (%s = '' or rt.item_code = %s)
           and {scope_predicate(scope)}
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.target_code = any(%s::text[]))
         order by rt.emperor_name, mrq.priority, mrq.id
         limit case when %s > 0 then %s else 2147483647 end
        """,
        (
            list(review_kinds),
            list(queue_statuses),
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


def load_candidate_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    for path in candidate_payload_paths(row):
        if path.exists():
            return read_json(path)
    return {}


def candidate_payload_paths(row: Mapping[str, Any]) -> list[Path]:
    artifacts = row.get("artifacts") if isinstance(row.get("artifacts"), Mapping) else {}
    candidates_path = text(artifacts.get("candidates"))
    paths: list[Path] = []
    if not candidates_path:
        paths = []
    else:
        paths.append(resolve_repo_path(candidates_path))
    target_code = text(row.get("target_code"))
    if target_code:
        run_root = ROOT / "tmp" / "retrieval_v2_clean_runs"
        pattern = f"*/{target_code}_appointment_delegation/candidates.final.json"
        fallback_paths = sorted(run_root.glob(pattern), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        paths.extend(path for path in fallback_paths if path not in paths)
    return paths


def candidate_slice_score(claim: Mapping[str, Any], candidate_slice: Mapping[str, Any], preferred_slice_refs: set[str]) -> int:
    slice_code = text(candidate_slice.get("slice_code"))
    object_name = text(claim.get("object_name"))
    summary = text(claim.get("claim_summary"))
    slice_text = text(candidate_slice.get("text"))
    score = 0
    if slice_code in preferred_slice_refs:
        score += 500
    if object_name and object_name == text(candidate_slice.get("object_name")):
        score += 160
    if object_name and object_name in slice_text:
        score += 120
    matched_aliases = {text(value) for value in candidate_slice.get("matched_aliases") or [] if text(value)}
    if object_name and object_name in matched_aliases:
        score += 80
    score += min(120, len(cjk_chars(summary) & cjk_chars(slice_text)) * 3)
    score += min(40, int(candidate_slice.get("score") or 0) // 3)
    return score


def select_candidate_slices(row: Mapping[str, Any], candidates: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    claim_payload = row.get("claim_payload") if isinstance(row.get("claim_payload"), Mapping) else {}
    preferred = {text(value) for value in claim_payload.get("source_slice_refs") or [] if text(value)}
    scored: list[tuple[int, str, Mapping[str, Any]]] = []
    for candidate in candidates.get("candidate_slices") or []:
        if not isinstance(candidate, Mapping):
            continue
        score = candidate_slice_score(row, candidate, preferred)
        if score <= 0:
            continue
        scored.append((score, text(candidate.get("slice_code")), candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected: list[dict[str, Any]] = []
    for score, _slice_code, candidate in scored[: max(1, limit)]:
        selected.append(
            {
                "slice_code": text(candidate.get("slice_code")),
                "document_code": text(candidate.get("document_code")),
                "locator": text(candidate.get("locator")),
                "object_name": text(candidate.get("object_name")),
                "score": score,
                "raw_candidate_score": candidate.get("score"),
                "matched_aliases": [text(value) for value in candidate.get("matched_aliases") or [] if text(value)],
                "text": trimmed(candidate.get("text"), max_chars=1800),
            }
        )
    return selected


def repair_workitem(row: Mapping[str, Any], *, candidate_limit: int) -> dict[str, Any]:
    candidates = load_candidate_payload(row)
    claim_payload = row.get("claim_payload") if isinstance(row.get("claim_payload"), Mapping) else {}
    return {
        "review_code": text(row.get("review_code")),
        "review_kind": text(row.get("review_kind")),
        "queue_status": text(row.get("queue_status")),
        "subject": {
            "target_code": text(row.get("target_code")),
            "emperor_name": text(row.get("emperor_name")),
            "item_code": text(row.get("item_code")),
            "source_pack_id": int(row.get("source_pack_id") or 0),
            "source_pack_code": text(row.get("source_pack_code")),
            "claim_id": int(row.get("claim_id") or 0),
            "claim_code": text(row.get("claim_code")),
            "raw_claim_code": text(row.get("raw_claim_code")),
            "object_name": text(row.get("object_name")),
            "object_type": text(row.get("object_type")),
            "claim_direction": text(row.get("claim_direction")),
        },
        "claim_summary": text(row.get("claim_summary")),
        "claim_source_slice_refs": [text(value) for value in claim_payload.get("source_slice_refs") or [] if text(value)],
        "claim_source_passage_refs": [text(value) for value in claim_payload.get("source_passage_refs") or [] if text(value)],
        "current_source_passages": [
            {
                "passage_code": text(passage.get("passage_code")),
                "raw_passage_code": text(passage.get("raw_passage_code")),
                "document_code": text(passage.get("document_code")),
                "raw_document_code": text(passage.get("raw_document_code")),
                "source_title": text(passage.get("source_title")),
                "title": text(passage.get("title")),
                "locator": text(passage.get("locator")),
                "raw_text": trimmed(passage.get("raw_text"), max_chars=900),
            }
            for passage in row.get("source_passages") or []
            if isinstance(passage, Mapping)
        ],
        "candidate_slices": select_candidate_slices(row, candidates, limit=candidate_limit),
        "required_patch": {
            "review_code": text(row.get("review_code")),
            "repair_action": "",
            "queue_status": "",
            "review_note": "",
            "claim_summary": "",
            "source_slice_codes": [],
            "claim_payload_patch": {},
        },
    }


def build_workitems(*, dsn: str, item_code: str, scope: str, review_kinds: Sequence[str], queue_statuses: Sequence[str], target_names: Sequence[str], target_codes: Sequence[str], limit: int, candidate_limit: int) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            rows = fetch_repair_rows(
                cur,
                item_code=item_code,
                scope=scope,
                review_kinds=review_kinds,
                queue_statuses=queue_statuses,
                target_names=target_names,
                target_codes=target_codes,
                limit=limit,
            )
    return [repair_workitem(row, candidate_limit=candidate_limit) for row in rows]


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> Iterable[list[Mapping[str, Any]]]:
    step = max(1, size)
    for index in range(0, len(rows), step):
        yield list(rows[index:index + step])


def task_code(rows: Sequence[Mapping[str, Any]]) -> str:
    return "CPR-" + stable_hash([row.get("review_code") for row in rows], length=16)


def prompt_for_task(*, task: Mapping[str, Any], workitems: Sequence[Mapping[str, Any]], patch_path: Path) -> str:
    return (
        "# retrieval_v2 claim/passage repair task\n\n"
        "你是抓包侧修包子进程。禁止联网，禁止修改代码或数据库，禁止读取任务外文件。\n"
        "任务是修复 claim_summary 与 source passage 错位：优先在 candidate_slices 里找能直接支撑 claim 的原文；找不到时再判断是否改写 claim 或废弃 claim。\n\n"
        "重要原则：伏诛、被废、被杀、撤权等处置性材料，不能单凭处置结果定为 negative appointment_delegation；除非材料本身同时证明任用授权安排造成了具体治理或人才结构损害，否则标为 `needs_source_refine` 或 `drop_claim`，交消费侧结合人物画像判断。\n\n"
        f"- task_code: `{task.get('task_code', '')}`\n"
        f"- patch_path: `{repo_relative(patch_path)}`\n\n"
        "每个 workitem 输出一行 JSON object，字段使用 `required_patch` 模板：\n"
        "- `repair_action=relink`, `queue_status=resolved`: 原 claim_summary 可被一个或多个 candidate_slices 直接支撑，`source_slice_codes` 填所选 slice。\n"
        "- `repair_action=rewrite`, `queue_status=resolved`: 原 summary 过宽，但可改写为 candidate_slices 直接支撑的原子 claim；必须填写新的 `claim_summary` 和 `source_slice_codes`。\n"
        "- `repair_action=drop_claim`, `queue_status=blocked`: 这个 claim 在给定上下文中不成立或只靠错位 passage 支撑。\n"
        "- `repair_action=block_claim`, `queue_status=blocked`: 史料有效但不应作为当前 appointment_delegation claim 自动消费；保留 claim 本体，只关闭本复核项。\n"
        "- `repair_action=needs_source_refine`, `queue_status=needs_review`: 同包候选不足，需要重新补源、补上下文或重判。\n"
        "`review_note` 必须用中文说明选择依据；不要判断因子，不要给分，不要做跨 rule 晋升。\n"
        "可以尝试写入 patch_path；最终消息必须只包含下列标记包住的完整 JSONL，不要附加解释：\n\n"
        f"{PATCH_BEGIN}\n"
        "{\"review_code\":\"...\",\"repair_action\":\"relink\",\"queue_status\":\"resolved\",\"review_note\":\"...\",\"claim_summary\":\"\",\"source_slice_codes\":[\"SLI-...\"],\"claim_payload_patch\":{}}\n"
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
            "task_kind": "claim_passage_repair",
            "batch_index": batch_index,
            "review_codes": [text(row.get("review_code")) for row in batch],
            "prompt_path": repo_relative(prompt_path),
            "patch_path": repo_relative(patch_path),
            "last_message_path": repo_relative(last_message_path),
            "log_path": repo_relative(log_path),
        }
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task=task, workitems=batch, patch_path=patch_path), encoding="utf-8")
        tasks.append(task)
    return tasks


def write_worklist_outputs(*, output_root: Path, workitems: Sequence[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    tasks = build_codex_tasks(workitems, output_root=output_root, batch_size=batch_size)
    workitems_path = output_root / "claim_passage_repair_workitems.jsonl"
    tasks_path = output_root / "codex_tasks.jsonl"
    summary_path = output_root / "claim_passage_repair_summary.json"
    write_jsonl(workitems_path, workitems)
    write_jsonl(tasks_path, tasks)
    summary = {
        "generated_by": "scripts/dev/retrieval_v2_claim_passage_repair.py",
        "totals": {"workitems": len(workitems), "codex_tasks": len(tasks)},
        "counts_by_target": dict(sorted(Counter(text((row.get("subject") or {}).get("emperor_name")) for row in workitems).items())),
        "counts_by_status": dict(sorted(Counter(text(row.get("queue_status")) for row in workitems).items())),
        "files": {
            "workitems": repo_relative(workitems_path),
            "codex_tasks": repo_relative(tasks_path),
            "summary": repo_relative(summary_path),
        },
    }
    write_json(summary_path, summary)
    return summary


def collect_patch_outputs(*, tasks_jsonl: Path, output_json: Path | None, overwrite: bool) -> dict[str, Any]:
    tasks = read_jsonl(tasks_jsonl)
    failures: list[dict[str, str]] = []
    rows_collected = 0
    files_written = 0
    files_existing = 0
    for task in tasks:
        patch_path = resolve_repo_path(text(task.get("patch_path")))
        last_message_path = resolve_repo_path(text(task.get("last_message_path")))
        if patch_path.exists() and not overwrite:
            files_existing += 1
            continue
        if not last_message_path.exists():
            failures.append({"task_code": text(task.get("task_code")), "reason": "last_message_missing"})
            continue
        try:
            rows = extract_patch_rows(last_message_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - surface task parse failures in JSON report.
            failures.append({"task_code": text(task.get("task_code")), "reason": str(exc)})
            continue
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")
        rows_collected += len(rows)
        files_written += 1
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_claim_passage_repair.py",
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
    }
    if output_json is not None:
        write_json(output_json, payload)
    return payload


def auto_patch_for_workitem(row: Mapping[str, Any], *, min_overlap: int = 14) -> tuple[dict[str, Any] | None, str]:
    subject = row.get("subject") if isinstance(row.get("subject"), Mapping) else {}
    refs = [text(value) for value in row.get("claim_source_slice_refs") or [] if text(value)]
    if not refs:
        return None, "missing_source_slice_refs"
    by_slice = slice_map_for_workitem(row)
    if any(ref not in by_slice for ref in refs):
        return None, "source_slice_ref_not_in_candidates"
    summary = text(row.get("claim_summary"))
    if text(subject.get("claim_direction")) == "negative" and any(term in summary for term in DISPOSITION_NEGATIVE_TERMS):
        return None, "disposition_negative_needs_review"
    candidate_text = " ".join(text(by_slice[ref].get("text")) for ref in refs)
    object_name = text(subject.get("object_name"))
    overlap = len(cjk_chars(summary) & cjk_chars(candidate_text))
    if object_name not in candidate_text and overlap < min_overlap:
        return None, "weak_text_overlap"
    return (
        {
            "review_code": text(row.get("review_code")),
            "repair_action": "relink",
            "queue_status": "resolved",
            "review_note": (
                "机械高置信重链：原 claim 的 source_slice_refs 均在当前 candidates 中找到，"
                "候选片段与 claim 摘要有足够字面重合；保留原 summary，仅重建 source_passage_refs。"
            ),
            "claim_summary": "",
            "source_slice_codes": refs,
            "claim_payload_patch": {"auto_repair": {"method": "source_slice_ref_relink", "overlap": overlap}},
        },
        "",
    )


def build_auto_patches(*, workitems_jsonl: Path, output_jsonl: Path, output_json: Path | None = None) -> dict[str, Any]:
    workitems = read_jsonl(workitems_jsonl)
    patches: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in workitems:
        patch, reason = auto_patch_for_workitem(row)
        if patch is None:
            skipped.append(
                {
                    "review_code": text(row.get("review_code")),
                    "reason": reason,
                    "emperor_name": text((row.get("subject") or {}).get("emperor_name") if isinstance(row.get("subject"), Mapping) else ""),
                    "object_name": text((row.get("subject") or {}).get("object_name") if isinstance(row.get("subject"), Mapping) else ""),
                }
            )
        else:
            patches.append(patch)
    write_jsonl(output_jsonl, patches)
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_claim_passage_repair.py",
        "command": "auto-patch",
        "ok": True,
        "files": {"patch_jsonl": repo_relative(output_jsonl)},
        "totals": {"workitems": len(workitems), "patches": len(patches), "skipped": len(skipped)},
        "skipped_counts": dict(sorted(Counter(row["reason"] for row in skipped).items())),
        "sample_skipped": skipped[:40],
    }
    if output_json is not None:
        write_json(output_json, payload)
    return payload


def auto_triage_patch_for_workitem(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    _patch, reason = auto_patch_for_workitem(row)
    if reason == "disposition_negative_needs_review":
        note = "按处置性材料原则转补源：当前材料属于伏诛、被废、撤权或类似处置结果，未直接证明任内治理或人才结构损害，需补源或由消费侧结合人物画像重判。"
    elif reason == "source_slice_ref_not_in_candidates":
        note = "机械转补源：原 claim 的 source_slice_refs 无法在当前 candidates 中完整找回，缺少可直接重链的同包候选上下文，需要补源或重判。"
    else:
        return None, reason
    return (
        {
            "review_code": text(row.get("review_code")),
            "repair_action": "needs_source_refine",
            "queue_status": "needs_review",
            "review_note": note,
            "claim_summary": "",
            "source_slice_codes": [],
            "claim_payload_patch": {"auto_repair": {"method": "needs_source_refine_triage", "reason": reason}},
        },
        "",
    )


def build_auto_triage_patches(*, workitems_jsonl: Path, output_jsonl: Path, output_json: Path | None = None) -> dict[str, Any]:
    workitems = read_jsonl(workitems_jsonl)
    patches: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in workitems:
        patch, reason = auto_triage_patch_for_workitem(row)
        if patch is None:
            skipped.append({"review_code": text(row.get("review_code")), "reason": reason})
        else:
            patches.append(patch)
    write_jsonl(output_jsonl, patches)
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_claim_passage_repair.py",
        "command": "auto-triage",
        "ok": True,
        "files": {"patch_jsonl": repo_relative(output_jsonl)},
        "totals": {"workitems": len(workitems), "patches": len(patches), "skipped": len(skipped)},
        "skipped_counts": dict(sorted(Counter(row["reason"] for row in skipped).items())),
        "sample_skipped": skipped[:40],
    }
    if output_json is not None:
        write_json(output_json, payload)
    return payload


def validate_patch_row(row: Mapping[str, Any]) -> dict[str, Any]:
    review_code = text(row.get("review_code"))
    if not review_code:
        raise ClaimPassageRepairError("patch row missing review_code")
    action = text(row.get("repair_action"))
    if action not in REPAIR_ACTIONS:
        raise ClaimPassageRepairError(f"{review_code}: unsupported repair_action {action}")
    queue_status = text(row.get("queue_status"))
    if queue_status not in PATCH_QUEUE_STATUSES:
        raise ClaimPassageRepairError(f"{review_code}: unsupported queue_status {queue_status}")
    if action in {"relink", "rewrite"} and queue_status != "resolved":
        raise ClaimPassageRepairError(f"{review_code}: {action} must use queue_status=resolved")
    if action in {"drop_claim", "block_claim"} and queue_status != "blocked":
        raise ClaimPassageRepairError(f"{review_code}: {action} must use queue_status=blocked")
    if action == "needs_source_refine" and queue_status != "needs_review":
        raise ClaimPassageRepairError(f"{review_code}: needs_source_refine must use queue_status=needs_review")
    source_slice_codes = [text(value) for value in row.get("source_slice_codes") or [] if text(value)]
    if action in {"relink", "rewrite"} and not source_slice_codes:
        raise ClaimPassageRepairError(f"{review_code}: {action} requires source_slice_codes")
    note = text(row.get("review_note"))
    if len(note) < 16:
        raise ClaimPassageRepairError(f"{review_code}: review_note is too short")
    payload_patch = row.get("claim_payload_patch") if isinstance(row.get("claim_payload_patch"), Mapping) else {}
    return {
        "review_code": review_code,
        "repair_action": action,
        "queue_status": queue_status,
        "review_note": note,
        "claim_summary": text(row.get("claim_summary")),
        "source_slice_codes": source_slice_codes,
        "claim_payload_patch": dict(payload_patch),
    }


def workitems_by_review_code(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    return {text(row.get("review_code")): row for row in rows if text(row.get("review_code"))}


def read_patch_inputs(paths: Sequence[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_dir():
            for child in sorted(path.glob("*.jsonl")):
                rows.extend(read_jsonl(child))
        else:
            rows.extend(read_jsonl(path))
    return rows


def slice_map_for_workitem(workitem: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("slice_code")): dict(row)
        for row in workitem.get("candidate_slices") or []
        if isinstance(row, Mapping) and text(row.get("slice_code"))
    }


def fetch_review_context(cur: Any, review_code: str) -> dict[str, Any]:
    cur.execute(
        """
        select
            mrq.id as review_id,
            mrq.queue_status::text as queue_status,
            mc.id as claim_id,
            mc.claim_summary,
            mc.claim_payload,
            sp.id as source_pack_id,
            sp.pack_code as source_pack_code
          from retrieval_v2.material_review_queue mrq
          join retrieval_v2.material_claims mc on mc.id = mrq.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
         where mrq.review_code = %s
        """,
        (review_code,),
    )
    row = cur.fetchone()
    if not row:
        raise ClaimPassageRepairError(f"review row not found: {review_code}")
    return dict(row)


def fetch_document_id(cur: Any, *, source_pack_id: int, raw_document_code: str) -> int:
    cur.execute(
        """
        select id
          from retrieval_v2.source_documents
         where source_pack_id = %s
           and (raw_document_code = %s or document_code = %s)
         order by case when raw_document_code = %s then 0 else 1 end
         limit 1
        """,
        (source_pack_id, raw_document_code, raw_document_code, raw_document_code),
    )
    row = cur.fetchone()
    if not row:
        raise ClaimPassageRepairError(f"source document not found for raw_document_code={raw_document_code}")
    return int(row["id"])


def upsert_repair_passage(cur: Any, *, context: Mapping[str, Any], candidate_slice: Mapping[str, Any], review_code: str) -> tuple[int, str]:
    raw_text = text(candidate_slice.get("text"))
    raw_document_code = text(candidate_slice.get("document_code"))
    document_id = fetch_document_id(cur, source_pack_id=int(context["source_pack_id"]), raw_document_code=raw_document_code)
    raw_passage_code = "RPR-" + text(candidate_slice.get("slice_code"))
    passage_code = text(context.get("source_pack_code")) + "::" + raw_passage_code
    payload = {
        "source": "retrieval_v2_claim_passage_repair",
        "review_code": review_code,
        "source_slice_code": text(candidate_slice.get("slice_code")),
        "candidate_slice": dict(candidate_slice),
    }
    cur.execute(
        """
        insert into retrieval_v2.source_passages (
            source_document_id, passage_code, raw_passage_code, deduped_raw_passage_codes,
            locator, raw_text, norm_text, quote_hash, passage_payload
        )
        values (%s, %s, %s, %s, %s, %s, '', %s, %s::jsonb)
        on conflict (source_document_id, raw_passage_code) where (btrim(raw_passage_code) <> '') do update set
            passage_code = excluded.passage_code,
            locator = excluded.locator,
            raw_text = excluded.raw_text,
            quote_hash = excluded.quote_hash,
            passage_payload = excluded.passage_payload
        returning id
        """,
        (
            document_id,
            passage_code,
            raw_passage_code,
            [],
            text(candidate_slice.get("locator")),
            raw_text,
            quote_hash(raw_text),
            json_param(payload),
        ),
    )
    row = cur.fetchone()
    if not row:
        raise ClaimPassageRepairError("repair source_passage upsert returned no id")
    return int(row["id"]), passage_code


def replace_claim_passages(cur: Any, *, context: Mapping[str, Any], passage_ids: Sequence[int], passage_codes: Sequence[str], patch: Mapping[str, Any]) -> None:
    claim_id = int(context["claim_id"])
    cur.execute("delete from retrieval_v2.claim_source_passages where claim_id = %s", (claim_id,))
    for passage_id in passage_ids:
        cur.execute(
            """
            insert into retrieval_v2.claim_source_passages (
                claim_id, source_passage_id, source_pack_id, relation_kind, relation_payload
            )
            values (%s, %s, %s, 'supporting_quote', %s::jsonb)
            on conflict on constraint rv2_claim_source_passages_uk do update set
                relation_payload = excluded.relation_payload
            """,
            (
                claim_id,
                int(passage_id),
                int(context["source_pack_id"]),
                json_param({"source": "retrieval_v2_claim_passage_repair", "patch": dict(patch)}),
            ),
        )
    new_summary = text(patch.get("claim_summary")) or text(context.get("claim_summary"))
    payload_patch = {
        "claim_summary": new_summary,
        "source_passage_refs": list(passage_codes),
        "source_slice_refs": list(patch.get("source_slice_codes") or []),
        "claim_passage_repair": {
            "source": "retrieval_v2_claim_passage_repair",
            "action": text(patch.get("repair_action")),
            "review_note": text(patch.get("review_note")),
        },
    }
    payload_patch.update(dict(patch.get("claim_payload_patch") or {}))
    cur.execute(
        """
        update retrieval_v2.material_claims
           set source_passage_id = %s,
               claim_summary = %s,
               claim_summary_hash = %s,
               claim_payload = claim_payload || %s::jsonb,
               updated_at = now()
         where id = %s
        """,
        (int(passage_ids[0]), new_summary, stable_hash(new_summary), json_param(payload_patch), claim_id),
    )


def update_review_queue(cur: Any, *, context: Mapping[str, Any], patch: Mapping[str, Any]) -> None:
    payload = {
        "claim_passage_repair": {
            "source": "retrieval_v2_claim_passage_repair",
            "patch": dict(patch),
        }
    }
    cur.execute(
        """
        update retrieval_v2.material_review_queue
           set queue_status = %s::retrieval_v2.rv2_queue_status,
               review_note = %s,
               review_payload = review_payload || %s::jsonb,
               resolved_at = case when %s in ('resolved', 'blocked', 'cancelled') then coalesce(resolved_at, now()) else resolved_at end,
               updated_at = now()
         where id = %s
        """,
        (text(patch.get("queue_status")), text(patch.get("review_note")), json_param(payload), text(patch.get("queue_status")), int(context["review_id"])),
    )


def close_control_plane_items(cur: Any, *, context: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, int]:
    if text(patch.get("queue_status")) not in {"resolved", "blocked"}:
        return {}
    payload = {
        "claim_passage_repair_resolution": {
            "source": "retrieval_v2_claim_passage_repair",
            "review_code": text(patch.get("review_code")),
            "repair_action": text(patch.get("repair_action")),
            "queue_status": text(patch.get("queue_status")),
        }
    }
    claim_id = int(context["claim_id"])
    cur.execute(
        """
        update retrieval_v2.coverage_gap_events
           set status = 'resolved',
               event_payload = event_payload || %s::jsonb,
               updated_at = now()
         where event_payload->>'source' = 'retrieval_v2_claim_passage_audit'
           and nullif(event_payload->>'claim_id', '')::bigint = %s
           and status in ('ready', 'queued', 'running', 'retry_wait', 'deferred')
        """,
        (json_param(payload), claim_id),
    )
    events = int(getattr(cur, "rowcount", 0) or 0)
    cur.execute(
        """
        update retrieval_v2.jobs
           set status = 'succeeded',
               payload = payload || %s::jsonb,
               last_error = '',
               updated_at = now()
         where kind = 'codex_material_review'
           and payload->'gap_event'->>'source' = 'retrieval_v2_claim_passage_audit'
           and nullif(payload->'gap_event'->>'claim_id', '')::bigint = %s
           and status in ('ready', 'running', 'retry_wait', 'deferred')
        """,
        (json_param(payload), claim_id),
    )
    jobs = int(getattr(cur, "rowcount", 0) or 0)
    return {
        "retrieval_v2.coverage_gap_events": events,
        "retrieval_v2.jobs": jobs,
    }


def mark_claim_dropped(cur: Any, *, context: Mapping[str, Any], patch: Mapping[str, Any]) -> None:
    payload = {
        "claim_passage_repair": {
            "source": "retrieval_v2_claim_passage_repair",
            "action": "drop_claim",
            "review_note": text(patch.get("review_note")),
        }
    }
    cur.execute(
        """
        update retrieval_v2.material_claims
           set review_status = 'rejected',
               claim_payload = claim_payload || %s::jsonb,
               updated_at = now()
         where id = %s
        """,
        (json_param(payload), int(context["claim_id"])),
    )


def apply_repair_patch(*, dsn: str, patch_rows: Sequence[Mapping[str, Any]], workitems: Mapping[str, Mapping[str, Any]], execute: bool) -> dict[str, Any]:
    validated = [validate_patch_row(row) for row in patch_rows]
    duplicates = [code for code, count in Counter(row["review_code"] for row in validated).items() if count > 1]
    if duplicates:
        raise ClaimPassageRepairError(f"duplicate review_code in patch: {', '.join(sorted(duplicates))}")
    psycopg, dict_row = import_psycopg()
    counts: Counter[str] = Counter()
    reviews: list[dict[str, Any]] = []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for patch in validated:
                review_code = text(patch.get("review_code"))
                context = fetch_review_context(cur, review_code)
                if review_code not in workitems:
                    raise ClaimPassageRepairError(f"{review_code}: missing workitem context")
                action = text(patch.get("repair_action"))
                if action in {"relink", "rewrite"}:
                    by_slice = slice_map_for_workitem(workitems[review_code])
                    passage_ids: list[int] = []
                    passage_codes: list[str] = []
                    for slice_code in patch["source_slice_codes"]:
                        if slice_code not in by_slice:
                            raise ClaimPassageRepairError(f"{review_code}: source_slice_code not in workitem: {slice_code}")
                        passage_id, passage_code = upsert_repair_passage(
                            cur,
                            context=context,
                            candidate_slice=by_slice[slice_code],
                            review_code=review_code,
                        )
                        passage_ids.append(passage_id)
                        passage_codes.append(passage_code)
                        counts["retrieval_v2.source_passages"] += 1
                    replace_claim_passages(cur, context=context, passage_ids=passage_ids, passage_codes=passage_codes, patch=patch)
                    counts["retrieval_v2.claim_source_passages"] += len(passage_ids)
                    counts["retrieval_v2.material_claims"] += 1
                elif action == "drop_claim":
                    mark_claim_dropped(cur, context=context, patch=patch)
                    counts["retrieval_v2.material_claims"] += 1
                elif action == "block_claim":
                    pass
                update_review_queue(cur, context=context, patch=patch)
                counts["retrieval_v2.material_review_queue"] += 1
                counts.update(close_control_plane_items(cur, context=context, patch=patch))
                reviews.append({"review_code": review_code, "repair_action": action, "queue_status": text(patch.get("queue_status"))})
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "generated_by": "scripts/dev/retrieval_v2_claim_passage_repair.py",
        "command": "apply-patch",
        "write_db": execute,
        "executed": execute,
        "ok": True,
        "rows": len(validated),
        "applied_counts": dict(sorted(counts.items())),
        "reviews": reviews,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair retrieval_v2 claim/passages mismatches from accepted clean packages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worklist = subparsers.add_parser("worklist", help="Build DB-backed claim/passage repair tasks.")
    worklist.add_argument("--env-file", type=Path)
    worklist.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    worklist.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    worklist.add_argument("--scope", choices=("active-targets", "accepted-packs"), default="accepted-packs")
    worklist.add_argument("--review-kind", action="append", choices=DEFAULT_REVIEW_KINDS, default=[])
    worklist.add_argument("--queue-status", action="append", default=[])
    worklist.add_argument("--target-name", action="append", default=[])
    worklist.add_argument("--target-code", action="append", default=[])
    worklist.add_argument("--limit", type=int, default=0)
    worklist.add_argument("--candidate-limit", type=int, default=8)
    worklist.add_argument("--batch-size", type=int, default=5)
    worklist.add_argument("--output-root", type=Path, required=True)

    run_plan = subparsers.add_parser("run-plan", help="Run or start Codex CLI repair tasks from codex_tasks.jsonl.")
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
    run_plan.add_argument("--search", action="store_true")

    collect = subparsers.add_parser("collect-patches", help="Collect JSONL repair patches from Codex last-message files.")
    collect.add_argument("--tasks-jsonl", type=Path, required=True)
    collect.add_argument("--output-json", type=Path)
    collect.add_argument("--overwrite", action="store_true")

    auto_patch = subparsers.add_parser("auto-patch", help="Build high-confidence deterministic relink patches from workitems.")
    auto_patch.add_argument("--workitems-jsonl", type=Path, required=True)
    auto_patch.add_argument("--output-jsonl", type=Path, required=True)
    auto_patch.add_argument("--output-json", type=Path)

    auto_triage = subparsers.add_parser("auto-triage", help="Build deterministic needs_source_refine patches for non-relinkable workitems.")
    auto_triage.add_argument("--workitems-jsonl", type=Path, required=True)
    auto_triage.add_argument("--output-jsonl", type=Path, required=True)
    auto_triage.add_argument("--output-json", type=Path)

    apply = subparsers.add_parser("apply-patch", help="Apply a claim/passage repair JSONL patch to retrieval_v2.")
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    apply.add_argument("--patch-jsonl", type=Path, action="append", required=True, help="Patch JSONL file, or a directory containing *.jsonl.")
    apply.add_argument("--workitems-jsonl", type=Path, required=True)
    apply.add_argument("--execute", action="store_true")
    apply.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "worklist":
        load_env_file(args.env_file)
        workitems = build_workitems(
            dsn=resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            scope=args.scope,
            review_kinds=args.review_kind or DEFAULT_REVIEW_KINDS,
            queue_statuses=args.queue_status or DEFAULT_QUEUE_STATUSES,
            target_names=args.target_name,
            target_codes=args.target_code,
            limit=max(0, args.limit),
            candidate_limit=max(1, args.candidate_limit),
        )
        summary = write_worklist_outputs(output_root=args.output_root, workitems=workitems, batch_size=max(1, args.batch_size))
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
            respect_task_argv=False,
            search=args.search,
        )
        return 0 if payload["returncode"] == 0 and payload["totals"].get("failed", 0) == 0 else 1
    if args.command == "collect-patches":
        payload = collect_patch_outputs(tasks_jsonl=args.tasks_jsonl, output_json=args.output_json, overwrite=args.overwrite)
        print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ok"] else 1
    if args.command == "auto-patch":
        payload = build_auto_patches(workitems_jsonl=args.workitems_jsonl, output_jsonl=args.output_jsonl, output_json=args.output_json)
        print(json.dumps({"ok": payload["ok"], "totals": payload["totals"], "skipped_counts": payload["skipped_counts"]}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "auto-triage":
        payload = build_auto_triage_patches(workitems_jsonl=args.workitems_jsonl, output_jsonl=args.output_jsonl, output_json=args.output_json)
        print(json.dumps({"ok": payload["ok"], "totals": payload["totals"], "skipped_counts": payload["skipped_counts"]}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "apply-patch":
        load_env_file(args.env_file)
        rows = read_patch_inputs(args.patch_jsonl)
        payload = apply_repair_patch(
            dsn=resolve_dsn(args.dsn_env),
            patch_rows=rows,
            workitems=workitems_by_review_code(args.workitems_jsonl),
            execute=args.execute,
        )
        if args.output_json is not None:
            write_json(args.output_json, payload)
        print(json.dumps({"ok": payload["ok"], "executed": payload["executed"], "rows": payload["rows"], "applied_counts": payload["applied_counts"]}, ensure_ascii=False, sort_keys=True))
        return 0
    raise ClaimPassageRepairError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
