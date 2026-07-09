from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_object_source_cache as object_cache  # noqa: E402
from scripts.dev import retrieval_v2_object_source_cache_worker as object_worker  # noqa: E402
from scripts.dev import retrieval_v2_summary_lead_discovery as lead_discovery  # noqa: E402
from scripts.dev.retrieval_v2_contracts import unique_strings  # noqa: E402


DEFAULT_OUTPUT_ROOT = ROOT / "tmp" / "retrieval_v2_summary_lead_pilot"
SCHEMA_VERSION = 1


class SummaryLeadPilotError(RuntimeError):
    pass


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def count_by_object(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        name = str(row.get("object_name") or row.get("person_name") or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def source_titles_by_object(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    titles: dict[str, list[str]] = {}
    for row in rows:
        name = str(row.get("person_name") or row.get("object_name") or "").strip()
        title = str(row.get("source_title") or row.get("title") or row.get("wikisource_title") or "").strip()
        if not name or not title:
            continue
        titles.setdefault(name, []).append(title)
    return {name: unique_strings(values) for name, values in sorted(titles.items())}


def lead_terms_by_object(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for row in rows:
        name = str(row.get("person_name") or "").strip()
        if not name:
            continue
        values = row.get("lead_terms") or []
        if isinstance(values, str):
            terms.setdefault(name, []).append(values)
        elif isinstance(values, Sequence) and not isinstance(values, (bytes, str)):
            terms.setdefault(name, []).extend(str(value or "") for value in values)
    return {name: unique_strings(value for value in values if value) for name, values in sorted(terms.items())}


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    paths = report.get("artifacts") if isinstance(report.get("artifacts"), Mapping) else {}
    object_cache_totals = report.get("object_cache_totals") if isinstance(report.get("object_cache_totals"), Mapping) else {}
    claim_plan = report.get("claim_plan") if isinstance(report.get("claim_plan"), Mapping) else {}
    by_object = claim_plan.get("by_object") if isinstance(claim_plan.get("by_object"), Mapping) else {}
    lines = [
        "# retrieval_v2 summary lead pilot report",
        "",
        f"- mode: `{report.get('mode')}`",
        f"- summary_pages_as_evidence: `{str(report.get('summary_pages_as_evidence')).lower()}`",
        f"- judge_invocation_enabled: `{str(report.get('judge_invocation_enabled')).lower()}`",
        f"- write_db: `{str(report.get('write_db')).lower()}`",
        f"- consumption_enabled: `{str(report.get('consumption_enabled')).lower()}`",
        f"- job_count: `{summary.get('job_count', 0)}`",
        f"- lead_count: `{summary.get('lead_count', 0)}`",
        f"- seed_count: `{summary.get('seed_count', 0)}`",
        f"- source_document_hint_count: `{summary.get('source_document_hint_count', 0)}`",
        f"- object_cache_source_documents: `{object_cache_totals.get('source_documents', 0)}`",
        f"- object_cache_mention_slices: `{object_cache_totals.get('mention_slices', 0)}`",
        f"- object_cache_fetch_errors: `{object_cache_totals.get('fetch_errors', 0)}`",
        f"- candidate_slice_count: `{claim_plan.get('candidate_slice_count', 0)}`",
        f"- uncovered_slice_count: `{claim_plan.get('uncovered_slice_count', 0)}`",
        "",
        "## Artifacts",
        "",
    ]
    for key, value in sorted(paths.items()):
        lines.append(f"- {key}: `{value}`")
    if by_object:
        lines.extend(["", "## By Object", "", "| object | total | uncovered | cached |", "| --- | ---: | ---: | ---: |"])
        for name, payload in sorted(by_object.items()):
            if not isinstance(payload, Mapping):
                continue
            lines.append(
                f"| {name} | {payload.get('total', 0)} | {payload.get('uncovered', 0)} | {payload.get('cached', 0)} |"
            )
    return "\n".join(lines) + "\n"


def run_pilot(
    *,
    input_jobs_jsonl: Path,
    output_root: Path,
    cache_dir: Path | None = None,
    claim_cache_root: Path | None = None,
    emperor_name: str = "",
    target_code: str = "",
    rule_code: str = "i5b_item_wide",
    capture_profile: str = "personnel_political_wide",
    pages_per_query: int = 0,
    source_hint_limit: int = 4,
    max_search_names: int = 1,
    search_timeout: int = 5,
    fetch_timeout: int = 8,
    context_chars: int = 220,
    max_slices_per_document: int = 8,
    max_slices_per_person: int = 12,
    max_total_slices: int = 0,
    selection_profile: str = "pilot",
    pilot_object_limit: int = 4,
    pilot_slices_per_object: int = 2,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    object_cache_root = output_root / "object_source_cache"
    claim_cache = claim_cache_root or output_root / "claim_cache"
    candidates_path = output_root / "claim_candidates.json"
    uncovered_candidates_path = output_root / "claim_candidates.uncovered.json"
    leads_path = output_root / "summary_leads.jsonl"
    seeds_path = output_root / "object_source_seeds.jsonl"
    discovery_report_path = output_root / "summary_lead_discovery_report.json"
    report_json_path = output_root / "pilot_report.json"
    report_md_path = output_root / "pilot_report.md"

    jobs = lead_discovery.read_jsonl(input_jobs_jsonl)
    leads, seeds, discovery_report = lead_discovery.discover_jobs(
        jobs,
        timeout=search_timeout,
        lead_terms=lead_discovery.DEFAULT_LEAD_TERMS,
    )
    lead_discovery.write_jsonl(leads_path, leads)
    lead_discovery.write_jsonl(seeds_path, seeds)
    lead_discovery.write_json(discovery_report_path, discovery_report)

    cache_manifest = object_cache.build_cache(
        seeds,
        output_root=object_cache_root,
        cache_dir=cache_dir or output_root / "source_cache",
        pages_per_query=pages_per_query,
        source_hint_limit=source_hint_limit,
        max_search_names=max_search_names,
        search_timeout=search_timeout,
        fetch_timeout=fetch_timeout,
        context_chars=context_chars,
        max_slices_per_document=max_slices_per_document,
        skip_fetch_errors=True,
        request_delay_seconds=0.05,
        max_retries=1,
        retry_backoff_seconds=0.2,
        max_retry_wait_seconds=2.0,
    )
    claim_plan = object_worker.plan_claim_extraction_from_cache(
        cache_root=object_cache_root,
        claim_cache_root=claim_cache,
        output_candidates=candidates_path,
        output_uncovered_candidates=uncovered_candidates_path,
        emperor_name=emperor_name,
        target_code=target_code,
        rule_code=rule_code,
        capture_profile=capture_profile,
        max_slices_per_person=max_slices_per_person,
        max_total_slices=max_total_slices,
        selection_profile=selection_profile,
        pilot_object_limit=pilot_object_limit,
        pilot_slices_per_object=pilot_slices_per_object,
        enqueue_claim_job=False,
    )

    source_documents = object_cache.read_jsonl(object_cache_root / "source_documents.jsonl")
    mention_slices = object_cache.read_jsonl(object_cache_root / "mention_slices.jsonl")
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/dev/retrieval_v2_summary_lead_pilot.py",
        "mode": "summary_lead_to_claim_plan_pilot",
        "summary_pages_as_evidence": False,
        "judge_invocation_enabled": False,
        "write_db": False,
        "consumption_enabled": False,
        "input_jobs_jsonl": str(input_jobs_jsonl),
        "output_root": str(output_root),
        "artifacts": {
            "summary_leads_jsonl": str(leads_path),
            "object_source_seeds_jsonl": str(seeds_path),
            "summary_lead_discovery_report_json": str(discovery_report_path),
            "object_source_cache_root": str(object_cache_root),
            "object_source_cache_manifest": str(object_cache_root / "manifest.json"),
            "claim_candidates_json": str(candidates_path),
            "claim_candidates_uncovered_json": str(uncovered_candidates_path),
            "pilot_report_json": str(report_json_path),
            "pilot_report_md": str(report_md_path),
        },
        "summary": {
            "job_count": discovery_report.get("job_count", len(jobs)),
            "lead_count": discovery_report.get("lead_count", len(leads)),
            "seed_count": discovery_report.get("seed_count", len(seeds)),
            "source_document_hint_count": discovery_report.get("source_document_hint_count", 0),
            "resolvable_source_document_hint_count": discovery_report.get("resolvable_source_document_hint_count", 0),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "lead_terms_by_object": lead_terms_by_object(leads),
        "source_titles_by_object": source_titles_by_object(source_documents),
        "mention_slice_count_by_object": count_by_object(mention_slices),
        "object_cache_totals": cache_manifest.get("totals") or {},
        "claim_plan": {
            "candidate_slice_count": claim_plan.get("candidate_slice_count"),
            "cached_slice_count": claim_plan.get("cached_slice_count"),
            "uncovered_slice_count": claim_plan.get("uncovered_slice_count"),
            "by_object": claim_plan.get("by_object") or {},
            "claim_plan_audit": claim_plan.get("claim_plan_audit") or {},
            "claim_opportunity_estimate": claim_plan.get("claim_opportunity_estimate") or {},
        },
        "execute_effect": "lead discovery -> object source cache -> claim-plan only; no Codex judge, no PG write, no consumption scoring",
    }
    write_json(report_json_path, report)
    write_text(report_md_path, render_markdown(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a lead-only summary page pilot through object source cache and claim-plan.")
    parser.add_argument("--input-jobs-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--claim-cache-root", type=Path)
    parser.add_argument("--emperor-name", default="")
    parser.add_argument("--target-code", default="")
    parser.add_argument("--rule-code", default="i5b_item_wide")
    parser.add_argument("--capture-profile", default="personnel_political_wide")
    parser.add_argument("--pages-per-query", type=int, default=0)
    parser.add_argument("--source-hint-limit", type=int, default=4)
    parser.add_argument("--max-search-names", type=int, default=1)
    parser.add_argument("--search-timeout", type=int, default=5)
    parser.add_argument("--fetch-timeout", type=int, default=8)
    parser.add_argument("--context-chars", type=int, default=220)
    parser.add_argument("--max-slices-per-document", type=int, default=8)
    parser.add_argument("--max-slices-per-person", type=int, default=12)
    parser.add_argument("--max-total-slices", type=int, default=0)
    parser.add_argument("--selection-profile", choices=("all", "pilot"), default="pilot")
    parser.add_argument("--pilot-object-limit", type=int, default=4)
    parser.add_argument("--pilot-slices-per-object", type=int, default=2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_pilot(
        input_jobs_jsonl=args.input_jobs_jsonl,
        output_root=args.output_root,
        cache_dir=args.cache_dir,
        claim_cache_root=args.claim_cache_root,
        emperor_name=args.emperor_name,
        target_code=args.target_code,
        rule_code=args.rule_code,
        capture_profile=args.capture_profile,
        pages_per_query=args.pages_per_query,
        source_hint_limit=args.source_hint_limit,
        max_search_names=args.max_search_names,
        search_timeout=args.search_timeout,
        fetch_timeout=args.fetch_timeout,
        context_chars=args.context_chars,
        max_slices_per_document=args.max_slices_per_document,
        max_slices_per_person=args.max_slices_per_person,
        max_total_slices=args.max_total_slices,
        selection_profile=args.selection_profile,
        pilot_object_limit=args.pilot_object_limit,
        pilot_slices_per_object=args.pilot_slices_per_object,
    )
    print(pretty_json({"ok": True, "output_root": report["output_root"], "summary": report["summary"]}), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SummaryLeadPilotError, lead_discovery.SummaryLeadDiscoveryError, object_cache.ObjectSourceCacheError, object_worker.ObjectSourceCacheWorkerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
