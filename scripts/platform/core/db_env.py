from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
LEGACY_ENV_DSN = "PG_SEARCH_BENCH_DSN"
DEFAULT_CHECK_FIELDS: dict[str, object] = {
    "default_tests_require_postgres": False,
    "will_apply": False,
}

DotenvReader = Callable[[Path], Mapping[str, str]]
QuoteIdentifier = Callable[[str], str]
ResolveDsn = Callable[..., "ResolvedDsn"]


@dataclass(frozen=True)
class ResolvedDsn:
    dsn: str | None
    source: str

    @property
    def present(self) -> bool:
        return bool(self.dsn)


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def resolve_database_dsn(
    explicit_dsn: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    env_names: Sequence[str] = (PRIMARY_ENV_DSN,),
    env_path: Path | None = None,
    dotenv_reader: DotenvReader | None = None,
    explicit_source: str = "--dsn",
) -> ResolvedDsn:
    if explicit_dsn:
        return ResolvedDsn(explicit_dsn, explicit_source)
    if env is None:
        env = os.environ
    for name in env_names:
        if env.get(name):
            return ResolvedDsn(env[name], f"env:{name}")
    if env_path is not None and dotenv_reader is not None:
        dotenv = dotenv_reader(env_path)
        for name in env_names:
            if dotenv.get(name):
                return ResolvedDsn(dotenv[name], f".env:{name}")
    return ResolvedDsn(None, "skip")


def make_resolve_dsn(
    *,
    env_names: Sequence[str] = (PRIMARY_ENV_DSN,),
    env_path: Path | None = None,
    dotenv_reader: DotenvReader | None = None,
    allow_explicit: bool = False,
    explicit_source: str = "--dsn",
) -> ResolveDsn:
    if allow_explicit:

        def resolve_dsn(
            explicit_dsn: str | None = None,
            *,
            env: Mapping[str, str] | None = None,
            env_path: Path | None = env_path,
        ) -> ResolvedDsn:
            return resolve_database_dsn(
                explicit_dsn,
                env=env,
                env_names=env_names,
                env_path=env_path,
                dotenv_reader=dotenv_reader,
                explicit_source=explicit_source,
            )

        return resolve_dsn

    def resolve_dsn(
        *,
        env: Mapping[str, str] | None = None,
        env_path: Path | None = env_path,
    ) -> ResolvedDsn:
        return resolve_database_dsn(
            env=env,
            env_names=env_names,
            env_path=env_path,
            dotenv_reader=dotenv_reader,
            explicit_source=explicit_source,
        )

    return resolve_dsn


def database_environment_report(
    resolved: ResolvedDsn,
    *,
    driver_available: bool | None = None,
    extra_fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if driver_available is None:
        driver_available = is_psycopg_available()
    report: dict[str, object] = {
        "mode": "check",
        "dsn_present": resolved.present,
        "dsn_source": resolved.source,
        "driver": "psycopg",
        "driver_available": driver_available,
    }
    report.update(DEFAULT_CHECK_FIELDS if extra_fields is None else extra_fields)
    return report


def _resolve_for_callable(
    resolve_dsn: ResolveDsn,
    *,
    resolved: ResolvedDsn | None,
    env: Mapping[str, str] | None,
) -> ResolvedDsn:
    if resolved is not None:
        return resolved
    if env is None:
        return resolve_dsn()
    return resolve_dsn(env=env)


def make_check_environment(
    resolve_dsn: ResolveDsn,
    *,
    extra_fields: Mapping[str, object] | None = None,
) -> Callable[..., dict[str, object]]:
    def check_environment(
        resolved: ResolvedDsn | None = None,
        *,
        env: Mapping[str, str] | None = None,
        driver_available: bool | None = None,
    ) -> dict[str, object]:
        return database_environment_report(
            _resolve_for_callable(resolve_dsn, resolved=resolved, env=env),
            driver_available=driver_available,
            extra_fields=extra_fields,
        )

    return check_environment


def database_integration_skip_reason(
    resolved: ResolvedDsn,
    *,
    missing_reason: str,
    driver_available: bool | None = None,
) -> str | None:
    if not resolved.dsn:
        return missing_reason
    if driver_available is None:
        driver_available = is_psycopg_available()
    if not driver_available:
        return "psycopg is not installed"
    return None


def make_integration_skip_reason(
    resolve_dsn: ResolveDsn,
    *,
    missing_reason: str,
) -> Callable[..., str | None]:
    def integration_skip_reason(
        resolved: ResolvedDsn | None = None,
        *,
        env: Mapping[str, str] | None = None,
        driver_available: bool | None = None,
    ) -> str | None:
        return database_integration_skip_reason(
            _resolve_for_callable(resolve_dsn, resolved=resolved, env=env),
            missing_reason=missing_reason,
            driver_available=driver_available,
        )

    return integration_skip_reason


def primary_env_check_report(
    *,
    env: Mapping[str, str] | None = None,
    driver_available: bool | None = None,
    primary_env_dsn: str = PRIMARY_ENV_DSN,
    extra_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if env is None:
        env = os.environ
    if driver_available is None:
        driver_available = is_psycopg_available()
    dsn_present = bool(env.get(primary_env_dsn))
    report: dict[str, Any] = {
        "mode": "check",
        "dsn_present": dsn_present,
        "dsn_source": f"env:{primary_env_dsn}" if dsn_present else "skip",
        "driver": "psycopg",
        "driver_available": driver_available,
    }
    if extra_fields:
        report.update(extra_fields)
    return report


def validate_isolated_schema_name(
    schema: str,
    *,
    quote_identifier: QuoteIdentifier,
    public_schema_message: str,
) -> None:
    quote_identifier(schema)
    if schema == "public":
        raise ValueError(public_schema_message)


def make_validate_isolated_schema(
    quote_identifier: QuoteIdentifier,
    *,
    public_schema_message: str,
) -> Callable[[str], None]:
    def validate_isolated_schema(schema: str) -> None:
        validate_isolated_schema_name(
            schema,
            quote_identifier=quote_identifier,
            public_schema_message=public_schema_message,
        )

    return validate_isolated_schema
