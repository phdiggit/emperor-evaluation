from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext,
    read_wikisource_snapshot,
    write_wikisource_snapshot,
)
from emperor_v4.contracts.source import SOURCE_CACHE_CONTRACT_V2
from emperor_v4.domain.source_segmentation import (
    PassageLinkSeed,
    PassageSeed,
    SourceSection,
    WindowPolicy,
    slice_source_section,
)


_FORBIDDEN_MANIFEST_FIELDS = frozenset(
    {
        "acceptance_decision",
        "candidate_boundary_key",
        "episode_code",
        "expected_participants",
        "gold_episodes",
        "gold_boundary",
        "gold_linkage",
        "gold_relations",
        "gold_rule_evidence_units",
        "must_merge",
        "must_not_merge",
        "expected_episode_boundary",
    }
)


def _load_yaml(path: Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"YAML root 必须为 mapping: {path}")
    return payload


def _forbidden_fields(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        found.update(_FORBIDDEN_MANIFEST_FIELDS & set(value))
        for child in value.values():
            found.update(_forbidden_fields(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_forbidden_fields(child))
    return found


def _reject_oracle_fields(value: Any, *, label: str) -> None:
    forbidden = _forbidden_fields(value)
    if forbidden:
        raise ValueError(f"{label} 含 Gold/boundary 字段: {sorted(forbidden)}")


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("status") != "open_development_source_recovery":
        raise ValueError("source development manifest 状态不允许执行")
    _reject_oracle_fields(manifest, label="source development manifest")
    pages = tuple(manifest.get("source_pages") or ())
    passages = tuple(manifest.get("passages") or ())
    page_codes = [str(row.get("page_code") or "") for row in pages]
    claim_codes = [str(row.get("claim_code") or "") for row in passages]
    if (
        not pages
        or not passages
        or "" in page_codes
        or "" in claim_codes
        or len(page_codes) != len(set(page_codes))
        or len(claim_codes) != len(set(claim_codes))
    ):
        raise ValueError("source development page_code/claim_code 必须非空且唯一")


def fetch_source_development_snapshots(
    manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    _validate_manifest(manifest)
    snapshots = []
    for page in manifest["source_pages"]:
        snapshot = fetch_wikisource_plaintext(
            page_code=str(page["page_code"]),
            page_title=str(page["page_title"]),
            expected_revision_id=(
                int(page["expected_revision_id"])
                if page.get("expected_revision_id") is not None
                else None
            ),
        )
        write_wikisource_snapshot(snapshot, output_dir / f"{snapshot.page_code}.json")
        snapshots.append(snapshot)
    return {
        "schema_version": 1,
        "status": "source_development_snapshots_fetched",
        "dataset_code": manifest.get("dataset_code"),
        "snapshot_count": len(snapshots),
        "snapshots": [
            {
                "page_code": item.page_code,
                "canonical_title": item.canonical_title,
                "canonical_url": item.canonical_url,
                "revision_id": item.revision_id,
                "revision_timestamp": item.revision_timestamp,
                "content_hash": item.content_hash,
            }
            for item in snapshots
        ],
        "safety": {
            "network_request_count": len(snapshots),
            "database_write_count": 0,
            "v3_runtime_started": False,
        },
    }


def _unique_anchor(text: str, anchor: str, *, after: int = 0) -> int:
    first = text.find(anchor, after)
    if first < 0:
        raise ValueError(f"source anchor 未找到: {anchor}")
    second = text.find(anchor, first + len(anchor))
    if second >= 0:
        raise ValueError(f"source anchor 不唯一: {anchor}")
    return first


def _claim_index(snapshot: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    claims = {}
    rulers = {}
    for person in snapshot.get("people") or ():
        ruler = str(person.get("ruler") or "")
        for claim in (person.get("payload") or {}).get("claims") or ():
            code = str(claim.get("claim_code") or "")
            if not code or code in claims:
                raise ValueError("claim snapshot claim_code 缺失或重复")
            claims[code] = dict(claim)
            rulers[code] = ruler
    return claims, rulers


def _document_id(snapshot: WikisourcePageSnapshot) -> str:
    identity = f"{snapshot.canonical_title}\x1f{snapshot.revision_id}"
    return "WSD-" + sha256(identity.encode("utf-8")).hexdigest()[:20].upper()


def materialize_source_development_input(
    *,
    manifest_path: Path,
    claim_snapshot: Mapping[str, Any],
    snapshot_dir: Path,
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    _validate_manifest(manifest)
    _reject_oracle_fields(claim_snapshot, label="claim snapshot")
    claims, rulers = _claim_index(claim_snapshot)
    page_specs = {
        str(row["page_code"]): row for row in manifest["source_pages"]
    }
    snapshots = {
        page_code: read_wikisource_snapshot(snapshot_dir / f"{page_code}.json")
        for page_code in page_specs
    }
    for page_code, page in page_specs.items():
        snapshot = snapshots[page_code]
        expected = page.get("expected_revision_id")
        if expected is not None and snapshot.revision_id != int(expected):
            raise ValueError(f"snapshot revision 与 manifest 不一致: {page_code}")

    specs_by_page: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for passage in manifest["passages"]:
        claim_code = str(passage["claim_code"])
        page_code = str(passage.get("page_code") or "")
        if claim_code not in claims or page_code not in page_specs:
            raise ValueError(f"passage spec 引用了未知 claim/page: {claim_code}/{page_code}")
        specs_by_page[page_code].append(passage)

    passage_by_claim = {}
    source_passages = []
    for page_code, passage_specs in sorted(specs_by_page.items()):
        page = page_specs[page_code]
        snapshot = snapshots[page_code]
        section = SourceSection(
            document_cache_id=_document_id(snapshot),
            content_version=f"revision:{snapshot.revision_id}:{snapshot.content_hash}",
            section_id=str(page["section_id"]),
            section_heading=str(page["section_heading"]),
            raw_text=snapshot.raw_text,
        )
        seeds = []
        for passage in passage_specs:
            start_anchor = str(passage.get("anchor_start") or "")
            end_anchor = str(passage.get("anchor_end") or "")
            start = _unique_anchor(snapshot.raw_text, start_anchor)
            end_start = _unique_anchor(snapshot.raw_text, end_anchor, after=start)
            end = end_start + len(end_anchor)
            seeds.append(
                PassageSeed(
                    seed_code=str(passage["claim_code"]),
                    anchor_start=start,
                    anchor_end=end,
                    passage_kind=str(passage.get("passage_kind") or "atomic"),
                    selection_reason=(
                        f"claim:{passage['claim_code']}",
                        *tuple(passage.get("selection_reason") or ()),
                    ),
                    links=tuple(
                        PassageLinkSeed(
                            target_seed_code=str(link["target_claim_code"]),
                            relation=str(link["relation"]),
                        )
                        for link in passage.get("linked_claims") or ()
                    ),
                )
            )
        policy = WindowPolicy(
            version=str(manifest["window_policy_version"]),
            sentence_radius_before=int(manifest.get("sentence_radius_before") or 0),
            sentence_radius_after=int(manifest.get("sentence_radius_after") or 0),
            context_chars_before=int(manifest.get("context_chars_before") or 160),
            context_chars_after=int(manifest.get("context_chars_after") or 160),
        )
        sliced = slice_source_section(section, seeds, policy)
        passage_by_seed = {
            seed.seed_code: next(
                item
                for item in sliced
                if item.selection_reason[0] == f"claim:{seed.seed_code}"
            )
            for seed in seeds
        }
        for spec in passage_specs:
            claim_code = str(spec["claim_code"])
            item = passage_by_seed[claim_code]
            passage_by_claim[claim_code] = item
            source_passages.append(
                {
                    "passage_code": item.passage_cache_id,
                    "document_code": item.document_cache_id,
                    "locator": item.locator,
                    "raw_text": item.raw_text,
                    "context_before": item.context_before,
                    "context_after": item.context_after,
                    "content_hash": item.content_hash,
                    "selection_reason": list(item.selection_reason),
                    "contract_version": SOURCE_CACHE_CONTRACT_V2,
                    "content_version": item.content_version,
                    "section_id": item.section_id,
                    "section_heading": item.section_heading,
                    "span_start": item.span_start,
                    "span_end": item.span_end,
                    "passage_kind": item.passage_kind,
                    "linked_passages": [asdict(link) for link in item.linked_passages],
                    "overlap_group": item.overlap_group,
                    "window_policy_version": item.window_policy_version,
                    "source_provenance": {
                        "origin": "wikisource_revision_snapshot",
                        "page_code": page_code,
                        "revision_id": snapshot.revision_id,
                        "canonical_url": snapshot.canonical_url,
                    },
                }
            )

    assertions = []
    passage_specs = {str(row["claim_code"]): row for row in manifest["passages"]}
    for claim_code in sorted(passage_by_claim):
        claim = claims[claim_code]
        fact = claim.get("fact_payload") or {}
        passage = passage_by_claim[claim_code]
        spec = passage_specs[claim_code]
        actor = str(fact.get("actor") or claim.get("emperor_name") or "")
        assertions.append(
            {
                "assertion_code": f"K0-A-{claim_code}@{passage.passage_cache_id}",
                "source_passage_ref": passage.passage_cache_id,
                "assertion_type": "event_fact",
                "subject": actor,
                "predicate": str(fact.get("action_type") or "historical_action"),
                "object": str(fact.get("object") or claim.get("object_name") or ""),
                "time_expression": fact.get("time_context") or None,
                "location_expression": spec.get("location_expression") or None,
                "qualifiers": {
                    "evaluation_context": rulers[claim_code],
                    "focal_person_ref": claim.get("object_name"),
                    "episode_type": fact.get("fact_schema"),
                    "responsibility_family": fact.get("responsibility_family"),
                    "office_or_domain": fact.get("office_or_domain"),
                    "normalized_time": fact.get("normalized_time") or {},
                    "outcome": fact.get("outcome") or None,
                    "legacy_claim_summary": claim.get("claim_summary"),
                },
                "polarity": "asserted",
                "source_attribution": {
                    "document_code": passage.document_cache_id,
                    "source_slice_ref": passage.passage_cache_id,
                },
                "confidence": float(claim.get("confidence") or 0.0),
                "ambiguity_flags": list(spec.get("ambiguity_flags") or ()),
                "passage_support": {
                    "support_mode": "single_passage",
                    "assertion_semantic_key": claim_code,
                    "supported_fields": list(spec.get("supported_fields") or ()),
                    "binding_provenance": {
                        "contract": "assertion-extraction-contract-v2",
                        "review_status": "open_development_source_review",
                    },
                },
                "extraction_provenance": {
                    "origin": "retrieval_v3_claim_rebound_to_v4_source_v2",
                    "legacy_claim_code": claim_code,
                    "legacy_passage_refs": list(claim.get("source_passage_refs") or ()),
                },
            }
        )

    source_documents = []
    for page_code, page in sorted(page_specs.items()):
        snapshot = snapshots[page_code]
        source_documents.append(
            {
                "document_cache_id": _document_id(snapshot),
                "work_identity": page["work_identity"],
                "edition_identity": page["edition_identity"],
                "title": snapshot.canonical_title,
                "url": snapshot.canonical_url,
                "source_role": page["source_role"],
                "retrieved_at": snapshot.retrieved_at,
                "content_hash": snapshot.content_hash,
                "http_metadata": {
                    "revision_id": snapshot.revision_id,
                    "revision_timestamp": snapshot.revision_timestamp,
                },
                "license_or_access_note": "Wikisource public-domain text; carrier CC BY-SA 4.0",
            }
        )
    return {
        "schema_version": 2,
        "dataset_code": manifest["dataset_code"],
        "assertion_input_contract": "passage-scoped-assertion-v2",
        "source_cache_contract": SOURCE_CACHE_CONTRACT_V2,
        "source_documents": source_documents,
        "source_passages": sorted(source_passages, key=lambda row: row["passage_code"]),
        "assertions": assertions,
        "canonical_people": claim_snapshot.get("canonical_people") or [],
        "collection_provenance": {
            "source_mode": "wikisource_revision_snapshot",
            "network_request_count": 0,
            "database_write_count": 0,
            "gold_accessed": False,
            "boundary_review_started": False,
        },
    }
