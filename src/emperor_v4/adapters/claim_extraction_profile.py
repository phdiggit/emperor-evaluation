from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


PROFILE_CONTRACT = "assertion-extraction-profile-v1"


@dataclass(frozen=True, slots=True)
class ClaimExtractionProfile:
    code: str
    output_contract: str
    purpose: str
    required_chains: tuple[str, ...]
    prohibitions: tuple[str, ...]


def load_claim_extraction_profile(path: Path, code: str) -> ClaimExtractionProfile:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("contract") != PROFILE_CONTRACT:
        raise ValueError("Claim extraction profile 根合同无效")
    row = (payload.get("profiles") or {}).get(code)
    if not isinstance(row, Mapping):
        raise ValueError(f"未知 Claim extraction profile: {code}")
    profile = ClaimExtractionProfile(
        code=code,
        output_contract=str(row.get("output_contract") or ""),
        purpose=str(row.get("purpose") or ""),
        required_chains=tuple(row.get("required_chains") or ()),
        prohibitions=tuple(row.get("prohibitions") or ()),
    )
    if profile.output_contract != "assertion-extraction-contract-v2" or not profile.purpose or not profile.prohibitions:
        raise ValueError("Claim extraction profile 缺少 v2 输出合同、目的或禁止项")
    return profile


def render_claim_extraction_request(
    *, profile: ClaimExtractionProfile, subject: Mapping[str, Any],
    passages: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    if not passages or any(not str(item.get("passage_id") or item.get("passage_code") or "") for item in passages):
        raise ValueError("Claim extraction request 必须包含具名 passage")
    body = {
        "contract": profile.output_contract,
        "profile_code": profile.code,
        "purpose": profile.purpose,
        "required_chains": list(profile.required_chains),
        "prohibitions": list(profile.prohibitions),
        "subject": dict(subject),
        "passages": [dict(item) for item in passages],
    }
    fingerprint = sha256(json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    return {**body, "input_fingerprint": fingerprint}
