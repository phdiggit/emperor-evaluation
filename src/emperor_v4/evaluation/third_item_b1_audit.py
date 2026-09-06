from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


AB_ROUTER_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
ANCHOR_PATH = Path("config/third-item/third-item-b1-region-anchors.json")
AUDIT_JSON_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/02-B1机械一致性审计.json")
AUDIT_MD_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/02-B1机械一致性审计.md")

TOL = 1e-6


@dataclass(frozen=True)
class AuditIssue:
    code: str
    severity: str
    message: str
    details: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.details:
            payload["details"] = dict(self.details)
        return payload


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records_from_shard(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    collections = payload.get("collections")
    if isinstance(collections, Mapping):
        records = collections.get("records")
        if isinstance(records, Mapping):
            rows = records.get("records")
            if isinstance(rows, list):
                return [dict(row) for row in rows]
    rows = payload.get("records")
    if isinstance(rows, list):
        return [dict(row) for row in rows]
    raise ValueError("AB分片缺少collections.records.records或records数组")


def _load_all_records(workspace_root: Path) -> list[dict[str, Any]]:
    router_path = workspace_root / AB_ROUTER_PATH
    router = _load(router_path)
    base = router_path.parent
    result: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for route in router.get("routes") or ():
        shard_path = base / str(route["path"])
        shard = _load(shard_path)
        rows = _records_from_shard(shard)
        expected = int((route.get("collection_counts") or {}).get("records", len(rows)))
        if len(rows) != expected:
            raise ValueError(f"{shard_path}记录数不符：{len(rows)} != {expected}")
        for row in rows:
            name = str(row.get("ruler_name") or "")
            if not name:
                raise ValueError(f"{shard_path}存在无ruler_name记录")
            if name in seen_names:
                raise ValueError(f"AB分片存在重复评价主体：{name}")
            seen_names.add(name)
            row["_audit_shard"] = str(route["path"])
            result.append(row)
    declared = int((router.get("collections") or {}).get("records", {}).get("record_count", len(result)))
    if len(result) != declared:
        raise ValueError(f"AB路由记录数不符：{len(result)} != {declared}")
    return result


def _anchor_index(payload: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, dict[str, Any]], list[set[str]], set[float]]:
    anchors = {str(row["region_id"]): dict(row) for row in payload.get("anchors") or ()}
    aliases = {str(key): str(value) for key, value in (payload.get("legacy_aliases") or {}).items()}
    must_rebuild = {
        str(row["legacy_id"]): dict(row)
        for row in payload.get("legacy_must_rebuild") or ()
    }
    overlap_sets = [
        {str(member) for member in group.get("members") or ()}
        for group in payload.get("mutual_exclusion_sets") or ()
    ]
    coverage_steps = {float(value) for value in payload["policy"]["coverage_steps"]}
    return anchors, aliases, must_rebuild, overlap_sets, coverage_steps


def _canonical_region_id(region_id: str, anchors: Mapping[str, Any], aliases: Mapping[str, str]) -> str | None:
    if region_id in anchors:
        return region_id
    target = aliases.get(region_id)
    if target in anchors:
        return target
    return None


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _close(left: float, right: float, tol: float = TOL) -> bool:
    return abs(left - right) <= tol


def _grade_for_weighted(value: float) -> str:
    if value <= 0:
        return "B1-0"
    if value < 0.75:
        return "B1-1"
    if value < 1.5:
        return "B1-2"
    if value < 3.0:
        return "B1-3"
    if value < 6.0:
        return "B1-4"
    return "B1-5"


def _rate(record: Mapping[str, Any], key: str) -> float | None:
    adjudication = record.get("B80_adjudication") or {}
    return _numeric(adjudication.get(key)) if isinstance(adjudication, Mapping) else None


def _axis_b1(record: Mapping[str, Any]) -> Mapping[str, Any]:
    axes = record.get("axes") or {}
    b1 = axes.get("B1") if isinstance(axes, Mapping) else None
    return b1 if isinstance(b1, Mapping) else {}


def _issue(code: str, severity: str, message: str, **details: Any) -> AuditIssue:
    return AuditIssue(code=code, severity=severity, message=message, details=details or None)


