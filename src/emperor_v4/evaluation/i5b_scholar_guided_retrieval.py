from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlparse

import yaml

from emperor_v4.evaluation.i5b_scholarly_object_profile import (
    build_scholarly_object_profile_report,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_SCHEMA_VERSION = "i5b-scholar-guided-retrieval-contract-v1"
TASK_SCHEMA_VERSION = "i5b-scholar-guided-retrieval-task-v1"
REPORT_SCHEMA_VERSION = "i5b-scholar-guided-retrieval-report-v1"
RULE_CODES = {
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
}
SUBJECT_KINDS = {"person", "institution", "policy"}
QUERY_MODES = {
    "person_event",
    "governance_output",
    "institution_operation",
    "policy_implementation",
}


def _load(path: Path) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"学术引导检索输入顶层必须为对象: {path}")
    return value


def _strings(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} 必须为字符串列表")
    values = tuple(str(item).strip() for item in value)
    if not values or "" in values or len(values) != len(set(values)):
        raise ValueError(f"{label} 必须非空且唯一")
    return values


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _wikisource_page_title(canonical_url: str) -> str | None:
    parsed = urlparse(canonical_url)
    if parsed.netloc != "zh.wikisource.org" or not parsed.path.startswith("/wiki/"):
        return None
    title = unquote(parsed.path.removeprefix("/wiki/")).replace("_", " ").strip()
    return title or None


