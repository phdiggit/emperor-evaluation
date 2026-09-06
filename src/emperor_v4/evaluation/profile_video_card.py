from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib.patches as patches

from emperor_v4.evaluation.profile_radar import (
    AXIS_COLORS,
    AXIS_LABELS,
    AXIS_ORDER,
    POOL,
    ROOT,
    Profile,
    _matplotlib,
    _project_profile_config,
    _read_json,
    load_profiles,
)


SAMPLE_RULER_IDS = (
    "RULER-TANG-LISHIMIN",
    "RULER-MING-ZHU-YUANZHANG",
    "RULER-NS-ZHAO-JI",
)


def _wrap_viewer_summary(summary: str, width: int = 17) -> str:
    """Wrap Chinese viewer copy predictably inside the fixed 16:9 text column."""
    lines: list[str] = []
    for hard_line in summary.splitlines() or [summary]:
        clauses = hard_line.split("；")
        for index, clause in enumerate(clauses):
            if index < len(clauses) - 1:
                clause += "；"
            while len(clause) > width:
                lines.append(clause[:width])
                clause = clause[width:]
            if clause:
                lines.append(clause)
    return "\n".join(lines)


def _pool_contexts() -> dict[str, dict[str, str]]:
    rows = _read_json(POOL)["records"]
    return {
        row["ruler_id"]: {
            "polity": row["polity"],
            "actual_power_window": row["actual_power_window"],
        }
        for row in rows
        if row["pool_status"] == "INCLUDED"
    }


def _radar_axis(figure: Any, position: Any, profile: Profile) -> Any:
    axis = figure.add_axes(position, projection="polar")
    angles = [2 * math.pi * index / len(AXIS_ORDER) for index in range(len(AXIS_ORDER))]
    closed_angles = angles + angles[:1]
    axis.set_theta_offset(math.pi / 2)
    axis.set_theta_direction(-1)
    axis.set_facecolor("#FFFDF8")
    for angle, color in zip(angles, AXIS_COLORS):
        axis.bar(angle, 100, width=2 * math.pi / len(AXIS_ORDER), color=color, alpha=0.05, edgecolor="none", zorder=0)
    axis.set_xticks(angles)
    labels = axis.set_xticklabels([AXIS_LABELS[code] for code in AXIS_ORDER], fontsize=11, fontweight="semibold")
    for label, color in zip(labels, AXIS_COLORS):
        label.set_color(color)
    # Keep labels clear of both the plot rim and the 16:9 card boundary.
    axis.tick_params(axis="x", pad=14)
    axis.set_ylim(0, 100)
    axis.set_yticks((20, 40, 60, 80, 100))
    axis.set_yticklabels(("20", "40", "60", "80", "100"), fontsize=8, color="#7A746D")
    axis.yaxis.grid(True, color="#D8D0C5", linewidth=0.65)
    axis.xaxis.grid(True, color="#B5ADA2", linewidth=0.7, linestyle="--")
    axis.spines["polar"].set_color("#756E65")
    values = list(profile.values) + [profile.values[0]]
    axis.plot(closed_angles, values, color="#3D4C9E", linewidth=2.5, marker="o", markersize=4.5, zorder=3)
    axis.fill(closed_angles, values, color="#5E72E4", alpha=0.16, zorder=2)
    axis.scatter(angles, profile.values, c=AXIS_COLORS, s=35, zorder=4, edgecolors="#FFFDF8", linewidths=0.7)
    return axis


