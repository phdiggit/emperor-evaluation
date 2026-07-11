from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_contracts import ALIAS_VARIANT_GROUPS  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v3_intake_rows import stable_json  # noqa: E402
from scripts.dev.retrieval_v3_review_worklists import object_group_key, read_jsonl  # noqa: E402


DIRECTIONS = {"positive", "negative", "neutral", "mixed"}
OBJECT_TYPES = {"person", "institution", "place", "event", "text", "other"}
HINT_STATUSES = {"formal_candidate", "current_rule_candidate", "future_rule_hint", "context_only", "rejected"}
NORMALIZED_FILES = [
    "source_packs",
    "source_pack_artifacts",
    "source_documents",
    "source_passages",
    "material_claims",
    "primary_claim_rule_bindings",
    "claim_rule_binding_candidates",
    "coverage_gap_events",
]
VIRTUAL_SOURCE_RULES = {"i5b_item_wide"}


class ImportPlanError(RuntimeError):
    pass


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_normalized_rows(normalized_root: Path) -> dict[str, list[dict[str, Any]]]:
    return {name: read_jsonl(normalized_root / f"{name}.jsonl") for name in NORMALIZED_FILES}


def load_review_rows(review_root: Path | None) -> dict[str, list[dict[str, Any]]]:
    if review_root is None:
        return {"object_resolution_worklist": [], "material_review_worklist": []}
    return {
        "object_resolution_worklist": read_jsonl(review_root / "object_resolution_worklist.jsonl"),
        "material_review_worklist": read_jsonl(review_root / "material_review_worklist.jsonl"),
    }


def index_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        value = text(row.get(key))
        if value:
            indexed.setdefault(value, row)
    return indexed


def duplicate_keys(rows: Sequence[Mapping[str, Any]], key: str) -> list[str]:
    counts = Counter(text(row.get(key)) for row in rows if text(row.get(key)))
    return sorted(value for value, count in counts.items() if count > 1)


