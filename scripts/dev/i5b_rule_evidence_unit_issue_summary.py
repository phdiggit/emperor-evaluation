from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_ITEM_CODE,
)
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_rule_evidence_unit_db_sync import (  # noqa: E402
    build_payloads,
    fetch_emperors_with_calc_details,
)
from scripts.dev.i5b_rule_evidence_unit_preview import build_preview  # noqa: E402


class RuleEvidenceUnitIssueSummaryError(ValueError):
    pass


@dataclass(frozen=True)
class IssueSummaryRow:
    emperor: str
    unit_count: int
    issue_count: int
    block_count: int
    warning_count: int
    issues: list[dict[str, str]]


def _text(value: object) -> str:
    return str(value or "").strip()


def _issues_from_preview(preview: Mapping[str, object]) -> list[dict[str, str]]:
    raw_issues = preview.get("issues")
    if not isinstance(raw_issues, list):
        return []
    issues: list[dict[str, str]] = []
    for issue in raw_issues:
        if not isinstance(issue, Mapping):
            continue
        issues.append(
            {
                "severity": _text(issue.get("severity")),
                "code": _text(issue.get("code")),
                "rule_code": _text(issue.get("rule_code")),
                "causal_chain_key": _text(issue.get("causal_chain_key")),
                "object_name": _text(issue.get("object_name")),
                "message": _text(issue.get("message")),
            }
        )
    return issues


def summarize_payload(payload: Mapping[str, object]) -> IssueSummaryRow:
    preview = payload.get("preview")
    if not isinstance(preview, Mapping):
        preview = build_preview(payload)
    issues = _issues_from_preview(preview)
    return IssueSummaryRow(
        emperor=_text(preview.get("emperor") or payload.get("emperor")),
        unit_count=int(preview.get("unit_count") or 0),
        issue_count=len(issues),
        block_count=sum(1 for issue in issues if issue["severity"] == "block"),
        warning_count=sum(1 for issue in issues if issue["severity"] == "warning"),
        issues=issues,
    )


def build_issue_summary(payloads: Sequence[Mapping[str, object]]) -> dict[str, object]:
    rows = [summarize_payload(payload) for payload in payloads]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rows": [asdict(row) for row in rows],
        "totals": {
            "emperors": len(rows),
            "units": sum(row.unit_count for row in rows),
            "issues": sum(row.issue_count for row in rows),
            "blocks": sum(row.block_count for row in rows),
            "warnings": sum(row.warning_count for row in rows),
        },
    }


def render_markdown(summary: Mapping[str, object]) -> str:
    rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    lines = [
        "# I5B 规则承载预览问题汇总",
        "",
        f"- generated_at: `{summary.get('generated_at') or ''}`",
        f"- emperors: `{totals.get('emperors', 0)}`",
        f"- units: `{totals.get('units', 0)}`",
        f"- issues: `{totals.get('issues', 0)}`",
        f"- blocks: `{totals.get('blocks', 0)}`",
        f"- warnings: `{totals.get('warnings', 0)}`",
        "",
        "| 皇帝 | units | issues | blocks | warnings |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _text(row.get("emperor")),
                    str(row.get("unit_count", 0)),
                    str(row.get("issue_count", 0)),
                    str(row.get("block_count", 0)),
                    str(row.get("warning_count", 0)),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 问题明细", ""])
    issue_rows: list[tuple[str, Mapping[str, object]]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        emperor = _text(row.get("emperor"))
        issues = row.get("issues") if isinstance(row.get("issues"), list) else []
        for issue in issues:
            if isinstance(issue, Mapping):
                issue_rows.append((emperor, issue))
    if not issue_rows:
        lines.append("无。")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| 皇帝 | severity | code | rule | chain | object | message |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for emperor, issue in issue_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    emperor,
                    _text(issue.get("severity")),
                    _text(issue.get("code")),
                    _text(issue.get("rule_code")),
                    _text(issue.get("causal_chain_key")),
                    _text(issue.get("object_name")),
                    _text(issue.get("message")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_output(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize I5B rule evidence unit preview issues.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name; repeatable.")
    parser.add_argument("--all-emperors", action="store_true", help="Summarize all emperors with I5B calc details.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit to one I5B rule_code; repeatable.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-issue", action="store_true")
    return parser.parse_args(argv)


def selected_emperors(args: argparse.Namespace, *, dsn: str) -> tuple[str, ...]:
    rule_codes = tuple(args.rule_code)
    if args.all_emperors:
        return fetch_emperors_with_calc_details(
            dsn=dsn,
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            rule_codes=rule_codes,
        )
    emperors = tuple(dict.fromkeys(args.emperor))
    if not emperors:
        raise RuleEvidenceUnitIssueSummaryError("no emperors selected; use --emperor or --all-emperors")
    return emperors


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = args.dsn or resolve_dsn(args.dsn_env)
    emperors = selected_emperors(args, dsn=dsn)
    payloads = build_payloads(
        dsn=dsn,
        emperors=emperors,
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        rule_codes=tuple(args.rule_code),
    )
    summary = build_issue_summary(payloads)
    if args.format == "json":
        text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = render_markdown(summary)
    write_output(text, args.output)
    totals = summary["totals"]
    issue_count = int(totals["issues"]) if isinstance(totals, Mapping) else 0
    return 1 if args.fail_on_issue and issue_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
