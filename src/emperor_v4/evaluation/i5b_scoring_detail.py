from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "i5b-scoring-detail-report-v1"
MANIFEST_SCHEMA_VERSION = "i5b-scoring-detail-manifest-v1"
CATALOG_SCHEMA_VERSION = "i5b-scoring-detail-catalog-v1"
SELECTION_SCHEMA_VERSION = "i5b-scoring-detail-selection-v1"
SELECTION_REPORT_SCHEMA_VERSION = "i5b-scoring-detail-selection-report-v1"
DISPLAY_SCHEMA_VERSION = "i5b-scoring-detail-display-v1"
RULE_ORDER = (
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
RULE_LABELS = {
    "talent_discovery": "人才发现",
    "appointment_delegation": "任用授权",
    "team_building": "团队建设",
    "tolerate_talent": "容才",
    "anti_nepotism": "反任人唯亲",
}
ADAPTERS = {
    "joint_projection_report",
    "appointment_parity_report",
    "appointment_expanded_shadow",
    "team_scored_shadow_report",
    "team_roster_shadow",
    "team_historical_scored_shadow",
    "rule_lane_shadow",
    "source_rebind_record",
    "source_rebind_batch",
}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _rounded(value: object) -> str:
    return str(_decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def _source_detail(
    *, adapter: str, rule_code: str, ruler: str, payload: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str] | None]:
    if adapter == "joint_projection_report":
        if payload.get("rule_code") != rule_code:
            raise ValueError(f"{rule_code} joint projection source rule mismatch")
        contributions = [
            row
            for row in _rows(payload.get("score_contributions") or (), "score contributions")
            if row.get("ruler") == ruler
        ]
        contribution = contributions[0] if contributions else None
        detail = {
            "materials": [
                row for row in payload.get("materials") or () if row.get("ruler") == ruler
            ],
            "insufficient_projections": [
                row
                for row in payload.get("insufficient_projections") or ()
                if row.get("ruler") == ruler
            ],
            "object_side_aggregates": [
                row
                for row in payload.get("object_side_aggregates") or ()
                if row.get("ruler") == ruler
            ],
            "score_contribution": contribution,
        }
        signals = None if contribution is None else {
            "positive_signal": str(contribution["positive_signal"]),
            "negative_signal": str(contribution["negative_signal"]),
            "rule_raw_net": str(contribution["rule_raw_net"]),
        }
        return detail, signals

    if adapter == "appointment_parity_report":
        aggregates = [
            row for row in payload.get("ruler_aggregates") or () if row.get("ruler") == ruler
        ]
        aggregate = aggregates[0] if aggregates else None
        detail = {
            "ruler_aggregate": aggregate,
            "judgments": [
                row for row in payload.get("judgments") or () if row.get("ruler") == ruler
            ],
        }
        signals = None if aggregate is None else {
            "positive_signal": str(aggregate["positive_signal"]),
            "negative_signal": str(aggregate["negative_signal"]),
            "rule_raw_net": str(aggregate["rule_raw_net"]),
        }
        return detail, signals

    if adapter == "appointment_expanded_shadow":
        if payload.get("ruler") != ruler:
            raise ValueError("appointment expanded shadow ruler mismatch")
        detail = {
            "aggregation_policy": payload.get("aggregation_policy"),
            "positive_lane_scale": payload.get("positive_lane_scale"),
            "object_decay": payload.get("object_decay"),
            "materials": list(payload.get("materials") or ()),
            "excluded_net_additions": list(payload.get("excluded_net_additions") or ()),
        }
        return detail, {
            "positive_signal": str(payload["positive_signal"]),
            "negative_signal": str(payload["negative_signal"]),
            "rule_raw_net": str(payload["rule_raw_net"]),
        }

    if adapter == "team_scored_shadow_report":
        if payload.get("rule_code") != rule_code:
            raise ValueError("team scored shadow source rule mismatch")
        windows = [row for row in payload.get("windows") or () if row.get("ruler") == ruler]
        return {"windows": windows}, None

    if adapter == "team_roster_shadow":
        if payload.get("ruler") != ruler:
            raise ValueError("team roster shadow ruler mismatch")
        calculation = payload.get("calculation") or {}
        detail = {
            "window": payload.get("window"),
            "members": list(payload.get("members") or ()),
            "blocked_or_excluded": list(payload.get("blocked_or_excluded") or ()),
            "not_yet_disposed_named_gaps": list(
                payload.get("not_yet_disposed_named_gaps") or ()
            ),
            "factors": dict(payload.get("factors") or {}),
            "calculation": dict(calculation),
        }
        return detail, {
            "positive_signal": str(calculation["positive_signal"]),
            "negative_signal": str(calculation["negative_signal"]),
            "rule_raw_net": str(calculation["rule_raw_net"]),
        }

    if adapter == "team_historical_scored_shadow":
        if payload.get("rule_code") != rule_code or payload.get("ruler") != ruler:
            raise ValueError("team historical shadow source identity mismatch")
        raw = payload.get("raw_signal") or {}
        detail = {
            "window": payload.get("window"),
            "members": [
                {
                    **dict(row),
                    "grade": row.get("accepted_talent_grade"),
                    "origin": "formally_accepted_historical",
                    "roles": list(row.get("role_families") or ()),
                    "window_negative_class": row.get("negative_talent_class"),
                    "window_negative_severity": row.get("negative_talent_severity"),
                }
                for row in payload.get("members") or ()
            ],
            "factors": dict(payload.get("factors") or {}),
            "factor_diagnostics": dict(payload.get("factor_diagnostics") or {}),
            "score_contribution": dict(payload.get("score_contribution") or {}),
            "assertion_episode_reu_trace": dict(
                payload.get("assertion_episode_reu_trace") or {}
            ),
        }
        return detail, {
            "positive_signal": str(raw["positive_signal"]),
            "negative_signal": str(raw["negative_signal"]),
            "rule_raw_net": str(raw["rule_raw_net"]),
        }

    if adapter == "rule_lane_shadow":
        if payload.get("ruler") != ruler:
            raise ValueError("rule lane shadow ruler mismatch")
        lane = payload.get(rule_code) or {}
        current = lane.get("strict_current") or {}
        if not current:
            raise ValueError(f"{rule_code} lane shadow lacks strict_current")
        return dict(lane), {
            "positive_signal": str(current["positive_signal"]),
            "negative_signal": str(current["negative_signal"]),
            "rule_raw_net": str(current["rule_raw_net"]),
        }

    if adapter == "source_rebind_record":
        return {
            "subject": payload.get("subject"),
            "observations": list(payload.get("observations") or ()),
            "factor_projection": dict(payload.get("factor_projection") or {}),
            "projection_decision": dict(payload.get("projection_decision") or {}),
        }, None

    if adapter == "source_rebind_batch":
        return {
            "candidate_inventory": dict(payload.get("candidate_inventory") or {}),
            "projection_units": list(payload.get("projection_units") or ()),
            "unresolved_priority_people": list(
                payload.get("unresolved_priority_people") or ()
            ),
        }, None

    raise ValueError(f"unsupported scoring detail adapter: {adapter}")


def build_i5b_scoring_detail(
    *,
    manifest: Mapping[str, Any],
    rule_net: Mapping[str, Any],
    scoring_policy: Mapping[str, Any],
    display_catalog: Mapping[str, Any],
    detail_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("scoring detail manifest schema mismatch")
    if rule_net.get("schema_version") != "i5b-ruler-rule-net-report-v1":
        raise ValueError("scoring detail requires a ruler rule net report")
    if scoring_policy.get("schema_version") != "i5b-scoring-policy-v1":
        raise ValueError("scoring detail scoring policy mismatch")
    if display_catalog.get("schema_version") != DISPLAY_SCHEMA_VERSION:
        raise ValueError("scoring detail display catalog mismatch")
    ruler = str(rule_net.get("ruler") or "")
    net_rows = {row["rule_code"]: row for row in rule_net.get("rules") or ()}
    if set(net_rows) != set(RULE_ORDER):
        raise ValueError("scoring detail requires exactly five rule net rows")

    configured = _rows(manifest.get("detail_sources") or (), "detail_sources")
    if len(configured) != len(detail_sources):
        raise ValueError("loaded scoring detail sources do not match manifest")
    by_rule: dict[str, list[dict[str, Any]]] = {code: [] for code in RULE_ORDER}
    for spec, loaded in zip(configured, detail_sources, strict=True):
        rule_code = str(spec.get("rule_code") or "")
        adapter = str(spec.get("adapter") or "")
        role = str(spec.get("role") or "")
        if rule_code not in by_rule or adapter not in ADAPTERS:
            raise ValueError("scoring detail source rule or adapter is invalid")
        if role not in {"primary", "supporting"}:
            raise ValueError("scoring detail source role must be primary or supporting")
        payload = loaded.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("scoring detail source payload must be an object")
        detail, signals = _source_detail(
            adapter=adapter, rule_code=rule_code, ruler=ruler, payload=payload
        )
        by_rule[rule_code].append(
            {
                "role": role,
                "adapter": adapter,
                "path": str(spec.get("path") or ""),
                "schema_version": payload.get("schema_version"),
                "status": payload.get("status"),
                "source_sha256": _hash(payload),
                "signals": signals,
                "detail": detail,
            }
        )

    rules: list[dict[str, Any]] = []
    for rule_code in RULE_ORDER:
        sources = by_rule[rule_code]
        primary = [source for source in sources if source["role"] == "primary"]
        if len(primary) != 1 or primary[0]["signals"] is None:
            raise ValueError(f"{rule_code} requires exactly one signal-bearing primary source")
        net = net_rows[rule_code]
        comparisons = {
            key: _rounded(primary[0]["signals"][key]) == _rounded(net[key])
            for key in ("positive_signal", "negative_signal", "rule_raw_net")
        }
        if not all(comparisons.values()):
            raise ValueError(f"{rule_code} primary detail does not reconcile to rule net")
        policy = scoring_policy["rules"][rule_code]
        translated_factors = _translate_factor_catalog(
            rule_code=rule_code,
            factor_catalog={
                key: value
                for key, value in policy.items()
                if isinstance(value, Mapping)
                and key not in {"formulas", "factor_roles"}
            },
            display_catalog=display_catalog,
        )
        rules.append(
            {
                "rule_code": rule_code,
                "rule_label": RULE_LABELS[rule_code],
                "calculation_status": net["calculation_status"],
                "historical_coverage_status": net["historical_coverage_status"],
                "positive_signal": net["positive_signal"],
                "negative_signal": net["negative_signal"],
                "rule_raw_net": net["rule_raw_net"],
                "rule_weight": net["rule_weight"],
                "weighted_raw_contribution": net["weighted_raw_contribution"],
                "formula": policy.get("formula") or policy.get("formulas") or {
                    "positive": policy.get("positive_formula"),
                    "negative": policy.get("negative_formula"),
                },
                "projection_mode": policy.get("projection_mode"),
                "aggregation_policy": policy.get("aggregation_policy"),
                "factor_catalog": {
                    key: value
                    for key, value in policy.items()
                    if isinstance(value, Mapping)
                    and key not in {"formulas", "factor_roles"}
                },
                "factor_catalog_zh": translated_factors,
                "limitations": list(net.get("limitations") or ()),
                "sensitivity_scenarios": list(net.get("sensitivity_scenarios") or ()),
                "source_refs": list(net.get("source_refs") or ()),
                "material_refs": list(net.get("material_refs") or ()),
                "detail_reconciliation": {
                    "status": "reconciled",
                    "primary_adapter": primary[0]["adapter"],
                    "checks": comparisons,
                },
                "detail_sources": sources,
            }
        )

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "report_only_scoring_detail_export",
        "ruler": ruler,
        "ruler_ref": rule_net.get("ruler_ref"),
        "input_version": rule_net.get("input_version"),
        "summary": dict(rule_net.get("summary") or {}),
        "rules": rules,
        "evidence_factor_policy": dict(scoring_policy.get("evidence_factor") or {}),
        "evidence_factor_catalog_zh": _translate_factor_catalog(
            rule_code=None,
            factor_catalog={
                key: value
                for key, value in (scoring_policy.get("evidence_factor") or {}).items()
                if isinstance(value, Mapping) and key != "v4_ownership"
            },
            display_catalog=display_catalog,
        ),
        "declarations": {
            "all_primary_details_reconciled": True,
            "historical_coverage_complete": all(
                row["historical_coverage_status"] == "coverage_complete" for row in rules
            ),
            "formal_45_point_score": None,
            "tier": None,
            "ranking": None,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def _translate_factor_catalog(
    *,
    rule_code: str | None,
    factor_catalog: Mapping[str, Mapping[str, Any]],
    display_catalog: Mapping[str, Any],
) -> list[dict[str, Any]]:
    translations: dict[str, Any] = dict(display_catalog.get("common_factors") or {})
    if rule_code is not None:
        translations.update(
            ((display_catalog.get("rules") or {}).get(rule_code) or {}).get("factors")
            or {}
        )
    translated: list[dict[str, Any]] = []
    for factor_code, values in factor_catalog.items():
        factor_display = translations.get(factor_code)
        if not isinstance(factor_display, Mapping):
            raise ValueError(f"missing Chinese factor translation: {factor_code}")
        option_display = factor_display.get("options") or {}
        options = []
        for option_code, value in values.items():
            display = option_display.get(option_code)
            if not isinstance(display, Mapping):
                raise ValueError(
                    f"missing Chinese option translation: {factor_code}.{option_code}"
                )
            options.append(
                {
                    "option_code": option_code,
                    "label_zh": str(display.get("label_zh") or ""),
                    "description_zh": str(display.get("description_zh") or ""),
                    "value": value,
                    **{
                        key: item
                        for key, item in display.items()
                        if key not in {"label_zh", "description_zh"}
                    },
                }
            )
        translated.append(
            {
                "factor_code": factor_code,
                "label_zh": str(factor_display.get("label_zh") or ""),
                "description_zh": str(factor_display.get("description_zh") or ""),
                "options": options,
            }
        )
    return translated


def _text(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return "、".join(str(item) for item in value)
    if isinstance(value, Mapping):
        return "；".join(
            f"{key}={_text(value[key])}" for key in sorted(value, key=str)
        )
    return str(value)


def _choice_text(
    material: Mapping[str, Any],
    factor_catalog_zh: Sequence[Mapping[str, Any]],
    evidence_factor_catalog_zh: Sequence[Mapping[str, Any]],
) -> str:
    projection = material.get("numeric_projection") or {}
    values = (
        projection.get("deterministic_dimension_values")
        or projection.get("dimension_values")
        or {}
    )
    choices = (
        projection.get("factor_option_codes")
        or projection.get("choices")
        or material.get("choices")
        or {}
    )
    if isinstance(choices, Mapping):
        option_lookup = {
            (factor["factor_code"], option["option_code"]): option
            for factor in (*factor_catalog_zh, *evidence_factor_catalog_zh)
            for option in factor["options"]
        }
        return "；".join(
            f"{option_lookup.get((key, choice), {}).get('label_zh', choice)}"
            f"[{key}={choice}]"
            + (f"({values[key]})" if key in values else "")
            for key, choice in choices.items()
        )
    return ""


def _option_status_suffix(option: Mapping[str, Any]) -> str:
    parts = []
    if option.get("current_projection_status_zh"):
        parts.append(f"当前投影状态={option['current_projection_status_zh']}")
    if option.get("contract_reachability_zh"):
        parts.append(f"合同可达性={option['contract_reachability_zh']}")
    return f"（{'；'.join(parts)}）" if parts else ""


def render_i5b_scoring_detail_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# {_text(report['ruler'])}当前计分详情",
        "",
        "> 本报告仅展示当前声明工作集的 shadow raw signal，不是45分、档位或排名。",
        "",
        "## 汇总",
        "",
        "| Rule | 正向 | 负向 | 净值 | 权重 | 加权贡献 | 历史覆盖 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rules"]:
        lines.append(
            f"| {row['rule_label']} (`{row['rule_code']}`) | {row['positive_signal']} | "
            f"{row['negative_signal']} | {row['rule_raw_net']} | {row['rule_weight']} | "
            f"{row['weighted_raw_contribution']} | `{row['historical_coverage_status']}` |"
        )
    lines += [
        "",
        f"- 当前 declared-workset weighted raw signal：`{summary['declared_workset_weighted_raw_signal']}`",
        f"- 历史覆盖完成：`{summary['historical_coverage_complete_rule_count']}/5`",
        "- 正式45分、tier、排名：均未生成",
        "",
        "### 通用证据因子",
        "",
        f"- 公式：`{_text(report['evidence_factor_policy'].get('formula'))}`",
        f"- 取值范围：`{_text(report['evidence_factor_policy'].get('minimum'))}` 至 "
        f"`{_text(report['evidence_factor_policy'].get('maximum'))}`",
    ]

    for row in report["rules"]:
        primary = next(source for source in row["detail_sources"] if source["role"] == "primary")
        detail = primary["detail"]
        lines += [
            "",
            f"## {row['rule_label']} (`{row['rule_code']}`)",
            "",
            f"- 当前净值：`{row['positive_signal']} - {row['negative_signal']} = {row['rule_raw_net']}`",
            f"- 加权贡献：`{row['rule_raw_net']} × {row['rule_weight']} = {row['weighted_raw_contribution']}`",
            f"- 投影模式：`{_text(row['projection_mode'])}`",
            f"- 聚合策略：`{_text(row['aggregation_policy'])}`",
            f"- 公式：`{_text(row['formula'])}`",
            f"- 明细对账：`{row['detail_reconciliation']['status']}`（`{primary['adapter']}`）",
        ]

        if row["factor_catalog_zh"]:
            lines += ["", "### 因子档位", ""]
            for factor in row["factor_catalog_zh"]:
                lines.append(
                    f"- **{factor['label_zh']}** (`{factor['factor_code']}`)："
                    f"{factor['description_zh']}"
                )
                for option in factor["options"]:
                    lines.append(
                        f"  - **{option['label_zh']}** (`{option['option_code']}`) = "
                        f"`{option['value']}`：{option['description_zh']}"
                        f"{_option_status_suffix(option)}"
                    )

        materials = detail.get("materials") or ()
        if materials:
            lines += [
                "",
                "### 计入材料",
                "",
                "| 对象 | 单元/材料 | 方向 | 材料分 | 排名权重/加权值 | 因子选择 |",
                "|---|---|---|---:|---|---|",
            ]
            for material in materials:
                subject = material.get("person") or material.get("subject") or "—"
                unit = material.get("unit_ref") or material.get("material_code") or "—"
                score = material.get("material_score") or material.get("absolute_material_score")
                weighted = material.get("weighted_signal") or material.get("weighted_value") or "—"
                weight = material.get("object_weight") or material.get("weight") or "—"
                lines.append(
                    f"| {_text(subject)} | `{_text(unit)}` | {_text(material.get('side'))} | "
                    f"{_text(score)} | {_text(weight)} / {_text(weighted)} | "
                    f"{_choice_text(material, row['factor_catalog_zh'], report['evidence_factor_catalog_zh'])} |"
                )

        members = detail.get("members") or ()
        if members:
            lines += [
                "",
                "### 团队成员池",
                "",
                "| 人物 | 人才档 | 来源 | 角色 | 窗口负向 |",
                "|---|---|---|---|---|",
            ]
            for member in members:
                negative = member.get("window_negative_class") or "—"
                if member.get("window_negative_severity"):
                    negative += f"/{member['window_negative_severity']}"
                lines.append(
                    f"| {member['person']} | `{member['grade']}` | `{member['origin']}` | "
                    f"{_text(member.get('roles'))} | {_text(negative)} |"
                )

        for label, key in (
            ("排除或净增为零", "excluded_net_additions"),
            ("阻断或排除候选", "blocked_or_excluded"),
            ("尚未逐项处置人物", "not_yet_disposed_named_gaps"),
            ("证据不足投影", "insufficient_projections"),
            ("独立回源观察", "observations"),
        ):
            values = detail.get(key) or ()
            if values:
                lines += ["", f"### {label}", ""]
                for value in values:
                    lines.append(f"- {_text(value)}")

        if detail.get("factors"):
            lines += ["", "### 当前结构因子", ""]
            lines.extend(f"- `{key}`：`{value}`" for key, value in detail["factors"].items())
        if detail.get("calculation"):
            lines += ["", "### 计算展开", ""]
            lines.extend(
                f"- `{key}`：`{_text(value)}`" for key, value in detail["calculation"].items()
            )
        if detail.get("strict_current"):
            current = detail["strict_current"]
            if current.get("factor_choice"):
                lines += ["", "### 当前因子选择", ""]
                lines.extend(
                    f"- `{key}`：`{value}`" for key, value in current["factor_choice"].items()
                )
            if current.get("rejection_reason"):
                lines += ["", f"- 当前拒绝原因：{current['rejection_reason']}"]
        if detail.get("sensitivity"):
            lines += ["", f"- 条件敏感性（不计入当前净值）：`{_text(detail['sensitivity'])}`"]

        if row["limitations"]:
            lines += ["", "### 限制", ""]
            lines.extend(f"- {value}" for value in row["limitations"])
        lines += ["", "### Lineage", ""]
        lines.extend(f"- `{value}`" for value in row["source_refs"])
        supporting = [source for source in row["detail_sources"] if source["role"] == "supporting"]
        if supporting:
            lines += ["", "补充明细源："]
            lines.extend(
                f"- `{source['adapter']}`：`{source['path']}`" for source in supporting
            )
            observations = [
                observation
                for source in supporting
                for observation in source["detail"].get("observations") or ()
            ]
            if observations:
                lines += ["", "补充回源观察："]
                lines.extend(
                    f"- `{observation.get('time_context')}`："
                    f"{observation.get('v4_frozen_observation')}"
                    for observation in observations
                )

    lines += [
        "",
        "## 安全声明",
        "",
        "- 本次导出模型调用：0",
        "- 本次导出数据库写入：0",
        "- 未执行动态映射，未生成正式评分或排名",
        "",
    ]
    return "\n".join(lines)


def _person_matches(candidate: object, person: str) -> bool:
    text = str(candidate or "")
    return text == person or text == f"{person}身后信用"


def _person_participations(
    report: Mapping[str, Any], person: str, selected_rules: set[str]
) -> list[dict[str, Any]]:
    participations: list[dict[str, Any]] = []
    for rule in report["rules"]:
        rule_code = rule["rule_code"]
        if rule_code not in selected_rules:
            continue
        for source in rule["detail_sources"]:
            detail = source["detail"]
            role = source["role"]

            def add(kind: str, item: object) -> None:
                participations.append(
                    {
                        "ruler": report["ruler"],
                        "rule_code": rule_code,
                        "rule_label": rule["rule_label"],
                        "source_role": role,
                        "source_adapter": source["adapter"],
                        "source_path": source["path"],
                        "participation_kind": kind,
                        "rule_raw_net": rule["rule_raw_net"],
                        "rule_weight": rule["rule_weight"],
                        "individual_score_claimed": False,
                        "detail": item,
                    }
                )

            for material in detail.get("materials") or ():
                candidate = material.get("person") or material.get("subject")
                if _person_matches(candidate, person):
                    add("counted_material" if role == "primary" else "supporting_material", material)
            for member in detail.get("members") or ():
                if _person_matches(member.get("person"), person):
                    add("team_member", member)
            for excluded in detail.get("excluded_net_additions") or ():
                if _person_matches(excluded.get("person"), person):
                    add("excluded_net_addition", excluded)
            for blocked in detail.get("blocked_or_excluded") or ():
                if _person_matches(blocked.get("person"), person):
                    add("blocked_or_excluded", blocked)
            for gap in detail.get("not_yet_disposed_named_gaps") or ():
                if _person_matches(gap, person):
                    add("not_yet_disposed_named_gap", {"person": gap})
            for insufficient in detail.get("insufficient_projections") or ():
                if _person_matches(insufficient.get("subject"), person):
                    add("insufficient_projection", insufficient)
            for judgment in detail.get("judgments") or ():
                if _person_matches(judgment.get("person"), person):
                    add("supporting_judgment", judgment)
            if _person_matches(detail.get("subject"), person) and detail.get("observations"):
                add(
                    "source_rebind_record",
                    {
                        "subject": detail["subject"],
                        "observations": detail["observations"],
                        "factor_projection": detail.get("factor_projection"),
                    },
                )
            for unit in detail.get("projection_units") or ():
                if _person_matches(unit.get("subject"), person):
                    add("source_rebind_record", unit)
    return participations


def _filtered_ruler_report(
    report: Mapping[str, Any], selected_rules: set[str]
) -> dict[str, Any]:
    filtered = dict(report)
    filtered["rules"] = [
        row for row in report["rules"] if row["rule_code"] in selected_rules
    ]
    selected_weighted = sum(
        (
            _decimal(row["rule_raw_net"]) * _decimal(row["rule_weight"])
            for row in filtered["rules"]
        ),
        Decimal("0"),
    )
    filtered["selection_summary"] = {
        "selected_rule_count": len(filtered["rules"]),
        "selected_rule_weighted_raw_signal": _rounded(selected_weighted),
        "complete_five_rule_signal": len(filtered["rules"]) == len(RULE_ORDER),
    }
    return filtered


def build_i5b_scoring_detail_selection(
    *,
    catalog: Mapping[str, Any],
    selection: Mapping[str, Any],
    ruler_reports: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if catalog.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise ValueError("scoring detail catalog schema mismatch")
    if selection.get("schema_version") != SELECTION_SCHEMA_VERSION:
        raise ValueError("scoring detail selection schema mismatch")
    catalog_rulers = [str(row.get("ruler") or "") for row in catalog.get("entries") or ()]
    if not catalog_rulers or len(set(catalog_rulers)) != len(catalog_rulers):
        raise ValueError("scoring detail catalog rulers must be non-empty and unique")
    if set(catalog_rulers) != set(ruler_reports):
        raise ValueError("loaded ruler reports do not match scoring detail catalog")
    if any(ruler_reports[ruler].get("ruler") != ruler for ruler in catalog_rulers):
        raise ValueError("scoring detail catalog ruler does not match loaded report")

    rulers = [str(value) for value in selection.get("rulers") or ()]
    people = [str(value) for value in selection.get("people") or ()]
    rules = [str(value) for value in selection.get("rules") or RULE_ORDER]
    if len(set(rulers)) != len(rulers) or len(set(people)) != len(people):
        raise ValueError("scoring detail selections must be unique")
    unknown_rulers = [value for value in rulers if value not in ruler_reports]
    unknown_rules = [value for value in rules if value not in RULE_ORDER]
    if unknown_rulers or unknown_rules:
        raise ValueError(
            f"unknown scoring detail selection: rulers={unknown_rulers}, rules={unknown_rules}"
        )
    if not rulers and not people:
        raise ValueError("select at least one ruler or person")
    selected_rules = set(rules)
    person_scope = str(selection.get("person_scope") or "catalog")
    if person_scope not in {"catalog", "selected_rulers"}:
        raise ValueError("person_scope must be catalog or selected_rulers")
    scoped_rulers = catalog_rulers if person_scope == "catalog" else rulers
    if person_scope == "selected_rulers" and people and not rulers:
        raise ValueError("selected_rulers person scope requires ruler selections")

    selected_ruler_reports = [
        _filtered_ruler_report(ruler_reports[ruler], selected_rules) for ruler in rulers
    ]
    person_rows: list[dict[str, Any]] = []
    unmatched_people: list[str] = []
    for person in people:
        participations = [
            participation
            for ruler in scoped_rulers
            for participation in _person_participations(
                ruler_reports[ruler], person, selected_rules
            )
        ]
        if not participations:
            unmatched_people.append(person)
        person_rows.append(
            {
                "person": person,
                "participation_count": len(participations),
                "participations": participations,
                "individual_score": None,
                "individual_score_claimed": False,
            }
        )
    if unmatched_people and bool(selection.get("strict", True)):
        raise ValueError(f"selected people have no matching participation: {unmatched_people}")

    report: dict[str, Any] = {
        "schema_version": SELECTION_REPORT_SCHEMA_VERSION,
        "status": "report_only_selected_scoring_detail_export",
        "selection": {
            "rulers": rulers,
            "people": people,
            "rules": rules,
            "person_scope": person_scope,
            "strict": bool(selection.get("strict", True)),
        },
        "selected_ruler_reports": selected_ruler_reports,
        "people": person_rows,
        "unmatched_people": unmatched_people,
        "declarations": {
            "partial_rule_selection_not_claimed_as_complete_item_score": True,
            "person_participation_not_aggregated_as_person_score": True,
            "formal_45_point_score": None,
            "tier": None,
            "ranking": None,
            "model_call_count": 0,
            "database_write_count": 0,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def render_i5b_scoring_detail_selection_markdown(report: Mapping[str, Any]) -> str:
    selection = report["selection"]
    lines = [
        "# 指定皇帝、臣子与 Rule 的计分详情",
        "",
        f"- 皇帝：{_text(selection['rulers'])}",
        f"- 臣子：{_text(selection['people'])}",
        f"- Rules：{_text(selection['rules'])}",
        f"- 臣子检索范围：`{selection['person_scope']}`",
        "",
        "> Rule 子集只展示加权 raw signal 小计；臣子条目只表示参与，不构成臣子个人分数。",
    ]
    for ruler_report in report["selected_ruler_reports"]:
        selection_summary = ruler_report["selection_summary"]
        lines += [
            "",
            f"## 皇帝：{ruler_report['ruler']}",
            "",
            "| Rule | 正向 | 负向 | 净值 | 权重 | 加权贡献 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for row in ruler_report["rules"]:
            lines.append(
                f"| {row['rule_label']} (`{row['rule_code']}`) | {row['positive_signal']} | "
                f"{row['negative_signal']} | {row['rule_raw_net']} | {row['rule_weight']} | "
                f"{row['weighted_raw_contribution']} |"
            )
        lines += [
            "",
            f"所选 Rule 加权 raw signal 小计：`{selection_summary['selected_rule_weighted_raw_signal']}`",
        ]
        for row in ruler_report["rules"]:
            primary = next(
                source for source in row["detail_sources"] if source["role"] == "primary"
            )
            lines += [
                "",
                f"### {row['rule_label']}明细",
                "",
                f"- 公式：`{_text(row['formula'])}`",
                f"- 对账：`{row['detail_reconciliation']['status']}`",
                f"- Primary：`{primary['path']}`",
            ]
            for factor in row["factor_catalog_zh"]:
                lines.append(
                    f"- **{factor['label_zh']}** (`{factor['factor_code']}`)："
                    f"{factor['description_zh']}"
                )
                lines.extend(
                    f"  - {option['label_zh']} (`{option['option_code']}`) = "
                    f"`{option['value']}`：{option['description_zh']}"
                    + _option_status_suffix(option)
                    for option in factor["options"]
                )
            materials = primary["detail"].get("materials") or ()
            for material in materials:
                subject = material.get("person") or material.get("subject") or "—"
                unit = material.get("unit_ref") or material.get("material_code") or "—"
                lines.append(
                    f"- {_text(subject)} / `{unit}` / 材料分 "
                    f"`{_text(material.get('material_score') or material.get('absolute_material_score'))}` / "
                    f"因子：{_choice_text(material, row['factor_catalog_zh'], ruler_report['evidence_factor_catalog_zh'])}"
                )
            members = primary["detail"].get("members") or ()
            if members:
                lines.append(f"- 团队成员池：{_text([row['person'] for row in members])}")

    for person in report["people"]:
        lines += [
            "",
            f"## 臣子：{person['person']}",
            "",
            f"参与项数量：`{person['participation_count']}`；个人分数：未生成。",
        ]
        for participation in person["participations"]:
            detail = participation["detail"]
            unit = detail.get("unit_ref") or detail.get("material_code") or detail.get("person") or "—"
            score = detail.get("material_score") or detail.get("absolute_material_score")
            lines.append(
                f"- {participation['ruler']} / {participation['rule_label']} / "
                f"`{participation['participation_kind']}` / `{unit}`"
                + (f" / 材料分 `{score}`" if score is not None else "")
            )
    lines += [
        "",
        "## 安全声明",
        "",
        "- 未把 Rule 子集声明为完整第五项分数",
        "- 未把臣子参与项合成为臣子个人分数",
        "- 模型调用和数据库写入均为0",
        "",
    ]
    return "\n".join(lines)
