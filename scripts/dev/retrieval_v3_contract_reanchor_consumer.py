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
from scripts.dev.retrieval_v2_import_plan import json_param, stable_hash  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v2_review_worklists import object_group_key  # noqa: E402
from scripts.dev.retrieval_v3_contract_reanchor_plan import (  # noqa: E402
    NATIVE_CONTRACT_CODE,
    PROFILE,
    RULE_CODE,
    code,
)


REANCHOR_PROFILE = "retrieval_v3_contract_reanchor"


class ContractReanchorConsumerError(RuntimeError):
    pass


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def canon_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest() if url else ""


def fetch_one_id(cur: Any, message: str) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ContractReanchorConsumerError(message)
    return int(row["id"])


def merge_payload(payload: Any, extra: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(payload) if isinstance(payload, Mapping) else {}
    base.update(extra)
    return base


def reanchored_pack_code(source_pack_code: str, contract_id: int) -> str:
    return code("SPK-R3R-", source_pack_code, contract_id)


def reanchored_document_code(source_document_code: str, contract_id: int) -> str:
    return code("DOC-R3R-", source_document_code, contract_id)


def reanchored_passage_code(source_passage_code: str, contract_id: int) -> str:
    return code("PAS-R3R-", source_passage_code, contract_id)


def reanchored_claim_code(source_claim_code: str, contract_id: int) -> str:
    return code("CLM-R3R-", source_claim_code, contract_id)


def reanchored_candidate_code(source_candidate_code: str, contract_id: int) -> str:
    return code("CRBC-R3R-", source_candidate_code, contract_id)


def reanchored_target_object_code(target_code: str, object_identity_key: str, scope_code: str) -> str:
    return code("TOB-R3R-", target_code, object_identity_key, scope_code)


def candidate_payload_for_reanchor(row: Mapping[str, Any], *, native_claim_id: int, native_target_object_id: int) -> dict[str, Any]:
    payload = merge_payload(
        row.get("candidate_payload"),
        {
            "created_from": REANCHOR_PROFILE,
            "routed_by_profile": REANCHOR_PROFILE,
            "formal_binding_allowed": True,
            "reanchor": {
                "source": REANCHOR_PROFILE,
                "source_candidate_id": row.get("source_candidate_id"),
                "source_candidate_code": text(row.get("source_candidate_code")),
                "source_claim_id": row.get("source_claim_id"),
                "source_claim_code": text(row.get("source_claim_code")),
                "native_claim_id": native_claim_id,
                "native_claim_code": text(row.get("native_claim_code")),
                "source_target_object_id": row.get("source_target_object_id"),
                "native_target_object_id": native_target_object_id,
                "legacy_data_migrated": False,
            },
        },
    )
    review = dict(payload.get("candidate_review") if isinstance(payload.get("candidate_review"), Mapping) else {})
    review["formal_binding_allowed"] = True
    review["identity_gate"] = "identity_ready"
    payload["candidate_review"] = review
    return payload


def fetch_contract(cur: Any) -> tuple[int, int]:
    cur.execute("select id from retrieval_v2.rule_contracts where contract_code = %s", (NATIVE_CONTRACT_CODE,))
    contract = cur.fetchone()
    if not contract:
        raise ContractReanchorConsumerError(f"native contract missing: {NATIVE_CONTRACT_CODE}")
    contract_id = int(contract["id"])
    cur.execute(
        "select id from retrieval_v2.rule_contract_rules where contract_id = %s and rule_code = %s",
        (contract_id, RULE_CODE),
    )
    rule = cur.fetchone()
    if not rule:
        raise ContractReanchorConsumerError(f"native contract rule missing: {RULE_CODE}")
    return contract_id, int(rule["id"])


def fetch_candidate_rows(cur: Any, *, contract_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            c.id as source_candidate_id,
            c.candidate_code as source_candidate_code,
            c.claim_id as source_claim_id,
            c.source_item_code,
            c.source_rule_code,
            c.candidate_item_code,
            c.candidate_rule_code,
            c.candidate_lane,
            c.hint_status,
            c.required_facts_present,
            c.candidate_predicate,
            c.candidate_object_role,
            c.candidate_direction::text as candidate_direction,
            c.reason_hash,
            c.candidate_reason,
            c.confidence as candidate_confidence,
            c.candidate_payload,
            mc.claim_code as source_claim_code,
            mc.raw_claim_code,
            mc.emperor_name,
            mc.object_name,
            mc.object_type,
            mc.claim_kind,
            mc.claim_summary,
            mc.direction as claim_direction,
            mc.confidence as claim_confidence,
            mc.review_status as claim_review_status,
            mc.claim_payload,
            mc.source_passage_id as source_primary_passage_id,
            osp.id as source_pack_id,
            osp.pack_code as source_pack_code,
            osp.pack_root as source_pack_root,
            osp.manifest_payload as source_manifest_payload,
            osp.accepted_run_fingerprint as source_accepted_run_fingerprint,
            osp.intake_manifest_path as source_intake_manifest_path,
            rt.id as source_target_id,
            rt.target_code as source_target_code,
            nt.id as native_target_id,
            nt.target_code as native_target_code,
            o.id as object_id,
            o.object_code,
            o.object_identity_key,
            o.canonical_name,
            tob.id as source_target_object_id,
            tob.scope_code::text as source_target_object_scope_code,
            tob.object_role as source_target_object_role,
            tob.target_object_payload as source_target_object_payload
          from retrieval_v2.claim_rule_binding_candidates c
          join retrieval_v2.material_claims mc on mc.id = c.claim_id
          join retrieval_v2.source_packs osp on osp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = osp.target_id
          join retrieval_v2.retrieval_targets nt on nt.contract_id = %s and nt.emperor_name = mc.emperor_name
          join retrieval_v2.objects o
            on lower(o.canonical_name) = lower(mc.object_name)
            or exists (
                select 1
                  from retrieval_v2.object_names onm
                 where onm.object_id = o.id
                   and onm.review_status::text = 'accepted'
                   and (
                       lower(onm.name_text) = lower(mc.object_name)
                       or lower(onm.normalized_name) = lower(mc.object_name)
                   )
            )
          join retrieval_v2.target_objects tob
            on tob.target_id = rt.id
           and tob.object_id = o.id
           and tob.review_status = 'accepted'
         where c.routed_by_profile = %s
           and c.candidate_rule_code = %s
           and c.review_status = 'accepted'
           and c.candidate_payload #>> '{candidate_review,identity_gate}' = 'identity_ready'
         order by c.id
        """,
        (contract_id, PROFILE, RULE_CODE),
    )
    rows = [dict(row) for row in cur.fetchall()]
    seen: set[int] = set()
    duplicates: list[int] = []
    for row in rows:
        candidate_id = int(row["source_candidate_id"])
        if candidate_id in seen:
            duplicates.append(candidate_id)
        seen.add(candidate_id)
    if duplicates:
        raise ContractReanchorConsumerError(f"ambiguous identity-ready candidate object joins: {duplicates[:5]}")
    return rows


def fetch_passage_rows(cur: Any, claim_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not claim_ids:
        return []
    cur.execute(
        """
        select distinct
            csp.claim_id as source_claim_id,
            csp.source_passage_id as source_passage_id,
            csp.relation_kind::text as relation_kind,
            csp.relation_payload,
            spg.source_document_id as source_document_id,
            spg.passage_code as source_passage_code,
            spg.raw_passage_code,
            spg.deduped_raw_passage_codes,
            spg.locator as passage_locator,
            spg.raw_text,
            spg.norm_text,
            spg.quote_hash,
            spg.passage_payload,
            sd.source_pack_id as source_pack_id,
            sd.document_code as source_document_code,
            sd.raw_document_code,
            sd.source_title,
            sd.title,
            sd.locator as document_locator,
            sd.canon_url,
            sd.source_kind,
            sd.document_payload
          from retrieval_v2.claim_source_passages csp
          join retrieval_v2.source_passages spg on spg.id = csp.source_passage_id
          join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
         where csp.claim_id = any(%s)
         order by csp.claim_id, csp.source_passage_id
        """,
        (list(claim_ids),),
    )
    return [dict(row) for row in cur.fetchall()]


def upsert_source_pack(cur: Any, row: Mapping[str, Any], *, contract_id: int) -> int:
    payload = merge_payload(
        row.get("source_manifest_payload"),
        {
            "source": REANCHOR_PROFILE,
            "reanchored_from_pack_id": row.get("source_pack_id"),
            "reanchored_from_pack_code": text(row.get("source_pack_code")),
            "native_contract_code": NATIVE_CONTRACT_CODE,
            "legacy_data_migrated": False,
        },
    )
    pack_code = reanchored_pack_code(text(row.get("source_pack_code")), contract_id)
    cur.execute(
        """
        insert into retrieval_v2.source_packs (
            pack_code, target_id, contract_id, pack_version, status, pack_root,
            manifest_payload, coverage_status, accepted_run_fingerprint, intake_manifest_path
        )
        values (%s, %s, %s, 'reanchor-v1', 'accepted', %s, %s::jsonb, 'passed', %s, %s)
        on conflict (pack_code) do update set
            target_id = excluded.target_id,
            contract_id = excluded.contract_id,
            status = excluded.status,
            coverage_status = excluded.coverage_status,
            manifest_payload = retrieval_v2.source_packs.manifest_payload || excluded.manifest_payload,
            updated_at = now()
        returning id
        """,
        (
            pack_code,
            int(row["native_target_id"]),
            contract_id,
            text(row.get("source_pack_root")),
            json_param(payload),
            text(row.get("source_accepted_run_fingerprint")),
            text(row.get("source_intake_manifest_path")),
        ),
    )
    return fetch_one_id(cur, f"failed to upsert source pack: {pack_code}")


def upsert_source_document(cur: Any, row: Mapping[str, Any], *, contract_id: int, pack_id: int) -> int:
    document_code = reanchored_document_code(text(row.get("source_document_code")), contract_id)
    payload = merge_payload(
        row.get("document_payload"),
        {
            "source": REANCHOR_PROFILE,
            "reanchored_from_document_id": row.get("source_document_id"),
            "reanchored_from_document_code": text(row.get("source_document_code")),
        },
    )
    canon_url = text(row.get("canon_url"))
    cur.execute(
        """
        insert into retrieval_v2.source_documents (
            source_pack_id, document_code, raw_document_code, source_title, title,
            locator, canon_url, canon_url_hash, source_kind, document_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (document_code) do update set
            source_pack_id = excluded.source_pack_id,
            raw_document_code = excluded.raw_document_code,
            source_title = excluded.source_title,
            title = excluded.title,
            locator = excluded.locator,
            canon_url = excluded.canon_url,
            canon_url_hash = excluded.canon_url_hash,
            source_kind = excluded.source_kind,
            document_payload = retrieval_v2.source_documents.document_payload || excluded.document_payload,
            updated_at = now()
        returning id
        """,
        (
            pack_id,
            document_code,
            text(row.get("raw_document_code")) or text(row.get("source_document_code")),
            text(row.get("source_title")),
            text(row.get("title")),
            text(row.get("document_locator")),
            canon_url,
            canon_url_hash(canon_url),
            text(row.get("source_kind") or "wikisource_page"),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur, f"failed to upsert source document: {document_code}")


def upsert_source_passage(cur: Any, row: Mapping[str, Any], *, contract_id: int, document_id: int) -> int:
    passage_code = reanchored_passage_code(text(row.get("source_passage_code")), contract_id)
    payload = merge_payload(
        row.get("passage_payload"),
        {
            "source": REANCHOR_PROFILE,
            "reanchored_from_passage_id": row.get("source_passage_id"),
            "reanchored_from_passage_code": text(row.get("source_passage_code")),
        },
    )
    cur.execute(
        """
        insert into retrieval_v2.source_passages (
            source_document_id, passage_code, raw_passage_code, deduped_raw_passage_codes,
            locator, raw_text, norm_text, quote_hash, passage_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (passage_code) do update set
            source_document_id = excluded.source_document_id,
            raw_passage_code = excluded.raw_passage_code,
            deduped_raw_passage_codes = excluded.deduped_raw_passage_codes,
            locator = excluded.locator,
            raw_text = excluded.raw_text,
            norm_text = excluded.norm_text,
            quote_hash = excluded.quote_hash,
            passage_payload = retrieval_v2.source_passages.passage_payload || excluded.passage_payload
        returning id
        """,
        (
            document_id,
            passage_code,
            text(row.get("raw_passage_code")) or text(row.get("source_passage_code")),
            [text(value) for value in row.get("deduped_raw_passage_codes") or [] if text(value)],
            text(row.get("passage_locator")),
            text(row.get("raw_text")),
            text(row.get("norm_text")),
            text(row.get("quote_hash")) or stable_hash(text(row.get("raw_text"))),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur, f"failed to upsert source passage: {passage_code}")


def upsert_material_claim(
    cur: Any,
    row: Mapping[str, Any],
    *,
    contract_id: int,
    pack_id: int,
    primary_passage_id: int | None,
) -> int:
    claim_code = reanchored_claim_code(text(row.get("source_claim_code")), contract_id)
    payload = merge_payload(
        row.get("claim_payload"),
        {
            "source": REANCHOR_PROFILE,
            "reanchored_from_claim_id": row.get("source_claim_id"),
            "reanchored_from_claim_code": text(row.get("source_claim_code")),
            "reanchored_from_candidate_id": row.get("source_candidate_id"),
        },
    )
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
            source_pack_id = excluded.source_pack_id,
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
            review_status = excluded.review_status,
            claim_payload = retrieval_v2.material_claims.claim_payload || excluded.claim_payload,
            updated_at = now()
        returning id
        """,
        (
            pack_id,
            primary_passage_id,
            claim_code,
            text(row.get("raw_claim_code")) or text(row.get("source_claim_code")),
            text(row.get("emperor_name")),
            text(row.get("object_name")),
            text(row.get("object_type") or "person"),
            text(row.get("claim_kind") or "material_claim"),
            summary,
            stable_hash(summary),
            object_group_key(text(row.get("object_name"))),
            text(row.get("claim_direction") or "neutral"),
            row.get("claim_confidence"),
            text(row.get("claim_review_status") or "accepted"),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur, f"failed to upsert material claim: {claim_code}")


def upsert_claim_source_passage(cur: Any, *, claim_id: int, passage_id: int, pack_id: int, row: Mapping[str, Any]) -> int:
    payload = merge_payload(
        row.get("relation_payload"),
        {
            "source": REANCHOR_PROFILE,
            "reanchored_from_claim_id": row.get("source_claim_id"),
            "reanchored_from_passage_id": row.get("source_passage_id"),
        },
    )
    cur.execute(
        """
        insert into retrieval_v2.claim_source_passages (
            claim_id, source_passage_id, source_pack_id, relation_kind, relation_payload
        )
        values (%s, %s, %s, %s::retrieval_v2.rv2_claim_passage_relation_kind, %s::jsonb)
        on conflict on constraint rv2_claim_source_passages_uk do update set
            source_pack_id = excluded.source_pack_id,
            relation_payload = retrieval_v2.claim_source_passages.relation_payload || excluded.relation_payload
        returning id
        """,
        (claim_id, passage_id, pack_id, text(row.get("relation_kind") or "supporting_quote"), json_param(payload)),
    )
    return fetch_one_id(cur, "failed to upsert claim_source_passages")


def upsert_target_object(
    cur: Any,
    row: Mapping[str, Any],
    *,
    pack_id: int,
    claim_id: int,
) -> int:
    scope_code = text(row.get("source_target_object_scope_code") or "item")
    target_object_code = reanchored_target_object_code(text(row.get("native_target_code")), text(row.get("object_identity_key")), scope_code)
    payload = merge_payload(
        row.get("source_target_object_payload"),
        {
            "source": REANCHOR_PROFILE,
            "reanchored_from_target_object_id": row.get("source_target_object_id"),
            "reanchored_from_target_id": row.get("source_target_id"),
            "reanchored_from_target_code": text(row.get("source_target_code")),
            "native_target_code": text(row.get("native_target_code")),
        },
    )
    cur.execute(
        """
        insert into retrieval_v2.target_objects (
            target_object_code, target_id, object_id, source_pack_id, first_claim_id,
            scope_code, object_role, review_status, target_object_payload
        )
        values (%s, %s, %s, %s, %s, %s::retrieval_v2.rv2_target_object_scope, %s, 'accepted', %s::jsonb)
        on conflict on constraint rv2_target_objects_scope_uk do update set
            source_pack_id = coalesce(retrieval_v2.target_objects.source_pack_id, excluded.source_pack_id),
            first_claim_id = coalesce(retrieval_v2.target_objects.first_claim_id, excluded.first_claim_id),
            object_role = case
                when btrim(retrieval_v2.target_objects.object_role) <> '' then retrieval_v2.target_objects.object_role
                else excluded.object_role
            end,
            review_status = case
                when retrieval_v2.target_objects.review_status in ('rejected', 'retired') then retrieval_v2.target_objects.review_status
                else 'accepted'::retrieval_v2.rv2_review_status
            end,
            target_object_payload = retrieval_v2.target_objects.target_object_payload || excluded.target_object_payload,
            updated_at = now()
        returning id
        """,
        (
            target_object_code,
            int(row["native_target_id"]),
            int(row["object_id"]),
            pack_id,
            claim_id,
            scope_code,
            text(row.get("source_target_object_role")),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur, f"failed to upsert target object: {target_object_code}")


def upsert_candidate(
    cur: Any,
    row: Mapping[str, Any],
    *,
    contract_id: int,
    contract_rule_id: int,
    claim_id: int,
    target_object_id: int,
) -> int:
    candidate_code = reanchored_candidate_code(text(row.get("source_candidate_code")), contract_id)
    candidate_payload = candidate_payload_for_reanchor(row, native_claim_id=claim_id, native_target_object_id=target_object_id)
    cur.execute(
        """
        insert into retrieval_v2.claim_rule_binding_candidates (
            candidate_code, claim_id, source_contract_rule_id, candidate_contract_rule_id,
            source_item_code, source_rule_code, candidate_item_code, candidate_rule_code,
            candidate_lane, hint_status, required_facts_present, routed_by_profile,
            candidate_predicate, candidate_object_role, candidate_direction, reason_hash,
            candidate_reason, confidence, review_status, resolved_binding_id, candidate_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'current_rule_candidate', %s::jsonb, %s,
                %s, %s, %s::retrieval_v2.rv2_claim_direction, %s, %s, %s, 'accepted', null, %s::jsonb)
        on conflict on constraint rv2_claim_rule_binding_candidates_code_uk do update set
            claim_id = excluded.claim_id,
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
                when retrieval_v2.claim_rule_binding_candidates.resolved_binding_id is not null then retrieval_v2.claim_rule_binding_candidates.review_status
                else excluded.review_status
            end,
            candidate_payload = retrieval_v2.claim_rule_binding_candidates.candidate_payload || excluded.candidate_payload,
            updated_at = now()
        returning id
        """,
        (
            candidate_code,
            claim_id,
            contract_rule_id,
            contract_rule_id,
            text(row.get("source_item_code") or "I5B"),
            text(row.get("source_rule_code") or RULE_CODE),
            text(row.get("candidate_item_code") or "I5B"),
            RULE_CODE,
            "I5B.appointment_delegation",
            json_param(row.get("required_facts_present") or {}),
            REANCHOR_PROFILE,
            text(row.get("candidate_predicate")),
            text(row.get("candidate_object_role")),
            text(row.get("candidate_direction") or row.get("claim_direction") or "neutral"),
            text(row.get("reason_hash")) or stable_hash(text(row.get("candidate_reason"))),
            text(row.get("candidate_reason")),
            row.get("candidate_confidence"),
            json_param(candidate_payload),
        ),
    )
    return fetch_one_id(cur, f"failed to upsert candidate: {candidate_code}")


def run(cur: Any, *, execute: bool) -> dict[str, Any]:
    contract_id, contract_rule_id = fetch_contract(cur)
    candidate_rows = fetch_candidate_rows(cur, contract_id=contract_id)
    claim_ids = [int(row["source_claim_id"]) for row in candidate_rows]
    passage_rows = fetch_passage_rows(cur, claim_ids)
    passage_rows_by_claim: dict[int, list[dict[str, Any]]] = {}
    for passage in passage_rows:
        passage_rows_by_claim.setdefault(int(passage["source_claim_id"]), []).append(passage)

    counts: Counter[str] = Counter()
    pack_ids: dict[int, int] = {}
    document_ids: dict[int, int] = {}
    passage_ids: dict[int, int] = {}
    claim_id_map: dict[int, int] = {}

    for row in candidate_rows:
        source_pack_id = int(row["source_pack_id"])
        if source_pack_id not in pack_ids:
            pack_ids[source_pack_id] = upsert_source_pack(cur, row, contract_id=contract_id)
            counts["retrieval_v3.source_packs"] += 1

    for passage in passage_rows:
        source_document_id = int(passage["source_document_id"])
        if source_document_id not in document_ids:
            document_ids[source_document_id] = upsert_source_document(
                cur,
                passage,
                contract_id=contract_id,
                pack_id=pack_ids[int(passage["source_pack_id"])],
            )
            counts["retrieval_v3.source_documents"] += 1
        source_passage_id = int(passage["source_passage_id"])
        if source_passage_id not in passage_ids:
            passage_ids[source_passage_id] = upsert_source_passage(
                cur,
                passage,
                contract_id=contract_id,
                document_id=document_ids[source_document_id],
            )
            counts["retrieval_v3.source_passages"] += 1

    for row in candidate_rows:
        source_claim_id = int(row["source_claim_id"])
        passages = passage_rows_by_claim.get(source_claim_id, [])
        primary_source_passage_id = row.get("source_primary_passage_id")
        primary_passage_id = passage_ids.get(int(primary_source_passage_id)) if primary_source_passage_id else None
        if primary_passage_id is None and passages:
            primary_passage_id = passage_ids[int(passages[0]["source_passage_id"])]
        claim_id = claim_id_map.get(source_claim_id)
        if claim_id is None:
            claim_id = upsert_material_claim(
                cur,
                {**row, "native_claim_code": reanchored_claim_code(text(row.get("source_claim_code")), contract_id)},
                contract_id=contract_id,
                pack_id=pack_ids[int(row["source_pack_id"])],
                primary_passage_id=primary_passage_id,
            )
            claim_id_map[source_claim_id] = claim_id
            counts["retrieval_v3.material_claims"] += 1
        for passage in passages:
            upsert_claim_source_passage(
                cur,
                claim_id=claim_id,
                passage_id=passage_ids[int(passage["source_passage_id"])],
                pack_id=pack_ids[int(row["source_pack_id"])],
                row=passage,
            )
            counts["retrieval_v3.claim_source_passages"] += 1
        target_object_id = upsert_target_object(cur, row, pack_id=pack_ids[int(row["source_pack_id"])], claim_id=claim_id)
        counts["retrieval_v3.target_objects"] += 1
        upsert_candidate(
            cur,
            {
                **row,
                "source_claim_code": text(row.get("source_claim_code")),
                "native_claim_code": reanchored_claim_code(text(row.get("source_claim_code")), contract_id),
            },
            contract_id=contract_id,
            contract_rule_id=contract_rule_id,
            claim_id=claim_id,
            target_object_id=target_object_id,
        )
        counts["retrieval_v3.claim_rule_binding_candidates"] += 1

    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_contract_reanchor_consumer.py",
        "write_db": execute,
        "executed": execute,
        "native_contract_code": NATIVE_CONTRACT_CODE,
        "native_contract_id": contract_id,
        "native_contract_rule_id": contract_rule_id,
        "source_candidates": len(candidate_rows),
        "source_claims": len(set(claim_ids)),
        "source_passages": len(passage_ids),
        "source_packs": len(pack_ids),
        "counts": dict(sorted(counts.items())),
        "candidate_counts_by_emperor": dict(sorted(Counter(text(row.get("emperor_name")) for row in candidate_rows).items())),
        "requirements_written": 0,
        "intents_written": 0,
        "legacy_data_reads": False,
        "legacy_data_migrated": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-anchor identity-ready v3 candidates onto the native v3 contract.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            payload = run(schema_cursor(raw, schema_name=args.pg_schema), execute=args.execute)
        if args.execute:
            conn.commit()
        else:
            conn.rollback()
    write_json(args.output_json, payload)
    print(json.dumps({key: payload[key] for key in ("ok", "write_db", "source_candidates", "counts")}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
