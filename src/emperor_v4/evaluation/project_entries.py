"""Validate current machine entries and the small reader-facing entry pages."""
from __future__ import annotations

from pathlib import Path
import json
import re
from urllib.parse import unquote
import yaml

from emperor_v4.evaluation.formal_json_store import load_json


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
    for axis, entry in profile["settled_axes"].items():
        for key in ("json", "markdown"):
            if (root / entry[key]).resolve() != (manifest_path.parent / by_axis[axis][key]).resolve():
                raise ValueError(f"Profile entry drift: {axis}.{key}")
        # Entry validation needs manifest metadata, not every polity's records.
        raw = json.loads((root / entry["json"]).read_text(encoding="utf-8"))
        payload = raw.get("payload_metadata", raw)
        if entry.get("contract_version", payload.get("contract_version")) != payload.get("contract_version"):
            raise ValueError(f"Profile contract version drift: {axis}")
        for ref in by_axis[axis].get("audit_jsons", []):
            candidates = [manifest_path.parent / ref, (root / entry["json"]).parent / ref]
            if not any(path.is_file() for path in candidates):
                raise ValueError(f"Current profile evidence entry missing: {axis}: {ref}")
    for rel in ("README.md", "docs/README.md", "docs/评分结算/README.md"):
        path = root / rel
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            local = unquote(target.split("#", 1)[0].strip("<>"))
            if not (path.parent / local).exists():
                raise ValueError(f"Broken reader entry: {rel}: {target}")
    return {"status": "PASS", "project_entry_count": len(checked), "profile_axis_count": len(by_axis), "reader_entry_pages": 3}
