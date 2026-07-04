from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_finite_values import (
    CANONICAL_TALENT_QUALITY_VALUES,
    DEFERRED_TALENT_QUALITY_VALUES,
    NEGATIVE_TALENT_QUALITY_VALUES,
    POSITIVE_TALENT_QUALITY_VALUES,
    TALENT_PROFILE_NOTE_ATTR,
    TALENT_QUALITY_ATTR,
)


DEFAULT_WORK_ROOT = Path("tmp/i5b-authority-eval-work")
DEFAULT_OUTPUT_DIR = Path("tmp/i5b-authority-eval-work/review")

TALENT_QUALITY_PROPOSAL_FIELD = f"{TALENT_QUALITY_ATTR}_proposal"
TALENT_QUALITY_BASIS_FIELD = f"{TALENT_QUALITY_ATTR}_basis"
LOCAL_DEFERRED_TALENT_QUALITY_VALUES = ("暂不定级", "needs_review", "unknown")
DEFERRED_TALENT_QUALITY_PROPOSALS = set(DEFERRED_TALENT_QUALITY_VALUES) | set(LOCAL_DEFERRED_TALENT_QUALITY_VALUES)
TALENT_QUALITY_PROPOSALS = set(CANONICAL_TALENT_QUALITY_VALUES) | DEFERRED_TALENT_QUALITY_PROPOSALS
HIGH_AUTHORITY_PROPOSALS = set(POSITIVE_TALENT_QUALITY_VALUES[2:]) | set(NEGATIVE_TALENT_QUALITY_VALUES[1:])
HISTORICAL_TALENT_QUALITY_PROPOSALS = {POSITIVE_TALENT_QUALITY_VALUES[-1], NEGATIVE_TALENT_QUALITY_VALUES[-1]}
TALENT_QUALITY_BASIS = {
    "authority_consensus",
    "mixed",
    "hard_merit",
    "authority_conflict",
    "negative_consensus",
    "uncertain",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
SOURCE_TYPES = {
    "official_history",
    "later_history",
    "chronicle",
    "modern_scholarship",
    "reference_work",
    "collected_works",
    "epigraphy",
    "local_gazetteer",
    "literary_tradition",
    "unknown",
}
HIGH_VALUE_SOURCE_TYPES = {
    "official_history",
    "later_history",
    "chronicle",
    "modern_scholarship",
    "reference_work",
    "collected_works",
    "epigraphy",
}
CAREER_TRACKS = {"civil", "military", "mixed", "cultural", "technical", "negative", "unknown"}


class AuthorityEvalHandoffError(ValueError):
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
            raise AuthorityEvalHandoffError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise AuthorityEvalHandoffError(f"{path}:{line_no}: expected JSON object")
        rows.append(JsonlRow(batch=batch, path=path, line_no=line_no, row=row))
    return rows


def load_batches(work_root: Path) -> list[JsonlRow]:
    rows: list[JsonlRow] = []
    for batch_dir in sorted(path for path in work_root.glob("batch-*") if path.is_dir()):
        rows.extend(load_jsonl(batch_dir / "authority_eval_attrs.jsonl", batch=batch_dir.name))
    return rows


def _text(value: object) -> str:
    return str(value or "").strip()


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def issue(row: JsonlRow, severity: str, code: str, message: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "batch": row.batch,
        "path": str(row.path),
        "line_no": row.line_no,
        "emperor": row.row.get("emperor") or "",
        "object_name": row.row.get("object_name") or "",
    }


def source_type_counts(sources: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(_text(source.get("source_type")) or "unknown" for source in sources)
    return dict(sorted(counts.items()))


def validate_source(row: JsonlRow, source: Mapping[str, Any], *, index: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    source_type = _text(source.get("source_type")) or "unknown"
    if source_type not in SOURCE_TYPES:
        issues.append(issue(row, "block", "invalid_source_type", f"authority_eval_sources[{index}].source_type={source_type}"))
    if not _text(source.get("source_ref")) and not _text(source.get("source_key")):
        issues.append(issue(row, "block", "missing_source_ref", f"authority_eval_sources[{index}] missing source_ref/source_key"))
    if not _text(source.get("evaluation_note")) and not _text(source.get("quote_excerpt")):
        issues.append(issue(row, "warning", "missing_evaluation_note", f"authority_eval_sources[{index}] missing evaluation_note/quote_excerpt"))
    return issues


def validate_eval_row(row: JsonlRow) -> list[dict[str, Any]]:
    data = row.row
    issues: list[dict[str, Any]] = []
    required = (
        "emperor",
        "object_name",
        "authority_eval_summary",
        "authority_eval_sources",
        TALENT_QUALITY_PROPOSAL_FIELD,
        TALENT_QUALITY_BASIS_FIELD,
        "confidence",
    )
    for key in required:
        if not data.get(key):
            issues.append(issue(row, "block", "missing_field", f"missing {key}"))

    proposal = _text(data.get(TALENT_QUALITY_PROPOSAL_FIELD))
    if proposal and proposal not in TALENT_QUALITY_PROPOSALS:
        issues.append(issue(row, "block", "invalid_talent_quality_proposal", proposal))
    basis = _text(data.get(TALENT_QUALITY_BASIS_FIELD))
    if basis and basis not in TALENT_QUALITY_BASIS:
        issues.append(issue(row, "block", "invalid_talent_quality_basis", basis))
    confidence = _text(data.get("confidence"))
    if confidence and confidence not in CONFIDENCE_LEVELS:
        issues.append(issue(row, "block", "invalid_confidence", confidence))
    career_track = _text(data.get("career_track"))
    if career_track and career_track not in CAREER_TRACKS:
        issues.append(issue(row, "warning", "invalid_career_track", career_track))

    sources_raw = _list(data.get("authority_eval_sources"))
    if not sources_raw:
        issues.append(issue(row, "block", "missing_authority_sources", "authority_eval_sources must be a non-empty list"))
    sources = [source for source in sources_raw if isinstance(source, Mapping)]
    if len(sources) != len(sources_raw):
        issues.append(issue(row, "block", "invalid_authority_source", "authority_eval_sources entries must be JSON objects"))
    for index, source in enumerate(sources):
        issues.extend(validate_source(row, source, index=index))

    source_types = {_text(source.get("source_type")) or "unknown" for source in sources}
    high_value_count = len(source_types & HIGH_VALUE_SOURCE_TYPES)
    if proposal in HIGH_AUTHORITY_PROPOSALS and not high_value_count:
        issues.append(issue(row, "warning", "weak_sources_for_high_proposal", "high proposal has no high-value authority source"))
    if proposal in HISTORICAL_TALENT_QUALITY_PROPOSALS and confidence == "low":
        issues.append(issue(row, "warning", "low_confidence_historical_proposal", "historical-level proposal is low confidence"))
    if basis == "authority_conflict" and confidence == "high":
        issues.append(issue(row, "warning", "conflict_with_high_confidence", "authority_conflict should usually not be high confidence"))
    return issues


def candidate_status(row: JsonlRow, row_issues: list[dict[str, Any]]) -> str:
    if any(item["severity"] == "block" for item in row_issues):
        return "blocked"
    if any(item["severity"] == "warning" for item in row_issues):
        return "needs_review"
    proposal = _text(row.row.get(TALENT_QUALITY_PROPOSAL_FIELD))
    if proposal in DEFERRED_TALENT_QUALITY_PROPOSALS:
        return "deferred"
    if _text(row.row.get("confidence")) == "high":
        return "ready_high_confidence"
    return "ready_review"


def candidate_rows(rows: Iterable[JsonlRow], issues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    issues_by_row: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for item in issues:
        issues_by_row.setdefault((item["path"], int(item["line_no"])), []).append(item)

    candidates: list[dict[str, Any]] = []
    for row in rows:
        data = row.row
        row_issues = issues_by_row.get((str(row.path), row.line_no), [])
        sources = [source for source in _list(data.get("authority_eval_sources")) if isinstance(source, Mapping)]
        candidates.append(
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
                "candidate_status": candidate_status(row, row_issues),
                "source_type_counts": source_type_counts(sources),
                "authority_eval_summary": data.get("authority_eval_summary") or "",
                "authority_eval_limitations": data.get("authority_eval_limitations") or data.get("limitations") or "",
                TALENT_PROFILE_NOTE_ATTR: data.get(TALENT_PROFILE_NOTE_ATTR) or "",
                "issue_codes": [item["code"] for item in row_issues],
            }
        )
    return candidates


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# I5B 权威评价交付验收",
        "",
        f"- authority_eval_attrs: {report['row_count']}",
        f"- talent_quality_candidates: {report['candidate_count']}",
        f"- blocks: {report['blocks']}",
        f"- warnings: {report['warnings']}",
        "",
        "## 候选状态",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in report["candidate_status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "## 建议等级", "", "| talent_quality_proposal | count |", "| --- | ---: |"])
    for proposal, count in report["proposal_counts"].items():
        lines.append(f"| `{proposal}` | {count} |")
    lines.extend(["", "## 批次", "", "| batch | rows |", "| --- | ---: |"])
    for batch, count in report["batch_counts"].items():
        lines.append(f"| `{batch}` | {count} |")
    if report["issues"]:
        lines.extend(["", "## Issues", "", "| severity | code | batch | line | object | message |", "| --- | --- | --- | ---: | --- | --- |"])
        for item in report["issues"][:80]:
            lines.append(
                f"| {item['severity']} | `{item['code']}` | `{item['batch']}` | {item['line_no']} | "
                f"{item['object_name']} | {item['message']} |"
            )
    lines.append("")
    return "\n".join(lines)


def render_priority_candidates(candidates: Iterable[Mapping[str, Any]]) -> str:
    rows = [row for row in candidates if row.get(TALENT_QUALITY_PROPOSAL_FIELD) in HIGH_AUTHORITY_PROPOSALS]
    rows.sort(
        key=lambda row: (
            str(row.get("candidate_status") or ""),
            str(row.get(TALENT_QUALITY_PROPOSAL_FIELD) or ""),
            str(row.get("emperor") or ""),
            str(row.get("object_name") or ""),
        )
    )
    lines = [
        "# I5B 高价值人才等级候选",
        "",
        "| status | proposal | confidence | emperor | object | source types | summary | limitations |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        source_counts = row.get("source_type_counts") if isinstance(row.get("source_type_counts"), Mapping) else {}
        source_text = ", ".join(f"{key}:{value}" for key, value in sorted(source_counts.items()))
        summary = str(row.get("authority_eval_summary") or "").replace("|", " / ")
        limitations = str(row.get("authority_eval_limitations") or "").replace("|", " / ")
        profile_note = str(row.get(TALENT_PROFILE_NOTE_ATTR) or "").replace("|", " / ")
        if profile_note:
            limitations = f"{limitations}；profile_note: {profile_note}" if limitations else f"profile_note: {profile_note}"
        lines.append(
            f"| `{row.get('candidate_status') or ''}` | {row.get(TALENT_QUALITY_PROPOSAL_FIELD) or ''} | "
            f"{row.get('confidence') or ''} | {row.get('emperor') or ''} | {row.get('object_name') or ''} | "
            f"{source_text} | {summary} | {limitations} |"
        )
    if not rows:
        lines.append("|  |  |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def build_report(work_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = load_batches(work_root)
    issues: list[dict[str, Any]] = []
    for row in rows:
        issues.extend(validate_eval_row(row))
    candidates = candidate_rows(rows, issues)
    report = {
        "schema_version": 1,
        "work_root": str(work_root),
        "row_count": len(rows),
        "candidate_count": len(candidates),
        "blocks": sum(1 for item in issues if item["severity"] == "block"),
        "warnings": sum(1 for item in issues if item["severity"] == "warning"),
        "batch_counts": dict(sorted(Counter(row.batch for row in rows).items())),
        "candidate_status_counts": dict(sorted(Counter(row["candidate_status"] for row in candidates).items())),
        "proposal_counts": dict(sorted(Counter(row[TALENT_QUALITY_PROPOSAL_FIELD] for row in candidates).items())),
        "issues": issues,
    }
    return report, candidates


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_outputs(report: Mapping[str, Any], candidates: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "authority_eval_handoff_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "authority_eval_handoff_report.md").write_text(render_markdown(report), encoding="utf-8")
    (output_dir / "talent_quality_priority_candidates.md").write_text(render_priority_candidates(candidates), encoding="utf-8")
    write_jsonl(output_dir / "talent_quality_candidates.jsonl", candidates)
    for status in ("ready_high_confidence", "ready_review", "needs_review", "deferred", "blocked"):
        write_jsonl(
            output_dir / f"talent_quality_{status}.jsonl",
            (row for row in candidates if row["candidate_status"] == status),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate I5B authority-evaluation handoffs and build talent-quality review candidates.")
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
