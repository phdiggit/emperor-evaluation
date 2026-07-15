from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


FREEZE_PACKAGE_SCHEMA_VERSION = "v3-person-profile-freeze-package-v1"
CROSSWALK_SCHEMA_VERSION = "person-identity-crosswalk-v1"
REVIEW_PACKAGE_SCHEMA_VERSION = "v4-person-profile-import-review-package-v1"
SOURCE_POLICY_VERSION = "v3-person-profile-readonly-adapter-v1"

TALENT_GRADE_MAPPING = {
    "historic_talent": "historic",
    "top_talent": "top",
    "important_talent": "important",
    "usable_talent": "usable",
    "ordinary_talent": "ordinary",
}
AUTHORITY_CONSENSUS_VALUES = {"weak", "moderate", "strong", "disputed"}
EVIDENCE_STRENGTH_VALUES = {"none", "weak", "moderate", "strong"}
EVIDENCE_COVERAGE_VALUES = {
    "insufficient",
    "partial",
    "substantial",
    "comprehensive",
}
NEGATIVE_TALENT_CLASSES = {
    "sycophant",
    "favorite",
    "power_abuser",
    "framer",
    "extractive_official",
    "cruel_official",
    "incompetent_harmful",
    "traitorous_actor",
    "mixed_or_disputed",
}
NEGATIVE_TALENT_SEVERITIES = {"minor", "material", "major", "historic"}


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    return str(value or "").strip()


def _rows(package: Mapping[str, Any], *names: str) -> list[Mapping[str, Any]]:
    for name in names:
        value = package.get(name)
        if value is not None:
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                raise ValueError(f"冻结包 {name} 必须是数组")
            if any(not isinstance(row, Mapping) for row in value):
                raise ValueError(f"冻结包 {name} 只能包含对象")
            return list(value)
    return []


def _package_view(package: Mapping[str, Any]) -> dict[str, Any]:
    if "entries" not in package:
        return dict(package)
    source = package.get("source") or {}
    identities = [entry["identity_source"] for entry in package.get("entries", ())]
    profiles = [entry["profile_source"] for entry in package.get("entries", ())]
    package_sha = _text(package.get("package_sha256"))
    return {
        **package,
        "package_ref": "v3-person-profiles:" + package_sha[:16],
        "package_version": _text(package.get("schema_version")),
        "source_freeze_ref": _text(source.get("source_freeze_ref")),
        "source_commit": package_sha,
        "source_system": _text(source.get("system")),
        "source_policy_version": SOURCE_POLICY_VERSION,
        "identity_rows": identities,
        "profile_rows": profiles,
    }


def _require_sha256(value: object, field_name: str) -> str:
    rendered = _text(value)
    if len(rendered) != 64 or any(ch not in "0123456789abcdef" for ch in rendered):
        raise ValueError(f"{field_name} 必须是小写 SHA-256")
    return rendered


