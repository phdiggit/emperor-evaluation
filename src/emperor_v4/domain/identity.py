from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalPerson:
    person_id: str
    canonical_name: str
    historical_context: str
    identity_fingerprint: str
    identity_status: str = "candidate"


def identity_fingerprint(
    canonical_name: str,
    historical_context: str,
    identity_discriminators: tuple[str, ...] = (),
) -> str:
    def normalized(value: str) -> str:
        return "".join(unicodedata.normalize("NFKC", value).split()).casefold()

    payload = {
        "canonical_name": normalized(canonical_name),
        "historical_context": normalized(historical_context),
        "identity_discriminators": sorted(
            normalized(value) for value in identity_discriminators
        ),
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
            canonical_name, historical_context
        ),
    )
