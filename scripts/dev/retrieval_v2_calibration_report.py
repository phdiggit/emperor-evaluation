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

from scripts.dev import retrieval_v2_claim_cache as claim_cache  # noqa: E402
from scripts.dev import retrieval_v2_quality_gate as quality_gate  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def pretty_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def int_value(value: Any) -> int:
    return int(number(value))


def usage_total(usage: Mapping[str, Any], key: str) -> int:
    return int_value(usage.get(key))


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def resolve_path(value: Any, *, run_root: Path) -> Path | None:
    if not text(value):
        return None
    path = Path(text(value))
    return path if path.is_absolute() else run_root / path


def latest_round(person: Mapping[str, Any]) -> Mapping[str, Any]:
    rounds = [row for row in person.get("rounds") or [] if isinstance(row, Mapping)]
    return rounds[-1] if rounds else {}


def object_claim_counts(judge_path: Path | None) -> dict[str, int]:
    if judge_path is None or not judge_path.exists():
        return {}
    judge = load_json(judge_path)
    counts: Counter[str] = Counter()
    for claim in judge.get("claims") or []:
        if isinstance(claim, Mapping) and text(claim.get("object_name")):
            counts[text(claim.get("object_name"))] += 1
    return dict(sorted(counts.items()))


def compact_cache_plan(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        return {}
    candidate_slice_count = int_value(plan.get("candidate_slice_count"))
    cached_slice_count = int_value(plan.get("cached_slice_count"))
    uncovered_slice_count = int_value(plan.get("uncovered_slice_count"))
    return {
        "cache_root": plan.get("cache_root") or "",
        "candidate_slice_count": candidate_slice_count,
        "cached_slice_count": cached_slice_count,
        "uncovered_slice_count": uncovered_slice_count,
        "cached_claim_key_count": int_value(plan.get("cached_claim_key_count")),
        "hit_ratio": ratio(cached_slice_count, candidate_slice_count),
        "by_object": plan.get("by_object") or {},
        "candidates_path": plan.get("candidates_path") or "",
        "uncovered_candidates_path": plan.get("uncovered_candidates_path") or "",
    }


def summarize_people(summary: Mapping[str, Any], *, run_root: Path) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for person in summary.get("people") or []:
        if not isinstance(person, Mapping):
            continue
        files = person.get("files") if isinstance(person.get("files"), Mapping) else {}
        judge_path = resolve_path(files.get("final_judge_result"), run_root=run_root)
        round_summary = latest_round(person)
        cache_plan = compact_cache_plan(round_summary.get("claim_cache_plan"))
        usage = person.get("judge_usage") if isinstance(person.get("judge_usage"), Mapping) else {}
        people.append(
            {
                "name": person.get("name") or "",
                "target_code": person.get("target_code") or "",
                "rule_code": person.get("rule_code") or "",
                "status": person.get("judge_status"),
                "candidate_slices": int_value(person.get("candidate_slices")),
                "claim_count": int_value(person.get("claim_count")),
                "judge_gap_count": int_value(person.get("judge_coverage_gap_count")),
                "candidate_gap_count": int_value(person.get("candidate_coverage_gap_count")),
                "judge_shard_count": int_value(person.get("judge_shard_count")),
                "judge_elapsed_seconds": number(person.get("judge_elapsed_seconds")),
                "object_seed_count": int_value(person.get("object_seed_count")),
                "source_document_count": int_value(person.get("source_document_count")),
                "objects_without_slices": person.get("objects_without_slices") or [],
                "usage": {
                    "input_tokens": usage_total(usage, "input_tokens"),
                    "cached_input_tokens": usage_total(usage, "cached_input_tokens"),
                    "output_tokens": usage_total(usage, "output_tokens"),
                    "reasoning_output_tokens": usage_total(usage, "reasoning_output_tokens"),
                },
                "claim_cache": cache_plan,
                "claim_count_by_object": object_claim_counts(judge_path),
            }
        )
    return people


def event_summary(run_root: Path) -> dict[str, Any]:
    events = read_jsonl(run_root / "run_events.jsonl")
    counts = Counter(text(row.get("event")) for row in events if text(row.get("event")))
    return {
        "event_count": len(events),
        "event_counts": dict(sorted(counts.items())),
        "last_event": events[-1] if events else {},
    }


def claim_cache_inventory_for_report(
    *,
    cache_root: Path | None,
    candidates_path: Path | None,
) -> dict[str, Any] | None:
    if cache_root is None:
        return None
    inventory = claim_cache.cache_inventory(cache_root, candidates_path, sample_limit=0)
    return {
        "cache_root": inventory.get("cache_root"),
        "totals": inventory.get("totals") or {},
        "candidate_cached_claim_count": inventory.get("candidate_cached_claim_count"),
        "candidate_plan": inventory.get("candidate_plan") or {},
        "by_object": inventory.get("by_object") or {},
    }


def default_candidates_path(people: Sequence[Mapping[str, Any]], *, run_root: Path) -> Path | None:
    for person in people:
        plan = person.get("claim_cache") if isinstance(person.get("claim_cache"), Mapping) else {}
        path = resolve_path(plan.get("candidates_path"), run_root=run_root)
        if path is not None and path.exists():
            return path
    return None


def build_alerts(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    quality = report.get("quality_gate") if isinstance(report.get("quality_gate"), Mapping) else {}
    for block in quality.get("blocks") or []:
        if isinstance(block, Mapping):
            alerts.append({"severity": "block", "code": block.get("code") or "quality_block", "detail": block})
    for warning in quality.get("warnings") or []:
        if isinstance(warning, Mapping):
            alerts.append({"severity": "warning", "code": warning.get("code") or "quality_warning", "detail": warning})
    for person in report.get("people") or []:
        if not isinstance(person, Mapping):
            continue
        name = person.get("name") or ""
        if person.get("status") != "succeeded":
            alerts.append({"severity": "warning", "code": "judge_not_succeeded", "person": name, "status": person.get("status")})
        if int_value(person.get("judge_shard_count")) > 0:
            alerts.append({"severity": "info", "code": "judge_ran", "person": name, "judge_shard_count": person.get("judge_shard_count")})
        if int_value(person.get("judge_gap_count")) > 0:
            alerts.append({"severity": "warning", "code": "judge_gaps_present", "person": name, "judge_gap_count": person.get("judge_gap_count")})
        cache_plan = person.get("claim_cache") if isinstance(person.get("claim_cache"), Mapping) else {}
        if int_value(cache_plan.get("uncovered_slice_count")) > 0:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "claim_cache_uncovered_slices",
                    "person": name,
                    "uncovered_slice_count": cache_plan.get("uncovered_slice_count"),
                }
            )
    return alerts


