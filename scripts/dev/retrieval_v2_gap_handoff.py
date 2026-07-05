from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dev.retrieval_v2_clean_summary import anomaly_counts, judge_anomalies


DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
SOURCE_PACK_REFINEMENT_TYPES = {
    "source_missing",
    "alias_missing",
    "fetch_error",
    "source_fetch_failed",
    "needs_primary_source",
    "predicate_missing",
    "civil_undercoverage",
    "negative_undercoverage",
    "weak_alias_noise",
    "core_no_material",
    "core_zero_signal",
    "alias_unsearched",
}
CODEX_REVIEW_TYPES = {
    "mixed_claim_not_split",
    "mixed_claim_needs_review",
    "negative_claim_not_scoring_without_gap",
    "other",
}
JOB_QUEUES = {"source_pack_refinement", "codex_review"}


class GapHandoffError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def text(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_artifact(path_text: str, *, run_root: Path) -> Path:
    path = Path(path_text)
    if path.exists() or path.is_absolute():
        return path
    candidate = run_root / path
    return candidate if candidate.exists() else path


def load_env_file(path: Path | None) -> list[str]:
    if path is None:
        return []
    if not path.exists():
        raise GapHandoffError(f"env file missing: {path}")
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")
        loaded.append(key)
    return loaded


def import_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
        raise GapHandoffError("psycopg is required for DB gap handoff") from exc
    return psycopg, dict_row


def json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def normalize_gap_type(raw_gap_type: str, *, source: str) -> str:
    value = text(raw_gap_type) or "other"
    if value == "source_fetch_failed":
        return "fetch_error"
    if value == "mixed_claim_needs_review":
        return "mixed_claim_not_split"
    if source == "objects_without_slices":
        return "source_missing"
    return value


def queue_for_gap_type(gap_type: str) -> str:
    if gap_type in SOURCE_PACK_REFINEMENT_TYPES:
        return "source_pack_refinement"
    if gap_type in CODEX_REVIEW_TYPES:
        return "codex_review"
    if gap_type == "object_payload_gap":
        return "object_payload_or_source_review"
    if gap_type == "material_classification_review":
        return "material_classification_review"
    if gap_type == "policy_block":
        return "policy_block_review"
    if gap_type == "true_lack":
        return "true_lack_note"
    return "source_pack_refinement"


def priority_for_event(gap_type: str, queue: str) -> int:
    if queue == "codex_review":
        return 40
    if gap_type in {"source_missing", "alias_missing", "fetch_error"}:
        return 50
    if gap_type in {"predicate_missing", "civil_undercoverage", "negative_undercoverage"}:
        return 60
    return 100


def idem_key_for_event(event: Mapping[str, Any]) -> str:
    parts = [
        text(event.get("target_code")),
        text(event.get("rule_code")),
        text(event.get("source_pack_code")),
        text(event.get("gap_type")),
        text(event.get("family_code")),
        text(event.get("object_name")),
        text(event.get("predicate")),
    ]
    return "|".join(parts)


def make_event(
    *,
    target_code: str,
    rule_code: str,
    item_code: str,
    emperor_name: str,
    source_pack_code: str,
    source: str,
    gap: Mapping[str, Any],
    run_root: Path,
    summary_path: Path,
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    gap_type = normalize_gap_type(text(gap.get("gap_type") or gap.get("code")), source=source)
    queue = text(gap.get("queue")) or queue_for_gap_type(gap_type)
    object_name = text(gap.get("object_name"))
    if source == "fetch_error" and not object_name:
        object_name = text(gap.get("title") or gap.get("document_code") or gap.get("url"))
    event = {
        "target_code": target_code,
        "rule_code": rule_code,
        "item_code": item_code,
        "emperor_name": emperor_name,
        "source_pack_code": source_pack_code,
        "gap_type": gap_type,
        "queue": queue,
        "status": "ready",
        "priority": int(gap.get("priority") or priority_for_event(gap_type, queue)),
        "family_code": text(gap.get("family_code")),
        "object_name": object_name,
        "predicate": text(gap.get("predicate")),
        "diagnosis": text(gap.get("diagnosis") or gap.get("message")),
        "recommended_action": text(gap.get("recommended_action")),
        "source": source,
        "run_root": str(run_root),
        "summary_path": str(summary_path),
        "artifact_paths": dict(artifact_paths),
        "raw_gap": dict(gap),
    }
    event["idem_key"] = idem_key_for_event(event)
    event["event_code"] = f"CGE-{stable_fingerprint(event['idem_key'])[:12].upper()}"
    return event


def fallback_source_pack_code(*, run_root: Path, target_code: str, rule_code: str) -> str:
    key = [str(run_root).replace("\\", "/"), target_code, rule_code]
    return f"RUN-{stable_fingerprint(key)[:12].upper()}"


def task_context(task: Mapping[str, Any], person: Mapping[str, Any], *, run_root: Path) -> dict[str, str]:
    context = {
        "target_code": text(task.get("target_code") or person.get("target_code")),
        "rule_code": text(task.get("rule_code") or person.get("rule_code")),
        "item_code": text(task.get("item_code") or person.get("item_code")),
        "emperor_name": text(task.get("emperor_name") or person.get("name")),
        "source_pack_code": text(task.get("source_pack_code") or person.get("source_pack_code")),
    }
    if not context["source_pack_code"]:
        context["source_pack_code"] = fallback_source_pack_code(
            run_root=run_root,
            target_code=context["target_code"],
            rule_code=context["rule_code"],
        )
    return context


def events_from_summary(summary_path: Path) -> list[dict[str, Any]]:
    summary = load_json(summary_path)
    run_root = summary_path.parent
    events: list[dict[str, Any]] = []
    for person in summary.get("people") or []:
        if not isinstance(person, Mapping):
            continue
        files = person.get("files") if isinstance(person.get("files"), Mapping) else {}
        task_path = resolve_artifact(text(files.get("final_task")), run_root=run_root) if files.get("final_task") else None
        candidates_path = (
            resolve_artifact(text(files.get("final_candidates")), run_root=run_root)
            if files.get("final_candidates")
            else None
        )
        judge_path = (
            resolve_artifact(text(files.get("final_judge_result")), run_root=run_root)
            if files.get("final_judge_result")
            else None
        )
        task = load_json(task_path) if task_path and task_path.exists() else {}
        candidates = load_json(candidates_path) if candidates_path and candidates_path.exists() else {}
        judge = load_json(judge_path) if judge_path and judge_path.exists() else {}
        context = task_context(task, person, run_root=run_root)
        artifact_paths = {
            "task": str(task_path) if task_path else "",
            "candidates": str(candidates_path) if candidates_path else "",
            "judge": str(judge_path) if judge_path else "",
        }

        coverage = candidates.get("coverage") if isinstance(candidates.get("coverage"), Mapping) else {}
        for object_name in coverage.get("objects_without_slices") or person.get("objects_without_slices") or []:
            if not text(object_name):
                continue
            events.append(
                make_event(
                    **context,
                    source="objects_without_slices",
                    gap={"gap_type": "source_missing", "object_name": text(object_name)},
                    run_root=run_root,
                    summary_path=summary_path,
                    artifact_paths=artifact_paths,
                )
            )
        for gap in candidates.get("coverage_gaps") or []:
            if isinstance(gap, Mapping):
                events.append(
                    make_event(
                        **context,
                        source="candidate_coverage_gap",
                        gap=gap,
                        run_root=run_root,
                        summary_path=summary_path,
                        artifact_paths=artifact_paths,
                    )
                )
        for fetch_error in candidates.get("fetch_errors") or []:
            if not isinstance(fetch_error, Mapping):
                fetch_error = {"diagnosis": text(fetch_error)}
            gap = {"gap_type": "fetch_error", **dict(fetch_error)}
            events.append(
                make_event(
                    **context,
                    source="fetch_error",
                    gap=gap,
                    run_root=run_root,
                    summary_path=summary_path,
                    artifact_paths=artifact_paths,
                )
            )
        for gap in judge.get("coverage_gaps") or []:
            if isinstance(gap, Mapping):
                events.append(
                    make_event(
                        **context,
                        source="judge_coverage_gap",
                        gap=gap,
                        run_root=run_root,
                        summary_path=summary_path,
                        artifact_paths=artifact_paths,
                    )
                )
        anomalies = [row for row in person.get("judge_anomalies") or [] if isinstance(row, Mapping)]
        if not anomalies and judge:
            anomalies = judge_anomalies(judge)
        for anomaly in anomalies:
            events.append(
                make_event(
                    **context,
                    source="judge_anomaly",
                    gap=anomaly,
                    run_root=run_root,
                    summary_path=summary_path,
                    artifact_paths=artifact_paths,
                )
            )
    return unique_events(events)


def unique_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for event in events:
        key = text(event.get("idem_key"))
        if key:
            by_key.setdefault(key, event)
    return list(by_key.values())


def write_jsonl(events: Sequence[Mapping[str, Any]], path: Path | None) -> None:
    lines = [stable_json(event) for event in events]
    payload = "\n".join(lines) + ("\n" if lines else "")
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


def markdown_report(events: Sequence[Mapping[str, Any]]) -> str:
    lines = ["# retrieval_v2 gap handoff", ""]
    if not events:
        lines.append("No gap events.")
        return "\n".join(lines) + "\n"
    lines.append("| target | rule | queue | gap_type | object | predicate | action |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for event in events:
        lines.append(
            "| "
            + " | ".join(
                [
                    text(event.get("emperor_name") or event.get("target_code")),
                    text(event.get("rule_code")),
                    text(event.get("queue")),
                    text(event.get("gap_type")),
                    text(event.get("object_name")) or "-",
                    text(event.get("predicate")) or "-",
                    text(event.get("recommended_action") or event.get("diagnosis")) or "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_markdown(events: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_report(events), encoding="utf-8")


def db_lookup_refs(cur: Any, event: Mapping[str, Any]) -> dict[str, int | None]:
    cur.execute(
        """
        select
            t.id as target_id,
            crr.id as contract_rule_id,
            sp.id as source_pack_id
          from retrieval_v2.retrieval_targets t
          left join retrieval_v2.rule_contract_rules crr
            on crr.contract_id = t.contract_id
           and crr.rule_code = %s
          left join retrieval_v2.source_packs sp
            on sp.target_id = t.id
           and sp.pack_code = %s
         where t.target_code = %s
         limit 1
        """,
        (text(event.get("rule_code")), text(event.get("source_pack_code")), text(event.get("target_code"))),
    )
    row = cur.fetchone()
    if not row:
        raise GapHandoffError(f"missing retrieval_v2 target for event {event.get('event_code')}: {event.get('target_code')}")
    return {
        "target_id": int(row["target_id"]),
        "contract_rule_id": int(row["contract_rule_id"]) if row.get("contract_rule_id") else None,
        "source_pack_id": int(row["source_pack_id"]) if row.get("source_pack_id") else None,
    }


def upsert_gap_events(*, dsn: str, events: Sequence[Mapping[str, Any]]) -> int:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            count = 0
            for event in events:
                refs = db_lookup_refs(cur, event)
                cur.execute(
                    """
                    insert into retrieval_v2.coverage_gap_events (
                        event_code, idem_key, target_id, contract_rule_id, source_pack_id,
                        gap_type, queue, diagnosis, recommended_action, status, priority, event_payload
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ready', %s, %s::jsonb)
                    on conflict (idem_key) do update set
                        gap_type = excluded.gap_type,
                        queue = excluded.queue,
                        diagnosis = excluded.diagnosis,
                        recommended_action = excluded.recommended_action,
                        priority = least(retrieval_v2.coverage_gap_events.priority, excluded.priority),
                        event_payload = excluded.event_payload,
                        updated_at = now()
                    """,
                    (
                        event["event_code"],
                        event["idem_key"],
                        refs["target_id"],
                        refs["contract_rule_id"],
                        refs["source_pack_id"],
                        event["gap_type"],
                        event["queue"],
                        event["diagnosis"],
                        event["recommended_action"],
                        int(event["priority"]),
                        json_param(event),
                    ),
                )
                count += 1
        conn.commit()
    return count


def action_for_gap_type(gap_type: str) -> str:
    if gap_type == "alias_missing":
        return "alias_refine"
    if gap_type == "fetch_error":
        return "fetch_retry"
    if gap_type == "mixed_claim_not_split":
        return "split_or_mark_material_claim"
    return "source_pack_refine"


def job_from_event(event: Mapping[str, Any]) -> dict[str, Any] | None:
    queue = text(event.get("queue"))
    gap_type = text(event.get("gap_type"))
    if queue == "source_pack_refinement":
        kind = "codex_source_pack_refine"
    elif queue == "codex_review":
        kind = "codex_material_review"
    else:
        return None
    idem_key = "gap_job|" + text(event.get("idem_key"))
    return {
        "job_code": f"JOB-GAP-{stable_fingerprint(idem_key)[:12].upper()}",
        "idem_key": idem_key,
        "kind": kind,
        "status": "ready",
        "priority": int(event.get("priority") or priority_for_event(gap_type, queue)),
        "payload": {
            "generated_by": "scripts/dev/retrieval_v2_gap_handoff.py",
            "action": action_for_gap_type(gap_type),
            "gap_event": dict(event),
        },
    }


def fetch_ready_gap_events(*, cur: Any, queues: Sequence[str], limit: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            e.event_code,
            e.idem_key,
            e.gap_type,
            e.queue,
            e.diagnosis,
            e.recommended_action,
            e.priority,
            e.event_payload,
            t.target_code,
            t.emperor_name,
            t.item_code,
            coalesce(crr.rule_code, '') as rule_code,
            coalesce(sp.pack_code, '') as source_pack_code
          from retrieval_v2.coverage_gap_events e
          join retrieval_v2.retrieval_targets t on t.id = e.target_id
          left join retrieval_v2.rule_contract_rules crr on crr.id = e.contract_rule_id
          left join retrieval_v2.source_packs sp on sp.id = e.source_pack_id
         where e.status = 'ready'
           and e.queue = any(%s)
         order by e.priority, e.created_at
         limit %s
        """,
        (list(queues), limit),
    )
    rows: list[dict[str, Any]] = []
    for row in cur.fetchall():
        payload = row.get("event_payload") if isinstance(row.get("event_payload"), Mapping) else {}
        event = {
            **dict(payload),
            "event_code": row["event_code"],
            "idem_key": row["idem_key"],
            "gap_type": row["gap_type"],
            "queue": row["queue"],
            "diagnosis": row["diagnosis"],
            "recommended_action": row["recommended_action"],
            "priority": row["priority"],
            "target_code": row["target_code"],
            "emperor_name": row["emperor_name"],
            "item_code": row["item_code"],
            "rule_code": row["rule_code"],
            "source_pack_code": row["source_pack_code"],
        }
        rows.append(event)
    return rows


def enqueue_jobs(*, dsn: str, queues: Sequence[str], limit: int, dry_run: bool = False) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            events = fetch_ready_gap_events(cur=cur, queues=queues, limit=limit)
            jobs = [job for event in events if (job := job_from_event(event))]
            if dry_run:
                conn.rollback()
                return jobs
            for job in jobs:
                cur.execute(
                    """
                    insert into retrieval_v2.jobs (job_code, idem_key, kind, status, priority, payload)
                    values (%s, %s, %s, 'ready', %s, %s::jsonb)
                    on conflict (idem_key) do update set
                        priority = least(retrieval_v2.jobs.priority, excluded.priority),
                        payload = excluded.payload,
                        updated_at = now()
                    """,
                    (job["job_code"], job["idem_key"], job["kind"], int(job["priority"]), json_param(job["payload"])),
                )
                event_code = job["payload"]["gap_event"]["event_code"]
                cur.execute(
                    """
                    update retrieval_v2.coverage_gap_events
                       set status = 'queued',
                           event_payload = jsonb_set(
                               event_payload,
                               '{job_code}',
                               to_jsonb(%s::text),
                               true
                           ),
                           updated_at = now()
                     where event_code = %s
                       and status = 'ready'
                    """,
                    (job["job_code"], event_code),
                )
        conn.commit()
    return jobs


def parse_queues(raw_queues: Sequence[str]) -> list[str]:
    queues = [text(queue) for queue in raw_queues if text(queue)]
    invalid = [queue for queue in queues if queue not in JOB_QUEUES]
    if invalid:
        raise GapHandoffError(f"unsupported job queue(s): {invalid}")
    return queues or ["source_pack_refinement"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit retrieval_v2 gap handoff events and enqueue gap jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    emit = subparsers.add_parser("emit", help="Emit gap handoff events from clean runner summary.json")
    emit.add_argument("--summary", type=Path, action="append", required=True)
    emit.add_argument("--output-jsonl", type=Path)
    emit.add_argument("--output-md", type=Path)
    emit.add_argument("--write-db", action="store_true")
    emit.add_argument("--env-file", type=Path)
    emit.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)

    enqueue = subparsers.add_parser("enqueue-jobs", help="Turn ready coverage_gap_events into retrieval_v2.jobs")
    enqueue.add_argument("--env-file", type=Path)
    enqueue.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    enqueue.add_argument("--queue", action="append", default=[])
    enqueue.add_argument("--limit", type=int, default=50)
    enqueue.add_argument("--dry-run", action="store_true")
    enqueue.add_argument("--output-jsonl", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "emit":
        events: list[dict[str, Any]] = []
        for summary_path in args.summary:
            events.extend(events_from_summary(summary_path))
        events = unique_events(events)
        write_jsonl(events, args.output_jsonl)
        if args.output_md:
            write_markdown(events, args.output_md)
        if args.write_db:
            load_env_file(args.env_file)
            dsn = os.environ.get(args.dsn_env)
            if not dsn:
                raise GapHandoffError(f"missing PostgreSQL DSN env var: {args.dsn_env}")
            upsert_gap_events(dsn=dsn, events=events)
        return 0

    if args.command == "enqueue-jobs":
        load_env_file(args.env_file)
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise GapHandoffError(f"missing PostgreSQL DSN env var: {args.dsn_env}")
        queues = parse_queues(args.queue)
        jobs = enqueue_jobs(dsn=dsn, queues=queues, limit=max(1, args.limit), dry_run=args.dry_run)
        write_jsonl(jobs, args.output_jsonl)
        return 0

    raise GapHandoffError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
