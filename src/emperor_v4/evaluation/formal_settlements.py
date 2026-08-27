from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.canonical_ruler_pool import verify_canonical_ruler_pool
from emperor_v4.evaluation.composite_ranking import verify_composite_ranking


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

SECOND_ITEM_COMPONENT_PATHS = {
    "A": "docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json",
    "B1": "docs/评分结算/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json",
    "B2": "docs/评分结算/第二项治国净收益/制度行政/03-B2反馈纠错与权力约束方向卡.json",
    "method": "docs/评分结算/第二项治国净收益/制度行政/04-治理手段165分正式结算.json",
    "C1": "docs/评分结算/第二项治国净收益/财政民生/01-C1正式结算.json",
    "C2": "docs/评分结算/第二项治国净收益/财政民生/02-C2正式结算.json",
    "C3": "docs/评分结算/第二项治国净收益/财政民生/03-C3正式结算.json",
    "C4": "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json",
    "result": "docs/评分结算/第二项治国净收益/财政民生/05-治理结果220分正式结算.json",
    "D1": "docs/评分结算/第二项治国净收益/政权交接稳定/01-D1继任行政连续性方向卡.json",
    "D3": "docs/评分结算/第二项治国净收益/政权交接稳定/02-D3政权交接稳定方向卡.json",
    "handoff": "docs/评分结算/第二项治国净收益/政权交接稳定/03-交接质量20分正式结算.json",
}


def _competition_rank(sorted_scores: list[float], index: int) -> int:
    return sorted_scores.index(sorted_scores[index]) + 1


def _records_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = payload.get("records") or payload.get("scores") or []
    return {str(row["ruler_id"]): row for row in records}


def _verify_records_hash(payload: dict[str, Any], label: str) -> None:
    if payload.get("payload_sha256_basis") != "canonical_records_json_v1":
        raise ValueError(f"{label} payload_sha256缺少规范算法声明")
    rows = payload.get("records") or payload.get("scores")
    serialized = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    if payload.get("payload_sha256") != expected:
        raise ValueError(f"{label} payload_sha256与当前记录不一致")


def _verify_second_item_components(workspace_root: Path) -> dict[str, Any]:
    payloads = {
        key: json.loads((workspace_root / path).read_text(encoding="utf-8"))
        for key, path in SECOND_ITEM_COMPONENT_PATHS.items()
    }
    for key in ("C4", "result"):
        _verify_records_hash(payloads[key], f"第二项{key}")
    indexed = {key: _records_by_id(payload) for key, payload in payloads.items()}
    id_sets = {key: set(rows) for key, rows in indexed.items()}
    complete_ids = id_sets["method"]
    complete_keys = {"A", "B1", "B2", "method", "D1", "D3", "handoff"}
    complete_differences = {
        key: len(id_sets[key] ^ complete_ids)
        for key in complete_keys
        if id_sets[key] != complete_ids
    }
    finance_ids = id_sets["C1"]
    finance_keys = {"C1", "C2", "C3", "C4", "result"}
    finance_differences = {
        key: len(id_sets[key] ^ finance_ids)
        for key in finance_keys
        if id_sets[key] != finance_ids
    }
    if (
        len(complete_ids) != 185
        or complete_differences
        or not complete_ids <= finance_ids
        or finance_differences
    ):
        raise ValueError(
            "第二项组件ID覆盖不一致："
            f"整体={len(complete_ids)}，财政民生={len(finance_ids)}，"
            f"整体差异={complete_differences}，财政差异={finance_differences}"
        )

    top = _records_by_id(
        json.loads(
            (workspace_root / str(SETTLEMENT_SPECS["second_item"]["path"])).read_text(
                encoding="utf-8"
            )
        )
    )
    top_payload = json.loads(
        (workspace_root / str(SETTLEMENT_SPECS["second_item"]["path"])).read_text(
            encoding="utf-8"
        )
    )
    _verify_records_hash(top_payload, "第二项总表")
    if set(top) != complete_ids:
        raise ValueError("第二项总表与组件ID集合不一致")

    for ruler_id in finance_ids:
        result = indexed["result"][ruler_id]
        components = [float(indexed[key][ruler_id]["score"]) for key in ("C1", "C2", "C3", "C4")]
        expected_result = round(sum(components), 1)
        if abs(float(result["score"]) - expected_result) > 1e-9:
            raise ValueError(f"第二项治理结果公式错误：{result['ruler_name']}")

    for ruler_id in complete_ids:
        method = indexed["method"][ruler_id]
        a = float(indexed["A"][ruler_id]["direction_index"])
        b1 = float(indexed["B1"][ruler_id]["direction_index"])
        b2 = float(indexed["B2"][ruler_id]["direction_index"])
        expected_method = round(
            0.8 * (max(a, b1) + 0.5 * min(a, b1)) + 1e-9, 1
        ) + round(
            45 / 80 * b2 + 1e-9, 1
        )
        if abs(float(method["score"]) - expected_method) > 1e-9:
            raise ValueError(f"第二项治理手段公式错误：{method['ruler_name']}")

        result = indexed["result"][ruler_id]

        total = top[ruler_id]
        expected_total = round(
            float(method["score"])
            + float(result["score"])
            + float(indexed["handoff"][ruler_id]["score"]),
            1,
        )
        copied = (
            float(total["governance_method_score"]),
            float(total["governance_result_score"]),
            float(total["handoff_score"]),
        )
        expected_copied = (
            float(method["score"]),
            float(result["score"]),
            float(indexed["handoff"][ruler_id]["score"]),
        )
        if copied != expected_copied or abs(float(total["second_item_score"]) - expected_total) > 1e-9:
            raise ValueError(f"第二项总表组件抄录或总分公式错误：{total['ruler_name']}")
        for key in ("C1", "C2", "C3", "C4"):
            if float(total[f"{key}_score"]) != float(indexed[key][ruler_id]["score"]):
                raise ValueError(f"第二项总表{key}抄录错误：{total['ruler_name']}")
    return {
        "component_file_count": len(payloads),
        "complete_ruler_count": len(complete_ids),
        "finance_ruler_count": len(finance_ids),
    }


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
        "composite_ranking": verify_composite_ranking(workspace_root),
        "second_item_components": _verify_second_item_components(workspace_root),
        "items": reports,
    }
