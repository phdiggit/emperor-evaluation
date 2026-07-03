from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
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
DEFAULT_WORKFLOW_CODE = "I5B"
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


class CacheMissError(ExcerptPoolError):
    pass


class TimeBudgetExceeded(ExcerptPoolError):
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


@dataclass(frozen=True)
class DirectPagePlan:
    object_name: str
    layer: str
    page_title: str
    source_target: str
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
        env[key.strip()] = value.strip().strip("\"'")
    return env


def resolve_dsn(env_name: str) -> str:
    env = load_env()
    if env_name not in env and os.environ.get(env_name):
        return str(os.environ[env_name])
    if env_name not in env:
        raise ExcerptPoolError(f"environment variable not set: {env_name}")
    return env[env_name]


def require_pg_identifier(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ExcerptPoolError(f"{label}: expected PostgreSQL identifier")
    return value


def quote_pg_identifier(value: str) -> str:
    require_pg_identifier(value, label="postgres identifier")
    return f'"{value}"'


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_workflow_code(value: str | None, *, default: str = DEFAULT_WORKFLOW_CODE) -> str:
    raw = value if value is not None else default
    cleaned = re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fff]+", "_", str(raw)).strip("._-")
    if cleaned:
        return cleaned
    fallback = re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fff]+", "_", default).strip("._-")
    return fallback or "SOURCE"


def workflow_slug(value: str | None, *, default: str = DEFAULT_WORKFLOW_CODE) -> str:
    return normalize_workflow_code(value, default=default).lower()


def _platform_path(value: Any) -> Path | None:
    if isinstance(value, str) and value.strip():
        return Path(value)
    if not isinstance(value, dict):
        return None
    key = "windows" if platform.system().lower().startswith("win") else "server"
    raw = value.get(key) or value.get("server") or value.get("windows")
    if isinstance(raw, str) and raw.strip():
        return Path(raw)
    return None


def _resolve_config_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _collect_source_paths(paths: Any) -> dict[str, Path]:
    if not isinstance(paths, dict):
        return {}
    resolved: dict[str, Path] = {}
    for key in ("query_profile", "query_profile_shared_copy", "source_pack_root", "jobs_dir", "logs_dir", "handoff_root"):
        path = _platform_path(paths.get(key))
        if path is not None:
            resolved[key] = _resolve_config_path(path)
    return resolved


def load_source_excerpt_pool_runtime(
    *,
    workflow_code: str | None = None,
    config_path: Path = PROJECT_CONFIG_PATH,
) -> dict[str, Any]:
    if not config_path.exists():
        code = normalize_workflow_code(workflow_code or DEFAULT_WORKFLOW_CODE)
        return {"workflow_code": code, "paths": {}}
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        code = normalize_workflow_code(workflow_code or DEFAULT_WORKFLOW_CODE)
        return {"workflow_code": code, "paths": {}}
    tooling = payload.get("tooling")
    if not isinstance(tooling, dict):
        code = normalize_workflow_code(workflow_code or DEFAULT_WORKFLOW_CODE)
        return {"workflow_code": code, "paths": {}}
    source_excerpt_pool = tooling.get("source_excerpt_pool")
    if not isinstance(source_excerpt_pool, dict):
        code = normalize_workflow_code(workflow_code or DEFAULT_WORKFLOW_CODE)
        return {"workflow_code": code, "paths": {}}

    default_code = normalize_workflow_code(source_excerpt_pool.get("default_workflow_code") or DEFAULT_WORKFLOW_CODE)
    selected_code = normalize_workflow_code(workflow_code or default_code)
    resolved = _collect_source_paths(source_excerpt_pool.get("paths"))
    workflows = source_excerpt_pool.get("workflows")
    workflow_row = None
    if isinstance(workflows, dict):
        for key, row in workflows.items():
            if normalize_workflow_code(str(key)) == selected_code:
                workflow_row = row
                break
    runtime: dict[str, Any] = {"workflow_code": selected_code, "paths": resolved}
    if isinstance(workflow_row, dict):
        resolved.update(_collect_source_paths(workflow_row.get("paths")))
        if isinstance(workflow_row.get("adapter"), str) and workflow_row["adapter"].strip():
            runtime["adapter"] = workflow_row["adapter"].strip()
        if isinstance(workflow_row.get("source_scope"), str) and workflow_row["source_scope"].strip():
            runtime["source_scope"] = workflow_row["source_scope"].strip()
    return runtime


def load_source_excerpt_pool_paths(
    *,
    workflow_code: str | None = None,
    config_path: Path = PROJECT_CONFIG_PATH,
) -> dict[str, Path]:
    runtime = load_source_excerpt_pool_runtime(workflow_code=workflow_code, config_path=config_path)
    paths = runtime.get("paths")
    return paths if isinstance(paths, dict) else {}


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


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
