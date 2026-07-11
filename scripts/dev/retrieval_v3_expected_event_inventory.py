from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_unseeded_actor_discovery import stable_code, text  # noqa: E402
from scripts.dev.retrieval_v3_unseeded_actor_review_tasks import PATCH_BEGIN, PATCH_END, stable_json  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


VERDICTS = {"events_expected", "no_relevant_events", "identity_mismatch_needs_review"}
DIRECTIONS = {"positive", "negative"}
IMPORTANCE_LEVELS = {"major", "secondary"}
DOMAINS = {"military", "civil", "institutional", "strategic", "fiscal", "frontier", "royal_clan"}
MAX_EVENTS_PER_OBJECT = 10
PLACEHOLDER_FRAGMENTS = ("示例", "某项", "制度名", "相关制度")
EXPLICIT_OUTCOME_MARKERS = (
    "被擒",
    "擒获",
    "俘",
    "平定",
    "灭",
    "破",
    "大溃",
    "败",
    "亡",
    "降",
    "归附",
    "克",
    "攻取",
    "颁行",
    "施行",
    "完成",
    "成书",
    "书成",
    "编成",
    "修举",
    "无滞",
    "安静",
    "平稳",
    "即位",
    "确定",
    "明验",
    "定谳",
    "班师",
    "退师",
    "无功",
    "有成",
    "称职",
    "畏威",
    "被杀",
    "伏诛",
    "被废",
    "废黜",
    "被立",
    "册立",
    "撤军",
    "脱身",
    "得还",
    "皆喜",
    "乏食",
    "复振",
    "解围",
    "失守",
    "不救",
    "断绝",
    "绝粮",
    "复梁",
    "自刎",
    "败走",
    "退走",
    "逃走",
    "得脱",
    "获胜",
    "全胜",
    "奏捷",
    "立为",
    "受降",
    "虏",
    "受学",
    "进学",
    "学成",
    "明白",
    "民安",
    "政成",
    "赐死",
    "民甚便",
    "定税",
    "势蹙",
    "解兵",
    "师还",
    "遇害",
    "大掠",
    "作乱",
    "贳",
    "无罪",
    "专权",
    "案发",
    "牵连",
    "悉定",
    "不敢犯",
    "遂足",
    "走元将",
    "定处州",
    "所定",
    "形成",
    "升平",
    "从之",
    "不决",
)
OUTCOME_VERB_CHARS = frozenset("破下克取获虏擒俘降灭平复据塞罢袭亨杀诛废立成施完溃败亡退还喜振解失救绝崩")


