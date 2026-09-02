from __future__ import annotations

import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import (
    ROUTER_SCHEMA,
    load_json,
    write_json,
    write_polity_routed_json,
)


ROOT = Path(__file__).resolve().parents[1]


def test_polity_router_reconstructs_payload_and_supports_partial_load(tmp_path) -> None:
    path = tmp_path / "formal.json"
    payload = {
        "schema_version": "example-v1",
        "title": "示例",
        "records": [
            {"ruler_id": "A", "polity": "汉", "value": 1},
            {"ruler_id": "B", "polity": "唐", "value": 2},
            {"ruler_id": "C", "polity": "汉", "value": 3},
        ],
        "global_notes": [{"label": "跨朝代"}],
    }

    manifest = write_polity_routed_json(path, payload, ruler_polities={})

    assert manifest["schema_version"] == ROUTER_SCHEMA
    assert load_json(path) == payload
    partial = load_json(path, polities=["汉"])
    assert partial["records"] == [payload["records"][0], payload["records"][2]]
    assert partial["global_notes"] == payload["global_notes"]


def test_polity_router_uses_canonical_ruler_mapping(tmp_path) -> None:
    path = tmp_path / "formal.json"
    payload = {"records": [{"ruler_id": "A", "value": 1}]}

    write_polity_routed_json(path, payload, ruler_polities={"A": "汉"})

    assert load_json(path) == payload


def test_polity_router_rejects_unknown_partial_route(tmp_path) -> None:
    path = tmp_path / "formal.json"
    write_polity_routed_json(
        path,
        {"records": [{"ruler_id": "A", "polity": "汉"}]},
        ruler_polities={},
    )

    with pytest.raises(ValueError, match="不存在的朝代路由"):
        load_json(path, polities=["宋"])


def test_normal_json_remains_supported(tmp_path) -> None:
    path = tmp_path / "normal.json"
    payload = {"schema_version": "normal-v1", "records": [1, 2]}
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_json(path) == payload


def test_write_json_preserves_existing_router(tmp_path) -> None:
    path = tmp_path / "formal.json"
    first = {"records": [{"ruler_id": "A", "polity": "汉", "value": 1}]}
    second = {"records": [{"ruler_id": "A", "polity": "汉", "value": 2}]}
    write_polity_routed_json(path, first, ruler_polities={})

    write_json(path, second, ruler_polities={})

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == ROUTER_SCHEMA
    assert load_json(path) == second


def test_checked_in_formal_routers_are_complete_and_exclude_audits() -> None:
    manifests = []
    for path in (ROOT / "docs/评分结算").rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("schema_version") == ROUTER_SCHEMA:
            manifests.append(path)

    assert len(manifests) == 22
    assert not any(any(marker in path.name for marker in ("审计", "复核", "验收", "报告")) for path in manifests)
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        full = load_json(path)
        assert list(full) == manifest["payload_key_order"]
        assert manifest["routes"]
        assert all((path.parent / route["path"]).is_file() for route in manifest["routes"])
        first_polity = manifest["routes"][0]["polity"]
        partial = load_json(path, polities=[first_polity])
        for collection in manifest["collections"]:
            assert len(partial[collection]) == sum(
                route["collection_counts"].get(collection, 0)
                for route in manifest["routes"]
                if route["polity"] == first_polity
            )
