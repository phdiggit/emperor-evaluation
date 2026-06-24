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

from scripts.platform.jsonl_sources_target_mapper import apply_target_mapper, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_sources_target_mapper_writes_isolated_targets_and_cleans_schema(tmp_path: Path) -> None:
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    fixture_root = _write_fixture_root(tmp_path)
    schema = f"emperor_eval_sources_mapper_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_target_mapper(dsn, schema=schema, source_root=fixture_root, drop_schema_after=True)

        assert report["mode"] == "apply"
        assert report["schema"] == schema
        assert report["import_rows"] == 1
        assert report["staging_rows"] == 1
        assert report["src_host_rows"] == 1
        assert report["src_doc_rows"] == 1
        assert report["doc_rev_rows"] == 1
        assert report["passage_rows"] == 1
        assert report["blocked_relationship_rows"] == 1
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False


def _write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(
        data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-SOURCES-INTEGRATION-001",
                "title": "资治通鉴",
                "url": "https://zh.wikisource.org/wiki/example",
                "host": "wikisource",
                "quote": "帝召见群臣。",
                "context": "测试上下文",
                "raw_text": "帝召见群臣。旁文留作修订 payload。",
                "volume": "卷一",
                "location": "本纪",
            }
        ],
    )
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
