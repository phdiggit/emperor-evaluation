from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
POOL = ROOT / "config/common/canonical-ruler-pool.json"
PROJECT = ROOT / "config/project.yml"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
SETTLEMENT = PROFILE_ROOT / "M4/34-M4政治联盟与内部联盟管理正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "M4/35-M4主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "M4/36-M4高档联盟生命周期复核.json"
FULL_POOL_REVIEW = PROFILE_ROOT / "M4/37-M4全池两轮复审.json"

NORMATIVE_ENTRIES = {
    "FIRST_ITEM_B", "FOURTH_ITEM_A", "FIFTH_ITEM_B", "FIFTH_ITEM_C",
    "PROFILE_M1", "PROFILE_M2", "PROFILE_M3", "PROFILE_C1", "PROFILE_C2",
    "PROFILE_C3", "PROFILE_C5", "M4_EXPLICIT_ADJUDICATION",
    "M4_UNCLOSED_OBSERVATION",
}

SCORES = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12},
    "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51},
    "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87},
    "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}


def _load(path: Path) -> dict[str, Any]:
    return load_json(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload, ruler_polities=load_ruler_polities(ROOT))


def _update_manifest() -> None:
    manifest = _load(MANIFEST)
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "M4")
    axis["formalization_note"] = (
        "M4正式JSON为逐人裁决唯一真源；程序只生成阅读视图，"
        "人物裁决变化只通过局部patch进入正式JSON，不由程序自动改档。"
    )
    _write_json(MANIFEST, manifest)


def build(*, write: bool = False) -> dict[str, Any]:
    settlement = _load(SETTLEMENT)
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("M4 formal settlement is not declared as the patch authority")
    if write:
        MARKDOWN.write_text(render_profile_markdown(settlement), encoding="utf-8", newline="\n")
        _update_manifest()
    return {"settlement": settlement}


if __name__ == "__main__":
    print(json.dumps(build(write=True)["settlement"]["summary"], ensure_ascii=False, indent=2))
