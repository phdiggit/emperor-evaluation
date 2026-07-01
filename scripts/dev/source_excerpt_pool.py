from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import psycopg
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ROOT / "data" / "query_profile_batches" / "i5b_layered_retrieval_profiles_20260630.jsonl"
PROJECT_CONFIG_PATH = ROOT / "data" / "configs" / "project_config.yml"
WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
DEFAULT_USER_AGENT = (
    "emperor-evaluation-source-excerpt-pool/0.1 "
    "(https://github.com/phdiggit/emperor-evaluation; source review tool) Python-urllib"
)
DEFAULT_CACHE_BACKEND = "postgres"
DEFAULT_CACHE_DSN_ENV = "EMPEROR_EVAL_PG_DSN"
DEFAULT_CACHE_SCHEMA = "tool_cache"
CACHE_SCHEMA_VERSION = 1
ADJACENT_LAYER = "adjacent_split_objects"
DEFAULT_REQUEST_DELAY_SECONDS = 0.75
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
RETRY_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
KNOWN_SOURCE_TITLE_VARIANTS = {
    "史记": ("史记", "史記"),
    "汉书": ("汉书", "漢書"),
    "后汉书": ("后汉书", "後漢書"),
    "三国志": ("三国志", "三國志"),
    "晋书": ("晋书", "晉書"),
    "宋书": ("宋书", "宋書"),
    "南史": ("南史",),
    "北史": ("北史",),
    "隋书": ("隋书", "隋書"),
    "旧唐书": ("旧唐书", "舊唐書"),
    "新唐书": ("新唐书", "新唐書"),
    "宋史": ("宋史",),
    "建炎以来系年要录": ("建炎以来系年要录", "建炎以來繫年要錄"),
    "续资治通鉴": ("续资治通鉴", "續資治通鑑"),
    "资治通鉴": ("资治通鉴", "資治通鑑"),
    "贞观政要": ("贞观政要", "貞觀政要"),
    "唐会要": ("唐会要", "唐會要"),
    "册府元龟": ("册府元龟", "冊府元龜"),
    "战国策": ("战国策", "戰國策"),
    "东观汉记": ("东观汉记", "東觀漢記"),
    "明史": ("明史",),
    "明实录": ("明实录", "明實錄"),
    "清史稿": ("清史稿",),
    "清实录": ("清实录", "清實錄"),
    "元史": ("元史",),
    "辽史": ("辽史", "遼史"),
    "金史": ("金史",),
}


class ExcerptPoolError(ValueError):
    pass


@dataclass(frozen=True)
class CandidateObject:
    raw_name: str
    layer: str
    search_terms: tuple[str, ...]


@dataclass(frozen=True)
class SearchPlan:
    object_name: str
    layer: str
    query: str
    search_terms: tuple[str, ...]


def cache_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_dsn(env_name: str) -> str:
    if os.environ.get(env_name):
        return str(os.environ[env_name])
    env = load_env()
    if env_name not in env:
        raise ExcerptPoolError(f"missing PostgreSQL DSN env var {env_name}")
    return env[env_name]


