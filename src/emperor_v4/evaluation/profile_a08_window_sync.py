"""A08 canonical actual-power-window contract and synchronization audit."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.canonical_ruler_pool import write_canonical_ruler_pool
from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.profile_markdown import write_axes
from emperor_v4.evaluation.profile_registry import write_profile_manifest


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SUMMARY = PROFILE_ROOT / "八轴结算汇总.md"
AUDIT = PROFILE_ROOT / "交叉轴复核" / "10-A08实际权力窗口统一同步审计.json"
AXES = ("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5")
GRADE_FIELDS = ("axis_grade", "position", "score_100", "radar_value")
REQUIRED_TOTAL_CLAUSES = (
    "称帝前已经实际主导创业、军政、政权奠基或最高责任中心",
    "窗口纳入只改变观察范围和阶段覆盖，不自动升档、降档或改变雷达值",
)
REQUIRED_DATA_CLAUSES = (
    "actual_power_window`的日期边界只读取规范人物池",
    "不得按轴命题自行缩短或延长",
    "窗口扩展只扩大可观察范围",
)


def _config() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))["profile_assessment"]


def _payloads() -> dict[str, dict[str, Any]]:
    config = _config()
    return {
        axis: load_json(ROOT / entry["json"])
        for axis, entry in config["settled_axes"].items()
    }


def _audit_paths() -> list[Path]:
    config = _config()
    paths: list[Path] = []
    for axis in AXES:
        for entry in config["settled_axes"][axis].get("audit_jsons") or []:
            path = ROOT / "docs/评分结算/皇帝人物画像" / entry["path"]
            if path.is_file():
                paths.append(path)
    return paths


def _pool() -> dict[str, Any]:
    return load_json(ROOT / "config/common/canonical-ruler-pool.json")


def _nested_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_nested_tuple(item) for item in value)
    return value


def _window_boundary(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return _nested_tuple(value)
    text = str(value or "").strip()
    if text.startswith("[["):
        try:
            return _nested_tuple(json.loads(text))
        except json.JSONDecodeError:
            pass
    matches = re.findall(r"前?\d{1,4}\s*[—-]\s*前?\d{1,4}", text)
    if matches:
        return tuple(re.sub(r"\s+", "", match) for match in matches)
    match = re.search(r"前?\d{1,4}", text)
    return match.group(0) if match else text


def _start_key(value: Any) -> tuple[int, int]:
    boundary = _window_boundary(value)
    if isinstance(boundary, tuple) and boundary and isinstance(boundary[0], tuple):
        value = boundary[0][0]
    elif isinstance(boundary, tuple) and boundary:
        value = boundary[0]
    else:
        value = boundary
    text = str(value or "")
    match = re.search(r"(前)?(\d+)", text)
    if not match:
        return (10**9, 10**9)
    year = int(match.group(2))
    return (-year if match.group(1) else year, 0)


def _summary_cells(line: str) -> list[str] | None:
    if not line.startswith("| ") or line.startswith("|---"):
        return None
    cells = [cell.strip() for cell in line[1:-1].split("|")]
    return cells if len(cells) >= 13 else None


def _summary_start_label(value: Any) -> str:
    text = str(value or "")
    if text.startswith("[["):
        try:
            text = str(json.loads(text)[0][0])
        except (json.JSONDecodeError, IndexError, TypeError):
            pass
    match = re.search(r"前?\d{1,4}", text)
    return f"{match.group(0)}年" if match else "—"


def _sync_summary(pool_by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = SUMMARY.read_text(encoding="utf-8")
    lines = text.splitlines()
    header_index = next(index for index, line in enumerate(lines) if line.startswith("| 时序 |"))
    end_index = header_index + 2
    rows: list[tuple[int, list[str]]] = []
    while end_index < len(lines):
        cells = _summary_cells(lines[end_index])
        if cells is None:
            break
        name = cells[2]
        if name not in pool_by_name:
            raise ValueError(f"八轴汇总人物不在规范池: {name}")
        row = pool_by_name[name]
        cells[1] = _summary_start_label(row["actual_power_window"])
        cells[4] = str(row["actual_power_window"])
        rows.append((int(cells[0]), cells))
        end_index += 1
    if len(rows) != 184:
        raise ValueError(f"八轴汇总人物行数量不是184: {len(rows)}")
    rows.sort(key=lambda item: (_start_key(pool_by_name[item[1][2]]["actual_power_window"]), item[0]))
    rendered = []
    for sequence, (_, cells) in enumerate(rows, 1):
        cells[0] = str(sequence)
        rendered.append("| " + " | ".join(cells) + " |")
    new_lines = lines[: header_index + 2] + rendered + lines[end_index:]
    changed = "\n".join(new_lines).rstrip() + "\n" != text
    if changed:
        SUMMARY.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return {"changed": changed, "row_count": len(rows), "li_cunxu_sequence": next(cells[0] for _, cells in rows if cells[2] == "李存勖")}


def _window_mismatches(payloads: dict[str, dict[str, Any]], pool_by_id: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    boundary_mismatches: list[dict[str, Any]] = []
    annotation_only: list[dict[str, Any]] = []
    for axis in AXES:
        for row in payloads[axis]["records"]:
            canonical = pool_by_id[row["ruler_id"]]["actual_power_window"]
            current = row.get("actual_power_window")
            if _window_boundary(current) != _window_boundary(canonical):
                boundary_mismatches.append(
                    {
                        "axis": axis,
                        "ruler_id": row["ruler_id"],
                        "ruler_name": row["ruler_name"],
                        "canonical": canonical,
                        "current": current,
                    }
                )
            elif current != canonical:
                annotation_only.append(
                    {
                        "axis": axis,
                        "ruler_id": row["ruler_id"],
                        "ruler_name": row["ruler_name"],
                        "canonical": canonical,
                        "current": current,
                    }
                )
    return boundary_mismatches, annotation_only


def _sync_nested_windows(value: Any, pool_by_id: dict[str, dict[str, Any]], inherited_ruler_id: str | None = None) -> int:
    changes = 0
    if isinstance(value, dict):
        ruler_id = str(value.get("ruler_id") or inherited_ruler_id or "")
        canonical_row = pool_by_id.get(ruler_id)
        if canonical_row and "actual_power_window" in value:
            canonical = canonical_row["actual_power_window"]
            if _window_boundary(value.get("actual_power_window")) != _window_boundary(canonical):
                value["actual_power_window"] = canonical
                changes += 1
        for child in value.values():
            changes += _sync_nested_windows(child, pool_by_id, ruler_id or inherited_ruler_id)
    elif isinstance(value, list):
        for child in value:
            changes += _sync_nested_windows(child, pool_by_id, inherited_ruler_id)
    return changes


def _sync_audit_files(pool_by_id: dict[str, dict[str, Any]]) -> tuple[list[dict[str, str]], int]:
    changes: list[dict[str, str]] = []
    total = 0
    for path in _audit_paths():
        payload = load_json(path)
        changed = _sync_nested_windows(payload, pool_by_id)
        if not changed:
            continue
        write_json(path, payload)
        total += changed
        changes.append({"path": path.relative_to(ROOT).as_posix(), "field_change_count": str(changed)})
    return changes, total


def _audit_window_mismatches(pool_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for path in _audit_paths():
        payload = load_json(path)

        def walk(value: Any, inherited_ruler_id: str | None = None) -> None:
            if isinstance(value, dict):
                ruler_id = str(value.get("ruler_id") or inherited_ruler_id or "")
                if ruler_id in pool_by_id and "actual_power_window" in value:
                    canonical = pool_by_id[ruler_id]["actual_power_window"]
                    if _window_boundary(value.get("actual_power_window")) != _window_boundary(canonical):
                        mismatches.append(
                            {
                                "path": path.relative_to(ROOT).as_posix(),
                                "ruler_id": ruler_id,
                                "current": value.get("actual_power_window"),
                                "canonical": canonical,
                            }
                        )
                for child in value.values():
                    walk(child, ruler_id or inherited_ruler_id)
            elif isinstance(value, list):
                for child in value:
                    walk(child, inherited_ruler_id)

        walk(payload)
    return mismatches


def _value_snapshot(payloads: dict[str, dict[str, Any]]) -> dict[tuple[str, str], tuple[Any, ...]]:
    return {
        (axis, row["ruler_id"]): tuple(row.get(field) for field in GRADE_FIELDS)
        for axis in AXES
        for row in payloads[axis]["records"]
    }


def _build_audit() -> dict[str, Any]:
    payloads = _payloads()
    pool = _pool()
    pool_by_id = {row["ruler_id"]: row for row in pool["records"] if row["pool_status"] == "INCLUDED"}
    boundary_mismatches, annotation_only = _window_mismatches(payloads, pool_by_id)
    contract_total = (ROOT / "docs/项目总纲/皇帝人物画像评估体系合同.md").read_text(encoding="utf-8")
    contract_data = (ROOT / "docs/分项规则/人物画像轴/00-共同数据与发布合同.md").read_text(encoding="utf-8")
    summary = _sync_summary_state(pool_by_id)
    audit_mismatches = _audit_window_mismatches(pool_by_id)
    errors: list[Any] = []
    if boundary_mismatches:
        errors.extend(boundary_mismatches)
    errors.extend(summary["errors"])
    errors.extend(audit_mismatches)
    if any(clause not in contract_total for clause in REQUIRED_TOTAL_CLAUSES):
        errors.append("总合同缺少A08口径")
    if any(clause not in contract_data for clause in REQUIRED_DATA_CLAUSES):
        errors.append("共同数据合同缺少A08口径")
    li_cunxu = pool_by_id.get("RULER-FD-LI-CUNXU") or {}
    adjudication = li_cunxu.get("actual_power_window_adjudication") or {}
    if li_cunxu.get("actual_power_window") != "908—926年" or not adjudication.get("evidence_refs"):
        errors.append("李存勖规范窗口裁决未闭合")
    return {
        "schema_version": "profile-a08-actual-power-window-sync-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A08_ACTUAL_POWER_WINDOW_CONTRACT_AND_FULL_POOL_SYNC",
        "source_registry": "config/project.yml:profile_assessment",
        "population_count": 184,
        "axis_count": len(AXES),
        "boundary_mismatch_count": len(boundary_mismatches),
        "boundary_mismatches": boundary_mismatches,
        "annotation_only_count": len(annotation_only),
        "annotation_only_examples": annotation_only[:80],
        "audit_window_mismatch_count": len(audit_mismatches),
        "audit_window_mismatches": audit_mismatches,
        "summary": summary,
        "formal_value_write": False,
        "grade_write": False,
        "position_write": False,
        "score_write": False,
        "radar_write": False,
        "unresolved_count": len(errors),
        "errors": errors,
    }


def _sync_summary_state(pool_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = SUMMARY.read_text(encoding="utf-8")
    lines = text.splitlines()
    header_index = next((index for index, line in enumerate(lines) if line.startswith("| 时序 |")), None)
    if header_index is None:
        return {"row_count": 0, "errors": ["八轴汇总缺少主表"]}
    end_index = header_index + 2
    rows = []
    while end_index < len(lines):
        cells = _summary_cells(lines[end_index])
        if cells is None:
            break
        pool_row = next((row for row in pool_by_id.values() if row["ruler_name"] == cells[2]), None)
        if pool_row is None:
            return {"row_count": len(rows), "errors": [f"八轴汇总人物不在规范池: {cells[2]}"]}
        rows.append((int(cells[0]), cells, pool_row))
        end_index += 1
    errors = []
    expected_order = sorted(rows, key=lambda item: (_start_key(item[2]["actual_power_window"]), item[0]))
    for index, (_, cells, pool_row) in enumerate(expected_order, 1):
        if cells[0] != str(index) or cells[1] != _summary_start_label(pool_row["actual_power_window"]) or cells[4] != str(pool_row["actual_power_window"]):
            errors.append({"ruler_name": cells[2], "sequence": cells[0], "expected_sequence": str(index), "window": cells[4], "expected_window": pool_row["actual_power_window"]})
    return {"row_count": len(rows), "errors": errors}


def write(root: Path = ROOT) -> dict[str, Any]:
    del root
    pool_report = write_canonical_ruler_pool(ROOT)
    pool = _pool()
    pool_by_id = {row["ruler_id"]: row for row in pool["records"] if row["pool_status"] == "INCLUDED"}
    before = _payloads()
    before_values = _value_snapshot(before)
    changes: list[dict[str, str]] = []
    changed_axes: list[str] = []
    polities = load_ruler_polities(ROOT)
    for axis in AXES:
        payload = before[axis]
        changed = False
        for row in payload["records"]:
            if _sync_nested_windows(row, pool_by_id):
                changes.append({"axis": axis, "ruler_id": row["ruler_id"], "ruler_name": row["ruler_name"], "field": "actual_power_window"})
                changed = True
        if changed:
            changed_axes.append(axis)
            write_json(ROOT / _config()["settled_axes"][axis]["json"], payload, ruler_polities=polities)
    if changed_axes:
        write_axes(tuple(changed_axes))
    audit_changes, audit_field_change_count = _sync_audit_files(pool_by_id)
    summary = _sync_summary({row["ruler_name"]: row for row in pool_by_id.values()})
    manifest = write_profile_manifest()
    after = _payloads()
    after_values = _value_snapshot(after)
    if before_values != after_values:
        raise ValueError("A08窗口同步意外改变档位、位置、分数或雷达值")
    audit = _build_audit()
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    write_json(AUDIT, audit)
    if audit["unresolved_count"]:
        raise ValueError(f"A08写入后仍有未闭合窗口问题: {audit['unresolved_count']}")
    return {
        "pool": {key: str(value) for key, value in pool_report.items()},
        "manifest": manifest.relative_to(ROOT).as_posix(),
        "changed_axes": changed_axes,
        "window_change_count": len(changes),
        "window_changes": changes,
        "audit_window_change_count": audit_field_change_count,
        "audit_window_changes": audit_changes,
        "summary": summary,
        "formal_value_write": False,
        "grade_write": False,
        "position_write": False,
        "score_write": False,
        "radar_write": False,
    }


def verify(root: Path = ROOT) -> dict[str, Any]:
    del root
    expected = _build_audit()
    if not AUDIT.is_file():
        raise ValueError(f"A08审计文件不存在: {AUDIT}")
    if load_json(AUDIT) != expected:
        raise ValueError("A08审计文件与当前窗口、合同或汇总不一致")
    if expected["unresolved_count"]:
        raise ValueError(f"A08仍有未闭合窗口问题: {expected['unresolved_count']}")
    return {
        "status": "PASS",
        "population_count": expected["population_count"],
        "axis_count": expected["axis_count"],
        "boundary_mismatch_count": expected["boundary_mismatch_count"],
        "annotation_only_count": expected["annotation_only_count"],
        "formal_value_write": False,
    }


if __name__ == "__main__":
    import sys

    result = write() if len(sys.argv) > 1 and sys.argv[1] == "write" else verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
