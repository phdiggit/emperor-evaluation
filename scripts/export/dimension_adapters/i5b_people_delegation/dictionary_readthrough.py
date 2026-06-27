from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parent / "i5b_rule_display_dictionary_snapshot_v1.json"
SNAPSHOT_VERSION = "i5b-rule-display-dictionary-snapshot-v1"
PACKAGE_VERSION = "i5b-runtime-dictionary-readthrough-shim-v1"
ALLOWED_STATUSES = {"active", "deprecated", "draft"}
REQUIRED_FIELDS = (
    "snapshot_version",
    "scope",
    "rule_id",
    "dictionary_type",
    "locale",
    "status",
    "effective_from",
    "gate_source",
    "digest_sha256",
    "payload",
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def stable_json_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_dictionary_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_dictionary_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if snapshot.get("snapshot_version") != SNAPSHOT_VERSION:
        errors.append("snapshot.snapshot_version_mismatch")
    if snapshot.get("scope") != "i5b_people_delegation":
        errors.append("snapshot.scope_mismatch")
    if not snapshot.get("gate_source"):
        errors.append("snapshot.gate_source_missing")
    if snapshot.get("status") not in ALLOWED_STATUSES:
        errors.append("snapshot.status_invalid")

    items = snapshot.get("items")
    if not isinstance(items, list) or not items:
        errors.append("snapshot.items_missing")
        return errors

    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(items):
        path = f"items[{index}]"
        if not isinstance(item, Mapping):
            errors.append(f"{path}.not_object")
            continue

        for field in REQUIRED_FIELDS:
            if field not in item:
                errors.append(f"{path}.{field}_missing")

        key = (str(item.get("scope", "")), str(item.get("rule_id", "")), str(item.get("locale", "")))
        if key in seen:
            errors.append(f"{path}.rule_id_duplicate")
        seen.add(key)

        if item.get("snapshot_version") != SNAPSHOT_VERSION:
            errors.append(f"{path}.snapshot_version_mismatch")
        if not item.get("scope"):
            errors.append(f"{path}.scope_missing")
        if not item.get("rule_id"):
            errors.append(f"{path}.rule_id_missing")
        if not item.get("dictionary_type"):
            errors.append(f"{path}.dictionary_type_missing")
        if not item.get("locale"):
            errors.append(f"{path}.locale_missing")
        if item.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{path}.status_invalid")
        if not DATE_RE.fullmatch(str(item.get("effective_from", ""))):
            errors.append(f"{path}.effective_from_invalid")
        if not item.get("gate_source"):
            errors.append(f"{path}.gate_source_missing")

        digest = str(item.get("digest_sha256", ""))
        payload = item.get("payload")
        if not SHA256_RE.fullmatch(digest):
            errors.append(f"{path}.digest_sha256_invalid")
        if not isinstance(payload, Mapping):
            errors.append(f"{path}.payload_missing")
            continue
        if digest and digest != stable_json_sha256(payload):
            errors.append(f"{path}.digest_sha256_mismatch")
    return errors


def load_validated_dictionary_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    snapshot = load_dictionary_snapshot(path)
    errors = validate_dictionary_snapshot(snapshot)
    if errors:
        raise ValueError(f"I5B dictionary snapshot validation failed: {', '.join(errors)}")
    return snapshot


def dictionary_items_by_type(snapshot: Mapping[str, Any] | None = None) -> dict[str, tuple[dict[str, Any], ...]]:
    source = snapshot if snapshot is not None else load_validated_dictionary_snapshot()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in source["items"]:
        grouped.setdefault(str(item["dictionary_type"]), []).append(deepcopy(dict(item)))
    return {key: tuple(items) for key, items in sorted(grouped.items())}


def dictionary_item_by_rule_id(rule_id: str, snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = snapshot if snapshot is not None else load_validated_dictionary_snapshot()
    for item in source["items"]:
        if item["rule_id"] == rule_id:
            return deepcopy(dict(item))
    raise KeyError(rule_id)


def values_by_symbol(rule_id: str, snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item = dictionary_item_by_rule_id(rule_id, snapshot)
    values = item["payload"].get("values_by_symbol")
    if not isinstance(values, Mapping):
        raise KeyError(f"{rule_id}: payload.values_by_symbol")
    return deepcopy(dict(values))


def source_symbols_by_dictionary_type(snapshot: Mapping[str, Any] | None = None) -> dict[str, tuple[str, ...]]:
    grouped = dictionary_items_by_type(snapshot)
    result: dict[str, tuple[str, ...]] = {}
    for dictionary_type, items in grouped.items():
        symbols: list[str] = []
        for item in items:
            payload = item["payload"]
            symbols.extend(str(symbol) for symbol in payload.get("source_symbols", []))
        result[dictionary_type] = tuple(sorted(symbols))
    return result
