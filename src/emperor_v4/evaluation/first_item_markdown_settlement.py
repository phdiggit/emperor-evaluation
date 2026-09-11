from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from emperor_v4.evaluation.first_item_weights import (
    A_MAX, B1_MAX, B2_MAX, C_MAX, C_POINTS as _C_POINTS,
    unification_pool,
)


SETTLEMENT_DIRECTORY = "docs/评分结算/第一项政权奠基与统一贡献及能力"
TOTAL_SETTLEMENT = f"{SETTLEMENT_DIRECTORY}/01-第一项政权奠基与统一贡献及能力正式结算.md"
COMPONENT_SETTLEMENTS = (
    f"{SETTLEMENT_DIRECTORY}/01-第一项A统一主链客观贡献正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/02-第一项B1创业难度与战略效率正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/03-第一项B2创业组织与政治整合正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/04-第一项C本人军事统帅与战争解题能力正式结算.md",
)

_TOTAL_ROW = re.compile(
    r"^\|\s*(?P<rank>\d+)\s*\|\s*(?P<name>[^|]+?)\s*\|\s*"
    r"(?P<a>[0-9.]+)\s*\|\s*(?P<b1>[0-9.]+)\s*\|\s*"
    r"(?P<b2>[0-9.]+)\s*\|\s*(?P<c>[0-9.]+)\s*\|\s*"
    r"(?P<gross>[0-9.]+)\s*\|\s*"
    r"(?P<cost_debit>[0-9.]+)\s*\|\s*\*\*(?P<total>[0-9.]+)\*\*\s*\|$",
    re.MULTILINE,
)

_C_ROW = re.compile(
    r"^\|\s*\d+\s*\|\s*(?P<name>[^|]+?)\s*\|\s*"
    r"(?P<route>STRATEGIC_COMMAND|HYBRID|NONE)\s*\|\s*"
    r"(?P<grade>C-[0-5](?:-(?:LOW|MID|HIGH))?)\s*\|\s*"
    r"\*\*(?P<points>[0-9.]+)\*\*\s*\|$",
    re.MULTILINE,
)

_A_POOL_DISPLAY = re.compile(r"项目A池为\*\*(?P<pool>[0-9.]+)\*\*")
_A_POOL_FORMULA = re.compile(
    r"项目A池\s*=\s*(?P<maximum>[0-9.]+)×\((?P<control>[0-9.]+)/1000\)\^0\.65=(?P<pool>[0-9.]+)"
)


def _validate_a_pool_text_consistency(workspace_root: Path) -> int:
    """Check displayed project A pools against the current formula and A max."""
    audited_sections = 0
    for relative in (COMPONENT_SETTLEMENTS[0], TOTAL_SETTLEMENT):
        text = (workspace_root / relative).read_text(encoding="utf-8-sig")
        sections = re.split(r"(?m)(?=^### )", text)
        for section in sections:
            display = _A_POOL_DISPLAY.findall(section)
            if not display:
                continue
            formulas = _A_POOL_FORMULA.findall(section)
            if len(display) != 1 or len(formulas) != 1:
                raise ValueError(f"第一项A池说明缺少唯一公式：{relative}")
            maximum, control, formula_pool = map(float, formulas[0])
            displayed_pool = float(display[0])
            expected_pool = unification_pool(control)
            if abs(maximum - A_MAX) > 1e-9:
                raise ValueError(f"第一项A池上限文字错误：{relative}")
            if abs(formula_pool - expected_pool) > 1e-9:
                raise ValueError(f"第一项A池公式结果错误：{relative}")
            if abs(displayed_pool - formula_pool) > 1e-9:
                raise ValueError(f"第一项A池说明与公式不一致：{relative}")
            audited_sections += 1
    if audited_sections == 0:
        raise ValueError("第一项A池说明未找到可审计段落")
    return audited_sections

