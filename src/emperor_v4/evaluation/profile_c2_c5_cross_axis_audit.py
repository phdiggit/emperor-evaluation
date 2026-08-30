from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
C2 = PROFILE_ROOT / "C2/19-C2信息处理学习与纠错正式结算.json"
C5 = PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_cross_axis_drift() -> dict[str, Any]:
    """Report C2/C5 same-chain review drift without invalidating either axis."""
    c2 = {row["ruler_id"]: row for row in _load(C2)["records"]}
    c5 = {row["ruler_id"]: row for row in _load(C5)["records"]}
    missing_in_c2 = sorted(set(c5) - set(c2))
    missing_in_c5 = sorted(set(c2) - set(c5))
    mismatches = []
    for ruler_id in sorted(set(c2) & set(c5)):
        c2_status = c2[ruler_id].get("same_chain_semantic_conflict_review_status")
        c5_status = c5[ruler_id].get("same_chain_semantic_conflict_review_status")
        if c2_status != c5_status:
            mismatches.append({"ruler_id": ruler_id, "c2_status": c2_status, "c5_status": c5_status})
    changed = bool(missing_in_c2 or missing_in_c5 or mismatches)
    return {
        "status": "REVIEW_REQUIRED" if changed else "CURRENT",
        "c2_record_count": len(c2),
        "c5_record_count": len(c5),
        "missing_in_c2_count": len(missing_in_c2),
        "missing_in_c5_count": len(missing_in_c5),
        "status_mismatch_count": len(mismatches),
        "missing_in_c2": missing_in_c2,
        "missing_in_c5": missing_in_c5,
        "status_mismatches": mismatches,
    }