def build_scholar_guided_retrieval_report(
    *, mechanism_contract_path: Path, task_contract_path: Path
) -> dict[str, Any]:
    mechanism = _load(mechanism_contract_path)
    task = _load(task_contract_path)
    if mechanism.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("学术引导检索机制合同版本非法")
    if task.get("schema_version") != TASK_SCHEMA_VERSION:
        raise ValueError("学术引导检索任务合同版本非法")
    budget_path = ROOT / str(mechanism.get("work_budget_ref") or "")
    budget = _load(budget_path)
    if budget.get("schema_version") != "i5b-historical-work-budget-v1":
        raise ValueError("学术引导检索缺少工作预算")
    limits = budget.get("per_rule_run") or {}

    boundary = mechanism.get("safety_boundary") or {}
    expected_boundary = {
        "output_disposition": "candidate_only",
        "formal_fact_acceptance_allowed": False,
        "factor_choice_allowed": False,
        "score_contribution_allowed": False,
        "database_write_allowed": False,
        "migration_allowed": False,
    }
    if any(boundary.get(key) != value for key, value in expected_boundary.items()):
        raise ValueError("学术引导检索不得直接接受事实、选因子、计分、写库或迁移")

    trigger = mechanism.get("trigger_policy") or {}
    mandatory_kinds = set(
        _strings(trigger.get("mandatory_subject_kinds"), label="mandatory_subject_kinds")
    )
    mandatory_modes = set(
        _strings(trigger.get("mandatory_query_modes"), label="mandatory_query_modes")
    )
    if mandatory_kinds != {"institution", "policy"} or mandatory_modes != {
        "governance_output",
        "institution_operation",
        "policy_implementation",
    }:
        raise ValueError("制度、政策、治理产出必须强制触发学术引导检索")
    if trigger.get("person_event_skip_requires_primary_locator") is not True:
        raise ValueError("普通人物事件跳过学术通道时必须已有原始史料定位")

    rule_profiles = mechanism.get("rule_mechanisms") or {}
    if set(rule_profiles) != RULE_CODES:
        raise ValueError("学术引导检索必须覆盖第五项B全部 rule")
    for rule_code, profile in rule_profiles.items():
        predicates = _strings(
            profile.get("mechanism_predicates"),
            label=f"{rule_code}.mechanism_predicates",
        )
        if not predicates:
            raise ValueError(f"{rule_code} 缺少机制谓词")

    profile_ref = str(task.get("scholarly_profile_contract_ref") or "").strip()
    if not profile_ref:
        raise ValueError("学术引导任务缺少对象画像合同")
    profile_report = build_scholarly_object_profile_report(ROOT / profile_ref)
    profiles = {row["profile_ref"]: row for row in profile_report["profiles"]}

    ruler = task.get("ruler") or {}
    window = ruler.get("freeze_window") or {}
    if not str(ruler.get("ref") or "").strip() or not str(
        ruler.get("name") or ""
    ).strip() or window != {"start": 626, "end": 649}:
        raise ValueError("当前冻结任务必须明确李世民 626—649 窗口")

    cases: list[dict[str, Any]] = []
    source_cache_tasks: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for row in task.get("cases") or ():
        case_ref = str(row.get("case_ref") or "").strip()
        profile = profiles.get(str(row.get("profile_ref") or "").strip())
        subject_kind = str(row.get("subject_kind") or "").strip()
        query_mode = str(row.get("query_mode") or "").strip()
        rules = _strings(row.get("target_rules"), label=f"{case_ref}.target_rules")
        directions = _strings(
            row.get("search_directions"), label=f"{case_ref}.search_directions"
        )
        selection_keys = _strings(
            row.get("source_cache_selection_keys"),
            label=f"{case_ref}.source_cache_selection_keys",
        )
        if (
            not case_ref
            or case_ref in seen_cases
            or profile is None
            or subject_kind not in SUBJECT_KINDS
            or query_mode not in QUERY_MODES
            or not set(rules) <= RULE_CODES
            or set(directions) != {"positive", "negative"}
            or profile["subject"]["kind"] != subject_kind
        ):
            raise ValueError(f"学术引导检索案例非法: {case_ref}")

        required = subject_kind in mandatory_kinds or query_mode in mandatory_modes
        primary_locator_supplied = any(
            item["primary_source_locators"] for item in profile["summary_items"]
        )
        if not required and not primary_locator_supplied:
            raise ValueError(f"人物事件跳过强制学术检索但无原始史料定位: {case_ref}")

        requested_predicates = {
            rule_code: list(rule_profiles[rule_code]["mechanism_predicates"])
            for rule_code in rules
        }
        locators = [
            {
                **locator,
                "summary_ref": item["summary_ref"],
                "retrieval_terms": item["retrieval_terms"],
            }
            for item in profile["summary_items"]
            for locator in item["primary_source_locators"]
        ]
        task_code = f"{task['task_code']}:{case_ref}"
        source_cache_task = {
            "task_code": task_code,
            "case_ref": case_ref,
            "subject_ref": profile["subject"]["ref"],
            "subject_label": profile["subject"]["label"],
            "target_rules": list(rules),
            "search_directions": sorted(directions),
            "mechanism_predicates": requested_predicates,
            "primary_source_locators": locators,
            "required_source_cache_selection_keys": list(selection_keys),
            "source_cache_request": {
                "request_id": f"SRC-{task_code}",
                "idempotency_key": (
                    "source-cache:v4:scholar-guided:"
                    f"{sha256(task_code.encode('utf-8')).hexdigest()[:24]}"
                ),
                "subject": {
                    "person_or_ruler_ref": profile["subject"]["ref"],
                    "canonical_name": profile["subject"]["label"],
                    "aliases": [],
                },
                "evaluation_context": {
                    "purpose": "scholar_guided_primary_source_location",
                    "ruler": ruler["name"],
                    "reign_window": window,
                    "rules": list(rules),
                    "mechanism_predicates": requested_predicates,
                    "search_directions": sorted(directions),
                },
                "source_hints": sorted(
                    {
                        title
                        for locator in locators
                        if (title := _wikisource_page_title(locator["canonical_url"]))
                    }
                ),
                "required_source_families": ["primary_text"],
                "mode": "ensure",
                "source_policy_version": "v4-scholar-guided-primary-location-v1",
                "requested_at": str(task.get("requested_at") or ""),
            },
            "next_gate": "versioned_source_cache_then_candidate_judge",
            "disposition": "candidate_only",
        }
        source_cache_tasks.append(source_cache_task)
        cases.append(
            {
                "case_ref": case_ref,
                "profile_ref": profile["profile_ref"],
                "subject_kind": subject_kind,
                "query_mode": query_mode,
                "triggered": required,
                "trigger_reason": (
                    "mandatory_institution_policy_or_governance_query"
                    if required
                    else "person_event_primary_locator_reuse"
                ),
                "source_cache_task_code": task_code,
            }
        )
        seen_cases.add(case_ref)
    if not cases:
        raise ValueError("学术引导检索任务不得为空")
    rule_task_counts = {
        rule: sum(rule in row["target_rules"] for row in source_cache_tasks)
        for rule in sorted(RULE_CODES)
    }
    if any(
        count > int(limits["max_source_cache_tasks"])
        for count in rule_task_counts.values()
    ):
        raise ValueError("学术引导 Source Cache 任务超过单轮预算")

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "candidate_tasks_ready_for_source_cache",
        "task_code": task["task_code"],
        "ruler": ruler,
        "mechanism_contract_sha256": sha256(
            (mechanism_contract_path if mechanism_contract_path.is_absolute() else ROOT / mechanism_contract_path).read_bytes()
        ).hexdigest(),
        "task_contract_sha256": sha256(
            (task_contract_path if task_contract_path.is_absolute() else ROOT / task_contract_path).read_bytes()
        ).hexdigest(),
        "scholarly_profile_report_sha256": profile_report["report_sha256"],
        "cases": cases,
        "source_cache_tasks": source_cache_tasks,
        "summary": {
            "case_count": len(cases),
            "mandatory_trigger_count": sum(row["triggered"] for row in cases),
            "source_cache_task_count": len(source_cache_tasks),
            "rule_task_counts": rule_task_counts,
            "work_budget_ref": str(mechanism["work_budget_ref"]),
            "within_work_budget": True,
            "network_request_count": 0,
            "model_call_count": 0,
            "business_write_count": 0,
        },
        "declarations": {
            "scholarship_is_formal_fact": False,
            "primary_source_location_precedes_judge": True,
            "candidate_judge_required": True,
            "formal_score": None,
            "tier": None,
            "ranking": None,
            "migration_executed": False,
        },
    }
    report["report_sha256"] = _stable_hash(report)
    return report


