from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


MANIFEST_SCHEMA = "military-talent-registry-manifest-v1"
SHARD_SCHEMA = "military-talent-registry-shard-v1"
DEFAULT_BUCKET_COUNT = 16


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-tmp")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(path)


def write_talent_registry(
    manifest_path: Path,
    payload: Mapping[str, Any],
    *,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
) -> dict[str, Any]:
    if bucket_count < 1:
        raise ValueError("talent registry bucket_count must be positive")
    profiles = [dict(row) for row in payload.get("profiles") or ()]
    profile_ids = [str(row.get("profile_ref") or "") for row in profiles]
    if any(not value for value in profile_ids):
        raise ValueError("武将人才等级存在缺失profile_ref的记录")
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("武将人才等级存在重复profile_ref")

    groups: dict[int, list[dict[str, Any]]] = {}
    for profile, profile_id in zip(profiles, profile_ids, strict=True):
        bucket = int(sha256(profile_id.encode("utf-8")).hexdigest()[:8], 16) % bucket_count
        groups.setdefault(bucket, []).append(profile)

    shard_root = manifest_path.with_suffix("")
    entries: list[dict[str, Any]] = []
    expected_names: set[str] = set()
    for bucket, shard_profiles in sorted(groups.items()):
        filename = f"bucket-{bucket:02d}.json"
        expected_names.add(filename)
        shard_path = shard_root / filename
        shard_payload = {
            "schema_version": SHARD_SCHEMA,
            "bucket": bucket,
            "bucket_count": bucket_count,
            "profile_count": len(shard_profiles),
            "profiles": shard_profiles,
        }
        shard_text = json.dumps(shard_payload, ensure_ascii=False, indent=2) + "\n"
        _atomic_write(shard_path, shard_text)
        entries.append(
            {
                "path": shard_path.relative_to(manifest_path.parent).as_posix(),
                "bucket": bucket,
                "profile_count": len(shard_profiles),
            }
        )

    if shard_root.exists():
        for existing in shard_root.glob("*.json"):
            if existing.name not in expected_names:
                existing.unlink()

    key_order = list(payload.keys())
    metadata = {key: value for key, value in payload.items() if key != "profiles"}
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "content_schema_version": str(payload.get("schema_version") or ""),
        "profile_count": len(profiles),
        "bucket_count": bucket_count,
        "payload_key_order": key_order,
        "profile_order": profile_ids,
        "payload_metadata": metadata,
        "shards": entries,
    }
    _atomic_write(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return manifest


def load_talent_registry(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(
            f"{manifest_path}不是{MANIFEST_SCHEMA}；消费者不得直接读取旧单体人才登记"
        )
    profiles_by_id: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("shards") or ():
        relative = Path(str(entry.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("武将人才等级shard路径越界")
        shard_path = manifest_path.parent / relative
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        if shard.get("schema_version") != SHARD_SCHEMA:
            raise ValueError(f"武将人才等级shard schema错误: {relative.as_posix()}")
        rows = [dict(row) for row in shard.get("profiles") or ()]
        if len(rows) != int(entry.get("profile_count") or -1):
            raise ValueError(f"武将人才等级shard数量漂移: {relative.as_posix()}")
        for row in rows:
            profile_id = str(row.get("profile_ref") or "")
            if not profile_id or profile_id in profiles_by_id:
                raise ValueError(f"武将人才等级profile_ref缺失或重复: {profile_id}")
            profiles_by_id[profile_id] = row

    order = [str(value) for value in manifest.get("profile_order") or ()]
    if len(profiles_by_id) != int(manifest.get("profile_count") or -1):
        raise ValueError("武将人才等级总记录数漂移")
    if set(order) != set(profiles_by_id):
        raise ValueError("武将人才等级profile_order与shard记录不一致")
    profiles = [profiles_by_id[profile_id] for profile_id in order]
    metadata = dict(manifest.get("payload_metadata") or {})
    result: dict[str, Any] = {}
    for key in manifest.get("payload_key_order") or ():
        result[key] = profiles if key == "profiles" else metadata[key]
    return result
