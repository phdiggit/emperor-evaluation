from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.object_pool_aliases import normalize_object_alias  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_expected_event_inventory import read_jsonl, stable_code, stable_json, text  # noqa: E402
from scripts.dev.retrieval_v3_unseeded_actor_review_tasks import PATCH_BEGIN, PATCH_END  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


DECISIONS = {
    "already_covered",
    "rebuild_event_group",
    "reextract_cached_source",
    "fetch_missing_source",
    "inventory_needs_review",
    "identity_mismatch",
}
RESOLVED_WITHOUT_NEW_SOURCE = {"already_covered", "rebuild_event_group", "reextract_cached_source"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
FACETS = ("appointment", "duty", "outcome", "same_event")
PLACEHOLDER_FRAGMENTS = ("示例", "EXAMPLE", "某事件", "某人物")
DEFAULT_MIN_EXISTING_SOURCE_RESOLUTION_RATE = 0.5


class ExpectedEventReconciliationError(ValueError):
    pass


def list_texts(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    result: list[str] = []
    for item in value:
        normalized = text(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def compact(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff\U00020000-\U0002fa1f]+", "", text(value)).lower()


def ngrams(value: Any, size: int = 2) -> set[str]:
    normalized = compact(value)
    if len(normalized) < size:
        return {normalized} if normalized else set()
    return {normalized[index:index + size] for index in range(len(normalized) - size + 1)}


def object_matches(event: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    event_id = int(event.get("object_id") or 0)
    row_id = int(row.get("object_id") or 0)
    if event_id and row_id:
        return event_id == row_id
    return normalize_object_alias(event.get("object_name")) == normalize_object_alias(row.get("object_name"))


def event_terms(event: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        "event": list_texts(event.get("event_anchor_terms")),
        "duty": list_texts(event.get("duty_anchor_terms")),
        "outcome": list_texts(event.get("outcome_anchor_terms")),
    }


def row_blob(row: Mapping[str, Any]) -> str:
    return " ".join(
        text(value)
        for value in (
            row.get("claim_summary"),
            row.get("action_type"),
            row.get("fact_type"),
            row.get("office_or_domain"),
            row.get("outcome"),
            row.get("slice_text_preview"),
        )
    )


def lexical_score(event: Mapping[str, Any], value: str) -> float:
    normalized = compact(value)
    terms = event_terms(event)
    score = 0.0
    score += 4.0 * sum(compact(term) in normalized for term in terms["outcome"] if compact(term))
    score += 3.0 * sum(compact(term) in normalized for term in terms["event"] if compact(term))
    score += 2.0 * sum(compact(term) in normalized for term in terms["duty"] if compact(term))
    event_grams = ngrams(" ".join([text(event.get("event_label")), *terms["event"], *terms["outcome"]]))
    value_grams = ngrams(value)
    if event_grams and value_grams:
        score += 3.0 * len(event_grams & value_grams) / len(event_grams | value_grams)
    return round(score, 4)


def group_claim_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for raw_row in rows:
        row = dict(raw_row)
        group_keys = list_texts(row.get("event_group_keys")) or [""]
        for group_key in group_keys:
            key = (
                text(row.get("emperor_name")),
                int(row.get("object_id") or 0),
                normalize_object_alias(row.get("object_name")),
                group_key,
            )
            group = groups.setdefault(
                key,
                {
                    "emperor_name": text(row.get("emperor_name")),
                    "object_id": row.get("object_id"),
                    "object_name": text(row.get("object_name")),
                    "group_key": group_key,
                    "claims": [],
                    "text": "",
                },
            )
            claim = {
                "claim_key": text(row.get("claim_key")),
                "action_type": text(row.get("action_type")),
                "fact_type": text(row.get("fact_type")),
                "office_or_domain": text(row.get("office_or_domain")),
                "outcome": text(row.get("outcome")),
                "outcome_support": text(row.get("outcome_support")),
                "claim_summary": text(row.get("claim_summary")),
                "evidence": row.get("evidence") or [],
            }
            group["claims"].append(claim)
            group["text"] += " " + row_blob(row)
    return list(groups.values())


def candidate_groups(
    event: Mapping[str, Any], groups: Sequence[Mapping[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for raw_group in groups:
        if text(event.get("emperor_name")) != text(raw_group.get("emperor_name")) or not object_matches(event, raw_group):
            continue
        group = dict(raw_group)
        group["lexical_score"] = lexical_score(event, text(group.get("text")))
        group.pop("text", None)
        candidates.append(group)
    return sorted(candidates, key=lambda row: (-float(row["lexical_score"]), text(row.get("group_key"))))[:limit]


def candidate_slices(
    event: Mapping[str, Any], source_rows: Sequence[Mapping[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for raw_row in source_rows:
        if not object_matches(event, raw_row):
            continue
        row = dict(raw_row)
        row["lexical_score"] = lexical_score(event, text(row.get("slice_text_preview")))
        candidates.append(row)
    return sorted(
        candidates,
        key=lambda row: (-float(row["lexical_score"]), text(row.get("document_code")), text(row.get("source_slice_ref"))),
    )[:limit]


def build_workitems(
    inventory_rows: Sequence[Mapping[str, Any]],
    claim_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
    *,
    max_groups: int = 5,
    max_slices: int = 3,
) -> list[dict[str, Any]]:
    events = [dict(row) for row in inventory_rows if text(row.get("record_type")) != "object_assessment"]
    groups = group_claim_rows(claim_rows)
    by_object: dict[tuple[str, int, str], dict[str, Any]] = {}
    for event in events:
        key = (
            text(event.get("emperor_name")),
            int(event.get("object_id") or 0),
            normalize_object_alias(event.get("object_name")),
        )
        workitem = by_object.setdefault(
            key,
            {
                "workitem_code": stable_code("EERW-", *key),
                "emperor_name": text(event.get("emperor_name")),
                "object_id": event.get("object_id"),
                "object_name": text(event.get("object_name")),
                "events": [],
                "_claim_group_index": {},
                "_source_slice_index": {},
                "write_db": False,
                "scoring_allowed": False,
            },
        )
        selected_groups = candidate_groups(event, groups, limit=max_groups)
        selected_slices = candidate_slices(event, source_rows, limit=max_slices)
        for group in selected_groups:
            group_key = text(group.get("group_key"))
            workitem["_claim_group_index"].setdefault(group_key, group)
        for source_slice in selected_slices:
            source_key = text(source_slice.get("source_slice_ref") or source_slice.get("slice_hash"))
            workitem["_source_slice_index"].setdefault(source_key, source_slice)
        workitem["events"].append(
            {
                "event_inventory_code": text(event.get("event_inventory_code")),
                "event_label": text(event.get("event_label")),
                "direction": text(event.get("direction")),
                "importance": text(event.get("importance")),
                "domain": text(event.get("domain")),
                **event_terms(event),
                "source_leads": event.get("source_leads") or [],
                "candidate_groups": [
                    {"group_key": text(group.get("group_key")), "lexical_score": group.get("lexical_score")}
                    for group in selected_groups
                ],
                "candidate_cached_slices": [
                    {
                        "source_slice_ref": text(source_slice.get("source_slice_ref")),
                        "lexical_score": source_slice.get("lexical_score"),
                    }
                    for source_slice in selected_slices
                ],
                "allowed_claim_keys": list(dict.fromkeys(
                    text(claim.get("claim_key"))
                    for group in selected_groups
                    for claim in group.get("claims") or []
                    if text(claim.get("claim_key"))
                )),
                "allowed_source_slice_refs": [
                    text(source_slice.get("source_slice_ref"))
                    for source_slice in selected_slices
                    if text(source_slice.get("source_slice_ref"))
                ],
            }
        )
    results: list[dict[str, Any]] = []
    for row in by_object.values():
        group_index = row.pop("_claim_group_index")
        source_index = row.pop("_source_slice_index")
        row["claim_groups"] = list(group_index.values())
        row["cached_source_slices"] = list(source_index.values())
        allowed_group_keys = [text(group.get("group_key")) for group in row["claim_groups"] if text(group.get("group_key"))]
        allowed_claim_keys = list(dict.fromkeys(
            text(claim.get("claim_key"))
            for group in row["claim_groups"]
            for claim in group.get("claims") or []
            if text(claim.get("claim_key"))
        ))
        allowed_source_refs = [
            text(source_slice.get("source_slice_ref"))
            for source_slice in row["cached_source_slices"]
            if text(source_slice.get("source_slice_ref"))
        ]
        for event in row["events"]:
            event["allowed_group_keys"] = allowed_group_keys
            event["allowed_claim_keys"] = allowed_claim_keys
            event["allowed_source_slice_refs"] = allowed_source_refs
        results.append(row)
    return sorted(results, key=lambda row: (text(row["emperor_name"]), text(row["object_name"])))


def fetch_context_rows(
    *, dsn: str, schema_name: str, inventory_rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = [row for row in inventory_rows if text(row.get("record_type")) != "object_assessment"]
    emperors = sorted({text(row.get("emperor_name")) for row in events if text(row.get("emperor_name"))})
    object_ids = sorted({int(row.get("object_id")) for row in events if row.get("object_id")})
    object_names = sorted({text(row.get("object_name")) for row in events if text(row.get("object_name"))})
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                with memberships as (
                    select claim_key, array_agg(distinct group_key) as event_group_keys
                      from retrieval_v3.claim_event_group_members
                     group by claim_key
                ), evidence as (
                    select e.claim_key,
                           jsonb_agg(distinct jsonb_build_object(
                               'source_slice_ref', e.source_slice_ref,
                               'document_code', e.document_code,
                               'quote_preview', e.quote_preview,
                               'slice_text_preview', e.slice_text_preview
                           )) as evidence
                      from retrieval_v3.claim_evidence e
                     group by e.claim_key
                )
                select c.claim_key, c.emperor_name, c.object_id, c.object_name,
                       c.action_type, c.fact_type, c.office_or_domain, c.outcome,
                       c.outcome_support, c.claim_summary,
                       coalesce(m.event_group_keys, array[]::text[]) as event_group_keys,
                       coalesce(e.evidence, '[]'::jsonb) as evidence
                  from retrieval_v3.claim_cache c
                  left join memberships m on m.claim_key = c.claim_key
                  left join evidence e on e.claim_key = c.claim_key
                 where c.status::text = 'active'
                   and c.emperor_name = any(%s::text[])
                   and ((c.object_id is not null and c.object_id = any(%s::bigint[])) or c.object_name = any(%s::text[]))
                 order by c.emperor_name, c.object_name, c.claim_key
                """,
                (emperors, object_ids, object_names),
            )
            claim_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select slice_hash, object_id, object_name, document_code, source_title,
                       source_url, source_slice_ref, slice_text_preview
                  from retrieval_v3.claim_source_slices
                 where (object_id is not null and object_id = any(%s::bigint[])) or object_name = any(%s::text[])
                 order by object_name, document_code, source_slice_ref
                """,
                (object_ids, object_names),
            )
            source_rows = [dict(row) for row in cur.fetchall()]
    return claim_rows, source_rows


def prompt_for_task(task_code: str, workitems: Sequence[Mapping[str, Any]], output_path: Path) -> str:
    example = {
        "event_inventory_code": "EEI-EXAMPLE",
        "decision": "reextract_cached_source",
        "has_appointment": True,
        "has_duty": True,
        "has_outcome": False,
        "same_event": True,
        "group_keys": ["CEG-EXAMPLE"],
        "claim_keys": ["CLMK-EXAMPLE"],
        "source_slice_refs": ["OSS-EXAMPLE"],
        "missing_facets": ["outcome"],
        "confidence": "high",
        "review_note": "现有 claim 已覆盖任用和职责，同一缓存切片含结果，应先重抽 claim。",
    }
    return (
        "# retrieval_v3 expected-event reconciliation\n\n"
        "你只使用 workitem 提供的 candidate_groups、claims、evidence 和 candidate_cached_slices，禁止联网，禁止使用历史记忆补事实。"
        "任务是判断 expected event 是否已被现有材料解决，以及下一步最窄动作；不做评分、binding、factorization 或数据库写入。\n"
        "每个 event_inventory_code 恰好输出一行。decision 只能是：\n"
        "- already_covered：同一 event group 的 claims 明确覆盖任用/授权、具体职责和结果；\n"
        "- rebuild_event_group：现有 claims 已覆盖同一事件的全部 facet，但被拆在多个 group；\n"
        "- reextract_cached_source：现有 claim 不完整，但提供的缓存切片明确含缺失 facet；\n"
        "- fetch_missing_source：现有 claims 与缓存切片都不含缺失事实，确需新回源；\n"
        "- inventory_needs_review：inventory 事件过宽、复合多个事件、偏离 appointment_delegation，不能直接触发回源；\n"
        "- identity_mismatch：候选材料明确属于其他人物或时期。\n"
        "语义等价可以通过，不要求逐字匹配；但 already_covered 必须引用实际 group_key 和 claim_key，结果不能由人物名气推断。"
        "rebuild_event_group 必须引用至少两个实际 group_key；reextract_cached_source 必须引用实际 source_slice_ref。"
        "fetch_missing_source 只能在最相近的 groups/slices 均不能支撑时使用。引用值只能来自当前 event 候选。\n"
        "has_appointment/has_duty/has_outcome/same_event 必须为布尔值；missing_facets 只能从 appointment/duty/outcome/same_event 中选择。"
        "missing_facets 必须恰好列出所有值为 false 的 facet，不能少写或多写。"
        "confidence 只能 high/medium/low，review_note 用一句中文说明。示例值含 EXAMPLE，严禁复制。\n"
        f"唯一允许写入 `{output_path.as_posix()}`；若不能写文件，最终回复只能输出 {PATCH_BEGIN}/{PATCH_END} 包住的 JSONL。"
        f"task_code: {task_code}\n\n{PATCH_BEGIN}\n{json.dumps(example, ensure_ascii=False, sort_keys=True)}\n{PATCH_END}\n\n"
        "## Workitems\n\n```json\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    step = max(1, int(size))
    return [list(rows[index:index + step]) for index in range(0, len(rows), step)]


def write_tasks(workitems: Sequence[Mapping[str, Any]], output_root: Path, *, batch_size: int) -> dict[str, Any]:
    runtime = agent_runtime_config.resolve_agent_stage("v3_expected_event_reconciliation")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "workitems.jsonl").write_text(
        "".join(stable_json(dict(row)) + "\n" for row in workitems), encoding="utf-8", newline="\n"
    )
    tasks: list[dict[str, Any]] = []
    for index, batch in enumerate(chunks(workitems, batch_size), start=1):
        task_code = stable_code("EERT-", [row.get("workitem_code") for row in batch])
        prompt_path = output_root / "prompts" / f"{task_code}.md"
        patch_path = output_root / "patches" / f"{task_code}.jsonl"
        last_path = output_root / "logs" / f"{task_code}.last.md"
        log_path = output_root / "logs" / f"{task_code}.jsonl"
        for path in (prompt_path, patch_path, last_path, log_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_task(task_code, batch, patch_path), encoding="utf-8", newline="\n")
        tasks.append(
            {
                "task_code": task_code,
                "task_kind": "retrieval_v3_expected_event_reconciliation",
                "batch_index": index,
                "workitem_codes": [text(row.get("workitem_code")) for row in batch],
                "prompt_path": str(prompt_path),
                "last_message_path": str(last_path),
                "log_path": str(log_path),
                "expected_outputs": [{
                    "kind": "jsonl_patch",
                    "path": str(patch_path),
                    "fallback": "last_message_marked_block",
                    "begin": PATCH_BEGIN,
                    "end": PATCH_END,
                }],
                "argv": agent_runtime_config.codex_task_argv("v3_expected_event_reconciliation"),
            }
        )
    tasks_path = output_root / "codex_tasks.jsonl"
    tasks_path.write_text("".join(stable_json(row) + "\n" for row in tasks), encoding="utf-8", newline="\n")
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_expected_event_reconciliation.py tasks",
        "workitem_count": len(workitems),
        "event_count": sum(len(row.get("events") or []) for row in workitems),
        "task_count": len(tasks),
        "batch_size": max(1, int(batch_size)),
        "agent_runtime": runtime,
        "tasks_jsonl": str(tasks_path),
        "write_db": False,
        "scoring_allowed": False,
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def allowed_refs(event: Mapping[str, Any]) -> tuple[set[str], set[str], set[str]]:
    groups = set(list_texts(event.get("allowed_group_keys")))
    claims = set(list_texts(event.get("allowed_claim_keys")))
    slices = set(list_texts(event.get("allowed_source_slice_refs")))
    return groups, claims, slices


def validate_result(row: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    code = text(row.get("event_inventory_code"))
    if code != text(event.get("event_inventory_code")):
        raise ExpectedEventReconciliationError(f"unexpected event_inventory_code: {code!r}")
    serialized = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    if any(fragment in serialized for fragment in PLACEHOLDER_FRAGMENTS):
        raise ExpectedEventReconciliationError(f"{code}: copied prompt placeholder")
    decision = text(row.get("decision"))
    confidence = text(row.get("confidence"))
    if decision not in DECISIONS or confidence not in CONFIDENCE_LEVELS:
        raise ExpectedEventReconciliationError(f"{code}: invalid finite value")
    booleans = {field: row.get(f"has_{field}") if field != "same_event" else row.get(field) for field in FACETS}
    if any(not isinstance(value, bool) for value in booleans.values()):
        raise ExpectedEventReconciliationError(f"{code}: facet flags must be booleans")
    missing = list_texts(row.get("missing_facets"))
    if any(value not in FACETS for value in missing):
        raise ExpectedEventReconciliationError(f"{code}: invalid missing_facets")
    expected_missing = {field for field, present in booleans.items() if not present}
    if set(missing) != expected_missing:
        raise ExpectedEventReconciliationError(f"{code}: missing_facets must match false facet flags")
    group_keys = list_texts(row.get("group_keys"))
    claim_keys = list_texts(row.get("claim_keys"))
    source_refs = list_texts(row.get("source_slice_refs"))
    allowed_groups, allowed_claims, allowed_slices = allowed_refs(event)
    if not set(group_keys) <= allowed_groups or not set(claim_keys) <= allowed_claims or not set(source_refs) <= allowed_slices:
        raise ExpectedEventReconciliationError(f"{code}: cited reference outside candidates")
    if decision == "already_covered" and (not all(booleans.values()) or not group_keys or not claim_keys):
        raise ExpectedEventReconciliationError(f"{code}: already_covered requires all facets and cited group/claim")
    if decision == "rebuild_event_group" and (not all(booleans.values()) or len(group_keys) < 2 or not claim_keys):
        raise ExpectedEventReconciliationError(f"{code}: rebuild_event_group requires all facets and multiple groups")
    if decision == "reextract_cached_source" and not source_refs:
        raise ExpectedEventReconciliationError(f"{code}: reextract_cached_source requires cached source refs")
    return {
        "event_inventory_code": code,
        "emperor_name": text(event.get("emperor_name")),
        "object_id": event.get("object_id"),
        "object_name": text(event.get("object_name")),
        "event_label": text(event.get("event_label")),
        "importance": text(event.get("importance")),
        "decision": decision,
        "has_appointment": booleans["appointment"],
        "has_duty": booleans["duty"],
        "has_outcome": booleans["outcome"],
        "same_event": booleans["same_event"],
        "group_keys": group_keys,
        "claim_keys": claim_keys,
        "source_slice_refs": source_refs,
        "missing_facets": missing,
        "confidence": confidence,
        "review_note": text(row.get("review_note")),
        "write_db": False,
        "scoring_allowed": False,
    }


def merge_results(
    tasks_root: Path, *, min_existing_source_resolution_rate: float, patch_roots: Sequence[Path] = ()
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workitems = read_jsonl(tasks_root / "workitems.jsonl")
    events = {
        text(event.get("event_inventory_code")): {
            **dict(event),
            "emperor_name": text(workitem.get("emperor_name")),
            "object_id": workitem.get("object_id"),
            "object_name": text(workitem.get("object_name")),
        }
        for workitem in workitems
        for event in workitem.get("events") or []
    }
    roots = [tasks_root / "patches", *patch_roots]
    patch_rows = [row for root in roots for path in sorted(root.glob("*.jsonl")) for row in read_jsonl(path)]
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for row in patch_rows:
        code = text(row.get("event_inventory_code"))
        if code in seen:
            errors.append(f"duplicate result: {code}")
            continue
        event = events.get(code)
        if event is None:
            errors.append(f"unknown event_inventory_code: {code}")
            continue
        seen.add(code)
        try:
            results.append(validate_result(row, event))
        except ExpectedEventReconciliationError as exc:
            errors.append(str(exc))
    missing = sorted(set(events) - seen)
    decision_counts = Counter(row["decision"] for row in results)
    resolved_count = sum(row["decision"] in RESOLVED_WITHOUT_NEW_SOURCE for row in results)
    denominator = len(events)
    rate = resolved_count / denominator if denominator else 1.0
    complete = not errors and not missing and len(results) == denominator
    gate_passed = complete and rate >= float(min_existing_source_resolution_rate)
    report = {
        "ok": complete,
        "generated_by": "scripts/dev/retrieval_v3_expected_event_reconciliation.py merge",
        "write_db": False,
        "scoring_allowed": False,
        "event_count": denominator,
        "validated_result_count": len(results),
        "decision_counts": dict(sorted(decision_counts.items())),
        "resolved_without_new_source_count": resolved_count,
        "existing_source_resolution_rate": round(rate, 6),
        "min_existing_source_resolution_rate": float(min_existing_source_resolution_rate),
        "gate_passed": gate_passed,
        "progress_allowed": gate_passed,
        "missing_event_codes": missing,
        "errors": errors,
        "results": results,
        "next_action": "continue_existing_source_repairs" if gate_passed else "stop_and_optimize_reconciliation",
    }
    return results, report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 expected-event reconciliation gate",
        "",
        f"- ok: `{str(bool(report.get('ok'))).lower()}`",
        f"- gate_passed: `{str(bool(report.get('gate_passed'))).lower()}`",
        f"- progress_allowed: `{str(bool(report.get('progress_allowed'))).lower()}`",
        f"- events: `{report.get('event_count', 0)}`",
        f"- existing-source resolution rate: `{float(report.get('existing_source_resolution_rate', 0)):.1%}`",
        f"- minimum rate: `{float(report.get('min_existing_source_resolution_rate', 0)):.1%}`",
        f"- next_action: `{report.get('next_action')}`",
        "",
        "| decision | count |",
        "| --- | ---: |",
    ]
    for decision, count in (report.get("decision_counts") or {}).items():
        lines.append(f"| {decision} | {count} |")
    if report.get("errors") or report.get("missing_event_codes"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {value}" for value in report.get("errors") or [])
        lines.extend(f"- missing: {value}" for value in report.get("missing_event_codes") or [])
    return "\n".join(lines) + "\n"


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(dict(row)) + "\n" for row in rows), encoding="utf-8", newline="\n")


def local_source_cache_rows(cache_root: Path) -> list[dict[str, Any]]:
    path = cache_root / "mention_slices.jsonl"
    if not path.exists():
        raise ExpectedEventReconciliationError(f"local source cache missing mention_slices.jsonl: {cache_root}")
    rows: list[dict[str, Any]] = []
    for raw in read_jsonl(path):
        rows.append(
            {
                "slice_hash": text(raw.get("quote_hash")),
                "object_id": None,
                "object_name": text(raw.get("person_name")),
                "document_code": text(raw.get("document_cache_code")),
                "source_title": text(raw.get("source_title")),
                "source_url": "",
                "source_slice_ref": text(raw.get("slice_cache_code")),
                "slice_text_preview": text(raw.get("raw_text")),
                "source_cache_root": str(cache_root),
            }
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile expected events against current v3 claims and cached sources.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    tasks = subparsers.add_parser("tasks")
    tasks.add_argument("--inventory-jsonl", type=Path, required=True)
    tasks.add_argument("--env-file", type=Path)
    tasks.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    tasks.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    tasks.add_argument("--output-root", type=Path, required=True)
    tasks.add_argument("--source-cache-root", type=Path, action="append", default=[])
    tasks.add_argument("--object-name", action="append", default=[])
    tasks.add_argument("--batch-size", type=int)
    tasks.add_argument("--max-groups", type=int, default=3)
    tasks.add_argument("--max-slices", type=int, default=2)
    merge = subparsers.add_parser("merge")
    merge.add_argument("--tasks-root", type=Path, required=True)
    merge.add_argument("--patch-root", type=Path, action="append", default=[])
    merge.add_argument("--min-existing-source-resolution-rate", type=float, default=DEFAULT_MIN_EXISTING_SOURCE_RESOLUTION_RATE)
    merge.add_argument("--output-jsonl", type=Path, required=True)
    merge.add_argument("--output-report-json", type=Path, required=True)
    merge.add_argument("--output-report-md", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "tasks":
        if args.env_file is not None:
            load_env_file(args.env_file)
        inventory_rows = read_jsonl(args.inventory_jsonl)
        selected_names = {normalize_object_alias(value) for value in args.object_name if text(value)}
        if selected_names:
            inventory_rows = [
                row for row in inventory_rows if normalize_object_alias(row.get("object_name")) in selected_names
            ]
        claim_rows, source_rows = fetch_context_rows(
            dsn=resolve_dsn(args.dsn_env), schema_name=args.pg_schema, inventory_rows=inventory_rows
        )
        for cache_root in args.source_cache_root:
            source_rows.extend(local_source_cache_rows(cache_root))
        workitems = build_workitems(
            inventory_rows, claim_rows, source_rows, max_groups=max(1, args.max_groups), max_slices=max(1, args.max_slices)
        )
        runtime = agent_runtime_config.resolve_agent_stage("v3_expected_event_reconciliation")
        summary = write_tasks(workitems, args.output_root, batch_size=int(args.batch_size or runtime["batch_size"]))
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    results, report = merge_results(
        args.tasks_root,
        min_existing_source_resolution_rate=args.min_existing_source_resolution_rate,
        patch_roots=args.patch_root,
    )
    write_jsonl(args.output_jsonl, results)
    write_json(args.output_report_json, report)
    args.output_report_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_report_md.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("ok", "gate_passed", "event_count", "existing_source_resolution_rate")}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
