from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_pending_material_worklist import ACTION_OPTIONS  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.rule_material_policy import RuleMaterialPolicyMap, fetch_policy_map_from_dsn  # noqa: E402


DEFAULT_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_pending_factor_patch_report.json"


class PendingFactorPatchError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PendingFactorPatchError(f"{path}: expected JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PendingFactorPatchError(f"{path}:{line_no}: expected JSON object")
        value["_line_no"] = line_no
        rows.append(value)
    return rows


def flatten_batch_materials(batch: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    materials: dict[int, dict[str, Any]] = {}
    groups = batch.get("groups") if isinstance(batch.get("groups"), list) else []
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        for row in group.get("materials", []) if isinstance(group.get("materials"), list) else []:
            if not isinstance(row, Mapping):
                continue
            obj_src_id = int(row.get("obj_src_id") or 0)
            if obj_src_id:
                materials[obj_src_id] = dict(row)
    return materials


def candidate_labels(material: Mapping[str, Any], factor_name: str) -> set[str]:
    template = material.get("factor_patch_template")
    if not isinstance(template, Mapping):
        return set()
    candidates = template.get("factor_option_candidates")
    if not isinstance(candidates, Mapping):
        return set()
    rows = candidates.get(factor_name)
    if not isinstance(rows, list):
        return set()
    return {str(row.get("label") or "") for row in rows if isinstance(row, Mapping) and row.get("label")}


def expected_factor_keys(material: Mapping[str, Any]) -> list[str]:
    template = material.get("factor_patch_template")
    if not isinstance(template, Mapping):
        return []
    keys = template.get("factor_keys")
    if not isinstance(keys, list):
        return []
    return [str(key) for key in keys]


def _text(value: object) -> str:
    return str(value or "").strip()


def _policy_set(policies: RuleMaterialPolicyMap | None, rule_code: str, key: str) -> set[str]:
    policy = (policies or {}).get(rule_code)
    if policy is None:
        return set()
    return {str(value) for value in getattr(policy, key)}


def validate_patch_row(
    row: Mapping[str, Any],
    material: Mapping[str, Any],
    *,
    policies: RuleMaterialPolicyMap | None = None,
) -> list[dict[str, object]]:
    obj_src_id = int(row.get("obj_src_id") or 0)
    base = {
        "obj_src_id": obj_src_id,
        "emperor": material.get("emperor"),
        "rule_code": material.get("rule_code"),
        "obj_name": material.get("obj_name"),
        "line_no": row.get("_line_no"),
    }
    issues: list[dict[str, object]] = []
    action = _text(row.get("target_action"))
    if action not in ACTION_OPTIONS:
        issues.append({**base, "severity": "error", "status": "invalid_target_action", "value": action})
        return issues
    if action in {"supporting_only", "exclude"}:
        if not _text(row.get("patch_note")):
            issues.append({**base, "severity": "error", "status": "missing_patch_note", "value": action})
        return issues

    obj_type = _text(material.get("obj_type") or material.get("type"))
    rule_code = _text(material.get("rule_code"))
    if policies is not None and rule_code and rule_code not in policies:
        issues.append({**base, "severity": "error", "status": "missing_rule_material_policy", "rule_code": rule_code})
    if obj_type in _policy_set(policies, rule_code, "disallowed_scored_obj_types"):
        issues.append({**base, "severity": "error", "status": "scored_obj_type_disallowed", "obj_type": obj_type})
    elif obj_type in _policy_set(policies, rule_code, "discouraged_scored_obj_types"):
        issues.append({**base, "severity": "warning", "status": "scored_obj_type_discouraged", "obj_type": obj_type})

    side = _text(row.get("side"))
    if side not in {"positive", "negative"}:
        issues.append({**base, "severity": "error", "status": "invalid_side", "value": side})
    expected_keys = expected_factor_keys(material)
    if not expected_keys:
        issues.append({**base, "severity": "error", "status": "score_without_factor_template"})
        return issues
    factor_refs = row.get("factor_refs")
    if not isinstance(factor_refs, Mapping):
        issues.append({**base, "severity": "error", "status": "missing_factor_refs"})
        return issues
    for factor_name in expected_keys:
        ref = factor_refs.get(factor_name)
        if not isinstance(ref, Mapping):
            issues.append({**base, "severity": "error", "status": "missing_factor_ref", "factor": factor_name})
            continue
        label = _text(ref.get("label"))
        if not label:
            issues.append({**base, "severity": "error", "status": "missing_factor_label", "factor": factor_name})
            continue
        labels = candidate_labels(material, factor_name)
        if labels and label not in labels:
            issues.append(
                {
                    **base,
                    "severity": "error",
                    "status": "unknown_factor_label",
                    "factor": factor_name,
                    "label": label,
                }
            )
    return issues


def build_patch_template_rows(batch: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for material in flatten_batch_materials(batch).values():
        template = material.get("factor_patch_template") if isinstance(material.get("factor_patch_template"), Mapping) else {}
        rows.append(
            {
                "obj_src_id": material["obj_src_id"],
                "target_action": "review",
                "side": template.get("side") or material.get("direction") or "",
                "factor_refs": template.get("factor_refs") or {},
                "patch_note": "",
            }
        )
    return rows


def build_report(
    batch: Mapping[str, Any],
    patch_rows: Sequence[Mapping[str, Any]],
    *,
    policies: RuleMaterialPolicyMap | None = None,
) -> dict[str, object]:
    materials = flatten_batch_materials(batch)
    issues: list[dict[str, object]] = []
    seen: dict[int, int] = {}
    for row in patch_rows:
        obj_src_id = int(row.get("obj_src_id") or 0)
        if not obj_src_id:
            issues.append({"severity": "error", "status": "missing_obj_src_id", "line_no": row.get("_line_no")})
            continue
        if obj_src_id in seen:
            issues.append(
                {
                    "severity": "error",
                    "status": "duplicate_patch_row",
                    "obj_src_id": obj_src_id,
                    "line_no": row.get("_line_no"),
                    "first_line_no": seen[obj_src_id],
                }
            )
            continue
        seen[obj_src_id] = int(row.get("_line_no") or 0)
        material = materials.get(obj_src_id)
        if material is None:
            issues.append(
                {
                    "severity": "error",
                    "status": "unknown_obj_src_id",
                    "obj_src_id": obj_src_id,
                    "line_no": row.get("_line_no"),
                }
            )
            continue
        issues.extend(validate_patch_row(row, material, policies=policies))
    for obj_src_id, material in materials.items():
        if obj_src_id not in seen:
            issues.append(
                {
                    "severity": "error",
                    "status": "missing_patch_row",
                    "obj_src_id": obj_src_id,
                    "emperor": material.get("emperor"),
                    "rule_code": material.get("rule_code"),
                    "obj_name": material.get("obj_name"),
                }
            )
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    action_counts: dict[str, int] = {}
    for row in patch_rows:
        action = _text(row.get("target_action"))
        if action:
            action_counts[action] = action_counts.get(action, 0) + 1
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": error_count == 0,
        "batch_id": batch.get("batch_id") or "",
        "expected_materials": len(materials),
        "patch_rows": len(patch_rows),
        "error_count": error_count,
        "warning_count": warning_count,
        "action_counts": dict(sorted(action_counts.items())),
        "issues": issues,
    }


def render_markdown(report: Mapping[str, object]) -> str:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    lines = [
        "# I5B Pending Factor Patch Validation",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- batch_id: `{report.get('batch_id') or ''}`",
        f"- ok: `{str(bool(report.get('ok'))).lower()}`",
        f"- expected_materials: `{report.get('expected_materials') or 0}`",
        f"- patch_rows: `{report.get('patch_rows') or 0}`",
        f"- errors: `{report.get('error_count') or 0}`",
        "",
        "## Issues",
        "",
    ]
    if not issues:
        lines.append("- 无")
    else:
        lines.extend(["| status | obj_src_id | material | detail |", "| --- | ---: | --- | --- |"])
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            material = f"{issue.get('emperor') or ''}/{issue.get('rule_code') or ''}/{issue.get('obj_name') or ''}"
            detail = issue.get("factor") or issue.get("value") or issue.get("label") or ""
            lines.append(f"| `{issue.get('status') or ''}` | {issue.get('obj_src_id') or ''} | {material} | {detail} |")
    return "\n".join(lines) + "\n"


def write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def write_output(path: Path | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate I5B pending-material factor patch JSONL against a worklist batch.")
    parser.add_argument("--batch", type=Path, required=True, help="pending_material_batch_XX.json from i5b_pending_material_worklist.py.")
    parser.add_argument("--patch", type=Path, help="JSONL patch filled by Codex subagent.")
    parser.add_argument("--template-output", type=Path, help="Write blank JSONL patch template for this batch.")
    parser.add_argument("--item-code", default="I5B")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-issue", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    batch = read_json(args.batch)
    if args.template_output:
        write_jsonl(args.template_output, build_patch_template_rows(batch))
    if not args.patch:
        print(json.dumps({"template_output": str(args.template_output) if args.template_output else None}, ensure_ascii=False, sort_keys=True))
        return 0
    policies = fetch_policy_map_from_dsn(
        dsn=args.dsn or resolve_dsn(args.dsn_env),
        item_code=args.item_code,
        rule_codes=tuple(sorted({_text(material.get("rule_code")) for material in flatten_batch_materials(batch).values()})),
    )
    report = build_report(batch, read_jsonl(args.patch), policies=policies)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    write_output(args.output, text)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "output": str(args.output) if args.output else None,
                "error_count": report["error_count"],
                "warning_count": report["warning_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.fail_on_issue and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
