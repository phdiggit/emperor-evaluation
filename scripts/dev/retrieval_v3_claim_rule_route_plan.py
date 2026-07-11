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

from scripts.dev import retrieval_v3_claim_chain_candidates as chain_candidates  # noqa: E402
from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_claim_event_groups import owner_scope_values  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_STATUSES = ("active",)
I5B_RULES = ("talent_discovery", "appointment_delegation", "team_building", "tolerate_talent", "anti_nepotism")
APPOINTMENT_ACTIONS = {"任命", "授权"}
DISCOVERY_TERMS = ("荐", "举荐", "推荐", "拔擢", "提拔", "擢用", "擢任", "延揽", "访求", "征辟", "识才", "知其才")
TOLERANCE_TERMS = ("容", "赦", "保全", "复用", "召还", "谏", "諫", "诤", "諍", "直言", "上疏", "纳谏", "納諫")
DISPOSITION_TERMS = ("诛", "杀", "废", "罢", "免", "贬", "夺", "禁锢", "圈禁")
NEPOTISM_TERMS = ("外戚", "近臣", "宠臣", "親", "亲", "宗室", "家族", "私门", "朋党", "党", "纳贿", "贿")
TEAM_OFFICE_TERMS = ("丞相", "宰相", "大将军", "太尉", "中书", "枢密", "内阁", "大学士", "总督", "巡抚")


def text(value: Any) -> str:
    return str(value or "").strip()


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def contains_any(value: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term and term in value)


def atomic(claim: Mapping[str, Any]) -> Mapping[str, Any]:
    value = as_mapping(claim.get("atomic_fact_payload"))
    return value if value else as_mapping(claim.get("fact_payload"))


def claim_field(claim: Mapping[str, Any], field: str) -> str:
    return text(claim.get(field) or atomic(claim).get(field))


def claim_haystack(claim: Mapping[str, Any]) -> str:
    fact = atomic(claim)
    return " ".join(
        text(value)
        for value in (
            claim.get("claim_summary"),
            claim.get("object_name"),
            claim.get("action_type"),
            claim.get("office_or_domain"),
            fact.get("actor"),
            fact.get("fact_object"),
            fact.get("outcome"),
            fact.get("cost_or_damage"),
        )
        if text(value)
    )


def route_row(
    *,
    source_kind: str,
    source_key: str,
    emperor_name: str,
    object_name: str,
    rule_code: str,
    route_status: str,
    reason_codes: Sequence[str],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "route_source_kind": source_kind,
        "route_source_key": source_key,
        "emperor_name": emperor_name,
        "object_name": object_name,
        "candidate_item_code": "I5B",
        "candidate_rule_code": rule_code,
        "route_status": route_status,
        "reason_codes": list(reason_codes),
        "evidence": dict(evidence),
        "write_db": False,
        "formal_binding_allowed": False,
    }


def route_claim(claim: Mapping[str, Any]) -> list[dict[str, Any]]:
    emperor_name = text(claim.get("emperor_name"))
    object_name = text(claim.get("object_name"))
    claim_key = text(claim.get("claim_key"))
    action_type = claim_field(claim, "action_type")
    actor = claim_field(claim, "actor")
    office = claim_field(claim, "office_or_domain")
    haystack = claim_haystack(claim)
    routes: list[dict[str, Any]] = []
    evidence = {
        "claim_key": claim_key,
        "action_type": action_type,
        "actor": actor,
        "office_or_domain": office,
        "fact_type": claim_field(claim, "fact_type"),
        "outcome_support": claim_field(claim, "outcome_support"),
    }
    if action_type in APPOINTMENT_ACTIONS and actor == emperor_name and object_name:
        routes.append(
            route_row(
                source_kind="claim",
                source_key=claim_key,
                emperor_name=emperor_name,
                object_name=object_name,
                rule_code="appointment_delegation",
                route_status="mechanical_current_rule_candidate",
                reason_codes=("emperor_actor", f"action_{action_type}"),
                evidence=evidence,
            )
        )
    discovery_terms = contains_any(haystack, DISCOVERY_TERMS)
    if discovery_terms:
        routes.append(
            route_row(
                source_kind="claim",
                source_key=claim_key,
                emperor_name=emperor_name,
                object_name=object_name,
                rule_code="talent_discovery",
                route_status="mechanical_current_rule_candidate",
                reason_codes=("discovery_terms", *discovery_terms),
                evidence=evidence,
            )
        )
    tolerance_terms = contains_any(haystack, TOLERANCE_TERMS)
    disposition_terms = contains_any(haystack, DISPOSITION_TERMS)
    if tolerance_terms or disposition_terms:
        routes.append(
            route_row(
                source_kind="claim",
                source_key=claim_key,
                emperor_name=emperor_name,
                object_name=object_name,
                rule_code="tolerate_talent",
                route_status="needs_light_rule_review",
                reason_codes=("tolerance_or_disposition_terms", *tolerance_terms, *disposition_terms),
                evidence=evidence,
            )
        )
    nepotism_terms = contains_any(haystack, NEPOTISM_TERMS)
    if nepotism_terms:
        routes.append(
            route_row(
                source_kind="claim",
                source_key=claim_key,
                emperor_name=emperor_name,
                object_name=object_name,
                rule_code="anti_nepotism",
                route_status="needs_light_rule_review",
                reason_codes=("nepotism_terms", *nepotism_terms),
                evidence=evidence,
            )
        )
    team_terms = contains_any(office, TEAM_OFFICE_TERMS)
    if team_terms:
        routes.append(
            route_row(
                source_kind="claim",
                source_key=claim_key,
                emperor_name=emperor_name,
                object_name=object_name,
                rule_code="team_building",
                route_status="defer_to_object_pool",
                reason_codes=("team_office", *team_terms),
                evidence=evidence,
            )
        )
    return routes


