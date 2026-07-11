from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_unseeded_actor_discovery import stable_code, text, write_jsonl, write_text  # noqa: E402
from scripts.dev.retrieval_v3_unseeded_actor_review_tasks import read_jsonl  # noqa: E402


ALLOWED_VERDICTS = {"source_refine", "reject_name", "needs_context"}
VERDICT_ACTIONS = {
    "source_refine": "run_object_source_refiner",
    "reject_name": "reject_name",
    "needs_context": "needs_context",
}
BOOLEAN_FIELDS = (
    "is_person_name",
    "is_same_reign_actor",
    "has_appointment_or_authorization_signal",
    "has_harm_or_failure_signal",
    "has_disposition_only",
)
JIFEILU_URL = "https://www.shidianguji.com/book/NGJ89241199901269069717/chapter/1lmyda88zy80y"
JIFEILU_OCR_ALIASES = {"朱檀": ["魚王", "鱼王"], "朱守谦": ["守謙", "守谦"]}


class ActorReviewConsumerError(ValueError):
    pass


def validate_patch(row: Mapping[str, Any]) -> dict[str, Any]:
    candidate_code = text(row.get("candidate_code"))
    verdict = text(row.get("review_verdict"))
    if not candidate_code:
        raise ActorReviewConsumerError("candidate_code is required")
    if verdict not in ALLOWED_VERDICTS:
        raise ActorReviewConsumerError(f"{candidate_code}: unsupported review_verdict={verdict!r}")
    for field in BOOLEAN_FIELDS:
        if not isinstance(row.get(field), bool):
            raise ActorReviewConsumerError(f"{candidate_code}: {field} must be boolean")
    expected_action = VERDICT_ACTIONS[verdict]
    if text(row.get("recommended_action")) != expected_action:
        raise ActorReviewConsumerError(f"{candidate_code}: recommended_action must be {expected_action}")
    if verdict == "source_refine" and not (row["is_person_name"] and row["is_same_reign_actor"]):
        raise ActorReviewConsumerError(f"{candidate_code}: source_refine requires person and same-reign actor")
    if row["has_disposition_only"] and row["has_harm_or_failure_signal"]:
        raise ActorReviewConsumerError(f"{candidate_code}: disposition-only cannot also claim harm/failure")
    hashes = [text(value) for value in row.get("evidence_window_hashes") or [] if text(value)]
    if not hashes:
        raise ActorReviewConsumerError(f"{candidate_code}: evidence_window_hashes is required")
    review_note = text(row.get("review_note"))
    if not review_note:
        raise ActorReviewConsumerError(f"{candidate_code}: review_note is required")
    return {
        "candidate_code": candidate_code,
        "review_verdict": verdict,
        **{field: bool(row[field]) for field in BOOLEAN_FIELDS},
        "recommended_action": expected_action,
        "evidence_window_hashes": list(dict.fromkeys(hashes)),
        "review_note": review_note,
        "scoring_allowed": False,
    }


