"""Load the profile-axis registry from the project configuration.

The project configuration is the source of paths and axis order.  This module
only exposes that registry; it does not adjudicate or rewrite profile data.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

from emperor_v4.evaluation.formal_json_store import load_json, write_json


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "config" / "project.yml"
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
PROFILE_ROOT_RELATIVE = "docs/评分结算/皇帝人物画像/"


def load_project_config() -> dict[str, Any]:
    """Return the project configuration without caching mutable config."""

    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))
    if not isinstance(project, dict):
        raise ValueError("project.yml不是对象")
    return project


def load_profile_config() -> dict[str, Any]:
    """Return the configured profile registry without caching mutable config."""

    profile = load_project_config().get("profile_assessment")
    if not isinstance(profile, dict):
        raise ValueError("project.yml缺少profile_assessment注册")
    return profile


def profile_axis_order(config: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Return the single configured axis order and validate its coverage."""

    profile = config or load_profile_config()
    order = tuple(profile.get("axis_order") or ())
    settled_axes = profile.get("settled_axes") or {}
    if not order:
        raise ValueError("profile_assessment缺少axis_order")
    if len(order) != len(set(order)):
        raise ValueError("axis_order包含重复画像轴")
    if set(order) != set(settled_axes):
        raise ValueError("axis_order与settled_axes覆盖不一致")
    radar_order = tuple((profile.get("radar_samples") or {}).get("axis_order") or ())
    if radar_order and radar_order != order:
        raise ValueError("axis_order与radar_samples.axis_order不一致")
    return order


def profile_axis_files(config: dict[str, Any] | None = None) -> dict[str, str]:
    """Return configured JSON paths relative to the profile result directory."""

    profile = config or load_profile_config()
    files: dict[str, str] = {}
    for axis in profile_axis_order(profile):
        configured = str((profile["settled_axes"].get(axis) or {}).get("json") or "")
        if not configured.startswith(PROFILE_ROOT_RELATIVE):
            raise ValueError(f"{axis}正式JSON路径必须位于画像正式目录: {configured}")
        relative = configured[len(PROFILE_ROOT_RELATIVE):].replace("\\", "/")
        if PurePosixPath(relative).parts[:1] != (axis,):
            raise ValueError(f"{axis}正式JSON路径必须以轴目录开头: {configured}")
        files[axis] = relative
    return files


def profile_axis_entry(axis: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return one configured axis entry with a stable error for unknown axes."""

    profile = config or load_profile_config()
    entry = (profile.get("settled_axes") or {}).get(axis)
    if not isinstance(entry, dict):
        raise KeyError(f"未注册画像轴: {axis}")
    return entry


def _profile_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not normalized.startswith(PROFILE_ROOT_RELATIVE):
        raise ValueError(f"画像正式路径不在正式目录内: {value}")
    return normalized[len(PROFILE_ROOT_RELATIVE):]


def _audit_entries(value: Any, axis: str) -> list[dict[str, str]]:
    """Normalize audit descriptors to manifest-root-relative paths."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{axis}审计入口必须是列表")
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{axis}审计入口必须使用audit_kind/path对象")
        audit_kind = str(item.get("audit_kind") or "").strip()
        path = str(item.get("path") or "").replace("\\", "/").strip()
        parts = PurePosixPath(path).parts
        if not audit_kind or not path:
            raise ValueError(f"{axis}审计入口缺少audit_kind或path")
        if PurePosixPath(path).is_absolute() or ".." in parts or parts[:1] != (axis,):
            raise ValueError(f"{axis}审计路径必须相对于画像入口且以轴目录开头: {path}")
        key = (audit_kind, path)
        if key in seen:
            raise ValueError(f"{axis}审计入口重复: {audit_kind}/{path}")
        seen.add(key)
        entries.append({"audit_kind": audit_kind, "path": path})
    return entries


def _axis_manifest(profile: dict[str, Any], axis: str) -> dict[str, Any]:
    entry = profile_axis_entry(axis, profile)
    payload = load_json(ROOT / entry["json"])
    axis_manifest: dict[str, Any] = {
        "axis_code": axis,
        "axis_name": entry["name"],
        "status": "FORMAL_CURRENT",
        "contract": entry["contract"],
        "axis_contract_version": entry["axis_contract_version"],
        "payload_schema_version": entry["payload_schema_version"],
        "axis_kind": entry["axis_kind"],
        "authority_mode": entry["authority_mode"],
        "reader_view_mode": entry["reader_view_mode"],
        "verify_command": entry["verify_command"],
        "record_count": payload["record_count"],
        "json": _profile_relative_path(entry["json"]),
        "markdown": _profile_relative_path(entry["markdown"]),
        "audit_markdowns": list(entry.get("audit_markdowns", [])),
        "audit_jsons": _audit_entries(entry.get("audit_jsons"), axis),
        "record_order_policy": payload["record_order_policy"],
    }
    for optional_key in ("input_scope", "formalization_note"):
        if optional_key in entry:
            axis_manifest[optional_key] = entry[optional_key]
    return axis_manifest


def _validate_selected_axes(
    axes: Iterable[str] | None,
    profile: dict[str, Any],
) -> tuple[str, ...]:
    configured = profile_axis_order(profile)
    selected = configured if axes is None else tuple(dict.fromkeys(axes))
    unknown = set(selected) - set(configured)
    if unknown:
        raise ValueError(f"未注册画像轴: {sorted(unknown)}")
    if not selected:
        raise ValueError("至少需要一个画像轴")
    return tuple(axis for axis in configured if axis in selected)


def build_profile_manifest() -> dict[str, Any]:
    """Project the complete configured axis registry to the manifest."""

    project = load_project_config()
    profile = project["profile_assessment"]
    axes = [_axis_manifest(profile, axis) for axis in profile_axis_order(profile)]
    return {
        "schema_version": "emperor-profile-formal-axis-manifest-v1",
        "contract_version": profile["contract_version"],
        "contract": profile["contract"],
        "data_contract": profile["data_contract"],
        "canonical_status": "FORMAL_CURRENT",
        "population_count": profile["population_count"],
        "settled_axis_count": len(axes),
        "unsettled_axis_count": 0,
        "profile_total_enabled": profile["profile_total_enabled"],
        "profile_ranking_enabled": profile["profile_ranking_enabled"],
        "composite_ranking_write": profile["composite_ranking_write"],
        "database_write": profile["database_write"],
        "canonical_pool": project["canonical_ruler_pool"]["json"],
        "axes": axes,
    }


def write_profile_manifest(axes: Iterable[str] | None = None) -> Path:
    """Write all or selected axis entries from the project registry."""

    profile = load_profile_config()
    selected = _validate_selected_axes(axes, profile)
    path = ROOT / profile["manifest_json"]
    if axes is None:
        manifest = build_profile_manifest()
    else:
        manifest = load_json(path)
        existing = {entry["axis_code"]: entry for entry in manifest["axes"]}
        missing = set(profile_axis_order(profile)) - set(existing)
        if missing:
            raise ValueError(f"现有画像manifest缺少轴: {sorted(missing)}")
        for axis in selected:
            existing[axis] = _axis_manifest(profile, axis)
        manifest["axes"] = [existing[axis] for axis in profile_axis_order(profile)]
    write_json(path, manifest)
    return path
