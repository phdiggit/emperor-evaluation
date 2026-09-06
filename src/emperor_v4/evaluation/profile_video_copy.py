from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.profile_radar import (
    AXIS_LABELS,
    AXIS_ORDER,
    POOL,
    ROOT,
    _project_profile_config,
    _read_json,
    load_profiles,
)


SAMPLE_RULER_IDS = (
    "RULER-TANG-LISHIMIN",
    "RULER-MING-ZHU-YUANZHANG",
    "RULER-NS-ZHAO-JI",
)
AXIS_PAGES = (("能力与治理画像", ("M1", "M2", "M3", "M4")), ("决策与用人画像", ("C1", "C2", "C3", "C5")))


def _pool_contexts() -> dict[str, dict[str, str]]:
    return {
        row["ruler_id"]: {
            "polity": row["polity"],
            "actual_power_window": row["actual_power_window"],
        }
        for row in _read_json(POOL)["records"]
        if row["pool_status"] == "INCLUDED"
    }


def _axis_rows() -> dict[str, dict[str, dict[str, Any]]]:
    config = _project_profile_config()
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    for axis_code in AXIS_ORDER:
        payload = _read_json(ROOT / config["settled_axes"][axis_code]["json"])
        if payload["axis_code"] != axis_code or payload["canonical_status"] != "FORMAL_CURRENT":
            raise ValueError(f"{axis_code}不是当前正式结算")
        rows[axis_code] = {row["ruler_id"]: row for row in payload["records"]}
    return rows


def _copy_card(axis_code: str, row: dict[str, Any], source_json: str) -> dict[str, Any]:
    """Keep formal prose verbatim; editorial compression is deliberately a later approval step."""
    counterpattern = row["counterpattern"]
    counter_source = "counterpattern"
    if not isinstance(counterpattern, str):
        negative_contexts = [
            parent["cycle_basis"]
            for parent in row.get("representative_parent_contexts", [])
            if parent.get("direction") in {"NEGATIVE", "MIXED", "MIXED_NEGATIVE"}
            and parent.get("cycle_basis")
        ]
        if not negative_contexts:
            counterpattern = row["grade_basis"]
            counter_source = "grade_basis_fallback"
        else:
            counterpattern = "；".join(negative_contexts)
            counter_source = "representative_parent_contexts.cycle_basis"
    return {
        "axis_code": axis_code,
        "axis_label": AXIS_LABELS[axis_code],
        "radar_value": row["radar_value"],
        "source_task_code": row["task_code"],
        "source_json": source_json,
        "main_basis": row["typical_pattern"],
        "counterevidence": counterpattern,
        "counterevidence_source": counter_source,
        "limitations": row["limitations"],
        "editorial_status": "VERBATIM_FORMAL_EXCERPT_REQUIRES_APPROVAL",
    }


def _editorial_summaries(path: Path) -> dict[str, str]:
    payload = _read_json(path)
    if payload["status"] != "DRAFT_REQUIRES_HUMAN_APPROVAL":
        raise ValueError("视频文案必须保持人工核准前草案状态")
    standard = payload["editorial_standard"]
    if (
        standard["character_range"] != [25, 80]
        or "分号" not in standard["required_structure"]
        or "具体事实、行动与后果" not in standard["audience_rule"]
        or "先按雷达值确定叙事强度" not in standard["score_alignment_rule"]
    ):
        raise ValueError("视频文案编辑标准必须保留字数和结果边界要求")
    rows = payload["cards"]
    summaries = {row["task_code"]: row["display_summary"] for row in rows}
    forbidden = ("画像总分", "轴内排名", "综合总分", *standard["forbidden_viewer_phrases"])
    if (
        len(summaries) != len(rows)
        or any(not 25 <= len(text) <= 80 or "；" not in text for text in summaries.values())
        or any(term in text for text in summaries.values() for term in forbidden)
    ):
        raise ValueError("视频文案必须唯一且保持25—80字的信息密度")
    return summaries