def validate_v3_person_profile_freeze_package(
    package: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate an already exported, read-only V3 profile package.

    The validator deliberately does not read V3 or write V4.  Numeric legacy IDs
    remain audit data and are never interpreted as V4 identities.
    """

    package = _package_view(package)
    if package.get("schema_version") != FREEZE_PACKAGE_SCHEMA_VERSION:
        raise ValueError("V3 人物画像冻结包 schema_version 非法")
    for field in ("package_ref", "package_version", "source_freeze_ref", "source_commit"):
        if not _text(package.get(field)):
            raise ValueError(f"V3 人物画像冻结包缺少 {field}")
    source_system = _text(package.get("source_system"))
    if source_system != "retrieval_v3":
        raise ValueError("人物画像导入只允许 retrieval_v3 冻结来源")
    policy = _text(package.get("source_policy_version") or SOURCE_POLICY_VERSION)
    if policy != SOURCE_POLICY_VERSION:
        raise ValueError("V3 人物画像来源策略版本非法")

    declarations = package.get("declarations") or {}
    if declarations.get("v3_database_write_count") != 0:
        raise ValueError("冻结迁移包必须声明 V3 零写入")
    if declarations.get("v3_primary_keys_reused_as_v4_ids") is not False:
        raise ValueError("冻结迁移包必须禁止复用 V3 主键")
    if declarations.get("scores_or_rankings_included") is not False:
        raise ValueError("人物画像迁移包不得包含分数或排名")

    identities = _rows(package, "identity_rows", "identities")
    profiles = _rows(package, "profile_rows", "profiles")
    if not identities or not profiles:
        raise ValueError("冻结迁移包必须同时包含 identity_rows 与 profile_rows")

    identity_codes: set[str] = set()
    for row in identities:
        code = _text(row.get("source_object_code"))
        if not code or code in identity_codes:
            raise ValueError("identity_rows 的 source_object_code 必须非空且唯一")
        identity_codes.add(code)
        fingerprints = row.get("source_row_fingerprints")
        fingerprint = row.get("source_row_fingerprint")
        if fingerprint is not None:
            _require_sha256(fingerprint, f"{code}.source_row_fingerprint")
        elif isinstance(fingerprints, Mapping):
            for name, value in fingerprints.items():
                _require_sha256(value, f"{code}.source_row_fingerprints.{name}")
        else:
            raise ValueError(f"{code} 缺少身份源行指纹")

    profile_refs: set[str] = set()
    for row in profiles:
        source_ref = _text(row.get("source_profile_ref"))
        object_code = _text(row.get("source_object_code"))
        if not source_ref or source_ref in profile_refs:
            raise ValueError("profile_rows 的 source_profile_ref 必须非空且唯一")
        if object_code not in identity_codes:
            raise ValueError(f"{source_ref} 指向未知 source_object_code")
        profile_refs.add(source_ref)
        _require_sha256(row.get("source_row_fingerprint"), f"{source_ref}.source_row_fingerprint")

    return {
        "package_ref": _text(package["package_ref"]),
        "package_version": _text(package["package_version"]),
        "source_freeze_ref": _text(package["source_freeze_ref"]),
        "source_commit": _text(package["source_commit"]),
        "identity_count": len(identities),
        "profile_count": len(profiles),
        "content_sha256": _stable_hash(
            {"identity_rows": identities, "profile_rows": profiles}
        ),
    }


def _crosswalk_index(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in decisions:
        if row.get("schema_version", CROSSWALK_SCHEMA_VERSION) != CROSSWALK_SCHEMA_VERSION:
            raise ValueError("人物 identity crosswalk schema_version 非法")
        source_ref = _text(row.get("source_object_ref"))
        source_code = _text(row.get("source_object_code"))
        keys = [key for key in (source_ref, source_code) if key]
        if not keys:
            raise ValueError("crosswalk 缺少 source_object_ref/source_object_code")
        if any(key in index for key in keys):
            raise ValueError("同一 V3 人物存在多条当前 crosswalk decision")
        for key in keys:
            index[key] = row
    return index


def _crosswalk_for(
    identity: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    for key in (
        _text(identity.get("source_object_ref")),
        _text(identity.get("source_object_code")),
    ):
        if key and key in index:
            return index[key]
    return None


def _capability_review(
    capability_domains_by_person: Mapping[str, object],
    *,
    person_ref: str,
    crosswalk_ref: str,
    source_object_code: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    value: object | None = None
    for key in (person_ref, crosswalk_ref, source_object_code):
        if key and key in capability_domains_by_person:
            value = capability_domains_by_person[key]
            break
    if value is None:
        return (), ()
    if isinstance(value, Mapping):
        domains = value.get("capability_domains") or value.get("domains") or ()
        evidence_refs = value.get("evidence_refs") or ()
        if value.get("review_status", "human_frozen") != "human_frozen":
            return (), ()
    else:
        domains = value
        evidence_refs = ()
    if not isinstance(domains, Sequence) or isinstance(domains, (str, bytes)):
        raise ValueError("capability_domains 必须是数组")
    normalized = tuple(dict.fromkeys(_text(item) for item in domains if _text(item)))
    refs = tuple(_text(item) for item in evidence_refs if _text(item))
    return normalized, refs


def _axis(profile: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = profile.get(name)
    return value if isinstance(value, Mapping) else {}


def _profile_candidate(
    package_summary: Mapping[str, Any],
    identity: Mapping[str, Any],
    profile: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    capability_domains_by_person: Mapping[str, object],
) -> tuple[str, list[str], dict[str, Any] | None]:
    source_status = _text(identity.get("source_identity_status"))
    merge_lineage = identity.get("merge_lineage") or {}
    merged_into = _text(
        merge_lineage.get("merged_into_source_object_code")
        if isinstance(merge_lineage, Mapping)
        else ""
    )
    if source_status == "merged" or merged_into:
        return "blocked_merge_conflict", ["legacy identity 存在未消解 merge lineage"], None
    if source_status != "active" or _text(profile.get("source_identity_status")) != "active":
        return "blocked_source_state", ["source identity_status 必须为 active"], None

    mapping_status = _text(crosswalk.get("mapping_status"))
    if mapping_status not in {
        "accepted",
        "accepted_existing_v4_identity",
        "accepted_user_authorized_v3_identity",
    }:
        status = {
            "conflicting_v4_refs": "blocked_identity_conflict",
            "no_v4_target": "blocked_identity_no_target",
            "unique_name_candidate": "blocked_identity_review",
            "needs_merge_resolution": "blocked_merge_conflict",
        }.get(mapping_status, "blocked_identity")
        return status, [f"crosswalk mapping_status={mapping_status or 'missing'}"], None
    person_ref = _text(
        crosswalk.get("v4_canonical_person_ref")
        or crosswalk.get("candidate_v4_person_ref")
    )
    source_numeric_id = _text(identity.get("source_numeric_id"))
    forbidden_refs = {
        source_numeric_id,
        _text(identity.get("source_object_code")),
        _text(identity.get("source_object_identity_key")),
    }
    if not person_ref or person_ref.isdigit() or person_ref in forbidden_refs:
        return "blocked_identity", ["V4 person ref 缺失或复用了 V3 身份"], None
    if not (crosswalk.get("mapping_basis_refs") or ()):
        return "blocked_identity", ["accepted crosswalk 缺少人工 mapping_basis_refs"], None

    if (
        _text(profile.get("source_review_status")) != "accepted"
        or _text(profile.get("source_readiness_status")) != "profile_complete"
    ):
        return "blocked_profile_review", ["V3 profile 必须 accepted 且 profile_complete"], None

    talent = _axis(profile, "talent_axis")
    source_grade = _text(talent.get("grade") or profile.get("talent_grade"))
    grade = TALENT_GRADE_MAPPING.get(source_grade)
    grade_version = _text(
        talent.get("version") or profile.get("talent_grade_version")
    )
    try:
        confidence = float(
            talent.get("confidence", profile.get("talent_grade_confidence"))
        )
    except (TypeError, ValueError):
        confidence = -1.0
    consensus = _text(
        talent.get("authority_consensus")
        or profile.get("talent_authority_consensus")
    )
    support = _text(
        talent.get("performance_support")
        or profile.get("talent_performance_support")
    )
    coverage = _text(
        talent.get("evidence_coverage")
        or profile.get("talent_evidence_coverage")
    )
    if (
        grade is None
        or not grade_version
        or not 0 <= confidence <= 1
        or consensus not in AUTHORITY_CONSENSUS_VALUES
        or support not in EVIDENCE_STRENGTH_VALUES
        or coverage not in EVIDENCE_COVERAGE_VALUES
    ):
        return "blocked_profile_review", ["人才能力轴字段不满足 V4 合同"], None

    negative = _axis(profile, "negative_axis")
    negative_version = _text(
        negative.get("version") or profile.get("negative_talent_version")
    )
    review_completed = negative.get("review_completed")
    has_negative = negative.get("has_negative_class")
    negative_class = negative.get("class", profile.get("negative_talent_class"))
    severity = negative.get("severity", profile.get("negative_talent_severity"))
    if review_completed is not True or not negative_version or not isinstance(has_negative, bool):
        return "blocked_negative_axis", ["负面画像轴必须显式完成评审"], None
    if has_negative:
        if (
            _text(negative_class) not in NEGATIVE_TALENT_CLASSES
            or _text(severity) not in NEGATIVE_TALENT_SEVERITIES
        ):
            return "blocked_negative_axis", ["负面画像 class/severity 非法"], None
        normalized_negative_class: str | None = _text(negative_class)
        normalized_severity: str | None = _text(severity)
    else:
        if negative_class not in (None, "") or severity not in (None, ""):
            return "blocked_negative_axis", ["无负面类型时 class/severity 必须为空"], None
        normalized_negative_class = None
        normalized_severity = None

    crosswalk_ref = _text(crosswalk.get("crosswalk_ref"))
    domains, domain_refs = _capability_review(
        capability_domains_by_person,
        person_ref=person_ref,
        crosswalk_ref=crosswalk_ref,
        source_object_code=_text(identity.get("source_object_code")),
    )
    if not domains:
        return (
            "blocked_capability_domains",
            ["accepted crosswalk 仍缺少独立冻结的 capability_domains"],
            None,
        )

    source_profile_ref = _text(profile.get("source_profile_ref"))
    source_row_fingerprint = _require_sha256(
        profile.get("source_row_fingerprint"),
        f"{source_profile_ref}.source_row_fingerprint",
    )
    snapshot_version = (
        "v3-profile-import@"
        + _text(package_summary["source_freeze_ref"])
        + ":"
        + grade_version
        + ":"
        + negative_version
    )
    lineage_refs = tuple(
        dict.fromkeys(
            item
            for item in (
                f"package:{package_summary['package_ref']}",
                f"crosswalk:{crosswalk_ref}",
                f"source-profile:{source_profile_ref}",
                *(crosswalk.get("mapping_basis_refs") or ()),
                *(talent.get("authority_source_refs") or ()),
                *(negative.get("authority_source_refs") or ()),
                *domain_refs,
            )
            if _text(item)
        )
    )
    candidate = {
        "profile_ref": f"PROFILE-{person_ref}@{snapshot_version}",
        "canonical_person_ref": person_ref,
        "snapshot_version": snapshot_version,
        "talent_grade": grade,
        "talent_grade_version": grade_version,
        "talent_grade_confidence": confidence,
        "talent_authority_consensus": consensus,
        "talent_performance_support": support,
        "talent_evidence_coverage": coverage,
        "capability_domains": list(domains),
        "negative_talent_class": normalized_negative_class,
        "negative_talent_severity": normalized_severity,
        "negative_talent_version": negative_version,
        "lineage_refs": list(lineage_refs),
        "source_profile_ref": source_profile_ref,
        "source_row_fingerprint": source_row_fingerprint,
        "candidate_status": "requires_v4_human_review",
    }
    candidate["semantic_fingerprint"] = _stable_hash(candidate)
    return "ready_for_v4_profile_review", [], candidate


def build_v4_profile_import_review_package(
    package: Mapping[str, Any],
    crosswalk_decisions: Sequence[Mapping[str, Any]],
    *,
    capability_domains_by_person: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Build a review package; never instantiate a formal PersonProfileSnapshot."""

    package_summary = validate_v3_person_profile_freeze_package(package)
    package = _package_view(package)
    identities = {
        _text(row.get("source_object_code")): row
        for row in _rows(package, "identity_rows", "identities")
    }
    profiles = _rows(package, "profile_rows", "profiles")
    crosswalks = _crosswalk_index(crosswalk_decisions)
    capability_reviews = capability_domains_by_person or {}

    items: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    seen_candidate_keys: dict[tuple[str, str], str] = {}
    for profile in profiles:
        object_code = _text(profile.get("source_object_code"))
        identity = identities[object_code]
        crosswalk = _crosswalk_for(identity, crosswalks)
        if crosswalk is None:
            status, blockers, candidate = (
                "blocked_identity",
                ["缺少当前 crosswalk decision"],
                None,
            )
        else:
            status, blockers, candidate = _profile_candidate(
                package_summary,
                identity,
                profile,
                crosswalk,
                capability_reviews,
            )
        if candidate is not None:
            key = (candidate["profile_ref"], candidate["snapshot_version"])
            prior = seen_candidate_keys.get(key)
            if prior is not None and prior != candidate["semantic_fingerprint"]:
                status = "duplicate_content_conflict"
                blockers = ["同一 profile_ref + snapshot_version 对应不同内容"]
                candidate = None
            else:
                seen_candidate_keys[key] = candidate["semantic_fingerprint"]
        status_counts[status] += 1
        items.append(
            {
                "source_profile_ref": _text(profile.get("source_profile_ref")),
                "source_object_code": object_code,
                "crosswalk_ref": _text((crosswalk or {}).get("crosswalk_ref")),
                "gate_status": status,
                "blockers": blockers,
                "profile_snapshot_candidate": candidate,
                "formal_profile_generated": False,
            }
        )

    payload = {
        "schema_version": REVIEW_PACKAGE_SCHEMA_VERSION,
        "status": "v4_profile_import_review_required",
        "source_package_ref": package_summary["package_ref"],
        "source_package_version": package_summary["package_version"],
        "source_freeze_ref": package_summary["source_freeze_ref"],
        "source_commit": package_summary["source_commit"],
        "source_content_sha256": package_summary["content_sha256"],
        "summary": {
            "profile_count": len(items),
            "gate_status_counts": dict(sorted(status_counts.items())),
            "formal_profile_generated_count": 0,
            "v3_database_write_count": 0,
            "v3_primary_key_reuse_count": 0,
        },
        "items": items,
        "declarations": {
            "requires_separate_v4_human_review": True,
            "formal_profile_generation_allowed": False,
            "pending_or_merged_source_auto_accept_allowed": False,
        },
    }
    payload["review_package_sha256"] = _stable_hash(payload)
    return payload


def evaluate_v3_person_profile_import(
    package: Mapping[str, Any],
    crosswalk_decisions: Sequence[Mapping[str, Any]],
    *,
    capability_domains_by_person: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Compatibility alias for the pure review-package builder."""

    return build_v4_profile_import_review_package(
        package,
        crosswalk_decisions,
        capability_domains_by_person=capability_domains_by_person,
    )
