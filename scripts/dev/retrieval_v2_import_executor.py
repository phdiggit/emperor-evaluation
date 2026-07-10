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

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import (  # noqa: E402
    ImportPlanError,
    build_plan,
    candidate_hint_status,
    candidate_required_facts,
    canonical_object_type,
    enum_direction,
    index_by,
    json_param,
    load_normalized_rows,
    load_review_rows,
    lookup_from_cursor,
    lookup_rule_id,
    lookup_target,
    markdown_report,
    reason_hash,
    stable_hash,
    write_json,
)
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import schema_cursor  # noqa: E402
from scripts.dev.retrieval_v2_review_worklists import object_group_key  # noqa: E402


def canon_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest() if url else ""


def fetch_one_id(cur: Any) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ImportPlanError("expected upsert statement to return id")
    return int(row["id"])


def upsert_source_pack(cur: Any, row: Mapping[str, Any], lookup: Mapping[str, Any], *, source_pack_status: str = "accepted") -> int:
    pack_code = text(row.get("source_pack_code"))
    target = lookup_target(lookup, text(row.get("target_code")))
    fingerprint = stable_hash(row.get("manifest_payload") or row)
    cur.execute(
        """
        insert into retrieval_v2.source_packs (
            pack_code, target_id, contract_id, pack_version, status, pack_root,
            manifest_payload, coverage_status, accepted_run_fingerprint, intake_manifest_path
        )
        values (%s, %s, %s, %s, %s, %s, %s::jsonb, 'passed', %s, %s)
        on conflict (pack_code) do update set
            status = excluded.status,
            coverage_status = 'passed',
            pack_root = excluded.pack_root,
            manifest_payload = excluded.manifest_payload,
            accepted_run_fingerprint = excluded.accepted_run_fingerprint,
            intake_manifest_path = excluded.intake_manifest_path,
            updated_at = now()
        returning id
        """,
        (
            pack_code,
            target["id"],
            target["contract_id"],
            fingerprint,
            source_pack_status,
            text(row.get("run_root")),
            json_param(row.get("manifest_payload") or row),
            fingerprint,
            text(row.get("manifest_payload", {}).get("manifest_path") if isinstance(row.get("manifest_payload"), Mapping) else ""),
        ),
    )
    return fetch_one_id(cur)


def upsert_source_pack_artifact(cur: Any, row: Mapping[str, Any], pack_ids: Mapping[str, int]) -> int:
    pack_code = text(row.get("source_pack_code"))
    cur.execute(
        """
        insert into retrieval_v2.source_pack_artifacts (
            source_pack_id, artifact_kind, artifact_path, sha256, artifact_payload
        )
        values (%s, %s, %s, %s, %s::jsonb)
        on conflict on constraint rv2_source_pack_artifacts_uk do update set
            sha256 = excluded.sha256,
            artifact_payload = excluded.artifact_payload
        returning id
        """,
        (pack_ids[pack_code], text(row.get("kind")), text(row.get("path")), text(row.get("sha256")), json_param(row)),
    )
    return fetch_one_id(cur)


def upsert_source_document(cur: Any, row: Mapping[str, Any], pack_ids: Mapping[str, int]) -> int:
    canon_url = text(row.get("canon_url"))
    cur.execute(
        """
        insert into retrieval_v2.source_documents (
            source_pack_id, document_code, raw_document_code, source_title, title,
            locator, canon_url, canon_url_hash, source_kind, document_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (document_code) do update set
            raw_document_code = excluded.raw_document_code,
            source_title = excluded.source_title,
            title = excluded.title,
            locator = excluded.locator,
            canon_url = excluded.canon_url,
            canon_url_hash = excluded.canon_url_hash,
            source_kind = excluded.source_kind,
            document_payload = excluded.document_payload,
            updated_at = now()
        returning id
        """,
        (
            pack_ids[text(row.get("source_pack_code"))],
            text(row.get("document_code")),
            text(row.get("raw_document_code")),
            text(row.get("source_title")),
            text(row.get("title")),
            text(row.get("locator")),
            canon_url,
            canon_url_hash(canon_url),
            text(row.get("source_kind") or "wikisource_page"),
            json_param(row.get("document_payload") or row),
        ),
    )
    return fetch_one_id(cur)