def _audit_snapshot_regions(
    record: Mapping[str, Any],
    issues: list[AuditIssue],
    *,
    anchors: Mapping[str, Mapping[str, Any]],
    aliases: Mapping[str, str],
    must_rebuild: Mapping[str, Mapping[str, Any]],
    overlap_sets: Sequence[set[str]],
    coverage_steps: set[float],
) -> tuple[float, float]:
    control = record.get("b1_region_control")
    if not isinstance(control, Mapping):
        issues.append(_issue("B1_REGION_CONTROL_MISSING", "BLOCKER", "缺少b1_region_control。"))
        return 0.0, 0.0

    totals: dict[str, float] = {}
    for anchor_name in ("start", "end"):
        snapshot = control.get(anchor_name)
        if snapshot is None:
            issues.append(_issue("B1_SNAPSHOT_MISSING", "BLOCKER", f"缺少{anchor_name}区域快照。", anchor=anchor_name))
            snapshot = {}
        if not isinstance(snapshot, Mapping):
            issues.append(_issue("B1_SNAPSHOT_INVALID", "BLOCKER", f"{anchor_name}区域快照不是对象。", anchor=anchor_name))
            snapshot = {}

        total = 0.0
        active: set[str] = set()
        for raw_id, raw_value in snapshot.items():
            region_id = str(raw_id)
            value = _numeric(raw_value)
            if value is None:
                issues.append(_issue("B1_SNAPSHOT_VALUE_NONNUMERIC", "BLOCKER", "区域快照值不是数值。", anchor=anchor_name, region_id=region_id))
                continue
            total += value
            if value <= TOL:
                continue

            if region_id in must_rebuild:
                issues.append(_issue("B1_MUST_REBUILD_REGION", "BLOCKER", "区域ID属于禁止直接迁移的旧聚合对象。", anchor=anchor_name, region_id=region_id))
                continue
            canonical = _canonical_region_id(region_id, anchors, aliases)
            if canonical is None:
                issues.append(_issue("B1_UNKNOWN_REGION_ID", "BLOCKER", "区域ID未进入统一锚点表或旧ID映射。", anchor=anchor_name, region_id=region_id))
                continue
            if region_id != canonical:
                issues.append(_issue("B1_LEGACY_REGION_ALIAS", "WARN", "仍在使用旧区域ID，重审时应迁移为规范ID。", anchor=anchor_name, region_id=region_id, canonical_region_id=canonical))
            active.add(canonical)
            weight = float(anchors[canonical]["spatial_weight"])
            if value > weight + TOL:
                issues.append(_issue("B1_SNAPSHOT_EXCEEDS_ANCHOR", "BLOCKER", "受控空间当量超过统一空间基准。", anchor=anchor_name, region_id=region_id, value=value, spatial_weight=weight))
                continue
            coverage = value / weight
            if not any(_close(coverage, step) for step in coverage_steps):
                issues.append(_issue("B1_SNAPSHOT_NONSTANDARD_COVERAGE", "BLOCKER", "快照当量不能由统一空间基准×标准覆盖阶梯得到。", anchor=anchor_name, region_id=region_id, value=value, spatial_weight=weight, inferred_coverage=round(coverage, 6)))

        for group in overlap_sets:
            used = sorted(active & group)
            if len(used) > 1:
                issues.append(_issue("B1_OVERLAPPING_ANCHORS", "BLOCKER", "同一快照同时使用互斥空间锚，存在重复消费风险。", anchor=anchor_name, region_ids=used))
        totals[anchor_name] = round(total, 9)

    return totals.get("start", 0.0), totals.get("end", 0.0)


