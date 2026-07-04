from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.rule_material_policy import (  # noqa: E402
    RuleMaterialPolicy,
    RuleMaterialPolicyMap,
    fetch_policy_map_from_dsn,
)


@dataclass(frozen=True)
class PreviewIssue:
    severity: str
    code: str
    rule_code: str
    causal_chain_key: str
    object_name: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _as_text(value: object) -> str:
    return str(value or "").strip()


def _policy_set(policy: RuleMaterialPolicy, key: str) -> set[str]:
    values = getattr(policy, key)
    return {str(value) for value in values}


def _obj_name(obj: Mapping[str, object]) -> str:
    return _as_text(obj.get("name") or obj.get("obj_name") or obj.get("object_name"))


def _obj_type(obj: Mapping[str, object]) -> str:
    return _as_text(obj.get("obj_type") or obj.get("type"))


def _obj_src_id(obj: Mapping[str, object]) -> str:
    value = obj.get("obj_src_id") or obj.get("material_id")
    return "" if value is None else str(value)


def _unit_scored_obj(unit: Mapping[str, object]) -> Mapping[str, object]:
    scored_obj = unit.get("scored_obj")
    return scored_obj if isinstance(scored_obj, Mapping) else {}


def _issue(
    severity: str,
    code: str,
    unit: Mapping[str, object],
    object_name: str,
    message: str,
) -> PreviewIssue:
    return PreviewIssue(
        severity=severity,
        code=code,
        rule_code=_as_text(unit.get("rule_code")),
        causal_chain_key=_as_text(unit.get("causal_chain_key")),
        object_name=object_name,
        message=message,
    )


def _iter_units(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    units = payload.get("units")
    if not isinstance(units, list):
        return []
    return [unit for unit in units if isinstance(unit, Mapping)]


def audit_payload(
    payload: Mapping[str, object],
    *,
    policies: RuleMaterialPolicyMap | None = None,
) -> list[PreviewIssue]:
    issues: list[PreviewIssue] = []
    units = _iter_units(payload)

    if not _as_text(payload.get("emperor")):
        issues.append(
            PreviewIssue("block", "missing_emperor", "", "", "", "payload 缺少 emperor")
        )
    if not units:
        issues.append(
            PreviewIssue("block", "missing_units", "", "", "", "payload 缺少 units")
        )
        return issues

    by_chain: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    by_scored_material: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)

    for unit in units:
        rule_code = _as_text(unit.get("rule_code"))
        chain_key = _as_text(unit.get("causal_chain_key"))
        scoring_role = _as_text(unit.get("scoring_role"))
        direction = _as_text(unit.get("direction"))
        scored_obj = _unit_scored_obj(unit)
        name = _obj_name(scored_obj)
        obj_type = _obj_type(scored_obj)
        material_id = _obj_src_id(scored_obj)

        policy = (policies or {}).get(rule_code)
        if not rule_code:
            issues.append(_issue("block", "missing_rule_code", unit, name, "unit 缺少 rule_code"))
            continue
        if policy is None:
            issues.append(_issue("block", "missing_rule_material_policy", unit, name, "规则材料策略表缺少该 rule 的 active policy"))
            continue

        if not chain_key:
            issues.append(_issue("block", "missing_causal_chain_key", unit, name, "unit 缺少 causal_chain_key"))
        if not name:
            issues.append(_issue("block", "missing_scored_object", unit, "", "unit 缺少 scored_obj.name"))
        if direction not in {"positive", "negative", "neutral", "mixed"}:
            issues.append(_issue("block", "invalid_direction", unit, name, "direction 必须是 positive/negative/neutral/mixed"))

        allowed_roles = _policy_set(policy, "allowed_scoring_roles")
        context_roles = _policy_set(policy, "context_roles")
        disallowed_types = _policy_set(policy, "disallowed_scored_obj_types")
        discouraged_types = _policy_set(policy, "discouraged_scored_obj_types")

        if scoring_role in context_roles:
            issues.append(
                _issue(
                    "block",
                    "context_role_used_as_scoring_role",
                    unit,
                    name,
                    "上下文角色不能作为计分承载角色",
                )
            )
        elif scoring_role not in allowed_roles:
            issues.append(
                _issue(
                    "block",
                    "scoring_role_not_allowed",
                    unit,
                    name,
                    "scoring_role 不在该 rule 的承载角色表内",
                )
            )

        if obj_type in disallowed_types:
            issues.append(
                _issue(
                    "block",
                    "scored_obj_type_disallowed",
                    unit,
                    name,
                    "该对象类型默认不能作为本 rule 的计分承载对象",
                )
            )
        elif obj_type in discouraged_types:
            issues.append(
                _issue(
                    "warning",
                    "scored_obj_type_discouraged",
                    unit,
                    name,
                    "该对象类型通常只作上下文，入分前需要说明没有更合适承载对象",
                )
            )

        if chain_key:
            by_chain[(rule_code, chain_key)].append(unit)
        if material_id:
            by_scored_material[(rule_code, material_id)].append(unit)

    for (rule_code, chain_key), chain_units in sorted(by_chain.items()):
        policy = (policies or {}).get(rule_code)
        if policy is not None and policy.single_scored_per_chain and len(chain_units) > 1:
            object_names = "、".join(_obj_name(_unit_scored_obj(unit)) for unit in chain_units)
            issues.append(
                PreviewIssue(
                    "warning",
                    "multiple_scored_units_in_chain",
                    rule_code,
                    chain_key,
                    object_names,
                    "该 rule 的同一因果链出现多个计分承载单元，需确认不是事件/群体/人物重复入分",
                )
            )

    for (rule_code, material_id), material_units in sorted(by_scored_material.items()):
        if len(material_units) <= 1:
            continue
        chain_keys = sorted({_as_text(unit.get("causal_chain_key")) for unit in material_units})
        issues.append(
            PreviewIssue(
                "block",
                "same_material_scored_multiple_times",
                rule_code,
                "、".join(chain_keys),
                material_id,
                "同一 obj_src_id 在同一 rule 下被多个证据单元计分",
            )
        )

    return issues