def upsert_source_passage(cur: Any, row: Mapping[str, Any], document_ids: Mapping[str, int]) -> int:
    cur.execute(
        """
        insert into retrieval_v2.source_passages (
            source_document_id, passage_code, raw_passage_code, deduped_raw_passage_codes,
            locator, raw_text, norm_text, quote_hash, passage_payload
        )
        values (%s, %s, %s, %s, %s, %s, '', %s, %s::jsonb)
        on conflict (passage_code) do update set
            raw_passage_code = excluded.raw_passage_code,
            deduped_raw_passage_codes = excluded.deduped_raw_passage_codes,
            locator = excluded.locator,
            raw_text = excluded.raw_text,
            quote_hash = excluded.quote_hash,
            passage_payload = excluded.passage_payload
        returning id
        """,
        (
            document_ids[text(row.get("document_code"))],
            text(row.get("passage_code")),
            text(row.get("raw_passage_code")),
            [text(value) for value in row.get("deduped_raw_passage_codes") or [] if text(value)],
            text(row.get("locator")),
            text(row.get("raw_text")),
            text(row.get("quote_hash")),
            json_param(row.get("passage_payload") or row),
        ),
    )
    return fetch_one_id(cur)


def upsert_material_claim(cur: Any, row: Mapping[str, Any], pack_ids: Mapping[str, int], passage_ids: Mapping[str, int]) -> int:
    passage_refs = [text(value) for value in row.get("source_passage_refs") or [] if text(value)]
    first_passage_id = passage_ids.get(passage_refs[0]) if passage_refs else None
    summary = text(row.get("claim_summary"))
    cur.execute(
        """
        insert into retrieval_v2.material_claims (
            source_pack_id, source_passage_id, claim_code, raw_claim_code,
            emperor_name, object_name, object_type, claim_kind, claim_summary,
            claim_summary_hash, object_group_key, direction, confidence, review_status, claim_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (claim_code) do update set
            source_passage_id = excluded.source_passage_id,
            raw_claim_code = excluded.raw_claim_code,
            emperor_name = excluded.emperor_name,
            object_name = excluded.object_name,
            object_type = excluded.object_type,
            claim_kind = excluded.claim_kind,
            claim_summary = excluded.claim_summary,
            claim_summary_hash = excluded.claim_summary_hash,
            object_group_key = excluded.object_group_key,
            direction = excluded.direction,
            confidence = excluded.confidence,
            review_status = case
                when retrieval_v2.material_claims.review_status = 'pending' then excluded.review_status
                else retrieval_v2.material_claims.review_status
            end,
            claim_payload = excluded.claim_payload,
            updated_at = now()
        returning id
        """,
        (
            pack_ids[text(row.get("source_pack_code"))],
            first_passage_id,
            text(row.get("claim_code")),
            text(row.get("raw_claim_code")),
            text(row.get("emperor_name")),
            text(row.get("object_name")),
            text(row.get("object_type") or "person"),
            text(row.get("claim_kind") or "material_claim"),
            summary,
            stable_hash(summary),
            object_group_key(text(row.get("object_name"))),
            text(row.get("direction")),
            row.get("confidence"),
            text(row.get("review_status") or "pending"),
            json_param(row.get("claim_payload") or row),
        ),
    )
    return fetch_one_id(cur)


