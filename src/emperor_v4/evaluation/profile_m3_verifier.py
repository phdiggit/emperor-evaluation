from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m3_settlement import (
    GRADE_PROJECTION,
    M3_CONTRACT,
    M3_MARKDOWN,
    M3_SETTLEMENT,
    POOL,
    ROOT,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


PROJECT = ROOT / "config/project.yml"
MANIFEST = ROOT / "docs/评分结算/皇帝人物画像/00-已结算轴正式入口.json"


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    return json.loads(raw.decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_payload(settlement: dict[str, Any]) -> dict[str, Any]:
    included = {
        row["ruler_id"]
        for row in _load(POOL)["records"]
        if row["pool_status"] == "INCLUDED"
    }
    records = settlement["records"]
    if settlement["schema_version"] != "profile-m3-livelihood-finance-formal-settlement-v3":
        raise ValueError("M3 schema mismatch")
    if settlement["canonical_status"] != "FORMAL_CURRENT":
        raise ValueError("M3 is not formal current")
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("M3 formal settlement is not the declared patch authority")
    if any(key in settlement for key in ("adjudication_source", "supplement_adjudication_source")):
        raise ValueError("M3 still declares a generated adjudication authority")
    if settlement["contract_sha256"] != _sha(M3_CONTRACT):
        raise ValueError("M3 contract hash mismatch")
    if settlement["record_count"] != len(records) or len(records) != 184:
        raise ValueError("M3 record count mismatch")
    ids = [row["ruler_id"] for row in records]
    if len(set(ids)) != len(ids) or set(ids) != included:
        raise ValueError("M3 canonical pool coverage mismatch")
    if records != sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"])):
        raise ValueError("M3 stable order mismatch")

    expected_task_codes = {f"PROFILE-M3-{ruler_id}" for ruler_id in included}
    if {row["task_code"] for row in records} != expected_task_codes:
        raise ValueError("M3 task code coverage mismatch")
    for row in records:
        key = (row["axis_grade"], row["position"])
        if key not in GRADE_PROJECTION:
            raise ValueError(f"illegal M3 grade: {row['ruler_id']}")
        expected = GRADE_PROJECTION[key]
        if row["score_100"] != expected or row["radar_value"] != expected:
            raise ValueError(f"M3 score projection mismatch: {row['ruler_id']}")
        if row["formal_status"] != "FORMAL_CURRENT":
            raise ValueError(f"non-formal M3 record: {row['ruler_id']}")
        if row["axis_evidence_level"] not in {"E1", "E2", "E3"}:
            raise ValueError(f"illegal M3 evidence level: {row['ruler_id']}")
        if row["output_mode"] not in {"EPISODE_TAG", "BOUNDED_PROFILE", "FULL_GRADE"}:
            raise ValueError(f"illegal M3 output mode: {row['ruler_id']}")
        if not row["limitations"] or not row["public_adjudication"].strip():
            raise ValueError(f"incomplete M3 adjudication: {row['ruler_id']}")
        if not isinstance(row["parents"], list) or not isinstance(row["source_refs"], list):
            raise ValueError(f"invalid M3 lineage shape: {row['ruler_id']}")
        if "adjudication_ref" in row:
            raise ValueError(f"M3 record still delegates authority: {row['ruler_id']}")

    distribution = Counter(row["axis_grade"] for row in records)
    declared = settlement["summary"]["grade_distribution"]
    expected_distribution = {
        grade: distribution.get(grade, 0) for grade in ("G0", "G1", "G2", "G3", "G4", "G5")
    }
    if declared != expected_distribution:
        raise ValueError("M3 grade distribution mismatch")
    return {
        "status": "PASS",
        "record_count": len(records),
        "grade_distribution": expected_distribution,
        "evidence_limited_count": sum(
            row["score_status"] == "EVIDENCE_LIMITED" for row in records
        ),
    }


def verify() -> dict[str, Any]:
    settlement = _load(M3_SETTLEMENT)
    result = verify_payload(settlement)
    if M3_MARKDOWN.read_text(encoding="utf-8") != render_profile_markdown(settlement):
        raise ValueError("M3 Markdown differs from formal JSON")

    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))["profile_assessment"]
    entry = project["settled_axes"]["M3"]
    if ROOT / entry["json"] != M3_SETTLEMENT or ROOT / entry["markdown"] != M3_MARKDOWN:
        raise ValueError("M3 project entry mismatch")

    manifest = _load(MANIFEST)
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "M3")
    if axis["json_sha256"] != _sha(M3_SETTLEMENT):
        raise ValueError("M3 manifest JSON hash mismatch")
    if axis["markdown_sha256"] != _sha(M3_MARKDOWN):
        raise ValueError("M3 manifest Markdown hash mismatch")
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
