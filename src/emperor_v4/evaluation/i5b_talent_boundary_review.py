from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

import yaml


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_SCHEMA = "i5b-talent-boundary-source-contract-v1"
REPORT_SCHEMA = "i5b-talent-boundary-source-report-v1"
DECISION_SCHEMA = "i5b-talent-boundary-decisions-v1"


def _hash(value: object) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"talent boundary 输入必须为 mapping: {path}")
    return payload


def _page_title(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != "zh.wikisource.org" or "/wiki/" not in parsed.path:
        raise ValueError(f"talent boundary 仅接受 Wikisource 精确页: {url}")
    return unquote(parsed.path.split("/wiki/", 1)[1]).replace("_", " ")


def build_talent_boundary_source_report(contract_path: Path) -> dict[str, Any]:
    contract = _load(contract_path)
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError("talent boundary source contract 版本非法")
    cases = contract.get("cases") or ()
    if len(cases) != 6 or len({row.get("person") for row in cases}) != 6:
        raise ValueError("talent boundary 必须一次且仅审查去重后的六组")
    tasks = []
    for row in cases:
        locators = row.get("primary_source_locators") or ()
        if row.get("disposition") == "existing_formal_acceptance_duplicate":
            if locators or not row.get("existing_formal_acceptance_ref"):
                raise ValueError("既有正式接受复用不得再领取 Source Cache")
            continue
        if not locators:
            raise ValueError(f"talent boundary 候选缺少史源: {row.get('person')}")
        task_code = f"{contract['task_code']}:{row['case_ref']}"
        tasks.append(
            {
                "task_code": task_code,
                "case_ref": row["case_ref"],
                "subject_ref": row["subject_ref"],
                "subject_label": row["person"],
                "target_rules": ["talent_discovery"],
                "primary_source_locators": list(locators),
                "required_source_cache_selection_keys": list(
                    row["required_source_cache_selection_keys"]
                ),
                "source_cache_request": {
                    "request_id": f"SRC-{task_code}",
                    "idempotency_key": (
                        "source-cache:v4:talent-boundary:"
                        + sha256(task_code.encode("utf-8")).hexdigest()[:24]
                    ),
                    "subject": {
                        "person_or_ruler_ref": row["subject_ref"],
                        "canonical_name": row["person"],
                        "aliases": [],
                    },
                    "evaluation_context": {
                        "purpose": "bounded_talent_discovery_boundary_review",
                        "ruler": "李世民",
                        "reign_window": {"start": 626, "end": 649},
                        "leadership_formation_lookback": True,
                        "rule": "talent_discovery",
                    },
                    "source_hints": sorted(
                        {_page_title(locator["canonical_url"]) for locator in locators}
                    ),
                    "required_source_families": ["primary_text"],
                    "mode": "ensure",
                    "source_policy_version": "v4-talent-boundary-primary-source-v1",
                    "requested_at": str(contract["requested_at"]),
                },
            }
        )
    if len(tasks) > 6:
        raise ValueError("talent boundary Source Cache 任务超过单 rule 上限")
    report = {
        "schema_version": REPORT_SCHEMA,
        "status": "bounded_source_tasks_ready",
        "task_code": contract["task_code"],
        "ruler": "李世民",
        "source_cache_tasks": tasks,
        "review_cases": list(cases),
        "summary": {
            "deduplicated_boundary_case_count": len(cases),
            "source_cache_task_count": len(tasks),
            "within_rule_budget": True,
            "exhaustive_search_required": False,
            "database_write_count": 0,
            "model_call_count": 0,
        },
        "declarations": {
            "candidate_only": True,
            "formal_score": None,
            "tier": None,
            "ranking": None,
            "migration_executed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def apply_talent_boundary_decisions(
    *, inventory: Mapping[str, Any], source_report: Mapping[str, Any],
    source_cache_response: Mapping[str, Any], decisions: Mapping[str, Any]
) -> dict[str, Any]:
    if decisions.get("schema_version") != DECISION_SCHEMA:
        raise ValueError("talent boundary decision 版本非法")
    if decisions.get("source_report_sha256") != source_report.get("report_sha256"):
        raise ValueError("talent boundary decision 与 source report 版本不一致")
    passages_by_task: dict[str, set[str]] = {}
    for passage in source_cache_response.get("passages") or ():
        passages_by_task.setdefault(
            str(passage.get("source_cache_task_code") or ""), set()
        ).add(str(passage.get("passage_id") or ""))
    cases = {row["person"]: row for row in source_report["review_cases"]}
    decision_rows = decisions.get("decisions") or ()
    by_person = {row.get("person"): row for row in decision_rows}
    if set(by_person) != set(cases) or len(by_person) != len(decision_rows):
        raise ValueError("talent boundary decision 必须完整覆盖六组")

    unresolved_dispositions = {
        "candidate_pending_primary_source_acceptance",
        "deferred_pre_accession_budget",
        "pending_pre_accession_ruler_agency_review",
    }
    rows = deepcopy(list(inventory.get("candidate_inventory") or ()))
    for person, decision in by_person.items():
        canonical_key = str(decision["canonical_event_group_key"])
        matching = [
            row for row in rows
            if row.get("final_disposition") in unresolved_dispositions
            and str((row.get("candidate_persons") or [""])[0]) == person
        ]
        if not matching or canonical_key not in {row["event_group_key"] for row in matching}:
            raise ValueError(f"talent boundary canonical group 不在 unresolved: {person}")
        source_task_code = decision.get("source_cache_task_code")
        passage_refs = set(decision.get("source_cache_passage_refs") or ())
        disposition = str(decision["disposition"])
        if disposition == "accepted_new_candidate":
            if not source_task_code or not passage_refs or not passage_refs <= passages_by_task.get(
                str(source_task_code), set()
            ):
                raise ValueError(f"talent boundary 接受决定缺少匹配 Source Cache: {person}")
        elif disposition != "accepted_duplicate":
            raise ValueError(f"talent boundary disposition 非法: {person}")
        for row in matching:
            is_canonical = row["event_group_key"] == canonical_key
            row["final_disposition"] = (
                disposition if is_canonical else "merged_duplicate_boundary_group"
            )
            row["final_rationale"] = (
                str(decision["rationale"])
                if is_canonical
                else f"与 {canonical_key} 属同一人物识才边界组，已合并裁决。"
            )
            row["boundary_review_v1"] = {
                "decision_ref": decisions["decision_ref"],
                "canonical_event_group_key": canonical_key,
                "source_cache_task_code": source_task_code,
                "source_cache_passage_refs": sorted(passage_refs),
            }

    remaining = [
        row for row in rows if row.get("final_disposition") in unresolved_dispositions
    ]
    if remaining:
        raise ValueError("talent boundary 六组裁决后仍有 unresolved")
    result = deepcopy(dict(inventory))
    result["schema_version"] = "i5b-talent-discovery-candidate-inventory-v4"
    result["status"] = "bounded_boundary_review_complete"
    result["candidate_inventory"] = rows
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row["final_disposition"])
        counts[key] = counts.get(key, 0) + 1
    result["candidate_summary"] = {
        **(result.get("candidate_summary") or {}),
        "final_disposition_counts": dict(sorted(counts.items())),
        "unresolved_candidate_count": 0,
        "deduplicated_boundary_case_count": 6,
        "accepted_new_candidate_count": sum(
            row["disposition"] == "accepted_new_candidate" for row in decision_rows
        ),
        "accepted_duplicate_count": sum(
            row["disposition"] == "accepted_duplicate" for row in decision_rows
        ),
    }
    reviewed_people = set(by_person)
    cross_rule_review = deepcopy(
        list(result.get("cross_rule_pre_accession_review") or ())
    )
    next_boundary_people: set[str] = set()
    for row in cross_rule_review:
        candidate_persons = [str(item) for item in row.get("candidate_persons") or ()]
        focal_person = next(
            (person for person in candidate_persons if person != "李世民"), ""
        )
        if focal_person in reviewed_people:
            row["route_status"] = "resolved_by_boundary_group_review"
            row["boundary_decision_ref"] = decisions["decision_ref"]
        elif not focal_person:
            row["route_status"] = "retained_in_source_rule_not_discovery_semantics"
        elif row.get("route_status") in {
            "pending_talent_discovery_semantic_route_review",
            "deferred_cross_rule_route_budget",
        }:
            row["route_status"] = "next_bounded_boundary_batch"
            next_boundary_people.add(focal_person)
    result["cross_rule_pre_accession_review"] = cross_rule_review
    result["candidate_summary"]["cross_rule_pending_semantic_route_count"] = len(
        next_boundary_people
    )
    result["candidate_summary"]["cross_rule_deferred_budget_count"] = 0
    result["candidate_summary"]["next_boundary_candidate_count"] = len(
        next_boundary_people
    )
    result["candidate_summary"]["next_boundary_candidates"] = sorted(
        next_boundary_people
    )
    result["historical_coverage_complete"] = not next_boundary_people
    result["formal_fact_acceptance_ready"] = True
    result["boundary_freeze"] = {
        "decision_ref": decisions["decision_ref"],
        "source_report_sha256": source_report["report_sha256"],
        "bounded_boundary_review_complete": True,
        "next_boundary_candidates": sorted(next_boundary_people),
        "exhaustive_search_claimed": False,
        "human_freeze_accepted": not next_boundary_people,
        "database_write_count": 0,
        "model_call_count": 0,
    }
    result["status"] = (
        "bounded_boundary_review_complete"
        if not next_boundary_people
        else "bounded_boundary_batch_complete_backlog_remains"
    )
    result.pop("report_sha256", None)
    result["report_sha256"] = _hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="生成李世民发现人才边界批次史源任务")
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--source-report", type=Path)
    parser.add_argument("--source-cache-response", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.decisions:
        required = (
            args.inventory,
            args.source_report,
            args.source_cache_response,
        )
        if not all(required) or args.contract:
            parser.error("应用边界裁决时必须提供 inventory/source-report/source-cache-response")
        load_json = lambda path: json.loads(path.read_text(encoding="utf-8"))
        source_cache_payload = load_json(args.source_cache_response)
        report = apply_talent_boundary_decisions(
            inventory=load_json(args.inventory),
            source_report=load_json(args.source_report),
            source_cache_response=(
                source_cache_payload.get("response") or source_cache_payload
            ),
            decisions=_load(args.decisions),
        )
    else:
        if not args.contract or any(
            (args.inventory, args.source_report, args.source_cache_response)
        ):
            parser.error("生成史源任务时只提供 contract")
        report = build_talent_boundary_source_report(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
