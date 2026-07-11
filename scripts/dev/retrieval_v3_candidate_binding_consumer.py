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

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import json_param, stable_hash  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_contract_reanchor_consumer import REANCHOR_PROFILE  # noqa: E402
from scripts.dev.retrieval_v3_contract_reanchor_plan import NATIVE_CONTRACT_CODE, RULE_CODE  # noqa: E402


MATERIAL_CANDIDATE_PROFILE = "retrieval_v3_material_candidate_plan"
BINDING_PROFILES = (REANCHOR_PROFILE, MATERIAL_CANDIDATE_PROFILE)


class CandidateBindingConsumerError(RuntimeError):
    pass


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def review_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("candidate_payload")
    if not isinstance(payload, Mapping):
        return {}
    review = payload.get("candidate_review")
    return review if isinstance(review, Mapping) else {}


def reanchor_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("candidate_payload")
    if not isinstance(payload, Mapping):
        return {}
    reanchor = payload.get("reanchor")
    return reanchor if isinstance(reanchor, Mapping) else {}


def binding_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    review = review_payload(row)
    direction = text(review.get("direction") or row.get("candidate_direction") or row.get("claim_direction"))
    if direction not in {"positive", "negative"}:
        raise CandidateBindingConsumerError(f"unsupported candidate direction for {row.get('candidate_code')}: {direction}")
    role = text(review.get("candidate_role") or row.get("candidate_object_role"))
    if not role:
        raise CandidateBindingConsumerError(f"missing candidate role for {row.get('candidate_code')}")
    predicate = "appointed_or_delegated_authority" if direction == "positive" else "misappointed_or_misdelegated_authority"
    return {"direction": direction, "object_role": role, "predicate": predicate}


def binding_code_for(candidate_code: str) -> str:
    return "BND-R3R-" + stable_hash([candidate_code, RULE_CODE], length=20)


def link_code_for(claim_code: str, object_identity_key: str, role: str) -> str:
    return "MOL-R3R-" + stable_hash([claim_code, object_identity_key, role], length=20)


def fetch_candidates(
    cur: Any,
    *,
    profiles: Sequence[str] = BINDING_PROFILES,
    emperor_names: Sequence[str] = (),
) -> list[dict[str, Any]]:
    selected_profiles = [text(value) for value in profiles if text(value)]
    selected_emperors = [text(value) for value in emperor_names if text(value)]
    cur.execute(
        """
        select
            c.id as candidate_id,
            c.candidate_code,
            c.claim_id,
            c.candidate_contract_rule_id,
            c.candidate_rule_code,
            c.candidate_object_role,
            c.candidate_direction::text as candidate_direction,
            c.candidate_reason,
            c.confidence as candidate_confidence,
            c.candidate_payload,
            mc.claim_code,
            mc.direction as claim_direction,
            mc.claim_summary,
            sp.id as source_pack_id,
            sp.pack_code as source_pack_code,
            rt.id as target_id,
            rt.target_code,
            rt.emperor_name,
            o.id as object_id,
            o.object_identity_key,
            o.canonical_name,
            tob.id as target_object_id,
            tob.review_status::text as target_object_review_status
          from retrieval_v2.claim_rule_binding_candidates c
          join retrieval_v2.material_claims mc on mc.id = c.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          join retrieval_v2.rule_contracts rc on rc.id = rt.contract_id and rc.contract_code = %s
          join retrieval_v2.target_objects tob
            on (
                c.routed_by_profile = %s
                and tob.id = nullif(c.candidate_payload #>> '{reanchor,native_target_object_id}', '')::bigint
            ) or (
                c.routed_by_profile <> %s
                and tob.target_id = rt.id
                and exists (
                    select 1
                      from retrieval_v2.objects matched_object
                     where matched_object.id = tob.object_id
                       and (
                           lower(matched_object.canonical_name) = lower(mc.object_name)
                           or exists (
                               select 1
                                 from retrieval_v2.object_names onm
                                where onm.object_id = matched_object.id
                                  and onm.review_status::text = 'accepted'
                                  and (
                                      lower(onm.name_text) = lower(mc.object_name)
                                      or lower(onm.normalized_name) = lower(mc.object_name)
                                  )
                           )
                       )
                )
            )
          join retrieval_v2.objects o on o.id = tob.object_id
         where c.routed_by_profile = any(%s)
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
           and c.candidate_rule_code = %s
           and c.review_status = 'accepted'
           and c.resolved_binding_id is null
           and c.candidate_contract_rule_id is not null
           and c.candidate_payload #>> '{candidate_review,identity_gate}' = 'identity_ready'
           and c.candidate_payload #>> '{candidate_review,review_verdict}' = 'accepted_candidate'
           and c.candidate_payload #>> '{candidate_review,scoring_candidate}' = 'true'
           and c.candidate_payload #>> '{candidate_review,usable_for_scoring_cluster}' = 'true'
           and tob.review_status = 'accepted'
         order by rt.emperor_name, c.id
        """,
        (NATIVE_CONTRACT_CODE, REANCHOR_PROFILE, REANCHOR_PROFILE, selected_profiles, selected_emperors, selected_emperors, RULE_CODE),
    )
    return [dict(row) for row in cur.fetchall()]


