from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_WORK_ROOT = Path("tmp/i5b-hard-merit-work")
DEFAULT_OUTPUT_DIR = Path("tmp/i5b-hard-merit-work/review")

CAREER_TRACKS = {"civil", "military", "mixed", "cultural", "technical", "negative", "unknown"}
HARD_MERIT_TAGS = {
    "military_campaign",
    "institution_law",
    "fiscal_economic",
    "administration",
    "frontier_diplomacy",
    "cultural_civilizational",
    "talent_recommendation",
    "political_stabilization",
}
SCOPE_HINTS = {
    "local",
    "regional",
    "dynasty_core",
    "dynasty_shaping",
    "cross_era",
    "civilizational",
    "unknown",
}
PREDICATE_HINTS = {
    "appointed_to_command",
    "delegated_military_command",
    "delegated_civil_office",
    "won_campaign",
    "implemented_policy",
    "reformed_law",
    "managed_fiscal_policy",
    "stabilized_politics",
    "recommended_talent",
    "frontier_diplomacy",
    "cultural_project",
    "harmed_security",
    "unknown",
}
RELATION_ROLE_HINTS = {
    "scored_candidate",
    "outcome_context",
    "capability_context",
    "cross_item_candidate",
    "supporting_context",
}

I5B_FORMAL_MAPPINGS = {
    ("delegated_military_command", "appointment_delegation"): (
        "delegated_actor",
        "appointed_or_delegated_authority",
        "scored_candidate",
    ),
    ("appointed_to_command", "appointment_delegation"): (
        "delegated_actor",
        "appointed_or_delegated_authority",
        "scored_candidate",
    ),
    ("delegated_civil_office", "appointment_delegation"): (
        "delegated_actor",
        "appointed_or_delegated_authority",
        "scored_candidate",
    ),
    ("recommended_talent", "talent_discovery"): ("recommended_talent", "recommended_talent", "scored_candidate"),
    ("harmed_security", "tolerate_talent"): ("harmed_talent", "harmed_talent", "scored_candidate"),
}


class HardMeritHandoffError(ValueError):
    pass


@dataclass(frozen=True)
class JsonlRow:
    batch: str
    path: Path
    line_no: int
    row: dict[str, Any]


def load_jsonl(path: Path, *, batch: str) -> list[JsonlRow]:
    rows: list[JsonlRow] = []
    if not path.exists():
        return rows
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HardMeritHandoffError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise HardMeritHandoffError(f"{path}:{line_no}: expected JSON object")
        rows.append(JsonlRow(batch=batch, path=path, line_no=line_no, row=row))
    return rows


def load_batches(work_root: Path) -> tuple[list[JsonlRow], list[JsonlRow]]:
    attr_rows: list[JsonlRow] = []
    hint_rows: list[JsonlRow] = []
    for batch_dir in sorted(path for path in work_root.glob("batch-*") if path.is_dir()):
        attr_rows.extend(load_jsonl(batch_dir / "hard_merit_attrs.jsonl", batch=batch_dir.name))
        hint_rows.extend(load_jsonl(batch_dir / "fact_relation_hints.jsonl", batch=batch_dir.name))
    return attr_rows, hint_rows


def _text(value: object) -> str:
    return str(value or "").strip()


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def validate_attr_row(row: JsonlRow) -> list[dict[str, Any]]:
    data = row.row
    issues: list[dict[str, Any]] = []
    required = ("emperor", "object_name", "career_track", "hard_merit_summary", "source_refs")
    for key in required:
        if not data.get(key):
            issues.append(issue(row, "block", "missing_field", f"missing {key}"))
    if _text(data.get("career_track")) not in CAREER_TRACKS:
        issues.append(issue(row, "block", "invalid_career_track", _text(data.get("career_track"))))
    tags = [str(value) for value in _list(data.get("hard_merit_tags"))]
    if _text(data.get("career_track")) != "negative" and not tags:
        issues.append(issue(row, "block", "missing_field", "missing hard_merit_tags"))
    invalid_tags = sorted(set(tags) - HARD_MERIT_TAGS)
    if invalid_tags:
        issues.append(issue(row, "block", "invalid_hard_merit_tag", ", ".join(invalid_tags)))
    scope = _text(data.get("hard_merit_scope_hint"))
    if scope and scope not in SCOPE_HINTS:
        issues.append(issue(row, "warning", "invalid_scope_hint", scope))
    return issues


def validate_hint_row(row: JsonlRow) -> list[dict[str, Any]]:
    data = row.row
    issues: list[dict[str, Any]] = []
    required = ("emperor", "subject_name", "predicate_hint", "relation_role_hint", "target_items_hint", "fact_summary")
    for key in required:
        if not data.get(key):
            issues.append(issue(row, "block", "missing_field", f"missing {key}"))
    if _text(data.get("predicate_hint")) not in PREDICATE_HINTS:
        issues.append(issue(row, "block", "invalid_predicate_hint", _text(data.get("predicate_hint"))))
    if _text(data.get("relation_role_hint")) not in RELATION_ROLE_HINTS:
        issues.append(issue(row, "block", "invalid_relation_role_hint", _text(data.get("relation_role_hint"))))
    if not _list(data.get("source_refs")) and not _list(data.get("source_keys")):
        issues.append(issue(row, "warning", "missing_source_anchor", "missing source_refs/source_keys"))
    return issues