class ExpectedEventInventoryError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ExpectedEventInventoryError(f"{path}: expected JSON object")
    return dict(payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExpectedEventInventoryError(f"{path}:{line_no}: invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise ExpectedEventInventoryError(f"{path}:{line_no}: expected object")
        rows.append(dict(payload))
    return rows


def unique_texts(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    result: list[str] = []
    for item in value:
        normalized = text(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return result[:limit]


def select_workitems(
    report: Mapping[str, Any],
    *,
    emperors: Sequence[str] = (),
    objects: Sequence[str] = (),
    excluded_objects: Sequence[str] = (),
    coverage_statuses: Sequence[str] = (),
    limit: int = 0,
) -> list[dict[str, Any]]:
    emperor_filter = {text(value) for value in emperors if text(value)}
    object_filter = {text(value) for value in objects if text(value)}
    excluded_object_filter = {text(value) for value in excluded_objects if text(value)}
    status_filter = {text(value) for value in coverage_statuses if text(value)}
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for raw_row in report.get("objects") or []:
        if not isinstance(raw_row, Mapping):
            continue
        emperor = text(raw_row.get("emperor_name"))
        object_name = text(raw_row.get("object_name"))
        status = text(raw_row.get("coverage_status"))
        object_id = int(raw_row["object_id"]) if raw_row.get("object_id") is not None else None
        if emperor_filter and emperor not in emperor_filter:
            continue
        if object_filter and object_name not in object_filter:
            continue
        if object_name in excluded_object_filter:
            continue
        if status_filter and status not in status_filter:
            continue
        if not emperor or not object_name:
            continue
        key = (emperor, object_id, object_name)
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            {
                "workitem_code": stable_code("EEIW-", emperor, object_id, object_name),
                "emperor_name": emperor,
                "object_id": object_id,
                "object_name": object_name,
                "object_type": text(raw_row.get("object_type")),
                "item_code": text(report.get("item_code")) or "I5B",
                "rule_code": text(report.get("rule_code")) or "appointment_delegation",
                "observed_pipeline": {
                    key: raw_row.get(key)
                    for key in (
                        "source_slice_count",
                        "claimed_source_slice_count",
                        "active_claim_count",
                        "event_group_count",
                        "material_claim_count",
                        "candidate_count",
                        "binding_count",
                        "factor_judgment_count",
                        "coverage_status",
                    )
                },
                "task_boundary": {
                    "retrieval_leads_only": True,
                    "scoring_allowed": False,
                    "database_write_allowed": False,
                    "max_events": MAX_EVENTS_PER_OBJECT,
                },
            }
        )
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    step = max(1, int(size))
    return [list(rows[index:index + step]) for index in range(0, len(rows), step)]


def prompt_for_task(task_code: str, workitems: Sequence[Mapping[str, Any]], output_path: Path) -> str:
    example = {
        "workitem_code": "EEIW-...",
        "inventory_verdict": "events_expected",
        "identity_note": "人物身份与目标皇帝时期相符。",
        "events": [
            {
                "event_label": "负责某项制度并形成明确结果",
                "direction": "positive",
                "importance": "major",
                "domain": "institutional",
                "event_anchor_terms": ["制度名", "主持"],
                "duty_anchor_terms": ["修订", "负责"],
                "outcome_anchor_terms": ["施行", "完成"],
                "source_leads": [
                    {"source_title": "正史人物本传", "locator_hint": "本传相关段落", "query_terms": ["制度名", "施行"]}
                ],
                "lead_note": "只作为回源检索线索，必须由原始史料核验。",
            }
        ],
        "coverage_note": "优先核对重大制度成果是否已形成同事件任用、职责、结果链。",
    }
    return (
        "# retrieval_v3 expected-event inventory\n\n"
        "你生成的是 appointment_delegation 历史覆盖审计的检索线索，不是史料证据、claim、binding、因子或分数。"
        "允许使用稳定的基础历史知识帮助列出待回源核验的事件，但不得把记忆当证据；每个事件后续都必须由原始或准原始史源验证。\n"
        "对每个具名对象，独立列出其在目标皇帝时期最重要的任用/授权事件：必须包含皇帝任用或交付权责、该对象的具体任务或职责、"
        "以及可检索的结果/反馈。将重大军事行动的最终战果、重大制度建设成果、重大政治任务结果纳入；负向则要求任用链上的实际失败或损害。"
        "不要受 observed_pipeline 数量影响：即使现有 claims/bindings 很多，也要独立检查著名重大事件是否遗漏。"
        "不要使用相邻项切分或其他 rule 排除话术；凡符合 appointment_delegation 说明的事件都列入。\n"
        "events 最多 10 条，只收 major/secondary；不要收人物总评、单纯受赏罚、单纯被处置、无具体职责的泛泛任官或只有战役小环节而无结果的条目。"
        "event_anchor_terms、duty_anchor_terms、outcome_anchor_terms 应使用史料中可能出现的短语或专名，分别至少 1 条；"
        "每个 outcome_anchor_term 自身必须描述明确结果，例如被擒、灭、平定、颁行、完成、不克、班师；"
        "年代、地点、官名、书名、对象名和泛称政事不能作为 outcome anchor。若找不到明确结果，该事件不要输出。"
        "source_leads 至少 1 条，优先正史本传、本纪、实录、政书或可靠公开古籍页面。\n"
        "inventory_verdict 只能是 events_expected、no_relevant_events、identity_mismatch_needs_review。"
        "若人物与目标皇帝年代明显不符，选 identity_mismatch_needs_review，不要硬造事件。"
        "示例中的示例对象、某项、制度名、正史人物本传等都是结构占位符，严禁复制到正式输出；必须换成该对象的具体事件、专名和史源。"
        "每个 workitem_code 恰好输出一行，字段和值必须与示例一致；direction 只能 positive/negative，importance 只能 major/secondary，"
        "domain 只能 military/civil/institutional/strategic/fiscal/frontier/royal_clan。\n"
        f"唯一允许写入 `{output_path.as_posix()}`，不要修改代码、数据库或其他文件。task_code: {task_code}\n"
        f"若无法写文件，最终回复只能输出 {PATCH_BEGIN}/{PATCH_END} 包住的完整 JSONL。\n\n"
        f"{PATCH_BEGIN}\n{json.dumps(example, ensure_ascii=False, sort_keys=True)}\n{PATCH_END}\n\n"
        "## Workitems\n\n```json\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def write_tasks(workitems: Sequence[Mapping[str, Any]], output_root: Path, *, batch_size: int) -> dict[str, Any]:
    runtime = agent_runtime_config.resolve_agent_stage("v3_expected_event_inventory")
    output_root.mkdir(parents=True, exist_ok=True)
    workitems_path = output_root / "workitems.jsonl"
    workitems_path.write_text(
        "".join(stable_json(dict(row)) + "\n" for row in workitems), encoding="utf-8", newline="\n"
    )
    tasks: list[dict[str, Any]] = []
    for batch_index, batch in enumerate(chunks(workitems, batch_size), start=1):
        task_code = stable_code("EEIT-", [row.get("workitem_code") for row in batch])
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
                "task_kind": "retrieval_v3_expected_event_inventory",
                "batch_index": batch_index,
                "workitem_codes": [text(row.get("workitem_code")) for row in batch],
                "prompt_path": str(prompt_path),
                "last_message_path": str(last_path),
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
                "argv": agent_runtime_config.codex_task_argv("v3_expected_event_inventory"),
            }
        )
    tasks_path = output_root / "codex_tasks.jsonl"
    tasks_path.write_text("".join(stable_json(row) + "\n" for row in tasks), encoding="utf-8", newline="\n")
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_expected_event_inventory.py tasks",
        "workitem_count": len(workitems),
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


def require_text_list(row: Mapping[str, Any], key: str, *, max_items: int = 8) -> list[str]:
    values = unique_texts(row.get(key), limit=max_items)
    if not values:
        raise ExpectedEventInventoryError(f"{key}: expected 1-{max_items} non-empty strings")
    return values


def is_explicit_outcome_term(value: str) -> bool:
    term = text(value)
    return any(marker in term for marker in EXPLICIT_OUTCOME_MARKERS) or (
        len(term) >= 3 and any(character in OUTCOME_VERB_CHARS for character in term)
    )


def validate_source_leads(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ExpectedEventInventoryError("source_leads: expected non-empty list")
    leads: list[dict[str, Any]] = []
    for raw_lead in list(value)[:5]:
        if not isinstance(raw_lead, Mapping) or not text(raw_lead.get("source_title")):
            raise ExpectedEventInventoryError("source_leads: source_title is required")
        leads.append(
            {
                "source_title": text(raw_lead.get("source_title")),
                "locator_hint": text(raw_lead.get("locator_hint")),
                "query_terms": require_text_list(raw_lead, "query_terms", max_items=8),
            }
        )
    return leads


def validate_patch_row(row: Mapping[str, Any], workitem: Mapping[str, Any]) -> dict[str, Any]:
    code = text(row.get("workitem_code"))
    if code != text(workitem.get("workitem_code")):
        raise ExpectedEventInventoryError(f"unexpected workitem_code: {code!r}")
    verdict = text(row.get("inventory_verdict"))
    if verdict not in VERDICTS:
        raise ExpectedEventInventoryError(f"{code}: invalid inventory_verdict {verdict!r}")
    raw_events = row.get("events") or []
    if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)):
        raise ExpectedEventInventoryError(f"{code}: events must be a list")
    if verdict == "events_expected" and not raw_events:
        raise ExpectedEventInventoryError(f"{code}: events_expected requires events")
    if verdict != "events_expected" and raw_events:
        raise ExpectedEventInventoryError(f"{code}: {verdict} must not include events")
    if len(raw_events) > MAX_EVENTS_PER_OBJECT:
        raise ExpectedEventInventoryError(f"{code}: too many events")
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            raise ExpectedEventInventoryError(f"{code}: event must be an object")
        serialized_event = json.dumps(raw_event, ensure_ascii=False, sort_keys=True, default=str)
        copied_placeholders = [fragment for fragment in PLACEHOLDER_FRAGMENTS if fragment in serialized_event]
        if copied_placeholders:
            raise ExpectedEventInventoryError(f"{code}: copied prompt placeholder(s): {', '.join(copied_placeholders)}")
        label = text(raw_event.get("event_label"))
        direction = text(raw_event.get("direction"))
        importance = text(raw_event.get("importance"))
        domain = text(raw_event.get("domain"))
        if not label or label in seen:
            raise ExpectedEventInventoryError(f"{code}: event_label must be non-empty and unique")
        if direction not in DIRECTIONS or importance not in IMPORTANCE_LEVELS or domain not in DOMAINS:
            raise ExpectedEventInventoryError(f"{code}/{label}: invalid finite value")
        seen.add(label)
        raw_event_terms = require_text_list(raw_event, "event_anchor_terms")
        subject_terms = {
            text(workitem.get("object_name")),
            text(workitem.get("emperor_name")),
        }
        event_terms = [term for term in raw_event_terms if term not in subject_terms]
        dropped_subject_terms = [term for term in raw_event_terms if term not in event_terms]
        if not event_terms:
            raise ExpectedEventInventoryError(f"{code}/{label}: event_anchor_terms only repeat the object or emperor name")
        duty_terms = require_text_list(raw_event, "duty_anchor_terms")
        raw_outcome_terms = require_text_list(raw_event, "outcome_anchor_terms")
        outcome_terms = [term for term in raw_outcome_terms if is_explicit_outcome_term(term)]
        dropped_outcome_terms = [term for term in raw_outcome_terms if term not in outcome_terms]
        if not outcome_terms:
            raise ExpectedEventInventoryError(f"{code}/{label}: outcome_anchor_terms lack an explicit result marker")
        events.append(
            {
                "event_inventory_code": stable_code(
                    "EEI-", workitem.get("emperor_name"), workitem.get("object_id"), label, event_terms, outcome_terms
                ),
                "record_type": "expected_event",
                "workitem_code": code,
                "emperor_name": text(workitem.get("emperor_name")),
                "object_id": workitem.get("object_id"),
                "object_name": text(workitem.get("object_name")),
                "object_type": text(workitem.get("object_type")),
                "item_code": text(workitem.get("item_code")),
                "rule_code": text(workitem.get("rule_code")),
                "event_label": label,
                "direction": direction,
                "importance": importance,
                "domain": domain,
                "event_anchor_terms": event_terms,
                "dropped_subject_anchor_terms": dropped_subject_terms,
                "duty_anchor_terms": duty_terms,
                "outcome_anchor_terms": outcome_terms,
                "dropped_non_result_outcome_terms": dropped_outcome_terms,
                "source_leads": validate_source_leads(raw_event.get("source_leads")),
                "lead_note": text(raw_event.get("lead_note")),
                "evidence_status": "retrieval_lead_only",
                "scoring_allowed": False,
            }
        )
    return {
        "workitem_code": code,
        "emperor_name": text(workitem.get("emperor_name")),
        "object_name": text(workitem.get("object_name")),
        "inventory_verdict": verdict,
        "identity_note": text(row.get("identity_note")),
        "coverage_note": text(row.get("coverage_note")),
        "events": events,
    }


def merge_patches(tasks_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workitems = read_jsonl(tasks_root / "workitems.jsonl")
    lookup = {text(row.get("workitem_code")): row for row in workitems}
    patch_rows = [row for path in sorted((tasks_root / "patches").glob("*.jsonl")) for row in read_jsonl(path)]
    seen: set[str] = set()
    reviews: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in patch_rows:
        code = text(row.get("workitem_code"))
        if code in seen:
            errors.append(f"duplicate patch row: {code}")
            continue
        workitem = lookup.get(code)
        if workitem is None:
            errors.append(f"unknown workitem_code: {code}")
            continue
        seen.add(code)
        try:
            reviews.append(validate_patch_row(row, workitem))
        except ExpectedEventInventoryError as exc:
            errors.append(str(exc))
    missing = sorted(set(lookup) - seen)
    events = [event for review in reviews for event in review["events"]]
    assessment_rows = [
        {
            "record_type": "object_assessment",
            "object_assessment_code": stable_code(
                "EEIA-", review.get("emperor_name"), review.get("object_name"), review.get("inventory_verdict")
            ),
            "workitem_code": review.get("workitem_code"),
            "emperor_name": review.get("emperor_name"),
            "object_name": review.get("object_name"),
            "inventory_verdict": review.get("inventory_verdict"),
            "identity_note": review.get("identity_note"),
            "coverage_note": review.get("coverage_note"),
            "evidence_status": "retrieval_lead_only",
            "scoring_allowed": False,
        }
        for review in reviews
        if review["inventory_verdict"] != "events_expected"
    ]
    inventory_rows = [*events, *assessment_rows]
    verdict_counts = Counter(review["inventory_verdict"] for review in reviews)
    importance_counts = Counter(event["importance"] for event in events)
    report = {
        "ok": not errors and not missing,
        "generated_by": "scripts/dev/retrieval_v3_expected_event_inventory.py merge",
        "write_db": False,
        "scoring_allowed": False,
        "workitem_count": len(workitems),
        "patch_row_count": len(patch_rows),
        "validated_review_count": len(reviews),
        "event_count": len(events),
        "object_assessment_count": len(assessment_rows),
        "inventory_record_count": len(inventory_rows),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "importance_counts": dict(sorted(importance_counts.items())),
        "missing_workitem_codes": missing,
        "errors": errors,
        "reviews": reviews,
    }
    return inventory_rows, report


def render_merge_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 预期事件 inventory 合并报告",
        "",
        f"- ok: `{str(bool(report.get('ok'))).lower()}`",
        "- write_db: `false`",
        f"- workitems: `{report.get('workitem_count', 0)}`",
        f"- events: `{report.get('event_count', 0)}`",
        "",
        "> inventory 只用于触发回源与覆盖对账，不是史料证据，不允许直接入分。",
        "",
        "| 皇帝 | 对象 | verdict | 事件数 |",
        "| --- | --- | --- | ---: |",
    ]
    for review in report.get("reviews") or []:
        lines.append(
            f"| {text(review.get('emperor_name'))} | {text(review.get('object_name'))} | "
            f"{text(review.get('inventory_verdict'))} | {len(review.get('events') or [])} |"
        )
    if report.get("errors") or report.get("missing_workitem_codes"):
        lines.extend(["", "## 错误", ""])
        lines.extend(f"- {value}" for value in report.get("errors") or [])
        lines.extend(f"- missing: {value}" for value in report.get("missing_workitem_codes") or [])
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(dict(row)) + "\n" for row in rows), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate retrieval-lead-only expected event inventories.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    tasks = subparsers.add_parser("tasks")
    tasks.add_argument("--input-coverage-json", type=Path, required=True)
    tasks.add_argument("--output-root", type=Path, required=True)
    tasks.add_argument("--emperor", action="append", default=[])
    tasks.add_argument("--object", action="append", default=[])
    tasks.add_argument("--exclude-object", action="append", default=[])
    tasks.add_argument("--coverage-status", action="append", default=[])
    tasks.add_argument("--limit", type=int, default=0)
    tasks.add_argument("--batch-size", type=int)
    merge = subparsers.add_parser("merge")
    merge.add_argument("--tasks-root", type=Path, required=True)
    merge.add_argument("--output-jsonl", type=Path, required=True)
    merge.add_argument("--output-report-json", type=Path, required=True)
    merge.add_argument("--output-report-md", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "tasks":
        runtime = agent_runtime_config.resolve_agent_stage("v3_expected_event_inventory")
        coverage_statuses = args.coverage_status or ([] if args.object else ["complete"])
        workitems = select_workitems(
            read_json(args.input_coverage_json),
            emperors=args.emperor,
            objects=args.object,
            excluded_objects=args.exclude_object,
            coverage_statuses=coverage_statuses,
            limit=max(0, args.limit),
        )
        summary = write_tasks(workitems, args.output_root, batch_size=int(args.batch_size or runtime["batch_size"]))
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    events, report = merge_patches(args.tasks_root)
    write_jsonl(args.output_jsonl, events)
    write_json(args.output_report_json, report)
    args.output_report_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_report_md.write_text(render_merge_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("ok", "workitem_count", "event_count")}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
