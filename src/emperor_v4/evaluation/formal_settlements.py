from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.canonical_ruler_pool import verify_canonical_ruler_pool
from emperor_v4.evaluation.composite_ranking import verify_composite_ranking
from emperor_v4.evaluation.third_item_current_settlement import (
    verify_current_third_item_settlement,
)
from emperor_v4.evaluation.third_item_d_settlement import (
    verify_third_item_d_formal_settlement,
)


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

IMPORTANT_INSTITUTION_REGISTRY = (
    "docs/公共成果/制度行政/03-重要制度发展节点链.json"
)


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


def verify_second_item_a_snapshot(workspace_root: Path) -> dict[str, Any]:
    a_payload = json.loads(
        (workspace_root / SECOND_ITEM_COMPONENT_PATHS["A"]).read_text(encoding="utf-8")
    )
    registry = json.loads(
        (workspace_root / IMPORTANT_INSTITUTION_REGISTRY).read_text(encoding="utf-8")
    )
    nodes = registry.get("nodes") or []
    active_node_ids = {
        str(node["institution_node_id"])
        for node in nodes
        if node.get("counts_toward_A") is True
    }
    active_nodes_by_id = {
        str(node["institution_node_id"]): node
        for node in nodes
        if node.get("counts_toward_A") is True
    }
    if (
        registry.get("record_count") != len(nodes)
        or registry.get("scoring_node_count") != len(active_node_ids)
        or registry.get("reference_node_count") != len(nodes) - len(active_node_ids)
    ):
        raise ValueError("第二项A上游03节点统计与当前JSON不一致")
    if len({node.get("institution_node_id") for node in nodes}) != len(nodes):
        raise ValueError("第二项A上游03存在重复节点ID")
    allowed_ca = {0.0, 0.5, 1.0, 2.0}
    allowed_m = {"M0", "M2", "M3"}
    generic_mechanisms = {
        "其他制度行政机制", "法律、司法与刑罚运行", "选官、人事与官僚专业化",
        "地方行政与政策交付", "A",
    }
    ca2_roles = {
        "FOUNDATIONAL_CREATION", "MAJOR_RESTRUCTURE", "MAJOR_RECONSTRUCTION",
        "CANONICALIZATION", "MAJOR_CODIFICATION", "MAJOR_CIVILIZATIONAL_CORRECTION",
        "STRUCTURAL_NON_DURABLE", "DURABILITY_EVIDENCE_PENDING",
    }
    grade_cost = {"G0": 0.0, "G1": 0.25, "G2": 0.5, "G3": 1.0, "G4": 2.0, "G5": 6.0}
    position_q = {"lower": 0.1, "lower-middle": 0.3, "middle": 0.5, "middle-upper": 0.7, "upper": 0.9}
    index_anchor = {
        "G0": {"lower": 2.0, "lower-middle": 6.0, "middle": 10.0, "middle-upper": 14.0, "upper": 18.0},
        "G1": {"lower": 22.0, "lower-middle": 26.0, "middle": 30.0, "middle-upper": 34.0, "upper": 38.0},
        "G2": {"lower": 41.5, "lower-middle": 44.5, "middle": 47.5, "middle-upper": 50.5, "upper": 53.4},
        "G3": {"lower": 56.5, "lower-middle": 59.5, "middle": 62.5, "middle-upper": 65.5, "upper": 68.4},
        "G4": {"lower": 71.5, "lower-middle": 74.5, "middle": 77.5, "middle-upper": 80.4, "upper": 83.5},
        "G5": {"lower": 86.5, "lower-middle": 89.5, "middle": 92.5, "middle-upper": 95.5, "upper": 98.5},
    }
    records = a_payload.get("records") or []
    if a_payload.get("A_position_formula_code") != "A_STRUCTURAL_THICKNESS_V2":
        raise ValueError("第二项A未使用当前position公式V2")
    for row in records:
        ruler_name = row.get("ruler_name")
        if float(row.get("C_A")) not in allowed_ca:
            raise ValueError(f"第二项A非法C_A：{ruler_name}={row.get('C_A')}")
        if row.get("grade") in {"G4", "G5"} and float(row.get("S_net") or 0) < 1:
            raise ValueError(f"第二项A高档未通过正向S门：{ruler_name}")
        referenced_ids = {
            str(item.get("institution_node_id"))
            for item in row.get("important_institutions") or []
        }
        missing_ids = sorted(referenced_ids - active_node_ids)
        if missing_ids:
            raise ValueError(f"第二项A引用未闭合：{ruler_name}={missing_ids}")
        referenced_nodes = [active_nodes_by_id[node_id] for node_id in referenced_ids]
        constructive_directions = {"positive", "mixed_positive", "mixed"}
        ca_value = float(row.get("C_A") or 0)
        if ca_value == 2 and not any(
            node.get("major_node_role") in ca2_roles
            and node.get("normative_direction") in constructive_directions
            for node in referenced_nodes
        ):
            raise ValueError(f"第二项A的C_A=2缺少纯重大支撑节点：{ruler_name}")
        if ca_value == 1 and ruler_name != "赵昀" and not any(
            node.get("major_node_role") == "LOCAL_OR_SECONDARY_CONSTRUCTION"
            and node.get("normative_direction") in constructive_directions
            for node in referenced_nodes
        ):
            raise ValueError(f"第二项A的C_A=1缺少局部支撑节点：{ruler_name}")
        if ca_value == 0.5 and not any(
            node.get("major_node_role") == "PAPER_OR_INCOMPLETE_CONSTRUCTION"
            and node.get("normative_direction") in constructive_directions
            for node in referenced_nodes
        ):
            raise ValueError(f"第二项A的C_A=0.5缺少未完成支撑节点：{ruler_name}")
        if row.get("grade") != "G0" and not referenced_nodes:
            if not (
                ruler_name == "赵昀"
                and ca_value == 1
                and "多个次级制度形成可识别组合" in str(row.get("grade_basis"))
            ):
                raise ValueError(f"第二项A非G0人物缺少03节点或组合裁决：{ruler_name}")
        for profile_key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
            for profile in row.get(profile_key) or []:
                if profile.get("M") not in allowed_m:
                    raise ValueError(
                        f"第二项A非法M档：{ruler_name}={profile.get('M')}"
                    )
                if profile.get("mechanism") in generic_mechanisms:
                    raise ValueError(f"第二项A仍有泛化机制：{ruler_name}={profile.get('mechanism')}")
        grade = str(row.get("grade"))
        if grade in {"G4", "G5"}:
            independent = 0.0
            seen_lifecycles: set[object] = set()
            for profile_key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
                for profile in row.get(profile_key) or []:
                    if profile.get("counts_toward_S") or profile.get("position_count_mode") == "context_only_no_effective_mechanism":
                        continue
                    lifecycle_key: object = (
                        profile.get("institution_node_id")
                        or profile.get("material_id")
                        or (profile.get("mechanism"), profile.get("direction"))
                    )
                    if lifecycle_key in seen_lifecycles:
                        continue
                    seen_lifecycles.add(lifecycle_key)
                    independent += float(profile.get("signed_weight") or 0)
            structural = 2 * float(row.get("S_net") or 0) + float(row.get("S_plus_plus") or 0)
        else:
            independent = float(row.get("A_independent_M_signed") or 0)
            structural = (
                2 * float(row.get("S_net") or 0)
                + float(row.get("S_plus_plus") or 0)
                + float(row.get("C_A") or 0) / 2
            )
        residual = structural - grade_cost[grade] + independent / 4
        has_profiles = any(
            row.get(profile_key)
            for profile_key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
        )
        if grade == "G0" and not has_profiles:
            expected_position = "middle"
        elif residual < -1:
            expected_position = "lower"
        elif residual < 0:
            expected_position = "lower-middle"
        elif residual < 1:
            expected_position = "middle"
        elif residual < 2:
            expected_position = "middle-upper"
        else:
            expected_position = "upper"
        formula_values = {
            "A_structural_thickness": round(structural, 2),
            "A_independent_M_signed": round(independent, 2),
            "A_independent_M_position_weight": round(independent / 4, 2),
            "A_position_residual": round(residual, 2),
            "position_q": position_q[expected_position],
            "direction_index": index_anchor[grade][expected_position],
        }
        if row.get("A_position_formula_code") != "A_STRUCTURAL_THICKNESS_V2" or row.get("position") != expected_position:
            raise ValueError(f"第二项A position公式不一致：{ruler_name}")
        for field, expected in formula_values.items():
            if abs(float(row.get(field) or 0) - expected) > 1e-9:
                raise ValueError(f"第二项A position字段不一致：{ruler_name}.{field}")
    markdown_path = (workspace_root / SECOND_ITEM_COMPONENT_PATHS["A"]).with_suffix(".md")
    markdown = markdown_path.read_text(encoding="utf-8")
    ruler_sections = markdown.split("\n### ")[1:]
    if len(ruler_sections) != len(records) or not all(
        "\n- 材料依据：\n  - 《" in section for section in ruler_sections
    ):
        raise ValueError("第二项A逐人材料依据未全部列出具体书名材料")
    material_lines = [line for line in markdown.splitlines() if line.startswith("  - ")]
    machine_tokens = ("material_id", "evidence_id", "source_url", "revision_ref", "sha256")
    if not material_lines or any(
        not line.startswith("  - 《") or any(token in line for token in machine_tokens)
        for line in material_lines
    ):
        raise ValueError("第二项A材料依据仍含无书名条目或机器审计字段")
    return {
        "status": "PASS",
        "record_count": len(records),
        "institution_node_count": len(nodes),
        "scoring_node_count": len(active_node_ids),
        "reference_node_count": len(nodes) - len(active_node_ids),
    }


def _verify_second_item_components(workspace_root: Path) -> dict[str, Any]:
    payloads = {
        key: json.loads((workspace_root / path).read_text(encoding="utf-8"))
        for key, path in SECOND_ITEM_COMPONENT_PATHS.items()
    }
    for key in ("C4", "result"):
        _verify_records_hash(payloads[key], f"第二项{key}")
    indexed = {key: _records_by_id(payload) for key, payload in payloads.items()}

    a_report = verify_second_item_a_snapshot(workspace_root)
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
        "A_institution_node_count": a_report["institution_node_count"],
        "A_scoring_node_count": a_report["scoring_node_count"],
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
        "third_item_components": {
            "D": verify_third_item_d_formal_settlement(workspace_root),
            "combined": verify_current_third_item_settlement(workspace_root),
        },
        "items": reports,
    }
