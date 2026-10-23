from __future__ import annotations
from emperor_v4.json_format import json_text

import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterable, Mapping


ROUTER_SCHEMA = "formal-json-polity-router-v1"
SHARD_SCHEMA = "formal-json-polity-shard-v1"
_READ_SESSION: ContextVar[dict | None] = ContextVar("formal_json_read_session", default=None)


@contextmanager
def json_read_session():
    """Share file text within one operation, never across operations.

    Each parse returns private values. File signatures invalidate entries after a
    patch, including edits made outside write_json. Nested verifiers share the
    outer session; nothing is persisted on disk.
    """
    if _READ_SESSION.get() is not None:
        yield
        return
    token = _READ_SESSION.set({})
    try:
        yield
    finally:
        _READ_SESSION.reset(token)


def _read_json(path: Path) -> Any:
    session = _READ_SESSION.get()
    if session is None:
        return json.loads(path.read_text(encoding="utf-8"))
    key = path.resolve()
    stat = key.stat()
    signature = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    cached = session.get(key)
    if cached is None or cached[0] != signature:
        cached = (signature, key.read_text(encoding="utf-8"))
        session[key] = cached
    # The C JSON decoder is faster than deepcopy for these nested evidence
    # payloads and still prevents a builder mutating another caller's snapshot.
    return json.loads(cached[1])


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    content = (json_text(payload)).encode("utf-8")
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.write-tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _safe_route_name(value: str) -> str:
    route = value.strip()
    if not route or route in {".", ".."}:
        raise ValueError("正式结算朝代路由为空")
    if any(character in route for character in '<>:"/\\|?*'):
        raise ValueError(f"正式结算朝代路由不能作为文件名: {route}")
    return route


def _record_polity(
    record: Mapping[str, Any],
    ruler_polities: Mapping[str, str],
) -> str | None:
    ruler_id = str(record.get("ruler_id") or "").strip()
    canonical = str(ruler_polities.get(ruler_id) or "").strip()
    if canonical:
        return canonical
    return str(record.get("polity") or "").strip() or None


def write_polity_routed_json(
    manifest_path: Path,
    payload: Mapping[str, Any],
    *,
    ruler_polities: Mapping[str, str],
) -> dict[str, Any]:
    """Replace one monolithic formal JSON payload with polity-routed shards.

    Every top-level object-array whose rows can all be assigned to a polity is
    routed. Other metadata and small cross-polity arrays stay in the manifest.
    Original array positions are stored in each shard so a full load recreates
    the exact logical payload and ordering.
    """

    routed: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
    metadata: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
            rows: list[tuple[int, str, dict[str, Any]]] = []
            for position, row in enumerate(value):
                polity = _record_polity(row, ruler_polities)
                if polity is None:
                    rows = []
                    break
                rows.append((position, _safe_route_name(polity), dict(row)))
            if rows:
                routed[key] = rows
                continue
        metadata[key] = value

    if not routed:
        raise ValueError(f"{manifest_path}没有可按朝代路由的顶层记录数组")

    shard_root = manifest_path.with_suffix("")
    by_polity: dict[str, dict[str, dict[str, Any]]] = {}
    for collection, rows in routed.items():
        for position, polity, row in rows:
            collection_payload = by_polity.setdefault(polity, {}).setdefault(
                collection,
                {"positions": [], "records": []},
            )
            collection_payload["positions"].append(position)
            collection_payload["records"].append(row)

    expected_names: set[str] = set()
    routes: list[dict[str, Any]] = []
    for polity in sorted(by_polity):
        filename = f"{polity}.json"
        expected_names.add(filename)
        shard_path = shard_root / filename
        collections = by_polity[polity]
        shard_payload = {
            "schema_version": SHARD_SCHEMA,
            "polity": polity,
            "collections": collections,
        }
        from .formal_reading_texts import C_SCHEMA, FINANCE_SCHEMAS, compact_reading_texts
        if payload.get('schema_id') == C_SCHEMA:
            shard_payload = compact_reading_texts(shard_payload)
        elif payload.get('schema_id') in FINANCE_SCHEMAS:
            fields = sorted({key for block in collections.values() for row in block['records']
                             for key in row if key.startswith('public_')})
            if fields:
                shard_payload = compact_reading_texts(shard_payload, fields=fields)
        _atomic_write(shard_path, shard_payload)
        routes.append(
            {
                "polity": polity,
                "path": shard_path.relative_to(manifest_path.parent).as_posix(),
                "collection_counts": {
                    key: len(value["records"])
                    for key, value in collections.items()
                },
            }
        )

    if shard_root.exists():
        for existing in shard_root.glob("*.json"):
            if existing.name not in expected_names:
                existing.unlink()

    manifest = {
        "schema_version": ROUTER_SCHEMA,
        "route_key": "polity",
        "content_schema_version": str(payload.get("schema_version") or ""),
        "payload_key_order": list(payload.keys()),
        "payload_metadata": metadata,
        "collections": {
            key: {"record_count": len(rows)} for key, rows in routed.items()
        },
        "routes": routes,
    }
    _atomic_write(manifest_path, manifest)
    return manifest


def load_json(path: Path, *, polities: Iterable[str] | None = None) -> Any:
    """Load logical JSON, reconstructing formal routes and retained unit tables."""

    raw = _read_json(path)
    if isinstance(raw, dict):
        from .cost_registry_storage import SHARD_SCHEMA as COST_SHARD_SCHEMA, expand_shard as expand_cost_shard
        if raw.get('schema_version') == COST_SHARD_SCHEMA:
            return expand_cost_shard(raw)
        from .profile_unit_tables import TABLE_SCHEMAS, MARKER, expand_unit_table
        if raw.get('schema_version') in TABLE_SCHEMAS or MARKER in raw:
            return expand_unit_table(raw)
    if not isinstance(raw, dict) or raw.get("schema_version") != ROUTER_SCHEMA:
        return raw
    return _load_router(path, raw, polities=polities)