def issue(row: JsonlRow, severity: str, code: str, message: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "batch": row.batch,
        "path": str(row.path),
        "line_no": row.line_no,
        "emperor": row.row.get("emperor") or "",
        "object_name": row.row.get("object_name") or row.row.get("subject_name") or "",
    }


def i5b_target_rule(target: str) -> str | None:
    prefix = "I5B."
    if not target.startswith(prefix):
        return None
    return target[len(prefix) :]


def candidate_rows(hint_rows: Iterable[JsonlRow]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in hint_rows:
        hint = row.row
        targets = [str(value) for value in _list(hint.get("target_items_hint"))]
        if not targets:
            targets = [""]
        for target in targets:
            rule_code = i5b_target_rule(target)
            mapping = None
            status = "cross_item_pending"
            reason = "target item is outside current I5B predicate catalog"
            if rule_code is not None:
                mapping = I5B_FORMAL_MAPPINGS.get((_text(hint.get("predicate_hint")), rule_code))
                if mapping:
                    status = "ready_i5b_catalog"
                    reason = "mapped to current I5B fact_relation_predicate_options"
                else:
                    status = "needs_i5b_predicate_catalog"
                    reason = "I5B target lacks a formal predicate mapping"
            scoring_role, predicate, relation_role = mapping if mapping else ("", "", _text(hint.get("relation_role_hint")))
            candidates.append(
                {
                    "batch": row.batch,
                    "source_hint_path": str(row.path),
                    "source_hint_line": row.line_no,
                    "emperor": hint.get("emperor") or "",
                    "emp_id": hint.get("emp_id"),
                    "subject_name": hint.get("subject_name") or "",
                    "subject_obj_id": hint.get("subject_obj_id"),
                    "emp_obj_id": hint.get("emp_obj_id"),
                    "obj_src_id": hint.get("obj_src_id"),
                    "predicate_hint": hint.get("predicate_hint") or "",
                    "target_item_hint": target,
                    "mapping_status": status,
                    "mapping_reason": reason,
                    "item_code": "I5B" if rule_code is not None else "",
                    "rule_code": rule_code or "",
                    "scoring_role": scoring_role,
                    "formal_predicate": predicate,
                    "relation_role": relation_role,
                    "source_keys": hint.get("source_keys") or [],
                    "source_refs": hint.get("source_refs") or [],
                    "fact_summary": hint.get("fact_summary") or "",
                    "limitations": hint.get("limitations") or "",
                }
            )
    return candidates


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# I5B 硬通货交付验收",
        "",
        f"- hard_merit_attrs: {report['attr_count']}",
        f"- fact_relation_hints: {report['hint_count']}",
        f"- relation_review_candidates: {report['candidate_count']}",
        f"- blocks: {report['blocks']}",
        f"- warnings: {report['warnings']}",
        "",
        "## 映射状态",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in report["mapping_status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "## 批次", "", "| batch | attrs | hints |", "| --- | ---: | ---: |"])
    for batch, counts in report["batch_counts"].items():
        lines.append(f"| `{batch}` | {counts.get('attrs', 0)} | {counts.get('hints', 0)} |")
    if report["issues"]:
        lines.extend(["", "## Issues", "", "| severity | code | batch | line | object | message |", "| --- | --- | --- | ---: | --- | --- |"])
        for item in report["issues"][:80]:
            lines.append(
                f"| {item['severity']} | `{item['code']}` | `{item['batch']}` | {item['line_no']} | "
                f"{item['object_name']} | {item['message']} |"
            )
    lines.append("")
    return "\n".join(lines)


def build_report(work_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attr_rows, hint_rows = load_batches(work_root)
    issues: list[dict[str, Any]] = []
    for row in attr_rows:
        issues.extend(validate_attr_row(row))
    for row in hint_rows:
        issues.extend(validate_hint_row(row))
    candidates = candidate_rows(hint_rows)
    batch_counts: dict[str, dict[str, int]] = {}
    for row in attr_rows:
        batch_counts.setdefault(row.batch, {"attrs": 0, "hints": 0})["attrs"] += 1
    for row in hint_rows:
        batch_counts.setdefault(row.batch, {"attrs": 0, "hints": 0})["hints"] += 1
    report = {
        "schema_version": 1,
        "work_root": str(work_root),
        "attr_count": len(attr_rows),
        "hint_count": len(hint_rows),
        "candidate_count": len(candidates),
        "blocks": sum(1 for item in issues if item["severity"] == "block"),
        "warnings": sum(1 for item in issues if item["severity"] == "warning"),
        "batch_counts": dict(sorted(batch_counts.items())),
        "mapping_status_counts": dict(sorted(Counter(row["mapping_status"] for row in candidates).items())),
        "issues": issues,
    }
    return report, candidates


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_outputs(report: Mapping[str, Any], candidates: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "hard_merit_handoff_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "hard_merit_handoff_report.md").write_text(render_markdown(report), encoding="utf-8")
    write_jsonl(output_dir / "fact_relation_review_candidates.jsonl", candidates)
    for status in ("ready_i5b_catalog", "needs_i5b_predicate_catalog", "cross_item_pending"):
        write_jsonl(
            output_dir / f"fact_relation_{status}.jsonl",
            (row for row in candidates if row["mapping_status"] == status),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate I5B hard-merit handoffs and map relation hints to review candidates.")
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--fail-on-issue", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report, candidates = build_report(args.work_root)
    write_outputs(report, candidates, args.output_dir)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report))
    if args.fail_on_issue and (report["blocks"] or report["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
