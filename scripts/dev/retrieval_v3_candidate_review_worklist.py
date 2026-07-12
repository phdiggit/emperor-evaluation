from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_candidate_review_protocols import PROTOCOLS, protocol  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


PROFILE = "retrieval_v3_material_candidate_plan"
RULE_CODE = "appointment_delegation"
PATCH_BEGIN = "PATCH_JSONL_BEGIN"
PATCH_END = "PATCH_JSONL_END"


class CandidateReviewWorklistError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_code(value: Any) -> str:
    return "CRW-" + hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:16].upper()


def classify_identity_gate(row: Mapping[str, Any]) -> str:
    objects = row.get("matching_objects") if isinstance(row.get("matching_objects"), list) else []
    target_objects = row.get("target_objects") if isinstance(row.get("target_objects"), list) else []
    if not objects:
        return "identity_missing"
    if len(objects) > 1:
        return "identity_ambiguous"
    if any(text(item.get("review_status")) == "accepted" for item in target_objects if isinstance(item, Mapping)):
        return "identity_ready"
    return "identity_pending"


def trim_passages(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for passage in value:
        if not isinstance(passage, Mapping):
            continue
        result.append(
            {
                "passage_code": text(passage.get("passage_code")),
                "document_code": text(passage.get("document_code")),
                "source_title": text(passage.get("source_title")),
                "locator": text(passage.get("locator")),
                "raw_text": text(passage.get("raw_text")),
            }
        )
    return result


def build_workitem(row: Mapping[str, Any]) -> dict[str, Any]:
    candidate_code = text(row.get("candidate_code"))
    review_code = stable_code(candidate_code)
    identity_gate = classify_identity_gate(row)
    rule_code = text(row.get("candidate_rule_code")) or RULE_CODE
    review_protocol = protocol(rule_code)
    return {
        "workitem_code": review_code,
        "review_code": review_code,
        "candidate_code": candidate_code,
        "rule_code": rule_code,
        "candidate_id": int(row.get("candidate_id") or 0),
        "claim_id": int(row.get("claim_id") or 0),
        "target_code": text(row.get("target_code")),
        "emperor_name": text(row.get("emperor_name")),
        "source_pack_code": text(row.get("source_pack_code")),
        "object_name": text(row.get("object_name")),
        "claim_direction": text(row.get("claim_direction")),
        "claim_summary": text(row.get("claim_summary")),
        "candidate_reason": text(row.get("candidate_reason")),
        "candidate_payload": row.get("candidate_payload") if isinstance(row.get("candidate_payload"), Mapping) else {},
        "source_passages": trim_passages(row.get("source_passages")),
        "identity_gate": identity_gate,
        "matching_objects": row.get("matching_objects") if isinstance(row.get("matching_objects"), list) else [],
        "target_objects": row.get("target_objects") if isinstance(row.get("target_objects"), list) else [],
        "required_patch": {
            "review_code": review_code,
            "review_verdict": "",
            "review_note": "",
            "rule_code": rule_code,
            "required_facts": {key: None for key in review_protocol.fact_keys},
            "candidate_role": "",
            "direction": text(row.get("claim_direction")),
            "scoring_candidate": False,
            "usable_for_scoring_cluster": False,
            "identity_gate": identity_gate,
            "evidence_passage_codes": [],
        },
    }


def fetch_rows(cur: Any, *, profile: str, review_status: str, rule_code: str, limit: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        with passage_agg as (
            select csp.claim_id,
                   jsonb_agg(jsonb_build_object(
                       'passage_code', spg.passage_code,
                       'document_code', sd.document_code,
                       'source_title', coalesce(sd.source_title, sd.title),
                       'locator', coalesce(nullif(spg.locator, ''), sd.locator),
                       'raw_text', spg.raw_text
                   ) order by csp.id) as source_passages
              from retrieval_v3.claim_source_passages csp
              join retrieval_v3.source_passages spg on spg.id = csp.source_passage_id
              join retrieval_v3.source_documents sd on sd.id = spg.source_document_id
             group by csp.claim_id
        )
        select c.id as candidate_id, c.candidate_code, c.claim_id, c.candidate_rule_code,
               c.candidate_reason, c.candidate_payload,
               mc.claim_code, mc.object_name, mc.claim_summary, mc.emperor_name, mc.direction::text as claim_direction,
               sp.pack_code as source_pack_code, rt.target_code,
               coalesce(pa.source_passages, '[]'::jsonb) as source_passages,
               coalesce(jsonb_agg(distinct jsonb_build_object(
                   'object_id', o.id, 'identity_key', o.object_identity_key,
                   'name', o.canonical_name, 'identity_status', o.identity_status::text
               )) filter (where o.id is not null), '[]'::jsonb) as matching_objects,
               coalesce(jsonb_agg(distinct jsonb_build_object(
                   'target_object_id', tob.id, 'object_id', tob.object_id,
                   'review_status', tob.review_status::text, 'scope', tob.scope_code::text
               )) filter (where tob.id is not null), '[]'::jsonb) as target_objects
          from retrieval_v3.claim_rule_binding_candidates c
          join retrieval_v3.material_claims mc on mc.id = c.claim_id
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
          left join passage_agg pa on pa.claim_id = mc.id
          left join retrieval_v3.objects o
            on o.identity_status::text = 'active'
           and (
                lower(o.canonical_name) = lower(mc.object_name)
                or exists (
                select 1
                  from retrieval_v3.object_names onm
                 where onm.object_id = o.id
                   and onm.review_status::text = 'accepted'
                   and (
                       lower(onm.name_text) = lower(mc.object_name)
                       or lower(onm.normalized_name) = lower(mc.object_name)
                   )
                )
           )
          left join retrieval_v3.target_objects tob on tob.target_id = rt.id and tob.object_id = o.id
         where c.routed_by_profile = %s
           and c.review_status::text = %s
           and c.candidate_rule_code = %s
         group by c.id, c.candidate_code, c.claim_id, c.candidate_reason, c.candidate_payload,
                  mc.claim_code, mc.object_name, mc.claim_summary, mc.emperor_name, mc.direction,
                  sp.pack_code, rt.target_code, pa.source_passages
         order by mc.emperor_name, c.id
         limit case when %s > 0 then %s else 2147483647 end
        """,
        (profile, review_status, rule_code, limit, limit),
    )
    return [dict(row) for row in cur.fetchall()]


def build_workitems(*, dsn: str, schema_name: str, profile: str, review_status: str, rule_code: str, limit: int) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            rows = fetch_rows(schema_cursor(raw_cur, schema_name=schema_name), profile=profile, review_status=review_status, rule_code=rule_code, limit=limit)
    return [build_workitem(row) for row in rows]


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    step = max(1, size)
    return [list(rows[i : i + step]) for i in range(0, len(rows), step)]


def prompt_for_task(task_code: str, workitems: Sequence[Mapping[str, Any]], *, rule_code: str = RULE_CODE) -> str:
    review_protocol = protocol(rule_code)
    return (
        "# retrieval_v3 candidate review\n\n"
        f"只依据给出的完整 source_passages 复核 {rule_code} 候选。禁止联网、禁止写库、禁止改代码。\n"
        f"规则门禁：{review_protocol.prompt}\n"
        f"required_facts 必须逐项使用布尔值：{', '.join(review_protocol.fact_keys)}。\n"
        f"candidate_role 只能使用以下枚举：{', '.join(review_protocol.roles)}。\n"
        "direction 只能是 positive 或 negative；优先沿用 workitem 的 claim_direction，不要写人物关系、自由描述或中文句子。\n"
        "identity_gate 只能复述输入状态，不能自行创造 object_id 或接受 target_object。\n\n"
        f"task_code: {task_code}\n"
        "输出只能是 PATCH_JSONL_BEGIN/END 包住的 JSONL，每行对应一个 workitem。\n"
        "review_verdict 只能是 accepted_candidate、supporting_only、rejected、needs_context。\n\n"
        f"{PATCH_BEGIN}\n"
        + json.dumps(
            {
                "review_code": "CRW-...",
                "rule_code": rule_code,
                "review_verdict": "needs_context",
                "review_note": "",
                "required_facts": {key: False for key in review_protocol.fact_keys},
                "candidate_role": "",
                "direction": "positive",
                "scoring_candidate": False,
                "usable_for_scoring_cluster": False,
                "identity_gate": "identity_pending",
                "evidence_passage_codes": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + f"\n{PATCH_END}\n\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
    )


def write_outputs(workitems: Sequence[Mapping[str, Any]], output_root: Path, batch_size: int, *, rule_code: str = RULE_CODE) -> dict[str, Any]:
    runtime = agent_runtime_config.resolve_agent_stage("v3_candidate_review")
    output_root.mkdir(parents=True, exist_ok=True)
    tasks = []
    for index, batch in enumerate(chunks(workitems, batch_size), start=1):
        task_code = "CVT-" + hashlib.sha256(stable_json([row.get("review_code") for row in batch]).encode("utf-8")).hexdigest()[:16].upper()
        prompt_path = output_root / "prompts" / f"{task_code}.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task_code, batch, rule_code=rule_code), encoding="utf-8")
        patch_path = output_root / "patches" / f"{task_code}.jsonl"
        tasks.append({
            "task_code": task_code,
            "task_kind": "retrieval_v3_candidate_review",
            "batch_index": index,
            "workitem_codes": [text(row.get("workitem_code")) for row in batch],
            "prompt_path": str(prompt_path),
            "expected_outputs": [
                {
                    "kind": "jsonl_patch",
                    "path": str(patch_path),
                    "fallback": "last_message_marked_block",
                    "begin": PATCH_BEGIN,
                    "end": PATCH_END,
                }
            ],
            "last_message_path": str(output_root / "logs" / f"{task_code}.last.md"),
            "log_path": str(output_root / "logs" / f"{task_code}.jsonl"),
            "argv": agent_runtime_config.codex_task_argv("v3_candidate_review"),
        })
    (output_root / "candidate_review_workitems.jsonl").write_text("".join(stable_json(row) + "\n" for row in workitems), encoding="utf-8")
    (output_root / "codex_tasks.jsonl").write_text("".join(stable_json(row) + "\n" for row in tasks), encoding="utf-8")
    gate_counts = Counter(text(row.get("identity_gate")) for row in workitems)
    emperor_counts = Counter(text(row.get("emperor_name")) for row in workitems)
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_candidate_review_worklist.py",
        "rule_code": rule_code,
        "candidate_count": len(workitems),
        "task_count": len(tasks),
        "identity_gate_counts": dict(sorted(gate_counts.items())),
        "candidate_counts_by_emperor": dict(sorted(emperor_counts.items())),
        "agent_runtime": runtime,
        "legacy_data_reads": False,
        "write_db": False,
    }
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only v3 candidate review and identity-gate worklists.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--profile", default=PROFILE)
    parser.add_argument("--rule-code", choices=tuple(PROTOCOLS), default=RULE_CODE)
    parser.add_argument("--review-status", default="pending")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    workitems = build_workitems(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        profile=args.profile,
        review_status=args.review_status,
        rule_code=args.rule_code,
        limit=max(0, args.limit),
    )
    runtime = agent_runtime_config.resolve_agent_stage("v3_candidate_review")
    summary = write_outputs(workitems, args.output_root, int(args.batch_size or runtime["batch_size"]), rule_code=args.rule_code)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