def load_ruler_polities(workspace_root: Path) -> dict[str, str]:
    pool_path = workspace_root / "config/common/canonical-ruler-pool.json"
    pool = _read_json(pool_path)
    result: dict[str, str] = {}
    for row in pool.get("records") or ():
        polity = str(row.get("polity") or "").strip()
        if not polity:
            continue
        identifiers = {str(row.get("ruler_id") or "").strip()}
        identifiers.update(
            str(value).strip()
            for value in (row.get("source_item_ids") or {}).values()
            if value
        )
        identifiers.update(
            str(value).strip()
            for value in (row.get("identity_resolution") or {}).get("legacy_id_refs") or ()
            if value
        )
        for identifier in identifiers - {""}:
            previous = result.setdefault(identifier, polity)
            if previous != polity:
                raise ValueError(f"人物ID跨朝代映射冲突: {identifier}={previous}/{polity}")
    for row in pool.get("first_item_outside_candidate_pool") or ():
        if row.get("ruler_id") and row.get("polity"):
            result[str(row["ruler_id"])] = str(row["polity"])
    return result


def write_json(
    path: Path,
    payload: Mapping[str, Any],
    *,
    ruler_polities: Mapping[str, str] | None = None,
    route: bool | None = None,
) -> None:
    """Write JSON, preserving an existing polity router unless told otherwise."""

    should_route = route
    if should_route is None and path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        should_route = (
            isinstance(current, dict)
            and current.get("schema_version") == ROUTER_SCHEMA
        )
    if should_route:
        if ruler_polities is None:
            raise ValueError("写入按朝代路由的正式JSON时必须提供ruler_polities")
        write_polity_routed_json(path, payload, ruler_polities=ruler_polities)
    else:
        from .cost_registry_storage import SHARD_SCHEMA as COST_SHARD_SCHEMA, compact_shard as compact_cost_shard
        if payload.get('schema_version') == COST_SHARD_SCHEMA:
            payload = compact_cost_shard(payload)
        from .profile_unit_tables import TABLE_SCHEMAS, M4_SCHEMA, compact_unit_table
        if payload.get('schema_version') in TABLE_SCHEMAS:
            payload = compact_unit_table(dict(payload),
                                         list_columns=('source_refs',) if payload.get('schema_version') == M4_SCHEMA else ())
        _atomic_write(path, payload)


def _load_router(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    *,
    polities: Iterable[str] | None,
) -> dict[str, Any]:
    requested = None if polities is None else {_safe_route_name(str(value)) for value in polities}
    routes = list(manifest.get("routes") or ())
    available = {str(route.get("polity") or "") for route in routes}
    if requested is not None and not requested <= available:
        raise ValueError(f"正式结算请求了不存在的朝代路由: {sorted(requested - available)}")

    collection_specs = dict(manifest.get("collections") or {})
    positioned: dict[str, dict[int, dict[str, Any]]] = {
        key: {} for key in collection_specs
    }
    for route in routes:
        polity = str(route.get("polity") or "")
        if requested is not None and polity not in requested:
            continue
        relative = Path(str(route.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("正式结算分片路径越界")
        shard = _read_json(manifest_path.parent / relative)
        if shard.get("schema_version") != SHARD_SCHEMA:
            raise ValueError(f"正式结算分片schema错误: {relative.as_posix()}")
        if shard.get("polity") != polity:
            raise ValueError(f"正式结算分片朝代漂移: {relative.as_posix()}")
        from .formal_reading_texts import C_SCHEMA, FINANCE_SCHEMAS, MARKER, CATALOG, FIELDS, expand_reading_texts
        if ((manifest.get('payload_metadata') or {}).get('schema_id') in FINANCE_SCHEMAS | {C_SCHEMA}
                or MARKER in shard or CATALOG in shard or FIELDS in shard):
            shard = expand_reading_texts(shard)
        shard_collections = dict(shard.get("collections") or {})
        expected_counts = dict(route.get("collection_counts") or {})
        actual_counts: dict[str, int] = {}
        for key, block in shard_collections.items():
            positions = list(block.get("positions") or ())
            records = list(block.get("records") or ())
            if len(positions) != len(records):
                raise ValueError(f"正式结算分片位置与记录数不一致: {relative.as_posix()}#{key}")
            actual_counts[key] = len(records)
            target = positioned.setdefault(key, {})
            for position, record in zip(positions, records, strict=True):
                index = int(position)
                if index in target:
                    raise ValueError(f"正式结算分片记录位置重复: {relative.as_posix()}#{key}[{index}]")
                target[index] = dict(record)
        if actual_counts != {str(key): int(value) for key, value in expected_counts.items()}:
            raise ValueError(f"正式结算分片计数漂移: {relative.as_posix()}")

    metadata = dict(manifest.get("payload_metadata") or {})
    result: dict[str, Any] = {}
    for key in manifest.get("payload_key_order") or ():
        if key in collection_specs:
            rows = positioned.get(str(key), {})
            if requested is None:
                expected = int(collection_specs[key].get("record_count") or 0)
                if set(rows) != set(range(expected)):
                    raise ValueError(f"正式结算分片覆盖不完整: {key}")
            result[str(key)] = [rows[index] for index in sorted(rows)]
        elif key in metadata:
            result[str(key)] = metadata[key]
    for key, value in metadata.items():
        result.setdefault(key, value)
    return result