def upsert_claim_source_passage(cur: Any, *, claim_id: int, passage_id: int, pack_id: int, relation_payload: Mapping[str, Any]) -> int:
    cur.execute(
        """
        insert into retrieval_v2.claim_source_passages (
            claim_id, source_passage_id, source_pack_id, relation_kind, relation_payload
        )
        values (%s, %s, %s, 'supporting_quote', %s::jsonb)
        on conflict on constraint rv2_claim_source_passages_uk do update set
            relation_payload = excluded.relation_payload
        returning id
        """,
        (claim_id, passage_id, pack_id, json_param(relation_payload)),
    )
    return fetch_one_id(cur)


def upsert_claim_rule_binding(
    cur: Any,
    row: Mapping[str, Any],
    *,
    claim_ids: Mapping[str, int],
    source_packs: Mapping[str, Mapping[str, Any]],
    lookup: Mapping[str, Any],
) -> int:
    pack = source_packs[text(row.get("source_pack_code"))]
    contract_rule_id = lookup_rule_id(lookup, target_code=text(pack.get("target_code")), rule_code=text(row.get("rule_code")))
    if contract_rule_id is None:
        raise ImportPlanError(f"missing contract rule for binding: {row.get('binding_code')}")
    cur.execute(
        """
        insert into retrieval_v2.claim_rule_bindings (
            claim_id, contract_rule_id, rule_code, predicate, direction, object_role,
            usable_for_object_payload, usable_for_scoring_cluster, confidence, review_status,
            binding_payload, binding_code, raw_binding_code
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        on conflict on constraint rv2_claim_rule_bindings_uk do update set
            rule_code = excluded.rule_code,
            usable_for_object_payload = excluded.usable_for_object_payload,
            usable_for_scoring_cluster = excluded.usable_for_scoring_cluster,
            confidence = excluded.confidence,
            review_status = case
                when retrieval_v2.claim_rule_bindings.review_status = 'pending' then excluded.review_status
                else retrieval_v2.claim_rule_bindings.review_status
            end,
            binding_payload = excluded.binding_payload,
            binding_code = excluded.binding_code,
            raw_binding_code = excluded.raw_binding_code,
            updated_at = now()
        returning id
        """,
        (
            claim_ids[text(row.get("claim_code"))],
            contract_rule_id,
            text(row.get("rule_code")),
            text(row.get("predicate")),
            text(row.get("direction")),
            text(row.get("object_role")),
            row.get("usable_for_object_payload") is True,
            row.get("usable_for_scoring_cluster") is True,
            row.get("confidence"),
            text(row.get("review_status") or "pending"),
            json_param(row.get("binding_payload") or row),
            text(row.get("binding_code")),
            text(row.get("raw_binding_code")),
        ),
    )
    return fetch_one_id(cur)


