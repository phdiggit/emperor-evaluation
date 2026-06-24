from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_anchors_target_mapper import apply_target_mapper, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists
from tests.test_anchors_resolver_contract import write_fixture_root


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_anchors_target_mapper_writes_isolated_targets_and_cleans_schema(tmp_path: Path) -> None:
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    fixture_root = write_fixture_root(tmp_path)
    schema = f"emperor_eval_anchors_mapper_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_target_mapper(dsn, schema=schema, source_root=fixture_root, drop_schema_after=True)

        assert report["mode"] == "apply"
        assert report["schema"] == schema
        assert report["import_rows"] == 7
        assert report["staging_rows"] == 7
        assert report["anchor_rows"] == 4
        assert report["anchor_link_candidate_rows"] == 7
        assert report["blocked_anchor_link_rows"] == 7
        assert report["manual_review_rows"] == 2
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False
