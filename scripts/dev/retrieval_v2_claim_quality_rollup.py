from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_import_plan import write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402


HARD_GATE_ISSUES = {
    "claim_evidence_object_mismatch",
    "claim_source_object_mismatch",
    "ineligible_slice_claim_evidence",
}
REVIEW_ONLY_ISSUES = {
    "wrong_person_section",
    "weak_single_mention",
    "action_type_authorization_anchor_missing",
    "negative_authorization_disposition_only_review",
}
CANONICALIZATION_ISSUES = {
    "near_duplicate_claim_group",
    "mixed_claim_grain_group",
}


class ClaimQualityRollupError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ClaimQualityRollupError(f"{path}: expected JSON object")
    return payload


def parse_audit_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        path = Path(value)
        return path.stem, path
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ClaimQualityRollupError(f"empty audit label in {value!r}")
    return label, Path(raw_path)


def issue_counts(report: Mapping[str, Any]) -> dict[str, int]:
    counts = report.get("issue_counts")
    if isinstance(counts, Mapping):
        return {text(key): int(value or 0) for key, value in counts.items() if text(key)}
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    counter: Counter[str] = Counter()
    for row in findings:
        if isinstance(row, Mapping):
            code = text(row.get("issue_code") or row.get("finding_type") or row.get("code"))
            if code:
                counter[code] += 1
    return dict(counter)


def sample_summary(label: str, path: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    opportunity = report.get("claim_opportunity_estimate") if isinstance(report.get("claim_opportunity_estimate"), Mapping) else {}
    opportunity_totals = opportunity.get("totals") if isinstance(opportunity.get("totals"), Mapping) else {}
    counts = issue_counts(report)
    return {
        "label": label,
        "path": str(path),
        "claims": int(totals.get("active_claims") or totals.get("claims") or 0),
        "evidence": int(totals.get("active_evidence") or totals.get("evidence") or 0),
        "findings": int(totals.get("findings") or sum(counts.values())),
        "issue_counts": counts,
        "suggested_claim_budget": int(opportunity_totals.get("suggested_claim_budget") or 0),
        "actual_claim_count": int(opportunity_totals.get("actual_claim_count") or 0),
        "undercoverage_objects": int(opportunity_totals.get("undercoverage_objects") or 0),
    }


def policy_decisions(samples: Sequence[Mapping[str, Any]], aggregate_issue_counts: Mapping[str, int]) -> list[dict[str, Any]]:
    sample_count = len(samples)
    decisions: list[dict[str, Any]] = []
    hard_gate_total = sum(int(aggregate_issue_counts.get(code) or 0) for code in HARD_GATE_ISSUES)
    decisions.append(
        {
            "policy_code": "evidence_object_integrity_gate",
            "decision": "keep_hard_gate",
            "basis": f"{sample_count} samples; hard gate issue total={hard_gate_total}",
            "action": "continue rejecting cross-object or ineligible evidence during claim-cache import",
        }
    )
    for code in sorted(CANONICALIZATION_ISSUES):
        count = int(aggregate_issue_counts.get(code) or 0)
        decisions.append(
            {
                "policy_code": code,
                "decision": "audit_only" if count == 0 else "candidate_auto_canonicalize_after_manual_review",
                "basis": f"{sample_count} samples; {code}={count}",
                "action": (
                    "keep audit signal and do not merge automatically while stable samples show zero groups"
                    if count == 0
                    else "prepare deterministic canonicalization worklist; require one more reviewed sample before destructive merge"
                ),
            }
        )
    for code in sorted(REVIEW_ONLY_ISSUES):
        count = int(aggregate_issue_counts.get(code) or 0)
        decisions.append(
            {
                "policy_code": code,
                "decision": "review_only",
                "basis": f"{sample_count} samples; {code}={count}",
                "action": "do not hard reject; surface in audit and keep manual patch/review route",
            }
        )
    return decisions


def build_rollup(audits: Sequence[tuple[str, Path]]) -> dict[str, Any]:
    samples = [sample_summary(label, path, read_json(path)) for label, path in audits]
    if not samples:
        raise ClaimQualityRollupError("at least one --audit is required")
    aggregate_counts: Counter[str] = Counter()
    for sample in samples:
        aggregate_counts.update(sample["issue_counts"])
    totals = {
        "sample_count": len(samples),
        "claims": sum(int(sample["claims"]) for sample in samples),
        "evidence": sum(int(sample["evidence"]) for sample in samples),
        "findings": sum(int(sample["findings"]) for sample in samples),
        "undercoverage_objects": sum(int(sample["undercoverage_objects"]) for sample in samples),
    }
    return {
        "generated_by": "scripts/dev/retrieval_v2_claim_quality_rollup.py",
        "ok": True,
        "totals": totals,
        "aggregate_issue_counts": dict(sorted(aggregate_counts.items())),
        "samples": samples,
        "policy_decisions": policy_decisions(samples, aggregate_counts),
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v2 claim quality rollup",
        "",
        f"- sample_count: `{totals.get('sample_count', 0)}`",
        f"- claims: `{totals.get('claims', 0)}`",
        f"- evidence: `{totals.get('evidence', 0)}`",
        f"- findings: `{totals.get('findings', 0)}`",
        f"- undercoverage_objects: `{totals.get('undercoverage_objects', 0)}`",
        "",
        "## Samples",
        "",
        "| sample | claims | evidence | findings | undercoverage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for sample in payload.get("samples") or []:
        lines.append(
            f"| {sample.get('label')} | {sample.get('claims')} | {sample.get('evidence')} | "
            f"{sample.get('findings')} | {sample.get('undercoverage_objects')} |"
        )
    lines.extend(["", "## Aggregate Issues", "", "| issue | count |", "| --- | ---: |"])
    for issue, count in (payload.get("aggregate_issue_counts") or {}).items():
        lines.append(f"| `{issue}` | {count} |")
    lines.extend(["", "## Policy Decisions", "", "| policy | decision | action |", "| --- | --- | --- |"])
    for row in payload.get("policy_decisions") or []:
        lines.append(f"| `{row.get('policy_code')}` | `{row.get('decision')}` | {row.get('action')} |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Roll up multiple retrieval_v2 claim audit reports and policy decisions.")
    parser.add_argument("--audit", action="append", default=[], help="Audit report path, or label=path. Repeatable.")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_rollup([parse_audit_arg(value) for value in args.audit])
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
