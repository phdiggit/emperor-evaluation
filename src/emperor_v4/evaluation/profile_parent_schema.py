"""Compatibility readers for the shared profile parent-chain vocabulary."""
from __future__ import annotations

from typing import Any


def parent_chains(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return complete parent chains from either the canonical or legacy shape."""

    return list(record.get("parent_chains") or record.get("parents") or [])


def representative_parent_chains(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve representative IDs without copying complete chains into the record."""

    chains = parent_chains(record)
    representative_ids = record.get("representative_parent_ids")
    if representative_ids is None:
        return list(record.get("representative_parent_contexts") or chains)
    by_id = {str(parent.get("parent_id")): parent for parent in chains}
    missing = [parent_id for parent_id in representative_ids if str(parent_id) not in by_id]
    if missing:
        raise ValueError(f"代表父链无法回指完整父链: {missing}")
    return [by_id[str(parent_id)] for parent_id in representative_ids]
