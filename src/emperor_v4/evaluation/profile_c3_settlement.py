from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
SETTLEMENT = PROFILE_ROOT / "C3/24-C3人才识别配置与授权正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "C3/25-C3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "C3/26-C3高档授权生命周期复核.json"
ACCEPTANCE = PROFILE_ROOT / "C3/27-C3全池结算验收报告.md"
SYSTEMIC_REVIEW = PROFILE_ROOT / "C3/28-C3高档门与错误清洗系统复核.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _update_manifest() -> None:
    manifest = _load(MANIFEST)
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "C3")
    if SYSTEMIC_REVIEW.name not in axis["audit_jsons"]:
        axis["audit_jsons"].append(SYSTEMIC_REVIEW.name)
    axis["formalization_note"] = (
        "C3正式JSON为逐人裁决唯一真源；程序只生成阅读视图，"
        "高档门、生命周期、模板与跨轴边界由轻量语义校验器守护。"
    )
    _write_json(MANIFEST, manifest)


def build(*, write: bool = False) -> dict[str, Any]:
    settlement = _load(SETTLEMENT)
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("C3 formal settlement is not declared as the patch authority")
    if write:
        MARKDOWN.write_text(
            render_profile_markdown(settlement), encoding="utf-8", newline="\n"
        )
        _update_manifest()
    return {"settlement": settlement}


if __name__ == "__main__":
    print(json.dumps(build(write=True)["settlement"]["summary"], ensure_ascii=False, indent=2))
