"""Read-only checks for explicit civilian-cost adjudications, not a grader.

Historical attribution and the independence of consequences require semantic
review. These checks prevent inconsistent projections and inferred high grades.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json

VERSION = "C4-CIVILIAN-COST-V1"
ROOT_PATH = Path("docs/评分结算/第二项治国净收益/财政民生")
AUDIT_PATH = ROOT_PATH / "06-主动民力成本去重审计.json"


def validate_record(row: Mapping[str, Any]) -> None:
    name = row.get("ruler_id", "synthetic")
    grade = row.get("destructive_amplification_grade", "")
    if not isinstance(grade, str) or not re.fullmatch(r"DA[0-6]", grade):
        raise ValueError(f"C4 invalid DA grade: {name}")
    tier = int(grade[-1])
    review = row.get("active_civilian_cost_review") or {}
    if review.get("version") != VERSION or review.get("status") != "REVIEWED":
        raise ValueError(f"C4 missing civilian-cost review: {name}")
    mode = review.get("evidence_mode")
    if mode not in {"DIRECT", "INFERRED", "NONE"}:
        raise ValueError(f"C4 invalid civilian evidence mode: {name}")
    if (mode == "NONE") != (tier == 0):
        raise ValueError(f"C4 residual admission disagrees with DA: {name}")
    if mode == "INFERRED" and tier != 1:
        raise ValueError(f"C4 inference exceeds the conservative floor: {name}")
    if review.get("military_input_double_charge") is not False:
        raise ValueError(f"C4 military input double charge: {name}")
    for field in ("choice_and_civilian_basis", "absorbed_and_excluded_basis"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError(f"C4 missing {field}: {name}")
    penalty = 4.5 * tier
    if row.get("destructive_amplification_penalty") != penalty:
        raise ValueError(f"C4 DA penalty mismatch: {name}")
    expected = round(max(-40, min(27, row["positive_score_retained"] - row["deterioration_penalty"] - penalty)), 1)
    if row.get("score") != expected or row.get("raw_score") != expected:
        raise ValueError(f"C4 signed score mismatch: {name}")


def verify_snapshot(workspace_root: Path) -> dict[str, Any]:
    source = load_json(workspace_root / ROOT_PATH / "04-C4正式结算.json")
    audit = load_json(workspace_root / AUDIT_PATH)
    rows = source["scores"]
    indexed = {row["ruler_id"]: row for row in rows}
    reviewed = {row["ruler_id"]: row for row in audit["records"]}
    if len(indexed) != len(rows) or len(reviewed) != len(audit["records"]) or set(indexed) != set(reviewed):
        raise ValueError("C4 civilian audit coverage mismatch")
    if audit["record_count"] != len(rows) or audit.get("contract_version") != VERSION:
        raise ValueError("C4 civilian audit metadata mismatch")
    scores = sorted((row["score"] for row in rows), reverse=True)
    markdown = (workspace_root / ROOT_PATH / "04-C4正式结算.md").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^### ", markdown)[1:]
    reader = {block.split("（", 1)[0]: block for block in blocks}
    if len(reader) != len(rows):
        raise ValueError("C4 reader coverage mismatch")
    for row in rows:
        validate_record(row)
        review = row["active_civilian_cost_review"]
        entry = reviewed[row["ruler_id"]]
        if entry["final_grade"] != row["destructive_amplification_grade"] or entry["final_penalty"] != row["destructive_amplification_penalty"]:
            raise ValueError(f"C4 civilian audit verdict mismatch: {row['ruler_id']}")
        for field in ("evidence_mode", "choice_and_civilian_basis", "absorbed_and_excluded_basis"):
            if entry[field] != review[field]:
                raise ValueError(f"C4 civilian audit basis mismatch: {row['ruler_id']}")
        if row["rank"] != scores.index(row["score"]) + 1 or row["main_band"] != "C4":
            raise ValueError(f"C4 score presentation mismatch: {row['ruler_id']}")
        block = reader.get(row["ruler_name"], "")
        if row["behavior_and_attribution"] not in block or f"C4净分**{row['score']:.1f}**" not in block:
            raise ValueError(f"C4 reader verdict mismatch: {row['ruler_id']}")
    return {"status": "PASS", "record_count": len(rows), "scope": "STRUCTURE_AND_PROJECTIONS_NOT_SEMANTIC_REGRADING"}
