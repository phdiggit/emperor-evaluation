from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.application.source_cache_service import CachedSourceCacheResult


class InMemorySourceCacheRepository:
    def __init__(self) -> None:
        self._entries: dict[str, CachedSourceCacheResult] = {}

    def get(self, idempotency_key: str) -> CachedSourceCacheResult | None:
        return self._entries.get(idempotency_key)

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
    ) -> None:
        if idempotency_key in self._entries:
            raise ValueError("Source Cache repository 不得覆盖已有幂等结果")
        self._entries[idempotency_key] = CachedSourceCacheResult(
            input_fingerprint=input_fingerprint,
            response=deepcopy(dict(response)),
        )


class ShadowJsonSourceCacheRepository:
    """仅用于离线演示的文件状态；不是 V4 业务数据库。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "entries": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(
            payload.get("entries"), dict
        ):
            raise ValueError("Source Cache shadow state schema 无效")
        return payload

    def get(self, idempotency_key: str) -> CachedSourceCacheResult | None:
        row = self._read()["entries"].get(idempotency_key)
        if row is None:
            return None
        return CachedSourceCacheResult(
            input_fingerprint=str(row["input_fingerprint"]),
            response=row["response"],
        )

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
    ) -> None:
        payload = self._read()
        if idempotency_key in payload["entries"]:
            raise ValueError("Source Cache shadow state 不得覆盖已有幂等结果")
        payload["entries"][idempotency_key] = {
            "input_fingerprint": input_fingerprint,
            "response": response,
        }
        rendered = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8", newline="\n")
        temporary.replace(self.path)
