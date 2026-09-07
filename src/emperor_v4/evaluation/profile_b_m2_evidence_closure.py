"""Close the two remaining B-list M2 display points after bounded local search."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.profile_markdown import write_axes


ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "docs/评分结算/皇帝人物画像/交叉轴复核/12-B-M2补证扩搜闭合复裁.json"
M2 = ROOT / "docs/评分结算/皇帝人物画像/M2/12-M2外交博弈与对外联盟能力正式结算.json"

DECISIONS = {
    "刘邦": {
        "axis_grade": "G3",
        "position": "LOW",
        "score_100": 58,
        "radar_value": 58,
        "axis_evidence_level": "E2",
        "output_mode": "BOUNDED_PROFILE",
        "confidence": "MEDIUM",
        "grade_basis": "按统一补证预算复核卷九至卷十二的外部对象材料：南越承认—通使—称臣构成一条可反查的本人授权与执行生命周期；反间、说齐与鸿沟材料分别受战争战略、臣使/将领执行或跨轴去重边界限制，未再闭合为独立M2计分父链。扩搜后可发布的M2能力是有界、单一外部周期，不保留整改前G4显示点。",
        "position_basis": "G3-LOW：仅有一条可反查的外部条件—授权—执行生命周期；其他候选未闭合，不以材料空白追加负证，也不足进入G3中高位。",
        "limitations": [
            "E2有界画像：南越链可定位，但楚汉战争中的反间、说齐与鸿沟材料仍受主轴、臣使归责或过程拆分限制。",
            "不把韩信、彭越内部联盟和白登军事误判继续计入M2。",
        ],
        "closure_basis": "本地卷九至卷十二定向扩搜完成；仅保留南越外部周期，未以候选数量或历史名望补成高档。",
    },
    "刘启": {
        "axis_grade": "G3",
        "position": "LOW",
        "score_100": 58,
        "radar_value": 58,
        "axis_evidence_level": "E1",
        "output_mode": "EPISODE_TAG",
        "confidence": "LOW",
        "grade_basis": "按统一补证预算复核景帝窗口的匈奴、和亲、边防和七国之乱材料：和亲后连续入侵未通过结果门与因果门；七国之乱属于本朝宗室/诸侯危机并已转M4；未找到可闭合的本人外部条件—反馈—执行M2生命周期。故闭合为E1有界G3-LOW，不把缺料写成外交负证。",
        "position_basis": "G3-LOW：当前仅能确认有界观察窗口和轴外/背景材料，没有合格外部计分父链；不把七国军事结果或和亲失败自动转入M2。",
        "limitations": [
            "E1有界画像：景帝朝匈奴方向尚无可归本人、含条件交换与反馈重谈的完整外部生命周期。",
            "七国之乱继续按M4/M1/C1边界处理，和亲继续按M2结果门/因果门失败的背景材料处理。",
        ],
        "closure_basis": "本地卷十五至卷十六定向扩搜完成；未找到合格M2计分链，按证据下限闭合，不保留工作中状态。",
    },
}

PRE_FORMAL_VALUES = {
    "刘邦": {"axis_grade": "G4", "position": "LOW", "radar_value": 77, "adjudication_state": "UNRESOLVED_EVIDENCE_GAP"},
    "刘启": {"axis_grade": "G3", "position": "LOW", "radar_value": 58, "adjudication_state": "UNRESOLVED_EVIDENCE_GAP"},
}


def _record(payload: dict[str, Any], name: str) -> dict[str, Any]:
    return next(row for row in payload["records"] if row["ruler_name"] == name)


def _summary(payload: dict[str, Any]) -> None:
    records = payload["records"]
    summary = payload.get("summary") or {}
    summary["grade_distribution"] = dict(Counter(row["axis_grade"] for row in records))
    summary["evidence_limited_count"] = sum(row.get("score_status") == "EVIDENCE_LIMITED" for row in records)
    summary["display_point_only_count"] = sum(bool(row.get("display_point_only")) for row in records)
    summary["pending_reassessment_count"] = sum(
        row.get("adjudication_state") in {"UNRESOLVED_EVIDENCE_GAP", "REASSESSMENT_REQUIRED"}
        for row in records
    )
    summary["record_count"] = len(records)
    payload["summary"] = summary


def build_audit(payload: dict[str, Any], before_values: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    decisions = []
    for name, spec in DECISIONS.items():
        row = _record(payload, name)
        decisions.append(
            {
                "ruler_id": row["ruler_id"],
                "ruler_name": name,
                "pre_formal_value": dict((before_values or PRE_FORMAL_VALUES)[name]),
                "post_formal_value": {key: row[key] for key in ("axis_grade", "position", "score_100", "radar_value", "axis_evidence_level", "output_mode", "confidence", "score_status")},
                "decision": "CLOSE_BOUNDED_CURRENT_VALUE",
                "basis": spec["closure_basis"],
            }
        )
    return {
        "schema_version": "profile-b-m2-evidence-closure-readjudication-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "B_M2_LOCAL_EXPANDED_SEARCH_CLOSE_UNRESOLVED_DISPLAY_POINTS",
        "source_scope": [
            "docs/史料通读产物/唐以前编年/汉/卷009-通读总结.md",
            "docs/史料通读产物/唐以前编年/汉/卷010-通读总结.md",
            "docs/史料通读产物/唐以前编年/汉/卷011-通读总结.md",
            "docs/史料通读产物/唐以前编年/汉/卷012-通读总结.md",
            "docs/史料通读产物/唐以前编年/汉/卷015-通读总结.md",
            "docs/史料通读产物/唐以前编年/汉/卷016-通读总结.md",
        ],
        "record_count": len(payload["records"]),
        "affected_ruler_count": len(decisions),
        "grade_changed_count": 1,
        "position_changed_count": 0,
        "radar_changed_count": 1,
        "formal_score_write": True,
        "decisions": decisions,
    }


def write() -> dict[str, Any]:
    payload = load_json(M2)
    before = {name: dict(PRE_FORMAL_VALUES[name]) for name in DECISIONS}
    for name, spec in DECISIONS.items():
        row = _record(payload, name)
        for key in ("axis_grade", "position", "score_100", "radar_value", "axis_evidence_level", "output_mode", "confidence", "grade_basis", "position_basis", "limitations"):
            row[key] = spec[key]
        row["score_status"] = "EVIDENCE_LIMITED"
        row["formal_status"] = "FORMAL_CURRENT"
        row["adjudication_state"] = "FORMAL_CURRENT"
        row["display_point_only"] = False
        for key in ("display_point_reason", "pending_reopen_condition", "historical_display_grade", "historical_display_radar_value"):
            row.pop(key, None)
    _summary(payload)
    write_json(M2, payload, ruler_polities=load_ruler_polities(ROOT))
    write_axes(("M2",))
    audit = build_audit(payload, before)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    write_json(AUDIT, audit)
    return {
        "audit_json": AUDIT.relative_to(ROOT).as_posix(),
        "before": before,
        "post_formal_values": {name: {key: _record(payload, name).get(key) for key in ("axis_grade", "position", "score_100", "radar_value")} for name in DECISIONS},
        "formal_score_write": True,
    }


def verify() -> dict[str, Any]:
    payload = load_json(M2)
    expected = build_audit(payload, PRE_FORMAL_VALUES)
    if not AUDIT.is_file() or load_json(AUDIT) != expected:
        raise ValueError("B M2证据闭合复裁审计与正式JSON不一致")
    if any(_record(payload, name).get("display_point_only") for name in DECISIONS):
        raise ValueError("B M2仍有已处理人物处于显示点状态")
    return {"status": "PASS", "affected_ruler_count": len(DECISIONS), "formal_score_write": True}


if __name__ == "__main__":
    import sys

    result = write() if len(sys.argv) > 1 and sys.argv[1] == "write" else verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
