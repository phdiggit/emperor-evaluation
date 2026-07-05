from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import alias_script_variants  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v2_intake_rows import stable_json  # noqa: E402


EVENT_NAME_RE = re.compile(r"(案|事件|之變|之变|叛亂|叛乱|兵變|兵变|政變|政变)$")
GROUP_NAME_RE = re.compile(r"(群臣|諸將|诸将|士大夫|功臣|官員|官员|集團|集团)$")


class ReviewWorklistError(RuntimeError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ReviewWorklistError(f"{path}:{line_number}: expected JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")


def stable_code(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def name_variants(name: str) -> list[str]:
    variants = {text(name)}
    variants.update(text(value) for value in alias_script_variants(name) if text(value))
    return sorted(variants)


def object_group_key(name: str) -> str:
    variants = name_variants(name)
    return variants[0] if variants else text(name)


def object_shape_hint(name: str, object_types: set[str]) -> str:
    if any(value and value != "person" for value in object_types):
        return "declared_non_person"
    if EVENT_NAME_RE.search(name):
        return "event_like_name"
    if GROUP_NAME_RE.search(name):
        return "group_like_name"
    return "person_like"


def load_rowset(normalized_root: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "source_packs": read_jsonl(normalized_root / "source_packs.jsonl"),
        "material_claims": read_jsonl(normalized_root / "material_claims.jsonl"),
        "primary_claim_rule_bindings": read_jsonl(normalized_root / "primary_claim_rule_bindings.jsonl"),
        "secondary_binding_candidates": read_jsonl(normalized_root / "secondary_binding_candidates.jsonl"),
        "claim_rule_binding_candidates": read_jsonl(normalized_root / "claim_rule_binding_candidates.jsonl"),
        "source_passages": read_jsonl(normalized_root / "source_passages.jsonl"),
        "coverage_gap_events": read_jsonl(normalized_root / "coverage_gap_events.jsonl"),
    }


def build_object_resolution_worklist(rows: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    claims = rows.get("material_claims", [])
    bindings_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in rows.get("primary_claim_rule_bindings", []):
        bindings_by_claim[text(binding.get("claim_code"))].append(binding)

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        object_name = text(claim.get("object_name"))
        if not object_name:
            continue
        key = (text(claim.get("emperor_name")), text(claim.get("item_code") or "I5B"), object_group_key(object_name))
        groups[key].append(claim)

    worklist: list[dict[str, Any]] = []
    for (emperor_name, item_code, group_key), group_claims in sorted(groups.items()):
        observed_names = sorted({text(claim.get("object_name")) for claim in group_claims if text(claim.get("object_name"))})
        object_types = {text(claim.get("object_type") or "person") for claim in group_claims}
        claim_codes = sorted({text(claim.get("claim_code")) for claim in group_claims if text(claim.get("claim_code"))})
        group_bindings = [binding for claim_code in claim_codes for binding in bindings_by_claim.get(claim_code, [])]
        roles = sorted({text(binding.get("object_role")) for binding in group_bindings if text(binding.get("object_role"))})
        predicates = sorted({text(binding.get("predicate")) for binding in group_bindings if text(binding.get("predicate"))})
        directions = sorted({text(claim.get("direction")) for claim in group_claims if text(claim.get("direction"))})
        source_pack_codes = sorted({text(claim.get("source_pack_code")) for claim in group_claims if text(claim.get("source_pack_code"))})
        variants = sorted({variant for name in observed_names for variant in name_variants(name)})
        shape_hint = object_shape_hint(observed_names[0], object_types)
        review_reasons: list[str] = []
        if len(observed_names) > 1:
            review_reasons.append("multiple_observed_names")
        if len(object_types) > 1:
            review_reasons.append("multiple_object_types")
        if shape_hint != "person_like":
            review_reasons.append(shape_hint)
        if not review_reasons:
            review_reasons.append("single_person_like_name")
        row = {
            "object_resolution_code": stable_code(
                "ORW",
                [emperor_name, item_code, group_key, observed_names, source_pack_codes],
            ),
            "emperor_name": emperor_name,
            "item_code": item_code,
            "object_group_key": group_key,
            "canonical_name_candidate": observed_names[0],
            "observed_names": observed_names,
            "script_variant_candidates": variants,
            "object_types": sorted(object_types),
            "shape_hint": shape_hint,
            "review_status": "needs_review" if review_reasons != ["single_person_like_name"] else "candidate_new_or_existing",
            "review_reasons": review_reasons,
            "source_pack_codes": source_pack_codes,
            "claim_codes": claim_codes,
            "claim_count": len(group_claims),
            "primary_binding_count": len(group_bindings),
            "directions": directions,
            "object_roles": roles,
            "predicates": predicates,
        }
        worklist.append(row)
    return worklist


def numeric_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def material_review_flags(*, claim: Mapping[str, Any], binding: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    if not text(claim.get("object_name")):
        flags.append("missing_object_name")
    if not claim.get("source_passage_refs"):
        flags.append("missing_source_passage_refs")
    if text(claim.get("direction")) in {"mixed", "neutral"}:
        flags.append("non_atomic_direction")
    if not text(binding.get("predicate")):
        flags.append("missing_predicate")
    if not text(binding.get("object_role")):
        flags.append("missing_object_role")
    if binding.get("usable_for_object_payload") is not True:
        flags.append("not_usable_for_object_payload")
    confidence = numeric_confidence(binding.get("confidence") if binding.get("confidence") is not None else claim.get("confidence"))
    if confidence is not None and confidence < 0.75:
        flags.append("low_confidence")
    return flags


def material_review_status(flags: Sequence[str]) -> str:
    blocking = {
        "missing_object_name",
        "missing_source_passage_refs",
        "non_atomic_direction",
        "missing_predicate",
        "missing_object_role",
        "not_usable_for_object_payload",
    }
    return "needs_review" if blocking & set(flags) else "ready_for_object_payload"


def build_material_review_worklist(rows: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    claims_by_code = {text(claim.get("claim_code")): claim for claim in rows.get("material_claims", [])}
    passages_by_code = {text(passage.get("passage_code")): passage for passage in rows.get("source_passages", [])}
    secondary_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rule_candidates = rows.get("claim_rule_binding_candidates") or rows.get("secondary_binding_candidates", [])
    for secondary in rule_candidates:
        secondary_by_claim[text(secondary.get("claim_code"))].append(secondary)

    worklist: list[dict[str, Any]] = []
    for binding in rows.get("primary_claim_rule_bindings", []):
        claim_code = text(binding.get("claim_code"))
        claim = claims_by_code.get(claim_code, {})
        passage_refs = [text(value) for value in claim.get("source_passage_refs") or [] if text(value)]
        passage_snippets = [
            {
                "passage_code": code,
                "document_code": passages_by_code.get(code, {}).get("document_code", ""),
                "locator": passages_by_code.get(code, {}).get("locator", ""),
                "quote": passages_by_code.get(code, {}).get("raw_text", ""),
            }
            for code in passage_refs[:3]
        ]
        flags = material_review_flags(claim=claim, binding=binding)
        row = {
            "material_review_code": stable_code("MRW", [claim_code, binding.get("binding_code")]),
            "review_status": material_review_status(flags),
            "review_flags": flags,
            "source_pack_code": text(binding.get("source_pack_code")),
            "target_emperor": text(claim.get("emperor_name")),
            "object_name": text(claim.get("object_name")),
            "object_type": text(claim.get("object_type")),
            "claim_code": claim_code,
            "binding_code": text(binding.get("binding_code")),
            "rule_code": text(binding.get("rule_code")),
            "predicate": text(binding.get("predicate")),
            "direction": text(binding.get("direction") or claim.get("direction")),
            "object_role": text(binding.get("object_role")),
            "claim_summary": text(claim.get("claim_summary")),
            "confidence": binding.get("confidence") if binding.get("confidence") is not None else claim.get("confidence"),
            "usable_for_object_payload": binding.get("usable_for_object_payload") is True,
            "usable_for_scoring_cluster": binding.get("usable_for_scoring_cluster") is True,
            "source_passage_refs": passage_refs,
            "passage_snippets": passage_snippets,
            "secondary_rule_candidates": [
                {
                    "binding_code": text(secondary.get("binding_code")),
                    "candidate_code": text(secondary.get("candidate_code")),
                    "source_item_code": text(secondary.get("source_item_code")),
                    "source_rule_code": text(secondary.get("source_rule_code")),
                    "candidate_item_code": text(secondary.get("candidate_item_code")),
                    "candidate_rule_code": text(secondary.get("candidate_rule_code") or secondary.get("rule_code")),
                    "confidence": secondary.get("confidence"),
                    "reason": text(secondary.get("reason")),
                }
                for secondary in secondary_by_claim.get(claim_code, [])
            ],
        }
        worklist.append(row)
    return worklist


def summarize_worklists(*, object_rows: Sequence[Mapping[str, Any]], material_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    object_status = Counter(text(row.get("review_status")) for row in object_rows)
    material_status = Counter(text(row.get("review_status")) for row in material_rows)
    by_emperor = Counter(text(row.get("target_emperor")) for row in material_rows)
    return {
        "generated_by": "scripts/dev/retrieval_v2_review_worklists.py",
        "totals": {
            "object_resolution_items": len(object_rows),
            "material_review_items": len(material_rows),
            "ready_for_object_payload": material_status.get("ready_for_object_payload", 0),
            "material_needs_review": material_status.get("needs_review", 0),
            "object_needs_review": object_status.get("needs_review", 0),
            "scoring_candidates": sum(1 for row in material_rows if row.get("usable_for_scoring_cluster") is True),
        },
        "material_items_by_emperor": dict(sorted(by_emperor.items())),
        "object_status_counts": dict(sorted(object_status.items())),
        "material_status_counts": dict(sorted(material_status.items())),
    }


def build_worklists(normalized_root: Path) -> dict[str, Any]:
    rows = load_rowset(normalized_root)
    object_rows = build_object_resolution_worklist(rows)
    material_rows = build_material_review_worklist(rows)
    summary = summarize_worklists(object_rows=object_rows, material_rows=material_rows)
    return {
        "object_resolution_worklist": object_rows,
        "material_review_worklist": material_rows,
        "summary": summary,
    }


def write_worklists(payload: Mapping[str, Any], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    object_path = output_root / "object_resolution_worklist.jsonl"
    material_path = output_root / "material_review_worklist.jsonl"
    summary_path = output_root / "worklist_summary.json"
    write_jsonl(object_path, payload["object_resolution_worklist"])
    write_jsonl(material_path, payload["material_review_worklist"])
    summary = {
        **payload["summary"],
        "files": {
            "object_resolution_worklist": repo_relative(object_path),
            "material_review_worklist": repo_relative(material_path),
        },
    }
    write_json(summary_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build retrieval_v2 object and material review worklists.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build review worklists from normalized staging rows.")
    build.add_argument("--normalized-root", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "build":
        raise ReviewWorklistError(f"unsupported command: {args.command}")
    payload = build_worklists(args.normalized_root)
    summary = write_worklists(payload, args.output_root)
    print(json.dumps({"output_root": str(args.output_root), "totals": summary["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
