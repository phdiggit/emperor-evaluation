from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


MANIFEST_SCHEMA = "battle-registry-manifest-v1"
SHARD_SCHEMA = "battle-registry-shard-v1"
DEFAULT_BUCKET_COUNT = 24


def _partition(record: Mapping[str, Any]) -> str:
    return str(record.get("dynasty_partition") or "qin_tang")


def _bucket(record_id: str, bucket_count: int) -> int:
    return int(sha256(record_id.encode("utf-8")).hexdigest()[:8], 16) % bucket_count


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-tmp")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(path)


def write_battle_registry(
    manifest_path: Path,
    payload: Mapping[str, Any],
    *,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
) -> dict[str, Any]:
    """Write the canonical battle registry as a small manifest plus stable shards."""
    if bucket_count < 1:
        raise ValueError("battle registry bucket_count must be positive")
    records = [dict(row) for row in payload.get("records") or ()]
    record_ids = [str(row.get("war_event_id") or "") for row in records]
    if any(not value for value in record_ids):
        raise ValueError("公共战役登记存在缺失war_event_id的记录")
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("公共战役登记存在重复war_event_id")

    shard_root = manifest_path.with_suffix("")
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for record, record_id in zip(records, record_ids, strict=True):
        key = (_partition(record), _bucket(record_id, bucket_count))
        groups.setdefault(key, []).append(record)

    shard_entries: list[dict[str, Any]] = []
    expected_names: set[str] = set()
    for (partition, bucket), shard_records in sorted(groups.items()):
        filename = f"{partition}-{bucket:02d}.json"
        expected_names.add(filename)
        shard_path = shard_root / filename
        shard_payload = {
            "schema_version": SHARD_SCHEMA,
            "partition": partition,
            "bucket": bucket,
            "bucket_count": bucket_count,
            "record_count": len(shard_records),
            "records": shard_records,
        }
        shard_text = json.dumps(shard_payload, ensure_ascii=False, indent=2) + "\n"
        _atomic_write(shard_path, shard_text)
        shard_entries.append(
            {
                "path": shard_path.relative_to(manifest_path.parent).as_posix(),
                "partition": partition,
                "bucket": bucket,
                "record_count": len(shard_records),
            }
        )

    if shard_root.exists():
        for existing in shard_root.glob("*.json"):
            if existing.name not in expected_names:
                existing.unlink()

    payload_key_order = list(payload.keys())
    metadata = {key: value for key, value in payload.items() if key != "records"}
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "content_schema_version": str(payload.get("schema_version") or ""),
        "record_count": len(records),
        "bucket_count": bucket_count,
        "partition_counts": {
            partition: sum(
                entry["record_count"]
                for entry in shard_entries
                if entry["partition"] == partition
            )
            for partition in sorted({entry["partition"] for entry in shard_entries})
        },
        "payload_key_order": payload_key_order,
        "record_order": record_ids,
        "payload_metadata": metadata,
        "shards": shard_entries,
    }
    _atomic_write(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return manifest


def load_battle_registry(
    manifest_path: Path,
    *,
    partitions: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Load and verify the canonical registry; direct legacy monoliths are rejected."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(
            f"{manifest_path}不是{MANIFEST_SCHEMA}；公共战役消费者不得直接读取旧单体登记"
        )
    requested = None if partitions is None else {str(value) for value in partitions}
    available_partitions = {
        str(value) for value in (manifest.get("partition_counts") or {})
    }
    if requested is not None and not requested <= available_partitions:
        raise ValueError(
            "公共战役登记请求了不存在的分区: "
            f"{sorted(requested - available_partitions)}"
        )
    selected_entries = [
        entry
        for entry in manifest.get("shards") or ()
        if requested is None or str(entry.get("partition")) in requested
    ]
    records_by_id: dict[str, dict[str, Any]] = {}
    for entry in selected_entries:
        relative = Path(str(entry.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("公共战役登记shard路径越界")
        shard_path = manifest_path.parent / relative
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        if shard.get("schema_version") != SHARD_SCHEMA:
            raise ValueError(f"公共战役登记shard schema错误: {relative.as_posix()}")
        rows = [dict(row) for row in shard.get("records") or ()]
        if len(rows) != int(entry.get("record_count") or -1):
            raise ValueError(f"公共战役登记shard数量漂移: {relative.as_posix()}")
        for row in rows:
            record_id = str(row.get("war_event_id") or "")
            if not record_id or record_id in records_by_id:
                raise ValueError(f"公共战役登记shard记录标识缺失或重复: {record_id}")
            records_by_id[record_id] = row

    order = [str(value) for value in manifest.get("record_order") or ()]
    if requested is None:
        if len(records_by_id) != int(manifest.get("record_count") or -1):
            raise ValueError("公共战役登记总记录数漂移")
        if set(order) != set(records_by_id):
            raise ValueError("公共战役登记record_order与shard记录不一致")
    selected_order = [record_id for record_id in order if record_id in records_by_id]
    records = [records_by_id[record_id] for record_id in selected_order]

    metadata = dict(manifest.get("payload_metadata") or {})
    result: dict[str, Any] = {}
    for key in manifest.get("payload_key_order") or ():
        if key == "records":
            result[key] = records
        elif key in metadata:
            result[key] = metadata[key]
    for key, value in metadata.items():
        result.setdefault(key, value)
    result.setdefault("records", records)
    return result