def require_pg_identifier(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ExcerptPoolError(f"{label}: expected PostgreSQL identifier")
    return value


def quote_pg_identifier(value: str) -> str:
    require_pg_identifier(value, label="postgres identifier")
    return f'"{value}"'


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
    next_request_at: float = 0.0

    def wait_for_slot(self) -> None:
        if self.request_delay_seconds <= 0:
            return
        now = time.monotonic()
        wait_seconds = self.next_request_at - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
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


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


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


def strip_html(value: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return compact_text(without_tags)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExcerptPoolError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(value, dict):
            raise ExcerptPoolError(f"{path}:{line_number}: expected JSON object")
        rows.append(value)
    return rows


def load_profile(path: Path, person: str) -> dict[str, Any]:
    matches = [row for row in read_jsonl(path) if row.get("person") == person]
    if not matches:
        raise ExcerptPoolError(f"profile not found for person: {person}")
    if len(matches) > 1:
        raise ExcerptPoolError(f"multiple profiles found for person: {person}")
    return matches[0]


def _add_unique(values: list[str], value: str) -> None:
    cleaned = compact_text(value)
    if cleaned and cleaned not in values:
        values.append(cleaned)


def derive_search_terms(raw_name: str) -> tuple[str, ...]:
    terms: list[str] = []
    _add_unique(terms, raw_name)

    for part in re.split(r"[/／、,，；;\s]+", raw_name):
        _add_unique(terms, part)
        if "等" in part:
            _add_unique(terms, part.split("等", 1)[0])
        if "相关" in part:
            before_related = part.split("相关", 1)[0]
            _add_unique(terms, before_related)
            _add_unique(terms, before_related.replace("事件", ""))

    if raw_name.endswith("功臣"):
        _add_unique(terms, raw_name.removesuffix("功臣"))
        _add_unique(terms, "功臣")
    if "功臣" in raw_name:
        _add_unique(terms, "功臣")
    if "官员" in raw_name:
        _add_unique(terms, "官员")
    for suffix in ("冤狱", "罢斥", "贬谪"):
        if raw_name.endswith(suffix):
            _add_unique(terms, raw_name.removesuffix(suffix))
            _add_unique(terms, suffix)

    return tuple(term for term in terms if len(term) >= 2)


def derive_query_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    for part in re.split(r"[/／、,，；;\s]+", query):
        _add_unique(terms, part)
    return tuple(
        sorted(
            (
                term
                for term in terms
                if len(term) >= 2 and not (len(term) == 2 and term.endswith(("帝", "宗", "祖", "王")))
            ),
            key=lambda term: (-len(term), terms.index(term)),
        )
    )


def iter_candidate_objects(profile: dict[str, Any], *, include_adjacent: bool = False) -> list[CandidateObject]:
    object_layers = profile.get("object_layers")
    if not isinstance(object_layers, dict):
        raise ExcerptPoolError("profile.object_layers: expected object")

    candidates: list[CandidateObject] = []
    for layer, names in object_layers.items():
        if layer == ADJACENT_LAYER and not include_adjacent:
            continue
        if not isinstance(names, list):
            raise ExcerptPoolError(f"profile.object_layers.{layer}: expected list")
        for name in names:
            if not isinstance(name, str) or not name.strip():
                raise ExcerptPoolError(f"profile.object_layers.{layer}: expected non-empty string")
            candidates.append(CandidateObject(name.strip(), layer, derive_search_terms(name.strip())))
    return candidates


def _bundle_matches(bundle: str, terms: Iterable[str]) -> bool:
    return any(term in bundle for term in terms)


def _bundle_mentions_other_candidate(bundle: str, candidate: CandidateObject, candidates: Iterable[CandidateObject]) -> bool:
    for other in candidates:
        if other.raw_name == candidate.raw_name:
            continue
        if _bundle_matches(bundle, other.search_terms):
            return True
    return False


def fallback_source_titles(profile: dict[str, Any]) -> tuple[str, ...]:
    titles = source_title_filters(profile)
    if titles:
        return titles
    return ("正史", "资治通鉴")


def fallback_object_queries(profile: dict[str, Any], *, person: str, primary: str) -> list[str]:
    queries: list[str] = []
    for source_title in fallback_source_titles(profile):
        _add_unique(queries, f"{person} {primary} {source_title} 任用 授权")
        _add_unique(queries, f"{person} {primary} {source_title} 人才安全")
    return queries


def build_search_plans(
    profile: dict[str, Any],
    *,
    include_adjacent: bool = False,
    max_queries_per_object: int | None = None,
) -> list[SearchPlan]:
    person = str(profile.get("person", "")).strip()
    if not person:
        raise ExcerptPoolError("profile.person: expected non-empty string")

    bundles = profile.get("query_bundles", [])
    if not isinstance(bundles, list):
        raise ExcerptPoolError("profile.query_bundles: expected list")
    query_bundles = [bundle.strip() for bundle in bundles if isinstance(bundle, str) and bundle.strip()]

    plans: list[SearchPlan] = []
    seen: set[tuple[str, str]] = set()
    candidates = iter_candidate_objects(profile, include_adjacent=include_adjacent)
    for candidate in candidates:
        object_plans = [
            bundle
            for bundle in query_bundles
            if _bundle_matches(bundle, candidate.search_terms)
        ]
        if not object_plans:
            primary = candidate.search_terms[0]
            object_plans = fallback_object_queries(profile, person=person, primary=primary)
        elif all(_bundle_mentions_other_candidate(bundle, candidate, candidates) for bundle in object_plans):
            primary = candidate.search_terms[0]
            for fallback_query in fallback_object_queries(profile, person=person, primary=primary):
                _add_unique(object_plans, fallback_query)

        selected_plans = object_plans
        if max_queries_per_object is not None:
            selected_plans = object_plans[:max_queries_per_object]
        for query in selected_plans:
            key = (candidate.raw_name, query)
            if key in seen:
                continue
            seen.add(key)
            query_terms = tuple(
                term
                for term in derive_query_terms(query)
                if term != person and term not in candidate.search_terms
            )
            plans.append(
                SearchPlan(
                    object_name=candidate.raw_name,
                    layer=candidate.layer,
                    query=query,
                    search_terms=(*query_terms, person, *candidate.search_terms),
                )
            )

    return plans


def limit_search_plans(
    plans: list[SearchPlan],
    *,
    max_queries: int | None = None,
    max_queries_per_object: int | None = None,
) -> tuple[list[SearchPlan], list[dict[str, str]]]:
    selected: list[SearchPlan] = []
    skipped: list[dict[str, str]] = []
    per_object_counts: dict[str, int] = defaultdict(int)

    for plan in plans:
        reason = ""
        if max_queries_per_object is not None and per_object_counts[plan.object_name] >= max_queries_per_object:
            reason = "max_queries_per_object"
        elif max_queries is not None and len(selected) >= max_queries:
            reason = "max_queries"

        if reason:
            skipped.append(
                {
                    "object_name": plan.object_name,
                    "layer": plan.layer,
                    "query": plan.query,
                    "reason": reason,
                }
            )
            continue

        selected.append(plan)
        per_object_counts[plan.object_name] += 1

    return selected, skipped


def source_title_filters(profile: dict[str, Any]) -> tuple[str, ...]:
    haystacks: list[str] = []
    for key in ("source_targets", "query_bundles"):
        value = profile.get(key, [])
        if isinstance(value, list):
            haystacks.extend(item for item in value if isinstance(item, str))

    filters: list[str] = []
    for simplified, variants in KNOWN_SOURCE_TITLE_VARIANTS.items():
        if any(_contains_source_title(simplified, variants, text) for text in haystacks):
            for variant in variants:
                _add_unique(filters, variant)
    return tuple(filters)


def _contains_source_title(simplified: str, variants: tuple[str, ...], text: str) -> bool:
    if simplified == "汉书":
        return bool(re.search(r"(?<!后)(?<!後)(汉书|漢書)", text))
    if simplified == "资治通鉴":
        return bool(re.search(r"(?<!续)(?<!續)(资治通鉴|資治通鑑)", text))
    if simplified == "明实录":
        return bool(re.search(r"明.{0,4}(实录|實錄)", text))
    if simplified == "清实录":
        return bool(re.search(r"清.{0,4}(实录|實錄)", text))
    return any(variant in text for variant in variants)


def title_matches_source_filters(title: str, filters: Iterable[str]) -> bool:
    source_filters = tuple(filters)
    if not source_filters:
        return True
    if any(source_filter in {"明实录", "明實錄"} for source_filter in source_filters):
        if re.match(r"明.{0,4}(实录|實錄)(/|／| |　|\(|（|$)", title):
            return True
    if any(source_filter in {"清实录", "清實錄"} for source_filter in source_filters):
        if re.match(r"清.{0,4}(实录|實錄)(/|／| |　|\(|（|$)", title):
            return True
    return any(
        title == source_filter
        or title.startswith(
            (
                f"{source_filter}/",
                f"{source_filter}／",
                f"{source_filter} ",
                f"{source_filter}　",
                f"{source_filter}(",
                f"{source_filter}（",
            )
        )
        for source_filter in source_filters
    )


def retry_after_seconds(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    try:
        parsed = float(cleaned)
    except ValueError:
        try:
            parsed_date = email.utils.parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            return None
        if parsed_date is None:
            return None
        seconds = parsed_date.timestamp() - time.time()
        return max(0.0, seconds)
    return max(0.0, parsed)


def retry_wait_seconds(exc: BaseException, *, attempt_index: int, retry_backoff_seconds: float) -> float:
    if isinstance(exc, urllib.error.HTTPError):
        retry_after = retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
        if retry_after is not None:
            return retry_after
    return retry_backoff_seconds * (2**attempt_index)


def should_retry_exception(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in RETRY_HTTP_STATUS_CODES
    return isinstance(exc, urllib.error.URLError)


def _fetch_json(
    url: str,
    *,
    timeout: int,
    fetch_context: FetchContext | None = None,
    stage: str = "api",
    label: str = "",
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    api_cache = fetch_context.api_cache if fetch_context is not None else None
    if api_cache is not None:
        cached_payload = api_cache.read(stage=stage, label=label, url=url)
        if cached_payload is not None:
            return cached_payload

    attempt_index = 0
    while True:
        if fetch_context is not None:
            fetch_context.wait_for_slot()
        request_user_agent = fetch_context.user_agent if fetch_context is not None else user_agent
        request = urllib.request.Request(url, headers={"User-Agent": request_user_agent})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ExcerptPoolError(f"unexpected JSON response from {url}")
            if api_cache is not None:
                api_cache.write(stage=stage, label=label, url=url, payload=value)
            return value
        except Exception as exc:
            if fetch_context is None or attempt_index >= fetch_context.max_retries or not should_retry_exception(exc):
                raise
            wait_seconds = retry_wait_seconds(
                exc,
                attempt_index=attempt_index,
                retry_backoff_seconds=fetch_context.retry_backoff_seconds,
            )
            fetch_context.record_retry(
                stage=stage,
                label=label,
                url=url,
                attempt=attempt_index + 1,
                wait_seconds=wait_seconds,
                reason=repr(exc),
                status_code=exc.code if isinstance(exc, urllib.error.HTTPError) else None,
            )
            time.sleep(wait_seconds)
            attempt_index += 1


def _api_url(params: dict[str, str]) -> str:
    query = urllib.parse.urlencode(params)
    return f"{WIKISOURCE_API}?{query}"


def wikisource_page_url(title: str) -> str:
    quoted = urllib.parse.quote(title.replace(" ", "_"), safe="/")
    return f"https://zh.wikisource.org/zh-hans/{quoted}"


def search_wikisource(
    query: str,
    *,
    limit: int,
    timeout: int,
    title_filters: Iterable[str] = (),
    fetch_context: FetchContext | None = None,
) -> list[dict[str, str]]:
    search_limit = max(limit, min(50, limit * 5))
    payload = _fetch_json(
        _api_url(
            {
                "action": "query",
                "list": "search",
                "srnamespace": "0",
                "srlimit": str(search_limit),
                "srsearch": query,
                "format": "json",
                "utf8": "1",
            }
        ),
        timeout=timeout,
        fetch_context=fetch_context,
        stage="search",
        label=query,
    )
    results = payload.get("query", {}).get("search", [])
    if not isinstance(results, list):
        return []
    pages: list[dict[str, str]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        title = str(result.get("title", "")).strip()
        if not title:
            continue
        if not title_matches_source_filters(title, title_filters):
            continue
        pages.append(
            {
                "title": title,
                "url": wikisource_page_url(title),
                "snippet": strip_html(str(result.get("snippet", ""))),
            }
        )
        if len(pages) >= limit:
            break
    return pages


def fetch_wikisource_plain_text(
    title: str,
    *,
    timeout: int,
    fetch_context: FetchContext | None = None,
) -> str:
    page_text_cache = fetch_context.page_text_cache if fetch_context is not None else None
    if page_text_cache is not None:
        cached_text = page_text_cache.read(title=title)
        if cached_text is not None:
            return cached_text

    payload = _fetch_json(
        _api_url(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
                "utf8": "1",
                "redirects": "1",
                "uselang": "zh-hans",
                "variant": "zh-hans",
            }
        ),
        timeout=timeout,
        fetch_context=fetch_context,
        stage="fetch_page",
        label=title,
    )
    html_text = payload.get("parse", {}).get("text", {}).get("*", "")
    if not isinstance(html_text, str) or not html_text:
        return ""
    text = strip_html(html_text)
    if page_text_cache is not None:
        page_text_cache.write(title=title, page_url=wikisource_page_url(title), text=text)
    return text


def extract_passages(
    text: str,
    terms: Iterable[str],
    *,
    context_chars: int,
    max_passages: int,
) -> list[dict[str, str]]:
    normalized = compact_text(text)
    passages: list[dict[str, str]] = []
    occupied: list[tuple[int, int]] = []

    for term in terms:
        if len(term) < 2:
            continue
        for match in re.finditer(re.escape(term), normalized):
            start = max(0, match.start() - context_chars)
            end = min(len(normalized), match.end() + context_chars)
            if any(not (end < used_start or start > used_end) for used_start, used_end in occupied):
                continue
            occupied.append((start, end))
            passages.append(
                {
                    "matched_term": term,
                    "text": normalized[start:end],
                }
            )
            if len(passages) >= max_passages:
                return passages
    return passages


def build_excerpt_pool(
    profile: dict[str, Any],
    *,
    include_adjacent: bool = False,
    max_queries: int | None = None,
    max_queries_per_object: int | None = None,
    pages_per_query: int = 2,
    context_chars: int = 220,
    max_passages_per_page: int = 2,
    timeout: int = 20,
    offline: bool = False,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
    cache_dir: Path | None = None,
    cache_enabled: bool | None = None,
    cache_refresh: bool = False,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
) -> dict[str, Any]:
    if request_delay_seconds < 0:
        raise ExcerptPoolError("request_delay_seconds must be >= 0")
    if max_retries < 0:
        raise ExcerptPoolError("max_retries must be >= 0")
    if retry_backoff_seconds < 0:
        raise ExcerptPoolError("retry_backoff_seconds must be >= 0")
    cache_config = load_source_excerpt_cache_config()
    api_cache, page_text_cache, cache_store, cache_report_config = make_cache_backends(
        cache_config=cache_config,
        cache_dir=cache_dir,
        cache_enabled=cache_enabled,
        cache_refresh=cache_refresh,
        cache_backend=cache_backend,
        cache_dsn_env=cache_dsn_env,
        cache_schema=cache_schema,
    )

    all_plans = build_search_plans(
        profile,
        include_adjacent=include_adjacent,
        max_queries_per_object=None,
    )
    plans, skipped_plans = limit_search_plans(
        all_plans,
        max_queries=max_queries,
        max_queries_per_object=max_queries_per_object,
    )

    objects = [
        {
            "name": candidate.raw_name,
            "layer": candidate.layer,
            "search_terms": list(candidate.search_terms),
        }
        for candidate in iter_candidate_objects(profile, include_adjacent=include_adjacent)
    ]
    report: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "person": profile.get("person"),
        "query_profile_id": profile.get("query_profile_id"),
        "offline": offline,
        "objects": objects,
        "title_filters": list(source_title_filters(profile)),
        "errors": [],
        "query_limits": {
            "max_queries": max_queries,
            "max_queries_per_object": max_queries_per_object,
        },
        "throttle": {
            "request_delay_seconds": request_delay_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
            "retry_http_status_codes": sorted(RETRY_HTTP_STATUS_CODES),
            "user_agent": user_agent,
        },
        "cache": cache_report(report_config=cache_report_config, api_cache=api_cache, page_text_cache=page_text_cache),
        "retry_events": [],
        "search_plans": [
            {
                "object_name": plan.object_name,
                "layer": plan.layer,
                "query": plan.query,
                "search_terms": list(plan.search_terms),
            }
            for plan in plans
        ],
        "skipped_search_plans": skipped_plans,
        "excerpts": [],
    }
    if offline:
        return report

    page_cache: dict[str, str] = {}
    excerpts: list[dict[str, Any]] = []
    title_filters = source_title_filters(profile)
    fetch_context = FetchContext(
        request_delay_seconds=request_delay_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        retry_events=report["retry_events"],
        user_agent=user_agent,
        api_cache=api_cache,
        page_text_cache=page_text_cache,
    )
    try:
        for plan in plans:
            try:
                pages = search_wikisource(
                    plan.query,
                    limit=pages_per_query,
                    timeout=timeout,
                    title_filters=title_filters,
                    fetch_context=fetch_context,
                )
            except Exception as exc:  # pragma: no cover - exercised by live network only.
                report["errors"].append({"stage": "search", "query": plan.query, "error": repr(exc)})
                continue
            for page in pages:
                title = page["title"]
                if title not in page_cache:
                    try:
                        page_cache[title] = fetch_wikisource_plain_text(
                            title,
                            timeout=timeout,
                            fetch_context=fetch_context,
                        )
                    except Exception as exc:  # pragma: no cover - exercised by live network only.
                        report["errors"].append(
                            {
                                "stage": "fetch_page",
                                "query": plan.query,
                                "page_title": title,
                                "error": repr(exc),
                            }
                        )
                        continue
                passages = extract_passages(
                    page_cache[title],
                    plan.search_terms,
                    context_chars=context_chars,
                    max_passages=max_passages_per_page,
                )
                if not passages and page["snippet"]:
                    passages = [{"matched_term": "search_snippet", "text": page["snippet"]}]
                if not passages:
                    continue
                excerpts.append(
                    {
                        "object_name": plan.object_name,
                        "layer": plan.layer,
                        "query": plan.query,
                        "page_title": title,
                        "page_url": page["url"],
                        "search_snippet": page["snippet"],
                        "passages": passages,
                    }
                )
    finally:
        if cache_store is not None:
            cache_store.close()

    report["excerpts"] = excerpts
    report["cache"] = cache_report(report_config=cache_report_config, api_cache=api_cache, page_text_cache=page_text_cache)
    return report


def migrate_filesystem_cache_to_cache(
    source_dir: Path,
    *,
    api_cache: Any,
    page_text_cache: Any,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "source_dir": str(source_dir),
        "api": {"scanned": 0, "imported": 0, "errors": []},
        "page_text": {"scanned": 0, "imported": 0, "errors": []},
    }
    api_root = source_dir / "api"
    if api_root.exists():
        for path in sorted(api_root.glob("*/*.json")):
            report["api"]["scanned"] += 1
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(envelope, dict):
                    raise ExcerptPoolError("cache envelope is not an object")
                payload = envelope.get("payload")
                if not isinstance(payload, dict):
                    raise ExcerptPoolError("cache payload is not an object")
                stage = str(envelope.get("stage") or path.parent.name)
                label = str(envelope.get("label") or "")
                url = str(envelope.get("url") or "")
                if not url:
                    raise ExcerptPoolError("cache envelope url is empty")
                before = api_cache.writes
                api_cache.write(stage=stage, label=label, url=url, payload=payload)
                if api_cache.writes > before:
                    report["api"]["imported"] += 1
            except Exception as exc:
                report["api"]["errors"].append({"path": str(path), "error": repr(exc)})

    page_root = source_dir / "pages"
    if page_root.exists():
        for meta_path in sorted(page_root.glob("*.json")):
            report["page_text"]["scanned"] += 1
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                if not isinstance(metadata, dict):
                    raise ExcerptPoolError("page cache metadata is not an object")
                title = str(metadata.get("title") or "")
                page_url = str(metadata.get("page_url") or "")
                text_name = str(metadata.get("text_path") or meta_path.with_suffix(".txt").name)
                text_path = page_root / text_name
                if not title:
                    raise ExcerptPoolError("page cache title is empty")
                if not text_path.exists():
                    raise ExcerptPoolError(f"page cache text missing: {text_path.name}")
                before = page_text_cache.writes
                page_text_cache.write(title=title, page_url=page_url, text=text_path.read_text(encoding="utf-8"))
                if page_text_cache.writes > before:
                    report["page_text"]["imported"] += 1
            except Exception as exc:
                report["page_text"]["errors"].append({"path": str(meta_path), "error": repr(exc)})
    return report


def migrate_configured_cache_to_postgres(
    *,
    cache_dir: Path | None = None,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
) -> dict[str, Any]:
    cache_config = load_source_excerpt_cache_config()
    backend = cache_backend or str(cache_config.get("backend") or DEFAULT_CACHE_BACKEND)
    if backend != "postgres":
        raise ExcerptPoolError("cache migration target backend must be postgres")
    api_cache, page_text_cache, store, report_config = make_cache_backends(
        cache_config=cache_config,
        cache_dir=cache_dir,
        cache_enabled=True,
        cache_refresh=False,
        cache_backend="postgres",
        cache_dsn_env=cache_dsn_env,
        cache_schema=cache_schema,
    )
    source_dir = cache_dir or cache_config.get("directory")
    if source_dir is None:
        raise ExcerptPoolError("cache migration requires --cache-dir after filesystem cache directory config removal")
    try:
        migration = migrate_filesystem_cache_to_cache(
            source_dir,
            api_cache=api_cache,
            page_text_cache=page_text_cache,
        )
    finally:
        if store is not None:
            store.close()
    return {
        "cache": cache_report(report_config=report_config, api_cache=api_cache, page_text_cache=page_text_cache),
        "migration": migration,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('person', '')} source excerpt pool",
        "",
        f"- query_profile_id: `{report.get('query_profile_id', '')}`",
        f"- offline: `{report.get('offline')}`",
        f"- objects: `{len(report.get('objects', []))}`",
        f"- excerpts: `{len(report.get('excerpts', []))}`",
        "",
        "## Objects",
        "",
    ]
    for obj in report.get("objects", []):
        terms = ", ".join(f"`{term}`" for term in obj.get("search_terms", []))
        lines.append(f"- `{obj.get('name')}` ({obj.get('layer')}): {terms}")

    lines.extend(["", "## Search Plans", ""])
    for plan in report.get("search_plans", []):
        lines.append(f"- `{plan.get('object_name')}`: {plan.get('query')}")

    skipped = report.get("skipped_search_plans", [])
    if skipped:
        lines.extend(["", "## Skipped Search Plans", ""])
        for item in skipped:
            lines.append(f"- `{item.get('object_name')}`: {item.get('query')} ({item.get('reason')})")

    retry_events = report.get("retry_events", [])
    if retry_events:
        lines.extend(["", "## Retry Events", ""])
        for event in retry_events:
            lines.append(
                f"- `{event.get('stage')}` `{event.get('label')}`: "
                f"attempt {event.get('attempt')}, wait {event.get('wait_seconds')}s"
            )

    cache = report.get("cache", {})
    if cache:
        lines.extend(["", "## Cache", ""])
        lines.append(f"- enabled: `{cache.get('enabled')}`")
        lines.append(f"- backend: `{cache.get('backend')}`")
        if cache.get("directory") or cache.get("cache_dir"):
            lines.append(f"- directory: `{cache.get('directory') or cache.get('cache_dir')}`")
        if cache.get("dsn_env"):
            lines.append(f"- dsn_env: `{cache.get('dsn_env')}`")
        if cache.get("schema"):
            lines.append(f"- schema: `{cache.get('schema')}`")
        lines.append(f"- refresh: `{cache.get('refresh')}`")
        for cache_name in ("api", "page_text"):
            cache_summary = cache.get(cache_name, {})
            if cache_summary:
                lines.append(
                    f"- {cache_name}: hits `{cache_summary.get('hits')}`, "
                    f"misses `{cache_summary.get('misses')}`, writes `{cache_summary.get('writes')}`"
                )
                cache_errors = cache_summary.get("errors", [])
                if cache_errors:
                    lines.append(f"- {cache_name}_errors: `{len(cache_errors)}`")

    errors = report.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", ""])
        for item in errors:
            label = item.get("query") or item.get("page_title") or item.get("stage")
            lines.append(f"- `{item.get('stage')}` `{label}`: {item.get('error')}")

    lines.extend(["", "## Excerpts", ""])
    for item in report.get("excerpts", []):
        lines.append(f"### {item.get('object_name')} / {item.get('page_title')}")
        lines.append("")
        lines.append(f"- layer: `{item.get('layer')}`")
        lines.append(f"- query: `{item.get('query')}`")
        lines.append(f"- page: {item.get('page_url')}")
        for passage in item.get("passages", []):
            lines.append("")
            lines.append(f"> [{passage.get('matched_term')}] {passage.get('text')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise ExcerptPoolError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a review-first source excerpt pool from an I5B query profile.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Query-profile JSONL path.")
    parser.add_argument("--person", help="Profile person name.")
    parser.add_argument("--output", type=Path, help="Output report path.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Output format.")
    parser.add_argument("--include-adjacent", action="store_true", help="Include adjacent_split_objects.")
    parser.add_argument("--offline", action="store_true", help="Only build object/query plans; do not call Wikisource.")
    parser.add_argument("--max-queries", type=int, default=None, help="Global maximum query count.")
    parser.add_argument(
        "--max-queries-per-object",
        type=int,
        default=None,
        help="Maximum queries per object; omit to keep every generated query.",
    )
    parser.add_argument("--pages-per-query", type=int, default=2, help="Wikisource pages to inspect per query.")
    parser.add_argument("--context-chars", type=int, default=220, help="Characters before/after each hit.")
    parser.add_argument("--max-passages-per-page", type=int, default=2, help="Passages to keep per page.")
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout in seconds.")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help="Minimum seconds between Wikisource API request starts.",
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retries for HTTP 429/5xx or URL errors.")
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
        help="Base seconds for exponential retry backoff when Retry-After is absent.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("WIKISOURCE_USER_AGENT", DEFAULT_USER_AGENT),
        help="Wikimedia-compliant User-Agent. Can also be set by WIKISOURCE_USER_AGENT.",
    )
    parser.add_argument("--cache-dir", type=Path, default=None, help="Persistent Wikisource cache root directory.")
    parser.add_argument("--cache-backend", choices=("filesystem", "postgres"), default=None, help="Override configured cache backend.")
    parser.add_argument("--cache-dsn-env", default=None, help="Override PostgreSQL cache DSN environment variable name.")
    parser.add_argument("--cache-schema", default=None, help="Override PostgreSQL cache schema.")
    parser.add_argument("--no-cache", action="store_true", help="Disable persistent Wikisource cache.")
    parser.add_argument("--cache-refresh", action="store_true", help="Ignore existing cache entries and overwrite them.")
    parser.add_argument(
        "--migrate-cache-to-postgres",
        action="store_true",
        help="Import existing filesystem Wikisource cache into the configured PostgreSQL cache tables.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.migrate_cache_to_postgres:
        report = migrate_configured_cache_to_postgres(
            cache_dir=args.cache_dir,
            cache_backend=args.cache_backend or "postgres",
            cache_dsn_env=args.cache_dsn_env,
            cache_schema=args.cache_schema,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not args.person:
        parser.error("--person is required unless --migrate-cache-to-postgres is used")
    if args.output is None:
        parser.error("--output is required unless --migrate-cache-to-postgres is used")
    profile = load_profile(args.profile, args.person)
    report = build_excerpt_pool(
        profile,
        include_adjacent=args.include_adjacent,
        max_queries=args.max_queries,
        max_queries_per_object=args.max_queries_per_object,
        pages_per_query=args.pages_per_query,
        context_chars=args.context_chars,
        max_passages_per_page=args.max_passages_per_page,
        timeout=args.timeout,
        offline=args.offline,
        request_delay_seconds=args.request_delay,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff,
        user_agent=args.user_agent,
        cache_dir=args.cache_dir,
        cache_enabled=False if args.no_cache else None,
        cache_refresh=args.cache_refresh,
        cache_backend=args.cache_backend,
        cache_dsn_env=args.cache_dsn_env,
        cache_schema=args.cache_schema,
    )
    write_report(args.output, report, output_format=args.format)
    print(json.dumps({"output": str(args.output), "objects": len(report["objects"]), "excerpts": len(report["excerpts"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
