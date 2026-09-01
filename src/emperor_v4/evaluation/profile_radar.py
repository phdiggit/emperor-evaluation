from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "config" / "project.yml"
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"

AXIS_ORDER = ("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5")
AXIS_LABELS = {
    "M1": "军事统帅",
    "M2": "外交博弈",
    "M3": "民生财政",
    "M4": "联盟整合",
    "C1": "战略风控",
    "C2": "学习纠错",
    "C3": "识才授权",
    "C5": "权力克制",
}
AXIS_COLORS = ("#2F80ED", "#27AE60", "#F2994A", "#EB5757", "#9B51E0", "#56CCF2", "#F2C94C", "#BB6BD9")
SAMPLE_RULER_IDS = (
    "RULER-QIN-YINGZHENG",
    "RULER-HAN-LIUXIU",
    "RULER-TANG-LISHIMIN",
    "RULER-YUAN-TEMUJI",
    "RULER-MING-ZHU-YUANZHANG",
    "RULER-PUBLIC-4EB7AC987FECC59F",
    "RULER-NS-ZHAO-JI",
    "RULER-QIN-HUHAI",
)
COMPARISONS = (
    ("RULER-TANG-LISHIMIN", "RULER-NS-ZHAO-JI"),
    ("RULER-MING-ZHU-YUANZHANG", "RULER-PUBLIC-4EB7AC987FECC59F"),
    ("RULER-QIN-YINGZHENG", "RULER-YUAN-TEMUJI"),
)
@dataclass(frozen=True)
class Profile:
    ruler_id: str
    ruler_name: str
    values: tuple[int, ...]


def _read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    return json.loads(raw.decode("utf-8"))


def _project_profile_config() -> dict[str, Any]:
    return yaml.safe_load(PROJECT.read_text(encoding="utf-8"))["profile_assessment"]


def load_profiles() -> dict[str, Profile]:
    """Load the eight formal axis files and reject any non-canonical join."""
    config = _project_profile_config()
    if config["status"] != "eight_axes_formally_settled":
        raise ValueError("八轴人物画像尚未正式结算")
    if any(config[key] for key in ("profile_total_enabled", "profile_ranking_enabled", "composite_ranking_write")):
        raise ValueError("人物画像雷达图不得启用总分、排名或综合榜写入")
    if tuple(config["settled_axes"]) != AXIS_ORDER:
        raise ValueError("八轴顺序必须为固定正式顺序")

    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))
    pool = _read_json(ROOT / project["canonical_ruler_pool"]["json"])
    expected_ids = {row["ruler_id"] for row in pool["records"] if row["pool_status"] == "INCLUDED"}
    if len(expected_ids) != 184 or config["population_count"] != 184:
        raise ValueError("正式人物池不是184人")

    radar_config = config["radar_samples"]
    if tuple(radar_config["axis_order"]) != AXIS_ORDER or radar_config["scale"] != [0, 100]:
        raise ValueError("雷达图配置必须保留固定八轴顺序和0—100刻度")
    manifest = _read_json(ROOT / config["manifest_json"])
    manifest_axes = {row["axis_code"]: row for row in manifest["axes"]}
    per_axis: dict[str, dict[str, dict[str, Any]]] = {}
    for axis_code in AXIS_ORDER:
        axis_config = config["settled_axes"][axis_code]
        path = ROOT / axis_config["json"]
        payload = _read_json(path)
        records = payload["records"]
        if (
            payload["canonical_status"] != "FORMAL_CURRENT"
            or payload["record_count"] != len(records) != 184
            or payload["axis_code"] != axis_code
        ):
            raise ValueError(f"{axis_code}不是184人正式轴结算")
        if manifest_axes[axis_code]["json"] != path.relative_to(PROFILE_ROOT).as_posix():
            raise ValueError(f"{axis_code}与正式入口清单不一致")
        rows = {row["ruler_id"]: row for row in records}
        if set(rows) != expected_ids or len(rows) != len(records):
            raise ValueError(f"{axis_code}与正式人物池覆盖不一致")
        for ruler_id, row in rows.items():
            value = row.get("radar_value")
            if (
                row.get("task_code") != f"PROFILE-{axis_code}-{ruler_id}"
                or value != row.get("score_100")
                or not isinstance(value, int)
                or not 0 <= value <= 100
            ):
                raise ValueError(f"{axis_code}的雷达值或稳定ID不合法：{ruler_id}")
        per_axis[axis_code] = rows

    profiles: dict[str, Profile] = {}
    for ruler_id in sorted(expected_ids):
        names = {per_axis[axis_code][ruler_id]["ruler_name"] for axis_code in AXIS_ORDER}
        if len(names) != 1:
            raise ValueError(f"八轴人物名称不一致：{ruler_id}")
        profiles[ruler_id] = Profile(
            ruler_id=ruler_id,
            ruler_name=names.pop(),
            values=tuple(per_axis[axis_code][ruler_id]["radar_value"] for axis_code in AXIS_ORDER),
        )
    return profiles


def sample_profiles(profiles: dict[str, Profile]) -> list[Profile]:
    missing = set(SAMPLE_RULER_IDS) - set(profiles)
    if missing:
        raise ValueError(f"小样稳定人物ID不在正式池：{sorted(missing)}")
    return [profiles[ruler_id] for ruler_id in SAMPLE_RULER_IDS]