def _audit_region_ledger(
    record: Mapping[str, Any],
    issues: list[AuditIssue],
    *,
    anchors: Mapping[str, Mapping[str, Any]],
    aliases: Mapping[str, str],
    must_rebuild: Mapping[str, Mapping[str, Any]],
    coverage_steps: set[float],
    start_total: float,
    end_total: float,
) -> None:
    ledger = record.get("b1_region_adjudications")
    axis = _axis_b1(record)
    score_rate = _numeric(axis.get("score_rate")) or 0.0
    if not isinstance(ledger, list):
        issues.append(_issue("B1_REGION_LEDGER_MISSING", "BLOCKER", "缺少b1_region_adjudications数组。"))
        return
    if not ledger:
        if start_total > TOL or end_total > TOL or score_rate > TOL:
            issues.append(_issue("B1_EMPTY_LEDGER_NONZERO", "BLOCKER", "B1存在非零快照或得分，但逐区域裁决账为空。", start_total=start_total, end_total=end_total, score_rate=score_rate))
        return

    status = str(record.get("b1_region_ledger_status") or "")
    if status == "LEGACY_AGGREGATE_REQUIRES_REGION_MIGRATION":
        issues.append(_issue("B1_LEGACY_AGGREGATE_LEDGER", "BLOCKER", "记录明确标记为旧聚合账，必须迁移后才能重新score_ready。"))

    for index, row in enumerate(ledger):
        if not isinstance(row, Mapping):
            issues.append(_issue("B1_LEDGER_ROW_INVALID", "BLOCKER", "逐区域裁决项不是对象。", index=index))
            continue
        if row.get("counted") is False:
            continue
        raw_id = row.get("object_id", row.get("region_id"))
        if raw_id is None:
            issues.append(_issue("B1_LEDGER_REGION_ID_MISSING", "BLOCKER", "逐区域裁决缺少object_id/region_id。", index=index))
            continue
        region_id = str(raw_id)
        if region_id in must_rebuild:
            issues.append(_issue("B1_MUST_REBUILD_LEDGER_REGION", "BLOCKER", "逐区域裁决使用禁止直接迁移的旧聚合对象。", index=index, region_id=region_id))
            continue
        canonical = _canonical_region_id(region_id, anchors, aliases)
        if canonical is None:
            issues.append(_issue("B1_UNKNOWN_LEDGER_REGION", "BLOCKER", "逐区域裁决的区域ID不在统一锚点表。", index=index, region_id=region_id))
            continue
        weight = float(anchors[canonical]["spatial_weight"])
        explicit_weight = _numeric(row.get("spatial_weight"))
        if explicit_weight is not None and not _close(explicit_weight, weight):
            issues.append(_issue("B1_NONCANONICAL_SPATIAL_WEIGHT", "BLOCKER", "逐区域裁决的spatial_weight与统一锚点不一致。", index=index, region_id=region_id, stored=explicit_weight, canonical=weight))

        coverage_values: list[tuple[str, float]] = []
        scalar_coverage = _numeric(row.get("coverage_factor"))
        if scalar_coverage is not None:
            coverage_values.append(("coverage_factor", scalar_coverage))
        for key in ("start_coverage", "end_coverage"):
            value = _numeric(row.get(key))
            if value is not None:
                coverage_values.append((key, value))
        for key, value in coverage_values:
            if not any(_close(value, step) for step in coverage_steps):
                issues.append(_issue("B1_NONSTANDARD_LEDGER_COVERAGE", "BLOCKER", "逐区域裁决使用非标准覆盖阶梯。", index=index, region_id=region_id, field=key, value=value))