def validate_review_package(
    workitems: Sequence[Mapping[str, Any]],
    patch_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    workitem_lookup = {text(row.get("candidate_code")): dict(row) for row in workitems if text(row.get("candidate_code"))}
    patches = [validate_patch(row) for row in patch_rows]
    patch_codes = [row["candidate_code"] for row in patches]
    duplicates = sorted(code for code, count in Counter(patch_codes).items() if count > 1)
    if duplicates:
        raise ActorReviewConsumerError(f"duplicate review patches: {duplicates[:5]}")
    missing = sorted(set(workitem_lookup) - set(patch_codes))
    unknown = sorted(set(patch_codes) - set(workitem_lookup))
    if missing:
        raise ActorReviewConsumerError(f"missing review patches: {missing[:5]}")
    if unknown:
        raise ActorReviewConsumerError(f"unknown review patches: {unknown[:5]}")
    merged: list[dict[str, Any]] = []
    for patch in patches:
        workitem = workitem_lookup[patch["candidate_code"]]
        allowed_hashes = {
            text(window.get("window_hash"))
            for window in workitem.get("evidence_windows") or []
            if isinstance(window, Mapping) and text(window.get("window_hash"))
        }
        if not set(patch["evidence_window_hashes"]).issubset(allowed_hashes):
            raise ActorReviewConsumerError(f"{patch['candidate_code']}: evidence_window_hashes not in workitem")
        merged.append({**workitem, "actor_review": patch, "scoring_allowed": False})
    return merged


def source_refiner_priority(row: Mapping[str, Any]) -> int:
    stages = set(text(value) for value in row.get("lead_stages") or [] if text(value))
    if "appointment_harm_lead" in stages:
        return 10
    if "appointment_disposition_lead" in stages:
        return 20
    if "harm_lead_without_appointment" in stages:
        return 30
    return 40


def source_profile_fields(row: Mapping[str, Any], canonical_name: str, aliases: Sequence[str]) -> dict[str, Any]:
    actor_scope = text(row.get("actor_scope")) or "official_or_other"
    fields: dict[str, Any] = {
        "actor_scope": actor_scope,
        "object_search_scopes": ["person", "royal_clan"] if actor_scope == "royal_clan" else ["person"],
    }
    if actor_scope != "royal_clan":
        return fields
    source_hints = [text(value) for value in row.get("source_hints") or [] if text(value)]
    fields["source_target_refs"] = [f"{hint} 宗室 藩王 {canonical_name}" for hint in source_hints]
    if text(row.get("emperor_name")) == "朱元璋":
        references = " ".join(dict.fromkeys([canonical_name, *aliases]))
        fields["source_document_hints"] = [
            {
                "title": "御制纪非录",
                "source_title": "御制纪非录",
                "locator": f"御制纪非录正文 宗室条 {references}",
                "url": JIFEILU_URL,
                "source_kind": "public_ocr_page",
                "fetch_mode": "url",
                "ocr_requires_image_review": True,
                "ocr_aliases": JIFEILU_OCR_ALIASES.get(canonical_name, []),
            }
        ]
    return fields


def source_refiner_rows(reviewed_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for row in reviewed_rows:
        review = row.get("actor_review") if isinstance(row.get("actor_review"), Mapping) else {}
        if text(review.get("review_verdict")) != "source_refine":
            continue
        observed_name = text(row.get("observed_name"))
        canonical_name = text(row.get("resolved_canonical_name")) or observed_name
        target_period = text(row.get("target_period"))
        source_hints = [text(value) for value in row.get("source_hints") or [] if text(value)]
        if not target_period or not source_hints:
            raise ActorReviewConsumerError(
                f"{row.get('candidate_code')}: source_refine requires deterministic target_period and source_hints"
            )
        aliases = [] if canonical_name == observed_name else [observed_name]
        aliases = list(dict.fromkeys([*aliases, *[text(value) for value in row.get("reference_aliases") or [] if text(value)]]))
        evidence = [
            dict(window)
            for window in row.get("evidence_windows") or []
            if isinstance(window, Mapping) and text(window.get("window_hash")) in set(review.get("evidence_window_hashes") or [])
        ]
        seeds.append(
            {
                "workitem_code": stable_code("UASR-", row.get("candidate_code")),
                "name": canonical_name,
                "aliases": aliases,
                "target_emperors": [text(row.get("emperor_name"))],
                "period": target_period,
                "source_hints": list(dict.fromkeys(source_hints)),
                **source_profile_fields(row, canonical_name, aliases),
                "is_emperor": False,
                "priority": source_refiner_priority(row),
                "capture_profile": "personnel_political_wide",
                "seed_sources": ["retrieval_v3_unseeded_actor_review"],
                "discovery_candidate_code": row.get("candidate_code"),
                "discovery_status": row.get("discovery_status"),
                "lead_stages": row.get("lead_stages"),
                "review_note": review.get("review_note"),
                "discovery_evidence": evidence,
                "required_chain": {
                    "appointment_or_authorization": True,
                    "task_or_responsibility": True,
                    "same_chain_harm_or_failure": True,
                    "royal_clan_power_or_fief": text(row.get("actor_scope")) == "royal_clan",
                    "disposition_alone_is_not_scoring": True,
                },
                "write_db": False,
                "scoring_allowed": False,
            }
        )
    return sorted(seeds, key=lambda row: (int(row["priority"]), text(row["target_emperors"][0]), text(row["name"])))


def build_report(reviewed_rows: Sequence[Mapping[str, Any]], source_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    verdicts = Counter(text(row.get("actor_review", {}).get("review_verdict")) for row in reviewed_rows)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_unseeded_actor_review_consumer.py",
        "write_db": False,
        "scoring_allowed": False,
        "input_rows": len(reviewed_rows),
        "counts_by_verdict": dict(sorted(verdicts.items())),
        "source_refiner_workitem_count": len(source_rows),
        "reviewed_candidates": list(reviewed_rows),
        "execute_effect": "validated review patches and file-only source-refiner worklist; no object, claim, binding, factor, or score writes",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate actor-review patches and emit file-only source-refiner seeds.")
    parser.add_argument("--workitems-jsonl", type=Path, required=True)
    parser.add_argument("--patch-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-source-refiner-jsonl", type=Path, required=True)
    args = parser.parse_args(argv)
    reviewed = validate_review_package(read_jsonl(args.workitems_jsonl), read_jsonl(args.patch_jsonl))
    source_rows = source_refiner_rows(reviewed)
    report = build_report(reviewed, source_rows)
    write_text(args.output_json, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write_jsonl(args.output_source_refiner_jsonl, source_rows)
    print(json.dumps({key: value for key, value in report.items() if key != "reviewed_candidates"}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
