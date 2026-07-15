from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.person_snapshot import (
    PersonProfileSnapshot,
    RulerTeamWindowMember,
    RulerTeamWindowSnapshot,
)


SCHEMA = "v4_person_profile"
AUTHORIZED_MAPPING_STATUS = "accepted_user_authorized_v3_identity"
ADVISORY_LOCK_ID = int.from_bytes(
    sha256(b"emperor-v4-person-profile-snapshots").digest()[:8],
    "big",
    signed=True,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class PersonProfileImportResult:
    table_writes: Mapping[str, int]

    @property
    def business_write_count(self) -> int:
        return sum(self.table_writes.values())


def _json_value(value: object) -> object:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _stable_hash(value: object) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    return str(value or "").strip()


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def _profile(value: Mapping[str, Any]) -> PersonProfileSnapshot:
    fields = PersonProfileSnapshot.__dataclass_fields__
    payload = {name: value[name] for name in fields if name in value}
    for name in ("capability_domains", "lineage_refs"):
        if name in payload:
            payload[name] = tuple(payload[name])
    return PersonProfileSnapshot(**payload)


def _window(value: Mapping[str, Any]) -> RulerTeamWindowSnapshot:
    fields = RulerTeamWindowSnapshot.__dataclass_fields__
    payload = {name: value[name] for name in fields if name in value}
    payload["members"] = tuple(
        RulerTeamWindowMember(
            person_ref=_text(member["person_ref"]),
            profile_ref=_text(member["profile_ref"]),
            active_from=_text(member["active_from"]),
            active_to=_text(member["active_to"]),
            role_families=tuple(_text(item) for item in member["role_families"]),
            evidence_refs=tuple(_text(item) for item in member["evidence_refs"]),
        )
        for member in _rows(payload.get("members"), "team window members")
    )
    return RulerTeamWindowSnapshot(**payload)


def _promotion_packages(
    promotions: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    packages = [promotions] if isinstance(promotions, Mapping) else list(promotions)
    if not packages or any(not isinstance(package, Mapping) for package in packages):
        raise ValueError("profile promotions must contain one or more packages")
    return packages


def _profile_snapshots(
    packages: Sequence[Mapping[str, Any]],
) -> tuple[tuple[PersonProfileSnapshot, Mapping[str, Any]], ...]:
    snapshots: list[tuple[PersonProfileSnapshot, Mapping[str, Any]]] = []
    seen: dict[tuple[str, str], object] = {}
    for package in packages:
        for item in _rows(package.get("items"), "profile promotion items"):
            raw = item.get("person_profile_snapshot")
            if raw is None:
                continue
            if not isinstance(raw, Mapping):
                raise ValueError("person_profile_snapshot must be an object")
            snapshot = _profile(raw)
            payload = _json_value(asdict(snapshot))
            key = (snapshot.profile_ref, snapshot.snapshot_version)
            previous = seen.get(key)
            if previous is not None and previous != payload:
                raise ValueError("duplicate profile identity has conflicting content")
            if previous is None:
                seen[key] = payload
                snapshots.append((snapshot, item))
    return tuple(snapshots)


def _profile_catalog_rows(
    profile_items: Sequence[tuple[PersonProfileSnapshot, Mapping[str, Any]]],
    identities: Sequence[Mapping[str, Any]],
    import_batch_id: str,
) -> tuple[dict[str, Any], ...]:
    identity_by_ref = {row["person_ref"]: row for row in identities}
    rows: list[dict[str, Any]] = []
    for profile, item in profile_items:
        identity = identity_by_ref.get(profile.canonical_person_ref)
        talent = item.get("talent_evaluation")
        political_risk = item.get("negative_evaluation")
        if not isinstance(identity, Mapping):
            raise ValueError("profile catalog identity is missing")
        if not isinstance(talent, Mapping) or not _text(talent.get("basis")):
            raise ValueError("profile catalog talent_grade_basis is missing")
        if not isinstance(political_risk, Mapping) or not _text(
            political_risk.get("basis")
        ):
            raise ValueError("profile catalog political_risk_basis is missing")
        row = {
            "profile_ref": profile.profile_ref,
            "snapshot_version": profile.snapshot_version,
            "person_ref": profile.canonical_person_ref,
            "canonical_name": _text(identity["canonical_name"]),
            "historical_context": _text(identity["historical_context"]),
            "talent_grade": profile.talent_grade,
            "talent_grade_version": profile.talent_grade_version,
            "talent_grade_confidence": profile.talent_grade_confidence,
            "talent_grade_basis": _text(talent["basis"]),
            "talent_authority_consensus": profile.talent_authority_consensus,
            "talent_performance_support": profile.talent_performance_support,
            "talent_evidence_coverage": profile.talent_evidence_coverage,
            "negative_risk_status": (
                "established"
                if profile.negative_talent_class is not None
                else "no_established_class"
            ),
            "negative_talent_class": profile.negative_talent_class,
            "negative_talent_severity": profile.negative_talent_severity,
            "negative_talent_basis": _text(political_risk["basis"]),
            "negative_talent_version": profile.negative_talent_version,
            "negative_talent_confidence": political_risk.get("confidence"),
            "negative_authority_consensus": _text(
                political_risk.get("authority_consensus")
            ),
            "negative_fact_support": _text(political_risk.get("fact_support")),
            "negative_evidence_coverage": _text(
                political_risk.get("evidence_coverage")
            ),
            "capability_domains": list(profile.capability_domains),
            "source_profile_ref": profile.source_profile_ref,
            "review_status": profile.review_status,
            "idempotency_key": (
                f"person-profile-catalog:{profile.profile_ref}:{profile.snapshot_version}"
            ),
            "import_batch_id": import_batch_id,
        }
        row["payload"] = _json_value(
            {key: value for key, value in row.items() if key != "import_batch_id"}
        )
        rows.append(row)
    return tuple(rows)


def _team_windows(
    promotion: Mapping[str, Any],
) -> tuple[RulerTeamWindowSnapshot, ...]:
    windows: list[RulerTeamWindowSnapshot] = []
    seen: dict[str, object] = {}
    for item in _rows(promotion.get("items"), "team window promotion items"):
        raw = item.get("team_window_snapshot")
        if raw is None:
            continue
        if not isinstance(raw, Mapping):
            raise ValueError("team_window_snapshot must be an object")
        snapshot = _window(raw)
        payload = _json_value(asdict(snapshot))
        previous = seen.get(snapshot.window_ref)
        if previous is not None and previous != payload:
            raise ValueError("duplicate team-window identity has conflicting content")
        if previous is None:
            seen[snapshot.window_ref] = payload
            windows.append(snapshot)
    return tuple(windows)


def _batch(
    metadata: Mapping[str, Any],
    *,
    packages: Sequence[Mapping[str, Any]],
    crosswalk: Mapping[str, Any],
    window_promotion: Mapping[str, Any],
) -> dict[str, Any]:
    required = (
        "import_batch_id",
        "idempotency_key",
        "source_system",
        "source_freeze_ref",
        "contract_version",
    )
    result = {name: _text(metadata.get(name)) for name in required}
    missing = [name for name, value in result.items() if not value]
    if missing:
        raise ValueError("import batch metadata missing: " + ", ".join(missing))
    fingerprint = _text(
        metadata.get("source_package_fingerprint")
        or crosswalk.get("source_package_sha256")
    )
    if not _SHA256.fullmatch(fingerprint):
        raise ValueError("source_package_fingerprint must be SHA-256")
    crosswalk_fingerprint = _text(crosswalk.get("source_package_sha256"))
    if crosswalk_fingerprint and crosswalk_fingerprint != fingerprint:
        raise ValueError("crosswalk and import batch source fingerprints disagree")
    status = _text(metadata.get("status") or "applied")
    if status not in {"prepared", "reviewed", "applied", "partially_blocked", "rejected"}:
        raise ValueError("invalid import batch status")
    payload = {
        "metadata": _json_value(dict(metadata.get("payload") or {})),
        "profile_promotion_fingerprints": [_stable_hash(item) for item in packages],
        "identity_crosswalk_fingerprint": _stable_hash(crosswalk),
        "team_window_promotion_fingerprint": _stable_hash(window_promotion),
    }
    return {
        **result,
        "source_package_fingerprint": fingerprint,
        "status": status,
        "payload": payload,
    }


def _ruler_identity_rows(
    metadata: Mapping[str, Any], windows: Sequence[RulerTeamWindowSnapshot]
) -> dict[str, dict[str, str]]:
    raw = metadata.get("ruler_identities")
    rows: dict[str, dict[str, str]] = {}
    if isinstance(raw, Mapping):
        iterator = []
        for person_ref, value in raw.items():
            if isinstance(value, Mapping):
                iterator.append({"person_ref": person_ref, **value})
            else:
                iterator.append({"person_ref": person_ref, "canonical_name": value})
    else:
        iterator = _rows(raw or (), "ruler_identities")
    for item in iterator:
        person_ref = _text(item.get("person_ref"))
        canonical_name = _text(item.get("canonical_name"))
        if not person_ref or not canonical_name or person_ref in rows:
            raise ValueError("ruler identities require unique person_ref and canonical_name")
        rows[person_ref] = {
            "person_ref": person_ref,
            "canonical_name": canonical_name,
            "historical_context": _text(item.get("historical_context") or "ruler"),
            "identity_fingerprint": _text(item.get("identity_fingerprint"))
            or _stable_hash(
                {
                    "person_ref": person_ref,
                    "canonical_name": canonical_name,
                    "historical_context": _text(item.get("historical_context") or "ruler"),
                }
            ),
        }
    missing = sorted({window.ruler_ref for window in windows} - rows.keys())
    if missing:
        raise ValueError("import batch metadata lacks ruler identities: " + ", ".join(missing))
    return rows


def _identity_and_legacy_rows(
    crosswalk: Mapping[str, Any],
    profile_items: Sequence[tuple[PersonProfileSnapshot, Mapping[str, Any]]],
    rulers: Mapping[str, Mapping[str, str]],
    import_batch_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    identities: dict[str, dict[str, Any]] = {}
    legacy_refs: list[dict[str, Any]] = []
    for decision in _rows(crosswalk.get("decisions"), "identity crosswalk decisions"):
        if decision.get("mapping_status") != AUTHORIZED_MAPPING_STATUS:
            raise ValueError("identity crosswalk contains a non-authorized mapping")
        person_ref = _text(
            decision.get("v4_canonical_person_ref")
            or decision.get("candidate_v4_person_ref")
        )
        fingerprint = _text(decision.get("source_identity_fingerprint"))
        basis_refs = list(decision.get("mapping_basis_refs") or ())
        if not person_ref or not _SHA256.fullmatch(fingerprint) or not basis_refs:
            raise ValueError("authorized identity crosswalk decision is incomplete")
        identities[person_ref] = {
            "person_ref": person_ref,
            "canonical_name": _text(decision.get("source_canonical_name")),
            "historical_context": "v3_authorized_person_profile",
            "identity_fingerprint": fingerprint,
            "identity_status": "active",
            "semantic_version": 1,
            "idempotency_key": f"person-identity:{person_ref}:v1",
            "import_batch_id": import_batch_id,
            "payload": _json_value(dict(decision)),
        }
        source_object_ref = _text(decision.get("source_object_ref"))
        legacy_refs.append(
            {
                "legacy_ref_id": "LREF-" + _stable_hash(
                    {"source_system": "retrieval_v3", "source_object_ref": source_object_ref}
                )[:24].upper(),
                "source_system": "retrieval_v3",
                "source_object_ref": source_object_ref,
                "source_identity_fingerprint": fingerprint,
                "person_ref": person_ref,
                "mapping_status": AUTHORIZED_MAPPING_STATUS,
                "mapping_basis_refs": basis_refs,
                "idempotency_key": f"legacy-ref:retrieval_v3:{fingerprint}",
                "import_batch_id": import_batch_id,
            }
        )

    for profile, item in profile_items:
        if profile.canonical_person_ref in identities:
            continue
        canonical_name = _text(item.get("person"))
        historical_context = _text(item.get("identity_scope") or "supplemental_profile")
        if not canonical_name:
            raise ValueError("supplemental profile lacks canonical person name")
        identity_payload = {
            "person_ref": profile.canonical_person_ref,
            "canonical_name": canonical_name,
            "historical_context": historical_context,
            "source_profile_ref": profile.source_profile_ref,
        }
        identities[profile.canonical_person_ref] = {
            **identity_payload,
            "identity_fingerprint": _stable_hash(identity_payload),
            "identity_status": "active",
            "semantic_version": 1,
            "idempotency_key": f"person-identity:{profile.canonical_person_ref}:v1",
            "import_batch_id": import_batch_id,
            "payload": _json_value(identity_payload),
        }

    for person_ref, ruler in rulers.items():
        if person_ref in identities:
            current = identities[person_ref]
            if current["canonical_name"] != ruler["canonical_name"]:
                raise ValueError("ruler identity conflicts with an existing person identity")
            continue
        identities[person_ref] = {
            **ruler,
            "identity_status": "active",
            "semantic_version": 1,
            "idempotency_key": f"person-identity:{person_ref}:v1",
            "import_batch_id": import_batch_id,
            "payload": _json_value(ruler),
        }
    if any(not row["canonical_name"] for row in identities.values()):
        raise ValueError("person identity canonical_name must not be empty")
    return list(identities.values()), legacy_refs


def _lineage(ref: str) -> dict[str, Any]:
    source_system = "v4_person_profile"
    lineage_kind = "declared_lineage"
    source_fingerprint = None
    if ref.startswith("http://") or ref.startswith("https://"):
        source_system, lineage_kind = "web", "historical_source"
    elif ref.startswith("user-authority:"):
        source_system, lineage_kind = "user_authority", "human_authorization"
    elif ref.startswith("source-package:"):
        source_system, lineage_kind = "retrieval_v3", "source_package"
        candidate = ref.rsplit(":", 1)[-1]
        source_fingerprint = candidate if _SHA256.fullmatch(candidate) else None
    elif ref.startswith("source-profile:") or ref.startswith("retrieval_v3:"):
        source_system, lineage_kind = "retrieval_v3", "legacy_profile_source"
    elif ref.startswith("crosswalk:"):
        source_system, lineage_kind = "v4_person_profile", "identity_crosswalk"
    return {
        "lineage_ref": ref,
        "lineage_kind": lineage_kind,
        "source_system": source_system,
        "source_ref": ref,
        "source_fingerprint": source_fingerprint,
    }


class PostgresPersonProfileRepository:
    """Atomic, fail-closed import of frozen identities, profiles, and team windows."""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgresPersonProfileRepository requires an explicit DSN")
        self._dsn = dsn

    def import_promotions(
        self,
        profile_promotions: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        team_window_promotion: Mapping[str, Any],
        identity_crosswalk: Mapping[str, Any],
        import_batch_metadata: Mapping[str, Any],
        *,
        expected_profile_count: int | None = None,
        expected_window_count: int | None = None,
    ) -> PersonProfileImportResult:
        packages = _promotion_packages(profile_promotions)
        profile_items = _profile_snapshots(packages)
        profiles = tuple(item[0] for item in profile_items)
        windows = _team_windows(team_window_promotion)
        if expected_profile_count is not None and len(profiles) != expected_profile_count:
            raise ValueError(f"expected {expected_profile_count} profiles, received {len(profiles)}")
        if expected_window_count is not None and len(windows) != expected_window_count:
            raise ValueError(f"expected {expected_window_count} windows, received {len(windows)}")
        profile_by_ref = {profile.profile_ref: profile for profile in profiles}
        if len(profile_by_ref) != len(profiles):
            raise ValueError("profile_ref must be unique across the import portfolio")
        for window in windows:
            for member in window.members:
                profile = profile_by_ref.get(member.profile_ref)
                if profile is None or profile.canonical_person_ref != member.person_ref:
                    raise ValueError("team window member profile identity is missing or inconsistent")

        batch = _batch(
            import_batch_metadata,
            packages=packages,
            crosswalk=identity_crosswalk,
            window_promotion=team_window_promotion,
        )
        rulers = _ruler_identity_rows(import_batch_metadata, windows)
        identities, legacy_refs = _identity_and_legacy_rows(
            identity_crosswalk, profile_items, rulers, batch["import_batch_id"]
        )
        catalog_rows = _profile_catalog_rows(
            profile_items, identities, batch["import_batch_id"]
        )

        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("PostgresPersonProfileRepository requires psycopg") from exc

        writes = {
            "import_batches": 0,
            "person_identity_registry": 0,
            "person_legacy_refs": 0,
            "person_profile_snapshots": 0,
            "person_profile_catalog": 0,
            "person_profile_lineage": 0,
            "ruler_team_window_snapshots": 0,
            "ruler_team_window_members": 0,
        }
        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))
                writes["import_batches"] += self._insert(
                    cursor,
                    Jsonb,
                    """INSERT INTO v4_person_profile.import_batches
                    (import_batch_id,idempotency_key,source_system,source_freeze_ref,
                     source_package_fingerprint,contract_version,status,payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (import_batch_id) DO NOTHING RETURNING 1""",
                    (
                        batch["import_batch_id"], batch["idempotency_key"],
                        batch["source_system"], batch["source_freeze_ref"],
                        batch["source_package_fingerprint"], batch["contract_version"],
                        batch["status"], Jsonb(batch["payload"]),
                    ),
                    """SELECT jsonb_build_object(
                    'import_batch_id',import_batch_id,'idempotency_key',idempotency_key,
                    'source_system',source_system,'source_freeze_ref',source_freeze_ref,
                    'source_package_fingerprint',source_package_fingerprint,
                    'contract_version',contract_version,'status',status,'payload',payload)
                    FROM v4_person_profile.import_batches WHERE import_batch_id=%s""",
                    (batch["import_batch_id"],), _json_value(batch), "ImportBatch",
                )
                for row in identities:
                    writes["person_identity_registry"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.person_identity_registry
                        (person_ref,canonical_name,historical_context,identity_fingerprint,
                         identity_status,semantic_version,idempotency_key,import_batch_id,payload)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (person_ref) DO NOTHING RETURNING 1""",
                        (
                            row["person_ref"], row["canonical_name"], row["historical_context"],
                            row["identity_fingerprint"], row["identity_status"],
                            row["semantic_version"], row["idempotency_key"],
                            row["import_batch_id"], Jsonb(row["payload"]),
                        ),
                        "SELECT payload FROM v4_person_profile.person_identity_registry WHERE person_ref=%s",
                        (row["person_ref"],), row["payload"], "PersonIdentity",
                    )
                for row in legacy_refs:
                    payload = _json_value(
                        {
                            key: value
                            for key, value in row.items()
                            if key != "import_batch_id"
                        }
                    )
                    writes["person_legacy_refs"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.person_legacy_refs
                        (legacy_ref_id,source_system,source_object_ref,source_identity_fingerprint,
                         person_ref,mapping_status,mapping_basis_refs,idempotency_key,import_batch_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (legacy_ref_id) DO NOTHING RETURNING 1""",
                        (
                            row["legacy_ref_id"], row["source_system"], row["source_object_ref"],
                            row["source_identity_fingerprint"], row["person_ref"],
                            row["mapping_status"], Jsonb(row["mapping_basis_refs"]),
                            row["idempotency_key"], row["import_batch_id"],
                        ),
                        """SELECT jsonb_build_object(
                        'legacy_ref_id',legacy_ref_id,'source_system',source_system,
                        'source_object_ref',source_object_ref,
                        'source_identity_fingerprint',source_identity_fingerprint,
                        'person_ref',person_ref,'mapping_status',mapping_status,
                        'mapping_basis_refs',mapping_basis_refs,
                        'idempotency_key',idempotency_key)
                        FROM v4_person_profile.person_legacy_refs WHERE legacy_ref_id=%s""",
                        (row["legacy_ref_id"],), payload, "PersonLegacyRef",
                    )
                for profile in profiles:
                    payload = _json_value(asdict(profile))
                    writes["person_profile_snapshots"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.person_profile_snapshots
                        (profile_ref,snapshot_version,person_ref,talent_grade,talent_grade_version,
                         talent_grade_confidence,talent_authority_consensus,talent_performance_support,
                         talent_evidence_coverage,capability_domains,negative_talent_class,
                         negative_talent_severity,negative_talent_version,source_profile_ref,
                         source_row_fingerprint,semantic_fingerprint,review_status,idempotency_key,
                         import_batch_id,payload)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (profile_ref,snapshot_version) DO NOTHING RETURNING 1""",
                        (
                            profile.profile_ref, profile.snapshot_version,
                            profile.canonical_person_ref, profile.talent_grade,
                            profile.talent_grade_version, profile.talent_grade_confidence,
                            profile.talent_authority_consensus, profile.talent_performance_support,
                            profile.talent_evidence_coverage, Jsonb(list(profile.capability_domains)),
                            profile.negative_talent_class, profile.negative_talent_severity,
                            profile.negative_talent_version, profile.source_profile_ref,
                            profile.source_row_fingerprint, profile.semantic_fingerprint,
                            profile.review_status,
                            f"person-profile:{profile.profile_ref}:{profile.snapshot_version}",
                            batch["import_batch_id"], Jsonb(payload),
                        ),
                        """SELECT payload FROM v4_person_profile.person_profile_snapshots
                        WHERE profile_ref=%s AND snapshot_version=%s""",
                        (profile.profile_ref, profile.snapshot_version), payload, "PersonProfileSnapshot",
                    )
                    for ref in profile.lineage_refs:
                        lineage = _lineage(ref)
                        lineage_payload = _json_value(lineage)
                        writes["person_profile_lineage"] += self._insert(
                            cursor, Jsonb,
                            """INSERT INTO v4_person_profile.person_profile_lineage
                            (profile_ref,snapshot_version,lineage_ref,lineage_kind,source_system,
                             source_ref,source_fingerprint,idempotency_key,payload)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (profile_ref,snapshot_version,lineage_ref)
                            DO NOTHING RETURNING 1""",
                            (
                                profile.profile_ref, profile.snapshot_version, ref,
                                lineage["lineage_kind"], lineage["source_system"],
                                lineage["source_ref"], lineage["source_fingerprint"],
                                "profile-lineage:" + _stable_hash(
                                    [profile.profile_ref, profile.snapshot_version, ref]
                                ), Jsonb(lineage_payload),
                            ),
                            """SELECT payload FROM v4_person_profile.person_profile_lineage
                            WHERE profile_ref=%s AND snapshot_version=%s AND lineage_ref=%s""",
                            (profile.profile_ref, profile.snapshot_version, ref),
                            lineage_payload, "PersonProfileLineage",
                        )
                for row in catalog_rows:
                    payload = row["payload"]
                    writes["person_profile_catalog"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.person_profile_catalog
                        (profile_ref,snapshot_version,person_ref,canonical_name,historical_context,
                         talent_grade,talent_grade_version,talent_grade_confidence,
                         talent_grade_basis,talent_authority_consensus,
                         talent_performance_support,talent_evidence_coverage,
                         negative_risk_status,negative_talent_class,negative_talent_severity,
                         negative_talent_basis,negative_talent_version,negative_talent_confidence,
                         negative_authority_consensus,negative_fact_support,
                         negative_evidence_coverage,capability_domains,
                         source_profile_ref,review_status,idempotency_key,import_batch_id,payload)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (profile_ref,snapshot_version) DO NOTHING RETURNING 1""",
                        (
                            row["profile_ref"], row["snapshot_version"], row["person_ref"],
                            row["canonical_name"], row["historical_context"],
                            row["talent_grade"], row["talent_grade_version"],
                            row["talent_grade_confidence"], row["talent_grade_basis"],
                            row["talent_authority_consensus"],
                            row["talent_performance_support"],
                            row["talent_evidence_coverage"], row["negative_risk_status"],
                            row["negative_talent_class"], row["negative_talent_severity"],
                            row["negative_talent_basis"], row["negative_talent_version"],
                            row["negative_talent_confidence"],
                            row["negative_authority_consensus"],
                            row["negative_fact_support"],
                            row["negative_evidence_coverage"], Jsonb(row["capability_domains"]),
                            row["source_profile_ref"], row["review_status"],
                            row["idempotency_key"], row["import_batch_id"], Jsonb(payload),
                        ),
                        """SELECT payload - 'import_batch_id'
                        FROM v4_person_profile.person_profile_catalog
                        WHERE profile_ref=%s AND snapshot_version=%s""",
                        (row["profile_ref"], row["snapshot_version"]),
                        payload, "PersonProfileCatalog",
                    )
                for window in windows:
                    payload = _json_value(asdict(window))
                    window_fingerprint = _stable_hash(payload)
                    writes["ruler_team_window_snapshots"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.ruler_team_window_snapshots
                        (window_ref,ruler_ref,window_start,window_end,date_precision,
                         window_policy_version,roster_version,profile_snapshot_version,
                         semantic_fingerprint,status,lineage,idempotency_key,import_batch_id,payload)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (window_ref,window_policy_version)
                        DO NOTHING RETURNING 1""",
                        (
                            window.window_ref, window.ruler_ref, window.start, window.end,
                            window.date_precision, window.window_policy_version,
                            window.roster_version, window.profile_snapshot_version,
                            window_fingerprint, window.status, Jsonb(dict(window.lineage)),
                            f"team-window:{window.window_ref}:{window.window_policy_version}",
                            batch["import_batch_id"], Jsonb(payload),
                        ),
                        """SELECT payload
                        FROM v4_person_profile.ruler_team_window_snapshots
                        WHERE window_ref=%s AND window_policy_version=%s""",
                        (window.window_ref, window.window_policy_version),
                        payload, "RulerTeamWindowSnapshot",
                    )
                    for member in window.members:
                        member_payload = _json_value(asdict(member))
                        member_fingerprint = _stable_hash(member_payload)
                        profile_version = profile_by_ref[member.profile_ref].snapshot_version
                        writes["ruler_team_window_members"] += self._insert(
                            cursor, Jsonb,
                            """INSERT INTO v4_person_profile.ruler_team_window_members
                            (window_ref,window_policy_version,person_ref,profile_ref,
                             profile_snapshot_version,active_from,
                             active_to,role_families,evidence_refs,semantic_fingerprint,idempotency_key)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (window_ref,window_policy_version,person_ref)
                            DO NOTHING RETURNING 1""",
                            (
                                window.window_ref, window.window_policy_version,
                                member.person_ref, member.profile_ref,
                                profile_version, member.active_from, member.active_to,
                                Jsonb(list(member.role_families)), Jsonb(list(member.evidence_refs)),
                                member_fingerprint,
                                "team-window-member:"
                                f"{window.window_ref}:{window.window_policy_version}:"
                                f"{member.person_ref}",
                            ),
                            """SELECT jsonb_build_object(
                            'active_from',active_from,'active_to',active_to,
                            'evidence_refs',evidence_refs,'person_ref',person_ref,
                            'profile_ref',profile_ref,'role_families',role_families)
                            FROM v4_person_profile.ruler_team_window_members
                            WHERE window_ref=%s AND window_policy_version=%s
                              AND person_ref=%s""",
                            (
                                window.window_ref,
                                window.window_policy_version,
                                member.person_ref,
                            ), member_payload,
                            "RulerTeamWindowMember",
                        )
        return PersonProfileImportResult(table_writes=writes)

    def import_catalog(
        self,
        profile_promotions: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        identity_crosswalk: Mapping[str, Any],
        import_batch_metadata: Mapping[str, Any],
        *,
        expected_profile_count: int | None = None,
    ) -> PersonProfileImportResult:
        """Insert the direct-readable projection for already frozen profiles."""

        packages = _promotion_packages(profile_promotions)
        profile_items = _profile_snapshots(packages)
        if expected_profile_count is not None and len(profile_items) != expected_profile_count:
            raise ValueError(
                f"expected {expected_profile_count} profiles, received {len(profile_items)}"
            )
        batch = _batch(
            import_batch_metadata,
            packages=packages,
            crosswalk=identity_crosswalk,
            window_promotion={"items": []},
        )
        identities, _ = _identity_and_legacy_rows(
            identity_crosswalk, profile_items, {}, batch["import_batch_id"]
        )
        catalog_rows = _profile_catalog_rows(
            profile_items, identities, batch["import_batch_id"]
        )
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("PostgresPersonProfileRepository requires psycopg") from exc

        writes = {"import_batches": 0, "person_profile_catalog": 0}
        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))
                writes["import_batches"] += self._insert(
                    cursor, Jsonb,
                    """INSERT INTO v4_person_profile.import_batches
                    (import_batch_id,idempotency_key,source_system,source_freeze_ref,
                     source_package_fingerprint,contract_version,status,payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (import_batch_id) DO NOTHING RETURNING 1""",
                    (
                        batch["import_batch_id"], batch["idempotency_key"],
                        batch["source_system"], batch["source_freeze_ref"],
                        batch["source_package_fingerprint"], batch["contract_version"],
                        batch["status"], Jsonb(batch["payload"]),
                    ),
                    """SELECT jsonb_build_object(
                    'import_batch_id',import_batch_id,'idempotency_key',idempotency_key,
                    'source_system',source_system,'source_freeze_ref',source_freeze_ref,
                    'source_package_fingerprint',source_package_fingerprint,
                    'contract_version',contract_version,'status',status,'payload',payload)
                    FROM v4_person_profile.import_batches WHERE import_batch_id=%s""",
                    (batch["import_batch_id"],), _json_value(batch), "ImportBatch",
                )
                for row in catalog_rows:
                    payload = row["payload"]
                    writes["person_profile_catalog"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.person_profile_catalog
                        (profile_ref,snapshot_version,person_ref,canonical_name,historical_context,
                         talent_grade,talent_grade_version,talent_grade_confidence,
                         talent_grade_basis,talent_authority_consensus,
                         talent_performance_support,talent_evidence_coverage,
                         negative_risk_status,negative_talent_class,negative_talent_severity,
                         negative_talent_basis,negative_talent_version,negative_talent_confidence,
                         negative_authority_consensus,negative_fact_support,
                         negative_evidence_coverage,capability_domains,
                         source_profile_ref,review_status,idempotency_key,import_batch_id,payload)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (profile_ref,snapshot_version) DO NOTHING RETURNING 1""",
                        (
                            row["profile_ref"], row["snapshot_version"], row["person_ref"],
                            row["canonical_name"], row["historical_context"],
                            row["talent_grade"], row["talent_grade_version"],
                            row["talent_grade_confidence"], row["talent_grade_basis"],
                            row["talent_authority_consensus"],
                            row["talent_performance_support"],
                            row["talent_evidence_coverage"], row["negative_risk_status"],
                            row["negative_talent_class"], row["negative_talent_severity"],
                            row["negative_talent_basis"], row["negative_talent_version"],
                            row["negative_talent_confidence"],
                            row["negative_authority_consensus"], row["negative_fact_support"],
                            row["negative_evidence_coverage"], Jsonb(row["capability_domains"]),
                            row["source_profile_ref"], row["review_status"],
                            row["idempotency_key"], row["import_batch_id"], Jsonb(payload),
                        ),
                        """SELECT payload - 'import_batch_id'
                        FROM v4_person_profile.person_profile_catalog
                        WHERE profile_ref=%s AND snapshot_version=%s""",
                        (row["profile_ref"], row["snapshot_version"]),
                        payload, "PersonProfileCatalog",
                    )
        return PersonProfileImportResult(table_writes=writes)

    def import_talent_grade_calibration(
        self,
        report: Mapping[str, Any],
        import_batch_metadata: Mapping[str, Any],
        *,
        expected_reviewed_count: int | None = None,
    ) -> PersonProfileImportResult:
        expected_counts = {
            "talent-grade-v6-calibration-v1": 94,
            "talent-grade-v7-important-calibration-v1": 157,
            "talent-grade-v8-final-calibration-v1": 74,
            "talent-grade-v9-high-tier-calibration-v1": 72,
            "talent-grade-v10-targeted-correction-v1": 2,
        }
        policy_version = str(report.get("policy_version") or "")
        if policy_version not in expected_counts:
            raise ValueError("unsupported talent calibration policy")
        if expected_reviewed_count is None:
            expected_reviewed_count = expected_counts[policy_version]
        items = _rows(report.get("items"), "talent calibration items")
        if len(items) != expected_reviewed_count:
            raise ValueError(
                f"expected {expected_reviewed_count} calibrations, received {len(items)}"
            )
        required_batch_fields = (
            "import_batch_id",
            "idempotency_key",
            "source_system",
            "source_freeze_ref",
            "contract_version",
        )
        batch = {
            field: _text(import_batch_metadata.get(field))
            for field in required_batch_fields
        }
        if any(not value for value in batch.values()):
            raise ValueError("talent calibration import batch metadata is incomplete")
        batch["source_package_fingerprint"] = _text(report.get("report_sha256"))
        if not _SHA256.fullmatch(batch["source_package_fingerprint"]):
            raise ValueError("talent calibration report fingerprint is invalid")
        batch["status"] = "applied"
        batch["payload"] = {
            "policy_version": report["policy_version"],
            "reviewed_profile_count": len(items),
            "report_sha256": report["report_sha256"],
            "metadata": _json_value(dict(import_batch_metadata.get("payload") or {})),
        }

        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("PostgresPersonProfileRepository requires psycopg") from exc

        writes = {"import_batches": 0, "talent_grade_calibrations": 0}
        with psycopg.connect(self._dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))
                writes["import_batches"] += self._insert(
                    cursor, Jsonb,
                    """INSERT INTO v4_person_profile.import_batches
                    (import_batch_id,idempotency_key,source_system,source_freeze_ref,
                     source_package_fingerprint,contract_version,status,payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (import_batch_id) DO NOTHING RETURNING 1""",
                    (
                        batch["import_batch_id"], batch["idempotency_key"],
                        batch["source_system"], batch["source_freeze_ref"],
                        batch["source_package_fingerprint"], batch["contract_version"],
                        batch["status"], Jsonb(batch["payload"]),
                    ),
                    """SELECT jsonb_build_object(
                    'import_batch_id',import_batch_id,'idempotency_key',idempotency_key,
                    'source_system',source_system,'source_freeze_ref',source_freeze_ref,
                    'source_package_fingerprint',source_package_fingerprint,
                    'contract_version',contract_version,'status',status,'payload',payload)
                    FROM v4_person_profile.import_batches WHERE import_batch_id=%s""",
                    (batch["import_batch_id"],), _json_value(batch), "ImportBatch",
                )
                for item in items:
                    payload = _json_value(dict(item))
                    writes["talent_grade_calibrations"] += self._insert(
                        cursor, Jsonb,
                        """INSERT INTO v4_person_profile.talent_grade_calibrations
                        (calibration_ref,person_ref,base_profile_ref,base_snapshot_version,
                         policy_version,original_grade,original_grade_version,calibrated_grade,
                         decision,gate_matrix,failure_codes,review_basis,source_basis,
                         semantic_fingerprint,review_status,idempotency_key,import_batch_id,payload)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (calibration_ref) DO NOTHING RETURNING 1""",
                        (
                            item["calibration_ref"], item["person_ref"],
                            item["base_profile_ref"], item["base_snapshot_version"],
                            report["policy_version"], item["original_grade"],
                            item["original_grade_version"], item["calibrated_grade"],
                            item["decision"], Jsonb(item["gate_matrix"]),
                            Jsonb(item["failure_codes"]), item["review_basis"],
                            item["source_basis"], item["semantic_fingerprint"],
                            item["review_status"],
                            "talent-calibration:" + item["calibration_ref"],
                            batch["import_batch_id"], Jsonb(payload),
                        ),
                        """SELECT payload
                        FROM v4_person_profile.talent_grade_calibrations
                        WHERE calibration_ref=%s""",
                        (item["calibration_ref"],), payload, "TalentGradeCalibration",
                    )
        return PersonProfileImportResult(table_writes=writes)

    @staticmethod
    def _insert(
        cursor: Any,
        jsonb_type: Any,
        insert_sql: str,
        insert_params: tuple[object, ...],
        select_sql: str,
        select_params: tuple[object, ...],
        expected_payload: object,
        label: str,
    ) -> int:
        del jsonb_type  # values are wrapped by the caller; kept for a uniform call contract
        cursor.execute(insert_sql, insert_params)
        inserted = cursor.fetchone() is not None
        if inserted:
            return 1
        cursor.execute(select_sql, select_params)
        row = cursor.fetchone()
        if row is None or _json_value(row[0]) != expected_payload:
            raise ValueError(f"{label} stable identity has conflicting content")
        return 0


def import_person_profiles_and_team_windows(
    dsn: str,
    profile_promotions: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    team_window_promotion: Mapping[str, Any],
    identity_crosswalk: Mapping[str, Any],
    import_batch_metadata: Mapping[str, Any],
    *,
    expected_profile_count: int | None = None,
    expected_window_count: int | None = None,
) -> PersonProfileImportResult:
    return PostgresPersonProfileRepository(dsn).import_promotions(
        profile_promotions,
        team_window_promotion,
        identity_crosswalk,
        import_batch_metadata,
        expected_profile_count=expected_profile_count,
        expected_window_count=expected_window_count,
    )


def import_frozen_person_profile_portfolio(
    dsn: str,
    profile_promotions: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    team_window_promotion: Mapping[str, Any],
    identity_crosswalk: Mapping[str, Any],
    import_batch_metadata: Mapping[str, Any],
) -> PersonProfileImportResult:
    return import_person_profiles_and_team_windows(
        dsn,
        profile_promotions,
        team_window_promotion,
        identity_crosswalk,
        import_batch_metadata,
        expected_profile_count=253,
        expected_window_count=12,
    )
