from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "i5b-talent-discovery-scope-contract-v1"
REPORT_SCHEMA_VERSION = "i5b-talent-discovery-candidate-inventory-v3"


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def build_talent_discovery_scope_refreeze(contract_path: Path) -> dict[str, Any]:
    contract_path = contract_path if contract_path.is_absolute() else ROOT / contract_path
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if not isinstance(contract, Mapping) or contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("发现人才时间范围合同版本非法")
    policy = contract.get("scope_policy") or {}
    if policy.get("evaluation_window") != {"start": 626, "end": 649}:
        raise ValueError("李世民评价窗口必须保持 626—649")
    if policy.get("pre_accession_mode") != "leadership_formation_lookback":
        raise ValueError("登基前只能按领导团队形成期回溯")
    budget_path = ROOT / str(contract.get("work_budget_ref") or "")
    budget = yaml.safe_load(budget_path.read_text(encoding="utf-8"))
    if budget.get("schema_version") != "i5b-historical-work-budget-v1":
        raise ValueError("发现人才重冻缺少工作预算")
    limits = budget["per_rule_run"]
    max_scope_reviews = int(limits["max_candidate_judge_items"])
    max_route_reviews = int(limits["max_cross_rule_route_reviews"])
    gates = policy.get("admission_gates") or {}
    if gates != {
        "ruler_or_direct_agent_recruited": True,
        "independent_conversion_to_ruler_team": True,
        "retained_into_evaluation_window": True,
        "predecessor_only_recruitment_excluded": True,
        "same_discovery_chain_settled_once": True,
    }:
        raise ValueError("登基前识才归责 Gate 不完整")

    base_path = ROOT / str(contract["base_inventory_ref"])
    base = json.loads(base_path.read_text(encoding="utf-8"))
    inventory = [dict(row) for row in base.get("candidate_inventory") or ()]
    reopened = 0
    scheduled_scope_reviews = 0
    for row in inventory:
        if row.get("final_disposition") != "reject_pre_reign_scope":
            continue
        scheduled = scheduled_scope_reviews < max_scope_reviews
        row["final_disposition"] = (
            "pending_pre_accession_ruler_agency_review"
            if scheduled
            else "deferred_pre_accession_budget"
        )
        row["final_rationale"] = (
            "旧版仅因626年前发生而排除；新合同要求核对是否由李世民本人或其直接授权者招募、"
            "验证并转化为本人团队，以及是否延续进入626—649评价窗口。未完成该核对前不得接受或排除。"
        )
        row["scope_relation"] = "pre_accession_leadership_formation"
        reopened += 1
        scheduled_scope_reviews += int(scheduled)

    known_groups = {str(row.get("event_group_key") or "") for row in inventory}
    for row in contract.get("orphan_candidates") or ():
        event_group_key = str(row.get("event_group_key") or "")
        if not event_group_key or event_group_key in known_groups:
            raise ValueError("新增识才候选 event_group_key 缺失或重复")
        if row.get("disposition") != "candidate_pending_primary_source_acceptance":
            raise ValueError("路由孤儿只能恢复为待回源候选")
        if not row.get("primary_source_locators"):
            raise ValueError("路由孤儿缺少原始史料定位")
        inventory.append(
            {
                "task_code": str(contract["task_code"]),
                "event_group_key": event_group_key,
                "rule_code": "talent_discovery",
                "candidate_persons": list(row["candidate_persons"]),
                "candidate_event_summary": str(row["candidate_event_summary"]),
                "claim_refs": [],
                "initial_disposition": "cross_rule_orphan_recovered",
                "final_disposition": str(row["disposition"]),
                "rationale": str(row["rationale"]),
                "final_rationale": str(row["rationale"]),
                "scope_relation": "pre_accession_leadership_formation",
                "primary_source_locators": list(row["primary_source_locators"]),
                "worker_authority": "candidate_only_no_v4_fact_authority",
            }
        )
        known_groups.add(event_group_key)

    cross_rule_review: list[dict[str, Any]] = []
    time_markers = ("即位前", "秦王时期", "秦王府", "在藩时", "窗口外")
    scheduled_route_reviews = 0
    for inventory_ref in contract.get("cross_rule_inventory_refs") or ():
        source_path = ROOT / str(inventory_ref)
        source = json.loads(source_path.read_text(encoding="utf-8"))
        for row in source.get("candidate_inventory") or ():
            rationale = str(row.get("final_rationale") or "")
            if not any(marker in rationale for marker in time_markers):
                continue
            event_group_key = str(row.get("event_group_key") or "")
            already_bound = event_group_key in known_groups
            scheduled = already_bound or scheduled_route_reviews < max_route_reviews
            cross_rule_review.append(
                {
                    "source_inventory_ref": str(inventory_ref),
                    "source_rule_code": str(source.get("rule_code") or ""),
                    "event_group_key": event_group_key,
                    "candidate_persons": list(row.get("candidate_persons") or ()),
                    "candidate_event_summary": str(
                        row.get("candidate_event_summary") or ""
                    ),
                    "already_bound_in_talent_inventory": already_bound,
                    "route_status": (
                        "bound_for_pre_accession_agency_review"
                        if already_bound
                        else (
                            "pending_talent_discovery_semantic_route_review"
                            if scheduled
                            else "deferred_cross_rule_route_budget"
                        )
                    ),
                    "route_rule": (
                        "只有招募、识别、验证或首次转化使用语义可转入发现人才；"
                        "单纯任务授权、战功奖叙或临时军事命令继续留在原rule作时间排除。"
                    ),
                }
            )
            if not already_bound and scheduled:
                scheduled_route_reviews += 1

    counts: dict[str, int] = {}
    for row in inventory:
        key = str(row["final_disposition"])
        counts[key] = counts.get(key, 0) + 1
    report: dict[str, Any] = {
        **{key: value for key, value in base.items() if key not in {
            "candidate_inventory", "candidate_summary", "scope", "report_sha256",
            "formal_fact_acceptance_ready", "historical_coverage_complete", "status",
            "schema_version",
        }},
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "candidate_refreeze_reopened",
        "scope": {
            "evaluation_window": {"start": 626, "end": 649},
            "discovery_lookback": "pre_accession_leadership_formation",
            "predecessor_only_recruitment": "excluded",
        },
        "candidate_inventory": inventory,
        "cross_rule_pre_accession_review": cross_rule_review,
        "candidate_summary": {
            "candidate_count": len(inventory),
            "reopened_pre_accession_count": reopened,
            "scheduled_pre_accession_review_count": scheduled_scope_reviews,
            "deferred_pre_accession_review_count": reopened
            - scheduled_scope_reviews,
            "recovered_cross_rule_orphan_count": len(contract.get("orphan_candidates") or ()),
            "final_disposition_counts": dict(sorted(counts.items())),
            "unresolved_candidate_count": sum(
                "pending_" in key or "deferred_" in key
                for key in [str(row["final_disposition"]) for row in inventory]
            ),
            "cross_rule_time_exclusion_count": len(cross_rule_review),
            "cross_rule_pending_semantic_route_count": sum(
                row["route_status"]
                == "pending_talent_discovery_semantic_route_review"
                for row in cross_rule_review
            ),
            "cross_rule_deferred_budget_count": sum(
                row["route_status"] == "deferred_cross_rule_route_budget"
                for row in cross_rule_review
            ),
            "within_work_budget": True,
        },
        "formal_fact_acceptance_ready": False,
        "historical_coverage_complete": False,
        "declarations": {
            "pre_accession_event_is_automatically_accepted": False,
            "li_yuan_or_predecessor_recruitment_attributed_to_li_shimin": False,
            "v3_hint_is_v4_fact": False,
            "database_write_count": 0,
            "model_call_count": 0,
            "formal_score": None,
            "tier": None,
            "ranking": None,
        },
    }
    report["report_sha256"] = _stable_hash(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="重开第五项B发现人才领导团队形成期候选")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_talent_discovery_scope_refreeze(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
