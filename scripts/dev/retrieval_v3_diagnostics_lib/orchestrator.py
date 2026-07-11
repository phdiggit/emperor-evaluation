from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v3_consumer import fetch_readiness_report
from scripts.dev.retrieval_v3_diagnostics_lib.actions import build_next_actions
from scripts.dev.retrieval_v3_diagnostics_lib.common import (
    DEFAULT_TOP_MATERIALS_PER_TARGET,
    RetrievalV3DiagnosticsError,
)
from scripts.dev.retrieval_v3_diagnostics_lib.reports import (
    fetch_coverage_checks,
    fetch_duplicate_checks,
    fetch_summary,
)
from scripts.dev.retrieval_v3_diagnostics_lib.score_chain import fetch_score_chain

def fetch_db_report(
    *,
    env_file: Path | None,
    dsn_env: str,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    command: str,
    target_code: str = "",
    target_codes: Sequence[str] | None = None,
    emperors: Sequence[str] | None = None,
    selector_type: str = "",
    selector_role: str = "",
    names: Sequence[str] | None = None,
    top_materials_per_target: int = DEFAULT_TOP_MATERIALS_PER_TARGET,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if command == "summary":
                return fetch_summary(cur, item_code=item_code, rule_code=rule_code, formula_code=formula_code, scope=scope)
            if command == "coverage":
                return fetch_coverage_checks(cur, item_code=item_code, rule_code=rule_code, formula_code=formula_code, scope=scope)
            if command == "duplicates":
                return fetch_duplicate_checks(cur, item_code=item_code, rule_code=rule_code, formula_code=formula_code, scope=scope)
            if command == "score-chain":
                return fetch_score_chain(
                    cur,
                    item_code=item_code,
                    rule_code=rule_code,
                    formula_code=formula_code,
                    scope=scope,
                    target_code=target_code,
                    target_codes=target_codes,
                    emperors=emperors,
                    selector_type=selector_type,
                    selector_role=selector_role,
                    names=names,
                    top_materials_per_target=top_materials_per_target,
                )
    raise RetrievalV3DiagnosticsError(f"unsupported DB report command: {command}")

def fetch_report(
    *,
    env_file: Path | None,
    dsn_env: str,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
) -> dict[str, Any]:
    summary = fetch_db_report(
        env_file=env_file,
        dsn_env=dsn_env,
        item_code=item_code,
        rule_code=rule_code,
        formula_code=formula_code,
        scope=scope,
        command="summary",
    )
    readiness = fetch_readiness_report(env_file=env_file, dsn_env=dsn_env, item_code=item_code, rule_code=rule_code, scope=scope)
    coverage = fetch_db_report(
        env_file=env_file,
        dsn_env=dsn_env,
        item_code=item_code,
        rule_code=rule_code,
        formula_code=formula_code,
        scope=scope,
        command="coverage",
    )
    duplicates = fetch_db_report(
        env_file=env_file,
        dsn_env=dsn_env,
        item_code=item_code,
        rule_code=rule_code,
        formula_code=formula_code,
        scope=scope,
        command="duplicates",
    )
    next_actions = build_next_actions(
        readiness=readiness,
        coverage=coverage,
        duplicates=duplicates,
        item_code=item_code,
        rule_code=rule_code,
        formula_code=formula_code,
        scope=scope,
    )
    blocking = [
        check
        for check in (coverage.get("checks") or []) + (duplicates.get("checks") or [])
        if check.get("status") == "blocking"
    ]
    return {
        "generated_by": "scripts/dev/retrieval_v3_diagnostics.py",
        "command": "report",
        "ok": bool(readiness.get("ok")) and not blocking,
        "scope": {"item_code": item_code, "rule_code": rule_code, "formula_code": formula_code, "scope": scope},
        "summary": summary,
        "readiness": readiness,
        "coverage": coverage,
        "duplicates": duplicates,
        "next_actions": next_actions,
        "totals": {
            "next_actions": len(next_actions),
            "coverage_issues": sum(1 for check in coverage.get("checks") or [] if int(check.get("count") or 0) > 0),
            "duplicate_issues": sum(1 for check in duplicates.get("checks") or [] if int(check.get("count") or 0) > 0),
        },
    }