def load_first_item_markdown_settlement(workspace_root: Path, *, validate_cost: bool = True) -> list[dict[str, Any]]:
    path = workspace_root / TOTAL_SETTLEMENT
    text = path.read_text(encoding="utf-8-sig")
    rows = []
    for match in _TOTAL_ROW.finditer(text):
        row = {key: value.strip() for key, value in match.groupdict().items()}
        row["rank"] = int(row["rank"])
        for key in ("a", "b1", "b2", "c", "gross", "cost_debit", "total"):
            row[key] = float(row[key])
        rows.append(row)
    if not rows or len({row["name"] for row in rows}) != len(rows):
        raise ValueError("第一项Markdown正式结算为空或存在重复适用对象")
    for index, row in enumerate(rows):
        if row["rank"] != index + 1:
            raise ValueError(f"第一项Markdown排名不连续：{row['name']}")
        if abs(sum(row[key] for key in ("a", "b1", "b2", "c")) - row["gross"]) > 1e-9:
            raise ValueError(f"第一项Markdown分项和不等于四轴合计：{row['name']}")
        if abs(max(0, row["gross"] - row["cost_debit"]) - row["total"]) > 1e-8:
            raise ValueError(f"第一项Markdown成本扣除与净分不一致：{row['name']}")
        if not 0 <= row["total"] <= 240:
            raise ValueError(f"第一项Markdown总分越界：{row['name']}")
        if any(not 0 <= row[key] <= cap for key, cap in
               (("a", A_MAX), ("b1", B1_MAX), ("b2", B2_MAX), ("c", C_MAX))):
            raise ValueError(f"第一项Markdown分轴超过合同上限：{row['name']}")
    if [row["total"] for row in rows] != sorted((row["total"] for row in rows), reverse=True):
        raise ValueError("第一项Markdown未按总分降序排列")
    if validate_cost:
        from emperor_v4.evaluation.first_item_cost import build_first_item_cost_report

        report = build_first_item_cost_report(workspace_root, formal_rows=rows)
        if report['status'] != 'READY':
            raise ValueError('第一项军事成本全池未闭合，禁止消费正式净分')
    return rows


def verify_first_item_markdown_settlement(workspace_root: Path) -> dict[str, Any]:
    rows = load_first_item_markdown_settlement(workspace_root)
    a_pool_text_audited_sections = _validate_a_pool_text_consistency(workspace_root)
    missing = [
        relative for relative in COMPONENT_SETTLEMENTS
        if not (workspace_root / relative).is_file()
    ]
    if missing:
        raise ValueError(f"第一项Markdown分项正式结算缺失：{', '.join(missing)}")
    c_text = (workspace_root / COMPONENT_SETTLEMENTS[-1]).read_text(encoding="utf-8-sig")
    c_rows = [match.groupdict() for match in _C_ROW.finditer(c_text)]
    c_by_name = {row["name"].strip(): row for row in c_rows}
    if len(c_rows) != len(rows) or len(c_by_name) != len(c_rows):
        raise ValueError("第一项C正式结算人数为空、缺失或重复")
    totals_by_name = {row["name"]: row for row in rows}
    a_text = (workspace_root / COMPONENT_SETTLEMENTS[0]).read_text(encoding="utf-8-sig")
    a_rows = {}
    for line in a_text.splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) == 7 and cells[0].isdigit():
            if cells[1] in a_rows:
                raise ValueError("第一项A人物重复")
            a_rows[cells[1]] = float(cells[-1].strip("*"))
    if set(a_rows) != set(totals_by_name):
        raise ValueError("第一项A与总表人物集合不一致")
    for name, points in a_rows.items():
        if points != totals_by_name[name]["a"]:
            raise ValueError(f"第一项A与总表分值不一致：{name}")
    if set(c_by_name) != set(totals_by_name):
        raise ValueError("第一项C与总表人物集合不一致")
    for name, c_row in c_by_name.items():
        points = float(c_row["points"])
        if points != _C_POINTS[c_row["grade"]]:
            raise ValueError(f"第一项C档位与分值不一致：{name}")
        if points != totals_by_name[name]["c"]:
            raise ValueError(f"第一项C与总表分值不一致：{name}")
        if (points == 0) != (c_row["route"] == "NONE"):
            raise ValueError(f"第一项C责任路线与分值不一致：{name}")
    return {
        "path": TOTAL_SETTLEMENT,
        "record_count": len(rows),
        "ranked_count": len(rows),
        "min_score": min(row["total"] for row in rows),
        "max_score": max(row["total"] for row in rows),
        "a_pool_text_audited_sections": a_pool_text_audited_sections,
        "component_paths": list(COMPONENT_SETTLEMENTS),
    }
