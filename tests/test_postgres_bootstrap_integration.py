from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import load_dotenv
from scripts.platform.postgres_bootstrap import (
    REQUIRED_TABLES,
    apply_bootstrap,
    drop_schema,
    inspect_bootstrap_contract,
    integration_skip_reason,
    resolve_dsn,
    schema_exists,
)


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_postgres_bootstrap_applies_schema_contract_and_cleans_up() -> None:
    load_dotenv()
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    schema = f"emperor_eval_bootstrap_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        apply_bootstrap(dsn, schema)
        report = inspect_bootstrap_contract(dsn, schema)

        assert report["schema_exists"] is True
        assert set(report["required_tables"]) >= set(REQUIRED_TABLES)
        assert report["pg_trgm_available"] is True
        assert report["passages_search_vec_generated"] is True
        assert report["passage_search_gin_index"] is True
        assert report["passage_norm_trgm_index"] is True
        assert report["jobs_idem_unique_constraint"] is True
        assert report["outbox_partial_index"] is True
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False
