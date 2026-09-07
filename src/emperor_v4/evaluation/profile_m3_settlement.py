from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.governance_state_recovery import (
    clean_retired_low_valley_references,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown
from emperor_v4.evaluation.profile_registry import write_profile_manifest


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
M3_CONTRACT_VERSION = "FORMAL-V3.6"


def _load(path: Path) -> dict[str, Any]:
    return load_json(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload, ruler_polities=load_ruler_polities(ROOT))


def sync_governance_inputs() -> None:
    """Refresh upstream facts without deriving an independent M3 grade from L."""
    from emperor_v4.evaluation.governance_state_recovery import FORMAL_PATHS
    from emperor_v4.evaluation.profile_m3_verifier import _expected_trajectory
    upstream = {a: {r['ruler_id']: r for r in load_json(ROOT / p)['scores']} for a,p in FORMAL_PATHS.items()}
    settlement = _load(M3_SETTLEMENT)
    for record in settlement['records']:
        rid = record['ruler_id']
        evidence = record['ability_evidence']
        for axis in FORMAL_PATHS:
            source = upstream[axis][rid]
            record['components'][axis] = {'band': source['main_band'], 'score': source['score']}
        evidence['trajectory'].update(_expected_trajectory(upstream, rid))
        evidence['trajectory']['recovery_score_27'] = upstream['C4'][rid]['recovery_score']
        for field in ('deterioration_penalty', 'destructive_amplification_grade', 'destructive_amplification_penalty'):
            evidence[field] = upstream['C4'][rid][field]
        evidence['state_loss_basis'] = {a: {'grade':upstream[a][rid].get('loss_grade'), 'role':'STATE_SCORE_ONLY_NOT_M3_GRADE'} for a in ('C1','C2','C3')}
        evidence.pop('stability_k_public_basis', None)
        evidence.pop('stability_k_structure_status', None)
        evidence['upstream_sync']['status'] = 'SYNCED_TO_FORMAL_GOVERNANCE_V3'
        evidence['upstream_sync'].pop('k_source', None)
        for field in ('construction_and_maintenance', 'costs_and_consequences', 'behavior_chain', 'counterpattern', 'public_adjudication'):
            if field in record:
                record[field] = clean_retired_low_valley_references(record[field], field)
    summary_sync = settlement.get('summary', {}).get('upstream_sync')
    if isinstance(summary_sync, dict):
        summary_sync['status'] = 'SYNCED_TO_FORMAL_GOVERNANCE_V3'
        summary_sync.pop('stability_k_source', None)
        summary_sync.pop('k_structure_distribution', None)
    _write_json(M3_SETTLEMENT, settlement)


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
    terminal_quality = round(0.5 * end[0] + 0.2 * end[1] + 0.3 * end[2], 2)
    terminal_tier = min(math.floor(terminal_quality + 0.5), min(end) + 1)
    terminal_band = f"C4T-{terminal_tier}"
    record["typical_pattern"] = (
        f"三轴起点、主态、最高实现、交班分别为{start}、{main}、{peak}、{end}；"
        f"恢复{recovery:.1f}/27，稳定{stability:.1f}/18；恶化扣减{deterioration:.1f}，"
        f"主动成本{da_grade}/{da_penalty:.1f}。正式逐人裁决为"
        f"{record['axis_grade']}-{record['position']}。"
    )
    record["construction_and_maintenance"] = (
        f"按正式档界公式重算恢复分{recovery:.1f}/27；"
        f"以三轴历史稳定诊断作独立画像复核，M3逐人裁决稳定分为{stability:.1f}/18；"
        "该诊断不参与第二项状态计分，L不自动换算M3档位或稳定分，独立稳定判断不回写C4。"
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
    readjudication = record.get("full_pool_grade_readjudication") or {}
    record["grade_basis"] = readjudication.get("grade_basis") or (
        f"依据当前C1—C4结构字段与逐人语义裁决，正式档位为{record['axis_grade']}。"
    )
    record["position_basis"] = readjudication.get("position_basis") or (
        f"当前档内位置为{record['position']}；不以结构字段自动替代逐人语义裁决。"
    )
    record["public_adjudication"] = clean_retired_low_valley_references(" ".join(
        part
        for part in (public, record["grade_basis"], record["position_basis"])
        if part
    ), "public_adjudication")
    for field in ("typical_pattern", "costs_and_consequences", "behavior_chain", "counterpattern"):
        if field in record:
            record[field] = clean_retired_low_valley_references(record[field], field)
    record["handoff_state"] = (
        f"按交班向量{end}推导C4终局标签为{terminal_band}；"
        "M3单独读取交班保留，不把稳定分回写C4。"
    )


def update_manifest() -> None:
    """Refresh only the M3 manifest entry from the project registry."""
    write_profile_manifest(("M3",))


def build(*, write: bool = False) -> dict[str, Any]:
    if write:
        sync_governance_inputs()
    settlement = _load(M3_SETTLEMENT)
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("M3 formal settlement is not declared as the patch authority")
    if write:
        settlement["contract_version"] = M3_CONTRACT_VERSION
        settlement["records"].sort(key=lambda row: (-row["radar_value"], row["ruler_id"]))
        settlement["summary"]["grade_distribution"] = {
            f"G{tier}": sum(row["axis_grade"] == f"G{tier}" for row in settlement["records"])
            for tier in range(6)
        }
        for record in settlement["records"]:
            record["contract_version"] = M3_CONTRACT_VERSION
            _refresh_redundant_record_text(record)
        _write_json(M3_SETTLEMENT, settlement)
        M3_MARKDOWN.write_text(
            render_profile_markdown(settlement), encoding="utf-8", newline="\n"
        )
        update_manifest()
    return {"settlement": settlement}


if __name__ == "__main__":
    build(write=True)
