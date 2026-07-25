from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


ASSERTION_EXTRACTION_CONTRACT_V2 = "assertion-extraction-contract-v2"


@dataclass(frozen=True, slots=True)
class ClaimExtractionRequest:
    request_id: str
    idempotency_key: str
    profile_code: str
    subject: Mapping[str, Any]
    passages: tuple[Mapping[str, Any], ...]
    requested_at: str

    def __post_init__(self) -> None:
        if not all((self.request_id, self.idempotency_key, self.profile_code, self.requested_at)):
            raise ValueError("ClaimExtractionRequest 缺少请求、幂等、profile 或时间")
        if not self.passages:
            raise ValueError("ClaimExtractionRequest passages 不得为空")
        refs = tuple(str(row.get("passage_id") or row.get("passage_code") or "") for row in self.passages)
        if any(not ref for ref in refs) or len(refs) != len(set(refs)):
            raise ValueError("ClaimExtractionRequest passage ref 必须非空且唯一")
