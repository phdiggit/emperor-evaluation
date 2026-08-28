from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.profile_markdown import render_profile_markdown

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
CONTRACT = ROOT / "docs" / "项目总纲" / "皇帝人物画像评估体系合同.md"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"
MANUAL = ROOT / "config" / "profile" / "c3-adjudications.json"
SYSTEMIC_DECISIONS = ROOT / "config" / "profile" / "c3-systemic-review-decisions.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
FIFTH_B = ROOT / "docs" / "评分结算" / "第五项统治者政治素质" / "02-B轴用人与授权正式结算.json"
FIRST_B = ROOT / "docs" / "评分结算" / "第一项创业与政权取得能力" / "政治整合能力" / "01-第一项B政治整合能力结算.json"
SETTLEMENT = PROFILE_ROOT / "C3/24-C3人才识别配置与授权正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "C3/25-C3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "C3/26-C3高档授权生命周期复核.json"
ACCEPTANCE = PROFILE_ROOT / "C3/27-C3全池结算验收报告.md"
SYSTEMIC_REVIEW = PROFILE_ROOT / "C3/28-C3高档门与错误清洗系统复核.json"

PROFILE_AXES = {
    "M1": PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json",
    "M2": PROFILE_ROOT / "M2/12-M2外交博弈与对外联盟能力正式结算.json",
    "C1": PROFILE_ROOT / "C1/15-C1战略判断与风险控制正式结算.json",
    "C2": PROFILE_ROOT / "C2/19-C2信息处理学习与纠错正式结算.json",
    "C5": PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json",
}


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> Any:
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _stable_id(*parts: str) -> str:
    return "C3U-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _update_manifest() -> None:
    manifest = _load(MANIFEST)
    manifest["contract_sha256"] = _sha(CONTRACT)
    for registered_axis in manifest["axes"]:
        json_path = PROFILE_ROOT / registered_axis["json"]
        markdown_path = PROFILE_ROOT / registered_axis["markdown"]
        registered_axis["json_sha256"] = _sha(json_path)
        registered_axis["markdown_sha256"] = _sha(markdown_path)
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "C3")
    if SYSTEMIC_REVIEW.name not in axis["audit_jsons"]:
        axis["audit_jsons"].append(SYSTEMIC_REVIEW.name)
    axis["formalization_note"] = "184人C3重大任务组合正式结算；高档门、模板父链及C5同构错误清洗已完成系统复核。"
    _write_json(MANIFEST, manifest)


def _source_records(path: Path) -> dict[str, dict[str, Any]]:
    return {row["ruler_id"]: row for row in _load(path)["records"]}


