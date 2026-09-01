from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
POOL = ROOT / "config/common/canonical-ruler-pool.json"
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
M3_CONTRACT = ROOT / "docs/分项规则/人物画像轴/M3-民生财政建设.md"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
M3_SETTLEMENT = PROFILE_ROOT / "M3/29-M3民生财政建设正式结算.json"
M3_MARKDOWN = M3_SETTLEMENT.with_suffix(".md")
M3_REVIEW = PROFILE_ROOT / "M3/30-M3对第二项C1-C4逐人补正审计.json"
M3_ACCEPTANCE = PROFILE_ROOT / "M3/31-M3民生财政建设全池收口.md"
M3_REMEDIATION = PROFILE_ROOT / "M3/32-M3上游同步与规模档界整改审计.json"

GRADE_PROJECTION = {
    ("G0", "LOW"): 2,
    ("G0", "MID"): 7,
    ("G0", "HIGH"): 12,
    ("G1", "LOW"): 18,
    ("G1", "MID"): 25,
    ("G1", "HIGH"): 31,
    ("G2", "LOW"): 38,
    ("G2", "MID"): 45,
    ("G2", "HIGH"): 51,
    ("G3", "LOW"): 58,
    ("G3", "MID"): 65,
    ("G3", "HIGH"): 71,
    ("G4", "LOW"): 77,
    ("G4", "MID"): 82,
    ("G4", "HIGH"): 87,
    ("G5", "LOW"): 91,
    ("G5", "MID"): 94,
    ("G5", "HIGH"): 97,
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest() -> None:
    """Update only the M3 manifest entry; other axes are independent snapshots."""
    manifest = _load(MANIFEST)
    current = next(row for row in manifest["axes"] if row["axis_code"] == "M3")
    current.clear()
    current.update(
        {
            "axis_code": "M3",
            "axis_name": "民生财政建设",
            "status": "FORMAL_CURRENT",
            "contract_version": "FORMAL-V3.3",
            "contract": M3_CONTRACT.relative_to(ROOT).as_posix(),
            "contract_sha256": _sha(M3_CONTRACT),
            "record_count": 184,
            "json": M3_SETTLEMENT.relative_to(PROFILE_ROOT).as_posix(),
            "markdown": M3_MARKDOWN.relative_to(PROFILE_ROOT).as_posix(),
            "json_sha256": _sha(M3_SETTLEMENT),
            "markdown_sha256": _sha(M3_MARKDOWN),
            "audit_jsons": [
                M3_REVIEW.relative_to(PROFILE_ROOT).as_posix(),
                M3_REMEDIATION.relative_to(PROFILE_ROOT).as_posix(),
            ],
            "audit_markdowns": [M3_ACCEPTANCE.relative_to(PROFILE_ROOT).as_posix()],
            "record_order_policy": "RADAR_VALUE_DESC_THEN_RULER_ID_ASC",
            "formalization_note": "M3正式JSON为逐人裁决唯一真源；日常修改采用局部patch。程序校验C1—C4事实同步、规模门来源和G4必要条件，只投影固定雷达值并生成阅读视图，不自动重裁。",
        }
    )
    _write_json(MANIFEST, manifest)


def build(*, write: bool = False) -> dict[str, Any]:
    settlement = _load(M3_SETTLEMENT)
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("M3 formal settlement is not declared as the patch authority")
    if write:
        M3_MARKDOWN.write_text(
            render_profile_markdown(settlement), encoding="utf-8", newline="\n"
        )
        update_manifest()
    return {"settlement": settlement}


if __name__ == "__main__":
    build(write=True)
