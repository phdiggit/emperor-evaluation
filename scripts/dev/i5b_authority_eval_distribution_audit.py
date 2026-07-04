from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_authority_eval_handoff import DEFAULT_WORK_ROOT, JsonlRow, load_batches
from scripts.dev.i5b_finite_values import (
    NEGATIVE_TALENT_QUALITY_VALUES,
    POSITIVE_TALENT_QUALITY_VALUES,
    TALENT_PROFILE_NOTE_ATTR,
    TALENT_QUALITY_ATTR,
)


DEFAULT_OUTPUT_DIR = Path("tmp/i5b-authority-eval-work/review")

TALENT_QUALITY_PROPOSAL_FIELD = f"{TALENT_QUALITY_ATTR}_proposal"
TALENT_QUALITY_BASIS_FIELD = f"{TALENT_QUALITY_ATTR}_basis"
NEGATIVE_PROPOSALS = set(NEGATIVE_TALENT_QUALITY_VALUES)
IMPORTANT_POSITIVE_PROPOSAL = POSITIVE_TALENT_QUALITY_VALUES[1]
TOP_POSITIVE_PROPOSAL = POSITIVE_TALENT_QUALITY_VALUES[2]
HISTORICAL_POSITIVE_PROPOSAL = POSITIVE_TALENT_QUALITY_VALUES[-1]
HIGH_POSITIVE_PROPOSALS = set(POSITIVE_TALENT_QUALITY_VALUES[2:])
MIXED_PROFILE_NEGATIVE_TERMS = {
    "严酷",
    "屠",
    "屠掠",
    "杀戮",
    "残酷",
    "酷烈",
    "构陷",
    "诬陷",
    "压制",
    "排斥",
    "贪腐",
    "聚敛",
    "党争",
    "祸",
    "损害",
    "民生",
    "治理伤害",
    "安全风险",
    "负向",
    "污点",
    "争议",
}
STRONG_RESULT_TERMS = {
    "开国",
    "中兴",
    "制度",
    "典章",
    "律令",
    "改革",
    "财政",
    "经济",
    "盐铁",
    "漕运",
    "战役",
    "统帅",
    "主帅",
    "战略",
    "平定",
    "统一",
    "灭",
    "攻",
    "守",
    "边疆",
    "外交",
    "法制",
    "宰辅",
    "宰相",
    "辅政",
    "军政",
    "谏",
    "荐才",
    "文化",
    "史学",
    "工程",
    "治水",
}
GENERIC_EVALUATION_TERMS = {
    "有传",
    "任职",
    "历任",
    "官至",
    "参与",
    "重臣",
    "名臣",
    "名将",
    "高层",
    "中枢",
    "政务",
    "具有一定",
    "评价较高",
    "官员",
    "执行",
}
SECONDARY_AUTHORITY_TYPES = {"chronicle", "modern_scholarship", "reference_work", "later_history"}
WEAK_BASIS_FOR_HIGH_GRADE = {"hard_merit", "uncertain", "authority_conflict"}
REVIEW_KEEP_STATUSES = {
    "keep_top",
    "keep_important",
    "keep_historical",
    "keep_negative",
}
MIXED_PROFILE_REVIEW_STATUSES = {
    "negative_followup_recorded",
    "mixed_profile_reviewed",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_types(row: Mapping[str, Any]) -> list[str]:
    sources = [source for source in _list(row.get("authority_eval_sources")) if isinstance(source, Mapping)]
    return [_text(source.get("source_type")) or "unknown" for source in sources]


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _review_codes(row: JsonlRow) -> list[str]:
    data = row.row
    if _text(data.get("distribution_review_status")) in REVIEW_KEEP_STATUSES:
        return []
    proposal = _text(data.get(TALENT_QUALITY_PROPOSAL_FIELD))
    confidence = _text(data.get("confidence"))
    basis = _text(data.get(TALENT_QUALITY_BASIS_FIELD))
    summary = _text(data.get("authority_eval_summary"))
    talent_profile_note = _text(data.get(TALENT_PROFILE_NOTE_ATTR))
    mixed_profile_review_status = _text(data.get("mixed_profile_review_status"))
    source_types = _source_types(data)
    source_count = len(source_types)
    codes: list[str] = []

    if (
        proposal in HIGH_POSITIVE_PROPOSALS
        and talent_profile_note
        and mixed_profile_review_status not in MIXED_PROFILE_REVIEW_STATUSES
        and _has_any(talent_profile_note, MIXED_PROFILE_NEGATIVE_TERMS)
    ):
        codes.append("positive_talent_with_negative_profile_note")

    if proposal == HISTORICAL_POSITIVE_PROPOSAL:
        if confidence == "high" and source_count < 2:
            codes.append("historical_single_source_needs_second_authority")
        if basis in WEAK_BASIS_FOR_HIGH_GRADE:
            codes.append("historical_weak_basis")

    if proposal == TOP_POSITIVE_PROPOSAL:
        if confidence == "high" and source_count < 2 and not (set(source_types) & SECONDARY_AUTHORITY_TYPES):
            codes.append("top_grade_single_source")
        if basis in WEAK_BASIS_FOR_HIGH_GRADE:
            codes.append("top_grade_weak_basis")
        if _has_any(summary, GENERIC_EVALUATION_TERMS) and not _has_any(summary, STRONG_RESULT_TERMS):
            codes.append("top_grade_needs_outcome_basis")

    if proposal == IMPORTANT_POSITIVE_PROPOSAL:
        if basis in {"uncertain", "authority_conflict"}:
            codes.append("important_uncertain_basis")
        if confidence == "high" and _has_any(summary, GENERIC_EVALUATION_TERMS) and not _has_any(summary, STRONG_RESULT_TERMS):
            codes.append("important_grade_needs_ordinary_check")

    if proposal in NEGATIVE_PROPOSALS and confidence == "high" and basis not in {"negative_consensus", "authority_consensus", "mixed"}:
        codes.append("negative_grade_basis_review")

    return codes


def _action_for_codes(codes: list[str]) -> str:
    if any(code.startswith("top_grade") for code in codes):
        return "review_top_to_important_or_keep"
    if any(code.startswith("important") for code in codes):
        return "review_important_to_ordinary_or_keep"
    if any(code.startswith("historical") for code in codes):
        return "review_historical_support_or_keep"
    if any(code.startswith("negative") for code in codes):
        return "review_negative_grade_or_keep"
    if "positive_talent_with_negative_profile_note" in codes:
        return "review_mixed_profile_negative_followup"
    return "keep"


def audit_rows(rows: Iterable[JsonlRow]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        data = row.row
        codes = _review_codes(row)
        if not codes:
            continue
        findings.append(
            {
                "batch": row.batch,
                "source_path": str(row.path),
                "source_line": row.line_no,
                "emperor": data.get("emperor") or "",
                "emp_id": data.get("emp_id"),
                "object_name": data.get("object_name") or "",
                "obj_id": data.get("obj_id"),
                "emp_obj_id": data.get("emp_obj_id"),
                "career_track": data.get("career_track") or "",
                TALENT_QUALITY_PROPOSAL_FIELD: data.get(TALENT_QUALITY_PROPOSAL_FIELD) or "",
                TALENT_QUALITY_BASIS_FIELD: data.get(TALENT_QUALITY_BASIS_FIELD) or "",
                "confidence": data.get("confidence") or "",
                "source_types": _source_types(data),
                "review_codes": codes,
                "recommended_action": _action_for_codes(codes),
                "authority_eval_summary": data.get("authority_eval_summary") or "",
                "authority_eval_limitations": data.get("authority_eval_limitations") or data.get("limitations") or "",
                TALENT_PROFILE_NOTE_ATTR: data.get(TALENT_PROFILE_NOTE_ATTR) or "",
                "mixed_profile_review_status": data.get("mixed_profile_review_status") or "",
            }
        )
    findings.sort(
        key=lambda item: (
            str(item["recommended_action"]),
            str(item[TALENT_QUALITY_PROPOSAL_FIELD]),
            str(item["emperor"]),
            str(item["object_name"]),
            int(item.get("source_line") or 0),
        )
    )
    return findings


def build_report(work_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = load_batches(work_root)
    findings = audit_rows(rows)
    proposal_counts = Counter(_text(row.row.get(TALENT_QUALITY_PROPOSAL_FIELD)) for row in rows)
    confidence_counts = Counter(_text(row.row.get("confidence")) for row in rows)
    review_code_counts = Counter(code for finding in findings for code in finding["review_codes"])
    action_counts = Counter(finding["recommended_action"] for finding in findings)
    report = {
        "schema_version": 1,
        "work_root": str(work_root),
        "row_count": len(rows),
        "review_candidate_count": len(findings),
        "proposal_counts": dict(sorted(proposal_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "review_action_counts": dict(sorted(action_counts.items())),
        "review_code_counts": dict(sorted(review_code_counts.items())),
    }
    return report, findings


def render_markdown(report: Mapping[str, Any], findings: list[dict[str, Any]]) -> str:
    lines = [
        "# I5B 权威评价分布复核",
        "",
        f"- authority_eval_attrs: {report['row_count']}",
        f"- review_candidates: {report['review_candidate_count']}",
        "",
        "## 建议等级分布",
        "",
        "| proposal | count |",
        "| --- | ---: |",
    ]
    for proposal, count in report["proposal_counts"].items():
        lines.append(f"| `{proposal}` | {count} |")
    lines.extend(["", "## 复核动作", "", "| action | count |", "| --- | ---: |"])
    for action, count in report["review_action_counts"].items():
        lines.append(f"| `{action}` | {count} |")
    lines.extend(["", "## 复核原因", "", "| code | count |", "| --- | ---: |"])
    for code, count in report["review_code_counts"].items():
        lines.append(f"| `{code}` | {count} |")
    lines.extend(
        [
            "",
            "## 候选明细",
            "",
            "| action | proposal | confidence | emperor | object | codes | summary | profile note |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for finding in findings[:200]:
        codes = ", ".join(finding["review_codes"])
        summary = str(finding["authority_eval_summary"]).replace("|", " / ")
        profile_note = str(finding.get(TALENT_PROFILE_NOTE_ATTR) or "").replace("|", " / ")
        lines.append(
            f"| `{finding['recommended_action']}` | {finding[TALENT_QUALITY_PROPOSAL_FIELD]} | {finding['confidence']} | "
            f"{finding['emperor']} | {finding['object_name']} | {codes} | {summary} |"
            f" {profile_note} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_outputs(report: Mapping[str, Any], findings: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "authority_eval_distribution_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "authority_eval_distribution_audit.md").write_text(render_markdown(report, findings), encoding="utf-8")
    write_jsonl(output_dir / "authority_eval_distribution_review_candidates.jsonl", findings)
    for action in (
        "review_top_to_important_or_keep",
        "review_important_to_ordinary_or_keep",
        "review_historical_support_or_keep",
        "review_negative_grade_or_keep",
        "review_mixed_profile_negative_followup",
    ):
        write_jsonl(
            output_dir / f"authority_eval_{action}.jsonl",
            (finding for finding in findings if finding["recommended_action"] == action),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit I5B authority-eval talent-quality distribution for over-grading review.")
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--fail-on-review-candidate", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report, findings = build_report(args.work_root)
    write_outputs(report, findings, args.output_dir)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report, findings))
    if args.fail_on_review_candidate and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