def _score_alignment_requirement(radar_value: int, standard: dict[str, Any]) -> dict[str, Any]:
    """Expose the editorial strength brief without leaking it into viewer prose."""
    matches = [
        band for band in standard["score_alignment_bands"]
        if band["min"] <= radar_value <= band["max"]
    ]
    if len(matches) != 1:
        raise ValueError(f"雷达值缺少唯一文案强度规则：{radar_value}")
    return {"range": [matches[0]["min"], matches[0]["max"]], "requirement": matches[0]["requirement"]}


def build_samples() -> dict[str, Any]:
    config = _project_profile_config()
    profiles = load_profiles()
    contexts = _pool_contexts()
    axis_rows = _axis_rows()
    video_config = config["video_copy_samples"]
    editorial_path = ROOT / video_config["editorial_draft_json"]
    editorial_summaries = _editorial_summaries(editorial_path)
    editorial_standard = _read_json(editorial_path)["editorial_standard"]
    missing = set(SAMPLE_RULER_IDS) - (set(profiles) & set(contexts))
    if missing:
        raise ValueError(f"视频文字小样不在正式池：{sorted(missing)}")

    people = []
    for ruler_id in SAMPLE_RULER_IDS:
        profile = profiles[ruler_id]
        axis_cards = {}
        for axis_code in AXIS_ORDER:
            card = _copy_card(axis_code, axis_rows[axis_code][ruler_id], config["settled_axes"][axis_code]["json"])
            card["display_summary"] = editorial_summaries[card["source_task_code"]]
            card["editorial_status"] = "DRAFT_REQUIRES_HUMAN_APPROVAL"
            card["score_alignment"] = _score_alignment_requirement(card["radar_value"], editorial_standard)
            axis_cards[axis_code] = card
        if any(card["radar_value"] != profile.values[index] for index, card in enumerate(axis_cards.values())):
            raise ValueError(f"八轴文案卡与雷达值不一致：{ruler_id}")
        people.append({
            "ruler_id": ruler_id,
            "ruler_name": profile.ruler_name,
            **contexts[ruler_id],
            "overview": "八轴独立画像，正式结算展示；不设画像总分或轴内排名。",
            "axis_cards": axis_cards,
        })
    return {
        "schema_version": "emperor-profile-video-copy-samples-v1",
        "source": "config/project.yml:profile_assessment.settled_axes",
        "editorial_policy": "DRAFT_SUMMARIES_BOUND_TO_FORMAL_TASK_CODES_REQUIRES_HUMAN_APPROVAL",
        "axis_order": list(AXIS_ORDER),
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "composite_ranking_write": False,
        "people": people,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    blocks = [
        "# 视频人物画像文字小样",
        "",
        "正式结算文本摘录，供编辑压缩与人工核准；不得改写为画像总分、排名或未被正式结算支持的历史结论。",
    ]
    for person in payload["people"]:
        blocks.extend((
            "",
            f"# {person['ruler_name']}（{person['polity']}）",
            "",
            "## 总览页",
            "",
            f"- 实际掌权时段：{person['actual_power_window']}",
            f"- 定位：{person['overview']}",
        ))
        for page_title, axes in AXIS_PAGES:
            blocks.extend(("", f"## {page_title}", ""))
            for axis_code in axes:
                card = person["axis_cards"][axis_code]
                blocks.extend((
                    f"### {card['axis_label']}（{card['radar_value']}）",
                    "",
                    f"- 上屏文案（草案）：{card['display_summary']}",
                    f"- 正式来源：`{card['source_task_code']}`，`{card['source_json']}`",
                    "",
                ))
    return "\n".join(blocks).rstrip() + "\n"


def write_samples(output_dir: Path | None = None) -> dict[str, Any]:
    config = _project_profile_config()["video_copy_samples"]
    if any(config[key] for key in ("profile_total_enabled", "profile_ranking_enabled", "composite_ranking_write")):
        raise ValueError("视频文字配置不得启用总分、排名或综合榜写入")
    output_dir = output_dir or ROOT / config["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_samples()
    (output_dir / "00-视频人物画像文字小样.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "00-视频人物画像文字小样.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload
