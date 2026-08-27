from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

import yaml


POOL_JSON = "config/common/canonical-ruler-pool.json"
POOL_MARKDOWN = "docs/项目总纲/正式评价对象范围.md"
ADMISSION_ADJUDICATIONS = "config/common/canonical-ruler-admission-adjudications.yml"
SECOND_ITEM_ELIGIBLE_JSON = (
    "docs/评分结算/第二项治国净收益/02-正式评价池排名.json"
)
SECOND_ITEM_ELIGIBLE_MARKDOWN = (
    "docs/评分结算/第二项治国净收益/02-正式评价池排名.md"
)

SETTLEMENT_PATHS = {
    "first_item": "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json",
    "second_item": "docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.json",
    "third_item": "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json",
    "fourth_item": "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json",
    "fifth_item": "docs/评分结算/第五项统治者政治素质/04-第五项统治者政治素质正式结算.json",
}

FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST = {
    "赵佶": "非奠基者；第一项源快照未收录不影响F=0。",
    "完颜永济": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "载湉": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "拓跋弘": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "李安全": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "李秉常": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "李德旺": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
}

FIRST_ITEM_PENDING_FORMAL_SETTLEMENT = {
    "刘崇": "北汉建国主链实际贡献者；第一项适用。",
    "孟知祥": "后蜀建国主链实际贡献者；第一项适用。",
    "李克用": "晋政权奠基主链实际贡献者；第一项适用。",
    "杨行密": "吴政权奠基主链实际贡献者；第一项适用。",
    "钱镠": "吴越建国主链实际贡献者；第一项适用。",
    "马殷": "楚政权建国主链实际贡献者；第一项适用。",
    "高季兴": "荆南建国主链实际贡献者；第一项适用。",
    "李德明": "西夏国家形成主链实际贡献者；第一项适用。",
}

# 已结算分项保留历史姓名和ID作为lineage；评价池统一消费右侧规范姓名和母池ID。
ITEM_NAME_ALIASES = {
    "first_item": {
        "完颜吴乞买": "完颜晟",
    },
}

