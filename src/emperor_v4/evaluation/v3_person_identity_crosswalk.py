from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from emperor_v4.evaluation.v3_person_profile_export import _fingerprint


def build_v4_person_identity_registry(
    profile_sets: Iterable[tuple[str, Iterable[Mapping[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    registry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_ref, profiles in profile_sets:
        for profile in profiles:
            name = str(profile.get("person") or "").strip()
            person_ref = str(profile.get("canonical_person_ref") or "").strip()
            if not name or not person_ref:
                continue
            registry[name].append(
                {
                    "canonical_person_ref": person_ref,
                    "review_status": profile.get("review_status"),
                    "capability_domains": sorted(
                        {str(item) for item in profile.get("capability_domains", ())}
                    ),
                    "source_ref": source_ref,
                    "source_profile_ref": profile.get("profile_ref"),
                    "source_snapshot_version": profile.get("snapshot_version"),
                    "identity_authority_status": (
                        "independent_v4_identity_accepted"
                        if profile.get("formal_v4_fact") is True
                        else "test_profile_candidate"
                    ),
                }
            )
    return dict(registry)


def build_person_identity_crosswalk(
    source_package: Mapping[str, Any],
    *,
    registry: Mapping[str, Iterable[Mapping[str, Any]]],
    crosswalk_version: str,
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for entry in source_package.get("entries", ()):
        identity = entry["identity_source"]
        name = str(identity["canonical_name"]).strip()
        candidates = list(registry.get(name, ()))
        candidate_refs = sorted(
            {
                str(item["canonical_person_ref"])
                for item in candidates
                if item.get("canonical_person_ref")
            }
        )
        accepted_refs = sorted(
            {
                str(item["canonical_person_ref"])
                for item in candidates
                if item.get("identity_authority_status")
                == "independent_v4_identity_accepted"
            }
        )
        if len(accepted_refs) == 1 and len(candidate_refs) == 1:
            mapping_status = "accepted_existing_v4_identity"
            candidate_ref: str | None = accepted_refs[0]
            ambiguity_flags: list[str] = []
        elif len(candidate_refs) == 1:
            mapping_status = "unique_name_candidate"
            candidate_ref = candidate_refs[0]
            ambiguity_flags = ["candidate_identity_not_independently_accepted"]
        elif not candidate_refs:
            mapping_status = "no_v4_target"
            candidate_ref = None
            ambiguity_flags = ["no_existing_human_frozen_v4_identity"]
        else:
            mapping_status = "conflicting_v4_refs"
            candidate_ref = None
            ambiguity_flags = ["multiple_existing_v4_identity_refs"]
        basis_refs = sorted(
            {
                str(item["source_ref"])
                for item in candidates
                if item.get("source_ref")
            }
        )
        decision = {
            "schema_version": "person-identity-crosswalk-v1",
            "crosswalk_ref": "XW-" + identity["source_row_fingerprint"][:16].upper(),
            "crosswalk_version": crosswalk_version,
            "source_package_sha256": source_package["package_sha256"],
            "source_object_ref": identity["source_object_ref"],
            "source_identity_fingerprint": identity["source_row_fingerprint"],
            "source_canonical_name": name,
            "candidate_v4_person_ref": candidate_ref,
            "mapping_status": mapping_status,
            "mapping_basis_refs": basis_refs,
            "ambiguity_flags": ambiguity_flags,
            "profile_import_review_status": "pending",
        }
        decision["decision_fingerprint"] = _fingerprint(decision)
        decisions.append(decision)
    decisions.sort(key=lambda item: item["source_object_ref"])
    counts: dict[str, int] = defaultdict(int)
    for decision in decisions:
        counts[decision["mapping_status"]] += 1
    payload: dict[str, Any] = {
        "schema_version": "person-identity-crosswalk-package-v1",
        "status": "identity_crosswalk_candidates_built",
        "crosswalk_version": crosswalk_version,
        "source_package_sha256": source_package["package_sha256"],
        "registry_policy": {
            "accepted_only_from_independently_accepted_v4_identity": True,
            "name_only_match_forbidden": True,
            "new_v4_identity_auto_accept_forbidden": True,
        },
        "summary": {
            "source_identity_count": len(decisions),
            "mapping_status_counts": dict(sorted(counts.items())),
            "accepted_identity_count": counts["accepted_existing_v4_identity"],
            "profile_import_review_pending_count": len(decisions),
        },
        "decisions": decisions,
        "declarations": {
            "v3_database_write_count": 0,
            "v4_database_write_count": 0,
            "model_call_count": 0,
            "formal_v4_profile_count": 0,
            "formal_scoring_allowed": False,
        },
    }
    payload["crosswalk_package_sha256"] = _fingerprint(payload)
    return payload


def build_user_authorized_identity_crosswalk(
    source_package: Mapping[str, Any],
    *,
    legacy_registry: Mapping[str, Iterable[Mapping[str, Any]]],
    authorization_ref: str,
    crosswalk_version: str,
) -> dict[str, Any]:
    if not authorization_ref.strip():
        raise ValueError("user authorization ref is required")
    decisions: list[dict[str, Any]] = []
    for entry in source_package.get("entries", ()):
        identity = entry["identity_source"]
        name = str(identity["canonical_name"]).strip()
        identity_key = str(identity["source_object_identity_key"]).strip()
        person_ref = "PER-V4-" + _fingerprint(
            {"canonical_name": name, "source_identity_key": identity_key}
        )[:12].upper()
        legacy_refs = sorted(
            {
                str(item["canonical_person_ref"])
                for item in legacy_registry.get(name, ())
                if item.get("canonical_person_ref")
            }
        )
        decision = {
            "schema_version": "person-identity-crosswalk-v1",
            "crosswalk_ref": "XW-" + identity["source_row_fingerprint"][:16].upper(),
            "crosswalk_version": crosswalk_version,
            "source_package_sha256": source_package["package_sha256"],
            "source_object_ref": identity["source_object_ref"],
            "source_identity_fingerprint": identity["source_row_fingerprint"],
            "source_canonical_name": name,
            "candidate_v4_person_ref": person_ref,
            "mapping_status": "accepted_user_authorized_v3_identity",
            "mapping_basis_refs": [
                authorization_ref,
                "source-package:" + source_package["package_sha256"],
            ],
            "legacy_person_refs": legacy_refs,
            "ambiguity_flags": (
                ["legacy_ref_namespace_conflict_resolved_by_new_v4_ref"]
                if len(legacy_refs) > 1
                else []
            ),
            "profile_import_review_status": "accepted_for_v3_axes",
        }
        decision["decision_fingerprint"] = _fingerprint(decision)
        decisions.append(decision)
    decisions.sort(key=lambda item: item["source_object_ref"])
    payload: dict[str, Any] = {
        "schema_version": "person-identity-crosswalk-package-v1",
        "status": "user_authorized_v3_identity_crosswalk_frozen",
        "crosswalk_version": crosswalk_version,
        "authorization_ref": authorization_ref,
        "source_package_sha256": source_package["package_sha256"],
        "identity_policy": {
            "v4_native_person_ref_allocated": True,
            "v3_numeric_primary_key_reused": False,
            "legacy_p_and_per_refs_are_aliases_only": True,
        },
        "summary": {
            "source_identity_count": len(decisions),
            "accepted_identity_count": len(decisions),
            "legacy_namespace_conflict_count": sum(
                bool(item["ambiguity_flags"]) for item in decisions
            ),
        },
        "decisions": decisions,
        "declarations": {
            "v3_database_write_count": 0,
            "v4_database_write_count": 0,
            "model_call_count": 0,
            "formal_scoring_allowed": False,
        },
    }
    payload["crosswalk_package_sha256"] = _fingerprint(payload)
    return payload


def build_capability_domain_reviews(
    source_package: Mapping[str, Any],
    *,
    crosswalk: Mapping[str, Any],
    profile_sets: Iterable[tuple[str, Iterable[Mapping[str, Any]]]],
) -> dict[str, dict[str, Any]]:
    person_ref_by_name = {
        decision["source_canonical_name"]: decision["candidate_v4_person_ref"]
        for decision in crosswalk.get("decisions", ())
    }
    domains: dict[str, set[str]] = defaultdict(set)
    evidence: dict[str, set[str]] = defaultdict(set)
    for source_ref, profiles in profile_sets:
        for profile in profiles:
            person_ref = person_ref_by_name.get(profile.get("person"))
            if not person_ref:
                continue
            domains[person_ref].update(
                str(item) for item in profile.get("capability_domains", ()) if item
            )
            evidence[person_ref].add(
                source_ref + "#" + str(profile.get("profile_ref") or profile.get("person"))
            )
    return {
        person_ref: {
            "capability_domains": sorted(values),
            "evidence_refs": sorted(evidence[person_ref]),
            "review_status": "human_frozen",
            "derivation_policy": "union_of_existing_human_frozen_team_profiles",
        }
        for person_ref, values in domains.items()
        if values
    }


def load_identity_registry_profile_sets(
    paths: Iterable[Path],
) -> list[tuple[str, list[dict[str, Any]]]]:
    result = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"identity registry profile set must be a list: {path}")
        result.append((path.as_posix(), payload))
    return result


def add_candidate_identity_manifest(
    registry: dict[str, list[dict[str, Any]]],
    *,
    source_ref: str,
    payload: Mapping[str, Any],
) -> None:
    independently_accepted = bool(
        (payload.get("acceptance_gate") or {}).get(
            "independent_identity_acceptance_completed"
        )
    )
    for person in payload.get("persons", ()):
        name = str(person.get("canonical_name") or "").strip()
        person_ref = str(person.get("person_id") or "").strip()
        if not name or not person_ref:
            continue
        registry.setdefault(name, []).append(
            {
                "canonical_person_ref": person_ref,
                "review_status": "human_frozen" if independently_accepted else "candidate",
                "capability_domains": [],
                "source_ref": source_ref,
                "source_profile_ref": None,
                "source_snapshot_version": payload.get("identity_manifest_code"),
                "identity_authority_status": (
                    "independent_v4_identity_accepted"
                    if independently_accepted
                    else "pilot_identity_candidate"
                ),
            }
        )


def build_team_profile_migration_readiness(
    source_package: Mapping[str, Any],
    *,
    profile_sets: Iterable[tuple[str, Iterable[Mapping[str, Any]]]],
    worklists: Iterable[tuple[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    source_names = {
        entry["identity_source"]["canonical_name"]
        for entry in source_package.get("entries", ())
    }
    profiles = [
        dict(profile)
        for _, rows in profile_sets
        for profile in rows
    ]
    unique_people = {profile.get("person") for profile in profiles}
    variants: dict[tuple[str, str], set[str]] = defaultdict(set)
    for profile in profiles:
        key = (
            str(profile.get("profile_ref") or ""),
            str(profile.get("snapshot_version") or ""),
        )
        variants[key].add(str(profile.get("semantic_fingerprint") or ""))
    conflicts = [
        {"profile_ref": key[0], "snapshot_version": key[1]}
        for key, fingerprints in variants.items()
        if len(fingerprints) > 1
    ]
    windows = [
        task
        for _, worklist in worklists
        for task in worklist.get("tasks", ())
    ]
    fully_covered = sum(
        all(member.get("person") in source_names for member in task.get("member_set", ()))
        for task in windows
    )
    return {
        "schema_version": "team-profile-migration-readiness-v1",
        "status": "blocked_pending_identity_profile_and_window_gates",
        "source_profile_match": {
            "team_profile_rows": len(profiles),
            "unique_team_people": len(unique_people),
            "unique_people_matched_to_v3_source": len(unique_people & source_names),
        },
        "window_coverage": {
            "team_window_count": len(windows),
            "fully_source_profile_covered_window_count": fully_covered,
        },
        "contract_readiness": {
            "person_profile_snapshot_directly_instantiable_count": 0,
            "ruler_team_window_snapshot_directly_instantiable_count": 0,
            "duplicate_profile_version_content_conflicts": sorted(
                conflicts, key=lambda item: item["profile_ref"]
            ),
        },
        "formal_team_building_scoring_allowed": False,
    }
