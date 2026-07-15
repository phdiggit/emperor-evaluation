from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "v3-person-profile-freeze-package-v1"
QUERY_CONTRACT_VERSION = "v3-person-profile-readonly-query-v1"
ELIGIBILITY_POLICY_VERSION = "v3-person-profile-eligibility-v1"


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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _normalise(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _fingerprint(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sorted_unique(values: Iterable[Any]) -> list[Any]:
    by_json = {_canonical_json(value): _normalise(value) for value in values}
    return [by_json[key] for key in sorted(by_json)]


def _exclusion_reason(row: Mapping[str, Any]) -> str | None:
    if row.get("object_type") != "person":
        return "object_not_person"
    if row.get("identity_status") != "active":
        return "identity_not_active"
    if row.get("review_status") != "accepted":
        return "profile_not_accepted"
    if row.get("readiness_status") != "profile_complete":
        return "readiness_not_complete"
    required = (
        "person_profile_code",
        "object_code",
        "object_identity_key",
        "talent_grade",
        "talent_grade_version",
        "talent_grade_confidence",
        "talent_authority_consensus",
        "talent_performance_support",
        "talent_evidence_coverage",
        "talent_grade_basis",
        "negative_talent_version",
        "negative_talent_confidence",
        "negative_authority_consensus",
        "negative_fact_support",
        "negative_evidence_coverage",
        "negative_talent_basis",
    )
    if any(row.get(field) is None for field in required):
        return "profile_axis_incomplete"
    has_class = row.get("negative_talent_class") is not None
    has_severity = row.get("negative_talent_severity") is not None
    if has_class != has_severity:
        return "negative_axis_shape_invalid"
    return None


def build_v3_person_profile_export(
    profile_rows: Iterable[Mapping[str, Any]],
    *,
    lineage_rows: Iterable[Mapping[str, Any]] = (),
    alias_rows: Iterable[Mapping[str, Any]] = (),
    affiliation_rows: Iterable[Mapping[str, Any]] = (),
    role_rows: Iterable[Mapping[str, Any]] = (),
    source_freeze_ref: str,
) -> dict[str, Any]:
    profiles = [_normalise(dict(row)) for row in profile_rows]
    lineage_by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lineage_rows:
        lineage_by_object[str(row["object_code"])].append(_normalise(dict(row)))
    aliases_by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in alias_rows:
        aliases_by_object[str(row["object_code"])].append(_normalise(dict(row)))
    affiliations_by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in affiliation_rows:
        affiliations_by_object[str(row["object_code"])].append(
            _normalise(dict(row))
        )
    roles_by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in role_rows:
        roles_by_object[str(row["object_code"])].append(_normalise(dict(row)))

    excluded = Counter()
    entries: list[dict[str, Any]] = []
    for row in profiles:
        reason = _exclusion_reason(row)
        if reason:
            excluded[reason] += 1
            continue
        object_code = str(row["object_code"])
        lineage = _sorted_unique(lineage_by_object.get(object_code, ()))
        if not lineage:
            excluded["authority_lineage_missing"] += 1
            continue
        profile_payload = row.get("profile_payload") or {}
        identity_source = {
            "record_type": "v3_person_identity_source",
            "source_object_ref": f"retrieval_v3:object_code:{object_code}",
            "source_object_code": object_code,
            "source_object_identity_key": row["object_identity_key"],
            "source_identity_status": row["identity_status"],
            "canonical_name": row["canonical_name"],
            "normalized_name": row["normalized_name"],
            "aliases": _sorted_unique(aliases_by_object.get(object_code, ())),
            "affiliations": _sorted_unique(
                affiliations_by_object.get(object_code, ())
            ),
            "roles": _sorted_unique(roles_by_object.get(object_code, ())),
        }
        identity_source["source_row_fingerprint"] = _fingerprint(identity_source)
        negative_class = row.get("negative_talent_class")
        profile_source = {
            "record_type": "v3_person_profile_source",
            "source_profile_ref": (
                "retrieval_v3:person_profile_code:" + row["person_profile_code"]
            ),
            "source_profile_code": row["person_profile_code"],
            "source_object_code": object_code,
            "source_identity_status": row["identity_status"],
            "source_review_status": row["review_status"],
            "source_readiness_status": row["readiness_status"],
            "talent_axis": {
                "grade": row["talent_grade"],
                "version": row["talent_grade_version"],
                "confidence": row["talent_grade_confidence"],
                "authority_consensus": row["talent_authority_consensus"],
                "performance_support": row["talent_performance_support"],
                "evidence_coverage": row["talent_evidence_coverage"],
                "basis": row["talent_grade_basis"],
            },
            "negative_axis": {
                "review_completed": True,
                "finding_status": (
                    "established"
                    if negative_class is not None
                    else "no_established_negative_class"
                ),
                "has_negative_class": negative_class is not None,
                "class": negative_class,
                "severity": row.get("negative_talent_severity"),
                "version": row["negative_talent_version"],
                "confidence": row["negative_talent_confidence"],
                "authority_consensus": row["negative_authority_consensus"],
                "fact_support": row["negative_fact_support"],
                "evidence_coverage": row["negative_evidence_coverage"],
                "basis": row["negative_talent_basis"],
            },
            "profile_payload_sha256": _fingerprint(profile_payload),
            "profile_cache_metadata_missing_or_repair_path": not bool(
                profile_payload.get("cache_root")
            ),
            "authority_lineage": lineage,
        }
        profile_source["source_row_fingerprint"] = _fingerprint(profile_source)
        entry = {
            "identity_source": identity_source,
            "profile_source": profile_source,
            "crosswalk_candidate": {
                "schema_version": "person-identity-crosswalk-v1",
                "source_object_ref": identity_source["source_object_ref"],
                "source_identity_fingerprint": identity_source[
                    "source_row_fingerprint"
                ],
                "candidate_v4_person_ref": None,
                "mapping_status": "pending_human_review",
                "mapping_basis_refs": [],
                "ambiguity_flags": [],
            },
            "conversion_status": "blocked_on_identity_crosswalk",
        }
        entry["entry_sha256"] = _fingerprint(entry)
        entries.append(entry)
    entries.sort(
        key=lambda item: (
            item["identity_source"]["source_object_identity_key"],
            item["identity_source"]["source_object_code"],
            item["profile_source"]["source_profile_code"],
        )
    )
    talent_versions = Counter(
        entry["profile_source"]["talent_axis"]["version"] for entry in entries
    )
    negative_versions = Counter(
        entry["profile_source"]["negative_axis"]["version"] for entry in entries
    )
    authority_links = [
        link
        for entry in entries
        for link in entry["profile_source"]["authority_lineage"]
    ]
    authority_evidence = [
        evidence for link in authority_links for evidence in link.get("evidence", ())
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "v3_person_profile_source_snapshot_frozen",
        "source": {
            "system": "retrieval_v3",
            "schema": "retrieval_v3",
            "source_freeze_ref": source_freeze_ref,
            "query_contract_version": QUERY_CONTRACT_VERSION,
            "database_read_only": True,
        },
        "eligibility": {
            "policy_version": ELIGIBILITY_POLICY_VERSION,
            "requires": {
                "object_type": "person",
                "identity_status": "active",
                "profile_review_status": "accepted",
                "readiness_status": "profile_complete",
                "complete_typed_talent_and_negative_axes": True,
                "accepted_authority_lineage": True,
            },
        },
        "summary": {
            "input_profile_count": len(profiles),
            "eligible_profile_count": len(entries),
            "excluded_counts": dict(sorted(excluded.items())),
            "talent_grade_version_partitions": dict(sorted(talent_versions.items())),
            "negative_talent_version_partitions": dict(
                sorted(negative_versions.items())
            ),
            "cross_version_comparison_allowed": False,
            "crosswalk_pending_count": len(entries),
            "v4_profile_snapshot_count": 0,
            "identity_hint_counts": {
                "alias_rows": sum(
                    len(entry["identity_source"]["aliases"]) for entry in entries
                ),
                "affiliation_rows": sum(
                    len(entry["identity_source"]["affiliations"])
                    for entry in entries
                ),
                "role_rows": sum(
                    len(entry["identity_source"]["roles"]) for entry in entries
                ),
            },
            "authority_lineage_counts": {
                "accepted_links": len(authority_links),
                "distinct_claims": len(
                    {link["claim_key"] for link in authority_links}
                ),
                "distinct_evidence": len(
                    {evidence["evidence_key"] for evidence in authority_evidence}
                ),
                "distinct_slices": len(
                    {evidence["slice_hash"] for evidence in authority_evidence}
                ),
            },
        },
        "entries": entries,
        "declarations": {
            "v3_database_write_count": 0,
            "model_call_count": 0,
            "formal_v4_fact": False,
            "formal_scoring_allowed": False,
            "qualification_use_allowed": False,
            "v3_primary_keys_reused_as_v4_ids": False,
            "scores_or_rankings_included": False,
        },
    }
    payload["package_sha256"] = _fingerprint(payload)
    return payload


def build_v3_person_profile_report(package: Mapping[str, Any]) -> dict[str, Any]:
    entries = package["entries"]
    return {
        "schema_version": "v3-person-profile-migration-report-v1",
        "status": "source_snapshot_ready_for_identity_review",
        "source_freeze_ref": package["source"]["source_freeze_ref"],
        "source_package_sha256": package["package_sha256"],
        "summary": package["summary"],
        "quality_flags": {
            "profile_cache_metadata_missing_or_repair_path_count": sum(
                bool(
                    entry["profile_source"][
                        "profile_cache_metadata_missing_or_repair_path"
                    ]
                )
                for entry in entries
            ),
            "missing_resolved_profile_id_link_count": sum(
                bool(link.get("missing_resolved_profile_id"))
                for entry in entries
                for link in entry["profile_source"]["authority_lineage"]
            ),
            "stable_url_missing_evidence_count": len(
                {
                    (
                        evidence.get("evidence_key"),
                        evidence.get("slice_hash"),
                        evidence.get("document_code"),
                    )
                    for entry in entries
                    for link in entry["profile_source"]["authority_lineage"]
                    for evidence in link.get("evidence", ())
                    if evidence.get("stable_url_missing")
                }
            ),
        },
        "next_gate": {
            "required": "person_identity_crosswalk_human_review",
            "automatic_v4_profile_conversion_allowed": False,
        },
        "declarations": package["declarations"],
    }


def _dict_rows(cursor: Any) -> list[dict[str, Any]]:
    names = [description.name for description in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def fetch_v3_person_profile_source(connection: Any) -> dict[str, list[dict[str, Any]]]:
    with connection.cursor() as cursor:
        cursor.execute("select current_setting('transaction_read_only')")
        if cursor.fetchone()[0] != "on":
            raise RuntimeError("V3 profile source connection is not read-only")
        cursor.execute(
            """
            select pp.person_profile_code, o.object_code, o.object_identity_key,
                   o.canonical_name, o.normalized_name, o.object_type::text,
                   o.identity_status::text, pp.review_status::text,
                   pp.readiness_status::text, pp.talent_grade::text,
                   pp.talent_grade_basis, pp.talent_grade_version,
                   pp.talent_grade_confidence, pp.talent_authority_consensus::text,
                   pp.talent_performance_support::text,
                   pp.talent_evidence_coverage::text,
                   pp.negative_talent_class::text,
                   pp.negative_talent_severity::text,
                   pp.negative_talent_version, pp.negative_talent_confidence,
                   pp.negative_authority_consensus::text,
                   pp.negative_fact_support::text,
                   pp.negative_evidence_coverage::text,
                   pp.negative_talent_basis, pp.profile_payload
            from retrieval_v3.person_profiles pp
            join retrieval_v3.objects o on o.id = pp.object_id
            order by o.object_identity_key, o.object_code, pp.person_profile_code
            """
        )
        profiles = _dict_rows(cursor)
        cursor.execute(
            """
            select o.object_code, n.object_name_code, n.name_text,
                   n.normalized_name, n.name_kind::text, n.review_status::text
            from retrieval_v3.object_names n
            join retrieval_v3.objects o on o.id = n.object_id
            order by o.object_code, n.object_name_code
            """
        )
        aliases = _dict_rows(cursor)
        cursor.execute(
            """
            select o.object_code, a.person_affiliation_code,
                   a.affiliation_kind::text, a.dynasty_label, a.polity_label,
                   a.affiliation_label, a.period_label, a.period_start_year,
                   a.period_end_year, a.review_status::text
            from retrieval_v3.person_affiliations a
            join retrieval_v3.objects o on o.id = a.object_id
            order by o.object_code, a.person_affiliation_code
            """
        )
        affiliations = _dict_rows(cursor)
        cursor.execute(
            """
            select o.object_code, r.person_role_code, r.role_kind::text,
                   r.dynasty_label, r.polity_label, r.role_title, r.period_label,
                   r.period_start_year, r.period_end_year, r.review_status::text
            from retrieval_v3.person_roles r
            join retrieval_v3.objects o on o.id = r.object_id
            order by o.object_code, r.person_role_code
            """
        )
        roles = _dict_rows(cursor)
        cursor.execute(
            """
            select o.object_code, ppl.link_key, ppl.claim_key,
                   ppl.profile_field::text, ppl.proposal_value,
                   ppl.proposal_status::text, ppl.basis, ppl.confidence,
                   (ppl.resolved_profile_id is null) as missing_resolved_profile_id,
                   cc.claim_summary, cc.confidence as claim_confidence,
                   cc.canonical_event_key, cc.extractor_version,
                   ce.evidence_key, ce.slice_hash, ce.source_slice_ref,
                   ce.document_code, ce.support_level::text,
                   css.source_title, css.source_url, css.text_hash
            from retrieval_v3.person_profile_claim_links ppl
            join retrieval_v3.objects o on o.id = ppl.object_id
            join retrieval_v3.person_profiles pp on pp.object_id = ppl.object_id
            join retrieval_v3.claim_cache cc
              on cc.claim_key = ppl.claim_key
             and cc.object_id = ppl.object_id
             and cc.status::text = 'active'
            join retrieval_v3.claim_evidence ce
              on ce.claim_key = ppl.claim_key and ce.object_id = ppl.object_id
            join retrieval_v3.claim_source_slices css
              on css.slice_hash = ce.slice_hash
             and css.document_code = ce.document_code
            where ppl.profile_field::text = 'authority_evaluation'
              and ppl.proposal_status::text = 'accepted'
              and (ppl.resolved_profile_id = pp.id or ppl.resolved_profile_id is null)
            order by o.object_code, ppl.link_key, ce.evidence_key
            """
        )
        flat_lineage = _dict_rows(cursor)
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for row in flat_lineage:
        key = (row["object_code"], row["link_key"])
        link = links.setdefault(
            key,
            {
                field: row[field]
                for field in (
                    "object_code",
                    "link_key",
                    "claim_key",
                    "profile_field",
                    "proposal_value",
                    "proposal_status",
                    "basis",
                    "confidence",
                    "missing_resolved_profile_id",
                    "claim_summary",
                    "claim_confidence",
                    "canonical_event_key",
                    "extractor_version",
                )
            }
            | {"evidence": []},
        )
        evidence = {
            field: row[field]
            for field in (
                "evidence_key",
                "slice_hash",
                "source_slice_ref",
                "document_code",
                "support_level",
                "source_title",
                "source_url",
                "text_hash",
            )
        }
        evidence["stable_url_missing"] = not bool(evidence["source_url"])
        link["evidence"].append(evidence)
    lineage = list(links.values())
    for link in lineage:
        link["evidence"] = _sorted_unique(link["evidence"])
    return {
        "profiles": profiles,
        "lineage": lineage,
        "aliases": aliases,
        "affiliations": affiliations,
        "roles": roles,
    }


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def export_v3_person_profile_package(
    *, source_freeze_ref: str, env_file: Path = Path(".env")
) -> dict[str, Any]:
    _load_env_file(env_file)
    dsn = (
        os.environ.get("EMPEROR_EVAL_V3_DSN")
        or os.environ.get("DATABASE_URL_V3")
        or os.environ.get("V3_DATABASE_URL")
    )
    if not dsn:
        raise RuntimeError("V3 profile source DSN is not configured")
    try:
        import psycopg

        with psycopg.connect(
            dsn, options="-c default_transaction_read_only=on"
        ) as connection:
            rows = fetch_v3_person_profile_source(connection)
    except Exception as exc:
        if isinstance(exc, (ValueError, RuntimeError)) and "read-only" in str(exc):
            raise
        raise RuntimeError("V3 profile source connection failed") from None
    return build_v3_person_profile_export(
        rows["profiles"],
        lineage_rows=rows["lineage"],
        alias_rows=rows["aliases"],
        affiliation_rows=rows["affiliations"],
        role_rows=rows["roles"],
        source_freeze_ref=source_freeze_ref,
    )
