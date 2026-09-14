from __future__ import annotations

import json

import pytest

from emperor_v4.evaluation.formal_json_store import (
    ROUTER_SCHEMA,
    load_json,
    write_json,
    write_polity_routed_json,
)


def test_polity_router_reconstructs_payload_and_supports_partial_load(tmp_path):
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


def test_polity_router_uses_canonical_ruler_mapping(tmp_path):
    path = tmp_path / "formal.json"
    payload = {"records": [{"ruler_id": "A", "value": 1}]}

    write_polity_routed_json(path, payload, ruler_polities={"A": "汉"})

    assert load_json(path) == payload


def test_polity_router_rejects_unknown_partial_route(tmp_path):
    path = tmp_path / "formal.json"
    write_polity_routed_json(
        path,
        {"records": [{"ruler_id": "A", "polity": "汉"}]},
        ruler_polities={},
    )

    with pytest.raises(ValueError, match="不存在的朝代路由"):
        load_json(path, polities=["宋"])


def test_normal_json_remains_supported(tmp_path):
    path = tmp_path / "normal.json"
    payload = {"schema_version": "normal-v1", "records": [1, 2]}
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_json(path) == payload


def test_write_json_preserves_existing_router(tmp_path):
    path = tmp_path / "formal.json"
    first = {"records": [{"ruler_id": "A", "polity": "汉", "value": 1}]}
    second = {"records": [{"ruler_id": "A", "polity": "汉", "value": 2}]}
    write_polity_routed_json(path, first, ruler_polities={})

    write_json(path, second, ruler_polities={})

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == ROUTER_SCHEMA
    assert load_json(path) == second