def upsert_binding(cur: Any, row: Mapping[str, Any], fields: Mapping[str, Any]) -> int:
    binding_code = binding_code_for(text(row.get("candidate_code")))
    payload = {
        "source": "retrieval_v3_candidate_binding_consumer",
        "candidate_required": True,
        "candidate_id": row.get("candidate_id"),
        "candidate_code": text(row.get("candidate_code")),
        "source_pack_code": text(row.get("source_pack_code")),
        "target_object_id": row.get("target_object_id"),
        "object_id": row.get("object_id"),
        "object_name": text(row.get("canonical_name")),
        "review": dict(review_payload(row)),
        "usable_for_scoring_cluster": True,
    }
    cur.execute(
        """
        insert into retrieval_v2.claim_rule_bindings (
            claim_id, contract_rule_id, rule_code, predicate, direction, object_role,
            usable_for_object_payload, usable_for_scoring_cluster, confidence, review_status,
            binding_payload, binding_code, raw_binding_code
        )
        values (%s, %s, %s, %s, %s, %s, false, true, %s, 'pending', %s::jsonb, %s, '')
        on conflict on constraint rv2_claim_rule_bindings_uk do update set
            usable_for_scoring_cluster = true,
            confidence = coalesce(retrieval_v2.claim_rule_bindings.confidence, excluded.confidence),
            review_status = case
                when retrieval_v2.claim_rule_bindings.review_status in ('rejected', 'retired') then retrieval_v2.claim_rule_bindings.review_status
                else retrieval_v2.claim_rule_bindings.review_status
            end,
            binding_payload = retrieval_v2.claim_rule_bindings.binding_payload || excluded.binding_payload,
            binding_code = case
                when btrim(retrieval_v2.claim_rule_bindings.binding_code) = '' then excluded.binding_code
                else retrieval_v2.claim_rule_bindings.binding_code
            end,
            updated_at = now()
        returning id
        """,
        (
            int(row["claim_id"]),
            int(row["candidate_contract_rule_id"]),
            RULE_CODE,
            text(fields.get("predicate")),
            text(fields.get("direction")),
            text(fields.get("object_role")),
            row.get("candidate_confidence"),
            json_param(payload),
            binding_code,
        ),
    )
    fetched = cur.fetchone()
    if not fetched or fetched.get("id") is None:
        raise CandidateBindingConsumerError(f"failed to upsert binding for {row.get('candidate_code')}")
    return int(fetched["id"])


def upsert_material_object_link(cur: Any, row: Mapping[str, Any], fields: Mapping[str, Any]) -> int:
    link_code = link_code_for(text(row.get("claim_code")), text(row.get("object_identity_key")), text(fields.get("object_role")))
    payload = {
        "source": "retrieval_v3_candidate_binding_consumer",
        "candidate_id": row.get("candidate_id"),
        "candidate_code": text(row.get("candidate_code")),
        "target_object_id": row.get("target_object_id"),
        "object_name": text(row.get("canonical_name")),
    }
    cur.execute(
        """
        insert into retrieval_v2.material_object_links (
            link_code, claim_id, object_id, target_object_id, role,
            confidence, review_status, link_payload
        )
        values (%s, %s, %s, %s, %s, %s, 'accepted', %s::jsonb)
        on conflict on constraint rv2_material_object_links_uk do update set
            target_object_id = coalesce(retrieval_v2.material_object_links.target_object_id, excluded.target_object_id),
            confidence = case
                when excluded.confidence is null then retrieval_v2.material_object_links.confidence
                when retrieval_v2.material_object_links.confidence is null then excluded.confidence
                else greatest(retrieval_v2.material_object_links.confidence, excluded.confidence)
            end,
            review_status = case
                when retrieval_v2.material_object_links.review_status in ('rejected', 'retired') then retrieval_v2.material_object_links.review_status
                else excluded.review_status
            end,
            link_payload = retrieval_v2.material_object_links.link_payload || excluded.link_payload,
            updated_at = now()
        returning id
        """,
        (
            link_code,
            int(row["claim_id"]),
            int(row["object_id"]),
            int(row["target_object_id"]),
            text(fields.get("object_role")),
            row.get("candidate_confidence"),
            json_param(payload),
        ),
    )
    fetched = cur.fetchone()
    if not fetched or fetched.get("id") is None:
        raise CandidateBindingConsumerError(f"failed to upsert material_object_link for {row.get('candidate_code')}")
    return int(fetched["id"])


