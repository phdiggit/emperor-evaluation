from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import json_param  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


PROFILE = "retrieval_v3_material_candidate_plan"


class IdentityGateConsumerError(ValueError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def classify_group(rows: Sequence[Mapping[str, Any]]) -> tuple[str, dict[str, Any]]:
    objects = {int(row["object_id"]): row for row in rows if row.get("object_id") is not None}
    target_objects = {int(row["target_object_id"]): row for row in rows if row.get("target_object_id") is not None}
    if not objects:
        return "identity_missing", {}
    if len(objects) > 1:
        return "identity_ambiguous", {}
    object_row = next(iter(objects.values()))
    if text(object_row.get("identity_status")) != "active":
        return "object_not_active", {}
    if not target_objects:
        return "target_object_missing", {}
    if len(target_objects) > 1:
        return "identity_ambiguous", {}
    target_row = next(iter(target_objects.values()))
    status = text(target_row.get("target_object_status"))
    if status == "accepted":
        return "identity_ready", {"object_id": object_row["object_id"], "target_object_id": target_row["target_object_id"]}
    if status != "pending":
        return "target_object_not_pending", {}
    return "identity_ready_for_accept", {"object_id": object_row["object_id"], "target_object_id": target_row["target_object_id"]}


def syncs_candidate_identity_gate(decision: str) -> bool:
    return decision in {"identity_ready_for_accept", "identity_ready"}


def fetch_groups(cur: Any, *, source_pack_codes: Sequence[str] = ()) -> dict[int, list[dict[str, Any]]]:
    pack_codes = [text(code) for code in source_pack_codes if text(code)]
    cur.execute(
        """
        select c.id as candidate_id, c.candidate_code, c.candidate_payload,
               mc.object_name, mc.object_type::text as object_type,
               rt.id as target_id, rt.target_code,
               o.id as object_id, o.canonical_name, o.identity_status::text as identity_status,
               tob.id as target_object_id, tob.review_status::text as target_object_status
          from retrieval_v3.claim_rule_binding_candidates c
          join retrieval_v3.material_claims mc on mc.id = c.claim_id
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
          left join retrieval_v3.objects o
            on lower(o.canonical_name) = lower(mc.object_name)
            or exists (
                select 1
                  from retrieval_v3.object_names onm
                 where onm.object_id = o.id
                   and onm.review_status::text = 'accepted'
                   and (
                       lower(onm.name_text) = lower(mc.object_name)
                       or lower(onm.normalized_name) = lower(mc.object_name)
                   )
            )
          left join retrieval_v3.target_objects tob on tob.target_id = rt.id and tob.object_id = o.id
         where c.routed_by_profile = %s
           and c.review_status::text = %s
           and c.candidate_rule_code = %s
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or sp.pack_code = any(%s::text[]))
        """,
        (PROFILE, "accepted", "appointment_delegation", pack_codes, pack_codes),
    )
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in cur.fetchall():
        grouped[int(row["candidate_id"])].append(dict(row))
    return grouped


def run_consumer(
    *,
    dsn: str,
    schema_name: str,
    execute: bool,
    source_pack_codes: Sequence[str] = (),
) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            groups = fetch_groups(cur, source_pack_codes=source_pack_codes)
            decisions: Counter[str] = Counter()
            eligible: list[dict[str, Any]] = []
            ready_candidates: list[dict[str, Any]] = []
            for candidate_id, rows in groups.items():
                decision, ids = classify_group(rows)
                decisions[decision] += 1
                if decision == "identity_ready_for_accept":
                    eligible.append({"candidate_id": candidate_id, **ids})
                if syncs_candidate_identity_gate(decision):
                    ready_candidates.append({"candidate_id": candidate_id, **ids})
            changed_target_objects = 0
            changed_candidates = 0
            if execute:
                for item in eligible:
                    cur.execute(
                        """
                        update retrieval_v3.target_objects
                           set review_status = %s::retrieval_v3.rv3_review_status,
                               target_object_payload = target_object_payload || %s::jsonb,
                               updated_at = now()
                         where id = %s and review_status::text = %s
                        """,
                        (
                            "accepted",
                            json_param({"identity_gate": {"status": "accepted", "source": "retrieval_v3_identity_gate_consumer"}}),
                            item["target_object_id"],
                            "pending",
                        ),
                    )
                    changed_target_objects += cur.rowcount
                for item in ready_candidates:
                    cur.execute(
                        """
                        update retrieval_v3.claim_rule_binding_candidates
                           set candidate_payload = jsonb_set(
                               candidate_payload,
                               %s::text[],
                               %s::jsonb,
                               true
                           ), updated_at = now()
                         where id = %s
                        """,
                        (
                            ["candidate_review", "identity_gate"],
                            json_param("identity_ready"),
                            item["candidate_id"],
                        ),
                    )
                    changed_candidates += cur.rowcount
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "ok": True,
        "write_db": execute,
        "executed": execute,
        "accepted_candidates": len(groups),
        "decision_counts": dict(sorted(decisions.items())),
        "eligible_candidate_count": len(eligible),
        "identity_ready_candidate_count": len(ready_candidates),
        "target_objects_changed": changed_target_objects,
        "candidate_payloads_changed": changed_candidates,
        "formal_binding_created": 0,
        "material_object_links_created": 0,
        "legacy_data_reads": False,
        "legacy_data_migrated": False,
        "source_pack_codes": [text(code) for code in source_pack_codes if text(code)],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply exact-match v3 identity gate; dry-run unless --execute.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-pack-code", action="append", default=[])
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    payload = run_consumer(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        execute=args.execute,
        source_pack_codes=args.source_pack_code,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
