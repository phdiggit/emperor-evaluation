from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import load_dotenv
from scripts.platform.jsonl_query_search_target_mapper import apply_target_mapper, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_query_search_target_mapper_writes_isolated_targets_and_cleans_schema(tmp_path: Path) -> None:
    load_dotenv()
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    fixture_root = _write_fixture_root(tmp_path)
    schema = f"emperor_eval_qsearch_mapper_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_target_mapper(dsn, schema=schema, source_root=fixture_root, drop_schema_after=True)

        assert report["mode"] == "apply"
        assert report["schema"] == schema
        assert report["import_rows"] == 2
        assert report["staging_rows"] == 2
        assert report["query_profile_rows"] == 1
        assert report["search_task_rows"] == 1
        assert report["unresolved_reference_rows"] == 2
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False


def _write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(
        data_dir / "query_profiles.jsonl",
        [
            {
                "query_profile_id": "QRY-INTEGRATION-001",
                "profile_scope": "item",
                "status": "active",
                "item": "第五项",
                "subitem": "B",
                "person": "刘秀",
                "query_terms": ["宽政", "民生"],
                "inherits_from": "QRY-BASE-001",
            }
        ],
    )
    _write_jsonl(
        data_dir / "search_logs.jsonl",
        [
            {
                "search_id": "SRCH-INTEGRATION-001",
                "query": "刘秀 宽政 民生",
                "status": "ready",
                "query_terms": ["刘秀", "宽政"],
                "query_profile_id": "QRY-INTEGRATION-001",
                "linked_source_ids": ["SRC-INTEGRATION-001"],
                "linked_evidence_ids": ["EVD-INTEGRATION-001"],
            }
        ],
    )
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
