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
        costs[name] += len(str(candidate_slice.get("text") or "")) + 180 + candidate_slice_risk_cost(candidate_slice)
    return costs


HIGH_RISK_OUTCOME_TERMS = {
    "败",
    "敗",
    "败绩",
    "敗績",
    "杀",
    "殺",
    "诛",
    "誅",
    "坐",
    "罪",
    "谋",
    "謀",
    "反",
    "赐死",
    "賜死",
    "伏诛",
    "伏誅",
    "有罪",
    "收印",
    "收大将军印",
    "敗绩",
}


def candidate_slice_risk_cost(candidate_slice: Mapping[str, Any]) -> int:
    text = str(candidate_slice.get("text") or "")
    object_name = str(candidate_slice.get("object_name") or "").strip()
    matched_aliases = [str(value or "") for value in candidate_slice.get("matched_aliases") or []]
    matched_outcome_terms = {str(value or "") for value in candidate_slice.get("matched_outcome_terms") or []}
    matched_alias_strengths = candidate_slice.get("matched_alias_strengths") or {}
    risk = 0
    if candidate_slice.get("weak_alias_only"):
        risk += 900
    if object_name and object_name not in text and matched_aliases:
        risk += 700
    if isinstance(matched_alias_strengths, Mapping) and matched_alias_strengths:
        strengths = {str(value or "").lower() for value in matched_alias_strengths.values()}
        if "strong" not in strengths:
            risk += 400
    if matched_outcome_terms & HIGH_RISK_OUTCOME_TERMS:
        risk += 350
    return risk


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


def compact_for_contains(value: Any) -> str:
    return "".join(str(value or "").split())


def slice_contains_span(candidate_slice: Mapping[str, Any], span_text: str) -> bool:
    needle = compact_for_contains(span_text)
    if not needle:
        return False
    return needle in compact_for_contains(candidate_slice.get("text"))


def choose_evidence_slice_ref(
    *,
    by_slice: Mapping[str, Mapping[str, Any]],
    claim: Mapping[str, Any],
    span_text: str,
    current_ref: str,
    claim_refs: Sequence[str],
    evidence_texts: Sequence[str],
) -> str:
    matches = sorted(code for code, row in by_slice.items() if slice_contains_span(row, span_text))
    if not matches:
        return ""
    current_doc = str((by_slice.get(current_ref) or {}).get("document_code") or "")
    object_name = str(claim.get("object_name") or "").strip()

    def score(slice_code: str) -> tuple[int, int, int, int, int]:
        candidate_slice = by_slice[slice_code]
        slice_text = str(candidate_slice.get("text") or "")
        compact_slice = compact_for_contains(slice_text)
        evidence_hits = sum(1 for text in evidence_texts if compact_for_contains(text) in compact_slice)
        return (
            int(slice_code in claim_refs),
            int(bool(current_doc) and str(candidate_slice.get("document_code") or "") == current_doc),
            int(object_name and str(candidate_slice.get("object_name") or "") == object_name),
            evidence_hits,
            len(slice_text),
        )

    return max(matches, key=score)


def repair_evidence_span_refs(candidates: Mapping[str, Any], claims: Sequence[dict[str, Any]]) -> None:
    by_slice = candidate_slices_by_code(candidates)
    if not by_slice:
        return
    for claim in claims:
        initial_refs = unique_texts(claim.get("source_slice_refs") or [])
        known_refs = [ref for ref in initial_refs if ref in by_slice]
        if len(known_refs) != len(initial_refs):
            claim["source_slice_refs"] = known_refs
            fact_payload = claim.get("fact_payload")
            if isinstance(fact_payload, dict):
                fact_payload["source_span_refs"] = [
                    ref for ref in unique_texts(fact_payload.get("source_span_refs") or []) if ref in by_slice
                ]
        spans = [span for span in claim.get("evidence_spans") or [] if isinstance(span, dict)]
        if not spans:
            continue
        claim_refs = unique_texts(claim.get("source_slice_refs") or [])
        evidence_texts = [str(span.get("text") or "").strip() for span in spans if span.get("text")]
        added_refs: list[str] = []
        for span in spans:
            span_text = str(span.get("text") or "").strip()
            if not span_text:
                continue
            current_ref = str(span.get("source_slice_ref") or "").strip()
            current_slice = by_slice.get(current_ref)
            if current_slice and slice_contains_span(current_slice, span_text):
                if current_ref not in claim_refs:
                    added_refs.append(current_ref)
                continue
            repaired_ref = choose_evidence_slice_ref(
                by_slice=by_slice,
                claim=claim,
                span_text=span_text,
                current_ref=current_ref,
                claim_refs=claim_refs,
                evidence_texts=evidence_texts,
            )
            if not repaired_ref:
                continue
            span["source_slice_ref"] = repaired_ref
            if repaired_ref not in claim_refs and repaired_ref not in added_refs:
                added_refs.append(repaired_ref)
        if added_refs:
            claim["source_slice_refs"] = unique_texts([*claim_refs, *added_refs])
            fact_payload = claim.get("fact_payload")
            if isinstance(fact_payload, dict):
                fact_payload["source_span_refs"] = unique_texts(
                    [*(fact_payload.get("source_span_refs") or []), *added_refs]
                )


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
            slice_text = str(candidate_slice.get("text") or "")
            passage_refs.append(passage_code)
            passages.setdefault(
                passage_code,
                {
                    "passage_code": passage_code,
                    "document_code": candidate_slice.get("document_code"),
                    "slice_code": slice_code,
                    "locator": candidate_slice.get("locator") or "",
                    "quote": slice_text,
                    "raw_text": slice_text,
                    "summary": claim.get("claim_summary") or "",
                    "matched_aliases": candidate_slice.get("matched_aliases") or [],
                },
            )
        if passage_refs and not claim.get("source_passage_refs"):
            claim["source_passage_refs"] = passage_refs
    return list(passages.values())


