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

from scripts.platform.jsonl_evidence_cards_target_mapper import apply_target_mapper, integration_skip_reason, resolve_dsn
from scripts.platform.postgres_bootstrap import drop_schema, schema_exists


pytestmark = [pytest.mark.db, pytest.mark.integration]


def test_evidence_cards_target_mapper_writes_isolated_targets_and_cleans_schema(tmp_path: Path) -> None:
    resolved = resolve_dsn(env=os.environ)
    reason = integration_skip_reason(resolved)
    if reason:
        pytest.skip(reason)

    fixture_root = _write_fixture_root(tmp_path)
    schema = f"emperor_eval_evd_cards_mapper_pytest_{uuid4().hex[:8]}"
    dsn = resolved.dsn or ""

    try:
        report = apply_target_mapper(dsn, schema=schema, source_root=fixture_root, drop_schema_after=True)

        assert report["mode"] == "apply"
        assert report["schema"] == schema
        assert report["import_rows"] == 1
        assert report["staging_rows"] == 1
        assert report["evd_card_rows"] == 1
        assert report["blocked_source_link_rows"] == 1
        assert report["blocked_cluster_link_rows"] == 1
        assert report["manual_review_rows"] == 1
        assert report["dropped"] is True
        assert report["schema_exists_after_drop"] is False
    finally:
        drop_schema(dsn, schema)

    assert schema_exists(dsn, schema) is False


def _write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(
        data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-CARDS-INTEGRATION-001",
                "person": "测试皇帝",
                "item": "第五项",
                "subitem": "第五项B",
                "source_id": "SRC-CARDS-INTEGRATION-001",
                "linked_source_ids": ["SRC-CARDS-INTEGRATION-001"],
                "polarity": "positive",
                "verification_status": "source_verified",
                "adjudication_status": "pending_human_adjudication",
                "notes": "只进入 payload。",
                "cluster_candidate_id": "CLUSTER-CARDS-INTEGRATION-001",
                "cluster_role": "core",
                "evidence_role": "primary",
                "trigger_family": "测试触发",
                "trigger_terms": ["召见"],
                "upper_bound_flag": "diagnostic",
            }
        ],
    )
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