def attach_link_to_binding(cur: Any, row: Mapping[str, Any], fields: Mapping[str, Any], *, binding_id: int, link_id: int) -> None:
    payload = {
        "promoted_material_object_link_id": link_id,
        "promoted_object_id": row.get("object_id"),
        "promoted_target_object_id": row.get("target_object_id"),
        "promoted_object_name": text(row.get("canonical_name")),
        "promoted_object_role": text(fields.get("object_role")),
    }
    cur.execute(
        """
        update retrieval_v2.claim_rule_bindings
           set binding_payload = binding_payload || %s::jsonb,
               updated_at = now()
         where id = %s
        returning id
        """,
        (json_param(payload), binding_id),
    )
    if not cur.fetchone():
        raise CandidateBindingConsumerError(f"failed to attach link to binding for {row.get('candidate_code')}")


def mark_candidate_resolved(cur: Any, row: Mapping[str, Any], fields: Mapping[str, Any], *, binding_id: int, link_id: int) -> None:
    payload = {
        "formal_binding": {
            "source": "retrieval_v3_candidate_binding_consumer",
            "binding_id": binding_id,
            "binding_code": binding_code_for(text(row.get("candidate_code"))),
            "material_object_link_id": link_id,
            "predicate": text(fields.get("predicate")),
            "object_role": text(fields.get("object_role")),
            "direction": text(fields.get("direction")),
        }
    }
    cur.execute(
        """
        update retrieval_v2.claim_rule_binding_candidates
           set resolved_binding_id = %s,
               review_status = 'resolved'::retrieval_v2.rv2_review_status,
               candidate_payload = candidate_payload || %s::jsonb,
               updated_at = now()
         where id = %s
        returning id
        """,
        (binding_id, json_param(payload), int(row["candidate_id"])),
    )
    if not cur.fetchone():
        raise CandidateBindingConsumerError(f"failed to mark candidate resolved: {row.get('candidate_code')}")


def run(
    cur: Any,
    *,
    execute: bool,
    profiles: Sequence[str] = BINDING_PROFILES,
    emperor_names: Sequence[str] = (),
) -> dict[str, Any]:
    rows = fetch_candidates(cur, profiles=profiles, emperor_names=emperor_names)
    counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    for row in rows:
        try:
            fields = binding_fields(row)
        except CandidateBindingConsumerError as exc:
            skipped[str(exc)] += 1
            continue
        binding_id = upsert_binding(cur, row, fields)
        counts["retrieval_v3.claim_rule_bindings"] += 1
        link_id = upsert_material_object_link(cur, row, fields)
        counts["retrieval_v3.material_object_links"] += 1
        attach_link_to_binding(cur, row, fields, binding_id=binding_id, link_id=link_id)
        mark_candidate_resolved(cur, row, fields, binding_id=binding_id, link_id=link_id)
        counts["retrieval_v3.claim_rule_binding_candidates"] += 1
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_candidate_binding_consumer.py",
        "write_db": execute,
        "executed": execute,
        "candidate_rows": len(rows),
        "applied_counts": dict(sorted(counts.items())),
        "skipped_by_reason": dict(sorted(skipped.items())),
        "direction_counts": dict(sorted(Counter(binding_fields(row)["direction"] for row in rows if review_payload(row)).items())),
        "requirements_written": 0,
        "intents_written": 0,
        "profiles": [text(value) for value in profiles if text(value)],
        "emperors": [text(value) for value in emperor_names if text(value)],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote accepted v3 candidates into formal native v3 bindings.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            payload = run(
                schema_cursor(raw, schema_name=args.pg_schema),
                execute=args.execute,
                profiles=args.profile or BINDING_PROFILES,
                emperor_names=args.emperor_name,
            )
        if args.execute:
            conn.commit()
        else:
            conn.rollback()
    write_json(args.output_json, payload)
    print(json.dumps({key: payload[key] for key in ("ok", "write_db", "candidate_rows", "applied_counts")}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