def route_chain(chain: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain_type = text(chain.get("chain_type"))
    readiness = text(chain.get("route_readiness"))
    if chain_type not in {"delegated_power_abuse_chain", "appointment_to_outcome_chain"}:
        return []
    status = "ready_for_rule_route_review" if readiness == "ready_for_chain_route_review" else "needs_light_rule_review"
    return [
        route_row(
            source_kind="event_chain",
            source_key=text(chain.get("chain_key")),
            emperor_name=text(chain.get("emperor_name")),
            object_name=text(chain.get("object_name")),
            rule_code="appointment_delegation",
            route_status=status,
            reason_codes=(chain_type, text(chain.get("chain_strength")), readiness),
            evidence={
                "member_count": int(chain.get("member_count") or 0),
                "member_claim_keys": [
                    text(member.get("claim_key"))
                    for member in (chain.get("members") or [])
                    if isinstance(member, Mapping) and text(member.get("claim_key"))
                ],
                "role_family_counts": dict(as_mapping(chain.get("role_family_counts"))),
                "source_slice_refs": list(chain.get("source_slice_refs") or []),
            },
        )
    ]


def dedupe_routes(routes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in routes:
        key = (text(row.get("route_source_kind")), text(row.get("route_source_key")), text(row.get("candidate_rule_code")))
        if key not in seen:
            seen.add(key)
            result.append(dict(row))
    return result


def build_plan(claims: Sequence[Mapping[str, Any]], *, min_members: int = chain_candidates.CHAIN_MIN_MEMBERS) -> dict[str, Any]:
    chains = chain_candidates.build_chain_candidates(claims, min_members=min_members)
    routes = dedupe_routes([route for claim in claims for route in route_claim(claim)] + [route for chain in chains for route in route_chain(chain)])
    by_rule = Counter(text(row.get("candidate_rule_code")) for row in routes)
    by_status = Counter(text(row.get("route_status")) for row in routes)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_claim_rule_route_plan.py",
        "mode": "dry_run_claim_cache_rule_route_plan",
        "write_db": False,
        "formal_binding_allowed": False,
        "input_claim_count": len(claims),
        "chain_candidate_count": len(chains),
        "route_count": len(routes),
        "candidate_rule_counts": dict(sorted(by_rule.items())),
        "route_status_counts": dict(sorted(by_status.items())),
        "routes": routes,
        "sample_routes": routes[:30],
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
        conn.rollback()
    report = build_plan(claims, min_members=min_members)
    report["schema_name"] = schema_name
    report["filters"] = {
        "emperor_names": [text(value) for value in emperor_names if text(value)],
        "statuses": [text(value) for value in statuses if text(value)],
        "owner_scopes": owner_scope_values(owner_scopes),
        "min_members": min_members,
    }
    return report


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        "# Claim cache rule route plan",
        "",
        f"- input_claim_count: `{payload.get('input_claim_count', 0)}`",
        f"- chain_candidate_count: `{payload.get('chain_candidate_count', 0)}`",
        f"- route_count: `{payload.get('route_count', 0)}`",
        "- write_db: `false`",
        "- formal_binding_allowed: `false`",
        "",
        "## Candidate rules",
        "",
    ]
    for rule_code, count in (payload.get("candidate_rule_counts") or {}).items():
        lines.append(f"- `{rule_code}`: {count}")
    lines.extend(["", "## Route statuses", ""])
    for status, count in (payload.get("route_status_counts") or {}).items():
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Sample routes", ""])
    for route in payload.get("sample_routes") or []:
        lines.append(
            f"- `{route.get('emperor_name')}` / `{route.get('object_name')}` / `{route.get('candidate_rule_code')}` / `{route.get('route_status')}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a zero-token I5B rule-route plan from active claim cache and event chains.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--status", action="append", default=list(DEFAULT_STATUSES))
    parser.add_argument("--owner-scope", action="append", default=[])
    parser.add_argument("--min-members", type=int, default=chain_candidates.CHAIN_MIN_MEMBERS)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = report_from_pg(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        emperor_names=args.emperor_name or [],
        statuses=args.status or [],
        owner_scopes=args.owner_scope or [],
        min_members=max(2, int(args.min_members)),
    )
    write_json(args.output_json, report)
    if args.output_md is not None:
        write_markdown(args.output_md, report)
    print(json.dumps({"ok": True, "route_count": report["route_count"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