def audit_record(record: Mapping[str, Any], anchor_payload: Mapping[str, Any]) -> dict[str, Any]:
    anchors, aliases, must_rebuild, overlap_sets, coverage_steps = _anchor_index(anchor_payload)
    issues: list[AuditIssue] = []

    start_sum, end_sum = _audit_snapshot_regions(
        record,
        issues,
        anchors=anchors,
        aliases=aliases,
        must_rebuild=must_rebuild,
        overlap_sets=overlap_sets,
        coverage_steps=coverage_steps,
    )
    _audit_region_ledger(
        record,
        issues,
        anchors=anchors,
        aliases=aliases,
        must_rebuild=must_rebuild,
        coverage_steps=coverage_steps,
        start_total=start_sum,
        end_total=end_sum,
    )

    totals = record.get("b1_control_equivalents")
    if not isinstance(totals, Mapping):
        issues.append(_issue("B1_TOTALS_MISSING", "BLOCKER", "缺少b1_control_equivalents。"))
        stored_start = stored_end = stored_net = stored_weighted = None
    else:
        stored_start = _numeric(totals.get("start"))
        stored_end = _numeric(totals.get("end"))
        stored_net = _numeric(totals.get("net_change"))
        stored_weighted = _numeric(totals.get("weighted_value"))
        for key, value in (("start", stored_start), ("end", stored_end), ("net_change", stored_net), ("weighted_value", stored_weighted)):
            if value is None:
                issues.append(_issue("B1_TOTAL_FIELD_MISSING", "BLOCKER", f"b1_control_equivalents.{key}缺失或非数值。", field=key))

    if stored_start is not None and not _close(stored_start, start_sum):
        issues.append(_issue("B1_START_TOTAL_MISMATCH", "BLOCKER", "逐区域start求和与总快照不一致。", region_sum=start_sum, stored=stored_start))
    if stored_end is not None and not _close(stored_end, end_sum):
        issues.append(_issue("B1_END_TOTAL_MISMATCH", "BLOCKER", "逐区域end求和与总快照不一致。", region_sum=end_sum, stored=stored_end))

    if stored_start is not None and stored_end is not None:
        expected_net = stored_end - stored_start
        excluded_weighted = _numeric(
            record.get("b1_cross_item_excluded_weighted_value")
        ) or 0.0
        expected_weighted = stored_end - 0.6 * stored_start - excluded_weighted
        if stored_net is not None and not _close(stored_net, expected_net):
            issues.append(_issue("B1_NET_CHANGE_MISMATCH", "BLOCKER", "net_change不等于end-start。", expected=round(expected_net, 9), stored=stored_net))
        if stored_weighted is not None and not _close(stored_weighted, expected_weighted):
            issues.append(_issue("B1_WEIGHTED_VALUE_MISMATCH", "BLOCKER", "weighted_value不等于end-0.6×start扣除跨项排除值。", expected=round(expected_weighted, 9), stored=stored_weighted, cross_item_excluded=excluded_weighted))

    axis = _axis_b1(record)
    grade = str(axis.get("grade") or "")
    axis_raw_net = _numeric(axis.get("raw_net_change"))
    axis_weighted = _numeric(axis.get("weighted_control_value"))
    axis_rate = _numeric(axis.get("score_rate"))
    if stored_weighted is not None:
        expected_grade = _grade_for_weighted(stored_weighted)
        if grade and grade != expected_grade:
            issues.append(_issue("B1_GRADE_MISMATCH", "BLOCKER", "B1档位与weighted_value机械阈值不一致。", expected=expected_grade, stored=grade, weighted_value=stored_weighted))
    if axis_raw_net is not None and stored_net is not None and not _close(axis_raw_net, stored_net):
        issues.append(_issue("B1_AXIS_RAW_NET_MISMATCH", "BLOCKER", "axes.B1.raw_net_change与总账不一致。", axis=axis_raw_net, totals=stored_net))
    if axis_weighted is not None and stored_weighted is not None and not _close(axis_weighted, stored_weighted):
        issues.append(_issue("B1_AXIS_WEIGHTED_MISMATCH", "BLOCKER", "axes.B1.weighted_control_value与总账不一致。", axis=axis_weighted, totals=stored_weighted))

    formal_rate = _rate(record, "formal_B1_rate")
    adjudicated_rate = _rate(record, "adjudicated_B1_rate")
    if formal_rate is not None and axis_rate is not None and not _close(formal_rate, axis_rate):
        issues.append(_issue("B1_FORMAL_RATE_MISMATCH", "BLOCKER", "formal_B1_rate与axes.B1.score_rate不一致，存在override或旧账覆盖。", formal=formal_rate, axis=axis_rate))
    if adjudicated_rate is not None and axis_rate is not None and not _close(adjudicated_rate, axis_rate):
        issues.append(_issue("B1_ADJUDICATED_RATE_MISMATCH", "BLOCKER", "adjudicated_B1_rate与axes.B1.score_rate不一致，当前B80正在消费另一套B1。", adjudicated=adjudicated_rate, axis=axis_rate))

    blocker_count = sum(issue.severity == "BLOCKER" for issue in issues)
    warn_count = sum(issue.severity == "WARN" for issue in issues)
    return {
        "ruler_id": record.get("ruler_id"),
        "ruler_name": record.get("ruler_name"),
        "polity": record.get("polity"),
        "reign_range": record.get("reign_range"),
        "shard": record.get("_audit_shard"),
        "machine_consistency_status": "BLOCKED" if blocker_count else ("WARN" if warn_count else "PASS"),
        "b1_reaudit_required": True,
        "blocker_count": blocker_count,
        "warn_count": warn_count,
        "current_b1": {
            "grade": grade or None,
            "score_rate": axis_rate,
            "formal_score_rate": formal_rate,
            "adjudicated_score_rate": adjudicated_rate,
            "start": stored_start,
            "end": stored_end,
            "weighted_value": stored_weighted,
        },
        "issues": [issue.as_dict() for issue in issues],
    }