def _matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    candidates = ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "SimSun")
    font_name = None
    for candidate in candidates:
        try:
            font_manager.findfont(candidate, fallback_to_default=False)
        except ValueError:
            continue
        font_name = candidate
        break
    if not font_name:
        raise RuntimeError("未找到可用中文字体（需要 Microsoft YaHei、Noto Sans CJK SC、SimHei 或 SimSun）")
    matplotlib.rcParams.update({
        "font.family": font_name,
        "axes.unicode_minus": False,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    return plt


def _radar_axes(plt: Any):
    import math

    angles = [2 * math.pi * index / len(AXIS_ORDER) for index in range(len(AXIS_ORDER))]
    closed_angles = angles + angles[:1]
    figure, axis = plt.subplots(figsize=(9.5, 9.5), subplot_kw={"projection": "polar"})
    axis.set_theta_offset(math.pi / 2)
    axis.set_theta_direction(-1)
    axis.set_xticks(angles)
    labels = axis.set_xticklabels([AXIS_LABELS[code] for code in AXIS_ORDER], fontsize=13, fontweight="semibold")
    for label, color in zip(labels, AXIS_COLORS):
        label.set_color(color)
    axis.tick_params(axis="x", pad=24)
    axis.set_ylim(0, 100)
    axis.set_yticks((0, 20, 40, 60, 80, 100))
    axis.set_yticklabels(("0", "20", "40", "60", "80", "100"), color="#4d4d4d", fontsize=9)
    for angle, color in zip(angles, AXIS_COLORS):
        axis.bar(angle, 100, width=2 * math.pi / len(AXIS_ORDER), bottom=0, color=color, alpha=0.045, edgecolor="none", zorder=0)
    axis.yaxis.grid(True, color="#c7c7c7", linewidth=0.7)
    axis.xaxis.grid(True, color="#a9a9a9", linewidth=0.8, linestyle="--")
    axis.spines["polar"].set_color("#6b7280")
    return figure, axis, closed_angles


def _save(figure: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    png_path = path.with_suffix(".png")
    temporary_png = path.parent / ".radar-render.png"
    figure.savefig(temporary_png, format="png", dpi=240, bbox_inches="tight")
    temporary_png.replace(png_path)
    svg_path = path.with_suffix(".svg")
    figure.savefig(svg_path, bbox_inches="tight")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )


def render_single(profile: Profile, output_path: Path) -> None:
    plt = _matplotlib()
    figure, axis, angles = _radar_axes(plt)
    values = list(profile.values) + [profile.values[0]]
    axis.plot(angles, values, color="#3D4C9E", linewidth=2.8, marker="o", markersize=5.5)
    axis.fill(angles, values, color="#5E72E4", alpha=0.16)
    axis.scatter(angles[:-1], values[:-1], c=AXIS_COLORS, s=42, zorder=4, edgecolors="white", linewidths=0.8)
    axis.set_title(profile.ruler_name, pad=34, fontsize=22, fontweight="bold", color="#202938")
    _save(figure, output_path)
    plt.close(figure)


def render_comparison(left: Profile, right: Profile, output_path: Path) -> None:
    plt = _matplotlib()
    figure, axis, angles = _radar_axes(plt)
    styles = ((left, "#3D4C9E", "o", "-"), (right, "#E76F51", "s", "--"))
    for profile, color, marker, line_style in styles:
        values = list(profile.values) + [profile.values[0]]
        axis.plot(angles, values, color=color, linewidth=2.3, marker=marker, markersize=5, linestyle=line_style, label=profile.ruler_name)
    axis.set_title(f"{left.ruler_name} · {right.ruler_name}", pad=34, fontsize=22, fontweight="bold", color="#202938")
    axis.legend(loc="upper right", bbox_to_anchor=(1.2, 1.13), frameon=True, fontsize=11)
    _save(figure, output_path)
    plt.close(figure)


def write_samples(output_dir: Path | None = None) -> dict[str, Any]:
    profiles = load_profiles()
    config = _project_profile_config()["radar_samples"]
    output_dir = output_dir or ROOT / config["output_dir"]
    selected = sample_profiles(profiles)
    written: list[str] = []
    for profile in selected:
        stem = f"single-{profile.ruler_id}"
        render_single(profile, output_dir / stem)
        written.extend([f"{stem}.svg", f"{stem}.png"])
    for left_id, right_id in COMPARISONS:
        left, right = profiles[left_id], profiles[right_id]
        stem = f"compare-{left_id}--{right_id}"
        render_comparison(left, right, output_dir / stem)
        written.extend([f"{stem}.svg", f"{stem}.png"])

    index = {
        "schema_version": "emperor-profile-radar-samples-v1",
        "source": "config/project.yml:profile_assessment.settled_axes",
        "axis_order": list(AXIS_ORDER),
        "scale": [0, 100],
        "population_count": len(profiles),
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "composite_ranking_write": False,
        "samples": [{"ruler_id": row.ruler_id, "ruler_name": row.ruler_name, "values": list(row.values)} for row in selected],
        "comparisons": [{"left": left, "right": right} for left, right in COMPARISONS],
        "files": sorted(written),
    }
    (output_dir / "00-雷达图小样索引.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rationale = "\n".join(
        f"- `{row.ruler_id}`：{row.ruler_name}（八轴值：{' / '.join(map(str, row.values))}）"
        for row in selected
    )
    (output_dir / "00-雷达图小样说明.md").write_text(
        "# 八轴人物画像雷达图小样\n\n"
        "固定八轴顺序为 M1、M2、M3、M4、C1、C2、C3、C5，刻度统一为 0—100。SVG 保留可编辑文本；PNG 以 240 DPI 输出。"
        "八个四字轴标题向外留白，使用多色标签与淡色扇区；对比线继续以线型、标记和颜色共同区分。\n\n"
        "## 候选人物\n\n" + rationale + "\n\n"
        "候选覆盖秦、汉、唐、元、明、清、北宋，并包含高位、低位和明显不均衡画像；选择只服务图表可读性测试，非总分或排名。\n",
        encoding="utf-8",
    )
    return index
