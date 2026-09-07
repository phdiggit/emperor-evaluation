"""A07 publication audit for historical display points.

`display_point_only` records retain a historical value for traceability, but
that value is not a current adjudication and must not enter the eight-axis
summary or radar consumers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.formal_json_store import load_json, write_json
from emperor_v4.evaluation.profile_markdown import render_profile_markdown
from emperor_v4.evaluation.profile_radar import (
    AXIS_ORDER,
    DISPLAY_POINT_STATES,
    SAMPLE_RULER_IDS,
    load_profiles,
    write_samples as write_radar_samples,
)


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
AUDIT = PROFILE_ROOT / "交叉轴复核" / "09-A07历史显示点发布同步审计.json"
SUMMARY = PROFILE_ROOT / "八轴结算汇总.md"
DISPLAY_NOTE = "- M2中`display_point_only=true`的记录只保留历史显示点；汇总显示为“显示点·档位（—）”，不得解释为当前正式实裁或当前雷达值。"


def _config() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))["profile_assessment"]


def _payloads() -> dict[str, dict[str, Any]]:
    config = _config()
    return {
        axis: load_json(ROOT / entry["json"])
        for axis, entry in config["settled_axes"].items()
    }


def _is_display_point(row: dict[str, Any]) -> bool:
    return bool(row.get("display_point_only")) or row.get("adjudication_state") in DISPLAY_POINT_STATES


def _display_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for axis in AXIS_ORDER:
        for row in payloads[axis]["records"]:
            if _is_display_point(row):
                rows.append(
                    {
                        "axis": axis,
                        "ruler_id": row["ruler_id"],
                        "ruler_name": row["ruler_name"],
                        "historical_display_grade": row.get("historical_display_grade") or f"{row['axis_grade']}-{row['position']}",
                        "historical_display_radar_value": row.get("historical_display_radar_value") or row.get("radar_value"),
                        "adjudication_state": row.get("adjudication_state"),
                        "display_point_only": bool(row.get("display_point_only")),
                    }
                )
    return rows


def _m2_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in payloads["M2"]["records"]:
        rows.append(
            {
                "axis": "M2",
                "ruler_id": row["ruler_id"],
                "ruler_name": row["ruler_name"],
                "axis_grade": row["axis_grade"],
                "position": row["position"],
                "radar_value": row["radar_value"],
                "historical_display_grade": row.get("historical_display_grade"),
                "adjudication_state": row.get("adjudication_state"),
                "display_point_only": bool(row.get("display_point_only")),
            }
        )
    return rows


def _summary_cells(line: str) -> list[str] | None:
    if not line.startswith("| ") or line.startswith("|---"):
        return None
    cells = [cell.strip() for cell in line[1:-1].split("|")]
    return cells if len(cells) >= 13 else None


def _expected_summary_cell(row: dict[str, Any]) -> str:
    if _is_display_point(row):
        grade = row.get("historical_display_grade") or f"{row['axis_grade']}-{row['position']}"
        return f"显示点·{grade}（—）"
    return f"{row['axis_grade']}-{row['position']}（{row['radar_value']}）"


def _summary_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    text = SUMMARY.read_text(encoding="utf-8")
    lines = text.splitlines()
    display_rows = [row for row in rows if row["axis"] == "M2" and _is_display_point(row)]
    expected_by_name = {row["ruler_name"]: _expected_summary_cell(row) for row in rows if row["axis"] == "M2"}
    seen: dict[str, str] = {}
    for line in lines:
        cells = _summary_cells(line)
        if cells is None or cells[2] not in expected_by_name:
            continue
        seen[cells[2]] = cells[6]
    errors = [
        {"ruler_name": name, "expected": expected, "actual": seen.get(name)}
        for name, expected in expected_by_name.items()
        if seen.get(name) != expected
    ]
    return {
        "path": SUMMARY.relative_to(PROFILE_ROOT).as_posix(),
        "display_point_count": len(display_rows),
        "matched_count": len(set(expected_by_name) & set(seen)),
        "errors": errors,
        "note_present": DISPLAY_NOTE in text,
    }


def update_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    text = SUMMARY.read_text(encoding="utf-8")
    lines = text.splitlines()
    m2_rows = [row for row in rows if row["axis"] == "M2"]
    expected_by_name = {row["ruler_name"]: _expected_summary_cell(row) for row in m2_rows}
    changed = False
    seen: set[str] = set()
    updated_lines: list[str] = []
    for line in lines:
        cells = _summary_cells(line)
        if cells is not None and cells[2] in expected_by_name:
            name = cells[2]
            seen.add(name)
            if cells[6] != expected_by_name[name]:
                cells[6] = expected_by_name[name]
                line = "| " + " | ".join(cells) + " |"
                changed = True
        updated_lines.append(line)
    if not set(expected_by_name) <= seen:
        missing = sorted(set(expected_by_name) - seen)
        raise ValueError(f"八轴汇总缺少A07人物行: {missing}")
    if DISPLAY_NOTE not in updated_lines:
        insert_at = next(
            (index + 1 for index, line in enumerate(updated_lines) if "雷达值沿用对应轴正式 JSON" in line),
            None,
        )
        if insert_at is None:
            raise ValueError("八轴汇总缺少可插入A07口径的位置")
        updated_lines.insert(insert_at, DISPLAY_NOTE)
        changed = True
    if changed:
        SUMMARY.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return {"changed": changed, "display_point_count": sum(_is_display_point(row) for row in m2_rows)}


def _radar_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = load_profiles()
    errors: list[dict[str, Any]] = []
    for row in rows:
        profile = profiles[row["ruler_id"]]
        axis_index = AXIS_ORDER.index(row["axis"])
        if profile.values[axis_index] is not None or row["axis"] not in profile.display_point_axes:
            errors.append(
                {
                    "ruler_id": row["ruler_id"],
                    "axis": row["axis"],
                    "profile_value": profile.values[axis_index],
                    "display_point_axes": list(profile.display_point_axes),
                }
            )
    omitted = [
        {
            "ruler_id": ruler_id,
            "ruler_name": profiles[ruler_id].ruler_name,
            "display_point_axes": list(profiles[ruler_id].display_point_axes),
        }
        for ruler_id in SAMPLE_RULER_IDS
        if profiles[ruler_id].display_point_axes
    ]
    stale_files = []
    radar_output = ROOT / _config()["radar_samples"]["output_dir"]
    for row in omitted:
        for suffix in (".svg", ".png"):
            path = radar_output / f"single-{row['ruler_id']}{suffix}"
            if path.is_file():
                stale_files.append(path.relative_to(ROOT).as_posix())
    return {
        "display_point_axis_value_errors": errors,
        "omitted_sample_count": len(omitted),
        "omitted_samples": omitted,
        "stale_omitted_sample_files": stale_files,
    }


def build_audit() -> dict[str, Any]:
    payloads = _payloads()
    rows = _display_rows(payloads)
    m2_rows = _m2_rows(payloads)
    m2 = payloads["M2"]
    m2_path = ROOT / _config()["settled_axes"]["M2"]["markdown"]
    markdown_errors = []
    if m2_path.read_text(encoding="utf-8") != render_profile_markdown(m2):
        markdown_errors.append("M2阅读视图不是正式JSON同值视图")
    summary = _summary_state(m2_rows)
    radar = _radar_state(rows)
    errors = list(summary["errors"])
    if not summary["note_present"]:
        errors.append("八轴汇总缺少A07显示点口径说明")
    errors.extend(markdown_errors)
    errors.extend(radar["display_point_axis_value_errors"])
    errors.extend(radar["stale_omitted_sample_files"])
    return {
        "schema_version": "profile-a07-display-point-publication-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A07_HISTORICAL_DISPLAY_POINT_SUMMARY_AND_RADAR_FULL_POOL",
        "source_registry": "config/project.yml:profile_assessment",
        "population_count": int(_config()["population_count"]),
        "display_point_count": len(rows),
        "display_point_axes": {axis: sum(row["axis"] == axis for row in rows) for axis in AXIS_ORDER if any(row["axis"] == axis for row in rows)},
        "display_points": rows,
        "summary": summary,
        "radar_consumer": radar,
        "markdown_errors": markdown_errors,
        "unresolved_count": len(errors),
        "formal_score_write": False,
        "grade_write": False,
        "position_write": False,
        "radar_value_write": False,
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    del root
    payloads = _payloads()
    rows = _display_rows(payloads)
    summary_update = update_summary(_m2_rows(payloads))
    radar_report = write_radar_samples()
    audit = build_audit()
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    write_json(AUDIT, audit)
    if audit["unresolved_count"]:
        raise ValueError(f"A07写入后仍有未闭合发布问题: {audit['unresolved_count']}")
    return {
        "audit_json": AUDIT.relative_to(ROOT).as_posix(),
        "summary_update": summary_update,
        "radar_samples": {
            "sample_count": len(radar_report["samples"]),
            "omitted_sample_count": len(radar_report.get("omitted_samples", [])),
        },
        "display_point_count": audit["display_point_count"],
        "formal_score_write": False,
        "grade_write": False,
        "position_write": False,
        "radar_value_write": False,
    }


def verify(root: Path = ROOT) -> dict[str, Any]:
    del root
    expected = build_audit()
    if not AUDIT.is_file():
        raise ValueError(f"A07审计文件不存在: {AUDIT}")
    if load_json(AUDIT) != expected:
        raise ValueError("A07审计文件与当前发布消费者不一致")
    if expected["unresolved_count"]:
        raise ValueError(f"A07仍有未闭合发布问题: {expected['unresolved_count']}")
    return {
        "status": "PASS",
        "population_count": expected["population_count"],
        "display_point_count": expected["display_point_count"],
        "display_point_axes": expected["display_point_axes"],
        "formal_score_write": False,
        "radar_value_write": False,
    }


if __name__ == "__main__":
    import sys

    result = write() if len(sys.argv) > 1 and sys.argv[1] == "write" else verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
