from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_CACHE_ROOT = ROOT / "tmp" / "retrieval_v2_claim_cache"
SCHEMA_VERSION = 1

PGSQL_SCHEMA_DRAFT = """
-- retrieval_v2 claim cache draft schema.
-- The first rollout writes filesystem artifacts; these tables reserve the PG-backed hot index shape.

create schema if not exists retrieval_v2;

create table if not exists retrieval_v2.claim_cache (
    claim_key text primary key,
    emperor_name text not null,
    object_name text not null,
    object_type text not null default 'person',
    claim_kind text not null default 'material_claim',
    direction text not null default '',
    action_type text not null default '',
    event_scope text not null default '',
    office_or_domain text not null default '',
    time_context text not null default '',
    outcome text not null default '',
    claim_summary text not null default '',
    confidence numeric,
    fact_payload jsonb not null default '{}'::jsonb,
    first_run_code text not null default '',
    last_run_code text not null default '',
    raw_output_path text not null default '',
    extractor_version text not null default '',
    status text not null default 'active',
    seen_count integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_claim_cache_object_not_blank check (btrim(object_name) <> ''),
    constraint rv2_claim_cache_status_ck check (status in ('active', 'superseded', 'needs_review', 'rejected'))
);

create table if not exists retrieval_v2.claim_evidence (
    evidence_key text primary key,
    claim_key text not null references retrieval_v2.claim_cache(claim_key) on delete cascade,
    slice_hash text not null,
    source_slice_ref text not null default '',
    document_code text not null default '',
    object_name text not null default '',
    span_payload jsonb not null default '{}'::jsonb,
    slice_text_preview text not null default '',
    raw_output_path text not null default '',
    first_run_code text not null default '',
    created_at timestamptz not null default now()
);

create table if not exists retrieval_v2.claim_source_slices (
    slice_hash text primary key,
    object_name text not null default '',
    document_code text not null default '',
    source_slice_ref text not null default '',
    slice_text_preview text not null default '',
    first_run_code text not null default '',
    seen_count integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists retrieval_v2.claim_route_cache (
    route_key text primary key,
    claim_key text not null references retrieval_v2.claim_cache(claim_key) on delete cascade,
    candidate_item_code text not null default '',
    candidate_rule_code text not null default '',
    candidate_lane text not null default '',
    route_status text not null default 'unrouted',
    route_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists rv2_claim_cache_object_idx
on retrieval_v2.claim_cache(emperor_name, object_name, direction);

create index if not exists rv2_claim_cache_action_idx
on retrieval_v2.claim_cache(action_type, event_scope, office_or_domain);

create index if not exists rv2_claim_evidence_claim_idx
on retrieval_v2.claim_evidence(claim_key, slice_hash);

create index if not exists rv2_claim_route_idx
on retrieval_v2.claim_route_cache(candidate_item_code, candidate_rule_code, route_status);
""".strip() + "\n"


