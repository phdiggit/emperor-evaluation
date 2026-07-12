from __future__ import annotations

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
    }
)


def _load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
) -> dict[str, Any]:
    started = time.perf_counter()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    source_snapshot = _load_json(fixture_dir / "source-cache-response.json")
    claim_snapshot = _load_json(fixture_dir / "claim-extractor-response.json")

    source = adapt_source_cache_snapshot(source_snapshot)
    assertions = adapt_claim_extractor_snapshot(claim_snapshot)
    packets = reconcile_episode_candidates(assertions)

    frozen_codes = set(manifest.get("frozen_episode_codes") or ())
    frozen_episodes = [
        episode
        for episode in manifest.get("episodes", [])
        if episode.get("episode_code") in frozen_codes
    ]
    actual_by_ruler = {
        person.get("ruler"): {
            _source_identity(document.get("title") or "")
            for document in person.get("payload", {}).get("source_documents", [])
        }
        for person in source_snapshot.get("people", [])
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
                    "matched": identity in actual_by_ruler.get(episode.get("ruler"), set()),
                }
            )

    matched_rows = [row for row in required_rows if row["matched"]]
    assertion_codes = {assertion.assertion_code for assertion in assertions}
    linked_codes = {
        link.assertion_ref for packet in packets for link in packet.assertion_links
    }
    elapsed = time.perf_counter() - started

    return {
        "report_schema_version": 1,
        "evaluation": "episode_pilot",
        "manifest_code": manifest.get("manifest_code"),
        "fixture_release": source_snapshot.get("captured_from_release"),
        "execution_mode": "offline_read_only_deterministic",
        "source_coverage": {
            "status": "document_identity_proxy_only",
            "required_passage_count": len(required_rows),
            "matched_required_document_count": len(matched_rows),
            "rate": len(matched_rows) / len(required_rows) if required_rows else None,
            "matched": matched_rows,
            "missing": [row for row in required_rows if not row["matched"]],
            "caveat": "文献身份命中不等于 passage 已覆盖 gold boundary。",
        },
        "episode_recall": {
            "status": "not_computable_missing_gold_linkage",
            "value": None,
            "reason": "冻结 fixture 尚无 assertion/packet 到 gold episode_code 的人工映射。",
        },
        "accepted_episode_precision": {
            "status": "not_computable_missing_gold_linkage",
            "value": None,
        },
        "merge_split": {
            "status": "not_computable_missing_gold_linkage",
            "wrong_merge_count": None,
            "wrong_split_count": None,
        },
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
        },
        "cost": {
            "network_request_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
            "cache_hit_rate": None,
            "wall_clock_seconds": round(elapsed, 6),
        },
        "failure_attribution": {
            "source_cache_missing_required_document": len(required_rows) - len(matched_rows),
            "source_metadata_contract_gap": len(source.contract_gaps),
            "episode_gold_linkage_missing": len(frozen_episodes),
        },
        "human_review_pending": [
            {
                "episode_code": episode.get("episode_code"),
                "task": "map assertion drafts and candidate packets to gold boundary",
            }
            for episode in frozen_episodes
        ],
    }
