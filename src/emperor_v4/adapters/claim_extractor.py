from __future__ import annotations

from typing import Any, Mapping

from emperor_v4.contracts.assertion import AssertionDraft


_TYPE_MAP = {
    "material_claim": "event_fact",
    "context_claim": "context_fact",
    "counter_claim": "causal_claim",
}


def _index_passages(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    passages: dict[str, Mapping[str, Any]] = {}
    for passage in payload.get("passages", []):
        passage_code = passage.get("passage_code", "")
        if not passage_code:
            raise ValueError("V3 claim passage 缺少 passage_code")
        if passage_code in passages:
            raise ValueError(f"重复 passage_code: {passage_code}")
        passages[passage_code] = passage
    return passages


def adapt_claim_extractor_snapshot(
    snapshot: Mapping[str, Any],
) -> tuple[AssertionDraft, ...]:
    if snapshot.get("legacy_contract") != "retrieval-v3-claim-judge-final":
        raise ValueError("不是受支持的 V3 claim extractor fixture")

    assertions: list[AssertionDraft] = []
    seen_codes: set[str] = set()

    for person in snapshot.get("people", []):
        payload = person.get("payload", {})
        claim_run = person.get("claim_run", "")
        if not claim_run:
            raise ValueError("V3 claim fixture 缺少 claim_run")
        passages = _index_passages(payload)
        documents = {
            item.get("document_code", ""): item
            for item in payload.get("documents", [])
        }
        for claim in payload.get("claims", []):
            claim_kind = claim.get("claim_kind")
            if claim_kind not in _TYPE_MAP:
                raise ValueError(f"未知 V3 claim_kind: {claim_kind}")
            passage_refs = tuple(claim.get("source_passage_refs") or ())
            if not passage_refs:
                raise ValueError(f"claim 无 passage lineage: {claim.get('claim_code', '')}")

            fact = claim.get("fact_payload") or {}
            for passage_ref in passage_refs:
                passage = passages.get(passage_ref)
                if passage is None:
                    raise ValueError(f"claim 引用了未知 passage: {passage_ref}")
                legacy_code = claim.get("claim_code", "")
                code = f"{claim_run}@{legacy_code}"
                if len(passage_refs) > 1:
                    code = f"{code}@{passage_ref}"
                if code in seen_codes:
                    raise ValueError(f"适配后 assertion_code 重复: {code}")
                seen_codes.add(code)

                document = documents.get(passage.get("document_code", ""), {})
                flags = ["missing_candidate_episode_key"]
                if len(passage_refs) > 1:
                    flags.append("legacy_multi_passage_claim_fanned_out")
                if not fact.get("time_context"):
                    flags.append("missing_time_expression")
                if not fact.get("event_scope"):
                    flags.append("missing_location_expression")

                assertions.append(
                    AssertionDraft(
                        assertion_code=code,
                        source_passage_ref=passage_ref,
                        assertion_type=_TYPE_MAP[claim_kind],
                        subject=fact.get("actor") or claim.get("emperor_name", ""),
                        predicate=fact.get("action_type") or claim_kind,
                        object=fact.get("object") or claim.get("object_name", ""),
                        time_expression=fact.get("time_context") or None,
                        location_expression=None,
                        qualifiers={
                            "legacy_claim_kind": claim_kind,
                            "legacy_claim_summary": claim.get("claim_summary", ""),
                            "event_scope": fact.get("event_scope") or None,
                            "office_or_domain": fact.get("office_or_domain") or None,
                            "outcome": fact.get("outcome") or None,
                            "cost_or_damage": fact.get("cost_or_damage") or None,
                            "evidence_spans": tuple(claim.get("evidence_spans") or ()),
                        },
                        polarity="disputed" if claim_kind == "counter_claim" else "asserted",
                        source_attribution={
                            "document_title": document.get("title"),
                            "document_code": passage.get("document_code"),
                            "locator": passage.get("locator"),
                            "source_slice_ref": passage.get("slice_code"),
                        },
                        candidate_episode_key=None,
                        confidence=float(claim.get("confidence", 0.0)),
                        ambiguity_flags=tuple(flags),
                        extraction_provenance={
                            "legacy_claim_code": legacy_code,
                            "legacy_claim_run": claim_run,
                            "captured_from_release": snapshot.get("captured_from_release"),
                        },
                    )
                )

    return tuple(assertions)
