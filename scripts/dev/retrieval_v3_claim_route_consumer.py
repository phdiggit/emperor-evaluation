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

from scripts.dev import retrieval_v3_claim_chain_candidates as chain_candidates  # noqa: E402
from scripts.dev import retrieval_v3_claim_rule_route_plan as route_plan  # noqa: E402
from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_contracts import APPOINTMENT_DELEGATION_RULE_CODE, NATIVE_CONTRACT_CODE  # noqa: E402

PROFILE = "retrieval_v3_claim_route_consumer"
RULE_CODE = APPOINTMENT_DELEGATION_RULE_CODE
ROUTABLE_RULE_CODES = (
    "talent_discovery",
    APPOINTMENT_DELEGATION_RULE_CODE,
    "tolerate_talent",
    "anti_nepotism",
)
ROUTABLE_STATUSES = {"mechanical_current_rule_candidate", "ready_for_rule_route_review", "needs_light_rule_review"}


def stable_hash(value: Any, *, length: int = 20) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_code(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{stable_hash([text(part) for part in parts], length=20)}"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def route_claim_keys(route: Mapping[str, Any]) -> list[str]:
    if text(route.get("route_source_kind")) == "claim":
        return [text(route.get("route_source_key"))]
    evidence = route.get("evidence") if isinstance(route.get("evidence"), Mapping) else {}
    return sorted({text(value) for value in evidence.get("member_claim_keys") or [] if text(value)})


def route_status_for_cache(status: str) -> str:
    return "candidate" if status == "mechanical_current_rule_candidate" else "needs_review"


def fetch_contract_rules(cur: Any, rule_codes: Sequence[str]) -> tuple[int, dict[str, int]]:
    cur.execute("select id from retrieval_v3.rule_contracts where contract_code = %s", (NATIVE_CONTRACT_CODE,))
    contract = cur.fetchone()
    if not contract:
        raise RuntimeError(f"native contract missing: {NATIVE_CONTRACT_CODE}")
    contract_id = int(contract["id"])
    cur.execute(
        "select id, rule_code from retrieval_v3.rule_contract_rules where contract_id = %s and rule_code = any(%s)",
        (contract_id, list(rule_codes)),
    )
    rules = {text(row["rule_code"]): int(row["id"]) for row in cur.fetchall()}
    missing = sorted(set(rule_codes) - rules.keys())
    if missing:
        raise RuntimeError(f"native contract rules missing: {missing}")
    return contract_id, rules


def fetch_materials(cur: Any, claim_keys: Sequence[str], emperor_names: Sequence[str]) -> dict[str, dict[str, Any]]:
    if not claim_keys:
        return {}
    cur.execute(
        """
        select distinct on (mm.claim_key)
               mm.claim_key,
               mc.id as claim_id, mc.claim_code, mc.emperor_name, mc.object_name,
               mc.direction::text as claim_direction, mc.confidence, mc.canonical_event_key,
               mc.raw_claim_code as representative_claim_key,
               sp.id as source_pack_id, sp.pack_code, rt.target_code
          from retrieval_v3.material_claims mc
          join retrieval_v3.material_claim_members mm on mm.material_id = mc.id
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
         where mm.claim_key = any(%s)
           and mc.emperor_name = any(%s)
         order by mm.claim_key, mc.updated_at desc, mc.id desc
        """,
        (list(claim_keys), list(emperor_names)),
    )
    return {text(row["claim_key"]): dict(row) for row in cur.fetchall()}


def upsert_route_cache(cur: Any, route: Mapping[str, Any], claim_key: str) -> None:
    source_kind = text(route.get("route_source_kind"))
    source_key = text(route.get("route_source_key"))
    rule_code = text(route.get("candidate_rule_code"))
    status = text(route.get("route_status"))
    route_key = stable_code("RTE-R3R", source_kind, source_key, claim_key, rule_code)
    payload = dict(route)
    payload.update({"created_from": PROFILE, "formal_binding_allowed": False, "write_db": False})
    cur.execute(
        """
        insert into retrieval_v3.claim_route_cache (
            route_key, claim_key, candidate_item_code, candidate_rule_code, candidate_lane,
            candidate_direction, route_status, route_reason, routed_by_profile, candidate_payload, confidence
        ) values (%s, %s, 'I5B', %s, %s, null, %s::retrieval_v3.rv3_claim_route_status,
                  %s, %s, %s::jsonb, null)
        on conflict (route_key) do update set
            route_status = excluded.route_status,
            route_reason = excluded.route_reason,
            routed_by_profile = excluded.routed_by_profile,
            candidate_payload = excluded.candidate_payload,
            updated_at = now()
        """,
        (
            route_key,
            claim_key,
            rule_code,
            f"I5B.{rule_code}",
            route_status_for_cache(status),
            ",".join(text(value) for value in route.get("reason_codes") or [] if text(value)),
            PROFILE,
            json_param(payload),
        ),
    )


def upsert_candidate(
    cur: Any,
    route: Mapping[str, Any],
    claim_key: str,
    material: Mapping[str, Any],
    *,
    contract_rule_id: int,
    rule_code: str,
) -> None:
    source_kind = text(route.get("route_source_kind"))
    source_key = text(route.get("route_source_key"))
    candidate_code = stable_code("CRBC-R3R", source_kind, source_key, claim_key, rule_code)
    route_status = text(route.get("route_status"))
    payload = dict(route)
    payload.update(
        {
            "created_from": PROFILE,
            "routed_by_profile": PROFILE,
            "cached_claim_key": claim_key,
            "formal_binding_allowed": False,
            "candidate_review": {"identity_gate": "identity_pending", "formal_binding_allowed": False},
        }
    )
    cur.execute(
        """
        insert into retrieval_v3.claim_rule_binding_candidates (
            candidate_code, claim_id, source_contract_rule_id, candidate_contract_rule_id,
            source_item_code, source_rule_code, candidate_item_code, candidate_rule_code,
            candidate_lane, hint_status, required_facts_present, routed_by_profile,
            candidate_predicate, candidate_object_role, candidate_direction, reason_hash,
            candidate_reason, confidence, review_status, candidate_payload
        ) values (%s, %s, %s, %s, 'I5B', %s, 'I5B', %s, %s,
                  'current_rule_candidate', '{}'::jsonb, %s, '', '', 'neutral', %s, %s, %s,
                  'pending', %s::jsonb)
        on conflict on constraint rv3_claim_rule_binding_candidates_uk do update set
            claim_id = excluded.claim_id,
            candidate_contract_rule_id = excluded.candidate_contract_rule_id,
            routed_by_profile = excluded.routed_by_profile,
            candidate_reason = excluded.candidate_reason,
            confidence = excluded.confidence,
            candidate_payload = retrieval_v3.claim_rule_binding_candidates.candidate_payload || excluded.candidate_payload,
            review_status = case
                when retrieval_v3.claim_rule_binding_candidates.resolved_binding_id is not null
                    then retrieval_v3.claim_rule_binding_candidates.review_status
                else 'pending'::retrieval_v3.rv3_review_status
            end,
            updated_at = now()
        """,
        (
            candidate_code,
            int(material["claim_id"]),
            contract_rule_id,
            contract_rule_id,
            rule_code,
            rule_code,
            f"I5B.{rule_code}",
            PROFILE,
            stable_hash(route.get("reason_codes") or []),
            ",".join(text(value) for value in route.get("reason_codes") or [] if text(value)),
            material.get("confidence"),
            json_param(payload),
        ),
    )


def run(cur: Any, *, emperor_names: Sequence[str], rule_codes: Sequence[str] = (RULE_CODE,), execute: bool) -> dict[str, Any]:
    names = sorted({text(value) for value in emperor_names if text(value)})
    if not names:
        raise RuntimeError("at least one --emperor-name is required")
    selected_rules = tuple(dict.fromkeys(text(value) for value in rule_codes if text(value)))
    unsupported = sorted(set(selected_rules) - set(ROUTABLE_RULE_CODES))
    if unsupported:
        raise RuntimeError(f"unsupported routable rule codes: {unsupported}")
    contract_id, contract_rule_ids = fetch_contract_rules(cur, selected_rules)
    claims = chain_candidates.fetch_claim_rows(cur, emperor_names=names, statuses=["active"], owner_scopes=[])
    plan = route_plan.build_plan(claims)
    routes = [
        route
        for route in plan["routes"]
        if text(route.get("candidate_rule_code")) in selected_rules
        and text(route.get("route_status")) in ROUTABLE_STATUSES
    ]
    claim_keys = sorted({key for route in routes for key in route_claim_keys(route)})
    materials = fetch_materials(cur, claim_keys, names)
    counts: Counter[str] = Counter()
    missing_material_keys: set[str] = set()
    event_routes: dict[tuple[str, str], tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for route in routes:
        for claim_key in route_claim_keys(route):
            material = materials.get(claim_key)
            if material is None:
                missing_material_keys.add(claim_key)
                continue
            event_key = text(material.get("canonical_event_key"))
            rule_code = text(route.get("candidate_rule_code"))
            event_routes.setdefault((rule_code, event_key), (route, material))
    if execute:
        cur.execute("set local retrieval_v3.rebuild_bypass='on'")
        for (_rule_code, _event_key), (route, material) in sorted(event_routes.items()):
            claim_key = text(material.get("representative_claim_key"))
            rule_code = text(route.get("candidate_rule_code"))
            upsert_route_cache(cur, route, claim_key)
            counts["retrieval_v3.claim_route_cache"] += 1
            upsert_candidate(
                cur, route, claim_key, material,
                contract_rule_id=contract_rule_ids[rule_code], rule_code=rule_code,
            )
            counts["retrieval_v3.claim_rule_binding_candidates"] += 1
    else:
        counts["retrieval_v3.claim_route_cache"] = len(event_routes)
        counts["retrieval_v3.claim_rule_binding_candidates"] = len(event_routes)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_claim_route_consumer.py",
        "mode": "execute" if execute else "dry_run",
        "write_db": execute,
        "emperors": names,
        "native_contract_id": contract_id,
        "input_claim_count": len(claims),
        "rule_codes": list(selected_rules),
        "route_count": len(routes),
        "route_counts_by_rule": dict(sorted(Counter(text(route.get("candidate_rule_code")) for route in routes).items())),
        "route_claim_key_count": len(claim_keys),
        "material_match_count": len(materials),
        "canonical_event_route_count": len(event_routes),
        "missing_material_claim_keys": sorted(missing_material_keys),
        "material_route_complete": not missing_material_keys,
        "counts": dict(sorted(counts.items())),
        "requirements_written": 0,
        "intents_written": 0,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist claim-cache routes and emit pending v3 native candidates.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--emperor-name", action="append", required=True)
    parser.add_argument("--rule-code", action="append", choices=ROUTABLE_RULE_CODES, default=[])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            payload = run(
                schema_cursor(raw, schema_name=args.pg_schema), emperor_names=args.emperor_name,
                rule_codes=args.rule_code or (RULE_CODE,), execute=args.execute,
            )
        if args.execute:
            conn.commit()
        else:
            conn.rollback()
    write_json(args.output_json, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
