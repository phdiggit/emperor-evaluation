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
PGSQL_SCHEMA_PATH = ROOT / "db" / "migrations" / "20260708_retrieval_v2_claim_cache.sql"

PGSQL_SCHEMA_DRAFT = PGSQL_SCHEMA_PATH.read_text(encoding="utf-8")


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


def claim_object_name(claim: Mapping[str, Any]) -> str:
    fact = claim_fact(claim)
    return str(claim.get("object_name") or fact.get("object") or "")


def filter_claim_source_refs(
    claim: Mapping[str, Any],
    slices: Mapping[str, Mapping[str, Any]],
    stats: Counter[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    source_refs = [str(ref) for ref in claim.get("source_slice_refs") or [] if str(ref)]
    if not source_refs:
        return dict(claim), []

    target_object = claim_object_name(claim)
    normalized_target = normalized_text(target_object)
    valid_refs: list[str] = []
    for source_ref in source_refs:
        slice_row = slices.get(source_ref)
        if not slice_row:
            stats["missing_source_ref_dropped"] += 1
            continue
        if normalized_text(slice_row.get("object_name")) != normalized_target:
            stats["cross_object_source_ref_dropped"] += 1
            continue
        valid_refs.append(source_ref)

    if not valid_refs:
        stats["claims_skipped_cross_object_only"] += 1
        return None, []

    valid_ref_set = set(valid_refs)
    sanitized = dict(claim)
    sanitized["source_slice_refs"] = valid_refs
    fact = claim_fact(sanitized)
    source_span_refs = [str(ref) for ref in fact.get("source_span_refs") or [] if str(ref) in valid_ref_set]
    if source_span_refs or "source_span_refs" in fact:
        fact["source_span_refs"] = source_span_refs
    if target_object and not str(sanitized.get("object_name") or ""):
        sanitized["object_name"] = target_object
    if target_object and not str(fact.get("object") or ""):
        fact["object"] = target_object
    if fact:
        sanitized["fact_payload"] = fact

    spans = sanitized.get("evidence_spans") if isinstance(sanitized.get("evidence_spans"), list) else []
    sanitized["evidence_spans"] = [
        dict(span)
        for span in spans
        if isinstance(span, Mapping) and str(span.get("source_slice_ref") or "") in valid_ref_set
    ]
    return sanitized, valid_refs


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
    clean_policy = summary.get("clean_policy") if isinstance(summary.get("clean_policy"), Mapping) else {}
    extractor_version = str(clean_policy.get("extractor_version") or clean_policy.get("judge_mode") or "")
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
            sanitized_claim, source_refs = filter_claim_source_refs(claim, slices, stats)
            if sanitized_claim is None:
                continue
            key = str(sanitized_claim.get("cached_claim_key") or "") or claim_key(sanitized_claim)
            imported_claim_keys.append(key)
            by_object[claim_object_name(sanitized_claim)] += 1
            if key in existing["claims"]:
                existing["claims"][key]["seen_count"] = int(existing["claims"][key].get("seen_count") or 1) + 1
                existing["claims"][key]["last_run_code"] = run
                stats["duplicate_claim_count"] += 1
            else:
                existing["claims"][key] = claim_row(
                    claim=sanitized_claim,
                    cache_key=key,
                    run=run,
                    raw_output_path=judge_path,
                    extractor_version=extractor_version,
                )
                stats["new_claim_count"] += 1
            spans = sanitized_claim.get("evidence_spans") if isinstance(sanitized_claim.get("evidence_spans"), list) else []
            if not source_refs:
                stats["claims_without_source_slice_refs"] += 1
            for source_ref in source_refs:
                slice_row = slices.get(source_ref, {"slice_code": source_ref, "object_name": sanitized_claim.get("object_name")})
                s_hash = slice_hash_from_row(slice_row)
                if s_hash in existing["slices"]:
                    existing["slices"][s_hash]["seen_count"] = int(existing["slices"][s_hash].get("seen_count") or 1) + 1
                    stats["duplicate_slice_count"] += 1
                else:
                    existing["slices"][s_hash] = {
                        "schema_version": SCHEMA_VERSION,
                        "slice_hash": s_hash,
                        "object_name": str(slice_row.get("object_name") or sanitized_claim.get("object_name") or ""),
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
                        "object_name": str(slice_row.get("object_name") or sanitized_claim.get("object_name") or ""),
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


def plan_candidates(
    candidates_path: Path,
    cache_root: Path,
    uncovered_candidates_path: Path | None = None,
    *,
    required_extractor_version: str = "",
) -> dict[str, Any]:
    candidates = read_json(candidates_path)
    if not isinstance(candidates, Mapping):
        raise ClaimCacheError(f"{candidates_path}: expected JSON object")
    existing = load_existing_cache(cache_root)
    slice_to_claims: dict[str, set[str]] = defaultdict(set)
    for row in existing["evidence"].values():
        claim_key_value = str(row.get("claim_key") or "")
        claim = existing["claims"].get(claim_key_value)
        if required_extractor_version and str((claim or {}).get("extractor_version") or "") != required_extractor_version:
            continue
        slice_to_claims[str(row.get("slice_hash") or "")].add(claim_key_value)
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
            "required_extractor_version": required_extractor_version,
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
        "required_extractor_version": required_extractor_version,
        "by_object": {name: dict(counter) for name, counter in sorted(by_object.items())},
        "uncovered_candidates_path": str(uncovered_candidates_path) if uncovered_candidates_path else "",
        "suggested_policy": "skip cached slices unless extractor_version or claim schema changes",
    }
    return report


def compact_plan_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "cache_root": report.get("cache_root"),
        "candidates_path": report.get("candidates_path"),
        "candidate_slice_count": report.get("candidate_slice_count"),
        "cached_slice_count": report.get("cached_slice_count"),
        "uncovered_slice_count": report.get("uncovered_slice_count"),
        "cached_claim_key_count": report.get("cached_claim_key_count"),
        "required_extractor_version": report.get("required_extractor_version"),
        "by_object": report.get("by_object") or {},
        "suggested_policy": report.get("suggested_policy"),
    }


def cached_claims_for_candidates(candidates: Mapping[str, Any], cache_root: Path) -> dict[str, Any]:
    existing = load_existing_cache(cache_root)
    evidence_by_slice: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for evidence in existing["evidence"].values():
        evidence_by_slice[str(evidence.get("slice_hash") or "")].append(evidence)

    claims_by_key: dict[str, dict[str, Any]] = {}
    by_object: dict[str, Counter[str]] = defaultdict(Counter)
    matched_slice_count = 0
    for source_slice in candidates.get("candidate_slices") or []:
        if not isinstance(source_slice, Mapping):
            continue
        s_hash = slice_hash_from_row(source_slice)
        evidence_rows = evidence_by_slice.get(s_hash) or []
        if not evidence_rows:
            continue
        matched_slice_count += 1
        current_ref = str(source_slice.get("slice_code") or "")
        for evidence in evidence_rows:
            key = str(evidence.get("claim_key") or "")
            claim = existing["claims"].get(key)
            if not key or not claim:
                continue
            object_name = str(claim.get("object_name") or evidence.get("object_name") or "")
            by_object[object_name]["claim_evidence_hits"] += 1
            entry = claims_by_key.setdefault(
                key,
                {
                    "claim": claim,
                    "source_slice_refs": set(),
                    "evidence_spans": [],
                },
            )
            if current_ref:
                entry["source_slice_refs"].add(current_ref)
            span = dict(evidence.get("span_payload") or {})
            if current_ref:
                span["source_slice_ref"] = current_ref
            if span:
                entry["evidence_spans"].append(span)

    claims: list[dict[str, Any]] = []
    for key, entry in sorted(claims_by_key.items()):
        row = entry["claim"]
        fact = dict(row.get("fact_payload") or {})
        source_refs = sorted(entry["source_slice_refs"])
        if source_refs:
            fact["source_span_refs"] = source_refs
        claim = {
            "claim_code": key,
            "cached_claim_key": key,
            "cache_status": "cached",
            "emperor_name": row.get("emperor_name") or "",
            "object_name": row.get("object_name") or "",
            "object_type": row.get("object_type") or "person",
            "claim_kind": row.get("claim_kind") or "material_claim",
            "claim_summary": row.get("claim_summary") or "",
            "direction": row.get("direction") or "",
            "confidence": row.get("confidence"),
            "source_slice_refs": source_refs,
            "fact_payload": fact,
            "evidence_spans": entry["evidence_spans"],
        }
        claims.append(claim)

    return {
        "schema_version": SCHEMA_VERSION,
        "cache_root": str(cache_root),
        "matched_slice_count": matched_slice_count,
        "claim_count": len(claims),
        "claims": claims,
        "by_object": {name: dict(counter) for name, counter in sorted(by_object.items())},
    }


def merge_cached_claims(judge_payload: Mapping[str, Any], cached_report: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(judge_payload)
    live_claims = [dict(row) for row in result.get("claims") or [] if isinstance(row, Mapping)]
    cached_claims = [dict(row) for row in cached_report.get("claims") or [] if isinstance(row, Mapping)]
    live_keys = {str(row.get("cached_claim_key") or claim_key(row)) for row in live_claims}
    merged_cached = [row for row in cached_claims if str(row.get("cached_claim_key") or "") not in live_keys]
    claims = merged_cached + live_claims
    result["claims"] = claims
    coverage = dict(result.get("coverage") or {})
    if claims:
        object_names = sorted({str(row.get("object_name") or "") for row in claims if str(row.get("object_name") or "")})
        coverage["checked_objects"] = sorted(set(coverage.get("checked_objects") or []) | set(object_names))
        coverage["positive_claim_count"] = sum(1 for row in claims if str(row.get("direction") or "") == "positive")
        coverage["negative_claim_count"] = sum(1 for row in claims if str(row.get("direction") or "") == "negative")
    result["coverage"] = coverage
    result["_claim_cache_hydrated"] = {
        "cache_root": cached_report.get("cache_root"),
        "matched_slice_count": cached_report.get("matched_slice_count"),
        "cached_claim_count": len(cached_claims),
        "merged_cached_claim_count": len(merged_cached),
        "final_claim_count": len(claims),
    }
    return result


def cache_inventory(cache_root: Path, candidates_path: Path | None = None, *, sample_limit: int = 3) -> dict[str, Any]:
    existing = load_existing_cache(cache_root)
    by_object: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "claim_count": 0,
            "slice_count": 0,
            "evidence_count": 0,
            "direction_counts": Counter(),
            "action_type_counts": Counter(),
            "sample_claims": [],
        }
    )
    for claim in existing["claims"].values():
        object_name = str(claim.get("object_name") or "")
        row = by_object[object_name]
        row["claim_count"] += 1
        direction = str(claim.get("direction") or "")
        action_type = str(claim.get("action_type") or "")
        if direction:
            row["direction_counts"][direction] += 1
        if action_type:
            row["action_type_counts"][action_type] += 1
        if len(row["sample_claims"]) < sample_limit:
            row["sample_claims"].append(
                {
                    "claim_key": claim.get("claim_key"),
                    "direction": direction,
                    "action_type": action_type,
                    "summary": claim.get("claim_summary") or "",
                }
            )
    for source_slice in existing["slices"].values():
        by_object[str(source_slice.get("object_name") or "")]["slice_count"] += 1
    for evidence in existing["evidence"].values():
        by_object[str(evidence.get("object_name") or "")]["evidence_count"] += 1

    objects: dict[str, dict[str, Any]] = {}
    for object_name, row in sorted(by_object.items()):
        objects[object_name] = {
            "claim_count": row["claim_count"],
            "slice_count": row["slice_count"],
            "evidence_count": row["evidence_count"],
            "direction_counts": dict(sorted(row["direction_counts"].items())),
            "action_type_counts": dict(sorted(row["action_type_counts"].items())),
            "sample_claims": row["sample_claims"],
        }

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cache_root": str(cache_root),
        "totals": {
            "claim_count": len(existing["claims"]),
            "slice_count": len(existing["slices"]),
            "evidence_count": len(existing["evidence"]),
            "run_count": len(existing["runs"]),
            "object_count": len([name for name in objects if name]),
        },
        "by_object": objects,
    }
    if candidates_path is not None:
        candidates = read_json(candidates_path)
        if not isinstance(candidates, Mapping):
            raise ClaimCacheError(f"{candidates_path}: expected JSON object")
        report["candidate_plan"] = compact_plan_report(plan_candidates(candidates_path, cache_root))
        cached_report = cached_claims_for_candidates(candidates, cache_root)
        report["candidate_cached_claim_count"] = cached_report["claim_count"]
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
    plan.add_argument("--required-extractor-version", default="")
    plan.set_defaults(func=run_plan_command)

    inventory = sub.add_parser("inventory", help="Summarize filesystem claim cache coverage and optional candidate hits.")
    inventory.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    inventory.add_argument("--candidates", type=Path)
    inventory.add_argument("--report-json", type=Path)
    inventory.add_argument("--sample-limit", type=int, default=3)
    inventory.set_defaults(func=run_inventory_command)
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
    report = plan_candidates(
        args.candidates,
        args.cache_root,
        args.write_uncovered_candidates,
        required_extractor_version=args.required_extractor_version,
    )
    if args.report_json is not None:
        write_json(args.report_json, report)
    sys.stdout.write(pretty_json(report))
    return 0


def run_inventory_command(args: argparse.Namespace) -> int:
    report = cache_inventory(args.cache_root, args.candidates, sample_limit=max(0, int(args.sample_limit)))
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