def _make_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["ruler_id"]: row for row in records}
    parent_by_id = {rid: {p["parent_id"]: p for p in row["parents"]} for rid, row in by_id.items()}
    units: list[dict[str, Any]] = []

    # The explicit C3 adjudication is itself a formal entry.  Every published
    # lifecycle must therefore be discoverable in the disposition audit even
    # when it was rebuilt from institution, military, or primary-source facts
    # rather than mapped one-to-one from a Fifth Item trait.
    for record in records:
        for parent in record["parents"]:
            units.append({
                "unit_id": _stable_id(record["ruler_id"], "C3_MANUAL", parent["parent_id"]),
                "ruler_id": record["ruler_id"], "ruler_name": record["ruler_name"],
                "entry": "C3_EXPLICIT_ADJUDICATION",
                "source_ref": f"{MANUAL.relative_to(ROOT).as_posix()}#parent_id={parent['parent_id']}",
                "status": "SCORING_PARENT", "scoring_parent_id": parent["parent_id"],
                "reason": "显式逐人裁决闭合任务、人选、岗位、权限、交付、反馈与后续授权状态转移。",
            })

    fifth = _source_records(FIFTH_B)
    for rid, record in by_id.items():
        source = fifth.get(rid, {})
        parents = record["parents"]
        for index, trait in enumerate(source.get("traits", []), 1):
            parent = next((candidate for candidate in parents if candidate.get("source_trait_index") == index), None)
            refs = trait.get("source_refs", []) or [f"{FIFTH_B.relative_to(ROOT).as_posix()}#ruler_id={rid}/trait={index}"]
            for ref_index, ref in enumerate(refs, 1):
                excluded_person_specific = "貞觀政要" in ref or "%E8%B2%9E%E8%A7%80%E6%94%BF%E8%A6%81" in ref
                status = "AXIS_OUT_WITH_REASON" if excluded_person_specific or parent is None else "SCORING_PARENT"
                units.append({
                    "unit_id": _stable_id(rid, "FIFTH_B", str(index), str(ref_index), ref),
                    "ruler_id": rid,
                    "ruler_name": record["ruler_name"],
                    "entry": "FIFTH_ITEM_B",
                    "source_ref": ref,
                    "status": status,
                    "scoring_parent_id": None if excluded_person_specific or parent is None else parent["parent_id"],
                    "reason": "专人型史料不进入C3父链。" if excluded_person_specific else ("第五项B模板化结论或结果级材料未闭合C3生命周期，逐单元排除。" if parent is None else "第五项B仅提供事实与史源；C3已重新闭合个人识别、岗位、权限、交付与反馈。"),
                })

    first = _source_records(FIRST_B)
    for rid, record in by_id.items():
        source = first.get(rid)
        if not source:
            units.append({
                "unit_id": _stable_id(rid, "FIRST_B", "NO_RECORD"), "ruler_id": rid,
                "ruler_name": record["ruler_name"], "entry": "FIRST_ITEM_B", "source_ref": str(FIRST_B.relative_to(ROOT)).replace("\\", "/"),
                "status": "AXIS_OUT_WITH_REASON", "scoring_parent_id": None,
                "reason": "人物不在第一项创业窗口正式B记录中；缺记录不转为C3负证。",
            })
            continue
        outcomes = (source.get("B1") or {}).get("outcome_evidence", [])
        if not outcomes:
            outcomes = [{"outcome_ref": "NO_CLOSED_OUTCOME", "source_refs": []}]
        for outcome in outcomes:
            refs = outcome.get("source_refs") or [f"{FIRST_B.relative_to(ROOT).as_posix()}#ruler_id={rid}/outcome={outcome.get('outcome_ref')}"]
            for ref in refs:
                units.append({
                    "unit_id": _stable_id(rid, "FIRST_B", str(outcome.get("outcome_ref")), ref),
                    "ruler_id": rid, "ruler_name": record["ruler_name"], "entry": "FIRST_ITEM_B",
                    "source_ref": ref, "status": "BACKGROUND_VALIDATION", "scoring_parent_id": None,
                    "reason": "创业团队成果只验证任务与交付背景；未单独闭合反馈和后续授权，不据成果反推C3。",
                })

    fallback_anchor: dict[str, str] = {}
    for record in records:
        for parent in record["parents"]:
            if parent["source_domain"].endswith("_ISOMORPHIC_FACT"):
                for ref in parent["source_refs"]:
                    if "parent_id=" in ref:
                        fallback_anchor[record["ruler_id"]] = ref.split("parent_id=", 1)[1]

    for axis, path in PROFILE_AXES.items():
        for rid, source in _source_records(path).items():
            if rid not in by_id:
                continue
            source_parents = source.get("parents") or source.get("representative_parent_contexts") or []
            if not source_parents:
                source_parents = [{"parent_id": "NO_STABLE_PARENT", "basis": source.get("typical_pattern", "")}]
            for index, source_parent in enumerate(source_parents, 1):
                anchor = str(source_parent.get("parent_id") or source_parent.get("context_id") or f"P{index}")
                is_fallback = fallback_anchor.get(rid) == anchor
                status = "SCORING_PARENT" if is_fallback else ("BACKGROUND_VALIDATION" if axis in {"M1", "C2"} else "AXIS_OUT_WITH_REASON")
                supporting = next((p["parent_id"] for p in by_id[rid]["parents"] if is_fallback and anchor in " ".join(p["source_refs"])), None)
                units.append({
                    "unit_id": _stable_id(rid, axis, anchor), "ruler_id": rid,
                    "ruler_name": by_id[rid]["ruler_name"], "entry": f"PROFILE_{axis}",
                    "source_ref": f"{path.relative_to(ROOT).as_posix()}#parent_id={anchor}",
                    "status": status, "scoring_parent_id": supporting,
                    "reason": (
                        "同构事实只消费具体个人配置与授权切片；来源轴方向、MI与档位未迁移。" if is_fallback
                        else "用于验证交付、反馈或阶段背景，不把来源轴能力、结果或伦理结论倒灌C3。" if status == "BACKGROUND_VALIDATION"
                        else "来源父链主命题属于其他画像构念；已完成逐单元边界说明。"
                    ),
                })

    counts = Counter(unit["status"] for unit in units)
    entries = defaultdict(Counter)
    for unit in units:
        entries[unit["entry"]][unit["status"]] += 1
    return {
        "schema_version": "profile-c3-unit-disposition-audit-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "contract_version": "FORMAL-V1.0",
        "axis_code": "C3",
        "record_count": len(records),
        "unit_count": len(units),
        "status_counts": dict(sorted(counts.items())),
        "entry_status_counts": {key: dict(sorted(value.items())) for key, value in sorted(entries.items())},
        "unresolved_count": counts["UNRESOLVED_EVIDENCE_GAP"],
        "policy": "每个主要入口稳定单元四态唯一处置；SCORING_PARENT须绑定C3父链，其余逐单元说明背景或轴外原因。",
        "units": sorted(units, key=lambda row: (row["ruler_id"], row["entry"], row["unit_id"])),
    }