def build_preview(
    payload: Mapping[str, object],
    *,
    policies: RuleMaterialPolicyMap | None = None,
) -> dict[str, object]:
    units = _iter_units(payload)
    issues = audit_payload(payload, policies=policies)
    return {
        "emperor": _as_text(payload.get("emperor")),
        "item_code": _as_text(payload.get("item_code") or "I5B"),
        "unit_count": len(units),
        "issue_count": len(issues),
        "has_blocking_issue": any(issue.severity == "block" for issue in issues),
        "units": units,
        "issues": [issue.to_dict() for issue in issues],
    }


def _member_text(member: Mapping[str, object]) -> str:
    role = _as_text(member.get("role") or member.get("member_role"))
    name = _obj_name(member)
    obj_type = _obj_type(member)
    material_id = _obj_src_id(member)
    parts = [part for part in [role, name, obj_type, f"obj_src_id={material_id}" if material_id else ""] if part]
    return " / ".join(parts)


def render_markdown(preview: Mapping[str, object]) -> str:
    lines = [
        "# I5B 规则证据单元预览",
        "",
        f"- 皇帝：{preview.get('emperor') or ''}",
        f"- 子项：{preview.get('item_code') or 'I5B'}",
        f"- 单元数：{preview.get('unit_count')}",
        f"- 问题数：{preview.get('issue_count')}",
        "",
        "## 证据单元",
        "",
        "| rule | chain | direction | scoring_role | scored_obj | members |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    units = preview.get("units") if isinstance(preview.get("units"), list) else []
    for unit in units:
        if not isinstance(unit, Mapping):
            continue
        scored_obj = _unit_scored_obj(unit)
        material_id = _obj_src_id(scored_obj)
        scored_parts = [_obj_name(scored_obj), _obj_type(scored_obj), f"obj_src_id={material_id}" if material_id else ""]
        scored = " / ".join(part for part in scored_parts if part)
        raw_members = unit.get("members") if isinstance(unit.get("members"), list) else []
        members = "<br>".join(
            _member_text(member)
            for member in raw_members
            if isinstance(member, Mapping)
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _as_text(unit.get("rule_code")),
                    _as_text(unit.get("causal_chain_key")),
                    _as_text(unit.get("direction")),
                    _as_text(unit.get("scoring_role")),
                    scored,
                    members,
                ]
            )
            + " |"
        )

    lines.extend(["", "## 审计问题", ""])
    issues = preview.get("issues") if isinstance(preview.get("issues"), list) else []
    if not issues:
        lines.append("无。")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| severity | code | rule | chain | object | message |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for issue in issues:
        if not isinstance(issue, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _as_text(issue.get("severity")),
                    _as_text(issue.get("code")),
                    _as_text(issue.get("rule_code")),
                    _as_text(issue.get("causal_chain_key")),
                    _as_text(issue.get("object_name")),
                    _as_text(issue.get("message")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def load_payload(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("payload root must be an object")
    return payload


def _rule_codes_from_payload(payload: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_as_text(unit.get("rule_code")) for unit in _iter_units(payload) if _as_text(unit.get("rule_code"))))


def write_output(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview rule evidence units in shadow mode.")
    parser.add_argument("--input", required=True, type=Path, help="JSON payload with emperor/item_code/units.")
    parser.add_argument("--output", type=Path, help="Write report to this path instead of stdout.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code for rule material policies.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--fail-on-issue", action="store_true", help="Exit non-zero when any issue is found.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = load_payload(args.input)
    item_code = _as_text(payload.get("item_code")) or args.item_code
    policies = fetch_policy_map_from_dsn(
        dsn=args.dsn or resolve_dsn(args.dsn_env),
        item_code=item_code,
        rule_codes=_rule_codes_from_payload(payload),
    )
    preview = build_preview(payload, policies=policies)
    if args.format == "json":
        text = json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = render_markdown(preview)
    write_output(text, args.output)
    return 1 if args.fail_on_issue and preview["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