def build_report(
    *,
    run_root: Path,
    baseline_run_root: Path | None = None,
    claim_cache_root: Path | None = None,
    candidates_path: Path | None = None,
) -> dict[str, Any]:
    summary = load_json(run_root / "summary.json")
    people = summarize_people(summary, run_root=run_root)
    candidates = candidates_path or default_candidates_path(people, run_root=run_root)
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    usage = totals.get("usage") if isinstance(totals.get("usage"), Mapping) else {}
    report: dict[str, Any] = {
        "ok": True,
        "report_type": "retrieval_v2_calibration_report",
        "run_root": str(run_root),
        "baseline_run_root": str(baseline_run_root) if baseline_run_root else "",
        "summary_path": str(run_root / "summary.json"),
        "clean_policy": summary.get("clean_policy") or {},
        "runtime_paths": summary.get("runtime_paths") or {},
        "timing": {
            "elapsed_seconds": number(summary.get("elapsed_seconds")),
            "pipeline_elapsed_seconds": number(summary.get("pipeline_elapsed_seconds")),
            "cli_elapsed_seconds": number(summary.get("cli_elapsed_seconds")),
            "total_elapsed_seconds": number(summary.get("total_elapsed_seconds")),
        },
        "totals": {
            "candidate_slices": int_value(totals.get("candidate_slices")),
            "claim_count": int_value(totals.get("claim_count")),
            "candidate_coverage_gap_count": int_value(totals.get("candidate_coverage_gap_count")),
            "judge_coverage_gap_count": int_value(totals.get("judge_coverage_gap_count")),
            "usage": {
                "input_tokens": usage_total(usage, "input_tokens"),
                "cached_input_tokens": usage_total(usage, "cached_input_tokens"),
                "output_tokens": usage_total(usage, "output_tokens"),
                "reasoning_output_tokens": usage_total(usage, "reasoning_output_tokens"),
            },
        },
        "people": people,
        "events": event_summary(run_root),
        "claim_cache_inventory": claim_cache_inventory_for_report(cache_root=claim_cache_root, candidates_path=candidates),
    }
    if baseline_run_root is not None:
        report["quality_gate"] = quality_gate.compare_runs(
            baseline_run_root=baseline_run_root,
            candidate_run_root=run_root,
        )
    else:
        report["quality_gate"] = None
    report["alerts"] = build_alerts(report)
    return report