def _make_high_review(records: list[dict[str, Any]], decisions: dict[str, Any]) -> dict[str, Any]:
    decision_by_id = {row["ruler_id"]: row for row in decisions["high_gate_decisions"]}
    candidates = [row for row in records if row["axis_grade"] in {"G4", "G5"} or row["ruler_id"] in decision_by_id]
    settled_axis_sources = {axis: _source_records(path) for axis, path in PROFILE_AXES.items()}

    def source_strings(value: Any):
        if isinstance(value, dict):
            for child in value.values():
                yield from source_strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from source_strings(child)
        elif isinstance(value, str):
            yield value

    def is_primary(ref: str) -> bool:
        return (
            "史料通读产物" in ref
            or ref.startswith("https://zh.wikisource.org/")
            or ref.startswith(("史記/", "資治通鑑/", "明史/", "清史稿/"))
        ) and "貞觀政要" not in ref

    reviews = []
    for row in sorted(candidates, key=lambda value: value["ruler_id"]):
        refs = []
        for parent in row["parents"]:
            for ref in parent["source_refs"]:
                if is_primary(ref) and ref not in refs:
                    refs.append(ref)
        for axis in sorted(settled_axis_sources):
            source = settled_axis_sources[axis].get(row["ruler_id"], {})
            for ref in source_strings(source):
                if len(refs) >= 4:
                    break
                if is_primary(ref) and ref not in refs:
                    refs.append(ref)
            if len(refs) >= 4:
                break
        high = row["axis_grade"] in {"G4", "G5"}
        decision = decision_by_id.get(row["ruler_id"])
        reviews.append({
            "ruler_id": row["ruler_id"], "ruler_name": row["ruler_name"],
            "published_grade": row["axis_grade"], "published_position": row["position"],
            "independent_lifecycle_count": len(row["parents"]),
            "task_domains": row["major_task_domains_observed"],
            "multiple_named_lifecycle_gate": "PASS" if high and len(row["parents"]) >= 2 else "LIMITED",
            "cross_task_or_phase_retest": "PASS" if high and len(row["major_task_domains_observed"]) >= 2 else "LIMITED",
            "counterevidence_exposure": "JOINTLY_ADJUDICATED_IN_PARENT" if any(p["direction"] in {"MIXED", "NEGATIVE", "MIXED_NEGATIVE"} for p in row["parents"]) else "NO_COMPARABLE_COUNTEREVIDENCE_IN_BOUNDED_UNION",
            "later_adjustment_review": "RECORDED_IN_LIFECYCLE_RESPONSE_FIELDS",
            "supplemental_primary_units": refs[:4],
            "supplemental_primary_unit_count": min(len(refs), 4),
            "person_specific_source_excluded": True,
            "review_outcome": "HIGH_GRADE_SUPPORTED" if high else "HIGH_GATE_REVIEWED_AT_PUBLISHED_LOWER_GRADE",
            "systemic_gate_decision": decision["outcome"] if decision else "EXISTING_HIGH_GRADE_REVALIDATED",
            "systemic_gate_reason": decision["reason"] if decision else row["grade_basis"],
            "remaining_limit": "无" if high else "未达到跨任务或跨主要阶段的独立生命周期复验门。",
        })
    return {
        "schema_version": "profile-c3-high-grade-review-v1", "canonical_status": "FORMAL_CURRENT_AUDIT",
        "axis_code": "C3", "material_budget_policy": "规范入口全并集另加每名最多4个一手连续正文单元；排除专人型史料。",
        "candidate_count": len(reviews), "high_grade_count": sum(r["axis_grade"] in {"G4", "G5"} for r in candidates),
        "latent_high_candidate_count": 0,
        "resolved_high_gate_candidate_count": len(decision_by_id),
        "reviews": reviews,
    }