def build_scholar_guided_judge_intake(
    report: Mapping[str, Any], *, source_cache_response: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError("Judge intake 只能消费学术引导检索报告")
    passages = (source_cache_response or {}).get("passages") or ()
    items = []
    for row in report.get("source_cache_tasks") or ():
        required_keys = set(row["required_source_cache_selection_keys"])
        matched_passages = [
            passage
            for passage in passages
            if (
                not passage.get("source_cache_task_code")
                or passage.get("source_cache_task_code") == row["task_code"]
            )
            and required_keys & set(passage.get("selection_reason") or ())
        ]
        matched_keys = {
            key
            for passage in matched_passages
            for key in passage.get("selection_reason") or ()
            if key in required_keys
        }
        status = (
            "ready_for_candidate_judge"
            if matched_keys == required_keys
            else "awaiting_versioned_source_cache"
        )
        for rule in row["target_rules"]:
            items.append({
            "intake_ref": f"JIN-{sha256((row['task_code'] + ':' + rule).encode('utf-8')).hexdigest()[:20].upper()}",
            "source_cache_task_code": row["task_code"],
            "case_ref": row["case_ref"],
            "subject_ref": row["subject_ref"],
            "rule_code": rule,
            "status": status,
            "source_cache_passage_refs": sorted(
                str(passage.get("passage_id") or "") for passage in matched_passages
            ),
            "matched_selection_keys": sorted(matched_keys),
            "missing_selection_keys": sorted(required_keys - matched_keys),
            "required_mechanism_predicates": row["mechanism_predicates"][rule],
            "judge_may_accept_scholarship_as_fact": False,
            })
    ready = sum(row["status"] == "ready_for_candidate_judge" for row in items)
    intake: dict[str, Any] = {
        "schema_version": "i5b-scholar-guided-judge-intake-v1",
        "status": (
            "partially_ready_for_candidate_judge"
            if ready
            else "routed_awaiting_source_cache"
        ),
        "source_report_sha256": report["report_sha256"],
        "items": items,
        "summary": {
            "item_count": len(items),
            "ready_for_candidate_judge_count": ready,
            "awaiting_source_cache_count": len(items) - ready,
            "formal_facts_accepted": 0,
            "model_call_count": 0,
            "business_write_count": 0,
        },
    }
    intake["report_sha256"] = _stable_hash(intake)
    return intake


def write_scholar_guided_retrieval_report(
    *,
    mechanism_contract_path: Path,
    task_contract_path: Path,
    output_path: Path,
    judge_intake_output_path: Path | None = None,
    source_cache_response_path: Path | None = None,
) -> dict[str, Any]:
    report = build_scholar_guided_retrieval_report(
        mechanism_contract_path=mechanism_contract_path,
        task_contract_path=task_contract_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if judge_intake_output_path is not None:
        source_cache_response = None
        if source_cache_response_path is not None:
            source_payload = json.loads(
                source_cache_response_path.read_text(encoding="utf-8")
            )
            source_cache_response = source_payload.get("response") or source_payload
        intake = build_scholar_guided_judge_intake(
            report, source_cache_response=source_cache_response
        )
        judge_intake_output_path.parent.mkdir(parents=True, exist_ok=True)
        judge_intake_output_path.write_text(
            json.dumps(intake, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="生成第五项B学术引导原始史料检索任务")
    parser.add_argument("--mechanism-contract", type=Path, required=True)
    parser.add_argument("--task-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-intake-output", type=Path)
    parser.add_argument("--source-cache-response", type=Path)
    args = parser.parse_args()
    write_scholar_guided_retrieval_report(
        mechanism_contract_path=args.mechanism_contract,
        task_contract_path=args.task_contract,
        output_path=args.output,
        judge_intake_output_path=args.judge_intake_output,
        source_cache_response_path=args.source_cache_response,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