def _candidate_item_code(row: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    return str(row.get("candidate_item_code") or payload.get("candidate_item_code") or "").strip()


def _is_ad_factor_hint_allowed(row: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
    rule_code = str(row.get("rule_code") or payload.get("rule_code") or "").strip()
    lane = str(row.get("candidate_lane") or payload.get("candidate_lane") or "").strip()
    direction = str(row.get("direction") or row.get("candidate_direction") or payload.get("direction") or "").strip()
    scoring = payload.get("scoring_candidate") is True or str(payload.get("scoring_candidate") or "").strip().lower() == "true"
    usable = (
        payload.get("usable_for_scoring_cluster") is True
        or str(payload.get("usable_for_scoring_cluster") or "").strip().lower() == "true"
    )
    return (
        rule_code == "appointment_delegation"
        and lane == "I5B.appointment_delegation"
        and scoring
        and usable
        and direction in {"positive", "negative"}
    )


def _prune_empty_profile_values(profile: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in profile.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if value == [] or value == {}:
            continue
        result[str(key)] = value
    return result


def _claim_by_code(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for claim in payload.get("claims") or []:
        if isinstance(claim, Mapping) and claim.get("claim_code"):
            result.setdefault(str(claim.get("claim_code")), claim)
    return result


def _fact_payload_for_claim(claim: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(claim, Mapping):
        return {}
    fact_payload = claim.get("fact_payload")
    if isinstance(fact_payload, Mapping):
        return fact_payload
    return {}


def inferred_personnel_profile(row: Mapping[str, Any], claim: Mapping[str, Any] | None) -> dict[str, Any]:
    fact_payload = _fact_payload_for_claim(claim)
    completeness = fact_payload.get("completeness") if isinstance(fact_payload.get("completeness"), Mapping) else {}
    return _prune_empty_profile_values(
        {
            "person": (claim or {}).get("object_name") or fact_payload.get("object"),
            "person_role": (row.get("candidate_payload") or {}).get("candidate_role") if isinstance(row.get("candidate_payload"), Mapping) else "",
            "talent_quality": "",
            "action_type": fact_payload.get("action_type"),
            "appointment_or_authorization": fact_payload.get("office_or_domain") or fact_payload.get("action_type"),
            "feedback_or_result": fact_payload.get("outcome") or fact_payload.get("cost_or_damage"),
            "team_function": row.get("candidate_lane"),
            "selection_channel": "",
            "same_event_chain": completeness.get("same_event_chain"),
        }
    )


def inferred_power_control_profile(row: Mapping[str, Any], claim: Mapping[str, Any] | None) -> dict[str, Any]:
    fact_payload = _fact_payload_for_claim(claim)
    completeness = fact_payload.get("completeness") if isinstance(fact_payload.get("completeness"), Mapping) else {}
    return _prune_empty_profile_values(
        {
            "power_holder": (claim or {}).get("object_name") or fact_payload.get("object"),
            "power_base": fact_payload.get("office_or_domain"),
            "power_channel": fact_payload.get("action_type"),
            "control_action": row.get("rule_code"),
            "control_result": fact_payload.get("outcome") or fact_payload.get("cost_or_damage"),
            "risk_type": row.get("candidate_lane"),
            "same_event_chain": completeness.get("same_event_chain"),
        }
    )


def normalize_candidate_payload_profiles(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(stable_json(payload))
    claims_by_code = _claim_by_code(result)
    candidates = [row for row in result.get("secondary_binding_candidates") or [] if isinstance(row, dict)]
    for row in candidates:
        raw_payload = row.get("candidate_payload")
        candidate_payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
        candidate_item_code = _candidate_item_code(row, candidate_payload)
        claim = claims_by_code.get(str(row.get("claim_code") or ""))
        candidate_payload.pop("profile_policy", None)
        if candidate_item_code != "I5B":
            candidate_payload.pop("personnel_profile", None)
        if candidate_item_code != "I5C":
            candidate_payload.pop("power_control_profile", None)
        if not _is_ad_factor_hint_allowed(row, candidate_payload):
            candidate_payload.pop("appointment_delegation_factor_hints", None)
        for profile_key in ("personnel_profile", "power_control_profile"):
            profile = candidate_payload.get(profile_key)
            if isinstance(profile, Mapping):
                pruned = _prune_empty_profile_values(profile)
                if pruned:
                    candidate_payload[profile_key] = pruned
                else:
                    candidate_payload.pop(profile_key, None)
        if candidate_item_code == "I5B" and not isinstance(candidate_payload.get("personnel_profile"), Mapping):
            profile = inferred_personnel_profile(row, claim)
            if profile:
                candidate_payload["personnel_profile"] = profile
        if candidate_item_code == "I5C" and not isinstance(candidate_payload.get("power_control_profile"), Mapping):
            profile = inferred_power_control_profile(row, claim)
            if profile:
                candidate_payload["power_control_profile"] = profile
        row["candidate_payload"] = candidate_payload
    result["secondary_binding_candidates"] = candidates
    return result


def enrich_judge_payload(candidates: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    result = normalize_candidate_payload_profiles(payload)
    claims = [claim for claim in result.get("claims") or [] if isinstance(claim, dict)]
    repair_evidence_span_refs(candidates, claims)
    result["claims"] = claims
    materialized_passages = materialize_passages_from_claims(candidates, claims)
    if not result.get("passages"):
        result["passages"] = materialized_passages
    else:
        passage_codes = {
            str(passage.get("passage_code") or "")
            for passage in result.get("passages") or []
            if isinstance(passage, Mapping) and passage.get("passage_code")
        }
        result["passages"] = [
            *(result.get("passages") or []),
            *[
                passage
                for passage in materialized_passages
                if str(passage.get("passage_code") or "") not in passage_codes
            ],
        ]

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
    claim_shard_plan = candidates.get("claim_shard_plan") if isinstance(candidates.get("claim_shard_plan"), Mapping) else {}
    planned_shards = claim_shard_plan.get("shards") if isinstance(claim_shard_plan.get("shards"), list) else []
    if claim_shard_plan.get("mode") == "owner_aware" and planned_shards:
        if len(planned_shards) <= 1:
            return []
        return build_judge_shards_from_plan(candidates, planned_shards, round_index=round_index)
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


def build_judge_shards_from_plan(
    candidates: Mapping[str, Any],
    planned_shards: Sequence[Any],
    *,
    round_index: int,
) -> list[dict[str, Any]]:
    seed_by_name = object_seed_map(candidates)
    base_matrix = candidates.get("coverage_matrix") if isinstance(candidates.get("coverage_matrix"), Mapping) else {}
    by_slice_code = {
        str(row.get("slice_code") or ""): dict(row)
        for row in candidates.get("candidate_slices") or []
        if isinstance(row, Mapping) and row.get("slice_code")
    }
    shards: list[dict[str, Any]] = []
    for shard_index, raw_shard in enumerate(planned_shards, start=1):
        if not isinstance(raw_shard, Mapping):
            continue
        slice_codes = [str(value or "") for value in raw_shard.get("slice_codes") or [] if str(value or "")]
        shard_slices = [by_slice_code[code] for code in slice_codes if code in by_slice_code]
        if not shard_slices:
            continue
        object_names = unique_texts(raw_shard.get("object_names") or [row.get("object_name") for row in shard_slices])
        object_seeds = [dict(seed_by_name[name]) for name in object_names if name in seed_by_name]
        object_slice_counts = {
            name: sum(1 for row in shard_slices if str(row.get("object_name") or "") == name) for name in object_names
        }
        shard_code = str(raw_shard.get("shard_code") or f"CSH-R{round_index:02d}-{shard_index:02d}")
        shard_payload = json.loads(stable_json(candidates))
        shard_payload["judge_shard"] = {
            "shard_code": shard_code,
            "round": round_index,
            "shard_index": shard_index,
            "shard_count": len(planned_shards),
            "object_names": object_names,
            "estimated_slice_chars": raw_shard.get("estimated_slice_chars"),
            "owner_anchor_class": raw_shard.get("owner_anchor_class"),
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
        name_set = set(object_names)
        shard_payload["coverage_gaps"] = [
            dict(gap)
            for gap in candidates.get("coverage_gaps") or []
            if isinstance(gap, Mapping)
            and (not str(gap.get("object_name") or "").strip() or str(gap.get("object_name") or "") in name_set)
        ]
        shards.append({"shard_code": shard_code, "object_names": object_names, "payload": shard_payload})
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


def claim_has_complete_action_object(claim: Mapping[str, Any]) -> bool:
    completeness = claim.get("claim_completeness") if isinstance(claim.get("claim_completeness"), Mapping) else {}
    if not completeness:
        return bool(claim.get("claim_summary") or claim.get("summary")) and bool(claim.get("source_passage_refs") or claim.get("source_slice_refs"))
    return bool(completeness.get("has_action_span")) and bool(completeness.get("has_object_span")) and not bool(
        completeness.get("needs_source_extension")
    )


def complete_claim_objects(claims: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(claim.get("object_name") or "")
        for claim in claims
        if claim.get("object_name") and claim_has_complete_action_object(claim)
    }


def gap_has_actionable_diagnosis(gap: Mapping[str, Any]) -> bool:
    return any(
        str(gap.get(key) or "").strip()
        for key in ("diagnosis", "diagnostic", "reason", "recommended_action", "suggested_action")
    )


def secondary_binding_object_name(binding: Mapping[str, Any], claim_objects: Mapping[str, str]) -> str:
    payload = binding.get("candidate_payload") if isinstance(binding.get("candidate_payload"), Mapping) else {}
    personnel_profile = payload.get("personnel_profile") if isinstance(payload.get("personnel_profile"), Mapping) else {}
    return str(
        binding.get("object_name")
        or payload.get("person")
        or personnel_profile.get("person")
        or claim_objects.get(str(binding.get("claim_code") or ""))
        or ""
    )


def secondary_binding_matches_family(binding: Mapping[str, Any], family_code: str) -> bool:
    lane = str(binding.get("candidate_lane") or binding.get("rule_code") or "")
    if not family_code:
        return True
    if family_code == "appointment_delegation_material":
        return lane in {"I5B.appointment_delegation", "appointment_delegation"}
    if family_code == "anti_nepotism_material":
        return lane in {"anti_nepotism", "I5B.anti_nepotism"}
    normalized_family = family_code.replace("_material", "")
    return normalized_family and (lane == normalized_family or normalized_family in lane)


def filter_resolved_shard_gaps(
    coverage_gaps: Sequence[Mapping[str, Any]],
    *,
    claims: Sequence[Mapping[str, Any]],
    primary_bindings: Sequence[Mapping[str, Any]],
    secondary_bindings: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    claim_objects = claim_object_by_code(claims)
    complete_objects = complete_claim_objects(claims)
    covered: dict[str, list[Mapping[str, Any]]] = {}
    for binding in primary_bindings:
        object_name = str(binding.get("object_name") or claim_objects.get(str(binding.get("claim_code") or "")) or "")
        if object_name:
            covered.setdefault(object_name, []).append(binding)
    secondary_covered: dict[str, list[Mapping[str, Any]]] = {}
    for binding in secondary_bindings:
        object_name = secondary_binding_object_name(binding, claim_objects)
        if object_name:
            secondary_covered.setdefault(object_name, []).append(binding)
    resolved_gap_types = {"predicate_missing", "weak_alias_noise", "civil_undercoverage", "negative_undercoverage"}
    result: list[dict[str, Any]] = []
    for gap in coverage_gaps:
        gap_type = str(gap.get("gap_type") or "")
        object_name = str(gap.get("object_name") or "")
        family_code = str(gap.get("family_code") or "")
        if (
            gap_type == "object_claim_undercoverage"
            and object_name in complete_objects
            and not gap_has_actionable_diagnosis(gap)
            and (
                any(binding_matches_family(binding, family_code) for binding in covered.get(object_name, []))
                or any(secondary_binding_matches_family(binding, family_code) for binding in secondary_covered.get(object_name, []))
            )
        ):
            continue
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
    coverage_gaps = filter_resolved_shard_gaps(
        coverage_gaps,
        claims=claims,
        primary_bindings=primary_bindings,
        secondary_bindings=secondary_bindings,
    )
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
