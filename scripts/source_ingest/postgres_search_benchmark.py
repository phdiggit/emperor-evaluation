from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.source_ingest.search_benchmark import build_token_text, normalize_query


DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "source_search" / "classical_chinese_passages.json"
BENCH_SQL_PATH = ROOT / "db" / "postgres" / "bench_search.sql"
ENV_DSN = "PG_SEARCH_BENCH_DSN"
STRATEGIES = ("tsvector", "like", "trgm")
FORBIDDEN_REPORT_KEYS = {"score", "rank", "final_score", "leaderboard"}

LIMITATIONS = (
    "opt-in PostgreSQL benchmark only; default tests do not require PostgreSQL.",
    "Results guide PostgreSQL FTS / pg_trgm tuning and are not production search quality conclusions.",
    "Single-character and two-character Chinese queries can expose pg_trgm false negative risk.",
    "Alias expansion is benchmark input only and does not rewrite raw_text or norm_text.",
    "False positive and false negative sets are reported per strategy for review.",
)


@dataclass(frozen=True)
class PostgresSearchCase:
    case_id: str
    category: str
    query: str
    expected_passage_codes: tuple[str, ...]

    @property
    def normalized_query(self) -> str:
        return normalize_query(self.query)


DEFAULT_CASES = (
    PostgresSearchCase("single_char_pei", "single_char", "沛", ("bench-shiji-008-p0001", "bench-shiji-008-p0002")),
    PostgresSearchCase("two_char_peifeng", "two_char", "沛丰", ("bench-shiji-008-p0001",)),
    PostgresSearchCase("long_term_zhongyangli", "long_term", "中阳里", ("bench-shiji-008-p0001",)),
    PostgresSearchCase("alias_liubang", "alias", "刘邦", ("bench-shiji-008-p0001",)),
    PostgresSearchCase("alias_tangtaizong", "alias", "唐太宗", ("bench-zizhi-weizheng-p0001",)),
    PostgresSearchCase("variant_mingshilu", "variant", "明实录", ("bench-mingshilu-hongwu-p0001",)),
    PostgresSearchCase("noise_liguan", "noise", "礼官［23］", ("bench-ritual-noise-p0001",)),
    PostgresSearchCase("known_unrelated_hanxin", "false_positive_probe", "韓信", ()),
)


