from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalPerson:
    person_id: str
    canonical_name: str
    historical_context: str
    identity_fingerprint: str
    identity_status: str = "accepted"
    semantic_version: int = 1


def identity_fingerprint(
    person_id: str,
    canonical_name: str,
    historical_context: str,
) -> str:
    payload = {
        "person_id": person_id,
        "canonical_name": canonical_name,
        "historical_context": historical_context,
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_person(
    person_id: str,
    canonical_name: str,
    historical_context: str,
) -> CanonicalPerson:
    return CanonicalPerson(
        person_id=person_id,
        canonical_name=canonical_name,
        historical_context=historical_context,
        identity_fingerprint=identity_fingerprint(
            person_id, canonical_name, historical_context
        ),
    )
