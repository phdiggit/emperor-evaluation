from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_alias_pretag as alias_pretag
from scripts.dev import retrieval_v2_claim_quality as claim_quality


OWNER_AWARE_MODE = "owner_aware"
LEGACY_MODE = "legacy"
OWNER_ANCHOR_CLASSES = ("A", "B", "C", "D")
CLASS_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def text(value: Any) -> str:
    return str(value or "").strip()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def unique_strings(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def source_title_by_document(candidates: Mapping[str, Any]) -> dict[str, str]:
    return {
        text(row.get("document_code")): text(row.get("title") or row.get("source_title"))
        for row in candidates.get("source_documents") or []
        if isinstance(row, Mapping) and text(row.get("document_code"))
    }


def event_signal_terms(row: Mapping[str, Any]) -> list[str]:
    raw_text = text(row.get("text") or row.get("raw_text"))
    terms = [
        *[text(value) for value in row.get("matched_rule_terms") or []],
        *[text(value) for value in row.get("matched_outcome_terms") or []],
        *[text(value) for value in row.get("lead_terms") or []],
    ]
    object_cache = claim_quality.object_cache_row(row)
    terms.extend(text(value) for value in object_cache.get("lead_terms") or [])
    terms.extend(term for term in (*claim_quality.OPPORTUNITY_ACTION_TERMS, *claim_quality.OPPORTUNITY_OUTCOME_TERMS) if term in raw_text)
    return unique_strings(terms)


def eligible_requested_owner_mentions(
    row: Mapping[str, Any],
    *,
    requested_owner_name: str,
    source_title: str,
    resolver: alias_pretag.AliasResolver,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mentions = alias_pretag.alias_mentions_in_text(
        text(row.get("text") or row.get("raw_text")),
        requested_owner_name=requested_owner_name,
        source_title=source_title,
        resolver=resolver,
        include_suppressed=True,
    )
    owner_mentions = [
        dict(mention)
        for mention in mentions
        if text(mention.get("resolution_status")) == "resolved"
        and text(mention.get("resolved_owner_name")) == requested_owner_name
        and mention.get("owner_anchor_eligible") is not False
    ]
    return owner_mentions, [dict(mention) for mention in mentions]


def classify_candidate_slice(
    row: Mapping[str, Any],
    *,
    requested_owner_name: str,
    source_title: str,
    resolver: alias_pretag.AliasResolver,
) -> dict[str, Any]:
    annotated = json.loads(stable_json(row))
    eligibility = claim_quality.slice_claim_eligibility(annotated)
    owner_mentions, all_mentions = eligible_requested_owner_mentions(
        annotated,
        requested_owner_name=requested_owner_name,
        source_title=source_title,
        resolver=resolver,
    )
    signals = event_signal_terms(annotated)
    reason_codes: list[str] = []
    if eligibility.get("claim_eligible") is False:
        owner_class = "D"
        reason_codes.extend(f"ineligible:{text(reason)}" for reason in eligibility.get("reasons") or [] if text(reason))
    elif owner_mentions:
        owner_class = "A"
        reason_codes.append("eligible_requested_owner_anchor")
    elif claim_quality.biography_like_source(annotated) and signals:
        owner_class = "B"
        reason_codes.extend(("biography_or_object_source", "event_signal_without_owner_anchor"))
    else:
        owner_class = "C"
        reason_codes.append("deferred_low_signal_or_non_biography_material")
    if any(mention.get("resolution_status") != "resolved" for mention in all_mentions):
        reason_codes.append("ambiguous_alias_audit_only")
    if any(text(mention.get("suppression_reason")) for mention in all_mentions):
        reason_codes.append("suppressed_alias_audit_only")
    event_score = len(signals) * 10 + (40 if claim_quality.biography_like_source(annotated) else 0) + (100 if owner_class == "A" else 0)
    annotated["owner_anchor_class"] = owner_class
    annotated["owner_anchor_mentions"] = owner_mentions
    annotated["owner_anchor_eligible"] = bool(owner_mentions)
    annotated["event_signal_terms"] = signals
    annotated["event_signal_score"] = event_score
    annotated["selection_reason_codes"] = unique_strings(reason_codes)
    return annotated


def classify_candidates(candidates: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_owner = alias_pretag.candidate_requested_owner(candidates)
    titles = source_title_by_document(candidates)
    resolver = alias_pretag.load_alias_resolver()
    rows: list[dict[str, Any]] = []
    counts = {name: 0 for name in OWNER_ANCHOR_CLASSES}
    for raw_row in candidates.get("candidate_slices") or []:
        if not isinstance(raw_row, Mapping):
            continue
        document_code = text(raw_row.get("document_code"))
        source_title = text(raw_row.get("source_title")) or titles.get(document_code, "")
        row = classify_candidate_slice(
            raw_row,
            requested_owner_name=requested_owner,
            source_title=source_title,
            resolver=resolver,
        )
        if source_title and not text(row.get("source_title")):
            row["source_title"] = source_title
        counts[row["owner_anchor_class"]] += 1
        rows.append(row)
    return rows, {
        "requested_owner_name": requested_owner,
        "class_counts": counts,
        "classification": "mechanical_alias_resolution_and_candidate_quality_only; no_model_invocation",
    }


def slice_cost(row: Mapping[str, Any]) -> int:
    return len(text(row.get("text") or row.get("raw_text"))) + 180


def ordered_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            CLASS_RANK.get(text(row.get("object_bundle_class") or row.get("owner_anchor_class")), 9),
            text(row.get("document_code")),
            text(row.get("object_name")),
            -int(row.get("event_signal_score") or 0),
            text(row.get("slice_code")),
        ),
    )


def build_shards(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_objects_per_shard: int,
    max_slices_per_shard: int,
    max_chars_per_shard: int,
) -> list[dict[str, Any]]:
    shards: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    class_indexes: dict[str, int] = {name: 0 for name in OWNER_ANCHOR_CLASSES}
    object_packets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in ordered_rows(rows):
        owner_class = text(row.get("object_bundle_class") or row.get("owner_anchor_class"))
        if owner_class != "D":
            object_packets.setdefault((owner_class, text(row.get("object_name")) or text(row.get("slice_code"))), []).append(row)
    for (owner_class, object_name), packet in sorted(
        object_packets.items(),
        key=lambda item: (
            CLASS_RANK.get(item[0][0], 9),
            -sum(int(row.get("event_signal_score") or 0) for row in item[1]),
            item[0][1],
        ),
    ):
        packet_cost = sum(slice_cost(row) for row in packet)
        must_start_new = current is None or current["owner_anchor_class"] != owner_class
        if not must_start_new and current is not None:
            current_objects = set(current["object_names"])
            exceeds_objects = max_objects_per_shard > 0 and object_name not in current_objects and len(current_objects) >= max_objects_per_shard
            exceeds_slices = max_slices_per_shard > 0 and len(current["slice_codes"]) + len(packet) > max_slices_per_shard
            exceeds_chars = max_chars_per_shard > 0 and current["estimated_slice_chars"] + packet_cost > max_chars_per_shard
            must_start_new = exceeds_objects or exceeds_slices or exceeds_chars
        if must_start_new:
            class_indexes[owner_class] += 1
            current = {
                "shard_code": f"CSH-{owner_class}-{class_indexes[owner_class]:02d}",
                "owner_anchor_class": owner_class,
                "object_names": [],
                "slice_codes": [],
                "estimated_slice_chars": 0,
                "event_signal_score": 0,
            }
            shards.append(current)
        if object_name and object_name not in current["object_names"]:
            current["object_names"].append(object_name)
        current["slice_codes"].extend(text(row.get("slice_code")) for row in packet)
        current["estimated_slice_chars"] += packet_cost
        current["event_signal_score"] += sum(int(row.get("event_signal_score") or 0) for row in packet)
    return shards


def assign_object_bundle_classes(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    class_by_object: dict[str, str] = {}
    for row in rows:
        owner_class = text(row.get("owner_anchor_class"))
        object_name = text(row.get("object_name"))
        if not object_name or owner_class == "D":
            continue
        current = class_by_object.get(object_name)
        if current is None or CLASS_RANK.get(owner_class, 9) < CLASS_RANK.get(current, 9):
            class_by_object[object_name] = owner_class
    bundled: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        object_name = text(row.get("object_name"))
        owner_class = text(row.get("owner_anchor_class"))
        bundle_class = owner_class if owner_class == "D" else class_by_object.get(object_name, owner_class)
        row["object_bundle_class"] = bundle_class
        if bundle_class != text(row.get("owner_anchor_class")):
            row["selection_reason_codes"] = unique_strings(
                [*(row.get("selection_reason_codes") or []), f"object_bundle_promoted_to_{bundle_class}"]
            )
        bundled.append(row)
    return bundled, class_by_object


def apply_owner_aware_shard_plan(
    candidates: Mapping[str, Any],
    *,
    max_objects_per_shard: int,
    max_slices_per_shard: int = 0,
    max_chars_per_shard: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    classified, classification = classify_candidates(candidates)
    bundled, class_by_object = assign_object_bundle_classes(classified)
    retained = [row for row in bundled if row.get("owner_anchor_class") != "D"]
    excluded = [
        {
            "slice_code": text(row.get("slice_code")),
            "object_name": text(row.get("object_name")),
            "owner_anchor_class": text(row.get("owner_anchor_class")),
            "selection_reason_codes": list(row.get("selection_reason_codes") or []),
        }
        for row in bundled
        if row.get("owner_anchor_class") == "D"
    ]
    shards = build_shards(
        retained,
        max_objects_per_shard=max_objects_per_shard,
        max_slices_per_shard=max_slices_per_shard,
        max_chars_per_shard=max_chars_per_shard,
    )
    manifest = {
        "schema_version": 1,
        "mode": OWNER_AWARE_MODE,
        "classification": classification,
        "object_bundle_classes": dict(sorted(class_by_object.items())),
        "limits": {
            "max_objects_per_shard": max_objects_per_shard,
            "max_slices_per_shard": max_slices_per_shard,
            "max_chars_per_shard": max_chars_per_shard,
        },
        "shards": shards,
        "summary": {
            "input_slice_count": len(classified),
            "prompt_slice_count": len(retained),
            "audit_only_slice_count": len(excluded),
            "shard_count": len(shards),
        },
        "audit_only_slices": excluded,
    }
    result = json.loads(stable_json(candidates))
    result["candidate_slices"] = retained
    result["claim_shard_plan"] = manifest
    stats = dict(result.get("stats") or {})
    stats["candidate_slices_before_owner_aware_sharding"] = len(classified)
    stats["candidate_slices"] = len(retained)
    stats["owner_aware_audit_only_slices"] = len(excluded)
    result["stats"] = stats
    return result, manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an owner-aware claim extraction shard manifest without model invocation.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-candidates", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--max-objects-per-shard", type=int, default=8)
    parser.add_argument("--max-slices-per-shard", type=int, default=0)
    parser.add_argument("--max-chars-per-shard", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidates, manifest = apply_owner_aware_shard_plan(
        read_json(args.candidates),
        max_objects_per_shard=args.max_objects_per_shard,
        max_slices_per_shard=args.max_slices_per_shard,
        max_chars_per_shard=args.max_chars_per_shard,
    )
    write_json(args.output_candidates, candidates)
    write_json(args.output_manifest, manifest)
    print(pretty_json({"ok": True, "manifest": str(args.output_manifest), "summary": manifest["summary"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
