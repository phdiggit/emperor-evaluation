from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.canonical_ruler_pool import verify_canonical_ruler_pool


SETTLEMENT_SPECS = {
    "first_item": {
        "path": "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json",
        "schema": "first-item-formal-settlement-v3",
        "score": "first_item_score_points",
        "rank": "canonical_rank",
        "range": (0, 240),
    },
    "second_item": {
        "path": "docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.json",
        "schema": "i2_total_405_signed_formal_v3",
        "score": "second_item_score",
        "rank": "rank",
        "range": (-45, 405),
    },
    "third_item": {
        "path": "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json",
        "schema": "emperor-v4-third-item-formal-settlement-v6-current-only",
        "score": "third_item_score_points",
        "rank": "rank",
        "range": (-40, 250),
    },
    "fourth_item": {
        "path": "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json",
        "schema": "fourth-item-signed-addon-formal-settlement-v1",
        "score": "fourth_item_signed_adjustment",
        "rank": "rank",
        "range": (-67.5, 67.5),
    },
    "fifth_item": {
        "path": "docs/评分结算/第五项统治者政治素质/04-第五项统治者政治素质正式结算.json",
        "schema": "emperor-v4-fifth-item-formal-settlement-v2-evidence-truth",
        "score": "fifth_item_score_points",
        "rank": "rank",
        "range": (-18, 120),
    },
}


def _competition_rank(sorted_scores: list[float], index: int) -> int:
    return sorted_scores.index(sorted_scores[index]) + 1


def verify_formal_settlements(workspace_root: Path) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for item, spec in SETTLEMENT_SPECS.items():
        path = workspace_root / str(spec["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema = payload.get("schema_id") or payload.get("schema_version")
        if schema != spec["schema"]:
            raise ValueError(f"{item} schema不匹配：{schema}")
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError(f"{item} records为空或类型错误")
        declared_count = payload.get("record_count")
        if declared_count is not None and declared_count != len(records):
            raise ValueError(f"{item} record_count与records长度不一致")
        ruler_ids = [row.get("ruler_id") for row in records]
        if any(not value for value in ruler_ids) or len(set(ruler_ids)) != len(ruler_ids):
            raise ValueError(f"{item} ruler_id缺失或重复")

        ranked: list[tuple[float, int, str]] = []
        minimum, maximum = spec["range"]
        for row in records:
            score = row.get(spec["score"])
            rank = row.get(spec["rank"])
            if score is None:
                if rank is not None:
                    raise ValueError(f"{item} 无分值记录不应有排名：{row.get('ruler_name')}")
                continue
            numeric_score = float(score)
            if not minimum <= numeric_score <= maximum:
                raise ValueError(f"{item} 分值越界：{row.get('ruler_name')}={score}")
            if rank is None:
                raise ValueError(f"{item} 有分值记录缺少排名：{row.get('ruler_name')}")
            ranked.append((numeric_score, int(rank), str(row.get("ruler_name"))))

        scores = [score for score, _, _ in ranked]
        if scores != sorted(scores, reverse=True):
            raise ValueError(f"{item} records未按分值降序排列")
        for index, (_, rank, ruler_name) in enumerate(ranked):
            expected = _competition_rank(scores, index)
            if rank != expected:
                raise ValueError(f"{item} 竞争排名错误：{ruler_name}={rank}，应为{expected}")
        reports[item] = {
            "path": str(spec["path"]),
            "record_count": len(records),
            "ranked_count": len(ranked),
            "min_score": min(scores),
            "max_score": max(scores),
        }
    return {
        "status": "PASS",
        "canonical_pool": verify_canonical_ruler_pool(workspace_root),
        "items": reports,
    }
