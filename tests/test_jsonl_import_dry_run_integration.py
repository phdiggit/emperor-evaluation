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
from scripts.platform.jsonl_import_dry_run import apply_dry_run, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "jsonl_import"
pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_jsonl_import_dry_run_writes_audit_rows_and_cleans_schema() -> None:
    load_dotenv()
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    schema = f"emperor_eval_import_dry_run_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_dry_run(dsn, schema=schema, source_root=FIXTURE_ROOT, drop_schema_after=True)

        assert report["schema"] == schema
        assert report["rows_total"] == 4
        assert report["rows_invalid_json"] == 1
        assert report["would_write_import_rows"] == 4
        assert report["inserted_import_rows"] == 4
        assert report["database_report"]["row_count"] == 4
        assert report["database_report"]["import_rows"] == 4
        assert report["database_report"]["error_rows"] == 1
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False
