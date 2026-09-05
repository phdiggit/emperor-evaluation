from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SETTLEMENT_DIRECTORY = "docs/评分结算/第一项政权奠基与统一贡献及能力"
TOTAL_SETTLEMENT = f"{SETTLEMENT_DIRECTORY}/01-第一项政权奠基与统一贡献及能力正式结算.md"
COMPONENT_SETTLEMENTS = (
    f"{SETTLEMENT_DIRECTORY}/01-第一项A统一主链客观贡献正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/02-第一项B1创业难度与战略效率正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/03-第一项B2创业组织与政治整合正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/04-第一项C1本人军事统帅能力正式结算.md",
    f"{SETTLEMENT_DIRECTORY}/05-第一项C2本人前线指挥能力正式结算.md",
)

_TOTAL_ROW = re.compile(
    r"^\|\s*(?P<rank>\d+)\s*\|\s*(?P<name>[^|]+?)\s*\|\s*"
    r"(?P<a>[0-9.]+)\s*\|\s*(?P<b1>[0-9.]+)\s*\|\s*"
    r"(?P<b2>[0-9.]+)\s*\|\s*(?P<c1>[0-9.]+)\s*\|\s*"
    r"(?P<c2>[0-9.]+)\s*\|\s*(?P<gross>[0-9.]+)\s*\|\s*"
    r"(?P<cost_debit>[0-9.]+)\s*\|\s*\*\*(?P<total>[0-9.]+)\*\*\s*\|$",
    re.MULTILINE,
)


def load_first_item_markdown_settlement(workspace_root: Path, *, validate_cost: bool = True) -> list[dict[str, Any]]:
    path = workspace_root / TOTAL_SETTLEMENT
    text = path.read_text(encoding="utf-8-sig")
    rows = []
    for match in _TOTAL_ROW.finditer(text):
        row = {key: value.strip() for key, value in match.groupdict().items()}
        row["rank"] = int(row["rank"])
        for key in ("a", "b1", "b2", "c1", "c2", "gross", "cost_debit", "total"):
            row[key] = float(row[key])
        rows.append(row)
    if not rows or len({row["name"] for row in rows}) != len(rows):
        raise ValueError("第一项Markdown正式结算为空或存在重复适用对象")
    for index, row in enumerate(rows):
        if row["rank"] != index + 1:
            raise ValueError(f"第一项Markdown排名不连续：{row['name']}")
        if abs(sum(row[key] for key in ("a", "b1", "b2", "c1", "c2")) - row["gross"]) > 1e-9:
            raise ValueError(f"第一项Markdown分项和不等于五轴合计：{row['name']}")
        if abs(max(0, row["gross"] - row["cost_debit"]) - row["total"]) > 1e-8:
            raise ValueError(f"第一项Markdown成本扣除与净分不一致：{row['name']}")
        if not 0 <= row["total"] <= 240:
            raise ValueError(f"第一项Markdown总分越界：{row['name']}")
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
    missing = [
        relative for relative in COMPONENT_SETTLEMENTS
        if not (workspace_root / relative).is_file()
    ]
    if missing:
        raise ValueError(f"第一项Markdown分项正式结算缺失：{', '.join(missing)}")
    return {
        "path": TOTAL_SETTLEMENT,
        "record_count": len(rows),
        "ranked_count": len(rows),
        "min_score": min(row["total"] for row in rows),
        "max_score": max(row["total"] for row in rows),
        "component_paths": list(COMPONENT_SETTLEMENTS),
    }