def duplicate_composite_keys(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> list[str]:
    counts = Counter(
        "|".join(text(row.get(key)) for key in keys)
        for row in rows
        if all(text(row.get(key)) for key in keys)
    )
    return sorted(value for value, count in counts.items() if count > 1)


def canonical_object_type(values: Any) -> str:
    if isinstance(values, list):
        for value in values:
            candidate = text(value)
            if candidate in OBJECT_TYPES:
                return candidate
    candidate = text(values)
    return candidate if candidate in OBJECT_TYPES else "other"


def enum_direction(value: Any) -> str | None:
    direction = text(value)
    if not direction:
        return None
    return direction if direction in DIRECTIONS else ""


def reason_hash(reason: str) -> str:
    return hashlib.sha256(reason.encode("utf-8")).hexdigest()[:16].upper() if reason else ""


def json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def candidate_hint_status(row: Mapping[str, Any]) -> str:
    payload = row.get("candidate_payload") if isinstance(row.get("candidate_payload"), Mapping) else {}
    raw = text(row.get("hint_status") or payload.get("hint_status") or payload.get("route_status"))
    return raw if raw in HINT_STATUSES else "formal_candidate"


def candidate_required_facts(row: Mapping[str, Any]) -> dict[str, Any] | list[Any]:
    value = row.get("required_facts_present")
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    payload = row.get("candidate_payload") if isinstance(row.get("candidate_payload"), Mapping) else {}
    value = payload.get("required_facts_present")
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return {}


def lookup_from_cursor(cur: Any) -> dict[str, Any]:
    cur.execute(
        """
        select id, target_code, contract_id, emperor_name, item_code
          from retrieval_v3.retrieval_targets
        """
    )
    targets = {
        text(row["target_code"]): {
            "id": int(row["id"]),
            "contract_id": int(row["contract_id"]),
            "emperor_name": text(row["emperor_name"]),
            "item_code": text(row["item_code"]),
        }
        for row in cur.fetchall()
    }
    cur.execute(
        """
        select id, contract_id, rule_code
          from retrieval_v3.rule_contract_rules
        """
    )
    rules = {
        f"{int(row['contract_id'])}|{text(row['rule_code'])}": int(row["id"])
        for row in cur.fetchall()
    }
    return {"targets": targets, "contract_rules": rules}


def db_lookup(*, env_file: Path | None, dsn_env: str, schema_name: str = "retrieval_v3") -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            return lookup_from_cursor(cur)


def lookup_rule_id(lookup: Mapping[str, Any] | None, *, target_code: str, rule_code: str) -> int | None:
    if not lookup:
        return None
    target = (lookup.get("targets") or {}).get(target_code)
    if not target:
        return None
    return (lookup.get("contract_rules") or {}).get(f"{target['contract_id']}|{rule_code}")


def lookup_target(lookup: Mapping[str, Any], target_code: str) -> Mapping[str, Any]:
    target = (lookup.get("targets") or {}).get(target_code)
    if not target:
        raise ImportPlanError(f"missing retrieval target: {target_code}")
    return target

def operation(table: str, natural_key: Mapping[str, Any], *, depends_on: Sequence[Mapping[str, Any]] = (), payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "operation_code": "RVI-" + stable_hash([table, natural_key], length=12),
        "action": "upsert",
        "table": table,
        "natural_key": dict(natural_key),
        "depends_on": [dict(row) for row in depends_on],
        "payload_hash": stable_hash(payload, length=16),
    }


def blocker(table: str, row_code: str, code: str, message: str) -> dict[str, str]:
    return {"table": table, "row_code": row_code, "code": code, "message": message}


def warning(table: str, row_code: str, code: str, message: str) -> dict[str, str]:
    return {"table": table, "row_code": row_code, "code": code, "message": message}


COMMON_CJK_STOP_CHARS = set("之乎者也而以于於其所为為与與及并並乃则則曰云有无無不在是此彼上中下")
SCRIPT_VARIANT_TRANSLATION = str.maketrans(
    {
        variant: group[0]
        for group in ALIAS_VARIANT_GROUPS
        for variant in group[1:]
        if len(group[0]) == 1 and len(variant) == 1
    }
)


def normalize_alignment_text(value: str) -> str:
    return value.translate(SCRIPT_VARIANT_TRANSLATION)


def cjk_chars(value: str) -> list[str]:
    normalized = normalize_alignment_text(value)
    return [char for char in normalized if "\u4e00" <= char <= "\u9fff"]


def summary_terms(value: str, *, object_name: str = "") -> set[str]:
    chars = cjk_chars(value)
    terms = {
        "".join(chars[index : index + 2])
        for index in range(max(0, len(chars) - 1))
        if not (chars[index] in COMMON_CJK_STOP_CHARS and chars[index + 1] in COMMON_CJK_STOP_CHARS)
    }
    if len(object_name) >= 2:
        terms.add(object_name)
    return terms


def claim_passage_alignment_issue(
    claim: Mapping[str, Any],
    passages: Mapping[str, Mapping[str, Any]],
) -> dict[str, str] | None:
    summary = text(claim.get("claim_summary"))
    object_name = normalize_alignment_text(text(claim.get("object_name")))
    refs = [text(ref) for ref in claim.get("source_passage_refs") or [] if text(ref) in passages]
    if not summary or not refs:
        return None
    haystack = normalize_alignment_text("\n".join(text(passages[ref].get("raw_text")) for ref in refs))
    if not haystack:
        return None

    terms = summary_terms(summary, object_name=object_name)
    overlaps = sorted(term for term in terms if term and term in haystack)
    object_present = bool(object_name and object_name in haystack)
    if not overlaps:
        return {
            "severity": "blocker",
            "code": "claim_passage_mismatch",
            "message": "claim_summary has no meaningful overlap with referenced source_passage raw_text",
        }
    if object_name and not object_present and len(overlaps) < 2:
        return {
            "severity": "blocker",
            "code": "claim_passage_object_mismatch",
            "message": f"object_name not found in referenced passages and summary overlap is weak: {','.join(overlaps[:3])}",
        }
    if object_present and overlaps == [object_name]:
        return {
            "severity": "warning",
            "code": "claim_passage_object_only_match",
            "message": "referenced passages only match claim_summary by object_name; review for summary/passage drift",
        }
    return None


def build_plan(*, normalized_root: Path, review_root: Path | None = None, lookup: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = load_normalized_rows(normalized_root)
    review_rows = load_review_rows(review_root)
    source_packs = index_by(rows["source_packs"], "source_pack_code")
    documents = index_by(rows["source_documents"], "document_code")
    passages = index_by(rows["source_passages"], "passage_code")
    claims = index_by(rows["material_claims"], "claim_code")
    bindings = index_by(rows["primary_claim_rule_bindings"], "binding_code")

    operations: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for table_name, key_name in [
        ("source_packs", "source_pack_code"),
        ("source_documents", "document_code"),
        ("source_passages", "passage_code"),
        ("material_claims", "claim_code"),
        ("primary_claim_rule_bindings", "binding_code"),
        ("claim_rule_binding_candidates", "candidate_code"),
        ("coverage_gap_events", "idem_key"),
    ]:
        for value in duplicate_keys(rows[table_name], key_name):
            blockers.append(blocker(table_name, value, "duplicate_key", f"{key_name} repeats in normalized rowset"))

    for value in duplicate_composite_keys(rows["source_documents"], ["source_pack_code", "raw_document_code"]):
        blockers.append(
            blocker(
                "source_documents",
                value,
                "duplicate_raw_document_code",
                "source_pack_code + raw_document_code repeats in normalized rowset",
            )
        )

    for pack in rows["source_packs"]:
        pack_code = text(pack.get("source_pack_code"))
        target_code = text(pack.get("target_code"))
        if lookup and target_code not in (lookup.get("targets") or {}):
            blockers.append(blocker("source_packs", pack_code, "missing_target", f"target_code not found in retrieval_v3.retrieval_targets: {target_code}"))
        operations.append(
            operation(
                "retrieval_v3.source_packs",
                {"pack_code": pack_code},
                payload={
                    "target_code": target_code,
                    "contract_rule_code": text(pack.get("rule_code")),
                    "status": "accepted",
                    "coverage_status": "passed",
                    "accepted_run_fingerprint": stable_hash(pack.get("manifest_payload") or pack),
                },
            )
        )

    for artifact in rows["source_pack_artifacts"]:
        pack_code = text(artifact.get("source_pack_code"))
        if pack_code not in source_packs:
            blockers.append(blocker("source_pack_artifacts", text(artifact.get("path")), "missing_source_pack", pack_code))
            continue
        operations.append(
            operation(
                "retrieval_v3.source_pack_artifacts",
                {
                    "source_pack_code": pack_code,
                    "artifact_kind": text(artifact.get("kind")),
                    "artifact_path": text(artifact.get("path")),
                },
                depends_on=[{"table": "retrieval_v3.source_packs", "pack_code": pack_code}],
                payload=artifact,
            )
        )

    for document in rows["source_documents"]:
        document_code = text(document.get("document_code"))
        pack_code = text(document.get("source_pack_code"))
        if pack_code not in source_packs:
            blockers.append(blocker("source_documents", document_code, "missing_source_pack", pack_code))
            continue
        if not text(document.get("title")):
            blockers.append(blocker("source_documents", document_code, "missing_title", "source_documents.title is required by DB schema"))
        operations.append(
            operation(
                "retrieval_v3.source_documents",
                {"source_pack_code": pack_code, "raw_document_code": text(document.get("raw_document_code"))},
                depends_on=[{"table": "retrieval_v3.source_packs", "pack_code": pack_code}],
                payload=document,
            )
        )

    for passage in rows["source_passages"]:
        passage_code = text(passage.get("passage_code"))
        document_code = text(passage.get("document_code"))
        if document_code not in documents:
            blockers.append(blocker("source_passages", passage_code, "missing_document", document_code))
            continue
        if not text(passage.get("raw_text")):
            blockers.append(blocker("source_passages", passage_code, "missing_raw_text", "source_passages.raw_text is required by DB schema"))
        operations.append(
            operation(
                "retrieval_v3.source_passages",
                {"document_code": document_code, "raw_passage_code": text(passage.get("raw_passage_code"))},
                depends_on=[{"table": "retrieval_v3.source_documents", "document_code": document_code}],
                payload=passage,
            )
        )

    for claim in rows["material_claims"]:
        claim_code = text(claim.get("claim_code"))
        pack_code = text(claim.get("source_pack_code"))
        direction = enum_direction(claim.get("direction"))
        if pack_code not in source_packs:
            blockers.append(blocker("material_claims", claim_code, "missing_source_pack", pack_code))
        if direction == "":
            blockers.append(blocker("material_claims", claim_code, "invalid_direction", text(claim.get("direction"))))
        if not text(claim.get("object_name")):
            blockers.append(blocker("material_claims", claim_code, "missing_object_name", "object_name is required by DB schema"))
        missing_refs = [ref for ref in claim.get("source_passage_refs") or [] if text(ref) not in passages]
        if missing_refs:
            blockers.append(blocker("material_claims", claim_code, "missing_source_passage_ref", ",".join(text(ref) for ref in missing_refs)))
        alignment_issue = claim_passage_alignment_issue(claim, passages)
        if alignment_issue:
            issue = alignment_issue
            if issue["severity"] == "blocker":
                blockers.append(blocker("material_claims", claim_code, issue["code"], issue["message"]))
            else:
                warnings.append(warning("material_claims", claim_code, issue["code"], issue["message"]))
        operations.append(
            operation(
                "retrieval_v3.material_claims",
                {"raw_claim_code": text(claim.get("raw_claim_code"))},
                depends_on=[{"table": "retrieval_v3.source_packs", "pack_code": pack_code}],
                payload={
                    "claim_code": claim_code,
                    "direction": direction,
                    "claim_summary_hash": stable_hash(text(claim.get("claim_summary"))),
                    "object_group_key": object_group_key(text(claim.get("object_name"))),
                },
            )
        )
        for passage_ref in claim.get("source_passage_refs") or []:
            passage_code = text(passage_ref)
            if passage_code in passages:
                operations.append(
                    operation(
                        "retrieval_v3.claim_source_passages",
                        {"claim_code": claim_code, "passage_code": passage_code, "relation_kind": "supporting_quote"},
                        depends_on=[
                            {"table": "retrieval_v3.material_claims", "claim_code": claim_code},
                            {"table": "retrieval_v3.source_passages", "passage_code": passage_code},
                        ],
                    )
                )

    for binding in rows["primary_claim_rule_bindings"]:
        binding_code = text(binding.get("binding_code"))
        claim_code = text(binding.get("claim_code"))
        pack_code = text(binding.get("source_pack_code"))
        pack = source_packs.get(pack_code, {})
        rule_code = text(binding.get("rule_code"))
        direction = enum_direction(binding.get("direction"))
        if claim_code not in claims:
            blockers.append(blocker("claim_rule_bindings", binding_code, "missing_claim", claim_code))
        if direction == "":
            blockers.append(blocker("claim_rule_bindings", binding_code, "invalid_direction", text(binding.get("direction"))))
        if lookup and not lookup_rule_id(lookup, target_code=text(pack.get("target_code")), rule_code=rule_code):
            blockers.append(blocker("claim_rule_bindings", binding_code, "missing_contract_rule", rule_code))
        operations.append(
            operation(
                "retrieval_v3.claim_rule_bindings",
                {
                    "claim_code": claim_code,
                    "rule_code": rule_code,
                    "predicate": text(binding.get("predicate")),
                    "direction": direction or "",
                    "object_role": text(binding.get("object_role")),
                },
                depends_on=[{"table": "retrieval_v3.material_claims", "claim_code": claim_code}],
                payload=binding,
            )
        )

    for candidate in rows["claim_rule_binding_candidates"]:
        candidate_code = text(candidate.get("candidate_code"))
        claim_code = text(candidate.get("claim_code"))
        pack_code = text(candidate.get("source_pack_code"))
        pack = source_packs.get(pack_code, {})
        candidate_rule_code = text(candidate.get("candidate_rule_code"))
        source_rule_code = text(candidate.get("source_rule_code"))
        direction = enum_direction(candidate.get("candidate_direction"))
        if claim_code not in claims:
            blockers.append(blocker("claim_rule_binding_candidates", candidate_code, "missing_claim", claim_code))
        if direction == "":
            blockers.append(blocker("claim_rule_binding_candidates", candidate_code, "invalid_direction", text(candidate.get("candidate_direction"))))
        source_rule_id = lookup_rule_id(lookup, target_code=text(pack.get("target_code")), rule_code=source_rule_code) if lookup else None
        if lookup and not source_rule_id and source_rule_code not in VIRTUAL_SOURCE_RULES:
            blockers.append(blocker("claim_rule_binding_candidates", candidate_code, "missing_source_contract_rule", source_rule_code))
        hint_status = candidate_hint_status(candidate)
        required_facts_present = candidate_required_facts(candidate)
        candidate_payload = candidate.get("candidate_payload") if isinstance(candidate.get("candidate_payload"), Mapping) else {}
        is_future_hint = hint_status == "future_rule_hint"
        if lookup and candidate_rule_code and not is_future_hint and not lookup_rule_id(lookup, target_code=text(pack.get("target_code")), rule_code=candidate_rule_code):
            warnings.append(warning("claim_rule_binding_candidates", candidate_code, "candidate_rule_not_in_contract", candidate_rule_code))
        operations.append(
            operation(
                "retrieval_v3.claim_rule_binding_candidates",
                {
                    "claim_code": claim_code,
                    "source_rule_code": source_rule_code,
                    "candidate_item_code": text(candidate.get("candidate_item_code")),
                    "candidate_lane": text(candidate.get("candidate_lane")),
                    "candidate_rule_code": candidate_rule_code,
                    "hint_status": hint_status,
                    "required_facts_present": required_facts_present,
                    "reason_hash": reason_hash(text(candidate.get("reason"))),
                },
                depends_on=[{"table": "retrieval_v3.material_claims", "claim_code": claim_code}],
                payload={
                    "hint_status": hint_status,
                    "required_facts_present": required_facts_present,
                    **candidate,
                },
            )
        )

    for event in rows["coverage_gap_events"]:
        event_key = text(event.get("idem_key"))
        pack_code = text(event.get("source_pack_code"))
        if pack_code and pack_code not in source_packs:
            blockers.append(blocker("coverage_gap_events", event_key, "missing_source_pack", pack_code))
        operations.append(
            operation(
                "retrieval_v3.coverage_gap_events",
                {"idem_key": event_key},
                depends_on=[{"table": "retrieval_v3.source_packs", "pack_code": pack_code}] if pack_code else [],
                payload={"status_policy": "preserve_non_ready_status", **event},
            )
        )

    for item in review_rows["object_resolution_worklist"]:
        code = text(item.get("object_resolution_code"))
        pack_codes = [text(value) for value in item.get("source_pack_codes") or [] if text(value)]
        pack = source_packs.get(pack_codes[0], {}) if pack_codes else {}
        target_code = text(pack.get("target_code"))
        if not target_code:
            blockers.append(blocker("object_resolution_queue", code, "missing_target_from_source_pack", ",".join(pack_codes)))
            continue
        queue_status = "needs_review" if text(item.get("review_status")) == "needs_review" else "ready"
        operations.append(
            operation(
                "retrieval_v3.object_resolution_queue",
                {"idem_key": "|".join([target_code, text(item.get("item_code")), text(item.get("object_group_key"))])},
                depends_on=[{"table": "retrieval_v3.source_packs", "pack_code": pack_codes[0]}] if pack_codes else [],
                payload={
                    "resolution_code": code,
                    "target_code": target_code,
                    "object_type": canonical_object_type(item.get("object_types")),
                    "queue_status": queue_status,
                    "diagnosis": ";".join(text(value) for value in item.get("review_reasons") or [] if text(value)),
                },
            )
        )

    queued_material_reviews = 0
    for item in review_rows["material_review_worklist"]:
        if text(item.get("review_status")) != "needs_review":
            continue
        queued_material_reviews += 1
        code = text(item.get("material_review_code"))
        claim_code = text(item.get("claim_code"))
        binding_code = text(item.get("binding_code"))
        allow_unbound_claim_review = item.get("allow_unbound_claim_review") is True
        if claim_code not in claims:
            blockers.append(blocker("material_review_queue", code, "missing_claim", claim_code))
        unbound_claim_review = allow_unbound_claim_review and not binding_code
        if binding_code not in bindings and not unbound_claim_review:
            blockers.append(blocker("material_review_queue", code, "missing_binding", binding_code))
        dependencies = [{"table": "retrieval_v3.material_claims", "claim_code": claim_code}]
        if binding_code:
            dependencies.append({"table": "retrieval_v3.claim_rule_bindings", "binding_code": binding_code})
        operations.append(
            operation(
                "retrieval_v3.material_review_queue",
                {"idem_key": "|".join([claim_code, binding_code, "material_review"])},
                depends_on=dependencies,
                payload={
                    "review_code": code,
                    "review_kind": ",".join(text(value) for value in item.get("review_flags") or [] if text(value)) or "material_review",
                    "queue_status": "ready",
                    "diagnosis": ",".join(text(value) for value in item.get("review_flags") or [] if text(value)),
                },
            )
        )

    operation_counts = Counter(op["table"] for op in operations)
    deferred = {
        "objects": len(review_rows["object_resolution_worklist"]),
        "object_names": len(review_rows["object_resolution_worklist"]),
        "target_objects": len(review_rows["object_resolution_worklist"]),
        "material_object_links": sum(1 for row in review_rows["material_review_worklist"] if text(row.get("review_status")) == "ready_for_object_payload"),
    }
    review_queue = {
        "object_resolution_queue": len(review_rows["object_resolution_worklist"]),
        "queued_material_reviews": queued_material_reviews,
        "ready_material_reviews_not_queued": sum(1 for row in review_rows["material_review_worklist"] if text(row.get("review_status")) == "ready_for_object_payload"),
    }
    return {
        "generated_by": "scripts/dev/retrieval_v3_import_plan.py",
        "mode": "dry_run_plan",
        "write_db": False,
        "normalized_root": repo_relative(normalized_root),
        "review_root": repo_relative(review_root) if review_root else "",
        "db_check": lookup is not None,
        "ok": not blockers,
        "totals": {
            "operations": len(operations),
            "blockers": len(blockers),
            "warnings": len(warnings),
            "deferred": sum(deferred.values()),
        },
        "operation_counts": dict(sorted(operation_counts.items())),
        "deferred": deferred,
        "review_queue": review_queue,
        "blockers": blockers,
        "warnings": warnings,
        "operations": operations,
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 import dry-run plan",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed', False)).lower()}`",
        f"- db_check: `{str(payload.get('db_check')).lower()}`",
        f"- operations: `{payload.get('totals', {}).get('operations', 0)}`",
        f"- blockers: `{payload.get('totals', {}).get('blockers', 0)}`",
        f"- warnings: `{payload.get('totals', {}).get('warnings', 0)}`",
        "",
        "| table | operations |",
        "| --- | ---: |",
    ]
    for table, count in (payload.get("operation_counts") or {}).items():
        lines.append(f"| {table} | {count} |")
    if payload.get("deferred"):
        lines.extend(["", "## Deferred", ""])
        for key, value in sorted((payload.get("deferred") or {}).items()):
            lines.append(f"- `{key}`: {value}")
    if payload.get("review_queue"):
        lines.extend(["", "## Review Queue", ""])
        for key, value in sorted((payload.get("review_queue") or {}).items()):
            lines.append(f"- `{key}`: {value}")
    if payload.get("executed_counts"):
        lines.extend(["", "## Executed", "", "| table | rows |", "| --- | ---: |"])
        for table, count in (payload.get("executed_counts") or {}).items():
            lines.append(f"| {table} | {count} |")
    if payload.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for item in payload.get("blockers") or []:
            lines.append(f"- `{item.get('table')}` `{item.get('row_code')}` `{item.get('code')}`: {item.get('message')}")
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for item in payload.get("warnings") or []:
            lines.append(f"- `{item.get('table')}` `{item.get('row_code')}` `{item.get('code')}`: {item.get('message')}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a dry-run upsert plan for retrieval_v3 normalized rows.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="Build a read-only import plan.")
    plan.add_argument("--normalized-root", type=Path, required=True)
    plan.add_argument("--review-root", type=Path)
    plan.add_argument("--output-json", type=Path, required=True)
    plan.add_argument("--output-md", type=Path, required=True)
    plan.add_argument("--db-check", action="store_true", help="Read retrieval_v3 target/rule metadata to validate FK lookups.")
    plan.add_argument("--env-file", type=Path)
    plan.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    plan.add_argument("--pg-schema", default="retrieval_v3", help="Schema used only by --db-check; defaults to retrieval_v3 for compatibility.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "plan":
        raise ImportPlanError(f"unsupported command: {args.command}")
    lookup = db_lookup(env_file=args.env_file, dsn_env=args.dsn_env, schema_name=args.pg_schema) if args.db_check else None
    payload = build_plan(normalized_root=args.normalized_root, review_root=args.review_root, lookup=lookup)
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 1 if not payload["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