CANONICAL_LEGACY_ID_REFS = {
    "RULER-JIN-TAIZONG": [
        "RULER-JIN-WANYAN-SHENG",
        "RULER-ROSTER-6FB8C85A5180DFB2",
    ],
    "RULER-PUBLIC-6E925E92C6F5ECA5": ["RULER-ROSTER-6E925E92C6F5ECA5"],
    "RULER-PUBLIC-6339E33979E7CCF5": ["RULER-ROSTER-6339E33979E7CCF5"],
    "RULER-PUBLIC-AD29E67DF9E98569": ["RULER-ROSTER-AD29E67DF9E98569"],
    "RULER-PUBLIC-5B02E75C191C9829": ["RULER-ROSTER-5B02E75C191C9829"],
    "RULER-PUBLIC-4EB7AC987FECC59F": ["RULER-ROSTER-4EB7AC987FECC59F"],
    "RULER-PUBLIC-6DACD59C17927ECA": ["RULER-ROSTER-6DACD59C17927ECA"],
    "RULER-PUBLIC-93F6E8CA07BBD59F": ["RULER-ROSTER-93F6E8CA07BBD59F"],
    "RULER-PUBLIC-7C4ED87E9C80BF8A": ["RULER-ROSTER-7C4ED87E9C80BF8A"],
    "RULER-PUBLIC-310D1C92CEE1924D": ["RULER-ROSTER-310D1C92CEE1924D"],
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_admission_adjudications(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ADMISSION_ADJUDICATIONS
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "canonical-ruler-admission-adjudications-v1":
        raise ValueError("正式池准入裁决schema不匹配")
    exclusions = payload.get("exclusions")
    groups = payload.get("pending_second_item_feasibility_groups")
    overrides = payload.get("actual_power_window_overrides") or {}
    window_groups = payload.get("second_item_window_adjudications") or {}
    if (
        not isinstance(exclusions, dict)
        or not isinstance(groups, dict)
        or not isinstance(overrides, dict)
        or not isinstance(window_groups, dict)
    ):
        raise ValueError("正式池准入裁决缺少排除或第二项可行性分组")
    for ruler_name, override in overrides.items():
        refs = override.get("evidence_refs") or []
        if not override.get("actual_power_window") or not override.get("basis") or not refs:
            raise ValueError(f"实际权力窗口覆写不完整：{ruler_name}")
        missing_refs = [ref for ref in refs if not (workspace_root / ref).exists()]
        if missing_refs:
            raise ValueError(f"实际权力窗口覆写存在悬空证据：{ruler_name}={missing_refs}")
    for group_code, group in groups.items():
        refs = group.get("evidence_refs") or []
        rulers = group.get("rulers") or []
        if not refs or not rulers or len(rulers) != len(set(rulers)):
            raise ValueError(f"第二项可行性分组无证据或对象重复：{group_code}")
        missing_refs = [ref for ref in refs if not (workspace_root / ref).exists()]
        if missing_refs:
            raise ValueError(f"第二项可行性分组存在悬空证据：{group_code}={missing_refs}")
    window_names: set[str] = set()
    for status, group in window_groups.items():
        refs = group.get("evidence_refs") or []
        rulers = [str(name) for name in group.get("rulers") or []]
        if not group.get("basis") or not refs or not rulers:
            raise ValueError(f"第二项窗口裁决不完整：{status}")
        duplicates = window_names.intersection(rulers)
        if duplicates:
            raise ValueError(f"第二项窗口对象重复裁决：{sorted(duplicates)}")
        window_names.update(rulers)
        missing_refs = [ref for ref in refs if not (workspace_root / ref).exists()]
        if missing_refs:
            raise ValueError(f"第二项窗口裁决存在悬空证据：{status}={missing_refs}")
    return payload


def _index_pending_second_item_feasibility(
    adjudications: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for group_code, group in adjudications["pending_second_item_feasibility_groups"].items():
        for ruler_name in group["rulers"]:
            if ruler_name in indexed:
                raise ValueError(f"第二项待结算对象重复登记：{ruler_name}")
            indexed[str(ruler_name)] = {
                "group_code": str(group_code),
                "evidence_refs": list(group["evidence_refs"]),
            }
    return indexed


def _index_second_item_window_adjudications(
    adjudications: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for status, group in adjudications["second_item_window_adjudications"].items():
        for ruler_name in group["rulers"]:
            indexed[str(ruler_name)] = {
                "status": str(status),
                "basis": str(group["basis"]),
                "evidence_refs": list(group["evidence_refs"]),
            }
    return indexed


def _index_by_name(payload: Mapping[str, Any], item: str) -> dict[str, Mapping[str, Any]]:
    records = payload.get("records") or ()
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in records:
        source_name = str(row.get("ruler_name") or "")
        name = ITEM_NAME_ALIASES.get(item, {}).get(source_name, source_name)
        if not name or name in indexed:
            raise ValueError(f"{item}存在空姓名或重复姓名：{name}")
        indexed[name] = row
    return indexed


def _fifth_evidence_counts(row: Mapping[str, Any]) -> tuple[int, int]:
    factual = 0
    baseline = 0
    for axis in ("A", "B", "C"):
        detail = (row.get("axes") or {}).get(axis)
        if not detail:
            continue
        if "客观皇帝基线" in str(detail.get("grade_reason") or ""):
            baseline += 1
        else:
            factual += 1
    return factual, baseline


def build_canonical_ruler_pool(workspace_root: Path) -> dict[str, Any]:
    paths = {key: workspace_root / relative for key, relative in SETTLEMENT_PATHS.items()}
    payloads = {key: _read_json(path) for key, path in paths.items()}
    indexed = {key: _index_by_name(payload, key) for key, payload in payloads.items()}
    admission_adjudications = _load_admission_adjudications(workspace_root)
    exclusions = admission_adjudications["exclusions"]
    actual_power_window_overrides = admission_adjudications.get(
        "actual_power_window_overrides", {}
    )
    pending_feasibility = _index_pending_second_item_feasibility(admission_adjudications)
    window_adjudications = _index_second_item_window_adjudications(
        admission_adjudications
    )
    invalidated_second_item_names = {
        name
        for name, adjudication in window_adjudications.items()
        if adjudication["status"]
        == "FORMAL_SCORE_INVALIDATED_PENDING_READJUDICATION"
    }

    master_records = list(payloads["fifth_item"].get("records") or ())
    master_ids = [str(row.get("ruler_id") or "") for row in master_records]
    if len(master_records) != 201 or any(not value for value in master_ids) or len(set(master_ids)) != 201:
        raise ValueError("第五项候选母池必须是201个唯一ruler_id")
    for item in ("third_item", "fourth_item"):
        ids = {str(row.get("ruler_id") or "") for row in payloads[item].get("records") or ()}
        if ids != set(master_ids):
            raise ValueError(f"{item}与201人候选母池ruler_id集合不一致")

    master_id_by_name = {
        str(row["ruler_name"]): str(row["ruler_id"]) for row in master_records
    }
    for item in ("second_item", "third_item", "fourth_item", "fifth_item"):
        mismatches = {
            name: (str(row.get("ruler_id") or ""), master_id_by_name.get(name))
            for name, row in indexed[item].items()
            if name in master_id_by_name
            and str(row.get("ruler_id") or "") != master_id_by_name[name]
        }
        if mismatches:
            raise ValueError(f"{item}存在非规范ruler_id：{mismatches}")

    master_names = {str(row["ruler_name"]) for row in master_records}
    unknown_exclusions = set(exclusions) - master_names
    if unknown_exclusions:
        raise ValueError(f"准入裁决包含候选母池外排除对象：{sorted(unknown_exclusions)}")
    unknown_overrides = set(actual_power_window_overrides) - master_names
    unknown_window_adjudications = set(window_adjudications) - set(indexed["second_item"])
    if unknown_overrides or unknown_window_adjudications:
        raise ValueError(
            "实际权力窗口裁决存在未知对象："
            f"覆写={sorted(unknown_overrides)}，第二项={sorted(unknown_window_adjudications)}"
        )
    expected_pending_names = master_names - set(indexed["second_item"]) - set(exclusions)
    if set(pending_feasibility) != expected_pending_names:
        raise ValueError(
            "第二项待结算可行性登记与当前缺分对象不一致："
            f"缺登记={sorted(expected_pending_names - set(pending_feasibility))}，"
            f"多登记={sorted(set(pending_feasibility) - expected_pending_names)}"
        )
    first_item_outside_candidate_pool = sorted(
        (
            {
                "ruler_id": str(row["ruler_id"]),
                "ruler_name": str(row["ruler_name"]),
                "pool_relation": "OUTSIDE_CANONICAL_CANDIDATE_POOL",
            }
            for canonical_name, row in indexed["first_item"].items()
            if canonical_name not in master_names
        ),
        key=lambda row: (row["ruler_name"], row["ruler_id"]),
    )
    outside_names = {row["ruler_name"] for row in first_item_outside_candidate_pool}
    expected_outside_names = {"塔不烟", "洪秀全", "耶律璟", "萧普速完", "黄巢"}
    if outside_names != expected_outside_names:
        raise ValueError(f"第一项池外记录集合漂移：{sorted(outside_names)}")

    records: list[dict[str, Any]] = []
    for master in master_records:
        name = str(master["ruler_name"])
        reason_code = None
        reason = None
        if name in exclusions:
            reason_code = str(exclusions[name]["reason_code"])
            reason = str(exclusions[name]["reason"])
        source_rows = {item: by_name.get(name) for item, by_name in indexed.items()}
        second_item_snapshot_present = source_rows["second_item"] is not None
        second_item_formal = (
            second_item_snapshot_present and name not in invalidated_second_item_names
        )
        if reason_code is None:
            missing = [
                item
                for item in ("third_item", "fourth_item", "fifth_item")
                if source_rows[item] is None
            ]
            if missing:
                raise ValueError(f"正式池候选{name}缺少共同项：{missing}")
            if (
                source_rows["second_item"] is not None
                and source_rows["second_item"].get("second_item_score") is None
            ):
                raise ValueError(f"正式池候选{name}已有第二项记录但无分")
            if source_rows["third_item"].get("third_item_score_points") is None:
                raise ValueError(f"正式池候选{name}第三项无分")
            if source_rows["fourth_item"].get("fourth_item_signed_adjustment") is None:
                raise ValueError(f"正式池候选{name}第四项未闭合")
            if source_rows["fifth_item"].get("fifth_item_score_points") is None:
                raise ValueError(f"正式池候选{name}第五项无分")
            if (
                source_rows["second_item"] is not None
                and source_rows["first_item"] is None
                and name not in FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST
            ):
                raise ValueError(f"正式池候选{name}缺少第一项记录且没有不适用裁决")
            if (
                source_rows["first_item"] is None
                and name not in FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST
                and name not in FIRST_ITEM_PENDING_FORMAL_SETTLEMENT
            ):
                raise ValueError(f"正式池候选{name}缺少第一项适用性裁决")
            if source_rows["second_item"] is None and name not in pending_feasibility:
                raise ValueError(f"正式池候选{name}缺少第二项本地材料可行性裁决")

        factual_axes, baseline_axes = _fifth_evidence_counts(master)
        records.append(
            {
                "ruler_id": master["ruler_id"],
                "ruler_name": name,
                "polity": master.get("polity"),
                "actual_power_window": (
                    actual_power_window_overrides.get(name, {}).get("actual_power_window")
                    or master.get("actual_power_window")
                ),
                "actual_power_window_adjudication": (
                    actual_power_window_overrides.get(name)
                ),
                "pool_status": "INCLUDED" if reason_code is None else "EXCLUDED",
                "settlement_readiness": (
                    "COMPOSITE_READY"
                    if reason_code is None and second_item_formal
                    else (
                        "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
                        if reason_code is None
                        else "NOT_APPLICABLE_EXCLUDED"
                    )
                ),
                "exclusion_reason_code": reason_code,
                "exclusion_reason": reason,
                "evidence_feasibility": {
                    "second_item_formal": second_item_formal,
                    "second_item_score_snapshot_present": second_item_snapshot_present,
                    "second_item_feasibility_group": (
                        pending_feasibility.get(name, {}).get("group_code")
                    ),
                    "second_item_local_evidence_refs": (
                        pending_feasibility.get(name, {}).get("evidence_refs", [])
                    ),
                    "third_item_formal": source_rows["third_item"] is not None,
                    "fourth_item_formal": source_rows["fourth_item"] is not None,
                    "fifth_item_formal": master.get("fifth_item_score_points") is not None,
                    "fifth_factual_axis_count": factual_axes,
                    "fifth_verified_baseline_axis_count": baseline_axes,
                },
                "second_item_window_adjudication": window_adjudications.get(name),
                "source_item_ids": {
                    item: row.get("ruler_id") if row else None for item, row in source_rows.items()
                },
                "source_item_names": {
                    item: row.get("ruler_name") if row else None for item, row in source_rows.items()
                },
                "identity_resolution": {
                    "canonical_ruler_id": master["ruler_id"],
                    "canonical_name": name,
                    "matched_aliases": sorted(
                        {
                            str(row.get("ruler_name"))
                            for row in source_rows.values()
                            if row and str(row.get("ruler_name")) != name
                        }
                    ),
                    "legacy_id_refs": CANONICAL_LEGACY_ID_REFS.get(
                        str(master["ruler_id"]), []
                    ),
                },
                "first_item_scope_note": (
                    "对象未通过评价池准入，不进入第一项池内缺口统计。"
                    if reason_code is not None
                    else (
                        FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST.get(name)
                        or FIRST_ITEM_PENDING_FORMAL_SETTLEMENT.get(name)
                    )
                ),
                "first_item_readiness": (
                    "NOT_APPLICABLE_EXCLUDED"
                    if reason_code is not None
                    else (
                        (
                            "FORMAL_RECORD_PRESENT_ALIAS_NORMALIZED"
                            if str(source_rows["first_item"].get("ruler_name")) != name
                            else "FORMAL_RECORD_PRESENT"
                        )
                        if source_rows["first_item"] is not None
                        else (
                            "EXPLICIT_NOT_APPLICABLE_F0"
                            if name in FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST
                            else "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
                        )
                    )
                ),
            }
        )

    records.sort(key=lambda row: str(row["ruler_id"]))
    included_count = sum(row["pool_status"] == "INCLUDED" for row in records)
    composite_ready_count = sum(row["settlement_readiness"] == "COMPOSITE_READY" for row in records)
    pending_second_item_count = sum(
        row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
        for row in records
    )
    pending_first_item_scope_count = sum(
        row["pool_status"] == "INCLUDED"
        and row["first_item_readiness"] == "PENDING_SCOPE_REVIEW_BEFORE_COMPOSITE"
        for row in records
    )
    pending_first_item_formal_settlement_count = sum(
        row["pool_status"] == "INCLUDED"
        and row["first_item_readiness"] == "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
        for row in records
    )
    reason_counts = Counter(
        row["exclusion_reason_code"] for row in records if row["pool_status"] == "EXCLUDED"
    )
    if (
        included_count != 184
        or len(records) - included_count != 17
        or composite_ready_count != 174
        or pending_second_item_count != 10
        or pending_first_item_scope_count != 0
        or pending_first_item_formal_settlement_count != 0
    ):
        raise ValueError(
            "正式池预期184人/排除17人/综合就绪165人/第二项待结算19人/第一项范围待复核0人/第一项待结算0人，"
            f"实际{included_count}/{len(records) - included_count}/{composite_ready_count}/"
            f"{pending_second_item_count}/{pending_first_item_scope_count}/"
            f"{pending_first_item_formal_settlement_count}"
        )
    expected_reason_counts = dict(
        Counter(str(row["reason_code"]) for row in exclusions.values())
    )
    if dict(reason_counts) != expected_reason_counts:
        raise ValueError(f"排除理由计数漂移：{dict(reason_counts)}")

    return {
        "schema_version": "canonical-ruler-pool-v2",
        "status": "CURRENT",
        "candidate_pool_count": 201,
        "included_count": included_count,
        "composite_ready_count": composite_ready_count,
        "pending_second_item_count": pending_second_item_count,
        "pending_first_item_scope_count": pending_first_item_scope_count,
        "pending_first_item_formal_settlement_count": pending_first_item_formal_settlement_count,
        "first_item_outside_candidate_pool_count": len(first_item_outside_candidate_pool),
        "excluded_count": len(records) - included_count,
        "selection_policy": {
            "minimum_effective_power_years": 3,
            "requires_independent_highest_decision_power": True,
            "requires_formal_scores_for_admission": ["third_item", "fifth_item"],
            "requires_closed_signed_adjustment": "fourth_item",
            "second_item_policy": "local evidence availability permits admission; missing or window-invalidated formal score blocks composite readiness and ranking",
            "first_item_policy": "conditional_add_on_only; every absent record must be adjudicated as explicit F=0 or pending formal A/B/C settlement",
            "feasibility_policy": "admit rulers with sufficient local reading products and historical sources even when second-item settlement is pending",
            "exclusion_precedence": [
                "NO_EFFECTIVE_POWER",
                "LIMITED_INDEPENDENT_POWER",
                "EFFECTIVE_POWER_LT_3_YEARS",
            ],
        },
        "exclusion_reason_counts": expected_reason_counts,
        "source_sha256": {
            **{item: _sha256(path) for item, path in paths.items()},
            "admission_adjudications": _sha256(workspace_root / ADMISSION_ADJUDICATIONS),
        },
        "item_name_aliases": ITEM_NAME_ALIASES,
        "first_item_outside_candidate_pool": first_item_outside_candidate_pool,
        "records": records,
    }


def build_second_item_eligible_ranking(
    workspace_root: Path,
    canonical_pool: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pool = canonical_pool or build_canonical_ruler_pool(workspace_root)
    source_path = workspace_root / SETTLEMENT_PATHS["second_item"]
    source = _read_json(source_path)
    source_records = list(source.get("records") or ())
    source_by_id = {str(row["ruler_id"]): row for row in source_records}
    ready_rows = [
        row
        for row in pool["records"]
        if row["settlement_readiness"] == "COMPOSITE_READY"
    ]
    ready_ids = {str(row["ruler_id"]) for row in ready_rows}
    if not ready_ids <= set(source_by_id):
        raise ValueError(
            f"第二项正式池排名缺少canonical ID：{sorted(ready_ids - set(source_by_id))}"
        )
    selected = [dict(source_by_id[ruler_id]) for ruler_id in ready_ids]
    selected.sort(key=lambda row: (-float(row["second_item_score"]), str(row["ruler_id"])))
    sorted_scores = [float(row["second_item_score"]) for row in selected]
    for index, row in enumerate(selected):
        row["source_snapshot_rank"] = row["rank"]
        row["rank"] = sorted_scores.index(sorted_scores[index]) + 1
        row["ranking_population"] = "COMPOSITE_READY"
    pool_by_name = {str(row["ruler_name"]): row for row in pool["records"]}
    excluded_lineage = sorted(
        (
            {
                "ruler_id": str(row["ruler_id"]),
                "ruler_name": str(row["ruler_name"]),
                "source_snapshot_rank": int(row["rank"]),
                "second_item_score": row["second_item_score"],
                "pool_status": pool_by_name[str(row["ruler_name"])]["pool_status"],
                "settlement_readiness": pool_by_name[str(row["ruler_name"])][
                    "settlement_readiness"
                ],
                "not_ranked_reason": (
                    pool_by_name[str(row["ruler_name"])]["exclusion_reason_code"]
                    or (
                        pool_by_name[str(row["ruler_name"])].get(
                            "second_item_window_adjudication"
                        )
                        or {}
                    ).get("status")
                ),
            }
            for row in source_records
            if str(row["ruler_id"]) not in ready_ids
        ),
        key=lambda row: (row["source_snapshot_rank"], row["ruler_id"]),
    )
    records_sha256 = hashlib.sha256(
        json.dumps(
            selected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_id": "second-item-canonical-ready-ranking-v1",
        "status": "FORMAL_CURRENT",
        "ranking_population": "COMPOSITE_READY",
        "source_score_snapshot": SETTLEMENT_PATHS["second_item"],
        "source_score_snapshot_sha256": _sha256(source_path),
        "record_count": len(selected),
        "excluded_lineage_record_count": len(excluded_lineage),
        "mean_score": round(mean(sorted_scores), 1),
        "median_score": round(median(sorted_scores), 2),
        "min_score": min(sorted_scores),
        "max_score": max(sorted_scores),
        "rank_tie_policy": "competition_rank_then_ruler_id",
        "records_sha256": records_sha256,
        "excluded_lineage_records": excluded_lineage,
        "records": selected,
    }


def render_second_item_eligible_ranking_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 第二项治国净收益正式评价池排名",
        "",
        (
            f"> 当前排名只覆盖`COMPOSITE_READY`的{payload['record_count']}人；"
            f"平均{payload['mean_score']}，中位数{payload['median_score']}，"
            f"范围{payload['min_score']}—{payload['max_score']}。"
        ),
        "",
        "185人分值快照保留全量分项分值与比较位次；本表是综合统计和未来总排名唯一可消费的第二项排名视图。",
        "",
        "| 排名 | 人物 | 政权 | 治理手段/165 | C1/80 | C2/35 | C3/60 | C4/-45—45 | 交接/20 | 总分/405 | 快照原位次 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["records"]:
        lines.append(
            "| {rank} | {name} | {polity} | {method:.1f} | {c1:.1f} | {c2:.1f} | "
            "{c3:.1f} | {c4:.1f} | {handoff:.1f} | **{total:.1f}** | {source_rank} |".format(
                rank=row["rank"],
                name=row["ruler_name"],
                polity=row["polity"],
                method=float(row["governance_method_score"]),
                c1=float(row["C1_score"]),
                c2=float(row["C2_score"]),
                c3=float(row["C3_score"]),
                c4=float(row["C4_score"]),
                handoff=float(row["handoff_score"]),
                total=float(row["second_item_score"]),
                source_rank=row["source_snapshot_rank"],
            )
        )
    lines.extend(
        [
            "",
            "## 仅保留历史分值、不进入正式池排名的记录",
            "",
            "| 人物 | 快照原位次 | 分值 | 未入排名原因 |",
            "|---|---:|---:|---|",
        ]
    )
    for row in payload["excluded_lineage_records"]:
        lines.append(
            f"| {row['ruler_name']} | {row['source_snapshot_rank']} | "
            f"{float(row['second_item_score']):.1f} | {row['not_ranked_reason']} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_canonical_ruler_pool_markdown(payload: Mapping[str, Any]) -> str:
    records = list(payload.get("records") or ())
    included = [row for row in records if row["pool_status"] == "INCLUDED"]
    excluded = [row for row in records if row["pool_status"] == "EXCLUDED"]
    by_polity: dict[str, list[str]] = defaultdict(list)
    for row in included:
        by_polity[str(row.get("polity") or "未标明")].append(str(row["ruler_name"]))

    lines = [
        "# 正式评价对象范围",
        "",
        "> 本文件是当前正式评价池的阅读视图；机器入口为 `config/common/canonical-ruler-pool.json`。`INCLUDED`表示通过对象准入，`COMPOSITE_READY`表示共同项已经齐备；综合分、总体统计与未来总排名只能消费后者。",
        "",
        "## 准入口径",
        "",
        "- 以第三、第四、第五项共同的201人全集为候选母池。",
        "- 实际、独立的最高决策权窗口至少3年；无实权、仅有有限本人选择或短期名义在位者排除。",
        "- 第三、第五项必须已有正式分，第四项必须已闭合有符号调整；第一项只决定奠基人附加分，不作为共同准入门。",
        "- 第二项无正式结算但本地通读产物和史料足以支持结算者仍纳入正式池；旧快照跨越摄政窗口且未完成逐轴重审者同样记为待结算；两类对象均不得进入综合分与总排名。",
        "",
        "## 结论",
        "",
        f"- 候选母池：{payload['candidate_pool_count']}人。",
        f"- 正式评价池：{payload['included_count']}人。",
        f"- 当前综合计算就绪：{payload['composite_ready_count']}人。",
        f"- 池内第二项待正式结算：{payload['pending_second_item_count']}人。",
        f"- 池内第一项适用范围待复核：{payload['pending_first_item_scope_count']}人。",
        f"- 池内第一项已判定适用、待正式结算：{payload['pending_first_item_formal_settlement_count']}人。",
        f"- 第一项历史快照中不属201人候选母池：{payload['first_item_outside_candidate_pool_count']}人；保留分项lineage，不进入本池。",
        f"- 排除：{payload['excluded_count']}人。",
        "",
        "## 排除对象",
        "",
        "| 对象 | 政权 | 实权窗口 | 排除理由 |",
        "|---|---|---|---|",
    ]
    reason_order = {
        "EXCLUDED_NO_EFFECTIVE_POWER": 0,
        "EXCLUDED_LIMITED_INDEPENDENT_POWER": 1,
        "EXCLUDED_EFFECTIVE_POWER_LT_3_YEARS": 2,
        "EXCLUDED_INCOMPLETE_COMMON_ITEM_COVERAGE": 3,
    }
    for row in sorted(
        excluded,
        key=lambda value: (reason_order[str(value["exclusion_reason_code"])], str(value["ruler_id"])),
    ):
        lines.append(
            f"| {row['ruler_name']} | {row.get('polity') or '—'} | {row.get('actual_power_window') or '—'} | {row['exclusion_reason']} |"
        )
    pending_second = [
        row for row in included if row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
    ]
    lines.extend(
        [
            "",
            "## 池内第二项待正式结算",
            "",
            "以下对象已经通过实权与时长门；缺少第二项正式分或旧分因实际掌权窗口失效者，在补齐或重审前不得计算综合分或进入总排名：",
            "",
            "| 对象 | 政权 | 实权窗口 | 第二项状态/依据组 | 第一项状态 |",
            "|---|---|---|---|---|",
        ]
    )
    for row in sorted(pending_second, key=lambda value: str(value["ruler_id"])):
        lines.append(
            f"| {row['ruler_name']} | {row.get('polity') or '—'} | {row.get('actual_power_window') or '—'} | "
            f"{((row.get('second_item_window_adjudication') or {}).get('status') or row['evidence_feasibility'].get('second_item_feasibility_group') or 'MISSING_FORMAL_SCORE')} | "
            f"{row['first_item_readiness']} |"
        )
    pending_first = [
        row for row in included
        if row["first_item_readiness"] == "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
    ]
    lines.extend(["", "## 池内第一项正式结算状态", ""])
    if pending_first:
        for row in sorted(pending_first, key=lambda value: str(value["ruler_id"])):
            lines.append(f"- {row['ruler_name']}：{row['first_item_scope_note']}")
    else:
        lines.append("池内第一项适用范围与A/B/C正式结算均已闭合，待正式结算0人。")
    lines.extend(["", "## 第一项池外历史记录", ""])
    lines.append(
        "、".join(row["ruler_name"] for row in payload["first_item_outside_candidate_pool"])
        + "。这些记录保留在第一项正式快照中作为既有结算，但不得被当前评价池或综合计算消费。"
    )
    lines.extend(["", "## 正式池名单", ""])
    for polity in sorted(by_polity):
        names = "、".join(sorted(by_polity[polity]))
        lines.append(f"- {polity}（{len(by_polity[polity])}）：{names}。")
    lines.append("")
    return "\n".join(lines)


def write_canonical_ruler_pool(workspace_root: Path) -> dict[str, Path]:
    payload = build_canonical_ruler_pool(workspace_root)
    json_path = workspace_root / POOL_JSON
    markdown_path = workspace_root / POOL_MARKDOWN
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_canonical_ruler_pool_markdown(payload), encoding="utf-8")
    ranking_payload = build_second_item_eligible_ranking(workspace_root, payload)
    ranking_json_path = workspace_root / SECOND_ITEM_ELIGIBLE_JSON
    ranking_markdown_path = workspace_root / SECOND_ITEM_ELIGIBLE_MARKDOWN
    ranking_json_path.write_text(
        json.dumps(ranking_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ranking_markdown_path.write_text(
        render_second_item_eligible_ranking_markdown(ranking_payload),
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "markdown": markdown_path,
        "second_item_ranking_json": ranking_json_path,
        "second_item_ranking_markdown": ranking_markdown_path,
    }


def verify_canonical_ruler_pool(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / POOL_JSON
    checked_in = _read_json(path)
    rebuilt = build_canonical_ruler_pool(workspace_root)
    if checked_in != rebuilt:
        raise ValueError("正式评价池与当前五项入口重建结果不一致")
    markdown_path = workspace_root / POOL_MARKDOWN
    expected_markdown = render_canonical_ruler_pool_markdown(rebuilt)
    if markdown_path.read_text(encoding="utf-8") != expected_markdown:
        raise ValueError("正式评价池Markdown与机器入口不一致")
    ranking_path = workspace_root / SECOND_ITEM_ELIGIBLE_JSON
    checked_in_ranking = _read_json(ranking_path)
    rebuilt_ranking = build_second_item_eligible_ranking(workspace_root, rebuilt)
    if checked_in_ranking != rebuilt_ranking:
        raise ValueError("第二项正式评价池排名与当前准入池或185人分值快照不一致")
    ranking_markdown_path = workspace_root / SECOND_ITEM_ELIGIBLE_MARKDOWN
    expected_ranking_markdown = render_second_item_eligible_ranking_markdown(rebuilt_ranking)
    if ranking_markdown_path.read_text(encoding="utf-8") != expected_ranking_markdown:
        raise ValueError("第二项正式评价池排名Markdown与机器入口不一致")
    return {
        "path": POOL_JSON,
        "candidate_pool_count": rebuilt["candidate_pool_count"],
        "included_count": rebuilt["included_count"],
        "composite_ready_count": rebuilt["composite_ready_count"],
        "pending_second_item_count": rebuilt["pending_second_item_count"],
        "pending_first_item_scope_count": rebuilt["pending_first_item_scope_count"],
        "pending_first_item_formal_settlement_count": rebuilt[
            "pending_first_item_formal_settlement_count"
        ],
        "first_item_outside_candidate_pool_count": rebuilt[
            "first_item_outside_candidate_pool_count"
        ],
        "excluded_count": rebuilt["excluded_count"],
        "exclusion_reason_counts": rebuilt["exclusion_reason_counts"],
        "second_item_ranked_count": rebuilt_ranking["record_count"],
        "second_item_not_ranked_snapshot_count": rebuilt_ranking[
            "excluded_lineage_record_count"
        ],
    }