def load_passages(path: Path = DEFAULT_FIXTURE) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_passages(passages: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    prepared: list[dict[str, str]] = []
    for passage in passages:
        raw_text = _required_str(passage, "raw_text")
        aliases = passage.get("aliases") or []
        if not isinstance(aliases, list):
            raise TypeError("aliases must be a list")
        prepared.append(
            {
                "passage_code": _required_str(passage, "passage_code"),
                "raw_text": raw_text,
                "norm_text": normalize_query(raw_text),
                "token_text": build_token_text(raw_text, aliases=[str(alias) for alias in aliases]),
            }
        )
    return prepared


def render_benchmark_sql(
    passages: Sequence[Mapping[str, Any]] | None = None,
    cases: Sequence[PostgresSearchCase] = DEFAULT_CASES,
) -> str:
    return _render_setup_sql(passages, cases) + _render_report_sql()


def render_explain_sql(
    passages: Sequence[Mapping[str, Any]] | None = None,
    cases: Sequence[PostgresSearchCase] = DEFAULT_CASES,
) -> str:
    return (
        _render_setup_sql(passages, cases)
        + """EXPLAIN (FORMAT JSON)
SELECT passage_code
FROM bench_passages
WHERE search_vec @@ plainto_tsquery('simple', '沛');

EXPLAIN (FORMAT JSON)
SELECT passage_code
FROM bench_passages
WHERE norm_text LIKE '%沛%';

EXPLAIN (FORMAT JSON)
SELECT passage_code
FROM bench_passages
WHERE norm_text % '沛豐';
"""
    )


def _render_setup_sql(
    passages: Sequence[Mapping[str, Any]] | None = None,
    cases: Sequence[PostgresSearchCase] = DEFAULT_CASES,
) -> str:
    prepared = prepare_passages(passages or load_passages())
    passage_rows = ",\n".join(
        "    ({code}, {raw}, {norm}, {token})".format(
            code=_sql_literal(passage["passage_code"]),
            raw=_sql_literal(passage["raw_text"]),
            norm=_sql_literal(passage["norm_text"]),
            token=_sql_literal(passage["token_text"]),
        )
        for passage in prepared
    )
    case_rows = ",\n".join(
        "    ({case_id}, {category}, {query}, {normalized}, {expected})".format(
            case_id=_sql_literal(case.case_id),
            category=_sql_literal(case.category),
            query=_sql_literal(case.query),
            normalized=_sql_literal(case.normalized_query),
            expected=_sql_array(case.expected_passage_codes),
        )
        for case in cases
    )

    return f"""\\set ON_ERROR_STOP on
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TEMP TABLE bench_passages (
    passage_code text PRIMARY KEY,
    raw_text text NOT NULL,
    norm_text text NOT NULL,
    token_text text NOT NULL,
    search_vec tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(token_text, norm_text, ''))
    ) STORED
);

CREATE INDEX bench_search_vec_gin ON bench_passages USING gin (search_vec);
CREATE INDEX bench_norm_trgm ON bench_passages USING gin (norm_text gin_trgm_ops);

INSERT INTO bench_passages (passage_code, raw_text, norm_text, token_text)
VALUES
{passage_rows};

CREATE TEMP TABLE bench_queries (
    case_id text PRIMARY KEY,
    category text NOT NULL,
    query text NOT NULL,
    normalized_query text NOT NULL,
    expected_passage_codes text[] NOT NULL
);

INSERT INTO bench_queries (case_id, category, query, normalized_query, expected_passage_codes)
VALUES
{case_rows};

ANALYZE bench_passages;
"""


def _render_report_sql() -> str:
    return """

CREATE TEMP TABLE bench_matches AS
SELECT
    q.case_id,
    q.category,
    q.query,
    q.normalized_query,
    q.expected_passage_codes,
    ARRAY(
        SELECT p.passage_code
        FROM bench_passages p
        WHERE p.search_vec @@ plainto_tsquery('simple', q.normalized_query)
        ORDER BY p.passage_code
    ) AS matched_by_tsvector,
    ARRAY(
        SELECT p.passage_code
        FROM bench_passages p
        WHERE p.norm_text LIKE '%' || q.normalized_query || '%'
        ORDER BY p.passage_code
    ) AS matched_by_like,
    ARRAY(
        SELECT p.passage_code
        FROM bench_passages p
        WHERE p.norm_text % q.normalized_query
        ORDER BY p.passage_code
    ) AS matched_by_trgm
FROM bench_queries q;

WITH expanded AS (
    SELECT
        *,
        ARRAY(
            SELECT value
            FROM (
                SELECT unnest(expected_passage_codes) AS value
                EXCEPT
                SELECT unnest(matched_by_tsvector) AS value
            ) diff
            ORDER BY value
        ) AS missed_tsvector,
        ARRAY(
            SELECT value
            FROM (
                SELECT unnest(matched_by_tsvector) AS value
                EXCEPT
                SELECT unnest(expected_passage_codes) AS value
            ) diff
            ORDER BY value
        ) AS unexpected_tsvector,
        ARRAY(
            SELECT value
            FROM (
                SELECT unnest(expected_passage_codes) AS value
                EXCEPT
                SELECT unnest(matched_by_like) AS value
            ) diff
            ORDER BY value
        ) AS missed_like,
        ARRAY(
            SELECT value
            FROM (
                SELECT unnest(matched_by_like) AS value
                EXCEPT
                SELECT unnest(expected_passage_codes) AS value
            ) diff
            ORDER BY value
        ) AS unexpected_like,
        ARRAY(
            SELECT value
            FROM (
                SELECT unnest(expected_passage_codes) AS value
                EXCEPT
                SELECT unnest(matched_by_trgm) AS value
            ) diff
            ORDER BY value
        ) AS missed_trgm,
        ARRAY(
            SELECT value
            FROM (
                SELECT unnest(matched_by_trgm) AS value
                EXCEPT
                SELECT unnest(expected_passage_codes) AS value
            ) diff
            ORDER BY value
        ) AS unexpected_trgm
    FROM bench_matches
)
SELECT jsonb_pretty(
    jsonb_build_object(
        'benchmark', 'postgres_search_benchmark',
        'fixture', 'tests/fixtures/source_search/classical_chinese_passages.json',
        'opt_in_env_var', '{ENV_DSN}',
        'default_tests_require_postgres', false,
        'strategies', jsonb_build_array('tsvector', 'like', 'trgm'),
        'limitations', '["opt-in PostgreSQL benchmark only; default tests do not require PostgreSQL.", "Results guide PostgreSQL FTS / pg_trgm tuning and are not production search quality conclusions.", "Single-character and two-character Chinese queries can expose pg_trgm false negative risk.", "Alias expansion is benchmark input only and does not rewrite raw_text or norm_text.", "False positive and false negative sets are reported per strategy for review."]'::jsonb,
        'cases', jsonb_agg(
            jsonb_build_object(
                'case_id', case_id,
                'category', category,
                'query', query,
                'normalized_query', normalized_query,
                'expected_passage_codes', expected_passage_codes,
                'matched_by_tsvector', matched_by_tsvector,
                'matched_by_like', matched_by_like,
                'matched_by_trgm', matched_by_trgm,
                'missed_by_strategy', jsonb_build_object(
                    'tsvector', missed_tsvector,
                    'like', missed_like,
                    'trgm', missed_trgm
                ),
                'unexpected_by_strategy', jsonb_build_object(
                    'tsvector', unexpected_tsvector,
                    'like', unexpected_like,
                    'trgm', unexpected_trgm
                )
            )
            ORDER BY case_id
        ),
        'explain_plan_strategies', jsonb_build_array('tsvector', 'like', 'trgm')
    )
)
FROM expanded;
"""


def build_contract_report(
    passages: Sequence[Mapping[str, Any]] | None = None,
    cases: Sequence[PostgresSearchCase] = DEFAULT_CASES,
) -> dict[str, Any]:
    prepared = prepare_passages(passages or load_passages())
    rows: list[dict[str, Any]] = []
    for case in cases:
        matches = {
            "tsvector": _match_tsvector(prepared, case.normalized_query),
            "like": _match_like(prepared, case.normalized_query),
            "trgm": _match_trgm_proxy(prepared, case.normalized_query),
        }
        expected = set(case.expected_passage_codes)
        rows.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "query": case.query,
                "normalized_query": case.normalized_query,
                "expected_passage_codes": sorted(expected),
                "matched_by_tsvector": matches["tsvector"],
                "matched_by_like": matches["like"],
                "matched_by_trgm": matches["trgm"],
                "missed_by_strategy": {
                    strategy: sorted(expected - set(matched)) for strategy, matched in matches.items()
                },
                "unexpected_by_strategy": {
                    strategy: sorted(set(matched) - expected) for strategy, matched in matches.items()
                },
            }
        )
    report = {
        "benchmark": "postgres_search_benchmark_contract",
        "fixture": "tests/fixtures/source_search/classical_chinese_passages.json",
        "opt_in_env_var": ENV_DSN,
        "default_tests_require_postgres": False,
        "strategies": list(STRATEGIES),
        "limitations": list(LIMITATIONS),
        "cases": rows,
    }
    _assert_no_forbidden_report_keys(report)
    return report


