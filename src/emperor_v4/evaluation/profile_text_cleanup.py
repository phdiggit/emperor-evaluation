"""Perform explicitly authorized, semantics-preserving cleanup of formal profile text."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import sys

import yaml

from .formal_json_store import load_json, load_ruler_polities, write_json

ROOT = Path(__file__).resolve().parents[3]
REPAIR_FILE = ROOT / "config/profile/profile-text-repairs.json"
EDITABLE_FIELDS = {"typical_pattern", "counterpattern", "grade_basis", "position_basis", "limitations"}
PROTECTED_FIELDS = {
    "axis_grade", "position", "score_100", "radar_value", "axis_evidence_level",
    "output_mode", "confidence", "score_status", "formal_status", "adjudication_state",
}


def _norm(text: str) -> str:
    return re.sub(r"[\s；;。,.，：:（）()【】\[\]“”\"'`]+", "", text or "")


def _texts(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [x for item in value for x in _texts(item)]
    return []


def prune_redundant_limitations(record: dict) -> int:
    """Remove only limitation entries repeated verbatim in another formal text field."""
    limitations = record.get("limitations")
    if not isinstance(limitations, list):
        return 0
    reference = set()
    for field in ("typical_pattern", "counterpattern", "grade_basis", "position_basis"):
        reference.update(_norm(text) for text in _texts(record.get(field)) if _norm(text))
    kept = []
    removed = 0
    for item in limitations:
        if isinstance(item, str) and _norm(item) in reference:
            removed += 1
            continue
        kept.append(item)
    if removed:
        record["limitations"] = kept
    return removed


def load_repairs() -> list[dict]:
    payload = json.loads(REPAIR_FILE.read_text(encoding="utf-8"))
    repairs = payload.get("repairs")
    if not isinstance(repairs, list):
        raise ValueError("profile text repairs must contain a repairs list")
    return repairs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write authorized cleanup back to routed formal JSON")
    args = parser.parse_args(argv)

    config = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    axis_specs = config["profile_assessment"]["settled_axes"]
    payloads = {}
    records = {}
    snapshots = {}
    changed_axes = set()

    for axis, spec in axis_specs.items():
        path = ROOT / spec["json"]
        payload = load_json(path)
        payloads[axis] = (path, payload)
        records[axis] = {str(row.get("ruler_id")): row for row in payload.get("records", [])}
        snapshots[axis] = {
            str(row.get("ruler_id")): {key: row.get(key) for key in PROTECTED_FIELDS}
            for row in payload.get("records", [])
        }

    repair_count = 0
    for repair in load_repairs():
        axis = str(repair.get("axis") or "")
        ruler_id = str(repair.get("ruler_id") or "")
        field = str(repair.get("field") or "")
        if axis not in records:
            raise ValueError(f"unknown repair axis: {axis}")
        if field not in EDITABLE_FIELDS or field in PROTECTED_FIELDS:
            raise ValueError(f"repair field is not reader-facing text: {field}")
        record = records[axis].get(ruler_id)
        if record is None:
            raise ValueError(f"repair ruler not found: {axis}/{ruler_id}")
        expected = repair.get("expected_old")
        if record.get(field) != expected:
            raise ValueError(f"stale repair source: {axis}/{ruler_id}/{field}")
        replacement = repair.get("replacement")
        if not isinstance(replacement, (str, list, dict)):
            raise ValueError(f"invalid repair replacement: {axis}/{ruler_id}/{field}")
        record[field] = replacement
        changed_axes.add(axis)
        repair_count += 1

    duplicate_limitations_removed = 0
    touched_records = 0
    for axis, axis_records in records.items():
        for record in axis_records.values():
            removed = prune_redundant_limitations(record)
            if removed:
                duplicate_limitations_removed += removed
                touched_records += 1
                changed_axes.add(axis)

    for axis, axis_records in records.items():
        for ruler_id, record in axis_records.items():
            after = {key: record.get(key) for key in PROTECTED_FIELDS}
            if after != snapshots[axis][ruler_id]:
                raise ValueError(f"protected adjudication fields changed: {axis}/{ruler_id}")

    print(
        "profile-text-cleanup: "
        f"repairs={repair_count} duplicate_limitations_removed={duplicate_limitations_removed} "
        f"records_touched={touched_records} axes_changed={','.join(sorted(changed_axes)) or 'none'}"
    )

    if args.apply and changed_axes:
        ruler_polities = load_ruler_polities(ROOT)
        for axis in sorted(changed_axes):
            path, payload = payloads[axis]
            write_json(path, payload, ruler_polities=ruler_polities)
        print("profile-text-cleanup: written")
    elif changed_axes:
        print("profile-text-cleanup: dry-run only; use --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
