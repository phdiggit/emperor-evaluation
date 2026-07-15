from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.person_snapshot import PersonProfileSnapshot
from emperor_v4.evaluation.v3_person_profile_import import (
    TALENT_GRADE_MAPPING,
    validate_v3_person_profile_freeze_package,
)


REPORT_SCHEMA_VERSION = "v3-authorized-profile-promotion-report-v1"
PROMOTION_POLICY_VERSION = "v3-authorized-profile-promotion-v1"
CAPABILITY_NOT_ASSESSED_POLICY_REF = (
    "migration-policy:v3-profile-capability-not-assessed-v1"
)
ACCEPTED_CROSSWALK_STATUSES = {
    "accepted",
    "accepted_existing_v4_identity",
    "accepted_user_authorized_v3_identity",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _entries(source_package: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    entries = source_package.get("entries")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise ValueError("V3 profile source package 缺少 entries")
    if any(not isinstance(entry, Mapping) for entry in entries):
        raise ValueError("V3 profile source package entries 只能包含对象")
    return list(entries)


def _decisions(
    crosswalk: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    if isinstance(crosswalk, Mapping):
        rows = crosswalk.get("decisions")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValueError("accepted crosswalk package 缺少 decisions")
        metadata: Mapping[str, Any] = crosswalk
    else:
        rows = crosswalk
        metadata = {}
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("crosswalk decisions 只能包含对象")
    return list(rows), metadata


def _crosswalk_index(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for decision in decisions:
        source_ref = _text(decision.get("source_object_ref"))
        if not source_ref or source_ref in index:
            raise ValueError("crosswalk source_object_ref 必须非空且唯一")
        index[source_ref] = decision
    return index


def _capability_entry(
    capability_map: Mapping[str, object], person_ref: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    value = capability_map.get(person_ref)
    if value is None:
        return (), ()
    if isinstance(value, Mapping):
        if value.get("review_status") != "human_frozen":
            return (), ()
        raw_domains = value.get("capability_domains") or value.get("domains") or ()
        raw_refs = value.get("evidence_refs") or ()
    else:
        raw_domains = value
        raw_refs = ()
    if not isinstance(raw_domains, Sequence) or isinstance(
        raw_domains, (str, bytes)
    ):
        raise ValueError("capability map 的 capability_domains 必须是数组")
    if not isinstance(raw_refs, Sequence) or isinstance(raw_refs, (str, bytes)):
        raise ValueError("capability map 的 evidence_refs 必须是数组")
    domains = tuple(
        dict.fromkeys(_text(item) for item in raw_domains if _text(item))
    )
    refs = tuple(dict.fromkeys(_text(item) for item in raw_refs if _text(item)))
    return domains, refs


def _lineage_refs(
    *,
    source_package: Mapping[str, Any],
    profile_source: Mapping[str, Any],
    decision: Mapping[str, Any],
    capability_refs: Sequence[str],
    authorization_ref: str,
) -> tuple[str, ...]:
    authority_refs: list[str] = []
    for row in profile_source.get("authority_lineage") or ():
        if not isinstance(row, Mapping):
            continue
        reference = _text(
            row.get("claim_key")
            or row.get("authority_source_ref")
            or row.get("source_ref")
        )
        authority_refs.append(
            reference if reference else "v3-authority-lineage:" + _stable_hash(row)
        )
    refs = (
        authorization_ref,
        "source-package:" + _text(source_package.get("package_sha256")),
        "crosswalk:" + _text(decision.get("crosswalk_ref")),
        "source-profile:" + _text(profile_source.get("source_profile_ref")),
        *(decision.get("mapping_basis_refs") or ()),
        *authority_refs,
        *capability_refs,
    )
    return tuple(dict.fromkeys(_text(item) for item in refs if _text(item)))


def _promote_entry(
    entry: Mapping[str, Any],
    *,
    source_package: Mapping[str, Any],
    decision: Mapping[str, Any] | None,
    capability_map: Mapping[str, object],
    authorization_ref: str,
) -> tuple[str, tuple[str, ...], dict[str, Any] | None]:
    identity = entry.get("identity_source")
    profile = entry.get("profile_source")
    if not isinstance(identity, Mapping) or not isinstance(profile, Mapping):
        return "blocked_typed_profile_source", ("缺少 typed identity/profile source",), None
    if (
        identity.get("record_type") != "v3_person_identity_source"
        or profile.get("record_type") != "v3_person_profile_source"
    ):
        return "blocked_typed_profile_source", ("source record_type 非法",), None
    if decision is None:
        return "blocked_identity", ("缺少 crosswalk decision",), None
    if decision.get("mapping_status") not in ACCEPTED_CROSSWALK_STATUSES:
        return (
            "blocked_identity",
            ("crosswalk 未接受: " + _text(decision.get("mapping_status")),),
            None,
        )
    if authorization_ref not in set(decision.get("mapping_basis_refs") or ()):
        return "blocked_authorization", ("crosswalk 未绑定本次 authorization_ref",), None
    if decision.get("profile_import_review_status") not in {
        "accepted_for_v3_axes",
        "accepted",
    }:
        return "blocked_authorization", ("画像轴未获授权接受",), None
    if (
        _text(identity.get("source_identity_status")) != "active"
        or _text(profile.get("source_identity_status")) != "active"
    ):
        return "blocked_source_state", ("V3 identity_status 必须为 active",), None
    if (
        _text(profile.get("source_review_status")) != "accepted"
        or _text(profile.get("source_readiness_status")) != "profile_complete"
    ):
        return (
            "blocked_source_state",
            ("V3 profile 必须 accepted 且 profile_complete",),
            None,
        )
    if decision.get("source_identity_fingerprint") != identity.get(
        "source_row_fingerprint"
    ):
        return "blocked_identity", ("crosswalk 与 source identity 指纹不一致",), None

    person_ref = _text(
        decision.get("v4_canonical_person_ref")
        or decision.get("candidate_v4_person_ref")
    )
    forbidden_refs = {
        _text(identity.get("source_numeric_id")),
        _text(identity.get("source_object_code")),
        _text(identity.get("source_object_identity_key")),
    }
    if not person_ref or person_ref.isdigit() or person_ref in forbidden_refs:
        return "blocked_identity", ("V4 person ref 缺失或复用了 V3 身份",), None

    capability_domains, capability_refs = _capability_entry(
        capability_map, person_ref
    )
    if not capability_domains:
        capability_refs = (CAPABILITY_NOT_ASSESSED_POLICY_REF,)

    talent = profile.get("talent_axis")
    negative = profile.get("negative_axis")
    if not isinstance(talent, Mapping) or not isinstance(negative, Mapping):
        return (
            "blocked_typed_profile_source",
            ("talent_axis/negative_axis 必须来自 typed profile_source",),
            None,
        )
    source_grade = _text(talent.get("grade"))
    talent_grade = TALENT_GRADE_MAPPING.get(source_grade)
    if talent_grade is None:
        return "blocked_typed_profile_source", ("V3 talent grade 非法",), None
    if negative.get("review_completed") is not True or not isinstance(
        negative.get("has_negative_class"), bool
    ):
        return "blocked_typed_profile_source", ("V3 negative axis 未完成评审",), None
    has_negative = negative["has_negative_class"]
    negative_class = negative.get("class")
    negative_severity = negative.get("severity")
    if has_negative != (negative_class is not None):
        return "blocked_typed_profile_source", ("V3 negative axis shape 非法",), None
    if not has_negative and negative_severity is not None:
        return "blocked_typed_profile_source", ("V3 negative severity 无 class",), None

    source_row_fingerprint = _text(profile.get("source_row_fingerprint"))
    source_profile_ref = _text(profile.get("source_profile_ref"))
    if len(source_row_fingerprint) != 64 or not source_profile_ref:
        return "blocked_typed_profile_source", ("profile source 身份或指纹非法",), None
    lineage_refs = _lineage_refs(
        source_package=source_package,
        profile_source=profile,
        decision=decision,
        capability_refs=capability_refs,
        authorization_ref=authorization_ref,
    )
    snapshot_version = (
        PROMOTION_POLICY_VERSION
        + ":"
        + _text(talent.get("version"))
        + ":"
        + _text(negative.get("version"))
        + ":"
        + source_row_fingerprint[:12]
    )
    snapshot_core = {
        "profile_ref": "PROFILE-" + person_ref + "@" + snapshot_version,
        "canonical_person_ref": person_ref,
        "snapshot_version": snapshot_version,
        "talent_grade": talent_grade,
        "talent_grade_version": _text(talent.get("version")),
        "talent_grade_confidence": talent.get("confidence"),
        "talent_authority_consensus": _text(talent.get("authority_consensus")),
        "talent_performance_support": _text(talent.get("performance_support")),
        "talent_evidence_coverage": _text(talent.get("evidence_coverage")),
        "capability_domains": capability_domains,
        "negative_talent_class": (
            _text(negative_class) if negative_class is not None else None
        ),
        "negative_talent_severity": (
            _text(negative_severity) if negative_severity is not None else None
        ),
        "negative_talent_version": _text(negative.get("version")),
        "lineage_refs": lineage_refs,
        "source_profile_ref": source_profile_ref,
        "source_row_fingerprint": source_row_fingerprint,
        "review_status": "human_frozen",
    }
    try:
        snapshot = PersonProfileSnapshot(
            **snapshot_core,
            semantic_fingerprint=_stable_hash(snapshot_core),
        )
    except (TypeError, ValueError) as exc:
        return "blocked_typed_profile_source", (str(exc),), None
    return "promoted_human_frozen", (), asdict(snapshot)


def promote_authorized_v3_person_profiles(
    source_package: Mapping[str, Any],
    accepted_crosswalk: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    capability_map: Mapping[str, object],
    authorization_ref: str,
) -> dict[str, Any]:
    """Promote only explicitly authorized, typed V3 profile axes.

    This pure function performs no database or model work.  Every returned formal
    snapshot has been constructed as ``PersonProfileSnapshot``; blocked rows never
    receive a partial snapshot.
    """

    authorization_ref = _text(authorization_ref)
    if not authorization_ref:
        raise ValueError("authorization_ref is required")
    source_summary = validate_v3_person_profile_freeze_package(source_package)
    decisions, crosswalk_metadata = _decisions(accepted_crosswalk)
    source_package_sha = _text(source_package.get("package_sha256"))
    crosswalk_source_sha = _text(crosswalk_metadata.get("source_package_sha256"))
    if crosswalk_source_sha and crosswalk_source_sha != source_package_sha:
        raise ValueError("crosswalk 与 source package SHA 不一致")
    crosswalk_authorization = _text(crosswalk_metadata.get("authorization_ref"))
    if crosswalk_authorization and crosswalk_authorization != authorization_ref:
        raise ValueError("crosswalk authorization_ref 与本次授权不一致")
    decision_by_ref = _crosswalk_index(decisions)

    items: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    seen_profile_keys: dict[tuple[str, str], str] = {}
    for entry in _entries(source_package):
        identity = entry.get("identity_source") or {}
        profile = entry.get("profile_source") or {}
        source_object_ref = _text(identity.get("source_object_ref"))
        decision = decision_by_ref.get(source_object_ref)
        status, blockers, snapshot = _promote_entry(
            entry,
            source_package=source_package,
            decision=decision,
            capability_map=capability_map,
            authorization_ref=authorization_ref,
        )
        if snapshot is not None:
            key = (snapshot["profile_ref"], snapshot["snapshot_version"])
            fingerprint = snapshot["semantic_fingerprint"]
            prior = seen_profile_keys.get(key)
            if prior is not None and prior != fingerprint:
                status = "blocked_duplicate_content_conflict"
                blockers = ("同一 V4 profile identity 对应不同内容",)
                snapshot = None
            else:
                seen_profile_keys[key] = fingerprint
        counts[status] += 1
        items.append(
            {
                "person": _text(identity.get("canonical_name")),
                "identity_scope": _text(identity.get("canonical_name"))
                + "（"
                + _text((identity.get("affiliations") or [{}])[0].get("dynasty_label"))
                + "）",
                "talent_evaluation": dict(profile.get("talent_axis") or {}),
                "negative_evaluation": dict(profile.get("negative_axis") or {}),
                "capability_domain_status": (
                    "not_assessed"
                    if snapshot is not None
                    and not tuple(snapshot.get("capability_domains") or ())
                    else "human_frozen"
                ),
                "source_object_ref": source_object_ref,
                "source_profile_ref": _text(profile.get("source_profile_ref")),
                "crosswalk_ref": _text((decision or {}).get("crosswalk_ref")),
                "promotion_status": status,
                "blockers": list(blockers),
                "person_profile_snapshot": snapshot,
            }
        )

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "v3_authorized_profile_promotion_complete",
        "promotion_policy_version": PROMOTION_POLICY_VERSION,
        "authorization_ref": authorization_ref,
        "source_package_ref": source_summary["package_ref"],
        "source_package_sha256": source_package_sha,
        "summary": {
            "source_profile_count": len(items),
            "promotion_status_counts": dict(sorted(counts.items())),
            "human_frozen_profile_count": counts["promoted_human_frozen"],
            "blocked_profile_count": len(items) - counts["promoted_human_frozen"],
            "capability_domain_reviewed_count": sum(
                item["capability_domain_status"] == "human_frozen"
                for item in items
            ),
            "capability_domain_not_assessed_count": sum(
                item["capability_domain_status"] == "not_assessed"
                for item in items
            ),
            "v3_database_write_count": 0,
            "v4_database_write_count": 0,
            "model_call_count": 0,
        },
        "items": items,
        "declarations": {
            "v3_numeric_primary_key_reused": False,
            "talent_and_negative_axes_source": "typed_v3_profile_source_only",
            "capability_domains_source": (
                "separate_human_frozen_map_or_empty_unasserted"
            ),
            "empty_capability_domains_mean_not_assessed_not_no_capability": True,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _stable_hash(report)
    return report


def evaluate_v3_authorized_profile_promotion(
    source_package: Mapping[str, Any],
    accepted_crosswalk: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    capability_map: Mapping[str, object],
    authorization_ref: str,
) -> dict[str, Any]:
    return promote_authorized_v3_person_profiles(
        source_package,
        accepted_crosswalk,
        capability_map,
        authorization_ref,
    )
