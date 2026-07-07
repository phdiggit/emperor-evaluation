from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_candidate_prompt as candidate_prompt


PROMPT_GOVERNANCE_VERSION = "prompt_governance_v0_1"

CASE_TERM_BLOCKLIST = ("刘基", "總中書政", "总中书政")

PROMPT_DEBT_PATTERNS = (
    {
        "debt_code": "finite_enum_verbatim",
        "category": "schema_validator",
        "preferred_location": "contract_constants_and_validator",
        "severity": "medium",
        "pattern": r"\|",
        "reason": "slash-separated finite enum text should migrate to constants and validators where possible.",
    },
    {
        "debt_code": "source_recall_terms_in_prompt",
        "category": "source_discovery",
        "preferred_location": "source_discovery_profile",
        "severity": "high",
        "pattern": r"召回|优先抽取|優先抽取|高优先级|高優先級|query terms|检索词|檢索詞",
        "reason": "recall and extraction priority text should live in source discovery/profile layers.",
    },
    {
        "debt_code": "route_table_verbatim",
        "category": "route_table",
        "preferred_location": "route_table_schema_validator",
        "severity": "medium",
        "pattern": r"candidate_lane|hint_status|future_rule_hint|current_rule_candidate|rejected_or_context_only",
        "reason": "route contract text should be generated from route tables and checked by validators.",
    },
    {
        "debt_code": "profile_schema_verbatim",
        "category": "payload_schema",
        "preferred_location": "payload_schema_validator",
        "severity": "medium",
        "pattern": r"personnel_profile|power_control_profile|fact_payload|claim_completeness|evidence_spans",
        "reason": "payload field inventory should migrate to schema constants and report validation.",
    },
    {
        "debt_code": "factor_hint_enum_verbatim",
        "category": "schema_validator",
        "preferred_location": "contract_constants_and_validator",
        "severity": "medium",
        "pattern": r"appointment_delegation_factor_hints|importance_hint|effect_hint|continuity_hint|uncertainty_flags",
        "reason": "factor hint enum inventory should be generated from constants and validated off-prompt.",
    },
    {
        "debt_code": "case_term_in_prompt",
        "category": "case_term",
        "preferred_location": "diagnostic_worklist_or_recall_sampler",
        "severity": "block",
        "pattern": "|".join(re.escape(term) for term in CASE_TERM_BLOCKLIST),
        "reason": "case terms must not become long-term prompt burden.",
    },
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def text(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def text_metrics(value: str) -> dict[str, int]:
    chars = len(value)
    return {
        "chars": chars,
        "utf8_bytes": len(value.encode("utf-8")),
        "line_count": len(value.splitlines()),
        "rough_token_units_4chars": int(math.ceil(chars / 4)),
    }


def prompt_kind(path: Path) -> str:
    name = path.name
    if name.startswith("judge_prompt."):
        return "judge_prompt"
    if name.startswith("taskgen_batch_prompt"):
        return "taskgen_batch_prompt"
    if name.startswith("taskgen_prompt"):
        return "taskgen_prompt"
    if name.startswith("alias_refiner_prompt"):
        return "alias_refiner_prompt"
    if "prompt" in name:
        return "other_prompt"
    return "unknown"


def prompt_file_entry(path: Path, *, base: Path | None = None) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    entry = {
        "path": str(path.relative_to(base)) if base else repo_relative(path),
        "prompt_kind": prompt_kind(path),
        **text_metrics(content),
    }
    if ".JSH-" in path.name:
        entry["sharded"] = True
    elif path.name.startswith("judge_prompt."):
        entry["sharded"] = False
    return entry


def find_prompt_files(run_root: Path) -> list[Path]:
    return sorted(path for path in run_root.rglob("*.md") if "prompt" in path.name)


def merge_usage(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    totals = summary.get("totals")
    if isinstance(totals, Mapping) and isinstance(totals.get("usage"), Mapping):
        return totals["usage"]
    usage = summary.get("usage")
    return usage if isinstance(usage, Mapping) else {}


def prompt_totals(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_chars = sum(int(entry.get("chars") or 0) for entry in entries)
    total_bytes = sum(int(entry.get("utf8_bytes") or 0) for entry in entries)
    total_units = sum(int(entry.get("rough_token_units_4chars") or 0) for entry in entries)
    max_chars = max((int(entry.get("chars") or 0) for entry in entries), default=0)
    by_kind: dict[str, int] = {}
    for entry in entries:
        kind = text(entry.get("prompt_kind")) or "unknown"
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "prompt_count": len(entries),
        "prompt_chars": total_chars,
        "prompt_utf8_bytes": total_bytes,
        "rough_token_units_4chars": total_units,
        "max_prompt_chars": max_chars,
        "avg_prompt_chars": round(total_chars / len(entries), 2) if entries else 0,
        "prompt_count_by_kind": dict(sorted(by_kind.items())),
    }


def prompt_debt_matches(source_text: str) -> list[dict[str, Any]]:
    lines = source_text.splitlines()
    matches: list[dict[str, Any]] = []
    for spec in PROMPT_DEBT_PATTERNS:
        pattern = re.compile(str(spec["pattern"]))
        examples: list[dict[str, Any]] = []
        matched_chars = 0
        for index, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue
            stripped = line.strip()
            matched_chars += len(stripped)
            if len(examples) < 5:
                examples.append(
                    {
                        "line": index,
                        "sample": stripped[:220],
                    }
                )
        if not examples:
            continue
        matches.append(
            {
                "debt_code": spec["debt_code"],
                "category": spec["category"],
                "preferred_location": spec["preferred_location"],
                "severity": spec["severity"],
                "reason": spec["reason"],
                "match_count": sum(1 for line in lines if pattern.search(line)),
                "matched_source_chars": matched_chars,
                "examples": examples,
            }
        )
    severity_order = {"block": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        matches,
        key=lambda row: (
            severity_order.get(str(row.get("severity")), 9),
            -int(row.get("matched_source_chars") or 0),
            str(row.get("debt_code")),
        ),
    )


def debt_summary(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    total_matches = 0
    total_chars = 0
    for item in items:
        category = text(item.get("category")) or "unknown"
        severity = text(item.get("severity")) or "unknown"
        by_category[category] = by_category.get(category, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
        total_matches += int(item.get("match_count") or 0)
        total_chars += int(item.get("matched_source_chars") or 0)
    return {
        "debt_item_count": len(items),
        "source_line_match_count": total_matches,
        "matched_source_chars": total_chars,
        "debt_item_count_by_category": dict(sorted(by_category.items())),
        "debt_item_count_by_severity": dict(sorted(by_severity.items())),
    }


def run_root_report(run_root: Path) -> dict[str, Any]:
    summary_path = run_root / "summary.json"
    summary = load_json(summary_path) if summary_path.exists() else {}
    prompt_entries = [prompt_file_entry(path, base=run_root) for path in find_prompt_files(run_root)]
    return {
        "generated_by": "scripts/dev/retrieval_v2_prompt_governance.py",
        "version": PROMPT_GOVERNANCE_VERSION,
        "report_type": "run_root_prompt_budget",
        "run_root": str(run_root),
        "summary_path": str(summary_path) if summary_path.exists() else None,
        "usage": merge_usage(summary if isinstance(summary, Mapping) else {}),
        "totals": prompt_totals(prompt_entries),
        "prompts": prompt_entries,
    }


def candidates_prompt_report(candidates_path: Path) -> dict[str, Any]:
    candidates = load_json(candidates_path)
    if not isinstance(candidates, Mapping):
        raise TypeError("candidates JSON must be an object")
    prompt = candidate_prompt.build_prompt(candidates)
    payload = candidate_prompt.prompt_payload(candidates)
    candidate_slices = payload.get("candidate_slices") if isinstance(payload, Mapping) else []
    object_seeds = payload.get("object_seeds") if isinstance(payload, Mapping) else []
    return {
        "generated_by": "scripts/dev/retrieval_v2_prompt_governance.py",
        "version": PROMPT_GOVERNANCE_VERSION,
        "report_type": "candidate_prompt_budget",
        "candidates_path": str(candidates_path),
        "candidate_slice_count": len(candidate_slices) if isinstance(candidate_slices, list) else 0,
        "object_seed_count": len(object_seeds) if isinstance(object_seeds, list) else 0,
        "prompt": {
            "prompt_kind": "judge_prompt",
            **text_metrics(prompt),
        },
    }


def source_debt_report(source_path: Path) -> dict[str, Any]:
    source_text = source_path.read_text(encoding="utf-8")
    debt_items = prompt_debt_matches(source_text)
    return {
        "generated_by": "scripts/dev/retrieval_v2_prompt_governance.py",
        "version": PROMPT_GOVERNANCE_VERSION,
        "report_type": "source_prompt_debt_inventory",
        "source_path": repo_relative(source_path),
        "source_metrics": text_metrics(source_text),
        "summary": debt_summary(debt_items),
        "debt_items": debt_items,
    }


def debt_template() -> dict[str, Any]:
    return {
        "generated_by": "scripts/dev/retrieval_v2_prompt_governance.py",
        "version": PROMPT_GOVERNANCE_VERSION,
        "report_type": "prompt_debt_template",
        "principle": "先迁移到 profile / route table / schema / validator，再删除长期 prompt 文本。",
        "debt_items": [
            {
                "debt_code": "judge_prompt_monolith",
                "owner_path": "scripts/dev/retrieval_v2_candidate_prompt.py",
                "current_location": "long_term_core_prompt",
                "preferred_location": "route_table_schema_validator",
                "status": "open",
                "exit_condition": "硬枚举和可校验字段已由 schema/report 覆盖，prompt 只保留机制级边界。",
            },
            {
                "debt_code": "source_recall_terms_in_prompt",
                "owner_path": "scripts/dev/retrieval_v2_candidate_prompt.py",
                "current_location": "long_term_core_prompt",
                "preferred_location": "source_discovery_profile",
                "status": "open",
                "exit_condition": "召回词均迁移到 source candidate/profile 层，judge prompt 不含个案词表。",
            },
            {
                "debt_code": "factor_hint_enum_verbatim",
                "owner_path": "scripts/dev/retrieval_v2_candidate_prompt.py",
                "current_location": "long_term_core_prompt",
                "preferred_location": "contract_constants_and_validator",
                "status": "open",
                "exit_condition": "有限枚举由契约常量和 report 校验，prompt 只说明不得输出正式 label/数值。",
            },
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 prompt governance report",
        "",
        f"- report_type: `{report.get('report_type')}`",
        f"- version: `{report.get('version')}`",
    ]
    if report.get("run_root"):
        lines.append(f"- run_root: `{report['run_root']}`")
    if report.get("candidates_path"):
        lines.append(f"- candidates_path: `{report['candidates_path']}`")
    if report.get("source_path"):
        lines.append(f"- source_path: `{report['source_path']}`")
    if isinstance(report.get("totals"), Mapping):
        totals = report["totals"]
        lines.extend(
            [
                f"- prompt_count: `{totals.get('prompt_count')}`",
                f"- prompt_chars: `{totals.get('prompt_chars')}`",
                f"- max_prompt_chars: `{totals.get('max_prompt_chars')}`",
                f"- rough_token_units_4chars: `{totals.get('rough_token_units_4chars')}`",
            ]
        )
    if isinstance(report.get("prompt"), Mapping):
        prompt = report["prompt"]
        lines.extend(
            [
                f"- prompt_chars: `{prompt.get('chars')}`",
                f"- rough_token_units_4chars: `{prompt.get('rough_token_units_4chars')}`",
                f"- candidate_slice_count: `{report.get('candidate_slice_count')}`",
                f"- object_seed_count: `{report.get('object_seed_count')}`",
            ]
        )
    if isinstance(report.get("usage"), Mapping) and report["usage"]:
        lines.append(f"- usage: `{json.dumps(report['usage'], ensure_ascii=False, sort_keys=True)}`")
    if isinstance(report.get("summary"), Mapping):
        summary = report["summary"]
        lines.extend(
            [
                f"- debt_item_count: `{summary.get('debt_item_count')}`",
                f"- source_line_match_count: `{summary.get('source_line_match_count')}`",
                f"- matched_source_chars: `{summary.get('matched_source_chars')}`",
            ]
        )
    if isinstance(report.get("debt_items"), list) and report["debt_items"]:
        lines.extend(["", "## debt items", ""])
        for item in report["debt_items"]:
            lines.append(
                f"- `{item.get('debt_code')}` severity=`{item.get('severity')}` "
                f"matches=`{item.get('match_count')}` target=`{item.get('preferred_location')}`"
            )
    return "\n".join(lines) + "\n"


def write_optional_outputs(report: Mapping[str, Any], *, output_json: Path | None, output_md: Path | None) -> None:
    if output_json is not None:
        write_json(output_json, report)
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate retrieval_v2 prompt budget and debt reports.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-root", help="Measure prompt files under a retrieval_v2 run_root.")
    run_parser.add_argument("--run-root", type=Path, required=True)
    run_parser.add_argument("--output-json", type=Path)
    run_parser.add_argument("--output-md", type=Path)

    candidates_parser = subparsers.add_parser("candidates", help="Build and measure the judge prompt for candidates JSON.")
    candidates_parser.add_argument("--candidates", type=Path, required=True)
    candidates_parser.add_argument("--output-json", type=Path)
    candidates_parser.add_argument("--output-md", type=Path)

    source_parser = subparsers.add_parser("source-debt", help="Scan a prompt source file for migration-ready debt.")
    source_parser.add_argument("--source", type=Path, default=ROOT / "scripts" / "dev" / "retrieval_v2_candidate_prompt.py")
    source_parser.add_argument("--output-json", type=Path)
    source_parser.add_argument("--output-md", type=Path)

    debt_parser = subparsers.add_parser("debt-template", help="Emit a starter prompt debt inventory.")
    debt_parser.add_argument("--output-json", type=Path)
    debt_parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run-root":
        report = run_root_report(args.run_root)
    elif args.command == "candidates":
        report = candidates_prompt_report(args.candidates)
    elif args.command == "source-debt":
        report = source_debt_report(args.source)
    elif args.command == "debt-template":
        report = debt_template()
    else:  # pragma: no cover
        parser.error(f"unknown command: {args.command}")
    write_optional_outputs(report, output_json=args.output_json, output_md=args.output_md)
    print(
        stable_json(
            {
                "ok": True,
                "report_type": report["report_type"],
                "totals": report.get("totals") or report.get("prompt") or report.get("summary") or {},
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
