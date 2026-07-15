from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "v3-claim-freeze-package-v1"
QUERY_CONTRACT_VERSION = "v3-claim-readonly-query-v1"
POLICY_VERSION = "v3-claim-to-v4-candidate-pilot-v1"
I5B_RULES = {
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
}


def _normalise(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _normalise(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _hash(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _rows(value: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_normalise(dict(row)) for row in value]


def _identity_indexes(
    profile_packages: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    by_object: dict[str, str] = {}
    by_name: dict[str, list[str]] = defaultdict(list)
    for package in profile_packages:
        for item in package.get("items") or ():
            snapshot = item.get("person_profile_snapshot") or {}
            person_ref = str(snapshot.get("canonical_person_ref") or "")
            name = str(item.get("person") or "")
            source_ref = str(item.get("source_object_ref") or "")
            if person_ref and name:
                by_name[name].append(person_ref)
            if source_ref.startswith("retrieval_v3:object_code:") and person_ref:
                object_code = source_ref.rsplit(":", 1)[-1]
                if object_code in by_object and by_object[object_code] != person_ref:
                    raise ValueError("V3 object code maps to multiple V4 people")
                by_object[object_code] = person_ref
    return by_object, {name: sorted(set(refs)) for name, refs in by_name.items()}


def build_v3_claim_pilot_package(
    *,
    ruler: str,
    source_freeze_ref: str,
    claim_rows: Iterable[Mapping[str, Any]],
    material_rows: Iterable[Mapping[str, Any]],
    evidence_rows: Iterable[Mapping[str, Any]],
    route_rows: Iterable[Mapping[str, Any]],
    profile_packages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    claims = _rows(claim_rows)
    materials = _rows(material_rows)
    evidence = _rows(evidence_rows)
    routes = _rows(route_rows)
    if not ruler or not source_freeze_ref:
        raise ValueError("V3 claim pilot requires ruler and source freeze ref")
    if any(row.get("emperor_name") != ruler for row in claims):
        raise ValueError("V3 claim pilot contains cross-ruler claims")
    claim_keys = [str(row.get("claim_key") or "") for row in claims]
    if any(not key for key in claim_keys) or len(set(claim_keys)) != len(claim_keys):
        raise ValueError("V3 claim pilot claim identities are missing or duplicated")
    if any(row.get("status") != "active" for row in claims):
        raise ValueError("V3 claim pilot accepts active claims only")

    material_by_claim: dict[str, dict[str, Any]] = {}
    for row in materials:
        key = str(row.get("claim_key") or "")
        if not key or key in material_by_claim:
            raise ValueError("V3 material membership must be unique per claim")
        material_by_claim[key] = row
    evidence_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        key = str(row.get("claim_key") or "")
        if key not in set(claim_keys):
            raise ValueError("V3 claim evidence references an unknown claim")
        safe = dict(row)
        if any("path" in field for field in safe):
            raise ValueError("V3 claim evidence must not export runtime paths")
        safe["source_row_fingerprint"] = _hash(safe)
        evidence_by_claim[key].append(safe)
    route_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in routes:
        key = str(row.get("claim_key") or "")
        rule_code = str(row.get("candidate_rule_code") or "")
        if key not in set(claim_keys) or rule_code not in I5B_RULES:
            raise ValueError("V3 route hint is outside the pilot scope")
        safe = dict(row)
        safe["accepted_as_v4_rule_binding"] = False
        route_by_claim[key].append(safe)

    by_object, by_name = _identity_indexes(profile_packages)
    entries: list[dict[str, Any]] = []
    for claim in claims:
        key = str(claim["claim_key"])
        object_code = str(claim.get("object_code") or "")
        object_name = str(claim.get("object_name") or "")
        if object_code and object_code in by_object:
            identity = {
                "status": "exact_identity_accepted_v4",
                "candidate_v4_person_ref": by_object[object_code],
                "automatic_assertion_acceptance_allowed": False,
            }
        elif len(by_name.get(object_name, ())) == 1:
            identity = {
                "status": "unique_name_candidate_only",
                "candidate_v4_person_ref": by_name[object_name][0],
                "automatic_assertion_acceptance_allowed": False,
            }
        else:
            identity = {
                "status": "no_v4_profile_candidate",
                "candidate_v4_person_ref": None,
                "automatic_assertion_acceptance_allowed": False,
            }
        material = material_by_claim.get(key)
        member_role = None if material is None else material.get("member_role")
        conversion_status = (
            "assertion_candidate_pending_source_review"
            if member_role == "representative"
            else "candidate_only_evidence_member"
            if member_role == "evidence_member"
            else "candidate_only_unmaterialized"
        )
        safe_claim = dict(claim)
        if any("path" in field for field in safe_claim):
            raise ValueError("V3 claim rows must not export runtime paths")
        entry: dict[str, Any] = {
            "legacy_claim_ref": f"retrieval_v3:claim_key:{key}",
            "claim_source": safe_claim,
            "identity_resolution": identity,
            "material_membership": material,
            "evidence": sorted(
                evidence_by_claim.get(key, ()),
                key=lambda row: (str(row.get("evidence_key")), str(row.get("slice_hash"))),
            ),
            "route_hints": sorted(
                route_by_claim.get(key, ()),
                key=lambda row: (str(row.get("candidate_rule_code")), str(row.get("route_key"))),
            ),
            "conversion_status": conversion_status,
            "formal_v4_assertion": False,
            "counts_toward_historical_coverage": False,
        }
        entry["source_row_fingerprint"] = _hash(safe_claim)
        entry["entry_sha256"] = _hash(entry)
        entries.append(entry)
    entries.sort(key=lambda row: row["legacy_claim_ref"])

    event_groups: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        event_key = str(entry["claim_source"].get("canonical_event_key") or "")
        event_groups[event_key].append(entry["legacy_claim_ref"])
    event_inventory = [
        {
            "canonical_event_key": key,
            "claim_refs": sorted(refs),
            "claim_count": len(refs),
            "automatic_atom_merge_allowed": False,
        }
        for key, refs in sorted(event_groups.items())
    ]
    identity_counts = Counter(
        entry["identity_resolution"]["status"] for entry in entries
    )
    conversion_counts = Counter(entry["conversion_status"] for entry in entries)
    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "v3_claim_candidates_frozen_for_v4_review",
        "source": {
            "system": "retrieval_v3",
            "schema": "retrieval_v3",
            "source_freeze_ref": source_freeze_ref,
            "query_contract_version": QUERY_CONTRACT_VERSION,
            "database_read_only": True,
        },
        "scope": {"ruler": ruler},
        "summary": {
            "active_claim_count": len(entries),
            "canonical_event_group_count": len(event_inventory),
            "evidence_count": sum(len(entry["evidence"]) for entry in entries),
            "distinct_source_slice_count": len(
                {
                    (row.get("slice_hash"), row.get("document_code"))
                    for entry in entries
                    for row in entry["evidence"]
                }
            ),
            "identity_status_counts": dict(sorted(identity_counts.items())),
            "conversion_status_counts": dict(sorted(conversion_counts.items())),
            "route_hint_count": sum(len(entry["route_hints"]) for entry in entries),
            "formal_v4_assertion_count": 0,
            "historical_coverage_accepted_claim_count": 0,
            "model_call_count": 0,
            "v3_database_write_count": 0,
            "v4_database_write_count": 0,
            "formal_scoring_allowed": False,
        },
        "event_inventory": event_inventory,
        "entries": entries,
        "declarations": {
            "v3_rule_binding_inherited": False,
            "v3_claim_accepted_as_formal_v4_fact": False,
            "historical_coverage_status_changed": False,
            "runtime_paths_exported": False,
            "v3_primary_keys_reused_as_v4_ids": False,
            "formal_scoring_allowed": False,
        },
    }
    package["package_sha256"] = _hash(package)
    return package


def build_v3_claim_pilot_report(package: Mapping[str, Any]) -> dict[str, Any]:
    rule_rows = []
    for rule_code in sorted(I5B_RULES):
        entries = [
            entry
            for entry in package["entries"]
            if any(
                hint["candidate_rule_code"] == rule_code
                for hint in entry["route_hints"]
            )
        ]
        hint_statuses = Counter(
            hint["route_status"]
            for entry in entries
            for hint in entry["route_hints"]
            if hint["candidate_rule_code"] == rule_code
        )
        rule_rows.append(
            {
                "rule_code": rule_code,
                "candidate_claim_count": len(entries),
                "route_hint_count": sum(hint_statuses.values()),
                "route_status_counts": dict(sorted(hint_statuses.items())),
                "accepted_v4_assertion_count": 0,
                "historical_coverage_status_after_pilot": "unassessed",
            }
        )
    report: dict[str, Any] = {
        "schema_version": "v3-claim-pilot-report-v1",
        "status": "candidate_inventory_expanded_without_fact_acceptance",
        "source_package_sha256": package["package_sha256"],
        "ruler": package["scope"]["ruler"],
        "summary": package["summary"],
        "rules": rule_rows,
        "next_gate": {
            "required": "v4_source_rebind_identity_review_and_semantic_dedup",
            "automatic_coverage_completion_allowed": False,
        },
        "declarations": package["declarations"],
    }
    report["report_sha256"] = _hash(report)
    return report


def _dict_rows(cursor: Any) -> list[dict[str, Any]]:
    names = [description.name for description in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def fetch_v3_claim_pilot_source(connection: Any, *, ruler: str) -> dict[str, list[dict[str, Any]]]:
    with connection.cursor() as cursor:
        cursor.execute("select current_setting('transaction_read_only')")
        if cursor.fetchone()[0] != "on":
            raise RuntimeError("V3 claim source connection is not read-only")
        cursor.execute(
            """
            select cc.claim_key, cc.claim_type::text, cc.fact_schema,
                   cc.emperor_name, cc.object_name, cc.object_type::text,
                   cc.action_type, cc.event_scope, cc.office_or_domain,
                   cc.time_context, cc.outcome, cc.claim_summary, cc.confidence,
                   cc.fact_payload, cc.extractor_version, cc.status::text as status,
                   cc.canonical_event_key, cc.canonical_event_payload,
                   cc.event_group_key, cc.event_group_payload, cc.claim_grain::text,
                   cc.quality_flags, cc.claim_usage_flags,
                   o.object_code, o.object_identity_key, o.canonical_name,
                   o.identity_status::text as object_identity_status
            from retrieval_v3.claim_cache cc
            left join retrieval_v3.objects o on o.id=cc.object_id
            where cc.emperor_name=%s and cc.status::text='active'
              and cc.extractor_version like 'claim_extraction_only:%%'
            order by cc.claim_key
            """,
            (ruler,),
        )
        claims = _dict_rows(cursor)
        cursor.execute(
            """
            select mcm.claim_key, mcm.member_role::text,
                   mc.claim_code, mc.review_status::text as material_review_status,
                   mc.direction::text as material_direction,
                   mc.canonical_event_key as material_canonical_event_key,
                   mc.event_group_key as material_event_group_key,
                   mc.material_rebuild_version
            from retrieval_v3.material_claim_members mcm
            join retrieval_v3.material_claims mc on mc.id=mcm.material_id
            join retrieval_v3.claim_cache cc on cc.claim_key=mcm.claim_key
            where cc.emperor_name=%s and cc.status::text='active'
              and cc.extractor_version like 'claim_extraction_only:%%'
            order by mcm.claim_key
            """,
            (ruler,),
        )
        materials = _dict_rows(cursor)
        cursor.execute(
            """
            select cc.claim_key, ce.evidence_key, ce.slice_hash,
                   ce.source_slice_ref, ce.document_code, ce.support_level::text,
                   ce.span_payload, ce.quote_preview, ce.slice_text_preview,
                   css.source_title, css.source_url, css.text_hash
            from retrieval_v3.claim_cache cc
            join retrieval_v3.claim_evidence ce on ce.claim_key=cc.claim_key
            join retrieval_v3.claim_source_slices css
              on css.slice_hash=ce.slice_hash and css.document_code=ce.document_code
            where cc.emperor_name=%s and cc.status::text='active'
              and cc.extractor_version like 'claim_extraction_only:%%'
            order by cc.claim_key, ce.evidence_key
            """,
            (ruler,),
        )
        evidence = _dict_rows(cursor)
        cursor.execute(
            """
            select crc.route_key, crc.claim_key, crc.candidate_rule_code,
                   crc.candidate_lane, crc.candidate_direction,
                   crc.route_status::text, crc.route_reason,
                   crc.routed_by_profile, crc.confidence
            from retrieval_v3.claim_route_cache crc
            join retrieval_v3.claim_cache cc on cc.claim_key=crc.claim_key
            where cc.emperor_name=%s and cc.status::text='active'
              and cc.extractor_version like 'claim_extraction_only:%%'
              and crc.candidate_rule_code = any(%s)
            order by crc.claim_key, crc.route_key
            """,
            (ruler, sorted(I5B_RULES)),
        )
        routes = _dict_rows(cursor)
    return {"claims": claims, "materials": materials, "evidence": evidence, "routes": routes}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def export_v3_claim_pilot_package(
    *,
    ruler: str,
    source_freeze_ref: str,
    profile_packages: Sequence[Mapping[str, Any]],
    env_file: Path = Path(".env"),
) -> dict[str, Any]:
    _load_env_file(env_file)
    dsn = (
        os.environ.get("EMPEROR_EVAL_V3_DSN")
        or os.environ.get("DATABASE_URL_V3")
        or os.environ.get("V3_DATABASE_URL")
    )
    if not dsn:
        raise RuntimeError("V3 claim source DSN is not configured")
    import psycopg

    with psycopg.connect(dsn, options="-c default_transaction_read_only=on") as connection:
        rows = fetch_v3_claim_pilot_source(connection, ruler=ruler)
    return build_v3_claim_pilot_package(
        ruler=ruler,
        source_freeze_ref=source_freeze_ref,
        claim_rows=rows["claims"],
        material_rows=rows["materials"],
        evidence_rows=rows["evidence"],
        route_rows=rows["routes"],
        profile_packages=profile_packages,
    )
