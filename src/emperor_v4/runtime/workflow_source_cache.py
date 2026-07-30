from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError
from uuid import uuid4

from opencc import OpenCC
import yaml

from emperor_v4.adapters.source_text_index import (
    build_local_source_index,
)
from emperor_v4.adapters.shidian import (
    discover_shidian_chapters,
    fetch_shidian_plaintext_batch,
)
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext_batch,
    list_wikisource_subpages,
)


CATALOG_SCHEMA = "workflow-source-cache-catalog-v1"
REQUEST_SCHEMA = "workflow-source-cache-request-v1"
IMPORT_SCHEMA = "workflow-source-cache-import-v1"
REPORT_SCHEMA = "workflow-source-cache-tick-v1"
_S2T = OpenCC("s2t")
_MATERIAL_KEYS = {
    "ruler_chronicles",
    "event_backsource",
    "person_biographies",
    "person_materials",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _token(value: str) -> str:
    cleaned = "".join(
        char if char.isascii() and (char.isalnum() or char in "-_") else "-"
        for char in value.upper()
    ).strip("-")
    return cleaned or sha256(value.encode("utf-8")).hexdigest()[:16].upper()


def _work_root(value: str) -> str:
    value = str(value).strip()
    for suffix in ("本纪", "本紀", "列传", "列傳", "载记", "載記"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return _S2T.convert(value)


def _walk_material_works(value: object, *, parent_key: str = "") -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk_material_works(item, parent_key=str(key))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if parent_key in _MATERIAL_KEYS:
            for item in value:
                if isinstance(item, str):
                    yield item
        else:
            for item in value:
                yield from _walk_material_works(item, parent_key=parent_key)


def _required_titles(work: Mapping[str, Any]) -> tuple[str, ...]:
    titles = [
        str(item).strip()
        for item in work.get("required_page_titles") or ()
        if str(item).strip()
    ]
    for row in work.get("required_page_ranges") or ():
        if not isinstance(row, Mapping):
            continue
        template = str(row.get("page_title_format") or "")
        first = int(row.get("first") or 0)
        last = int(row.get("last") or -1)
        if template and first > 0 and last >= first:
            titles.extend(template.format(volume=volume) for volume in range(first, last + 1))
    return tuple(dict.fromkeys(titles))


def _dynasty_tokens(project: Mapping[str, Any]) -> dict[str, str]:
    rows = (
        (project.get("dynasty_governance_catalog") or {}).get("dynasties") or {}
    )
    return {
        str(name): str(row.get("dynasty_token") or _token(str(name)))
        for name, row in rows.items()
        if isinstance(row, Mapping)
    }


def load_collections(
    catalog_path: Path, *, repo_root: Path, request_root: Path
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, Mapping) or catalog.get("schema_version") != CATALOG_SCHEMA:
        raise ValueError("workflow Source Cache catalog schema 不支持")
    source_catalogs = catalog.get("source_catalogs") or {}
    project = yaml.safe_load(
        (repo_root / str(source_catalogs["project"])).read_text(encoding="utf-8")
    )
    scope = yaml.safe_load(
        (repo_root / str(source_catalogs["search_scope"])).read_text(encoding="utf-8")
    )
    skip_fragments = tuple(
        str(item) for item in (catalog.get("provider") or {}).get("skip_name_fragments") or ()
    )
    collections: dict[str, dict[str, Any]] = {}

    def ensure(collection_id: str, dynasty: str, purpose: str) -> dict[str, Any]:
        return collections.setdefault(
            collection_id,
            {
                "collection_id": collection_id,
                "dynasty": dynasty,
                "purpose": purpose,
                "works": {},
                "priority": 20,
            },
        )

    if source_catalogs.get("derive_neutral_material_works"):
        for dynasty, row in (scope.get("dynasties") or {}).items():
            if not isinstance(row, Mapping):
                continue
            collection = ensure(
                "WORKFLOW-SHARED", "MULTI", "background_workflow_preload"
            )
            for work in _walk_material_works(row.get("neutral_material_strategy") or {}):
                root = _work_root(work)
                if root and not any(fragment in root for fragment in skip_fragments):
                    collection["works"].setdefault(
                        root, {"work_title": root, "root_title": root}
                    )

    if source_catalogs.get("derive_dynasty_governance_works"):
        governance = (
            (project.get("dynasty_governance_catalog") or {}).get("dynasties") or {}
        )
        for dynasty, row in governance.items():
            if not isinstance(row, Mapping):
                continue
            collection = ensure(
                "WORKFLOW-SHARED", "MULTI", "background_workflow_preload"
            )
            for work in row.get("source_works") or ():
                if not isinstance(work, Mapping):
                    continue
                root = _work_root(str(work.get("work") or ""))
                if root:
                    collection["works"].setdefault(
                        root, {"work_title": root, "root_title": root}
                    )

    for row in catalog.get("pinned_collections") or ():
        if not isinstance(row, Mapping):
            continue
        collection_id = str(row["collection_id"])
        collection = ensure(collection_id, "", str(row.get("purpose") or "pinned"))
        collection["priority"] = 0
        for work in row.get("works") or ():
            if not isinstance(work, Mapping):
                continue
            normalized = dict(work)
            normalized["work_title"] = str(work["work_title"])
            normalized["root_title"] = str(
                work.get("root_title") or _work_root(str(work["work_title"]))
            )
            collection["works"][normalized["work_title"]] = normalized

    if request_root.is_dir():
        for path in sorted(request_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != REQUEST_SCHEMA:
                raise ValueError(f"Source Cache request schema 不支持: {path}")
            collection_id = str(payload["collection_id"])
            collection = ensure(
                collection_id, str(payload.get("dynasty") or ""), "session_request"
            )
            collection["priority"] = min(int(collection["priority"]), 5)
            for work in payload.get("works") or ():
                if not isinstance(work, Mapping):
                    continue
                title = str(work["work_title"])
                current = collection["works"].setdefault(
                    title,
                    {
                        "work_title": title,
                        "root_title": str(
                            work.get("root_title") or _work_root(title)
                        ),
                    },
                )
                current["required_page_titles"] = list(
                    dict.fromkeys(
                        [
                            *_required_titles(current),
                            *_required_titles(work),
                        ]
                    )
                )

    normalized_collections = {}
    for collection_id, row in collections.items():
        normalized_collections[collection_id] = {
            **row,
            "works": tuple(row["works"].values()),
        }
    return dict(catalog), normalized_collections


def submit_source_cache_request(
    *, request_path: Path, request_root: Path
) -> dict[str, Any]:
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError("workflow Source Cache request schema 不支持")
    request_id = str(payload.get("request_id") or "").strip()
    collection_id = str(payload.get("collection_id") or "").strip()
    works = payload.get("works")
    if (
        not request_id
        or not collection_id
        or not isinstance(works, Sequence)
        or isinstance(works, (str, bytes))
        or not works
    ):
        raise ValueError("workflow Source Cache request 缺少 request_id、collection_id 或 works")
    for work in works:
        if not isinstance(work, Mapping) or not str(work.get("work_title") or "").strip():
            raise ValueError("workflow Source Cache request work 缺少 work_title")
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    target = request_root / f"{_token(request_id).lower()}.json"
    if target.is_file():
        if target.read_bytes() != encoded:
            raise ValueError(f"workflow Source Cache request_id 冲突: {request_id}")
        changed = False
    else:
        request_root.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(encoded)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        changed = True
    return {
        "schema_version": REQUEST_SCHEMA,
        "status": "submitted" if changed else "reused",
        "request_id": request_id,
        "collection_id": collection_id,
        "request_path": str(target),
        "network_request_count": 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "model_call_count": 0,
    }


def _carrier_routes(
    catalog: Mapping[str, Any], work: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    carriers = catalog.get("carriers") or {}
    configured = (carriers.get("works") or {}).get(str(work["work_title"]))
    routes = configured or carriers.get("defaults") or (
        {"carrier_id": "wikisource-zh", "provider_code": "wikisource"},
    )
    normalized = []
    for route in routes:
        if not isinstance(route, Mapping):
            raise ValueError("Source Cache carrier route 必须为对象")
        provider_code = str(route.get("provider_code") or "").strip()
        carrier_id = str(route.get("carrier_id") or "").strip()
        if not provider_code or not carrier_id:
            raise ValueError("Source Cache carrier route 缺少 carrier_id/provider_code")
        normalized.append({**work, **route})
    return tuple(normalized)


def _provider_code(route: Mapping[str, Any]) -> str:
    return str(route["provider_code"])


def _inventory_path(state_root: Path, route: Mapping[str, Any]) -> Path:
    identity = f"{route['carrier_id']}:{route['root_title']}"
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return state_root / "inventories" / f"{digest}.json"


def _page_path(state_root: Path, page_title: str) -> Path:
    digest = sha256(page_title.encode("utf-8")).hexdigest()
    return state_root / "pages" / f"{digest}.json"


def _read_seed_rows(
    index_root: Path,
    *,
    with_text: bool = False,
    work_roots: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for path in sorted(index_root.rglob("*.sqlite3")):
        if any(parent.name.startswith("workflow-") for parent in path.parents):
            continue
        connection = None
        try:
            connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            with connection:
                columns = (
                    "page_title, work_title, source_url, revision_ref, raw_text"
                    if with_text
                    else "page_title, work_title, source_url, revision_ref"
                )
                for row in connection.execute(f"SELECT {columns} FROM pages"):
                    item = {key: str(row[key] or "") for key in row.keys()}
                    if work_roots is not None and _work_root(item["work_title"]) not in work_roots:
                        continue
                    rows.setdefault(item["page_title"], item)
        except (OSError, sqlite3.Error):
            continue
        finally:
            if connection is not None:
                connection.close()
    return rows


def _page_catalog_path(state_root: Path) -> Path:
    return state_root / "page-catalog.json"


def _read_page_catalog(state_root: Path) -> dict[str, dict[str, str]]:
    path = _page_catalog_path(state_root)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(title): {str(key): str(value) for key, value in row.items()}
        for title, row in (payload.get("pages") or {}).items()
        if isinstance(row, Mapping)
    }


def _cached_rows(
    state_root: Path,
    *,
    with_text: bool = False,
    work_roots: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    rows = {}
    for title, metadata in _read_page_catalog(state_root).items():
        if work_roots is not None and _work_root(metadata["work_title"]) not in work_roots:
            continue
        row = {
            "page_title": title,
            "work_title": metadata["work_title"],
            "source_url": metadata["source_url"],
            "revision_ref": metadata["revision_ref"],
        }
        if with_text:
            payload = json.loads(
                (state_root / metadata["relative_path"]).read_text(encoding="utf-8")
            )
            row["raw_text"] = str(payload["raw_text"])
        rows[title] = row
    return rows


def _record_cached_pages(
    state_root: Path, snapshots: Sequence[tuple[str, Mapping[str, Any]]]
) -> None:
    pages = _read_page_catalog(state_root)
    for work_title, snapshot in snapshots:
        canonical_title = str(snapshot["canonical_title"])
        path = _page_path(state_root, canonical_title)
        pages[canonical_title] = {
            "work_title": work_title,
            "source_url": str(snapshot["canonical_url"]),
            "revision_ref": str(snapshot["revision_ref"]),
            "carrier_id": str(snapshot.get("carrier_id") or "legacy"),
            "content_hash": str(snapshot["content_hash"]),
            "relative_path": path.relative_to(state_root).as_posix(),
        }
    _atomic_json(
        _page_catalog_path(state_root),
        {
            "schema_version": "workflow-source-cache-page-catalog-v1",
            "pages": pages,
        },
    )


def import_source_cache_snapshots(
    *, import_path: Path, state_root: Path
) -> dict[str, Any]:
    payload = json.loads(import_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != IMPORT_SCHEMA:
        raise ValueError("workflow Source Cache import schema 不支持")
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, Sequence) or isinstance(snapshots, (str, bytes)):
        raise ValueError("workflow Source Cache import 缺少 snapshots")
    existing = _read_page_catalog(state_root)
    accepted: list[tuple[str, dict[str, Any]]] = []
    reused = 0
    for row in snapshots:
        if not isinstance(row, Mapping):
            raise ValueError("workflow Source Cache import snapshot 必须为对象")
        required = (
            "page_title",
            "work_title",
            "source_url",
            "revision_ref",
            "raw_text",
            "content_hash",
            "carrier_id",
        )
        missing = [key for key in required if not str(row.get(key) or "").strip()]
        if missing:
            raise ValueError(f"workflow Source Cache import snapshot 缺少字段: {missing}")
        raw_text = str(row["raw_text"])
        content_hash = sha256(raw_text.encode("utf-8")).hexdigest()
        if content_hash != str(row["content_hash"]):
            raise ValueError(f"workflow Source Cache import 正文 hash 不匹配: {row['page_title']}")
        page_title = str(row["page_title"])
        current = existing.get(page_title)
        if current is not None:
            current_payload = json.loads(
                (state_root / current["relative_path"]).read_text(encoding="utf-8")
            )
            if (
                str(current["revision_ref"]) != str(row["revision_ref"])
                or sha256(str(current_payload["raw_text"]).encode("utf-8")).hexdigest()
                != content_hash
            ):
                raise ValueError(f"workflow Source Cache import 页面身份冲突: {page_title}")
            reused += 1
            continue
        accepted.append(
            (
                str(row["work_title"]),
                {
                    "requested_title": page_title,
                    "canonical_title": page_title,
                    "canonical_url": str(row["source_url"]),
                    "revision_ref": str(row["revision_ref"]),
                    "retrieved_at": str(row.get("retrieved_at") or _now().isoformat()),
                    "raw_text": raw_text,
                    "content_hash": content_hash,
                    "carrier_id": str(row["carrier_id"]),
                },
            )
        )
    for _work_title, snapshot in accepted:
        _atomic_json(
            _page_path(state_root, str(snapshot["canonical_title"])), snapshot
        )
    _record_cached_pages(state_root, accepted)
    return {
        "schema_version": IMPORT_SCHEMA,
        "status": "imported" if accepted else "reused",
        "accepted_page_count": len(accepted),
        "reused_page_count": reused,
        "network_request_count": 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "model_call_count": 0,
    }


def _carrier_failure_path(state_root: Path, route: Mapping[str, Any]) -> Path:
    identity = f"{route['carrier_id']}:{route['root_title']}"
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return state_root / "carrier-failures" / f"{digest}.json"


def _carrier_retry_after(
    state_root: Path, route: Mapping[str, Any]
) -> datetime | None:
    path = _carrier_failure_path(state_root, route)
    if not path.is_file():
        return None
    value = str(json.loads(path.read_text(encoding="utf-8")).get("retry_after") or "")
    return datetime.fromisoformat(value) if value else None


def _write_carrier_failure(
    state_root: Path,
    *,
    route: Mapping[str, Any],
    error: Exception,
    seconds: int,
) -> None:
    _atomic_json(
        _carrier_failure_path(state_root, route),
        {
            "schema_version": "workflow-source-cache-carrier-failure-v1",
            "carrier_id": route["carrier_id"],
            "provider_code": route["provider_code"],
            "root_title": route["root_title"],
            "retry_after": (_now() + timedelta(seconds=seconds)).isoformat(),
            "error_type": type(error).__name__,
            "http_status": error.code if isinstance(error, HTTPError) else None,
        },
    )


def _work_inventory_state(
    *,
    catalog: Mapping[str, Any],
    work: Mapping[str, Any],
    state_root: Path,
) -> tuple[set[str], bool, list[tuple[dict[str, Any], Mapping[str, Any]]]]:
    discoverable: set[str] = set()
    inventories = []
    routes = _carrier_routes(catalog, work)
    required = set(_required_titles(work))
    for route in routes:
        path = _inventory_path(state_root, route)
        if not path.is_file():
            if required and required <= discoverable:
                break
            continue
        inventory = json.loads(path.read_text(encoding="utf-8"))
        inventories.append((route, inventory))
        discoverable.update(str(title) for title in inventory.get("page_titles") or ())
        if required and required <= discoverable:
            break
        if not required:
            break
    complete = bool(inventories) and (
        not required or required <= discoverable or len(inventories) == len(routes)
    )
    return discoverable, complete, inventories


def _discover_route(
    route: Mapping[str, Any],
    *,
    list_pages: Callable[..., tuple[str, ...]],
) -> tuple[tuple[str, ...], Mapping[str, Mapping[str, Any]]]:
    provider_code = _provider_code(route)
    if provider_code == "shidian":
        page_metadata = discover_shidian_chapters(
            catalog_url=str(route["catalog_url"]),
            work_title=str(route["work_title"]),
            chapter_name_contains=str(route["chapter_name_contains"]),
            first_volume=int(route["first_volume"]),
            last_volume=int(route["last_volume"]),
        )
        return tuple(page_metadata), page_metadata
    if provider_code == "wikisource":
        return tuple(list_pages(root_title=str(route["root_title"]))), {}
    raise ValueError(f"Source Cache 不支持 provider_code: {provider_code}")


def _fetch_route(
    route: Mapping[str, Any],
    *,
    page_titles: Sequence[str],
    inventory: Mapping[str, Any],
    fetch_pages: Callable[..., Mapping[str, WikisourcePageSnapshot]],
) -> Mapping[str, Any]:
    provider_code = _provider_code(route)
    if provider_code == "shidian":
        return fetch_shidian_plaintext_batch(
            page_titles=page_titles,
            page_metadata=inventory["page_metadata"],
            book_id=str(route["book_id"]),
            chapter_url_format=str(route["chapter_url_format"]),
        )
    if provider_code == "wikisource":
        return fetch_pages(page_titles=page_titles)
    raise ValueError(f"Source Cache 不支持 provider_code: {provider_code}")


def _build_collection(
    *,
    catalog: Mapping[str, Any],
    collection: Mapping[str, Any],
    rows: Mapping[str, Mapping[str, str]],
    index_root: Path,
    state_root: Path,
    force_rebuild: bool,
) -> dict[str, Any]:
    work_titles = {str(work["work_title"]) for work in collection["works"]}
    work_roots = {_work_root(title) for title in work_titles}
    selected_metadata = [
        dict(row)
        for row in rows.values()
        if _work_root(str(row["work_title"])) in work_roots
    ]
    target_root = index_root / f"workflow-{_token(str(collection['collection_id'])).lower()}-current"
    target = target_root / f"workflow-{_token(str(collection['collection_id'])).lower()}.sqlite3"
    current_path = target_root / "CURRENT.json"
    collection_fingerprint = sha256(
        json.dumps(
            {
                "collection_id": collection["collection_id"],
                "works": [
                    {
                        "work_title": work["work_title"],
                        "root_title": work["root_title"],
                        "required_page_titles": list(_required_titles(work)),
                    }
                    for work in collection["works"]
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    previous_fingerprint = None
    if current_path.is_file():
        previous_fingerprint = json.loads(
            current_path.read_text(encoding="utf-8")
        ).get("collection_fingerprint")
    available = set(rows)
    required = {
        title
        for work in collection["works"]
        for title in _required_titles(work)
    }
    inventory_complete = True
    carrier_missing: set[str] = set()
    pending: set[str] = set()
    discoverable: set[str] = set()
    carrier_status = []
    for work in collection["works"]:
        titles, work_complete, inventories = _work_inventory_state(
            catalog=catalog, work=work, state_root=state_root
        )
        inventory_complete = inventory_complete and work_complete
        discoverable.update(titles)
        work_required = set(_required_titles(work))
        if work_complete:
            carrier_missing.update(work_required - titles - available)
        pending.update((work_required & titles) - available)
        carrier_status.append(
            {
                "work_title": work["work_title"],
                "inventory_complete": work_complete,
                "discoverable_page_count": len(titles),
                "carriers_used": [
                    str(route["carrier_id"]) for route, _inventory in inventories
                ],
            }
        )
    preload_complete = inventory_complete and discoverable <= available
    publish_partial = int(collection["priority"]) <= 5
    built = None
    if selected_metadata and (publish_partial or preload_complete) and (
        force_rebuild
        or not target.is_file()
        or previous_fingerprint != collection_fingerprint
    ):
        full_rows = {
            **_read_seed_rows(
                index_root, with_text=True, work_roots=work_roots
            ),
            **_cached_rows(
                state_root, with_text=True, work_roots=work_roots
            ),
        }
        built = build_local_source_index(full_rows.values(), target)
    elif target.is_file():
        with sqlite3.connect(f"file:{target.resolve()}?mode=ro", uri=True) as connection:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        built = {
            "index_identity": metadata["index_identity"],
            "page_count": int(metadata["page_count"]),
        }
    report = {
        "schema_version": "workflow-source-cache-collection-v1",
        "collection_id": collection["collection_id"],
        "collection_fingerprint": collection_fingerprint,
        "purpose": collection["purpose"],
        "works": sorted(work_titles),
        "required_page_count": len(required),
        "cached_required_page_count": len(required & available),
        "carrier_missing_page_titles": sorted(carrier_missing),
        "pending_page_count": len(pending),
        "inventory_complete": inventory_complete,
        "carrier_status": carrier_status,
        "index": str(target) if built else None,
        "index_identity": built["index_identity"] if built else None,
        "page_count": built["page_count"] if built else 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "model_call_count": 0,
        "updated_at": _now().isoformat(),
    }
    _atomic_json(current_path, report)
    return report


def run_workflow_source_cache_once(
    *,
    catalog_path: Path,
    repo_root: Path,
    state_root: Path,
    request_root: Path,
    index_root: Path,
    list_pages: Callable[..., tuple[str, ...]] = list_wikisource_subpages,
    fetch_pages: Callable[..., Mapping[str, WikisourcePageSnapshot]] = fetch_wikisource_plaintext_batch,
) -> dict[str, Any]:
    catalog, collections = load_collections(
        catalog_path, repo_root=repo_root, request_root=request_root
    )
    provider = catalog.get("provider") or {}
    max_pages = int(provider.get("max_pages_per_tick") or 5)
    seed_rows = _read_seed_rows(index_root)
    cache_rows = _cached_rows(state_root)
    all_rows = {**seed_rows, **cache_rows}
    ordered = sorted(
        collections.values(),
        key=lambda row: (int(row["priority"]), str(row["collection_id"])),
    )
    network_requests = 0
    action = "idle"
    error_text = None
    changed_collection: str | None = None
    carrier_errors = []

    for collection in ordered:
        if action != "idle":
            break
        for work in collection["works"]:
            discoverable, complete, inventories = _work_inventory_state(
                catalog=catalog, work=work, state_root=state_root
            )
            known_carriers = {
                str(route["carrier_id"]) for route, _inventory in inventories
            }
            if not complete:
                for route in _carrier_routes(catalog, work):
                    if str(route["carrier_id"]) in known_carriers:
                        continue
                    retry_after = _carrier_retry_after(state_root, route)
                    if retry_after is not None and retry_after > _now():
                        continue
                    try:
                        titles, page_metadata = _discover_route(
                            route, list_pages=list_pages
                        )
                        network_requests += 1
                        _atomic_json(
                            _inventory_path(state_root, route),
                            {
                                "schema_version": "workflow-source-cache-inventory-v1",
                                "carrier_id": route["carrier_id"],
                                "provider_code": route["provider_code"],
                                "root_title": route["root_title"],
                                "page_titles": list(titles),
                                "page_metadata": page_metadata,
                                "page_count": len(titles),
                                "retrieved_at": _now().isoformat(),
                            },
                        )
                        action = "inventory_discovered"
                        changed_collection = str(collection["collection_id"])
                        break
                    except Exception as exc:
                        seconds = int(
                            provider.get(
                                "rate_limit_retry_after_seconds"
                                if isinstance(exc, HTTPError) and exc.code == 429
                                else "transient_retry_after_seconds"
                            )
                            or 1800
                        )
                        _write_carrier_failure(
                            state_root=state_root,
                            route=route,
                            error=exc,
                            seconds=seconds,
                        )
                        carrier_errors.append(
                            f"{route['carrier_id']}: {type(exc).__name__}: {exc}"
                        )
                if action != "idle":
                    break
        if action != "idle":
            break

        candidate_groups = []
        seen_titles: set[str] = set()
        for work in collection["works"]:
            _discoverable, _complete, inventories = _work_inventory_state(
                catalog=catalog, work=work, state_root=state_root
            )
            required = _required_titles(work)
            if not required:
                continue
            for route, inventory in inventories:
                inventory_titles = tuple(
                    str(title) for title in inventory.get("page_titles") or ()
                )
                ordered_titles = (
                    tuple(title for title in required if title in inventory_titles)
                    if required
                    else inventory_titles
                )
                titles = [
                    title
                    for title in ordered_titles
                    if title not in all_rows and title not in seen_titles
                ]
                if titles:
                    candidate_groups.append((work, route, inventory, titles))
                    seen_titles.update(titles)
        for work, route, inventory, titles in candidate_groups:
            retry_after = _carrier_retry_after(state_root, route)
            if retry_after is not None and retry_after > _now():
                continue
            page_titles = titles[:max_pages]
            try:
                snapshots = _fetch_route(
                    route,
                    page_titles=page_titles,
                    inventory=inventory,
                    fetch_pages=fetch_pages,
                )
                network_requests += 1
                normalized_snapshots = {}
                for requested_title, snapshot in snapshots.items():
                    if isinstance(snapshot, WikisourcePageSnapshot):
                        snapshot_payload = {
                            **asdict(snapshot),
                            "revision_ref": str(snapshot.revision_id),
                        }
                    else:
                        snapshot_payload = dict(snapshot)
                    payload = {
                        **snapshot_payload,
                        "work_title": str(work["work_title"]),
                        "carrier_id": str(route["carrier_id"]),
                    }
                    normalized_snapshots[requested_title] = payload
                    _atomic_json(
                        _page_path(state_root, str(payload["canonical_title"])),
                        payload,
                    )
                _record_cached_pages(
                    state_root,
                    [
                        (str(work["work_title"]), snapshot)
                        for snapshot in normalized_snapshots.values()
                    ],
                )
                cache_rows = _cached_rows(state_root)
                all_rows = {**seed_rows, **cache_rows}
                action = "pages_cached"
                changed_collection = str(collection["collection_id"])
                break
            except Exception as exc:
                seconds = int(
                    provider.get(
                        "rate_limit_retry_after_seconds"
                        if isinstance(exc, HTTPError) and exc.code == 429
                        else "transient_retry_after_seconds"
                    )
                    or 1800
                )
                _write_carrier_failure(
                    state_root=state_root,
                    route=route,
                    error=exc,
                    seconds=seconds,
                )
                carrier_errors.append(
                    f"{route['carrier_id']}: {type(exc).__name__}: {exc}"
                )
        if action != "idle":
            break

    if action == "idle" and carrier_errors:
        action = "carrier_retry_scheduled"
        error_text = "; ".join(carrier_errors)

    reports = [
        _build_collection(
            catalog=catalog,
            collection=collection,
            rows=all_rows,
            index_root=index_root,
            state_root=state_root,
            force_rebuild=str(collection["collection_id"]) == changed_collection,
        )
        for collection in ordered
    ]
    result = {
        "schema_version": REPORT_SCHEMA,
        "status": "ok" if error_text is None else "retryable_error",
        "action": action,
        "changed_collection": changed_collection,
        "collection_count": len(reports),
        "network_request_count": network_requests,
        "error": error_text,
        "carrier_errors": carrier_errors,
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "model_call_count": 0,
    }
    _atomic_json(state_root / "last-tick.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按工作流书目低速预热固定 revision 史源并发布本地索引"
    )
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--request-root", type=Path, required=True)
    parser.add_argument("--source-index-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_workflow_source_cache_once(
        catalog_path=args.catalog,
        repo_root=args.repo_root,
        state_root=args.state_root,
        request_root=args.request_root,
        index_root=args.source_index_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
