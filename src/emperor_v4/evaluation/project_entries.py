"""Validate current machine entries and the small reader-facing entry pages."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import json
import re
from urllib.parse import unquote
import yaml

from emperor_v4.evaluation.formal_json_store import load_json


def _manifest_audit_entries(manifest_path: Path, axis: str, value: object) -> list[dict[str, str]]:
    """Validate audit descriptors and resolve them from the manifest directory."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Profile audit registry must be a list: {axis}")
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    manifest_root = manifest_path.parent.resolve()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Profile audit registry must use audit_kind/path objects: {axis}")
        audit_kind = str(item.get("audit_kind") or "").strip()
        ref = str(item.get("path") or "").replace("\\", "/").strip()
        parts = PurePosixPath(ref).parts
        if not audit_kind or not ref:
            raise ValueError(f"Profile audit entry is incomplete: {axis}")
        if PurePosixPath(ref).is_absolute() or ".." in parts or parts[:1] != (axis,):
            raise ValueError(f"Profile audit path must be manifest-root-relative and axis-scoped: {axis}: {ref}")
        resolved = (manifest_root / Path(*parts)).resolve()
        try:
            resolved.relative_to(manifest_root)
        except ValueError as exc:
            raise ValueError(f"Profile audit path escapes the manifest directory: {axis}: {ref}") from exc
        if not resolved.is_file():
            raise ValueError(f"Current profile evidence entry missing: {axis}: {ref}")
        key = (audit_kind, ref)
        if key in seen:
            raise ValueError(f"Duplicate profile audit entry: {axis}: {audit_kind}/{ref}")
        seen.add(key)
        entries.append({"audit_kind": audit_kind, "path": ref})
    return entries


def verify(root: Path) -> dict:
    project = yaml.safe_load((root / "config/project.yml").read_text(encoding="utf-8"))
    checked = set()

    def check(value):
        if isinstance(value, dict):
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, str) and value.startswith(("docs/", "config/", "src/")):
            path = root / value.split("#", 1)[0]
            if not path.exists():
                raise ValueError(f"Project entry does not exist: {value}")
            checked.add(value)

    check(project)
    profile = project["profile_assessment"]
    manifest_path = root / profile["manifest_json"]
    manifest = load_json(manifest_path)
    by_axis = {r["axis_code"]: r for r in manifest["axes"]}
    if set(by_axis) != set(profile["settled_axes"]):
        raise ValueError("Project and profile manifest axis sets differ")
    if tuple(profile.get("axis_order") or ()) != tuple(axis["axis_code"] for axis in manifest["axes"]):
        raise ValueError("Project axis_order and profile manifest order differ")
    for key in ("contract", "data_contract"):
        path = root / str(profile.get(key) or "")
        if not path.is_file():
            raise ValueError(f"Profile {key} does not exist: {profile.get(key)}")
    if manifest.get("contract") != profile.get("contract") or manifest.get("data_contract") != profile.get("data_contract"):
        raise ValueError("Profile manifest common contract entries differ from project config")
    for axis, entry in profile["settled_axes"].items():
        for key in ("json", "markdown"):
            manifest_ref = str(by_axis[axis][key]).replace("\\", "/")
            if PurePosixPath(manifest_ref).parts[:1] != (axis,):
                raise ValueError(f"Profile {key} must be stored below its axis directory: {axis}: {manifest_ref}")
            if (root / entry[key]).resolve() != (manifest_path.parent / by_axis[axis][key]).resolve():
                raise ValueError(f"Profile entry drift: {axis}.{key}")
        required_metadata = (
            "contract", "axis_contract_version", "payload_schema_version", "axis_kind",
            "authority_mode", "reader_view_mode", "verify_command",
        )
        if any(not entry.get(key) for key in required_metadata):
            raise ValueError(f"Profile registry metadata incomplete: {axis}")
        if any(by_axis[axis].get(key) != entry.get(key) for key in required_metadata):
            raise ValueError(f"Profile manifest metadata drift: {axis}")
        expected_audits = _manifest_audit_entries(manifest_path, axis, entry.get("audit_jsons", []))
        actual_audits = _manifest_audit_entries(manifest_path, axis, by_axis[axis].get("audit_jsons", []))
        if expected_audits != actual_audits:
            raise ValueError(f"Profile manifest audit registry drift: {axis}")
        if entry.get("input_scope") != by_axis[axis].get("input_scope"):
            raise ValueError(f"Profile manifest input scope drift: {axis}")
        if not (root / entry["contract"]).is_file():
            raise ValueError(f"Profile contract does not exist: {axis}: {entry['contract']}")
        # Entry validation needs manifest metadata, not every polity's records.
        raw = json.loads((root / entry["json"]).read_text(encoding="utf-8"))
        payload = raw.get("payload_metadata", raw)
        if entry["axis_contract_version"] != payload.get("contract_version"):
            raise ValueError(f"Profile axis contract version drift: {axis}")
        if entry["payload_schema_version"] != payload.get("schema_version"):
            raise ValueError(f"Profile payload schema version drift: {axis}")
        if by_axis[axis].get("record_count") != payload.get("record_count"):
            raise ValueError(f"Profile manifest record count drift: {axis}")
    reader_pages = ["README.md", "docs/README.md", "docs/评分结算/README.md"]
    manifest_markdown = str(profile.get("manifest_markdown") or "")
    if manifest_markdown:
        reader_pages.append(manifest_markdown)
    for rel in dict.fromkeys(reader_pages):
        path = root / rel
        if not path.is_file():
            raise ValueError(f"Reader entry page does not exist: {rel}")
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            local = unquote(target.split("#", 1)[0].strip("<>"))
            if not (path.parent / local).exists():
                raise ValueError(f"Broken reader entry: {rel}: {target}")
    return {"status": "PASS", "project_entry_count": len(checked), "profile_axis_count": len(by_axis), "reader_entry_pages": len(dict.fromkeys(reader_pages))}