def markdown_table_row(values: Sequence[Any]) -> str:
    return "| " + " | ".join(str(value) for value in values) + " |"


def render_markdown(report: Mapping[str, Any]) -> str:
    lines: list[str] = [
        "# retrieval_v2 calibration report",
        "",
        f"- run_root: `{report.get('run_root')}`",
        f"- baseline_run_root: `{report.get('baseline_run_root') or ''}`",
    ]
    timing = report.get("timing") if isinstance(report.get("timing"), Mapping) else {}
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    usage = totals.get("usage") if isinstance(totals.get("usage"), Mapping) else {}
    lines += [
        f"- total_elapsed_seconds: `{timing.get('total_elapsed_seconds')}`",
        f"- candidate_slices: `{totals.get('candidate_slices')}`",
        f"- claim_count: `{totals.get('claim_count')}`",
        f"- judge_coverage_gap_count: `{totals.get('judge_coverage_gap_count')}`",
        f"- usage_input/output/reasoning: `{usage.get('input_tokens')}` / `{usage.get('output_tokens')}` / `{usage.get('reasoning_output_tokens')}`",
        "",
        "## People",
        "",
        markdown_table_row(["person", "status", "claims", "slices", "cache hit", "uncovered", "judge shards", "judge sec"]),
        markdown_table_row(["---", "---", "---:", "---:", "---:", "---:", "---:", "---:"]),
    ]
    for person in report.get("people") or []:
        if not isinstance(person, Mapping):
            continue
        cache_plan = person.get("claim_cache") if isinstance(person.get("claim_cache"), Mapping) else {}
        lines.append(
            markdown_table_row(
                [
                    person.get("name") or "",
                    person.get("status") or "",
                    person.get("claim_count") or 0,
                    person.get("candidate_slices") or 0,
                    cache_plan.get("hit_ratio"),
                    cache_plan.get("uncovered_slice_count") or 0,
                    person.get("judge_shard_count") or 0,
                    person.get("judge_elapsed_seconds") or 0,
                ]
            )
        )
    lines += ["", "## Alerts", ""]
    alerts = [row for row in report.get("alerts") or [] if isinstance(row, Mapping)]
    if not alerts:
        lines.append("- none")
    else:
        for alert in alerts:
            lines.append(f"- `{alert.get('severity')}` `{alert.get('code')}` {alert.get('person') or ''}".rstrip())
    quality = report.get("quality_gate") if isinstance(report.get("quality_gate"), Mapping) else None
    if quality is not None:
        lines += [
            "",
            "## Quality Gate",
            "",
            f"- ok: `{quality.get('ok')}`",
            f"- blocks: `{len(quality.get('blocks') or [])}`",
            f"- warnings: `{len(quality.get('warnings') or [])}`",
        ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize retrieval_v2 calibration run cost, cache hits, and quality deltas.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--baseline-run-root", type=Path)
    parser.add_argument("--claim-cache-root", type=Path)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(
        run_root=args.run_root,
        baseline_run_root=args.baseline_run_root,
        claim_cache_root=args.claim_cache_root,
        candidates_path=args.candidates,
    )
    if args.output_json:
        write_json(args.output_json, report)
    if args.output_md:
        write_text(args.output_md, render_markdown(report))
    if not args.output_json and not args.output_md:
        sys.stdout.write(pretty_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
