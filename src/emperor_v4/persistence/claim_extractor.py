from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.application.claim_extractor_service import CachedClaimExtractionResult


@dataclass(slots=True)
class InMemoryClaimExtractionRepository:
    records: dict[str, CachedClaimExtractionResult]

    def __init__(self) -> None:
        self.records = {}

    def get(self, idempotency_key: str) -> CachedClaimExtractionResult | None:
        return self.records.get(idempotency_key)

    def put(self, idempotency_key: str, input_fingerprint: str, response: Mapping[str, Any]) -> int:
        existing = self.records.get(idempotency_key)
        candidate = CachedClaimExtractionResult(input_fingerprint, dict(response))
        if existing is not None:
            if existing != candidate:
                raise ValueError("Claim extraction repository 幂等冲突")
            return 0
        self.records[idempotency_key] = candidate
        return 1


class ShadowJsonClaimExtractionRepository(InMemoryClaimExtractionRepository):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key, row in (payload.get("records") or {}).items():
                self.records[key] = CachedClaimExtractionResult(row["input_fingerprint"], row["response"])

    def put(self, idempotency_key: str, input_fingerprint: str, response: Mapping[str, Any]) -> int:
        writes = super().put(idempotency_key, input_fingerprint, response)
        if writes:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"schema_version": 1, "records": {
                key: {"input_fingerprint": row.input_fingerprint, "response": row.response}
                for key, row in sorted(self.records.items())
            }}
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return writes
