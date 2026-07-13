from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.application.source_cache_service import CachedSourceCacheResult
from emperor_v4.application.source_cache_service import source_content_version
from emperor_v4.contracts.source import SourceRevisionContent


class InMemorySourceCacheRepository:
    def __init__(self) -> None:
        self._entries: dict[str, CachedSourceCacheResult] = {}
        self._revisions: dict[tuple[str, str], SourceRevisionContent] = {}

    def get(self, idempotency_key: str) -> CachedSourceCacheResult | None:
        return self._entries.get(idempotency_key)

    def put(
        self,
        idempotency_key: str,
        input_fingerprint: str,
        response: Mapping[str, Any],
        source_revisions: Mapping[str, SourceRevisionContent],
    ) -> int:
        if idempotency_key in self._entries:
            raise ValueError("Source Cache repository 不得覆盖已有幂等结果")
        self._entries[idempotency_key] = CachedSourceCacheResult(
            input_fingerprint=input_fingerprint,
            response=deepcopy(dict(response)),
        )
        for document_id, revision in source_revisions.items():
            key = (document_id, source_content_version(revision))
            existing = self._revisions.setdefault(key, revision)
            if existing != revision:
                raise ValueError("Source Cache repository revision identity 冲突")
        return 1

    def get_revision(
        self,
        document_cache_id: str,
        content_version: str,
    ) -> SourceRevisionContent | None:
        return self._revisions.get((document_cache_id, content_version))


class ShadowJsonSourceCacheRepository:
    """仅用于离线演示的文件状态；不是 V4 业务数据库。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 2, "entries": {}, "source_revisions": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") != 2
            or not isinstance(payload.get("entries"), dict)
            or not isinstance(payload.get("source_revisions"), dict)
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
        source_revisions: Mapping[str, SourceRevisionContent],
    ) -> int:
        payload = self._read()
        if idempotency_key in payload["entries"]:
            raise ValueError("Source Cache shadow state 不得覆盖已有幂等结果")
        payload["entries"][idempotency_key] = {
            "input_fingerprint": input_fingerprint,
            "response": response,
        }
        for document_id, revision in source_revisions.items():
            content_version = source_content_version(revision)
            key = f"{document_id}@{content_version}"
            revision_payload = asdict(revision)
            existing = payload["source_revisions"].setdefault(
                key,
                revision_payload,
            )
            if existing != revision_payload:
                raise ValueError("Source Cache shadow revision identity 冲突")
        rendered = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8", newline="\n")
        temporary.replace(self.path)
        return 1

    def get_revision(
        self,
        document_cache_id: str,
        content_version: str,
    ) -> SourceRevisionContent | None:
        row = self._read()["source_revisions"].get(
            f"{document_cache_id}@{content_version}"
        )
        return SourceRevisionContent(**row) if row is not None else None
