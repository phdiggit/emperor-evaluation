from __future__ import annotations

import re
from typing import Any, Mapping

from emperor_v4.contracts.assertion import AssertionDraft, PassageSupport


_TYPE_MAP = {
    "material_claim": "event_fact",
    "context_claim": "context_fact",
    "counter_claim": "causal_claim",
}


def _participant_names(value: object) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        name.strip()
        for name in re.split(r"[、,，/]", str(value))
        if name.strip()
    )


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


def _passage_semantic_payload(assertion: AssertionDraft) -> tuple[object, ...]:
    qualifiers = assertion.qualifiers
    normalized_time = qualifiers.get("normalized_time") or {}
    return (
        assertion.subject,
        assertion.predicate,
        assertion.object,
        assertion.time_expression,
        assertion.location_expression,
        qualifiers.get("responsibility_family"),
        qualifiers.get("office_or_domain"),
        qualifiers.get("outcome"),
        qualifiers.get("cost_or_damage"),
        tuple(sorted(normalized_time.items())) if isinstance(normalized_time, Mapping) else (),
        assertion.polarity,
    )


def _validate_v2_claim_support(
    claim_code: str,
    passage_refs: tuple[str, ...],
    assertions: tuple[AssertionDraft, ...],
) -> None:
    by_key: dict[str, list[AssertionDraft]] = {}
    for assertion in assertions:
        support = assertion.passage_support
        if support is None:
            raise ValueError(f"v2 claim passage 缺少 PassageSupport: {claim_code}")
        by_key.setdefault(support.assertion_semantic_key, []).append(assertion)
    if len(passage_refs) == 1:
        if assertions[0].passage_support.support_mode not in {
            "single_passage",
            "atomic_component",
            "context_only",
        }:
            raise ValueError(f"单 passage claim 使用了错误 support mode: {claim_code}")
        return
    for semantic_key, items in by_key.items():
        modes = {item.passage_support.support_mode for item in items}
        if len(items) > 1:
            if modes != {"equivalent_evidence"}:
                raise ValueError(
                    f"同一 assertion_semantic_key 的多 passage 必须声明 equivalent_evidence: "
                    f"{claim_code}/{semantic_key}"
                )
            if len({_passage_semantic_payload(item) for item in items}) != 1:
                raise ValueError(
                    f"equivalent_evidence 的逐 passage 语义不一致: {claim_code}/{semantic_key}"
                )
        elif next(iter(modes)) not in {"atomic_component", "context_only"}:
            raise ValueError(
                f"多 passage claim 的单独语义分量必须声明 atomic_component/context_only: "
                f"{claim_code}/{semantic_key}"
            )


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
            focal_names = (
                _participant_names(claim.get("object_name"))
                or (
                    _participant_names(fact.get("object"))
                    if claim.get("object_type") == "person"
                    else ()
                )
            )
            target_contract = snapshot.get("adapter_target_contract")
            support_bindings: dict[str, Mapping[str, Any]] = {}
            if target_contract == "assertion-extraction-contract-v2":
                for binding in claim.get("passage_support_bindings") or ():
                    ref = str(binding.get("source_passage_ref") or "")
                    if not ref or ref in support_bindings:
                        raise ValueError(f"v2 claim support binding 缺少或重复 passage ref: {claim.get('claim_code', '')}")
                    support_bindings[ref] = binding
                if set(support_bindings) != set(passage_refs):
                    raise ValueError(
                        f"v2 claim support binding 未完整且唯一覆盖 passages: {claim.get('claim_code', '')}"
                    )
            claim_assertions: list[AssertionDraft] = []
            for passage_ref in passage_refs:
                passage = passages.get(passage_ref)
                if passage is None:
                    raise ValueError(f"claim 引用了未知 passage: {passage_ref}")
                binding = support_bindings.get(passage_ref)
                fact_for_passage = dict(fact)
                if binding is not None:
                    overrides = binding.get("fact_overrides") or {}
                    if not isinstance(overrides, Mapping):
                        raise ValueError("v2 fact_overrides 必须是 object")
                    fact_for_passage.update(overrides)
                location_expression = (
                    fact_for_passage.get("location_expression")
                    or fact_for_passage.get("location")
                    or fact_for_passage.get("structured_place")
                )
                if target_contract in {
                    "assertion-extraction-contract-v1",
                    "assertion-extraction-contract-v2",
                }:
                    participant_roles = {
                        (person.get("ruler"), "ruler"),
                        *(
                            (name, "actor")
                            for name in _participant_names(fact_for_passage.get("actor"))
                        ),
                        *(
                            (name, "subject_person")
                            for name in _participant_names(fact_for_passage.get("object"))
                            if claim.get("object_type") == "person"
                        ),
                        *(
                            (name, "focus_person")
                            for name in _participant_names(claim.get("object_name"))
                        ),
                    }
                    participant_roles.discard((None, "ruler"))
                else:
                    participant_roles = {
                        (person.get("ruler"), "ruler"),
                        (claim.get("object_name"), "subject_person"),
                    }
                legacy_code = claim.get("claim_code", "")
                code = f"{claim_run}@{legacy_code}"
                if len(passage_refs) > 1:
                    code = f"{code}@{passage_ref}"
                if code in seen_codes:
                    raise ValueError(f"适配后 assertion_code 重复: {code}")
                seen_codes.add(code)

                document = documents.get(passage.get("document_code", ""), {})
                flags = ["missing_candidate_episode_key"]
                if len(passage_refs) > 1 and target_contract != "assertion-extraction-contract-v2":
                    flags.append("legacy_multi_passage_claim_fanned_out")
                if not fact_for_passage.get("time_context"):
                    flags.append("missing_time_expression")
                if not location_expression:
                    flags.append("missing_location_expression")
                if len(focal_names) != 1:
                    flags.append("missing_focal_person_ref")

                qualifiers = {
                    "evaluation_context": person.get("ruler"),
                    "candidate_participant_roles": tuple(sorted(participant_roles)),
                    "episode_type": "political_action",
                    "responsibility_family": fact_for_passage.get("responsibility_family")
                    or "political_action",
                    "legacy_claim_kind": claim_kind,
                    "legacy_claim_summary": claim.get("claim_summary", ""),
                    "event_scope": fact_for_passage.get("event_scope") or None,
                    "office_or_domain": fact_for_passage.get("office_or_domain") or None,
                    "outcome": fact_for_passage.get("outcome") or None,
                    "cost_or_damage": fact_for_passage.get("cost_or_damage") or None,
                    "evidence_spans": tuple(claim.get("evidence_spans") or ()),
                }
                if len(focal_names) == 1:
                    qualifiers["focal_person_ref"] = focal_names[0]
                    qualifiers["focal_role"] = "focus_person"
                if isinstance(fact_for_passage.get("normalized_time"), Mapping):
                    qualifiers["normalized_time"] = dict(fact_for_passage["normalized_time"])

                passage_support = None
                if binding is not None:
                    passage_support = PassageSupport(
                        support_mode=str(binding.get("support_mode") or ""),
                        assertion_semantic_key=str(binding.get("assertion_semantic_key") or ""),
                        supported_fields=tuple(binding.get("supported_fields") or ()),
                        binding_provenance={
                            "contract": "assertion-extraction-contract-v2",
                            "claim_code": legacy_code,
                        },
                    )
                claim_assertions.append(
                    AssertionDraft(
                        assertion_code=code,
                        source_passage_ref=passage_ref,
                        assertion_type=_TYPE_MAP[claim_kind],
                        subject=fact_for_passage.get("actor") or claim.get("emperor_name", ""),
                        predicate=fact_for_passage.get("action_type") or claim_kind,
                        object=fact_for_passage.get("object") or claim.get("object_name", ""),
                        time_expression=fact_for_passage.get("time_context") or None,
                        location_expression=location_expression or None,
                        qualifiers=qualifiers,
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
                            "claim_key": legacy_code,
                            "legacy_claim_run": claim_run,
                            "captured_from_release": snapshot.get("captured_from_release"),
                        },
                        passage_support=passage_support,
                    )
                )
            if target_contract == "assertion-extraction-contract-v2":
                _validate_v2_claim_support(
                    str(claim.get("claim_code") or ""),
                    passage_refs,
                    tuple(claim_assertions),
                )
            assertions.extend(claim_assertions)

    return tuple(assertions)