class ClaimCacheError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def sha256_text(value: str, *, length: int | None = None) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest if length is None else digest[:length]


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def compact_preview(value: str, *, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ClaimCacheError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(stable_json(row) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def cache_paths(cache_root: Path) -> dict[str, Path]:
    return {
        "claims": cache_root / "claims.jsonl",
        "evidence": cache_root / "claim_evidence.jsonl",
        "slices": cache_root / "source_slices.jsonl",
        "runs": cache_root / "import_runs.jsonl",
        "reports": cache_root / "reports",
    }


def claim_fact(claim: Mapping[str, Any]) -> dict[str, Any]:
    payload = claim.get("fact_payload")
    return dict(payload) if isinstance(payload, Mapping) else {}


def claim_identity_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    fact = claim_fact(claim)
    return {
        "emperor_name": normalized_text(claim.get("emperor_name")),
        "object_name": normalized_text(claim.get("object_name") or fact.get("object")),
        "claim_kind": normalized_text(claim.get("claim_kind") or "material_claim"),
        "direction": normalized_text(claim.get("direction")),
        "action_type": normalized_text(fact.get("action_type")),
        "event_scope": normalized_text(fact.get("event_scope")),
        "office_or_domain": normalized_text(fact.get("office_or_domain")),
        "time_context": normalized_text(fact.get("time_context")),
        "outcome": normalized_text(fact.get("outcome")),
        "cost_or_damage": normalized_text(fact.get("cost_or_damage")),
        "summary": normalized_text(claim.get("claim_summary") or claim.get("summary")),
    }


def claim_key(claim: Mapping[str, Any]) -> str:
    return "CLMK-" + sha256_text(stable_json(claim_identity_payload(claim)), length=20).upper()


def slice_hash_from_row(row: Mapping[str, Any]) -> str:
    payload = {
        "object_name": normalized_text(row.get("object_name")),
        "document_code": normalized_text(row.get("document_code")),
        "text": normalized_text(row.get("text") or row.get("raw_text") or row.get("quote")),
    }
    return "SLH-" + sha256_text(stable_json(payload), length=24).upper()


def evidence_key(claim_cache_key: str, slice_hash: str, span: Mapping[str, Any]) -> str:
    payload = {
        "claim_key": claim_cache_key,
        "slice_hash": slice_hash,
        "span_type": normalized_text(span.get("span_type")),
        "text": normalized_text(span.get("text")),
    }
    return "EVD-" + sha256_text(stable_json(payload), length=24).upper()


def run_code(run_root: Path, summary: Mapping[str, Any]) -> str:
    return "RUN-" + sha256_text(f"{run_root.resolve()}|{summary.get('elapsed_seconds')}|{summary.get('targets')}", length=16).upper()


def load_existing_cache(cache_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    paths = cache_paths(cache_root)
    return {
        "claims": {str(row["claim_key"]): row for row in read_jsonl(paths["claims"])},
        "evidence": {str(row["evidence_key"]): row for row in read_jsonl(paths["evidence"])},
        "slices": {str(row["slice_hash"]): row for row in read_jsonl(paths["slices"])},
        "runs": {str(row["run_code"]): row for row in read_jsonl(paths["runs"])},
    }


def slice_lookup(candidates: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in candidates.get("candidate_slices") or []:
        if not isinstance(row, Mapping):
            continue
        code = str(row.get("slice_code") or "")
        if code:
            result[code] = dict(row)
    return result


def claim_row(
    *,
    claim: Mapping[str, Any],
    cache_key: str,
    run: str,
    raw_output_path: Path,
    extractor_version: str,
) -> dict[str, Any]:
    fact = claim_fact(claim)
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_key": cache_key,
        "emperor_name": str(claim.get("emperor_name") or ""),
        "object_name": str(claim.get("object_name") or fact.get("object") or ""),
        "object_type": str(claim.get("object_type") or "person"),
        "claim_kind": str(claim.get("claim_kind") or "material_claim"),
        "direction": str(claim.get("direction") or ""),
        "action_type": str(fact.get("action_type") or ""),
        "event_scope": str(fact.get("event_scope") or ""),
        "office_or_domain": str(fact.get("office_or_domain") or ""),
        "time_context": str(fact.get("time_context") or ""),
        "outcome": str(fact.get("outcome") or ""),
        "claim_summary": str(claim.get("claim_summary") or claim.get("summary") or ""),
        "confidence": claim.get("confidence"),
        "fact_payload": fact,
        "first_run_code": run,
        "last_run_code": run,
        "raw_output_path": str(raw_output_path),
        "extractor_version": extractor_version,
        "status": "active",
        "seen_count": 1,
    }


def import_run(run_root: Path, cache_root: Path) -> dict[str, Any]:
    summary_path = run_root / "summary.json"
    if not summary_path.exists():
        raise ClaimCacheError(f"summary.json missing under run root: {run_root}")
    summary = read_json(summary_path)
    if not isinstance(summary, Mapping):
        raise ClaimCacheError(f"{summary_path}: expected JSON object")
    run = run_code(run_root, summary)
    extractor_version = str(summary.get("clean_policy", {}).get("judge_mode") or "")
    existing = load_existing_cache(cache_root)
    stats: Counter[str] = Counter()
    by_object: Counter[str] = Counter()
    imported_claim_keys: list[str] = []

    for person in summary.get("people") or []:
        if not isinstance(person, Mapping):
            continue
        files = person.get("files") if isinstance(person.get("files"), Mapping) else {}
        judge_path = Path(str(files.get("final_judge_result") or ""))
        candidates_path = Path(str(files.get("final_candidates") or ""))
        if not judge_path.exists() or not candidates_path.exists():
            stats["missing_person_artifacts"] += 1
            continue
        judge = read_json(judge_path)
        candidates = read_json(candidates_path)
        slices = slice_lookup(candidates if isinstance(candidates, Mapping) else {})
        for claim in judge.get("claims") or []:
            if not isinstance(claim, Mapping):
                continue
            key = claim_key(claim)
            imported_claim_keys.append(key)
            by_object[str(claim.get("object_name") or "")] += 1
            if key in existing["claims"]:
                existing["claims"][key]["seen_count"] = int(existing["claims"][key].get("seen_count") or 1) + 1
                existing["claims"][key]["last_run_code"] = run
                stats["duplicate_claim_count"] += 1
            else:
                existing["claims"][key] = claim_row(
                    claim=claim,
                    cache_key=key,
                    run=run,
                    raw_output_path=judge_path,
                    extractor_version=extractor_version,
                )
                stats["new_claim_count"] += 1
            source_refs = [str(ref) for ref in claim.get("source_slice_refs") or [] if str(ref)]
            spans = claim.get("evidence_spans") if isinstance(claim.get("evidence_spans"), list) else []
            if not source_refs:
                stats["claims_without_source_slice_refs"] += 1
            for source_ref in source_refs:
                slice_row = slices.get(source_ref, {"slice_code": source_ref, "object_name": claim.get("object_name")})
                s_hash = slice_hash_from_row(slice_row)
                if s_hash in existing["slices"]:
                    existing["slices"][s_hash]["seen_count"] = int(existing["slices"][s_hash].get("seen_count") or 1) + 1
                    stats["duplicate_slice_count"] += 1
                else:
                    existing["slices"][s_hash] = {
                        "schema_version": SCHEMA_VERSION,
                        "slice_hash": s_hash,
                        "object_name": str(slice_row.get("object_name") or claim.get("object_name") or ""),
                        "document_code": str(slice_row.get("document_code") or ""),
                        "source_slice_ref": source_ref,
                        "slice_text_preview": compact_preview(str(slice_row.get("text") or "")),
                        "first_run_code": run,
                        "seen_count": 1,
                    }
                    stats["new_slice_count"] += 1
                related_spans = [span for span in spans if isinstance(span, Mapping) and str(span.get("source_slice_ref") or "") == source_ref]
                if not related_spans:
                    related_spans = [{"source_slice_ref": source_ref, "span_type": "slice", "text": ""}]
                for span in related_spans:
                    e_key = evidence_key(key, s_hash, span)
                    if e_key in existing["evidence"]:
                        stats["duplicate_evidence_count"] += 1
                        continue
                    existing["evidence"][e_key] = {
                        "schema_version": SCHEMA_VERSION,
                        "evidence_key": e_key,
                        "claim_key": key,
                        "slice_hash": s_hash,
                        "source_slice_ref": source_ref,
                        "document_code": str(slice_row.get("document_code") or ""),
                        "object_name": str(slice_row.get("object_name") or claim.get("object_name") or ""),
                        "span_payload": dict(span),
                        "slice_text_preview": compact_preview(str(slice_row.get("text") or "")),
                        "raw_output_path": str(judge_path),
                        "first_run_code": run,
                    }
                    stats["new_evidence_count"] += 1

    existing["runs"][run] = {
        "schema_version": SCHEMA_VERSION,
        "run_code": run,
        "run_root": str(run_root),
        "summary_path": str(summary_path),
        "claim_key_count": len(set(imported_claim_keys)),
        "import_stats": dict(stats),
    }
    paths = cache_paths(cache_root)
    write_jsonl(paths["claims"], sorted(existing["claims"].values(), key=lambda row: str(row["claim_key"])))
    write_jsonl(paths["evidence"], sorted(existing["evidence"].values(), key=lambda row: str(row["evidence_key"])))
    write_jsonl(paths["slices"], sorted(existing["slices"].values(), key=lambda row: str(row["slice_hash"])))
    write_jsonl(paths["runs"], sorted(existing["runs"].values(), key=lambda row: str(row["run_code"])))
    report = {
        "schema_version": SCHEMA_VERSION,
        "cache_root": str(cache_root),
        "run_code": run,
        "run_root": str(run_root),
        "stats": dict(stats),
        "claim_count_by_object": dict(sorted(by_object.items())),
        "total_cached_claims": len(existing["claims"]),
        "total_cached_slices": len(existing["slices"]),
        "total_cached_evidence": len(existing["evidence"]),
    }
    write_json(paths["reports"] / f"import_{run}.json", report)
    return report


def plan_candidates(candidates_path: Path, cache_root: Path, uncovered_candidates_path: Path | None = None) -> dict[str, Any]:
    candidates = read_json(candidates_path)
    if not isinstance(candidates, Mapping):
        raise ClaimCacheError(f"{candidates_path}: expected JSON object")
    existing = load_existing_cache(cache_root)
    slice_to_claims: dict[str, set[str]] = defaultdict(set)
    for row in existing["evidence"].values():
        slice_to_claims[str(row.get("slice_hash") or "")].add(str(row.get("claim_key") or ""))
    by_object: dict[str, Counter[str]] = defaultdict(Counter)
    cached_claim_keys: set[str] = set()
    uncovered_slices: list[dict[str, Any]] = []
    for row in candidates.get("candidate_slices") or []:
        if not isinstance(row, Mapping):
            continue
        s_hash = slice_hash_from_row(row)
        object_name = str(row.get("object_name") or "")
        by_object[object_name]["total"] += 1
        claim_keys = slice_to_claims.get(s_hash, set())
        if claim_keys:
            by_object[object_name]["cached"] += 1
            cached_claim_keys.update(claim_keys)
        else:
            by_object[object_name]["uncovered"] += 1
            uncovered_slices.append(dict(row))
    if uncovered_candidates_path is not None:
        filtered = dict(candidates)
        filtered["candidate_slices"] = uncovered_slices
        filtered.setdefault("claim_cache_plan", {})
        filtered["claim_cache_plan"] = {
            "source_candidates": str(candidates_path),
            "cache_root": str(cache_root),
            "policy": "cached slices removed; run claim extraction only for uncovered slices",
        }
        write_json(uncovered_candidates_path, filtered)
    total = sum(row["total"] for row in by_object.values())
    cached = sum(row["cached"] for row in by_object.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "cache_root": str(cache_root),
        "candidates_path": str(candidates_path),
        "candidate_slice_count": total,
        "cached_slice_count": cached,
        "uncovered_slice_count": total - cached,
        "cached_claim_key_count": len(cached_claim_keys),
        "cached_claim_keys": sorted(cached_claim_keys),
        "by_object": {name: dict(counter) for name, counter in sorted(by_object.items())},
        "uncovered_candidates_path": str(uncovered_candidates_path) if uncovered_candidates_path else "",
        "suggested_policy": "skip cached slices unless extractor_version or claim schema changes",
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage retrieval_v2 claim-only extraction cache.")
    sub = parser.add_subparsers(dest="command", required=True)
    emit = sub.add_parser("emit-pg-schema", help="Print PostgreSQL schema draft for the hot claim index.")
    emit.set_defaults(func=run_emit_pg_schema_command)

    import_cmd = sub.add_parser("import-run", help="Import a claim-only clean run into the filesystem claim cache.")
    import_cmd.add_argument("--run-root", type=Path, required=True)
    import_cmd.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    import_cmd.add_argument("--report-json", type=Path)
    import_cmd.set_defaults(func=run_import_command)

    plan = sub.add_parser("plan-candidates", help="Report which candidate slices are already covered by cached claims.")
    plan.add_argument("--candidates", type=Path, required=True)
    plan.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    plan.add_argument("--report-json", type=Path)
    plan.add_argument("--write-uncovered-candidates", type=Path)
    plan.set_defaults(func=run_plan_command)
    return parser


def run_emit_pg_schema_command(_args: argparse.Namespace) -> int:
    sys.stdout.write(PGSQL_SCHEMA_DRAFT)
    return 0


def run_import_command(args: argparse.Namespace) -> int:
    report = import_run(args.run_root, args.cache_root)
    if args.report_json is not None:
        write_json(args.report_json, report)
    sys.stdout.write(pretty_json(report))
    return 0


def run_plan_command(args: argparse.Namespace) -> int:
    report = plan_candidates(args.candidates, args.cache_root, args.write_uncovered_candidates)
    if args.report_json is not None:
        write_json(args.report_json, report)
    sys.stdout.write(pretty_json(report))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
