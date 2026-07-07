from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_clean_summary import judge_anomalies  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev import retrieval_v2_runtime_paths as runtime_paths  # noqa: E402


SOURCE_PACK_REFINEMENT_TYPES = {
    "source_missing",
    "alias_missing",
    "fetch_error",
    "source_fetch_failed",
    "object_claim_undercoverage",
    "predicate_missing",
    "civil_undercoverage",
    "negative_undercoverage",
    "weak_alias_noise",
    "core_no_material",
    "core_zero_signal",
    "alias_unsearched",
}
CODEX_REVIEW_TYPES = {
    "mixed_claim_not_split",
    "mixed_claim_needs_review",
    "negative_claim_not_scoring_without_gap",
    "other",
}
HINT_STATUSES = {"formal_candidate", "current_rule_candidate", "future_rule_hint", "context_only", "rejected"}


class IntakeRowsError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IntakeRowsError(f"{path}: expected JSON object")
    return payload


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 12) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def json_object_or_array(value: Any) -> dict[str, Any] | list[Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return {}


def candidate_hint_status(binding: Mapping[str, Any], candidate_payload: Mapping[str, Any]) -> str:
    raw = text(
        binding.get("hint_status")
        or binding.get("route_status")
        or candidate_payload.get("hint_status")
        or candidate_payload.get("route_status")
    )
    if raw in HINT_STATUSES:
        return raw
    return "formal_candidate"


def candidate_lane(
    binding: Mapping[str, Any],
    candidate_payload: Mapping[str, Any],
    *,
    candidate_item_code: str,
    candidate_rule_code: str,
) -> str:
    explicit = text(
        binding.get("candidate_lane")
        or binding.get("lane")
        or candidate_payload.get("candidate_lane")
        or candidate_payload.get("lane")
    )
    if explicit:
        return explicit
    if candidate_item_code and candidate_rule_code:
        return f"{candidate_item_code}.{candidate_rule_code}"
    return candidate_rule_code


def path_from_artifact(package: Mapping[str, Any], kind: str) -> Path:
    artifacts = [row for row in package.get("artifacts") or [] if isinstance(row, Mapping)]
    path_text = next((text(row.get("path")) for row in artifacts if text(row.get("kind")) == kind), "")
    if not path_text:
        raise IntakeRowsError(f"{package.get('source_pack_code')}: missing {kind} artifact path")
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def rows_from_payload(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def namespaced_code(source_pack_code: str, raw_code: str, *, fallback_kind: str, payload: Any) -> str:
    raw = text(raw_code)
    if not raw:
        raw = f"{fallback_kind}-{stable_hash(payload)}"
    return f"{source_pack_code}::{raw}"


def queue_for_gap_type(gap_type: str) -> str:
    if gap_type in SOURCE_PACK_REFINEMENT_TYPES:
        return "source_pack_refinement"
    if gap_type in CODEX_REVIEW_TYPES:
        return "codex_review"
    if gap_type == "object_payload_gap":
        return "object_payload_or_source_review"
    if gap_type == "material_classification_review":
        return "material_classification_review"
    if gap_type == "policy_block":
        return "policy_block_review"
    if gap_type == "true_lack":
        return "true_lack_note"
    return "source_pack_refinement"


def priority_for_gap(gap_type: str, queue: str) -> int:
    if queue == "codex_review":
        return 40
    if gap_type in {"source_missing", "alias_missing", "fetch_error", "source_fetch_failed", "object_claim_undercoverage"}:
        return 50
    if gap_type in {"predicate_missing", "civil_undercoverage", "negative_undercoverage"}:
        return 60
    return 100


def gap_type_from_source(raw_gap_type: str, source: str) -> str:
    gap_type = text(raw_gap_type) or "other"
    if source == "objects_without_slices":
        return "source_missing"
    if gap_type == "source_fetch_failed":
        return "fetch_error"
    if gap_type == "mixed_claim_needs_review":
        return "mixed_claim_not_split"
    return gap_type


def gap_event_row(
    *,
    package: Mapping[str, Any],
    source: str,
    gap: Mapping[str, Any],
) -> dict[str, Any]:
    gap_type = gap_type_from_source(text(gap.get("gap_type") or gap.get("code")), source)
    queue = text(gap.get("queue")) or queue_for_gap_type(gap_type)
    object_name = text(gap.get("object_name"))
    if source == "fetch_error" and not object_name:
        object_name = text(gap.get("title") or gap.get("document_code") or gap.get("url"))
    idem_key = "|".join(
        [
            text(package.get("target_code")),
            text(package.get("rule_code")),
            text(package.get("source_pack_code")),
            gap_type,
            text(gap.get("family_code")),
            object_name,
            text(gap.get("predicate")),
        ]
    )
    return {
        "event_code": f"CGE-{stable_hash(idem_key)}",
        "idem_key": idem_key,
        "source_pack_code": package["source_pack_code"],
        "target_code": package["target_code"],
        "emperor_name": package["emperor_name"],
        "item_code": package["item_code"],
        "rule_code": package["rule_code"],
        "gap_type": gap_type,
        "queue": queue,
        "status": "ready",
        "priority": int(gap.get("priority") or priority_for_gap(gap_type, queue)),
        "family_code": text(gap.get("family_code")),
        "object_name": object_name,
        "predicate": text(gap.get("predicate")),
        "diagnosis": text(gap.get("diagnosis") or gap.get("message")),
        "recommended_action": text(gap.get("recommended_action")),
        "source": source,
        "event_payload": dict(gap),
    }


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(stable_json(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def append_gap_rows(rows: list[dict[str, Any]], *, package: Mapping[str, Any], candidates: Mapping[str, Any], judge: Mapping[str, Any]) -> None:
    coverage = candidates.get("coverage") if isinstance(candidates.get("coverage"), Mapping) else {}
    for object_name in coverage.get("objects_without_slices") or package.get("objects_without_slices") or []:
        if text(object_name):
            rows.append(
                gap_event_row(
                    package=package,
                    source="objects_without_slices",
                    gap={"gap_type": "source_missing", "object_name": text(object_name)},
                )
            )
    for gap in rows_from_payload(candidates, "coverage_gaps"):
        rows.append(gap_event_row(package=package, source="candidate_coverage_gap", gap=gap))
    for gap in rows_from_payload(candidates, "fetch_errors"):
        rows.append(gap_event_row(package=package, source="fetch_error", gap={"gap_type": "fetch_error", **dict(gap)}))
    for gap in rows_from_payload(judge, "coverage_gaps"):
        rows.append(gap_event_row(package=package, source="judge_coverage_gap", gap=gap))
    for anomaly in judge_anomalies(judge):
        rows.append(gap_event_row(package=package, source="judge_anomaly", gap=anomaly))


def unique_rows(rows: Sequence[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = text(row.get(key))
        if value:
            seen.setdefault(value, row)
    return list(seen.values())


def unique_document_raw_code(raw_code: str, document: Mapping[str, Any], *, is_last: bool) -> str:
    if is_last:
        return raw_code
    return f"{raw_code}--ALT-{stable_hash(document, length=8)}"


def normalize_package(package: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    source_pack_code = text(package.get("source_pack_code"))
    if not source_pack_code:
        raise IntakeRowsError("package missing source_pack_code")
    task = load_json(path_from_artifact(package, "task"))
    candidates = load_json(path_from_artifact(package, "candidates"))
    judge = load_json(path_from_artifact(package, "judge"))

    document_code_map: dict[str, str] = {}
    passage_code_map: dict[str, str] = {}
    passage_identity_map: dict[tuple[str, str, str], str] = {}
    passage_rows_by_code: dict[str, dict[str, Any]] = {}
    claim_code_map: dict[str, str] = {}
    rows: dict[str, list[dict[str, Any]]] = {
        "source_packs": [
            {
                "source_pack_code": source_pack_code,
                "target_code": package["target_code"],
                "emperor_name": package["emperor_name"],
                "item_code": package["item_code"],
                "rule_code": package["rule_code"],
                "run_root": package["run_root"],
                "run_dir": package["run_dir"],
                "manifest_payload": dict(package),
            }
        ],
        "source_pack_artifacts": [],
        "source_documents": [],
        "source_passages": [],
        "material_claims": [],
        "primary_claim_rule_bindings": [],
        "secondary_binding_candidates": [],
        "claim_rule_binding_candidates": [],
        "coverage_gap_events": [],
    }

    for artifact in package.get("artifacts") or []:
        if isinstance(artifact, Mapping):
            rows["source_pack_artifacts"].append({"source_pack_code": source_pack_code, **dict(artifact)})

    documents = rows_from_payload(judge, "documents")
    last_document_index_by_raw_code: dict[str, int] = {}
    for index, document in enumerate(documents, start=1):
        raw_code = text(document.get("document_code")) or f"DOC-{index:04d}"
        last_document_index_by_raw_code[raw_code] = index

    for index, document in enumerate(documents, start=1):
        raw_code = text(document.get("document_code")) or f"DOC-{index:04d}"
        unique_raw_code = unique_document_raw_code(
            raw_code,
            document,
            is_last=last_document_index_by_raw_code.get(raw_code) == index,
        )
        document_code = namespaced_code(source_pack_code, unique_raw_code, fallback_kind="DOC", payload=document)
        if unique_raw_code == raw_code:
            document_code_map[raw_code] = document_code
        rows["source_documents"].append(
            {
                "source_pack_code": source_pack_code,
                "document_code": document_code,
                "raw_document_code": unique_raw_code,
                "original_raw_document_code": raw_code,
                "source_title": text(document.get("source_title")),
                "title": text(document.get("title")),
                "locator": text(document.get("locator")),
                "canon_url": text(document.get("url") or document.get("canon_url")),
                "source_kind": text(document.get("source_kind") or "wikisource_page"),
                "document_payload": {"original_raw_document_code": raw_code, **dict(document)},
            }
        )

    for index, passage in enumerate(rows_from_payload(judge, "passages"), start=1):
        raw_code = text(passage.get("passage_code")) or f"PAS-{index:04d}"
        passage_code = namespaced_code(source_pack_code, raw_code, fallback_kind="PAS", payload=passage)
        raw_document_code = text(passage.get("document_code"))
        document_code = document_code_map.get(raw_document_code, raw_document_code)
        locator = text(passage.get("locator"))
        quote = text(passage.get("quote") or passage.get("raw_text"))
        quote_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest() if quote else ""
        identity_key = (document_code, locator, quote_hash)
        if all(identity_key):
            canonical_code = passage_identity_map.get(identity_key)
            if canonical_code:
                passage_code_map[raw_code] = canonical_code
                canonical_row = passage_rows_by_code.get(canonical_code)
                if canonical_row is not None:
                    canonical_row.setdefault("deduped_raw_passage_codes", []).append(raw_code)
                continue
            passage_identity_map[identity_key] = passage_code
        passage_code_map[raw_code] = passage_code
        row = {
            "source_pack_code": source_pack_code,
            "passage_code": passage_code,
            "raw_passage_code": raw_code,
            "document_code": document_code,
            "raw_document_code": raw_document_code,
            "locator": locator,
            "raw_text": quote,
            "quote_hash": quote_hash,
            "passage_payload": dict(passage),
        }
        passage_rows_by_code[passage_code] = row
        rows["source_passages"].append(row)

    for index, claim in enumerate(rows_from_payload(judge, "claims"), start=1):
        raw_code = text(claim.get("claim_code")) or f"CLM-{index:04d}"
        claim_code = namespaced_code(source_pack_code, raw_code, fallback_kind="CLM", payload=claim)
        claim_code_map[raw_code] = claim_code
        raw_passage_refs = [text(ref) for ref in claim.get("source_passage_refs") or [] if text(ref)]
        passage_refs = list(dict.fromkeys(passage_code_map.get(ref, ref) for ref in raw_passage_refs))
        rows["material_claims"].append(
            {
                "source_pack_code": source_pack_code,
                "claim_code": claim_code,
                "raw_claim_code": raw_code,
                "emperor_name": text(claim.get("emperor_name") or package.get("emperor_name")),
                "object_name": text(claim.get("object_name")),
                "object_type": text(claim.get("object_type") or "person"),
                "claim_kind": text(claim.get("claim_kind") or "material_claim"),
                "claim_summary": text(claim.get("claim_summary") or claim.get("summary")),
                "direction": text(claim.get("direction")),
                "confidence": claim.get("confidence"),
                "review_status": text(claim.get("review_status") or "pending"),
                "source_passage_refs": passage_refs,
                "raw_source_passage_refs": raw_passage_refs,
                "source_slice_refs": list(claim.get("source_slice_refs") or []),
                "claim_payload": dict(claim),
            }
        )

    for index, binding in enumerate(rows_from_payload(judge, "primary_bindings"), start=1):
        raw_claim_code = text(binding.get("claim_code"))
        raw_binding_code = text(binding.get("binding_code")) or f"BND-P-{index:04d}-{stable_hash(binding, length=8)}"
        rows["primary_claim_rule_bindings"].append(
            {
                "source_pack_code": source_pack_code,
                "binding_code": namespaced_code(source_pack_code, raw_binding_code, fallback_kind="BND", payload=binding),
                "raw_binding_code": raw_binding_code,
                "claim_code": claim_code_map.get(raw_claim_code, raw_claim_code),
                "raw_claim_code": raw_claim_code,
                "rule_code": text(binding.get("rule_code") or package.get("rule_code")),
                "predicate": text(binding.get("predicate")),
                "direction": text(binding.get("direction")),
                "object_role": text(binding.get("object_role")),
                "usable_for_object_payload": binding.get("usable_for_object_payload") is True,
                "usable_for_scoring_cluster": binding.get("usable_for_scoring_cluster") is True,
                "confidence": binding.get("confidence"),
                "review_status": text(binding.get("review_status") or "pending"),
                "binding_payload": dict(binding),
            }
        )

    for index, binding in enumerate(rows_from_payload(judge, "secondary_binding_candidates"), start=1):
        raw_claim_code = text(binding.get("claim_code"))
        raw_binding_code = text(binding.get("binding_code")) or f"CRBC-S-{index:04d}-{stable_hash(binding, length=8)}"
        candidate_code = namespaced_code(source_pack_code, raw_binding_code, fallback_kind="CRBC", payload=binding)
        binding_payload = dict(binding)
        raw_candidate_payload = binding.get("candidate_payload") if isinstance(binding.get("candidate_payload"), Mapping) else {}
        candidate_payload = {
            **dict(raw_candidate_payload),
            "source_binding": binding_payload,
            "created_from": "secondary_binding_candidates",
        }
        for lifted_key in ("candidate_lane", "hint_status", "required_facts_present", "routed_by_profile"):
            if lifted_key in binding and lifted_key not in candidate_payload:
                candidate_payload[lifted_key] = binding[lifted_key]
        candidate_item_code = text(binding.get("candidate_item_code") or binding.get("item_code"))
        candidate_rule_code = text(binding.get("candidate_rule_code") or binding.get("rule_code"))
        hint_status = candidate_hint_status(binding, candidate_payload)
        lane = candidate_lane(
            binding,
            candidate_payload,
            candidate_item_code=candidate_item_code,
            candidate_rule_code=candidate_rule_code,
        )
        required_facts = json_object_or_array(
            binding.get("required_facts_present") or candidate_payload.get("required_facts_present")
        )
        routed_by_profile = text(
            binding.get("routed_by_profile")
            or candidate_payload.get("routed_by_profile")
            or package.get("capture_profile")
            or package.get("capture_mode")
            or "secondary_binding_candidates"
        )
        candidate_row = {
            "source_pack_code": source_pack_code,
            "candidate_code": candidate_code,
            "binding_code": candidate_code,
            "raw_binding_code": raw_binding_code,
            "claim_code": claim_code_map.get(raw_claim_code, raw_claim_code),
            "raw_claim_code": raw_claim_code,
            "source_item_code": text(package.get("item_code")),
            "source_rule_code": text(package.get("rule_code")),
            "candidate_item_code": candidate_item_code,
            "candidate_rule_code": candidate_rule_code,
            "candidate_lane": lane,
            "hint_status": hint_status,
            "required_facts_present": required_facts,
            "routed_by_profile": routed_by_profile,
            "candidate_predicate": text(binding.get("predicate") or binding.get("candidate_predicate")),
            "candidate_object_role": text(binding.get("object_role") or binding.get("candidate_object_role")),
            "candidate_direction": text(binding.get("direction") or binding.get("candidate_direction")),
            "confidence": binding.get("confidence"),
            "reason": text(binding.get("reason")),
            "review_status": "pending",
            "resolved_binding_code": "",
            "created_from": "secondary_binding_candidates",
            "binding_payload": binding_payload,
            "candidate_payload": candidate_payload,
        }
        rows["secondary_binding_candidates"].append(candidate_row)
        rows["claim_rule_binding_candidates"].append(candidate_row)

    append_gap_rows(rows["coverage_gap_events"], package=package, candidates=candidates, judge=judge)
    rows["coverage_gap_events"] = unique_rows(rows["coverage_gap_events"], "idem_key")
    return rows


def merge_rows(row_groups: Iterable[Mapping[str, list[dict[str, Any]]]]) -> dict[str, list[dict[str, Any]]]:
    merged: dict[str, list[dict[str, Any]]] = {}
    for group in row_groups:
        for name, rows in group.items():
            merged.setdefault(name, []).extend(rows)
    if "coverage_gap_events" in merged:
        merged["coverage_gap_events"] = unique_rows(merged["coverage_gap_events"], "idem_key")
    return merged


def build_rows(manifest_path: Path) -> dict[str, list[dict[str, Any]]]:
    manifest = load_json(manifest_path)
    packages = [row for row in manifest.get("packages") or [] if isinstance(row, Mapping)]
    return merge_rows(normalize_package(package) for package in packages)


def default_package_name(manifest_path: Path) -> str:
    stem = manifest_path.stem
    if stem and stem != "intake_manifest":
        return stem
    parent = manifest_path.parent.name
    return parent or stem or "retrieval_v2_consumption"


def write_rowset(rows: Mapping[str, Sequence[Mapping[str, Any]]], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    totals: dict[str, int] = {}
    for name in sorted(rows):
        path = output_root / f"{name}.jsonl"
        write_jsonl(path, rows[name])
        files[name] = repo_relative(path)
        totals[name] = len(rows[name])
    summary = {
        "generated_by": "scripts/dev/retrieval_v2_intake_rows.py",
        "files": files,
        "totals": totals,
    }
    (output_root / "normalized_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expand retrieval_v2 intake manifest into normalized staging JSONL rows.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Write normalized staging rows.")
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--output-root", type=Path)
    build.add_argument("--package-name", help="Runtime output directory name when --output-root is omitted.")
    build.add_argument("--runtime-paths-config", type=Path, help="Optional runtime_paths.json for output defaults.")
    build.add_argument(
        "--use-local-runtime",
        action="store_true",
        help="Force repo-local tmp/.tmp runtime defaults instead of NAS/env runtime config.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "build":
        raise IntakeRowsError(f"unsupported command: {args.command}")
    runtime = runtime_paths.load_runtime_paths(
        config_path=args.runtime_paths_config,
        use_local=args.use_local_runtime,
    )
    output_root = args.output_root or runtime_paths.default_consumption_root(
        args.package_name or default_package_name(args.manifest),
        runtime,
    )
    rows = build_rows(args.manifest)
    summary = write_rowset(rows, output_root)
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "runtime_paths": {
                    "uses_runtime_config": bool(runtime["uses_runtime_config"]),
                    "config_source": str(runtime["config_source"]),
                },
                "totals": summary["totals"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
