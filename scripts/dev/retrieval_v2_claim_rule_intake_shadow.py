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

from scripts.dev import retrieval_v2_claim_chain_candidates as chain_candidates  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_claim_event_groups import owner_scope_values  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_STATUSES = ("active",)
ROUTABLE_CHAIN_TYPES = {"delegated_power_abuse_chain", "appointment_to_outcome_chain"}
READY_CHAIN_READINESS = "ready_for_chain_route_review"
OPEN_MATERIAL_REVIEW_STATUSES = ("ready", "needs_review", "running", "blocked")


def text(value: Any) -> str:
    return str(value or "").strip()


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def ready_rule_route_chains(claims: Sequence[Mapping[str, Any]], *, min_members: int) -> list[dict[str, Any]]:
    return [
        dict(chain)
        for chain in chain_candidates.build_chain_candidates(claims, min_members=min_members)
        if text(chain.get("chain_type")) in ROUTABLE_CHAIN_TYPES
        and text(chain.get("route_readiness")) == READY_CHAIN_READINESS
    ]


def fetch_material_claim_rows(cur: Any, *, claim_keys: Sequence[str]) -> list[dict[str, Any]]:
    keys = [text(key) for key in claim_keys if text(key)]
    if not keys:
        return []
    cur.execute(
        """
        select
            coalesce(nullif(mc.claim_payload->>'cached_claim_key', ''), nullif(mc.claim_payload->>'claim_key', '')) as claim_key,
            mc.id as material_claim_id,
            mc.claim_code,
            mc.review_status::text as material_claim_review_status,
            sp.pack_code as source_pack_code,
            sp.status::text as source_pack_status,
            sp.coverage_status::text as source_pack_coverage_status,
            rt.emperor_name,
            mc.object_name,
            count(distinct csp.id) as linked_passage_count,
            exists (
                select 1
                  from retrieval_v2.material_review_queue mrq
                 where mrq.claim_id = mc.id
                   and mrq.queue_status = any(%s)
            ) as has_open_material_review
          from retrieval_v2.material_claims mc
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join retrieval_v2.claim_source_passages csp on csp.claim_id = mc.id
         where coalesce(nullif(mc.claim_payload->>'cached_claim_key', ''), nullif(mc.claim_payload->>'claim_key', '')) = any(%s)
         group by
            mc.claim_payload, mc.id, mc.claim_code, mc.review_status,
            sp.pack_code, sp.status, sp.coverage_status, rt.emperor_name, mc.object_name
         order by coalesce(nullif(mc.claim_payload->>'cached_claim_key', ''), nullif(mc.claim_payload->>'claim_key', '')), mc.id
        """,
        [list(OPEN_MATERIAL_REVIEW_STATUSES), keys],
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_object_rows(cur: Any, *, chains: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    emperors = sorted({text(chain.get("emperor_name")) for chain in chains if text(chain.get("emperor_name"))})
    objects = sorted({text(chain.get("object_name")) for chain in chains if text(chain.get("object_name"))})
    if not emperors or not objects:
        return []
    cur.execute(
        """
        select
            rt.emperor_name,
            o.canonical_name as object_name,
            o.id as object_id,
            o.object_identity_key,
            tob.id as target_object_id,
            tob.review_status::text as target_object_review_status
          from retrieval_v2.retrieval_targets rt
          join retrieval_v2.target_objects tob on tob.target_id = rt.id
          join retrieval_v2.objects o on o.id = tob.object_id
         where rt.emperor_name = any(%s)
           and o.canonical_name = any(%s)
         order by rt.emperor_name, o.canonical_name, tob.id
        """,
        [emperors, objects],
    )
    return [dict(row) for row in cur.fetchall()]


def material_is_consumable(row: Mapping[str, Any]) -> bool:
    return (
        text(row.get("source_pack_status")) == "accepted"
        and text(row.get("source_pack_coverage_status")) == "passed"
        and not bool(row.get("has_open_material_review"))
        and int(row.get("linked_passage_count") or 0) > 0
    )


def shadow_chain_row(
    chain: Mapping[str, Any],
    *,
    material_by_key: Mapping[str, Sequence[Mapping[str, Any]]],
    objects_by_pair: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    emperor_name = text(chain.get("emperor_name"))
    object_name = text(chain.get("object_name"))
    members = chain.get("members") if isinstance(chain.get("members"), Sequence) else []
    claim_keys = [text(member.get("claim_key")) for member in members if isinstance(member, Mapping) and text(member.get("claim_key"))]
    material_rows = [row for claim_key in claim_keys for row in material_by_key.get(claim_key, [])]
    mapped_claim_keys = sorted({text(row.get("claim_key")) for row in material_rows if text(row.get("claim_key"))})
    missing_claim_keys = sorted(set(claim_keys) - set(mapped_claim_keys))
    consumable_rows = [row for row in material_rows if material_is_consumable(row)]
    has_open_review = any(bool(row.get("has_open_material_review")) for row in material_rows)
    object_rows = list(objects_by_pair.get((emperor_name, object_name), []))
    accepted_objects = [row for row in object_rows if text(row.get("target_object_review_status")) == "accepted"]

    blockers: list[str] = []
    if missing_claim_keys:
        blockers.append("missing_cache_claim_intake_mapping")
    if material_rows and len(consumable_rows) < len(material_rows):
        blockers.append("material_not_consumable")
    if has_open_review:
        blockers.append("open_material_review")
    if missing_claim_keys:
        next_step = "needs_cache_intake"
    elif has_open_review or len(consumable_rows) < len(material_rows):
        next_step = "needs_passage_review"
    else:
        next_step = "ready_for_rule_candidate_review"
    return {
        "chain_key": text(chain.get("chain_key")),
        "emperor_name": emperor_name,
        "object_name": object_name,
        "candidate_item_code": "I5B",
        "candidate_rule_code": "appointment_delegation",
        "chain_type": text(chain.get("chain_type")),
        "chain_strength": text(chain.get("chain_strength")),
        "route_readiness": text(chain.get("route_readiness")),
        "claim_keys": claim_keys,
        "material_alignment": {
            "mapped_claim_keys": mapped_claim_keys,
            "missing_claim_keys": missing_claim_keys,
            "material_claim_count": len(material_rows),
            "consumable_material_claim_count": len(consumable_rows),
            "has_open_material_review": has_open_review,
        },
        "object_alignment": {
            "identity_gate": "deferred_until_formal_binding",
            "identity_status": "accepted_target_object_available" if accepted_objects else "deferred_identity_resolution",
            "target_object_count": len(object_rows),
            "accepted_target_object_count": len(accepted_objects),
            "accepted_target_objects": [
                {
                    "object_id": row.get("object_id"),
                    "target_object_id": row.get("target_object_id"),
                    "object_identity_key": text(row.get("object_identity_key")),
                }
                for row in accepted_objects
            ],
        },
        "blockers": blockers,
        "next_step": next_step,
        "write_db": False,
        "formal_binding_allowed": False,
    }


def build_shadow_plan(
    chains: Sequence[Mapping[str, Any]],
    *,
    material_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    material_by_key: dict[str, list[Mapping[str, Any]]] = {}
    for row in material_rows:
        material_by_key.setdefault(text(row.get("claim_key")), []).append(row)
    objects_by_pair: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in object_rows:
        objects_by_pair.setdefault((text(row.get("emperor_name")), text(row.get("object_name"))), []).append(row)
    rows = [shadow_chain_row(chain, material_by_key=material_by_key, objects_by_pair=objects_by_pair) for chain in chains]
    next_step_counts = Counter(text(row.get("next_step")) for row in rows)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_rule_intake_shadow.py",
        "mode": "dry_run_claim_cache_intake_shadow",
        "write_db": False,
        "formal_binding_allowed": False,
        "ready_chain_count": len(chains),
        "next_step_counts": dict(sorted(next_step_counts.items())),
        "chains": rows,
    }


def report_from_pg(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
    min_members: int,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            claims = chain_candidates.fetch_claim_rows(
                cur,
                emperor_names=emperor_names,
                statuses=statuses,
                owner_scopes=owner_scopes,
            )
            chains = ready_rule_route_chains(claims, min_members=min_members)
            claim_keys = [
                text(member.get("claim_key"))
                for chain in chains
                for member in (chain.get("members") or [])
                if isinstance(member, Mapping)
            ]
            material_rows = fetch_material_claim_rows(cur, claim_keys=claim_keys)
            object_rows = fetch_object_rows(cur, chains=chains)
        conn.rollback()
    report = build_shadow_plan(chains, material_rows=material_rows, object_rows=object_rows)
    report["schema_name"] = schema_name
    report["filters"] = {
        "emperor_names": [text(name) for name in emperor_names if text(name)],
        "statuses": [text(status) for status in statuses if text(status)],
        "owner_scopes": owner_scope_values(owner_scopes),
        "min_members": min_members,
    }
    report["input_claim_count"] = len(claims)
    return report


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Claim-cache Intake Shadow",
        "",
        f"- mode: `{payload.get('mode')}`",
        f"- write_db: `{payload.get('write_db')}`",
        f"- formal_binding_allowed: `{payload.get('formal_binding_allowed')}`",
        f"- input_claim_count: `{payload.get('input_claim_count', 0)}`",
        f"- ready_chain_count: `{payload.get('ready_chain_count', 0)}`",
        "",
        "## Next Steps",
        "",
        "| next_step | count |",
        "| --- | ---: |",
    ]
    for key, count in (payload.get("next_step_counts") or {}).items():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Strong Chain Intake Worklist", ""])
    for row in payload.get("chains") or []:
        material = row.get("material_alignment") or {}
        objects = row.get("object_alignment") or {}
        lines.extend(
            [
                f"### {row.get('emperor_name')} - {row.get('object_name')}",
                "",
                f"- chain_key: `{row.get('chain_key')}`",
                f"- next_step: `{row.get('next_step')}`",
                f"- blockers: `{', '.join(row.get('blockers') or []) or 'none'}`",
                f"- cache claims: `{len(row.get('claim_keys') or [])}`; mapped material claims: `{material.get('material_claim_count', 0)}`; consumable: `{material.get('consumable_material_claim_count', 0)}`",
                f"- object identity: `{objects.get('identity_status')}`; accepted target objects: `{objects.get('accepted_target_object_count', 0)}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_report(payload), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a read-only strong claim-chain intake shadow worklist.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--owner-scope", action="append", default=[])
    parser.add_argument("--min-members", type=int, default=chain_candidates.CHAIN_MIN_MEMBERS)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = report_from_pg(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        emperor_names=args.emperor_name,
        statuses=args.status or DEFAULT_STATUSES,
        owner_scopes=args.owner_scope,
        min_members=args.min_members,
    )
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(pretty_json({key: report[key] for key in ("ok", "mode", "input_claim_count", "ready_chain_count", "next_step_counts")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
