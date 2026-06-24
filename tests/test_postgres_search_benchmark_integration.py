from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.source_ingest.postgres_search_benchmark import ENV_DSN, integration_skip_reason, load_dotenv, run_psql_benchmark


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_postgres_search_benchmark_runs_with_opt_in_dsn() -> None:
    load_dotenv()
    psql_path = shutil.which("psql")
    reason = integration_skip_reason(os.environ, psql_path)
    if reason:
        pytest.skip(reason)

    report = run_psql_benchmark(os.environ[ENV_DSN], psql=psql_path or "psql")

    assert report["opt_in_env_var"] == ENV_DSN
    assert report["default_tests_require_postgres"] is False
    assert report["strategies"] == ["tsvector", "like", "trgm"]
    assert report["cases"]
    assert any(case["case_id"] == "alias_liubang" for case in report["cases"])
    assert all("missed_by_strategy" in case for case in report["cases"])
    assert all("unexpected_by_strategy" in case for case in report["cases"])