def run_psql_benchmark(dsn: str, psql: str = "psql") -> dict[str, Any]:
    completed = subprocess.run(
        [psql, "-X", "--no-psqlrc", "-q", "-t", "-A", dsn],
        input=render_benchmark_sql(),
        text=True,
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    report = json.loads(completed.stdout)
    explain = subprocess.run(
        [psql, "-X", "--no-psqlrc", "-q", "-t", "-A", dsn],
        input=render_explain_sql(),
        text=True,
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    report["explain_output_line_count"] = len([line for line in explain.stdout.splitlines() if line.strip()])
    _assert_no_forbidden_report_keys(report)
    return report


def integration_skip_reason(env: Mapping[str, str] | None = None, psql_path: str | None = None) -> str | None:
    if env is None:
        env = os.environ
    if not env.get(ENV_DSN):
        return f"{ENV_DSN} is not set"
    if psql_path is None:
        psql_path = shutil.which("psql")
    if not psql_path:
        return "psql is not installed or not on PATH"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run optional PostgreSQL search benchmark.")
    parser.add_argument("--sql-only", action="store_true", help="print executable benchmark SQL without connecting")
    parser.add_argument("--contract-report", action="store_true", help="print local report structure without connecting")
    parser.add_argument("--dsn", default=os.environ.get(ENV_DSN), help=f"PostgreSQL DSN, defaults to {ENV_DSN}")
    args = parser.parse_args(argv)

    if args.sql_only:
        sys.stdout.write(render_benchmark_sql())
        return 0
    if args.contract_report:
        sys.stdout.write(json.dumps(build_contract_report(), ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return 0

    reason = integration_skip_reason({ENV_DSN: args.dsn or ""})
    if reason:
        sys.stderr.write(f"skip: {reason}\n")
        return 2
    report = run_psql_benchmark(args.dsn or "")
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0


def _match_tsvector(passages: Sequence[Mapping[str, str]], normalized_query: str) -> list[str]:
    return sorted(
        passage["passage_code"]
        for passage in passages
        if normalized_query and normalized_query in set(passage["token_text"].split())
    )


def _match_like(passages: Sequence[Mapping[str, str]], normalized_query: str) -> list[str]:
    return sorted(
        passage["passage_code"]
        for passage in passages
        if normalized_query and normalized_query in passage["norm_text"]
    )


def _match_trgm_proxy(passages: Sequence[Mapping[str, str]], normalized_query: str) -> list[str]:
    if len(normalized_query) < 3:
        return []
    return _match_like(passages, normalized_query)


def _required_str(passage: Mapping[str, Any], key: str) -> str:
    value = passage.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"passage must include non-empty {key}")
    return value


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_array(values: Sequence[str]) -> str:
    if not values:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ", ".join(_sql_literal(value) for value in values) + "]::text[]"


def _assert_no_forbidden_report_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_REPORT_KEYS:
                raise ValueError(f"forbidden report key: {key}")
            _assert_no_forbidden_report_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_report_keys(child)


if __name__ == "__main__":
    raise SystemExit(main())
