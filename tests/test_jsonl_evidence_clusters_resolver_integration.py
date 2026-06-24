from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_evidence_clusters_resolver import apply_resolver, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_jsonl_evidence_clusters_resolver_writes_relaxed_rows_and_cleans_schema() -> None:
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    schema = f"emperor_eval_clusters_resolver_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_resolver(dsn, schema=schema, source_root=ROOT, drop_schema_after=True)

        assert report["mode"] == "apply"
        assert report["schema"] == schema
        assert report["import_rows"] > 0
        assert report["staging_rows"] == report["import_rows"]
        assert report["cluster_rows"] > 0
        assert report["cluster_evd_candidate_rows"] > 0
        assert report["blocked_cluster_evd_rows"] > 0
        assert report["manual_review_rows"] > 0
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False
