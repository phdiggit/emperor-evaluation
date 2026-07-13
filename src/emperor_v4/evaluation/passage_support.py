from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict
from typing import Any, Mapping

from emperor_v4.adapters import adapt_claim_extractor_snapshot
from emperor_v4.evaluation.blind_holdout import validate_blind_kernel_input


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def materialize_passage_scoped_blind_input(
    source_snapshot: Mapping[str, Any],
    support_review: Mapping[str, Any],
) -> dict[str, Any]:
    if support_review.get("status") != "frozen_before_episode_review":
        raise ValueError("PassageSupport review 尚未冻结")
    if support_review.get("reviewed_without_episode_gold_or_candidates") is not True:
        raise ValueError("PassageSupport review 未声明 Episode Gold/candidate 隔离")
    source_hash = canonical_payload_hash(source_snapshot)
    if support_review.get("source_snapshot_sha256") != source_hash:
        raise ValueError("PassageSupport review 与 source snapshot hash 不一致")

    snapshot = copy.deepcopy(source_snapshot)
    snapshot["adapter_target_contract"] = "assertion-extraction-contract-v2"
    claims: dict[str, dict[str, Any]] = {}
    passages: dict[str, Mapping[str, Any]] = {}
    for person in snapshot.get("people") or ():
        payload = person.get("payload") or {}
        for passage in payload.get("passages") or ():
            code = str(passage.get("passage_code") or "")
            if not code:
                raise ValueError("source snapshot passage 缺少 code")
            previous = passages.setdefault(code, passage)
            if previous != passage:
                raise ValueError(f"source snapshot passage code 冲突: {code}")
        for claim in payload.get("claims") or ():
            code = str(claim.get("claim_code") or "")
            if not code or code in claims:
                raise ValueError(f"source snapshot claim code 缺少或重复: {code}")
            claims[code] = claim

    review_rows = support_review.get("claim_support_reviews") or ()
    reviews: dict[str, Mapping[str, Any]] = {}
    for row in review_rows:
        code = str(row.get("claim_code") or "")
        if not code or code in reviews:
            raise ValueError(f"PassageSupport review claim code 缺少或重复: {code}")
        reviews[code] = row
    if set(reviews) != set(claims):
        raise ValueError("PassageSupport review 未完整且唯一覆盖 source claims")

    for claim_code, claim in claims.items():
        bindings = reviews[claim_code].get("passage_support_bindings") or ()
        claim["passage_support_bindings"] = copy.deepcopy(list(bindings))

    assertions = adapt_claim_extractor_snapshot(snapshot)
    source_passages = [
        {
            "passage_code": code,
            "document_code": passage.get("document_code"),
            "locator": passage.get("locator"),
            "raw_text": passage.get("raw_text") or passage.get("text") or "",
            "content_hash": passage.get("content_hash"),
            "source_provenance": passage.get("source_provenance") or {},
        }
        for code, passage in sorted(passages.items())
    ]
    assertion_rows = []
    for assertion in assertions:
        row = asdict(assertion)
        row.pop("candidate_episode_key", None)
        assertion_rows.append(row)
    result = {
        "schema_version": 1,
        "dataset_code": source_snapshot.get("dataset_code"),
        "assertion_input_contract": "passage-scoped-assertion-v2",
        "collection_provenance": {
            **(source_snapshot.get("collection_provenance") or {}),
            "passage_support_review_sha256": canonical_payload_hash(support_review),
        },
        "canonical_people": copy.deepcopy(
            list(source_snapshot.get("canonical_people") or ())
        ),
        "source_passages": source_passages,
        "assertions": assertion_rows,
    }
    validate_blind_kernel_input(result)
    return result