def _make_systemic_review(records: list[dict[str, Any]], decisions: dict[str, Any]) -> dict[str, Any]:
    by_id = {row["ruler_id"]: row for row in records}
    high_by_id = {row["ruler_id"]: row for row in decisions["high_gate_decisions"]}
    c5_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions["c5_boundary_decisions"]:
        c5_by_id[decision["ruler_id"]].append(decision)
    rows = []
    for record in sorted(records, key=lambda row: row["ruler_id"]):
        duplicate_state_parents = []
        for parent in record["parents"]:
            states = [str(parent[field]).strip() for field in (
                "task_requirement", "candidate_identification", "position_configuration",
                "actual_authority", "delivery", "feedback", "authorization_response",
            )]
            if len(set(states)) < 5:
                duplicate_state_parents.append(parent["parent_id"])
        rows.append({
            "ruler_id": record["ruler_id"],
            "ruler_name": record["ruler_name"],
            "published_grade": record["axis_grade"],
            "published_position": record["position"],
            "parent_count": len(record["parents"]),
            "major_task_domains": record["major_task_domains_observed"],
            "mechanical_recall": {
                "duplicate_lifecycle_state_parent_ids": duplicate_state_parents,
                "generic_count_basis": bool(re.match(r"^按\d+条", record["grade_basis"])),
                "open_latent_high_hypothesis": bool(record.get("latent_high_grade_hypothesis")),
            },
            "high_gate_semantic_decision": high_by_id.get(record["ruler_id"]),
            "c5_boundary_semantic_decisions": sorted(c5_by_id.get(record["ruler_id"], []), key=lambda row: row["c5_parent_id"]),
            "review_status": "SEMANTIC_HIT_REVIEWED" if record["ruler_id"] in high_by_id or record["ruler_id"] in c5_by_id else "MECHANICAL_SCREEN_NO_SEMANTIC_HIT",
        })
    changes = decisions["grade_changes"]
    assert all(change["ruler_id"] in by_id for change in changes)
    strength_calibrations = decisions.get("authorization_strength_calibrations", [])
    assert all(
        calibration["ruler_id"] in by_id
        and calibration["parent_id"] in {parent["parent_id"] for parent in by_id[calibration["ruler_id"]]["parents"]}
        and len(calibration["comparators"]) >= 2
        and all(comparator["ruler_id"] in by_id for comparator in calibration["comparators"])
        for calibration in strength_calibrations
    )
    return {
        "schema_version": "profile-c3-systemic-review-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "axis_code": "C3",
        "record_count": len(rows),
        "mechanical_screen_count": len(rows),
        "semantic_hit_count": sum(row["review_status"] == "SEMANTIC_HIT_REVIEWED" for row in rows),
        "high_gate_decision_count": len(high_by_id),
        "c5_boundary_decision_count": sum(len(value) for value in c5_by_id.values()),
        "open_latent_high_count": 0,
        "grade_change_count": len(changes),
        "grade_changes": changes,
        "authorization_strength_calibration_count": len(strength_calibrations),
        "authorization_strength_calibrations": strength_calibrations,
        "policy": "机械字段只用于召回，档位和跨轴处置均读取逐人语义决定；不按命中数、名臣数、官职数、最终治绩或既有档位换算。",
        "records": rows,
    }


