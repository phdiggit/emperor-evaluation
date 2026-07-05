from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from scripts.dev import retrieval_v2_candidate_prompt as candidate_prompt
from scripts.dev import retrieval_v2_source_candidates as source_candidates


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_fingerprint(value: Any) -> str:
    return source_candidates.stable_fingerprint(value)


def unique_texts(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def candidate_object_name(seed: Mapping[str, Any]) -> str:
    return source_candidates.object_seed_name(seed)


def objects_from_candidate_slices(candidates: Mapping[str, Any]) -> list[str]:
    return unique_texts([row.get("object_name") for row in candidates.get("candidate_slices") or []])


def object_seed_map(candidates: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for seed in candidates.get("object_seeds") or []:
        if not isinstance(seed, Mapping):
            continue
        name = candidate_object_name(seed)
        if name:
            result.setdefault(name, seed)
    return result


def object_slice_costs(candidates: Mapping[str, Any], object_names: Sequence[str]) -> dict[str, int]:
    costs = {name: 0 for name in object_names}
    for candidate_slice in candidates.get("candidate_slices") or []:
        if not isinstance(candidate_slice, Mapping):
            continue
        name = str(candidate_slice.get("object_name") or "")
        if name not in costs:
            continue
        costs[name] += len(str(candidate_slice.get("text") or "")) + 180
    return costs


def balanced_object_chunks(
    candidates: Mapping[str, Any],
    object_names: Sequence[str],
    *,
    max_objects_per_shard: int,
) -> list[list[str]]:
    if max_objects_per_shard <= 0:
        return [list(object_names)]
    if len(object_names) <= max_objects_per_shard:
        return [list(object_names)]

    shard_count = max(1, (len(object_names) + max_objects_per_shard - 1) // max_objects_per_shard)
    costs = object_slice_costs(candidates, object_names)
    buckets: list[list[str]] = [[] for _ in range(shard_count)]
    bucket_costs = [0 for _ in range(shard_count)]
    for name in sorted(object_names, key=lambda value: (-costs.get(value, 0), value)):
        eligible = [index for index, bucket in enumerate(buckets) if len(bucket) < max_objects_per_shard]
        if not eligible:
            eligible = list(range(shard_count))
        bucket_index = min(eligible, key=lambda index: (bucket_costs[index], len(buckets[index]), index))
        buckets[bucket_index].append(name)
        bucket_costs[bucket_index] += costs.get(name, 0)
    return [bucket for bucket in buckets if bucket]


def filter_source_documents(
    candidates: Mapping[str, Any],
    candidate_slices: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    wanted_codes = {str(row.get("document_code") or "") for row in candidate_slices if row.get("document_code")}
    documents: list[dict[str, Any]] = []
    for document in candidates.get("source_documents") or []:
        if not isinstance(document, Mapping):
            continue
        if not wanted_codes or str(document.get("document_code") or "") in wanted_codes:
            documents.append(dict(document))
    return documents


def source_documents_by_code(candidates: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for document in candidates.get("source_documents") or []:
        if isinstance(document, Mapping) and document.get("document_code"):
            result.setdefault(str(document["document_code"]), dict(document))
    return result


def candidate_slices_by_code(candidates: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate_slice in candidates.get("candidate_slices") or []:
        if isinstance(candidate_slice, Mapping) and candidate_slice.get("slice_code"):
            result.setdefault(str(candidate_slice["slice_code"]), dict(candidate_slice))
    return result


def passage_code_for_slice(slice_code: str) -> str:
    return f"PAS-{stable_fingerprint(slice_code)[:12].upper()}"


def materialize_passages_from_claims(
    candidates: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_slice = candidate_slices_by_code(candidates)
    passages: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        passage_refs: list[str] = []
        for raw_slice_ref in claim.get("source_slice_refs") or []:
            slice_code = str(raw_slice_ref or "").strip()
            if not slice_code or slice_code not in by_slice:
                continue
            candidate_slice = by_slice[slice_code]
            passage_code = passage_code_for_slice(slice_code)
            passage_refs.append(passage_code)
            passages.setdefault(
                passage_code,
                {
                    "passage_code": passage_code,
                    "document_code": candidate_slice.get("document_code"),
                    "slice_code": slice_code,
                    "locator": candidate_slice.get("locator") or "",
                    "quote": str(candidate_slice.get("text") or "")[:120],
                    "summary": claim.get("claim_summary") or "",
                    "matched_aliases": candidate_slice.get("matched_aliases") or [],
                },
            )
        if passage_refs and not claim.get("source_passage_refs"):
            claim["source_passage_refs"] = passage_refs
    return list(passages.values())


def enrich_judge_payload(candidates: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(stable_json(payload))
    claims = [claim for claim in result.get("claims") or [] if isinstance(claim, dict)]
    result["claims"] = claims
    if not result.get("passages"):
        result["passages"] = materialize_passages_from_claims(candidates, claims)

    documents_by_code = source_documents_by_code(candidates)
    referenced_doc_codes = {
        str(passage.get("document_code") or "")
        for passage in result.get("passages") or []
        if isinstance(passage, Mapping) and passage.get("document_code")
    }
    if not result.get("documents"):
        result["documents"] = [
            documents_by_code[code] for code in sorted(referenced_doc_codes) if code in documents_by_code
        ]
    return result


def shard_coverage_matrix(
    base_matrix: Mapping[str, Any],
    candidate_slices: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    matrix = json.loads(stable_json(base_matrix))
    role_families: list[dict[str, Any]] = []
    for raw_family in matrix.get("role_families") or []:
        if not isinstance(raw_family, Mapping):
            continue
        family_code = str(raw_family.get("family_code") or "").strip()
        family_slices = [
            row for row in candidate_slices if family_code and family_code in (row.get("matched_role_families") or [])
        ]
        family_row = dict(raw_family)
        family_row["candidate_slice_count"] = len(family_slices)
        family_row["objects_checked"] = sorted(
            {str(row.get("object_name") or "") for row in family_slices if row.get("object_name")}
        )
        family_row["gaps"] = []
        role_families.append(family_row)
    matrix["role_families"] = role_families
    return matrix


def build_judge_shards(
    candidates: Mapping[str, Any],
    *,
    max_objects_per_shard: int,
    round_index: int,
) -> list[dict[str, Any]]:
    if max_objects_per_shard <= 0:
        return []
    object_names = objects_from_candidate_slices(candidates)
    chunks = balanced_object_chunks(candidates, object_names, max_objects_per_shard=max_objects_per_shard)
    if len(chunks) <= 1:
        return []

    seed_by_name = object_seed_map(candidates)
    base_matrix = candidates.get("coverage_matrix") if isinstance(candidates.get("coverage_matrix"), Mapping) else {}
    shards: list[dict[str, Any]] = []
    for shard_index, names in enumerate(chunks, start=1):
        name_set = set(names)
        shard_slices = [
            dict(row)
            for row in candidates.get("candidate_slices") or []
            if str(row.get("object_name") or "") in name_set
        ]
        shard_code = f"JSH-R{round_index:02d}-{shard_index:02d}"
        object_seeds = [dict(seed_by_name[name]) for name in names if name in seed_by_name]
        object_slice_counts = {
            name: sum(1 for row in shard_slices if str(row.get("object_name") or "") == name) for name in names
        }
        shard_payload = json.loads(stable_json(candidates))
        shard_payload["judge_shard"] = {
            "shard_code": shard_code,
            "round": round_index,
            "shard_index": shard_index,
            "shard_count": len(chunks),
            "object_names": names,
            "estimated_slice_chars": sum(object_slice_costs(candidates, names).values()),
            "partial_judge": True,
        }
        shard_payload["object_seeds"] = object_seeds
        shard_payload["source_documents"] = filter_source_documents(candidates, shard_slices)
        shard_payload["candidate_slices"] = shard_slices
        shard_payload["coverage_matrix"] = shard_coverage_matrix(base_matrix, shard_slices)
        shard_payload["coverage"] = {
            "object_slice_counts": object_slice_counts,
            "objects_without_slices": [name for name, count in object_slice_counts.items() if count == 0],
            "ready_for_judgement": all(count > 0 for count in object_slice_counts.values()),
            "partial_judge": True,
        }
        shard_payload["coverage_gaps"] = [
            dict(gap)
            for gap in candidates.get("coverage_gaps") or []
            if isinstance(gap, Mapping)
            and (not str(gap.get("object_name") or "").strip() or str(gap.get("object_name") or "") in name_set)
        ]
        shards.append(
            {
                "shard_code": shard_code,
                "object_names": names,
                "payload": shard_payload,
            }
        )
    return shards


def build_judge_shard_prompt(shard_payload: Mapping[str, Any]) -> str:
    shard = shard_payload.get("judge_shard") if isinstance(shard_payload.get("judge_shard"), Mapping) else {}
    object_names = ", ".join(str(name) for name in shard.get("object_names") or [])
    return (
        "这是 retrieval_v2 judge 分片任务。只判读本 shard 的 candidate_slices 和对象；"
        "不要为 shard 外对象、shard 外角色族或本 shard 未给出的 source_documents 报缺口。"
        "最终 coverage 可以是 partial，主控聚合器会合并所有 shard。\n"
        f"shard_code={shard.get('shard_code')}；objects={object_names}\n\n"
        f"{candidate_prompt.build_prompt(shard_payload)}"
    )


def prefixed_code(prefix: str, value: Any, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    if text.startswith(f"{prefix}-"):
        return text
    return f"{prefix}-{text}"


def remap_passages(payload: Mapping[str, Any], shard_code: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    passages: list[dict[str, Any]] = []
    passage_map: dict[str, str] = {}
    for index, raw_passage in enumerate(payload.get("passages") or [], start=1):
        if not isinstance(raw_passage, Mapping):
            continue
        old_code = str(raw_passage.get("passage_code") or f"PAS-{index:03d}")
        new_code = prefixed_code(shard_code, old_code, f"PAS-{index:03d}")
        passage_map[old_code] = new_code
        passage = dict(raw_passage)
        passage["passage_code"] = new_code
        passages.append(passage)
    return passages, passage_map


def remap_claims(
    payload: Mapping[str, Any],
    shard_code: str,
    passage_map: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    claims: list[dict[str, Any]] = []
    claim_map: dict[str, str] = {}
    for index, raw_claim in enumerate(payload.get("claims") or [], start=1):
        if not isinstance(raw_claim, Mapping):
            continue
        old_code = str(raw_claim.get("claim_code") or f"CLM-{index:03d}")
        new_code = prefixed_code(shard_code, old_code, f"CLM-{index:03d}")
        claim_map[old_code] = new_code
        claim = dict(raw_claim)
        claim["claim_code"] = new_code
        claim["source_passage_refs"] = [
            passage_map.get(str(ref), str(ref)) for ref in claim.get("source_passage_refs") or []
        ]
        claims.append(claim)
    return claims, claim_map


def remap_bindings(
    rows: Sequence[Any],
    claim_map: Mapping[str, str],
    *,
    shard_code: str,
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for raw_binding in rows:
        if not isinstance(raw_binding, Mapping):
            continue
        binding = dict(raw_binding)
        old_claim = str(binding.get("claim_code") or "")
        if old_claim:
            binding["claim_code"] = claim_map.get(old_claim, old_claim)
        binding.setdefault("binding_code", f"{shard_code}-BND-{stable_fingerprint(binding)[:10].upper()}")
        bindings.append(binding)
    return bindings


def dedupe_rows(rows: Sequence[Mapping[str, Any]], key_fields: Sequence[str]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = stable_fingerprint([row.get(field) for field in key_fields] or row)
        deduped.setdefault(key, dict(row))
    return list(deduped.values())


def final_status(statuses: Sequence[str]) -> str:
    normalized = [status for status in statuses if status]
    if any(status == "blocked" for status in normalized):
        return "blocked"
    if any(status != "succeeded" for status in normalized):
        return "needs_refinement"
    return "succeeded"


QUEUEABLE_GAP_TYPES = {
    "alias_missing",
    "civil_undercoverage",
    "fetch_error",
    "negative_undercoverage",
    "needs_primary_source",
    "predicate_missing",
    "source_missing",
    "true_lack",
    "weak_alias_noise",
    "other",
}


def queueable_gap_status(
    statuses: Sequence[str],
    coverage_gaps: Sequence[Mapping[str, Any]],
) -> str:
    status = final_status(statuses)
    if status == "blocked":
        return status
    normalized = [status for status in statuses if status]
    if any(status not in {"succeeded", "needs_refinement"} for status in normalized):
        return status
    if all(str(gap.get("gap_type") or "") in QUEUEABLE_GAP_TYPES for gap in coverage_gaps):
        return "succeeded"
    return status


def binding_matches_family(binding: Mapping[str, Any], family_code: str) -> bool:
    role = str(binding.get("object_role") or "")
    return bool(family_code and (role == family_code or role in family_code or family_code in role))


def claim_object_by_code(claims: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {
        str(claim.get("claim_code") or ""): str(claim.get("object_name") or "")
        for claim in claims
        if claim.get("claim_code") and claim.get("object_name")
    }


def filter_resolved_shard_gaps(
    coverage_gaps: Sequence[Mapping[str, Any]],
    *,
    claims: Sequence[Mapping[str, Any]],
    primary_bindings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    claim_objects = claim_object_by_code(claims)
    covered: dict[str, list[Mapping[str, Any]]] = {}
    for binding in primary_bindings:
        object_name = str(binding.get("object_name") or claim_objects.get(str(binding.get("claim_code") or "")) or "")
        if object_name:
            covered.setdefault(object_name, []).append(binding)
    resolved_gap_types = {"predicate_missing", "weak_alias_noise", "civil_undercoverage", "negative_undercoverage"}
    result: list[dict[str, Any]] = []
    for gap in coverage_gaps:
        gap_type = str(gap.get("gap_type") or "")
        object_name = str(gap.get("object_name") or "")
        family_code = str(gap.get("family_code") or "")
        if gap_type in resolved_gap_types and object_name and any(
            binding_matches_family(binding, family_code) for binding in covered.get(object_name, [])
        ):
            continue
        result.append(dict(gap))
    return result


def merged_coverage_matrix(
    candidates: Mapping[str, Any],
    primary_bindings: Sequence[Mapping[str, Any]],
    coverage_gaps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    base = candidates.get("coverage_matrix") if isinstance(candidates.get("coverage_matrix"), Mapping) else {}
    matrix = json.loads(stable_json(base))
    slices = [row for row in candidates.get("candidate_slices") or [] if isinstance(row, Mapping)]
    role_families: list[dict[str, Any]] = []
    for raw_family in matrix.get("role_families") or []:
        if not isinstance(raw_family, Mapping):
            continue
        family_code = str(raw_family.get("family_code") or "").strip()
        family_slices = [
            row for row in slices if family_code and family_code in (row.get("matched_role_families") or [])
        ]
        family_gaps = [
            dict(gap)
            for gap in coverage_gaps
            if isinstance(gap, Mapping) and str(gap.get("family_code") or "") == family_code
        ]
        family_row = dict(raw_family)
        family_row["candidate_slice_count"] = len(family_slices)
        family_row["accepted_claim_count"] = sum(
            1 for binding in primary_bindings if binding_matches_family(binding, family_code)
        )
        family_row["objects_checked"] = sorted(
            {str(row.get("object_name") or "") for row in family_slices if row.get("object_name")}
        )
        family_row["gaps"] = family_gaps
        role_families.append(family_row)
    matrix["role_families"] = role_families
    return matrix


def merge_judge_shard_results(
    *,
    candidates: Mapping[str, Any],
    shard_results: Sequence[Mapping[str, Any]],
    elapsed_seconds: float,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    documents_by_code: dict[str, dict[str, Any]] = {}
    passages: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    primary_bindings: list[dict[str, Any]] = []
    secondary_bindings: list[dict[str, Any]] = []
    coverage_gaps: list[dict[str, Any]] = []
    checked_objects: list[str] = []
    missing_core_objects: list[str] = []
    statuses: list[str] = []
    shard_summaries: list[dict[str, Any]] = []

    for row in shard_results:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        shard = row.get("shard") if isinstance(row.get("shard"), Mapping) else {}
        shard_code = str(shard.get("shard_code") or f"JSH-{len(shard_summaries) + 1:02d}")
        statuses.append(str(payload.get("status") or "needs_refinement"))
        for document in payload.get("documents") or []:
            if isinstance(document, Mapping) and document.get("document_code"):
                documents_by_code.setdefault(str(document["document_code"]), dict(document))
        remapped_passages, passage_map = remap_passages(payload, shard_code)
        remapped_claims, claim_map = remap_claims(payload, shard_code, passage_map)
        passages.extend(remapped_passages)
        claims.extend(remapped_claims)
        primary_bindings.extend(
            remap_bindings(payload.get("primary_bindings") or payload.get("bindings") or [], claim_map, shard_code=shard_code)
        )
        secondary_bindings.extend(
            remap_bindings(payload.get("secondary_binding_candidates") or [], claim_map, shard_code=shard_code)
        )
        coverage = payload.get("coverage") if isinstance(payload.get("coverage"), Mapping) else {}
        checked_objects.extend(str(value) for value in coverage.get("checked_objects") or [])
        missing_core_objects.extend(str(value) for value in coverage.get("missing_core_objects") or [])
        for gap in payload.get("coverage_gaps") or []:
            if isinstance(gap, Mapping):
                coverage_gaps.append(dict(gap))
        shard_summaries.append(
            {
                "shard_code": shard_code,
                "object_names": list(shard.get("object_names") or []),
                "status": payload.get("status"),
                "elapsed_seconds": row.get("elapsed_seconds"),
                "claim_count": len(payload.get("claims") or []),
                "primary_binding_count": len(payload.get("primary_bindings") or payload.get("bindings") or []),
                "usage": row.get("usage") or {},
                "result_path": row.get("output_path"),
            }
        )

    carry_gap_types = {"alias_missing", "weak_alias_noise", "fetch_error"}
    for gap in candidates.get("coverage_gaps") or []:
        if isinstance(gap, Mapping) and str(gap.get("gap_type") or "") in carry_gap_types:
            coverage_gaps.append(dict(gap))

    primary_bindings = dedupe_rows(primary_bindings, ("claim_code", "rule_code", "predicate", "object_role"))
    secondary_bindings = dedupe_rows(secondary_bindings, ("claim_code", "rule_code", "reason"))
    coverage_gaps = dedupe_rows(coverage_gaps, ("gap_type", "object_name", "family_code", "diagnosis"))
    coverage_gaps = filter_resolved_shard_gaps(coverage_gaps, claims=claims, primary_bindings=primary_bindings)
    status = queueable_gap_status(statuses, coverage_gaps)
    positive_count = sum(1 for claim in claims if str(claim.get("direction") or "") == "positive")
    negative_count = sum(1 for claim in claims if str(claim.get("direction") or "") == "negative")
    all_checked_objects = sorted(set(objects_from_candidate_slices(candidates)) | set(checked_objects))
    merged = {
        "job_code": (candidates.get("task_identity") or {}).get("job_code", ""),
        "status": status,
        "documents": list(documents_by_code.values()) or list(candidates.get("source_documents") or []),
        "passages": passages,
        "claims": claims,
        "primary_bindings": primary_bindings,
        "secondary_binding_candidates": secondary_bindings,
        "coverage_matrix": merged_coverage_matrix(candidates, primary_bindings, coverage_gaps),
        "coverage": {
            "ready_for_object_pool": status == "succeeded" and not coverage_gaps,
            "checked_objects": all_checked_objects,
            "missing_core_objects": sorted(set(value for value in missing_core_objects if value)),
            "positive_claim_count": positive_count,
            "negative_claim_count": negative_count,
            "alias_coverage_note": "merged from judge shards",
        },
        "coverage_gaps": coverage_gaps,
        "judge_shards": shard_summaries,
        "_sharded": True,
        "_shard_count": len(shard_summaries),
        "_elapsed_seconds": elapsed_seconds,
        "_usage": dict(usage),
    }
    return enrich_judge_payload(candidates, merged)