def upsert_claim_rule_binding_candidate(
    cur: Any,
    row: Mapping[str, Any],
    *,
    claim_ids: Mapping[str, int],
    binding_ids: Mapping[str, int],
    source_packs: Mapping[str, Mapping[str, Any]],
    lookup: Mapping[str, Any],
) -> int:
    pack = source_packs[text(row.get("source_pack_code"))]
    target_code = text(pack.get("target_code"))
    source_contract_rule_id = lookup_rule_id(lookup, target_code=target_code, rule_code=text(row.get("source_rule_code")))
    candidate_contract_rule_id = lookup_rule_id(lookup, target_code=target_code, rule_code=text(row.get("candidate_rule_code")))
    resolved_code = text(row.get("resolved_binding_code"))
    direction = enum_direction(row.get("candidate_direction"))
    payload = row.get("candidate_payload") if isinstance(row.get("candidate_payload"), Mapping) else {}
    candidate_rule_code = text(row.get("candidate_rule_code"))
    candidate_lane = text(row.get("candidate_lane") or payload.get("candidate_lane") or payload.get("lane") or candidate_rule_code)
    hint_status = candidate_hint_status(row)
    required_facts_present = candidate_required_facts(row)
    routed_by_profile = text(
        row.get("routed_by_profile")
        or payload.get("routed_by_profile")
        or payload.get("capture_profile")
        or payload.get("created_from")
    )
    cur.execute(
        """
        insert into retrieval_v2.claim_rule_binding_candidates (
            candidate_code, claim_id, source_contract_rule_id, candidate_contract_rule_id,
            source_item_code, source_rule_code, candidate_item_code, candidate_rule_code,
            candidate_lane, hint_status, required_facts_present, routed_by_profile,
            candidate_predicate, candidate_object_role, candidate_direction, reason_hash,
            candidate_reason, confidence, review_status, resolved_binding_id, candidate_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::retrieval_v2.rv2_claim_direction, %s, %s, %s, 'pending', %s, %s::jsonb)
        on conflict on constraint rv2_claim_rule_binding_candidates_code_uk do update set
            source_contract_rule_id = excluded.source_contract_rule_id,
            candidate_contract_rule_id = excluded.candidate_contract_rule_id,
            source_item_code = excluded.source_item_code,
            source_rule_code = excluded.source_rule_code,
            candidate_item_code = excluded.candidate_item_code,
            candidate_rule_code = excluded.candidate_rule_code,
            candidate_lane = excluded.candidate_lane,
            hint_status = excluded.hint_status,
            required_facts_present = excluded.required_facts_present,
            routed_by_profile = excluded.routed_by_profile,
            candidate_predicate = excluded.candidate_predicate,
            candidate_object_role = excluded.candidate_object_role,
            candidate_direction = excluded.candidate_direction,
            reason_hash = excluded.reason_hash,
            candidate_reason = excluded.candidate_reason,
            confidence = excluded.confidence,
            review_status = case
                when retrieval_v2.claim_rule_binding_candidates.review_status = 'pending' then excluded.review_status
                else retrieval_v2.claim_rule_binding_candidates.review_status
            end,
            resolved_binding_id = coalesce(retrieval_v2.claim_rule_binding_candidates.resolved_binding_id, excluded.resolved_binding_id),
            candidate_payload = excluded.candidate_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("candidate_code")),
            claim_ids[text(row.get("claim_code"))],
            source_contract_rule_id,
            candidate_contract_rule_id,
            text(row.get("source_item_code")),
            text(row.get("source_rule_code")),
            text(row.get("candidate_item_code")),
            candidate_rule_code,
            candidate_lane,
            hint_status,
            json_param(required_facts_present),
            routed_by_profile,
            text(row.get("candidate_predicate")),
            text(row.get("candidate_object_role")),
            direction,
            reason_hash(text(row.get("reason"))),
            text(row.get("reason")),
            row.get("confidence"),
            binding_ids.get(resolved_code) if resolved_code else None,
            json_param(payload or row.get("binding_payload") or row),
        ),
    )
    return fetch_one_id(cur)


def upsert_coverage_gap_event(
    cur: Any,
    row: Mapping[str, Any],
    *,
    pack_ids: Mapping[str, int],
    source_packs: Mapping[str, Mapping[str, Any]],
    lookup: Mapping[str, Any],
) -> int:
    target = lookup_target(lookup, text(row.get("target_code")))
    contract_rule_id = lookup_rule_id(lookup, target_code=text(row.get("target_code")), rule_code=text(row.get("rule_code")))
    pack_code = text(row.get("source_pack_code"))
    cur.execute(
        """
        insert into retrieval_v2.coverage_gap_events (
            event_code, idem_key, target_id, contract_rule_id, source_pack_id, coverage_report_id,
            gap_type, queue, diagnosis, recommended_action, status, priority, event_payload
        )
        values (%s, %s, %s, %s, %s, null, %s, %s, %s, %s, 'ready', %s, %s::jsonb)
        on conflict on constraint rv2_coverage_gap_events_idem_uk do update set
            contract_rule_id = excluded.contract_rule_id,
            source_pack_id = excluded.source_pack_id,
            gap_type = excluded.gap_type,
            queue = excluded.queue,
            diagnosis = excluded.diagnosis,
            recommended_action = excluded.recommended_action,
            status = case
                when retrieval_v2.coverage_gap_events.status in ('queued', 'running', 'retry_wait', 'deferred', 'resolved', 'blocked', 'cancelled')
                    then retrieval_v2.coverage_gap_events.status
                else excluded.status
            end,
            priority = excluded.priority,
            event_payload = excluded.event_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("event_code")) or "CGE-" + stable_hash(text(row.get("idem_key")), length=12),
            text(row.get("idem_key")),
            target["id"],
            contract_rule_id,
            pack_ids.get(pack_code),
            text(row.get("gap_type") or "other"),
            text(row.get("queue") or "source_pack_refinement"),
            text(row.get("diagnosis")),
            text(row.get("recommended_action")),
            int(row.get("priority") or 100),
            json_param(row.get("event_payload") or row),
        ),
    )
    return fetch_one_id(cur)


