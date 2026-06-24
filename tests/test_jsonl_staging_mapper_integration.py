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
from scripts.platform.jsonl_staging_mapper import apply_staging_mapper, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_jsonl_staging_mapper_writes_staging_rows_and_cleans_schema() -> None:
    load_dotenv()
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    schema = f"emperor_eval_staging_mapper_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_staging_mapper(dsn, schema=schema, source_root=ROOT, drop_schema_after=True)

        assert report["mode"] == "apply"
        assert report["schema"] == schema
        assert report["import_rows"] > 0
        assert report["staging_rows"] == report["import_rows"]
        assert report["reference_risk_rows"] > 0
        assert report["unknown_field_rows"] >= 0
        assert report["validation_error_rows"] == 0
        assert report["staging_only_rows"] > 0
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False
