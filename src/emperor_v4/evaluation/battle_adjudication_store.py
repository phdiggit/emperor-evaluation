from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


MANIFEST_SCHEMA = "battle-parent-adjudication-manifest-v1"
SHARD_SCHEMA = "battle-parent-adjudication-shard-v1"
DEFAULT_BUCKET_COUNT = 8


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-tmp")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(path)


def write_battle_parent_adjudications(
    manifest_path: Path,
    payload: Mapping[str, Any],
    *,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
) -> dict[str, Any]:
    rows = [dict(row) for row in payload.get("adjudications") or ()]
    ids = [str(row.get("war_event_id") or "") for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("父战役合同裁决war_event_id缺失或重复")
    groups: dict[int, list[dict[str, Any]]] = {}
    for row, event_id in zip(rows, ids, strict=True):
        bucket = int(sha256(event_id.encode("utf-8")).hexdigest()[:8], 16) % bucket_count
        groups.setdefault(bucket, []).append(row)

    shard_root = manifest_path.with_suffix("")
    entries: list[dict[str, Any]] = []
    expected_names: set[str] = set()
    for bucket, shard_rows in sorted(groups.items()):
        filename = f"bucket-{bucket:02d}.json"
        expected_names.add(filename)
        shard_path = shard_root / filename
        shard = {
            "schema_version": SHARD_SCHEMA,
            "bucket": bucket,
            "bucket_count": bucket_count,
            "adjudication_count": len(shard_rows),
            "adjudications_fingerprint": _digest(shard_rows),
            "adjudications": shard_rows,
        }
        text = json.dumps(shard, ensure_ascii=False, indent=2) + "\n"
        _atomic_write(shard_path, text)
        entries.append({
            "path": shard_path.relative_to(manifest_path.parent).as_posix(),
            "bucket": bucket,
            "adjudication_count": len(shard_rows),
            "sha256": sha256(text.encode("utf-8")).hexdigest(),
            "adjudications_fingerprint": shard["adjudications_fingerprint"],
        })
    if shard_root.exists():
        for existing in shard_root.glob("*.json"):
            if existing.name not in expected_names:
                existing.unlink()

    key_order = list(payload.keys())
    metadata = {key: value for key, value in payload.items() if key != "adjudications"}
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "content_schema_version": str(payload.get("schema_version") or ""),
        "adjudication_count": len(rows),
        "bucket_count": bucket_count,
        "payload_key_order": key_order,
        "adjudication_order": ids,
        "payload_metadata": metadata,
        "shards": entries,
        "content_fingerprint": _digest(payload),
    }
    manifest["manifest_fingerprint"] = _digest(manifest)
    _atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def load_battle_parent_adjudications(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(f"{manifest_path}不是{MANIFEST_SCHEMA}；不得直接读取旧单体父战役裁决")
    if str(manifest.get("manifest_fingerprint") or "") != _digest(
        {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
    ):
        raise ValueError("父战役合同裁决manifest指纹漂移")
    rows_by_id: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("shards") or ():
        relative = Path(str(entry.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("父战役合同裁决shard路径越界")
        raw = (manifest_path.parent / relative).read_bytes()
        if sha256(raw).hexdigest() != str(entry.get("sha256") or ""):
            raise ValueError(f"父战役合同裁决shard字节指纹漂移: {relative.as_posix()}")
        shard = json.loads(raw.decode("utf-8"))
        rows = [dict(row) for row in shard.get("adjudications") or ()]
        if shard.get("schema_version") != SHARD_SCHEMA:
            raise ValueError(f"父战役合同裁决shard schema错误: {relative.as_posix()}")
        if len(rows) != int(entry.get("adjudication_count") or -1):
            raise ValueError(f"父战役合同裁决shard数量漂移: {relative.as_posix()}")
        if _digest(rows) != str(entry.get("adjudications_fingerprint") or ""):
            raise ValueError(f"父战役合同裁决shard语义指纹漂移: {relative.as_posix()}")
        for row in rows:
            event_id = str(row.get("war_event_id") or "")
            if not event_id or event_id in rows_by_id:
                raise ValueError(f"父战役合同裁决war_event_id缺失或重复: {event_id}")
            rows_by_id[event_id] = row
    order = [str(value) for value in manifest.get("adjudication_order") or ()]
    if set(order) != set(rows_by_id) or len(rows_by_id) != int(manifest.get("adjudication_count") or -1):
        raise ValueError("父战役合同裁决顺序或总数漂移")
    rows = [rows_by_id[event_id] for event_id in order]
    metadata = dict(manifest.get("payload_metadata") or {})
    result = {
        key: rows if key == "adjudications" else metadata[key]
        for key in manifest.get("payload_key_order") or ()
    }
    if _digest(result) != str(manifest.get("content_fingerprint") or ""):
        raise ValueError("父战役合同裁决重建内容指纹漂移")
    return result
