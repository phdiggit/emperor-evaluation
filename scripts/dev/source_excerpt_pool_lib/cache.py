from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import psycopg
import yaml

from .common import (
    CACHE_SCHEMA_VERSION,
    DEFAULT_CACHE_BACKEND,
    DEFAULT_CACHE_DSN_ENV,
    DEFAULT_CACHE_SCHEMA,
    DEFAULT_USER_AGENT,
    PROJECT_CONFIG_PATH,
    ExcerptPoolError,
    TimeBudgetExceeded,
    cache_key,
    quote_pg_identifier,
    require_pg_identifier,
    resolve_dsn,
    resolve_repo_path,
)


@dataclass
class ApiCache:
    cache_dir: Path
    enabled: bool = True
    refresh: bool = False
    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def _path_for(self, *, stage: str, url: str) -> Path:
        safe_stage = re.sub(r"[^A-Za-z0-9_.-]+", "_", stage or "api").strip("_") or "api"
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / safe_stage / f"{digest}.json"

    def read(self, *, stage: str, label: str, url: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if self.refresh:
            self.misses += 1
            return None
        path = self._path_for(stage=stage, url=url)
        if not path.exists():
            self.misses += 1
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(envelope, dict):
                raise ExcerptPoolError("cache envelope is not an object")
            payload = envelope.get("payload")
            if not isinstance(payload, dict):
                raise ExcerptPoolError("cache payload is not an object")
        except Exception as exc:
            self.errors.append({"stage": stage, "label": label, "path": str(path), "error": repr(exc)})
            self.misses += 1
            return None
        self.hits += 1
        return payload

    def write(self, *, stage: str, label: str, url: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path_for(stage=stage, url=url)
        envelope = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cached_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "stage": stage,
            "label": label,
            "url": url,
            "payload": payload,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temp_path.replace(path)
            self.writes += 1
        except Exception as exc:
            self.errors.append({"stage": stage, "label": label, "path": str(path), "error": repr(exc)})

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cache_dir": str(self.cache_dir),
            "refresh": self.refresh,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "errors": list(self.errors),
        }


@dataclass
class PageTextCache:
    cache_dir: Path
    enabled: bool = True
    refresh: bool = False
    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def _paths_for(self, title: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(title.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.txt", self.cache_dir / f"{digest}.json"

    def read(self, *, title: str) -> str | None:
        if not self.enabled:
            return None
        if self.refresh:
            self.misses += 1
            return None
        text_path, _meta_path = self._paths_for(title)
        if not text_path.exists():
            self.misses += 1
            return None
        try:
            text = text_path.read_text(encoding="utf-8")
        except Exception as exc:
            self.errors.append({"title": title, "path": str(text_path), "error": repr(exc)})
            self.misses += 1
            return None
        self.hits += 1
        return text

    def write(self, *, title: str, page_url: str, text: str) -> None:
        if not self.enabled:
            return
        text_path, meta_path = self._paths_for(title)
        metadata = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cached_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "title": title,
            "page_url": page_url,
            "text_path": text_path.name,
        }
        try:
            text_path.parent.mkdir(parents=True, exist_ok=True)
            temp_text_path = text_path.with_name(text_path.name + ".tmp")
            temp_meta_path = meta_path.with_name(meta_path.name + ".tmp")
            temp_text_path.write_text(text, encoding="utf-8")
            temp_meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temp_text_path.replace(text_path)
            temp_meta_path.replace(meta_path)
            self.writes += 1
        except Exception as exc:
            self.errors.append({"title": title, "path": str(text_path), "error": repr(exc)})

    def iter_pages(self) -> Iterable[tuple[str, str]]:
        if not self.enabled or self.refresh:
            return
        for meta_path in sorted(self.cache_dir.glob("*.json")):
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                if not isinstance(metadata, dict):
                    raise ExcerptPoolError("page cache metadata is not an object")
                title = str(metadata.get("title") or "")
                text_name = str(metadata.get("text_path") or meta_path.with_suffix(".txt").name)
                text_path = self.cache_dir / text_name
                if not title:
                    raise ExcerptPoolError("page cache title is empty")
                if not text_path.exists():
                    raise ExcerptPoolError(f"page cache text missing: {text_path.name}")
                yield title, text_path.read_text(encoding="utf-8")
            except Exception as exc:
                self.errors.append({"path": str(meta_path), "error": repr(exc)})

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cache_dir": str(self.cache_dir),
            "refresh": self.refresh,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "errors": list(self.errors),
        }


@dataclass
class PostgresCacheStore:
    dsn_env: str = DEFAULT_CACHE_DSN_ENV
    schema: str = DEFAULT_CACHE_SCHEMA
    errors: list[dict[str, str]] = field(default_factory=list)
    _conn: Any = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.schema = require_pg_identifier(self.schema, label="cache.schema")

    @property
    def api_table(self) -> str:
        return f"{quote_pg_identifier(self.schema)}.wikisource_api_cache"

    @property
    def page_table(self) -> str:
        return f"{quote_pg_identifier(self.schema)}.wikisource_page_cache"

    def connection(self) -> Any:
        if self._conn is None or getattr(self._conn, "closed", False):
            self._conn = psycopg.connect(resolve_dsn(self.dsn_env))
            self._conn.autocommit = True
        if not self._initialized:
            self.ensure_schema()
        return self._conn

    def ensure_schema(self) -> None:
        conn = self._conn
        if conn is None:
            conn = psycopg.connect(resolve_dsn(self.dsn_env))
            conn.autocommit = True
            self._conn = conn
        schema = quote_pg_identifier(self.schema)
        with conn.cursor() as cur:
            cur.execute(f"create schema if not exists {schema}")
            cur.execute(
                f"""
                create table if not exists {self.api_table} (
                    stage text not null,
                    cache_key text not null,
                    url text not null,
                    label text not null default '',
                    payload_json jsonb not null,
                    schema_version integer not null,
                    cached_at timestamptz not null default now(),
                    updated_at timestamptz not null default now(),
                    last_hit_at timestamptz,
                    hit_count bigint not null default 0,
                    primary key (stage, cache_key)
                )
                """
            )
            cur.execute(
                f"""
                create index if not exists wikisource_api_cache_url_idx
                  on {self.api_table} (url)
                """
            )
            cur.execute(
                f"""
                create table if not exists {self.page_table} (
                    title text primary key,
                    page_url text not null,
                    plain_text text not null,
                    schema_version integer not null,
                    cached_at timestamptz not null default now(),
                    updated_at timestamptz not null default now(),
                    last_hit_at timestamptz,
                    hit_count bigint not null default 0
                )
                """
            )
        self._initialized = True

    def close(self) -> None:
        if self._conn is not None and not getattr(self._conn, "closed", False):
            self._conn.close()

    def record_error(self, *, operation: str, label: str, error: BaseException) -> None:
        self.errors.append({"operation": operation, "label": label, "error": repr(error)})


def _json_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ExcerptPoolError("cached PostgreSQL JSON payload is not an object")


@dataclass
class PostgresApiCache:
    store: PostgresCacheStore
    enabled: bool = True
    refresh: bool = False
    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def read(self, *, stage: str, label: str, url: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if self.refresh:
            self.misses += 1
            return None
        key = cache_key(url)
        try:
            with self.store.connection().cursor() as cur:
                cur.execute(
                    f"select payload_json from {self.store.api_table} where stage = %s and cache_key = %s",
                    (stage, key),
                )
                row = cur.fetchone()
                if row is None:
                    self.misses += 1
                    return None
                cur.execute(
                    f"""
                    update {self.store.api_table}
                       set last_hit_at = now(),
                           hit_count = hit_count + 1
                     where stage = %s and cache_key = %s
                    """,
                    (stage, key),
                )
        except Exception as exc:
            self.errors.append({"stage": stage, "label": label, "url": url, "error": repr(exc)})
            self.store.record_error(operation="api_read", label=label, error=exc)
            self.misses += 1
            return None
        self.hits += 1
        return _json_payload(row[0])

    def write(self, *, stage: str, label: str, url: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        key = cache_key(url)
        try:
            with self.store.connection().cursor() as cur:
                cur.execute(
                    f"""
                    insert into {self.store.api_table} (
                        stage, cache_key, url, label, payload_json, schema_version
                    )
                    values (%s, %s, %s, %s, %s::jsonb, %s)
                    on conflict (stage, cache_key) do update set
                        url = excluded.url,
                        label = excluded.label,
                        payload_json = excluded.payload_json,
                        schema_version = excluded.schema_version,
                        updated_at = now()
                    """,
                    (stage, key, url, label, json.dumps(payload, ensure_ascii=False), CACHE_SCHEMA_VERSION),
                )
            self.writes += 1
        except Exception as exc:
            self.errors.append({"stage": stage, "label": label, "url": url, "error": repr(exc)})
            self.store.record_error(operation="api_write", label=label, error=exc)

    def summary(self) -> dict[str, Any]:
        return {
            "backend": "postgres",
            "enabled": self.enabled,
            "dsn_env": self.store.dsn_env,
            "schema": self.store.schema,
            "refresh": self.refresh,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "errors": [*self.errors, *self.store.errors],
        }


@dataclass
class PostgresPageTextCache:
    store: PostgresCacheStore
    enabled: bool = True
    refresh: bool = False
    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def read(self, *, title: str) -> str | None:
        if not self.enabled:
            return None
        if self.refresh:
            self.misses += 1
            return None
        try:
            with self.store.connection().cursor() as cur:
                cur.execute(f"select plain_text from {self.store.page_table} where title = %s", (title,))
                row = cur.fetchone()
                if row is None:
                    self.misses += 1
                    return None
                cur.execute(
                    f"""
                    update {self.store.page_table}
                       set last_hit_at = now(),
                           hit_count = hit_count + 1
                     where title = %s
                    """,
                    (title,),
                )
        except Exception as exc:
            self.errors.append({"title": title, "error": repr(exc)})
            self.store.record_error(operation="page_read", label=title, error=exc)
            self.misses += 1
            return None
        self.hits += 1
        return str(row[0])

    def write(self, *, title: str, page_url: str, text: str) -> None:
        if not self.enabled:
            return
        try:
            with self.store.connection().cursor() as cur:
                cur.execute(
                    f"""
                    insert into {self.store.page_table} (
                        title, page_url, plain_text, schema_version
                    )
                    values (%s, %s, %s, %s)
                    on conflict (title) do update set
                        page_url = excluded.page_url,
                        plain_text = excluded.plain_text,
                        schema_version = excluded.schema_version,
                        updated_at = now()
                    """,
                    (title, page_url, text, CACHE_SCHEMA_VERSION),
                )
            self.writes += 1
        except Exception as exc:
            self.errors.append({"title": title, "error": repr(exc)})
            self.store.record_error(operation="page_write", label=title, error=exc)

    def iter_pages(self) -> Iterable[tuple[str, str]]:
        if not self.enabled or self.refresh:
            return
        try:
            with self.store.connection().cursor() as cur:
                cur.execute(f"select title, plain_text from {self.store.page_table} order by title")
                rows = cur.fetchall()
        except Exception as exc:
            self.errors.append({"operation": "iter_pages", "error": repr(exc)})
            self.store.record_error(operation="page_iter", label="page_text_cache", error=exc)
            return
        for title, text in rows:
            yield str(title), str(text)

    def summary(self) -> dict[str, Any]:
        return {
            "backend": "postgres",
            "enabled": self.enabled,
            "dsn_env": self.store.dsn_env,
            "schema": self.store.schema,
            "refresh": self.refresh,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "errors": [*self.errors, *self.store.errors],
        }


@dataclass
class FetchContext:
    request_delay_seconds: float
    max_retries: int
    retry_backoff_seconds: float
    retry_events: list[dict[str, Any]]
    user_agent: str = DEFAULT_USER_AGENT
    api_cache: ApiCache | None = None
    page_text_cache: PageTextCache | None = None
    max_retry_wait_seconds: float | None = None
    cache_only: bool = False
    deadline_at: float | None = None
    next_request_at: float = 0.0

    def assert_time_budget(self, *, stage: str, label: str) -> None:
        if self.deadline_at is not None and time.monotonic() >= self.deadline_at:
            raise TimeBudgetExceeded(f"{stage} {label}: max wall time exceeded")

    def wait_for_slot(self) -> None:
        self.assert_time_budget(stage="throttle", label="request")
        if self.request_delay_seconds <= 0:
            return
        now = time.monotonic()
        wait_seconds = self.next_request_at - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self.assert_time_budget(stage="throttle", label="request")
        self.next_request_at = time.monotonic() + self.request_delay_seconds

    def record_retry(
        self,
        *,
        stage: str,
        label: str,
        url: str,
        attempt: int,
        wait_seconds: float,
        reason: str,
        status_code: int | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "stage": stage,
            "label": label,
            "url": url,
            "attempt": attempt,
            "wait_seconds": round(wait_seconds, 3),
            "reason": reason,
        }
        if status_code is not None:
            event["status_code"] = status_code
        self.retry_events.append(event)


def load_source_excerpt_cache_config(path: Path = PROJECT_CONFIG_PATH) -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "backend": DEFAULT_CACHE_BACKEND,
        "dsn_env": DEFAULT_CACHE_DSN_ENV,
        "schema": DEFAULT_CACHE_SCHEMA,
    }
    if not path.exists():
        return defaults
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return defaults
    tooling = payload.get("tooling")
    if tooling is None:
        return defaults
    if not isinstance(tooling, dict):
        raise ExcerptPoolError("project_config.yml tooling must be a mapping")
    source_excerpt_pool = tooling.get("source_excerpt_pool")
    if source_excerpt_pool is None:
        return defaults
    if not isinstance(source_excerpt_pool, dict):
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool must be a mapping")
    cache = source_excerpt_pool.get("cache")
    if cache is None:
        return defaults
    if not isinstance(cache, dict):
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache must be a mapping")

    enabled = cache.get("enabled", defaults["enabled"])
    if not isinstance(enabled, bool):
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache.enabled must be a boolean")
    backend = cache.get("backend")
    if backend is None:
        backend = "filesystem" if "directory" in cache else defaults["backend"]
    if backend not in {"filesystem", "postgres"}:
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache.backend must be filesystem or postgres")
    directory = cache.get("directory")
    if backend == "postgres" and directory is not None:
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache.directory is only allowed for filesystem backend")
    if backend == "filesystem" and (not isinstance(directory, str) or not directory.strip()):
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache.directory must be a non-empty string")
    dsn_env = cache.get("dsn_env", defaults["dsn_env"])
    if not isinstance(dsn_env, str) or not dsn_env.strip():
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache.dsn_env must be a non-empty string")
    schema = cache.get("schema", defaults["schema"])
    if not isinstance(schema, str) or not schema.strip():
        raise ExcerptPoolError("project_config.yml tooling.source_excerpt_pool.cache.schema must be a non-empty string")
    require_pg_identifier(schema, label="project_config.yml tooling.source_excerpt_pool.cache.schema")
    config = {
        "enabled": enabled,
        "backend": backend,
        "dsn_env": dsn_env.strip(),
        "schema": schema.strip(),
    }
    if directory is not None:
        config["directory"] = resolve_repo_path(directory)
    return config


def make_cache_backends(
    *,
    cache_config: dict[str, Any],
    cache_dir: Path | None,
    cache_enabled: bool | None,
    cache_refresh: bool,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
) -> tuple[Any, Any, PostgresCacheStore | None, dict[str, Any]]:
    cache_is_enabled = cache_config["enabled"] if cache_enabled is None else cache_enabled
    backend = cache_backend or str(cache_config.get("backend") or DEFAULT_CACHE_BACKEND)
    if backend not in {"filesystem", "postgres"}:
        raise ExcerptPoolError("cache backend must be filesystem or postgres")

    if backend == "postgres":
        dsn_env = cache_dsn_env or str(cache_config.get("dsn_env") or DEFAULT_CACHE_DSN_ENV)
        schema = cache_schema or str(cache_config.get("schema") or DEFAULT_CACHE_SCHEMA)
        store = PostgresCacheStore(dsn_env=dsn_env, schema=schema)
        api_cache = PostgresApiCache(
            store=store,
            enabled=cache_is_enabled,
            refresh=cache_refresh,
        )
        page_text_cache = PostgresPageTextCache(
            store=store,
            enabled=cache_is_enabled,
            refresh=cache_refresh,
        )
    else:
        cache_root = cache_dir or cache_config.get("directory")
        if not isinstance(cache_root, Path):
            raise ExcerptPoolError("filesystem cache backend requires --cache-dir or cache.directory")
        store = None
        api_cache = ApiCache(
            cache_dir=cache_root / "api",
            enabled=cache_is_enabled,
            refresh=cache_refresh,
        )
        page_text_cache = PageTextCache(
            cache_dir=cache_root / "pages",
            enabled=cache_is_enabled,
            refresh=cache_refresh,
        )

    report_config = {
        "enabled": cache_is_enabled,
        "backend": backend,
        "refresh": cache_refresh,
        "dsn_env": getattr(store, "dsn_env", None),
        "schema": getattr(store, "schema", None),
    }
    if backend == "filesystem":
        report_config["directory"] = str(cache_root)
        report_config["cache_dir"] = str(cache_root)
    return api_cache, page_text_cache, store, report_config


def cache_report(
    *,
    report_config: dict[str, Any],
    api_cache: Any,
    page_text_cache: Any,
) -> dict[str, Any]:
    return {
        **report_config,
        "api": api_cache.summary(),
        "page_text": page_text_cache.summary(),
    }