def upsert_object_resolution_queue(
    cur: Any,
    row: Mapping[str, Any],
    *,
    pack_ids: Mapping[str, int],
    source_packs: Mapping[str, Mapping[str, Any]],
    lookup: Mapping[str, Any],
) -> int:
    pack_codes = [text(value) for value in row.get("source_pack_codes") or [] if text(value)]
    pack_code = pack_codes[0] if pack_codes else ""
    pack = source_packs.get(pack_code, {})
    target_code = text(pack.get("target_code"))
    target = lookup_target(lookup, target_code)
    idem_key = "|".join([target_code, text(row.get("item_code")), text(row.get("object_group_key"))])
    queue_status = "needs_review" if text(row.get("review_status")) == "needs_review" else "ready"
    diagnosis = ";".join(text(value) for value in row.get("review_reasons") or [] if text(value))
    object_name = text(row.get("canonical_name_candidate"))
    cur.execute(
        """
        insert into retrieval_v2.object_resolution_queue (
            resolution_code, idem_key, target_id, source_pack_id, claim_id, object_name,
            normalized_name, object_type, object_group_key, suggested_identity_key,
            queue_status, priority, diagnosis, resolution_note, resolved_object_id, queue_payload
        )
        values (%s, %s, %s, %s, null, %s, %s, %s::retrieval_v2.rv2_object_type, %s, %s, %s::retrieval_v2.rv2_queue_status, 100, %s, '', null, %s::jsonb)
        on conflict on constraint rv2_object_resolution_queue_idem_uk do update set
            resolution_code = excluded.resolution_code,
            source_pack_id = excluded.source_pack_id,
            object_name = excluded.object_name,
            normalized_name = excluded.normalized_name,
            object_type = excluded.object_type,
            object_group_key = excluded.object_group_key,
            suggested_identity_key = excluded.suggested_identity_key,
            queue_status = case
                when retrieval_v2.object_resolution_queue.queue_status in ('running', 'resolved', 'blocked', 'cancelled')
                    then retrieval_v2.object_resolution_queue.queue_status
                else excluded.queue_status
            end,
            diagnosis = excluded.diagnosis,
            resolution_note = case
                when btrim(retrieval_v2.object_resolution_queue.resolution_note) <> '' then retrieval_v2.object_resolution_queue.resolution_note
                else excluded.resolution_note
            end,
            queue_payload = excluded.queue_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("object_resolution_code")),
            idem_key,
            target["id"],
            pack_ids.get(pack_code),
            object_name,
            text(row.get("object_group_key")) or object_name,
            canonical_object_type(row.get("object_types")),
            text(row.get("object_group_key")),
            text(row.get("suggested_identity_key")),
            queue_status,
            diagnosis,
            json_param(row),
        ),
    )
    return fetch_one_id(cur)


def upsert_material_review_queue(cur: Any, row: Mapping[str, Any], *, claim_ids: Mapping[str, int], binding_ids: Mapping[str, int]) -> int:
    claim_code = text(row.get("claim_code"))
    binding_code = text(row.get("binding_code"))
    idem_key = "|".join([claim_code, binding_code, "material_review"])
    flags = [text(value) for value in row.get("review_flags") or [] if text(value)]
    cur.execute(
        """
        insert into retrieval_v2.material_review_queue (
            review_code, idem_key, claim_id, binding_id, candidate_id, review_kind,
            queue_status, priority, diagnosis, recommended_action, review_note, review_payload
        )
        values (%s, %s, %s, %s, null, %s, 'ready', 100, %s, %s, '', %s::jsonb)
        on conflict on constraint rv2_material_review_queue_idem_uk do update set
            review_code = excluded.review_code,
            binding_id = excluded.binding_id,
            review_kind = excluded.review_kind,
            queue_status = case
                when retrieval_v2.material_review_queue.queue_status in ('running', 'resolved', 'blocked', 'cancelled')
                    then retrieval_v2.material_review_queue.queue_status
                else excluded.queue_status
            end,
            diagnosis = excluded.diagnosis,
            recommended_action = excluded.recommended_action,
            review_note = case
                when btrim(retrieval_v2.material_review_queue.review_note) <> '' then retrieval_v2.material_review_queue.review_note
                else excluded.review_note
            end,
            review_payload = excluded.review_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("material_review_code")),
            idem_key,
            claim_ids[claim_code],
            binding_ids.get(binding_code),
            ",".join(flags) or "material_review",
            ",".join(flags),
            text(row.get("recommended_action")),
            json_param(row),
        ),
    )
    return fetch_one_id(cur)


