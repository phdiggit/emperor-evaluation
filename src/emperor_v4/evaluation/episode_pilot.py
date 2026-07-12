from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

import yaml

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
)
from emperor_v4.application.reconcile_episode import reconcile_episode_candidates


_SOURCE_TRANSLATION = str.maketrans(
    {
        "舊": "旧",
        "書": "书",
        "記": "记",
        "鑑": "鉴",
        "實": "实",
        "錄": "录",
        "語": "语",
        "資": "资",
    }
)


def _load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> Mapping[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _source_identity(value: str) -> str:
    normalized = value.translate(_SOURCE_TRANSLATION).strip().strip("/")
    if normalized.startswith("zh-hant/"):
        normalized = normalized.removeprefix("zh-hant/")
    if normalized.startswith("wiki/"):
        normalized = normalized.removeprefix("wiki/")
    return normalized


def _required_identity(passage: Mapping[str, Any]) -> str:
    url = passage.get("url") or ""
    if url:
        return _source_identity(unquote(urlsplit(url).path))
    return _source_identity(str(passage.get("source_title") or ""))


def evaluate_episode_pilot(
    manifest_path: Path,
    fixture_dir: Path,
    linkage_path: Path | None = None,
    source_supplement_path: Path | None = None,
    claim_supplement_path: Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    manifest = _load_yaml(manifest_path)
    source_snapshot = _load_json(fixture_dir / "source-cache-response.json")
    claim_snapshot = _load_json(fixture_dir / "claim-extractor-response.json")

    source = adapt_source_cache_snapshot(source_snapshot)
    assertions = adapt_claim_extractor_snapshot(claim_snapshot)
    packets = reconcile_episode_candidates(assertions)
    packet_fingerprints = {packet.semantic_fingerprint for packet in packets}

    frozen_codes = set(manifest.get("frozen_episode_codes") or ())
    frozen_episodes = [
        episode
        for episode in manifest.get("episodes", [])
        if episode.get("episode_code") in frozen_codes
    ]
    baseline_actual_by_ruler = {
        person.get("ruler"): {
            _source_identity(document.get("title") or "")
            for document in person.get("payload", {}).get("source_documents", [])
        }
        for person in source_snapshot.get("people", [])
    }
    actual_by_ruler = {
        ruler: set(identities) for ruler, identities in baseline_actual_by_ruler.items()
    }
    source_supplement: Mapping[str, Any] | None = None
    if source_supplement_path is not None:
        source_supplement = _load_json(source_supplement_path)
        for document in source_supplement.get("documents", []):
            ruler = document.get("ruler")
            if ruler:
                actual_by_ruler.setdefault(ruler, set()).add(
                    _source_identity(document.get("title") or "")
                )
    claim_supplement: Mapping[str, Any] | None = None
    supplement_assertions = ()
    supplement_packets = ()
    supplement_used_slices: set[str] = set()
    if claim_supplement_path is not None:
        claim_supplement = _load_json(claim_supplement_path)
        supplement_assertions = adapt_claim_extractor_snapshot(claim_supplement)
        supplement_packets = reconcile_episode_candidates(supplement_assertions)
        supplement_used_slices = {
            ref
            for person in claim_supplement.get("people", [])
            for claim in person.get("payload", {}).get("claims", [])
            for ref in claim.get("source_slice_refs", [])
        }
    required_rows: list[dict[str, Any]] = []
    for episode in frozen_episodes:
        for passage in episode.get("required_source_passages", []):
            identity = _required_identity(passage)
            required_rows.append(
                {
                    "episode_code": episode.get("episode_code"),
                    "ruler": episode.get("ruler"),
                    "required_source_identity": identity,
                    "matched_in_baseline": identity
                    in baseline_actual_by_ruler.get(episode.get("ruler"), set()),
                    "matched": identity in actual_by_ruler.get(episode.get("ruler"), set()),
                }
            )

    matched_rows = [row for row in required_rows if row["matched"]]
    baseline_matched_rows = [row for row in required_rows if row["matched_in_baseline"]]
    assertion_codes = {assertion.assertion_code for assertion in assertions}
    linked_codes = {
        link.assertion_ref for packet in packets for link in packet.assertion_links
    }
    linkage: Mapping[str, Any] | None = None
    if linkage_path is not None:
        linkage = _load_yaml(linkage_path)
        decisions = linkage.get("candidate_decisions") or {}
        decision_fingerprints = set(decisions)
        if decision_fingerprints != packet_fingerprints:
            missing = sorted(packet_fingerprints - decision_fingerprints)
            unknown = sorted(decision_fingerprints - packet_fingerprints)
            raise ValueError(
                "linkage candidate set 与 kernel 输出不一致: "
                f"missing={missing}, unknown={unknown}"
            )
        fingerprint_text = "\n".join(sorted(packet_fingerprints)) + "\n"
        fingerprint_hash = hashlib.sha256(fingerprint_text.encode("utf-8")).hexdigest()
        if fingerprint_hash != linkage.get("candidate_fingerprint_set_sha256"):
            raise ValueError("linkage candidate fingerprint set hash 不一致")

        allowed_decisions = set(linkage.get("decision_vocabulary") or {})
        unknown_decisions = sorted(
            {
                item.get("decision")
                for item in decisions.values()
                if item.get("decision") not in allowed_decisions
            }
        )
        if unknown_decisions:
            raise ValueError(f"linkage 包含未知 decision: {unknown_decisions}")

    elapsed = time.perf_counter() - started

    if linkage is None:
        episode_recall: dict[str, Any] = {
            "status": "not_computable_missing_gold_linkage",
            "value": None,
            "reason": "冻结 fixture 尚无 assertion/packet 到 gold episode_code 的人工映射。",
        }
        accepted_precision: dict[str, Any] = {
            "status": "not_computable_missing_gold_linkage",
            "value": None,
        }
        merge_split: dict[str, Any] = {
            "status": "not_computable_missing_gold_linkage",
            "wrong_merge_count": None,
            "wrong_split_count": None,
        }
        linkage_integrity: dict[str, Any] = {
            "status": "missing",
            "mapped_candidate_count": 0,
            "mapping_coverage": 0.0,
        }
        human_review_pending: list[Any] = [
            {
                "episode_code": episode.get("episode_code"),
                "task": "map assertion drafts and candidate packets to gold boundary",
            }
            for episode in frozen_episodes
        ]
        linkage_failure_count = len(frozen_episodes)
    else:
        decisions = linkage["candidate_decisions"]
        full_codes = {
            code
            for item in decisions.values()
            if item["decision"] == "full_match"
            for code in item.get("gold_episode_codes", [])
            if code in frozen_codes
        }
        partial_codes = {
            code
            for item in decisions.values()
            if item["decision"] == "partial_support"
            for code in item.get("gold_episode_codes", [])
            if code in frozen_codes
        }
        relevant_candidate_count = sum(
            item["decision"] in {"full_match", "partial_support"}
            for item in decisions.values()
        )
        episode_recall = {
            "status": f"preliminary_{linkage.get('status')}",
            "full_match_episode_count": len(full_codes),
            "frozen_episode_count": len(frozen_codes),
            "value": len(full_codes) / len(frozen_codes) if frozen_codes else None,
            "partial_boundary_episode_count": len(partial_codes),
            "partial_boundary_coverage": (
                len(partial_codes) / len(frozen_codes) if frozen_codes else None
            ),
            "any_candidate_support_episode_count": len(full_codes | partial_codes),
            "any_candidate_support_coverage": (
                len(full_codes | partial_codes) / len(frozen_codes)
                if frozen_codes
                else None
            ),
            "warning": "partial_support 不计入 full recall；linkage 通过人工 Gate 前指标不是 accepted 结果。",
        }
        accepted_precision = {
            "status": "not_applicable_no_accepted_packets",
            "value": None,
            "candidate_relevance_rate": (
                relevant_candidate_count / len(packets) if packets else None
            ),
            "relevant_candidate_count": relevant_candidate_count,
            "candidate_packet_count": len(packets),
        }
        merge_split = {
            "status": "review_required",
            "confirmed_wrong_merge_count": len(
                linkage.get("confirmed_wrong_merge_fingerprints") or ()
            ),
            "confirmed_wrong_split_count": len(
                linkage.get("confirmed_wrong_split_gold_episode_codes") or ()
            ),
            "assessments": linkage.get("merge_split_assessments") or [],
            "warning": "零个 confirmed error 不表示 merge/split Gate 已通过。",
        }
        linkage_integrity = {
            "status": linkage.get("status"),
            "mapped_candidate_count": len(decisions),
            "candidate_packet_count": len(packets),
            "mapping_coverage": len(decisions) / len(packets) if packets else None,
            "candidate_fingerprint_set_sha256": linkage.get(
                "candidate_fingerprint_set_sha256"
            ),
            "acceptance_gate": linkage.get("acceptance_gate"),
        }
        human_review_pending = [
            {
                "episode_code": code,
                "task": "no full or partial packet support in frozen fixture",
            }
            for code in sorted(frozen_codes - full_codes - partial_codes)
        ]
        human_review_pending.extend(
            {"task": requirement}
            for requirement in linkage.get("acceptance_gate", {}).get("requirements", [])
        )
        linkage_failure_count = 0

    return {
        "report_schema_version": 1,
        "evaluation": "episode_pilot",
        "manifest_code": manifest.get("manifest_code"),
        "fixture_release": source_snapshot.get("captured_from_release"),
        "execution_mode": "offline_read_only_deterministic",
        "source_coverage": {
            "status": "document_identity_proxy_only",
            "required_passage_count": len(required_rows),
            "baseline_matched_required_document_count": len(baseline_matched_rows),
            "baseline_rate": (
                len(baseline_matched_rows) / len(required_rows) if required_rows else None
            ),
            "matched_required_document_count": len(matched_rows),
            "rate": len(matched_rows) / len(required_rows) if required_rows else None,
            "matched": matched_rows,
            "missing": [row for row in required_rows if not row["matched"]],
            "caveat": "文献身份命中不等于 passage 已覆盖 gold boundary。",
            "supplement_fixture_applied": source_supplement is not None,
        },
        "episode_recall": episode_recall,
        "accepted_episode_precision": accepted_precision,
        "merge_split": merge_split,
        "linkage_integrity": linkage_integrity,
        "consumption_integrity": {
            "assertion_count": len(assertion_codes),
            "linked_assertion_count": len(linked_codes),
            "unlinked_assertion_count": len(assertion_codes - linked_codes),
            "rate": len(linked_codes) / len(assertion_codes) if assertion_codes else None,
        },
        "kernel_output": {
            "source_document_draft_count": len(source.documents),
            "source_passage_count": len(source.passages),
            "source_document_contract_gap_count": len(source.contract_gaps),
            "assertion_draft_count": len(assertions),
            "episode_candidate_packet_count": len(packets),
            "supplement_source_document_count": (
                len(source_supplement.get("documents", [])) if source_supplement else 0
            ),
            "supplement_source_passage_count": (
                len(source_supplement.get("passages", [])) if source_supplement else 0
            ),
            "supplement_assertion_draft_count": len(supplement_assertions),
            "supplement_episode_candidate_packet_count": len(supplement_packets),
        },
        "cost": {
            "network_request_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
            "cache_hit_rate": None,
            "wall_clock_seconds": round(elapsed, 6),
        },
        "fixture_generation_cost": {
            "source_network_fetch_count_final_rerun": (
                source_supplement.get("network_fetch_count")
                if source_supplement
                else None
            ),
            "claim_model_call_count_initial_run": (
                claim_supplement.get("model_call_count")
                if claim_supplement
                else None
            ),
            "claim_database_import_performed": (
                claim_supplement.get("database_import_performed")
                if claim_supplement
                else None
            ),
        },
        "failure_attribution": {
            "source_cache_missing_required_document": len(required_rows) - len(matched_rows),
            "source_metadata_contract_gap": len(source.contract_gaps),
            "assertion_extraction_pending_supplement_passage": (
                len(
                    {
                        item.get("passage_cache_id")
                        for item in source_supplement.get("passages", [])
                    }
                    - supplement_used_slices
                )
                if source_supplement
                else 0
            ),
            "supplement_assertion_gold_linkage_pending": len(supplement_assertions),
            "episode_gold_linkage_missing": linkage_failure_count,
            "gold_boundary_without_full_match": (
                episode_recall.get("frozen_episode_count", len(frozen_episodes))
                - episode_recall.get("full_match_episode_count", 0)
            ),
            "gold_boundary_without_partial_support": (
                episode_recall.get("frozen_episode_count", len(frozen_episodes))
                - episode_recall.get("any_candidate_support_episode_count", 0)
            ),
        },
        "human_review_pending": human_review_pending,
    }