def render_card(profile: Profile, context: dict[str, str], portrait_path: Path, tag: str, summary: str, citation: str, output_path: Path) -> None:
    plt = _matplotlib()
    figure = plt.figure(figsize=(12.8, 7.2), dpi=150, facecolor="#F7F0E3")
    figure.subplots_adjust(left=0, right=1, top=1, bottom=0)
    canvas = figure.add_axes((0, 0, 1, 1))
    canvas.set_axis_off()
    canvas.add_patch(patches.Rectangle((0, 0), 1, 1, facecolor="#F7F0E3", edgecolor="none"))
    canvas.text(0.5, 0.915, tag, fontsize=24, color="#9A7246", fontweight="bold", ha="center", va="center")
    canvas.plot((0.31, 0.405), (0.915, 0.915), color="#C6A36E", linewidth=1.1)
    canvas.plot((0.595, 0.69), (0.915, 0.915), color="#C6A36E", linewidth=1.1)

    # Keep each painting's native aspect ratio.  The display width is calculated
    # in physical figure units, then centred in a common left-hand portrait bay.
    portrait = plt.imread(portrait_path)
    portrait_height = 0.618
    portrait_width = portrait.shape[1] / portrait.shape[0] * (7.2 / 12.8) * portrait_height
    portrait_x = 0.17 - portrait_width / 2
    portrait_axis = figure.add_axes((portrait_x, 0.168, portrait_width, portrait_height))
    portrait_axis.imshow(portrait, aspect="auto")
    portrait_axis.set_axis_off()
    # The frame hugs the visible portrait area; it is a boundary, not a second panel.
    portrait_frame = figure.add_axes((portrait_x, 0.168, portrait_width, portrait_height), zorder=3)
    portrait_frame.patch.set_alpha(0)
    portrait_frame.set_axis_off()
    portrait_frame.add_patch(patches.Rectangle((0, 0), 1, 1, transform=portrait_frame.transAxes, facecolor="none", edgecolor="#B58C4E", linewidth=2.0, clip_on=False))
    canvas.text(0.34, 0.745, profile.ruler_name, fontsize=37, color="#302016", fontweight="bold", va="center")
    canvas.text(0.342, 0.675, f"{context['polity']} · {context['actual_power_window']}", fontsize=15, color="#806144", va="center")
    canvas.plot((0.342, 0.586), (0.622, 0.622), color="#D5B888", linewidth=0.8)
    # Place the quotation below the radar's left-side label corridor.
    canvas.add_patch(patches.FancyBboxPatch((0.335, 0.150), 0.258, 0.242, boxstyle="round,pad=0.014,rounding_size=0.012", facecolor="#F2E7D2", edgecolor="#D5B888", linewidth=1.0))
    # A conservative line width keeps the closing quotation mark inside the box
    # even for the longest of the three verified excerpts.
    canvas.text(0.357, 0.350, _wrap_viewer_summary(summary, width=15), fontsize=12, color="#50392B", va="top", linespacing=1.66)
    canvas.plot((0.382, 0.568), (0.210, 0.210), color="#B9915D", linewidth=0.9)
    canvas.text(0.568, 0.180, f"——{citation}", fontsize=9.5, color="#856547", ha="right", va="center")
    # Reserve a full text-width margin at the right edge for “民生财政”.
    _radar_axis(figure, (0.63, 0.205, 0.250, 0.57), profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_png = output_path.parent / ".video-card-render.png"
    figure.savefig(temporary_png, format="png", dpi=150)
    temporary_png.replace(output_path.with_suffix(".png"))
    figure.savefig(output_path.with_suffix(".svg"))
    plt.close(figure)


def write_samples(output_dir: Path | None = None) -> dict[str, Any]:
    profiles = load_profiles()
    contexts = _pool_contexts()
    profile_config = _project_profile_config()
    config = profile_config["video_card_samples"]
    if config["canvas"] != [1920, 1080] or any(config[key] for key in ("profile_total_enabled", "profile_ranking_enabled", "composite_ranking_write")):
        raise ValueError("视频人物卡配置不得启用总分、排名或综合榜写入")
    portrait_manifest = _read_json(ROOT / config["portrait_manifest"])
    if portrait_manifest["status"] != "LOCAL_PUBLIC_DOMAIN_ASSETS":
        raise ValueError("视频人物卡只能使用已登记的本地公共领域肖像")
    portrait_assets = portrait_manifest["assets"]
    editorial = _read_json(ROOT / config["editorial_draft_json"])
    if editorial["status"] != "DRAFT_REQUIRES_HUMAN_APPROVAL":
        raise ValueError("人物卡文案必须保持人工核准前草案状态")
    output_dir = output_dir or ROOT / config["output_dir"]
    missing = set(SAMPLE_RULER_IDS) - (set(profiles) & set(contexts))
    if missing:
        raise ValueError(f"视频人物卡小样不在正式池：{sorted(missing)}")
    cards = []
    for ruler_id in SAMPLE_RULER_IDS:
        profile = profiles[ruler_id]
        portrait = portrait_assets[ruler_id]
        card_copy = editorial["cards"][ruler_id]
        portrait_path = ROOT / portrait["path"]
        if portrait["license"] != "PUBLIC_DOMAIN_PD_ART" or not portrait_path.is_file():
            raise ValueError(f"肖像素材不可用或许可不合格：{ruler_id}")
        if (
            not 10 <= len(card_copy["summary"]) <= 60
            or any(term in card_copy["summary"] for term in ("总分", "排名", "综合"))
            or not card_copy["context_sources"]
            or not card_copy["citation"]
        ):
            raise ValueError(f"人物卡文案不符合独立画像边界：{ruler_id}")
        if len(card_copy["tag"]) != 4:
            raise ValueError(f"人物卡标签必须为四字：{ruler_id}")
        render_card(profile, contexts[ruler_id], portrait_path, card_copy["tag"], card_copy["summary"], card_copy["citation"], output_dir / f"{ruler_id}-人物卡")
        cards.append({
            "ruler_id": ruler_id,
            "ruler_name": profile.ruler_name,
            "polity": contexts[ruler_id]["polity"],
            "actual_power_window": contexts[ruler_id]["actual_power_window"],
            "values": list(profile.values),
            "portrait": portrait,
            "editorial": card_copy,
        })
    index = {
        "schema_version": "emperor-profile-video-card-samples-v1",
        "canvas": {"width": 1920, "height": 1080, "aspect_ratio": "16:9"},
        "portrait_status": "LOCAL_PUBLIC_DOMAIN_ASSETS",
        "portrait_manifest": config["portrait_manifest"],
        "editorial_status": editorial["status"],
        "axis_order": list(AXIS_ORDER),
        "scale": [0, 100],
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "composite_ranking_write": False,
        "cards": cards,
    }
    (output_dir / "00-视频人物卡小样索引.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index