def execute_upserts(
    cur: Any,
    *,
    normalized_root: Path,
    review_root: Path | None,
    lookup: Mapping[str, Any],
    source_pack_status: str = "accepted",
) -> dict[str, int]:
    rows = load_normalized_rows(normalized_root)
    review_rows = load_review_rows(review_root)
    source_packs = index_by(rows["source_packs"], "source_pack_code")

    ids: dict[str, dict[str, int]] = {
        "source_packs": {},
        "source_documents": {},
        "source_passages": {},
        "material_claims": {},
        "claim_rule_bindings": {},
        "claim_rule_binding_candidates": {},
        "coverage_gap_events": {},
        "object_resolution_queue": {},
        "material_review_queue": {},
    }
    counts: Counter[str] = Counter()

    for row in rows["source_packs"]:
        code = text(row.get("source_pack_code"))
        ids["source_packs"][code] = upsert_source_pack(cur, row, lookup, source_pack_status=source_pack_status)
        counts["retrieval_v2.source_packs"] += 1

    for row in rows["source_pack_artifacts"]:
        upsert_source_pack_artifact(cur, row, ids["source_packs"])
        counts["retrieval_v2.source_pack_artifacts"] += 1

    for row in rows["source_documents"]:
        code = text(row.get("document_code"))
        ids["source_documents"][code] = upsert_source_document(cur, row, ids["source_packs"])
        counts["retrieval_v2.source_documents"] += 1

    for row in rows["source_passages"]:
        code = text(row.get("passage_code"))
        ids["source_passages"][code] = upsert_source_passage(cur, row, ids["source_documents"])
        counts["retrieval_v2.source_passages"] += 1

    for row in rows["material_claims"]:
        code = text(row.get("claim_code"))
        ids["material_claims"][code] = upsert_material_claim(cur, row, ids["source_packs"], ids["source_passages"])
        counts["retrieval_v2.material_claims"] += 1
        for passage_ref in row.get("source_passage_refs") or []:
            passage_code = text(passage_ref)
            if passage_code in ids["source_passages"]:
                upsert_claim_source_passage(
                    cur,
                    claim_id=ids["material_claims"][code],
                    passage_id=ids["source_passages"][passage_code],
                    pack_id=ids["source_packs"][text(row.get("source_pack_code"))],
                    relation_payload={"claim_code": code, "passage_code": passage_code},
                )
                counts["retrieval_v2.claim_source_passages"] += 1

    for row in rows["primary_claim_rule_bindings"]:
        code = text(row.get("binding_code"))
        ids["claim_rule_bindings"][code] = upsert_claim_rule_binding(
            cur,
            row,
            claim_ids=ids["material_claims"],
            source_packs=source_packs,
            lookup=lookup,
        )
        counts["retrieval_v2.claim_rule_bindings"] += 1

    for row in rows["claim_rule_binding_candidates"]:
        code = text(row.get("candidate_code"))
        ids["claim_rule_binding_candidates"][code] = upsert_claim_rule_binding_candidate(
            cur,
            row,
            claim_ids=ids["material_claims"],
            binding_ids=ids["claim_rule_bindings"],
            source_packs=source_packs,
            lookup=lookup,
        )
        counts["retrieval_v2.claim_rule_binding_candidates"] += 1

    for row in rows["coverage_gap_events"]:
        key = text(row.get("idem_key"))
        ids["coverage_gap_events"][key] = upsert_coverage_gap_event(
            cur,
            row,
            pack_ids=ids["source_packs"],
            source_packs=source_packs,
            lookup=lookup,
        )
        counts["retrieval_v2.coverage_gap_events"] += 1

    for row in review_rows["object_resolution_worklist"]:
        code = text(row.get("object_resolution_code"))
        ids["object_resolution_queue"][code] = upsert_object_resolution_queue(
            cur,
            row,
            pack_ids=ids["source_packs"],
            source_packs=source_packs,
            lookup=lookup,
        )
        counts["retrieval_v2.object_resolution_queue"] += 1

    for row in review_rows["material_review_worklist"]:
        if text(row.get("review_status")) != "needs_review":
            continue
        code = text(row.get("material_review_code"))
        ids["material_review_queue"][code] = upsert_material_review_queue(
            cur,
            row,
            claim_ids=ids["material_claims"],
            binding_ids=ids["claim_rule_bindings"],
        )
        counts["retrieval_v2.material_review_queue"] += 1

    return dict(sorted(counts.items()))


def execute_import(
    *,
    normalized_root: Path,
    review_root: Path | None,
    env_file: Path | None,
    dsn_env: str,
    execute: bool,
    source_pack_status: str = "accepted",
    schema_name: str = "retrieval_v2",
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            lookup = lookup_from_cursor(cur)
            plan = build_plan(normalized_root=normalized_root, review_root=review_root, lookup=lookup)
            report = {
                **{key: value for key, value in plan.items() if key != "operations"},
                "generated_by": "scripts/dev/retrieval_v2_import_executor.py",
                "mode": "execute" if execute else "dry_run_executor",
                "write_db": execute,
                "executed": False,
                "executed_counts": {},
                "source_pack_status": source_pack_status,
            }
            if not plan["ok"]:
                conn.rollback()
                return report
            if not execute:
                conn.rollback()
                return report
            report["executed_counts"] = execute_upserts(
                cur,
                normalized_root=normalized_root,
                review_root=review_root,
                lookup=lookup,
                source_pack_status=source_pack_status,
            )
            report["executed"] = True
        conn.commit()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply retrieval_v2 normalized rows; default is a DB-backed dry-run.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Run the importer executor; default is DB-backed dry-run.")
    apply.add_argument("--normalized-root", type=Path, required=True)
    apply.add_argument("--review-root", type=Path)
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V2_DSN")
    apply.add_argument("--pg-schema", default="retrieval_v2", help="Schema used by the importer; defaults to retrieval_v2 for compatibility.")
    apply.add_argument("--source-pack-status", choices=["accepted", "draft", "ready", "needs_refinement"], default="accepted")
    apply.add_argument("--execute", action="store_true", help="Actually write retrieval_v2 consumption rows. Omit for dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise ImportPlanError(f"unsupported command: {args.command}")
    payload = execute_import(
        normalized_root=args.normalized_root,
        review_root=args.review_root,
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        execute=args.execute,
        source_pack_status=args.source_pack_status,
        schema_name=args.pg_schema,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 1 if not payload["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