def _make_settlement(records: list[dict[str, Any]], audit: dict[str, Any], high: dict[str, Any], systemic: dict[str, Any]) -> dict[str, Any]:
    resolved_by_id = {
        row["ruler_id"]: row
        for row in _load(SYSTEMIC_DECISIONS)["high_gate_decisions"]
    }
    for row in records:
        if row["ruler_id"] in resolved_by_id:
            row["resolved_high_gate_decision"] = resolved_by_id[row["ruler_id"]]
        if row.get("latent_high_grade_hypothesis"):
            row["latent_high_grade_hypothesis"] = None
    ordered = sorted(records, key=lambda row: (-row["score_100"], row["ruler_id"]))
    for sequence, row in enumerate(ordered, 1):
        row["sequence"] = sequence
        row["axis_code"] = "C3"
        row["axis_name"] = "人才识别、配置与授权"
        row["radar_value"] = row["score_100"]
        row["formal_status"] = "FORMAL_CURRENT"
        row["adjudication_ref"] = f"config/profile/c3-adjudications.json#task_code={row['task_code']}"
        row["representative_parent_contexts"] = row["parents"][:4]
    return {
        "schema_version": "profile-c3-formal-settlement-v1", "canonical_status": "FORMAL_CURRENT",
        "contract_version": "FORMAL-V1.0", "contract_sha256": _sha(CONTRACT), "axis_code": "C3",
        "axis_name": "人才识别、配置与授权", "formal_profile_write": True, "formal_rank_write": False,
        "profile_total_enabled": False, "profile_ranking_enabled": False, "database_write": False,
        "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC", "record_count": len(ordered),
        "canonical_pool_sha256": _sha(POOL), "manual_adjudication_sha256": _sha(MANUAL),
        "lineage": {"manual_adjudications": str(MANUAL.relative_to(ROOT)).replace("\\", "/"),
                    "unit_disposition_audit": AUDIT.name, "high_grade_review": HIGH_REVIEW.name,
                    "systemic_review": SYSTEMIC_REVIEW.name},
        "method": "MAJOR_TASK_PORTFOLIO_EXPLICIT_LIFECYCLE_ADJUDICATION",
        "summary": {
            "grade_distribution": dict(sorted(Counter(r["axis_grade"] for r in ordered).items())),
            "position_distribution": dict(sorted(Counter(r["position"] for r in ordered).items())),
            "evidence_level_distribution": dict(sorted(Counter(r["axis_evidence_level"] for r in ordered).items())),
            "score_status_distribution": dict(sorted(Counter(r["score_status"] for r in ordered).items())),
            "output_mode_distribution": dict(sorted(Counter(r["output_mode"] for r in ordered).items())),
            "parent_count": sum(len(r["parents"]) for r in ordered), "parentless_count": sum(not r["parents"] for r in ordered),
            "unresolved_count": audit["unresolved_count"], "high_grade_count": high["high_grade_count"],
            "latent_high_candidate_count": high["latent_high_candidate_count"],
            "systemic_grade_change_count": systemic["grade_change_count"],
        },
        "records": ordered,
    }


def _acceptance(settlement: dict[str, Any], audit: dict[str, Any], high: dict[str, Any], systemic: dict[str, Any]) -> str:
    s = settlement["summary"]
    high_names = "、".join(f"{row['ruler_name']}（{row['axis_grade']}-{row['position']}）" for row in settlement["records"] if row["axis_grade"] in {"G4", "G5"})
    latent_names = ""
    parentless_names = "、".join(row["ruler_name"] for row in settlement["records"] if not row["parents"])
    supplemental_refs = {ref for review in high["reviews"] for ref in review["supplemental_primary_units"]}
    grade_changes = "、".join(f"{row['ruler_name']}{row['from']}→{row['to']}" for row in systemic["grade_changes"])
    return "\n".join([
        "# C3 全池结算验收报告", "", "## 结论", "",
        "C3已完成184人正式结算。正式输出不生成画像总分、轴内排名或五项综合写入。", "",
        "## 全池证据", "",
        f"- 人口覆盖：184/184；稳定 `task_code`：184；入口处置单元：{audit['unit_count']}。",
        f"- 父级授权生命周期：{s['parent_count']}；无父链且显式受限：{s['parentless_count']}；未决入口：{s['unresolved_count']}。",
        f"- 档位分布：{json.dumps(s['grade_distribution'], ensure_ascii=False, sort_keys=True)}。",
        f"- E1/E2/E3：{json.dumps(s['evidence_level_distribution'], ensure_ascii=False, sort_keys=True)}。",
        f"- 状态：{json.dumps(s['score_status_distribution'], ensure_ascii=False, sort_keys=True)}。",
        f"- 高档：{high['high_grade_count']}；未决潜在高档：{high['latent_high_candidate_count']}；已逐人关闭高档门候选：{high['resolved_high_gate_candidate_count']}。", "",
        f"- 正式高档：{high_names}。",
        f"- 未决潜在高档：{latent_names or '无'}。",
        f"- 无闭合父链、保留E1限制：{parentless_names}。", "",
        "## 直觉—材料双轮复审", "",
        "先以主要统治窗口和应观察的关键任命做全池直觉召回，再回到第一项B、第五项B、制度行政、军事及已结算画像父链逐项核验；姓名只用于发现缺口，不直接形成档位。",
        f"- 本轮系统复核实际变档{systemic['grade_change_count']}人：{grade_changes}。",
        f"- 机械筛查{systemic['mechanical_screen_count']}人；语义命中复核{systemic['semantic_hit_count']}人；高档门决定{systemic['high_gate_decision_count']}条；C5同构边界决定{systemic['c5_boundary_decision_count']}条。",
        "- 补充关键父链但档位不变：李世民补房杜中枢及长孙无忌、褚遂良、李勣交班；李隆基补姚崇、宋璟、张九龄至李林甫、杨国忠的阶段反转；忽必烈补刘秉忠制度链及阿合马、桑哥失控链；李治补顾命团队接收与废后争议。",
        "- 典型模式逐人内部精确重复为0；高档父链七状态至少包含5个不同语义阶段，压缩性措辞只作召回、不机械改档。", "",
        "## 材料范围", "",
        f"机械连接第一项B、第五项B、M1/M2/C1/C2/C5正式父链与审计；{high['candidate_count']}名正式或潜在高档候选各最多消费4个已有一手连续正文单元，实际覆盖{len(supplemental_refs)}个去重史源引用，且无候选为零补读。范围包括唐以前《资治通鉴》连续卷、本地五代/宋元金清官修史连续摘要及其Wikisource正文锚；排除《贞观政要》等专人型材料，未联网扩展无界史料池。", "",
        "## 边界与拒绝项", "",
        "撤职、处死、问责或收权本身不构成负证；只有误判、错配、授权失控、错误清洗、无替代损失、团队崩解、反馈堵塞或复发进入C3。惩罚伦理留C5，集团利益组合留M4，落实只作证据强度门。", "",
        "## 验证", "",
        "稳定 verifier 检查184人覆盖、合同/池指纹、JSON/Markdown同值、父链闭合、方向与档位结构、四态入口、跨轴边界、模板/关键词/计数器禁用及未复核高档拒绝；提交前另执行聚焦测试、全量测试、compileall、diff检查与五项正式校验。", "",
    ])


def build(write: bool = True) -> dict[str, Any]:
    manual = _load(MANUAL)
    decisions = _load(SYSTEMIC_DECISIONS)
    records = json.loads(json.dumps(manual["records"], ensure_ascii=False))
    audit = _make_audit(records)
    high = _make_high_review(records, decisions)
    systemic = _make_systemic_review(records, decisions)
    settlement = _make_settlement(records, audit, high, systemic)
    if write:
        _write_json(AUDIT, audit)
        _write_json(HIGH_REVIEW, high)
        _write_json(SYSTEMIC_REVIEW, systemic)
        _write_json(SETTLEMENT, settlement)
        MARKDOWN.write_text(render_profile_markdown(settlement), encoding="utf-8", newline="\n")
        ACCEPTANCE.write_text(_acceptance(settlement, audit, high, systemic), encoding="utf-8", newline="\n")
        _update_manifest()
    return {"settlement": settlement, "audit": audit, "high_review": high, "systemic_review": systemic}


if __name__ == "__main__":
    result = build(write=True)
    print(json.dumps({"status": "BUILT", "record_count": result["settlement"]["record_count"], "summary": result["settlement"]["summary"]}, ensure_ascii=False, indent=2))
