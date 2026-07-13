from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from emperor_v4.adapters.source_cache_wikisource import (
    FetchWikisource,
    WikisourceSourceMaterialProvider,
)
from emperor_v4.application.source_cache_service import ensure_source_cache
from emperor_v4.persistence.source_cache import InMemorySourceCacheRepository
from emperor_v4.runtime.source_cache import load_source_cache_request


def _identity_map(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows}


def compare_source_cache_responses(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_documents = _identity_map(baseline.get("documents") or [], "document_cache_id")
    candidate_documents = _identity_map(candidate.get("documents") or [], "document_cache_id")
    baseline_passages = _identity_map(baseline.get("passages") or [], "passage_id")
    candidate_passages = _identity_map(candidate.get("passages") or [], "passage_id")
    document_refs_match = set(baseline_documents) == set(candidate_documents)
    passage_refs_match = set(baseline_passages) == set(candidate_passages)
    document_content_match = document_refs_match and all(
        baseline_documents[ref]["content_hash"]
        == candidate_documents[ref]["content_hash"]
        for ref in baseline_documents
    )
    passage_content_match = passage_refs_match and all(
        (
            baseline_passages[ref]["content_hash"],
            baseline_passages[ref]["raw_text"],
            baseline_passages[ref]["span_start"],
            baseline_passages[ref]["span_end"],
        )
        == (
            candidate_passages[ref]["content_hash"],
            candidate_passages[ref]["raw_text"],
            candidate_passages[ref]["span_start"],
            candidate_passages[ref]["span_end"],
        )
        for ref in baseline_passages
    )
    return {
        "document_refs_match": document_refs_match,
        "document_content_hashes_match": document_content_match,
        "passage_refs_match": passage_refs_match,
        "passage_content_and_spans_match": passage_content_match,
        "matched": all(
            (
                document_refs_match,
                document_content_match,
                passage_refs_match,
                passage_content_match,
            )
        ),
    }


def run_wikisource_shadow(
    *,
    request_path: Path,
    plan_path: Path,
    baseline_report_path: Path,
    service_release_sha: str,
    fetch: FetchWikisource | None = None,
) -> dict[str, Any]:
    request = load_source_cache_request(request_path)
    provider = WikisourceSourceMaterialProvider(
        plan_path=plan_path,
        **({"fetch": fetch} if fetch is not None else {}),
    )
    run = ensure_source_cache(
        request,
        provider=provider,
        repository=InMemorySourceCacheRepository(),
        service_release_sha=service_release_sha,
    )
    baseline_payload = json.loads(
        baseline_report_path.read_text(encoding="utf-8")
    )
    baseline = baseline_payload.get("response") or baseline_payload
    comparison = compare_source_cache_responses(baseline, dict(run.response))
    return {
        "schema_version": 1,
        "status": (
            "source_cache_wikisource_shadow_match"
            if comparison["matched"]
            else "source_cache_wikisource_shadow_mismatch"
        ),
        "comparison": comparison,
        "candidate_response": run.response,
        "runtime_audit": {
            "provider_call_count": run.provider_call_count,
            "network_request_count": run.network_request_count,
            "repository_write_count": run.repository_write_count,
            "database_write_count": 0,
            "model_call_count": 0,
            "formal_acceptance_performed": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V4 Source Cache Wikisource shadow")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_wikisource_shadow(
        request_path=args.request,
        plan_path=args.plan,
        baseline_report_path=args.baseline_report,
        service_release_sha=args.service_release_sha,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0 if report["status"].endswith("_match") else 1


if __name__ == "__main__":
    raise SystemExit(main())