def build_b1_audit(workspace_root: Path) -> dict[str, Any]:
    anchor_payload = _load(workspace_root / ANCHOR_PATH)
    records = _load_all_records(workspace_root)
    audited = [audit_record(row, anchor_payload) for row in records]

    code_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    polity_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in audited:
        polity = str(row.get("polity") or "UNKNOWN")
        polity_counts[polity][str(row["machine_consistency_status"])] += 1
        for issue in row["issues"]:
            code_counts[str(issue["code"])] += 1
            severity_counts[str(issue["severity"])] += 1

    blocked = sum(row["machine_consistency_status"] == "BLOCKED" for row in audited)
    warned = sum(row["machine_consistency_status"] == "WARN" for row in audited)
    passed = sum(row["machine_consistency_status"] == "PASS" for row in audited)
    return {
        "schema_id": "third-item-b1-machine-consistency-audit-v1",
        "canonical_status": "AUDIT_ONLY_DOES_NOT_MODIFY_SETTLEMENT",
        "scope": "第三项B1现有201人分片机械一致性扫描；所有人物仍需按统一空间锚进行语义重审。",
        "source_router": str(AB_ROUTER_PATH),
        "anchor_registry": str(ANCHOR_PATH),
        "record_count": len(audited),
        "summary": {
            "blocked_count": blocked,
            "warn_count": warned,
            "machine_pass_count": passed,
            "reaudit_required_count": len(audited),
            "issue_count_by_severity": dict(sorted(severity_counts.items())),
            "issue_count_by_code": dict(sorted(code_counts.items())),
            "status_by_polity": {key: dict(sorted(value.items())) for key, value in sorted(polity_counts.items())},
        },
        "records": audited,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# B1机械一致性审计",
        "",
        "> 本报告只检查现有B1底账是否能从统一空间锚和机械公式自洽推出，不替代史料语义重审，也不直接改写任何人物分数。",
        "",
        f"- 记录数：{payload['record_count']}",
        f"- BLOCKED：{summary['blocked_count']}",
        f"- WARN：{summary['warn_count']}",
        f"- 机械PASS：{summary['machine_pass_count']}",
        f"- 仍需语义重审：{summary['reaudit_required_count']}（全员）",
        "",
        "## 异常码统计",
        "",
        "| 异常码 | 数量 |",
        "|---|---:|",
    ]
    for code, count in summary["issue_count_by_code"].items():
        lines.append(f"| `{code}` | {count} |")

    lines += ["", "## 按人物", "", "| 人物 | 政权 | 状态 | Blocker | Warn | 主要异常 |", "|---|---|---|---:|---:|---|"]
    for row in payload["records"]:
        issues = row["issues"]
        codes = "、".join(str(issue["code"]) for issue in issues[:6])
        if len(issues) > 6:
            codes += f" 等{len(issues)}项"
        lines.append(
            f"| {row['ruler_name']} | {row['polity']} | {row['machine_consistency_status']} | "
            f"{row['blocker_count']} | {row['warn_count']} | {codes or '—'} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_b1_audit(workspace_root: Path) -> dict[str, Any]:
    payload = build_b1_audit(workspace_root)
    json_path = workspace_root / AUDIT_JSON_PATH
    md_path = workspace_root / AUDIT_MD_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="扫描第三项B1分片机械一致性")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--write", action="store_true", help="写出正式审计JSON/Markdown")
    args = parser.parse_args(argv)
    root = Path(args.workspace_root).resolve()
    payload = write_b1_audit(root) if args.write else build_b1_audit(root)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 1 if payload["summary"]["blocked_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
