from __future__ import annotations

import json
import math
import re
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


def _refresh_redundant_record_text(record: dict[str, Any]) -> None:
    """Render repeated summaries only from the current formal structure."""
    evidence = record["ability_evidence"]
    trajectory = evidence["trajectory"]
    start = trajectory["start_vector"]
    main = trajectory["main_vector"]
    peak = trajectory["peak_vector"]
    end = trajectory["end_vector"]
    recovery = trajectory["recovery_score_27"]
    stability = trajectory["stability_score_18"]
    deterioration = evidence["deterioration_penalty"]
    da_grade = evidence["destructive_amplification_grade"]
    da_penalty = evidence["destructive_amplification_penalty"]
    retained = round(recovery + stability, 1)
    terminal_quality = round(0.5 * end[0] + 0.2 * end[1] + 0.3 * end[2], 2)
    terminal_tier = min(math.floor(terminal_quality + 0.5), min(end) + 1)
    terminal_band = f"C4T-{terminal_tier}"
    terminal_cap = {1: 7.9, 2: 15.9, 3: 24.9, 4: 34.9, 5: 40.9, 6: 45.0}[terminal_tier]

    record["typical_pattern"] = (
        f"三轴起点、主态、最高实现、交班分别为{start}、{main}、{peak}、{end}；"
        f"恢复{recovery:.1f}/27，稳定{stability:.1f}/18；恶化扣减{deterioration:.1f}，"
        f"主动成本{da_grade}/{da_penalty:.1f}。正式逐人裁决为"
        f"{record['axis_grade']}-{record['position']}。"
    )
    record["construction_and_maintenance"] = (
        f"按正式档界公式重算恢复分{recovery:.1f}/27；稳定承压按当前K结构计"
        f"{stability:.1f}/18，未把恢复信用并入稳定分；正向保留{retained:.1f}。"
    )
    record["costs_and_consequences"] = (
        f"交班局面为{end}；可归责恶化扣减{deterioration:.1f}；"
        f"本人可选择行为的残余额外成本为{da_grade}，扣减{da_penalty:.1f}。"
    )

    old_grade_basis = record.get("grade_basis", "")
    old_position_basis = record.get("position_basis", "")
    public = record.get("public_adjudication", "")
    for stale in (old_grade_basis, old_position_basis):
        if stale:
            public = public.replace(stale, "")
    public = re.sub(
        r"依据最新C1—C3三轴曲线与C4恢复、稳定、恶化、DA正式值复核；"
        r"本轮仅更新已确认上游事实，保留已确认的G[0-5]档裁决。",
        "",
        public,
    )
    public = re.sub(
        r"档内位置保留为(?:LOW|MID|HIGH)；未以结构字段更新自动重裁档位或档内位置。",
        "",
        public,
    )
    da_tier = int(da_grade[-1])
    if da_tier < 4:
        public = public.replace(f"不升{da_grade}", f"不升DA{da_tier + 1}")
        for field in ("counterpattern", "behavior_chain"):
            if isinstance(record.get(field), str):
                record[field] = record[field].replace(
                    f"不升{da_grade}", f"不升DA{da_tier + 1}"
                )
    public = " ".join(public.split())
    record["grade_basis"] = (
        f"依据当前C1—C4结构字段与逐人语义裁决，正式档位为{record['axis_grade']}。"
    )
    record["position_basis"] = (
        f"当前档内位置为{record['position']}；不以结构字段自动替代逐人语义裁决。"
    )
    record["public_adjudication"] = " ".join(
        part
        for part in (public, record["grade_basis"], record["position_basis"])
        if part
    )
    record["handoff_state"] = (
        f"按交班向量{end}推导终局为{terminal_band}，正向上限{terminal_cap:.1f}。"
    )


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
            "contract_version": "FORMAL-V3.5",
            "contract": M3_CONTRACT.relative_to(ROOT).as_posix(),
            "record_count": 184,
            "json": M3_SETTLEMENT.relative_to(PROFILE_ROOT).as_posix(),
            "markdown": M3_MARKDOWN.relative_to(PROFILE_ROOT).as_posix(),
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
        for record in settlement["records"]:
            _refresh_redundant_record_text(record)
        _write_json(M3_SETTLEMENT, settlement)
        M3_MARKDOWN.write_text(
            render_profile_markdown(settlement), encoding="utf-8", newline="\n"
        )
        update_manifest()
    return {"settlement": settlement}


if __name__ == "__main__":
    build(write=True)
