from __future__ import annotations

import hashlib
import json
import re
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
    if a_payload.get("A_position_formula_code") == "A_NET_DURABILITY_V2":
        if len(records) != 185 or a_payload.get("record_count") != 185:
            raise ValueError("第二项A V2正式记录数不是185")
        if len({row.get("ruler_id") for row in records}) != 185 or len(
            {row.get("ruler_name") for row in records}
        ) != 185:
            raise ValueError("第二项A V2人物ID或姓名不唯一")
        direction_factor = {
            "positive": 1.0,
            "mixed_positive": 0.5,
            "mixed": 0.0,
            "balanced": 0.0,
            "neutral": 0.0,
            "mixed_negative": -0.5,
            "negative": -1.0,
        }
        explicit_patch_count = 0
        reopen_count = 0
        for row in records:
            ruler_name = str(row.get("ruler_name"))
            if row.get("A_position_formula_code") != "A_NET_DURABILITY_V2":
                raise ValueError(f"第二项A人物记录未切换V2：{ruler_name}")
            if row.get("v2_explicit_patch") is True:
                explicit_patch_count += 1
                required = {
                    "A_net_units", "P_gross", "N_gross", "unfloored_grade",
                    "polarization_floor_triggered", "extreme_delta_reopen",
                }
                missing = sorted(required - set(row))
                if missing:
                    raise ValueError(f"第二项A显式patch缺少审计字段：{ruler_name}={missing}")
                if row.get("extreme_delta_reopen") is not False:
                    raise ValueError(f"第二项A已裁人物仍处重开状态：{ruler_name}")
                if float(row.get("P_gross") or 0) < 0 or float(row.get("N_gross") or 0) < 0:
                    raise ValueError(f"第二项A正负总量非法：{ruler_name}")
                if row.get("polarization_floor_triggered"):
                    p_gross = float(row.get("P_gross") or 0)
                    n_gross = float(row.get("N_gross") or 0)
                    ratio = n_gross / p_gross if p_gross else 0
                    if (
                        row.get("unfloored_grade") not in {"G0", "G1"}
                        or row.get("grade") not in {"G2", "G3"}
                        or p_gross < 4
                        or n_gross < 4
                        or not 0.75 <= ratio <= 1.25
                    ):
                        raise ValueError(f"第二项A极化托底字段非法：{ruler_name}")
            if row.get("extreme_delta_reopen") is True:
                reopen_count += 1
            referenced_ids = {
                str(item.get("institution_node_id"))
                for item in row.get("important_institutions") or []
                if item.get("institution_node_id")
            }
            missing_ids = sorted(referenced_ids - active_node_ids)
            if missing_ids:
                raise ValueError(f"第二项A引用未闭合：{ruler_name}={missing_ids}")
            seen_lifecycles: set[object] = set()
            for profile_key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
                for profile in row.get(profile_key) or []:
                    if profile.get("M") not in allowed_m:
                        raise ValueError(f"第二项A非法M档：{ruler_name}={profile.get('M')}")
                    direction = str(profile.get("direction"))
                    if direction in direction_factor and abs(
                        float(profile.get("direction_factor") or 0) - direction_factor[direction]
                    ) > 1e-9:
                        raise ValueError(f"第二项A方向与factor不一致：{ruler_name}={direction}")
                    if profile.get("mechanism") in generic_mechanisms:
                        raise ValueError(f"第二项A仍有泛化机制：{ruler_name}={profile.get('mechanism')}")
                    lifecycle_key: object = (
                        profile.get("institution_node_id")
                        or profile.get("lifecycle_id")
                        or (profile.get("mechanism"), profile.get("direction"))
                    )
                    if lifecycle_key in seen_lifecycles and not profile.get("absorbed_into_lifecycle_key"):
                        raise ValueError(f"第二项A生命周期重复消费：{ruler_name}={lifecycle_key}")
                    seen_lifecycles.add(lifecycle_key)
        if explicit_patch_count != a_payload.get("v2_explicit_patch_count"):
            raise ValueError("第二项A V2显式patch计数不一致")
        if reopen_count != a_payload.get("v2_extreme_delta_reopen_count"):
            raise ValueError("第二项A V2重开计数不一致")
        markdown_path = (workspace_root / SECOND_ITEM_COMPONENT_PATHS["A"]).with_suffix(".md")
        markdown = markdown_path.read_text(encoding="utf-8")
        material_lines = [line for line in markdown.splitlines() if line.startswith("  - ")]
        if not material_lines or any(not line.startswith("  - 《") for line in material_lines):
            raise ValueError("第二项A材料依据仍含无书名条目")
        for row in records:
            if row.get("v2_explicit_patch") is not True:
                continue
            ruler_name = str(row["ruler_name"])
            card_line = (
                f"- 方向卡：{row['grade']}，档内"
            )
            section_match = re.search(
                rf"^### {re.escape(ruler_name)}（.*?\n\n(.*?)(?=\n### |\Z)",
                markdown,
                flags=re.M | re.S,
            )
            if not section_match or card_line not in section_match.group(1):
                raise ValueError(f"第二项A V2阅读版未同步：{ruler_name}")
            table_pattern = (
                rf"^\| \d+ \| {re.escape(ruler_name)} \| .*? \| "
                rf"{row['grade']}（{row['position']}） \|"
            )
            if not re.search(table_pattern, markdown, flags=re.M):
                raise ValueError(f"第二项A V2排序表未同步：{ruler_name}")
        expected_markdown_order = [
            str(row["ruler_name"])
            for row in sorted(records, key=lambda item: int(item["rank"]))
        ]
        table_names = re.findall(r"^\| \d+ \| ([^|]+?) \|", markdown, flags=re.M)
        detail_names = re.findall(r"^### (.+?)（.*?分项第\d+名）$", markdown, flags=re.M)
        if table_names != expected_markdown_order:
            raise ValueError("第二项A阅读版排序表未按正式rank稳定排序")
        if detail_names != expected_markdown_order:
            raise ValueError("第二项A阅读版人物详卡未按正式rank稳定排序")
        return {
            "status": "PASS_WITH_REOPEN" if reopen_count else "PASS",
            "record_count": len(records),
            "institution_node_count": len(nodes),
            "scoring_node_count": len(active_node_ids),
            "reference_node_count": len(nodes) - len(active_node_ids),
            "explicit_patch_count": explicit_patch_count,
            "extreme_delta_reopen_count": reopen_count,
        }


def verify_second_item_b2_snapshot(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / SECOND_ITEM_COMPONENT_PATHS["B2"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    if len(records) != 185 or payload.get("record_count") != 185:
        raise ValueError("第二项B2正式记录数不是185")
    if payload.get("direction_card_ready_count") != 185:
        raise ValueError("第二项B2方向卡未全部就绪")
    if len({row.get("ruler_id") for row in records}) != 185 or len(
        {row.get("ruler_name") for row in records}
    ) != 185:
        raise ValueError("第二项B2人物ID或姓名不唯一")

    position_index = {
        "G0": {"lower": 1.6, "lower-middle": 4.8, "middle": 8.0, "middle-upper": 11.1, "upper": 14.3},
        "G1": {"lower": 17.6, "lower-middle": 20.8, "middle": 24.0, "middle-upper": 27.1, "upper": 30.3},
        "G2": {"lower": 33.2, "lower-middle": 35.6, "middle": 38.0, "middle-upper": 40.3, "upper": 42.7},
        "G3": {"lower": 45.2, "lower-middle": 47.6, "middle": 50.0, "middle-upper": 52.3, "upper": 54.7},
        "G4": {"lower": 57.2, "lower-middle": 59.6, "middle": 62.0, "middle-upper": 64.3, "upper": 66.7},
        "G5": {"lower": 69.2, "lower-middle": 71.6, "middle": 74.0, "middle-upper": 76.4, "upper": 78.8},
    }
    gate_codes = {
        "G0": "B2_G0_SYSTEM_CLOSURE",
        "G1": "B2_G1_FORMAL_OR_FAILURE_DOMINANT",
        "G2": "B2_G2_ONE_CLOSED_OR_MIXED",
        "G3": "B2_G3_MAIN_STAGE_FEEDBACK_SAFE",
        "G4": "B2_G4_MULTICHANNEL_CROSSLEVEL_SUPREME",
        "G5": "B2_G5_RARE_MULTICHANNEL_INSTITUTIONALIZED",
    }
    distribution = {grade: 0 for grade in gate_codes}
    for row in records:
        grade = str(row.get("grade"))
        position = str(row.get("position"))
        if grade not in position_index or position not in position_index[grade]:
            raise ValueError(f"第二项B2非法档位或position：{row.get('ruler_name')}")
        if float(row.get("direction_index")) != position_index[grade][position]:
            raise ValueError(f"第二项B2档位、position与index不一致：{row.get('ruler_name')}")
        if row.get("grade_gate_code") != gate_codes[grade]:
            raise ValueError(f"第二项B2仍有旧门禁代码：{row.get('ruler_name')}")
        if not row.get("material_basis") or not all(
            isinstance(item, str) and item.strip() for item in row.get("material_basis") or []
        ):
            raise ValueError(f"第二项B2缺少可直述的材料依据：{row.get('ruler_name')}")
        if not row.get("settlement_basis") or not all(
            isinstance(item, str) and item.strip() for item in row.get("settlement_basis") or []
        ):
            raise ValueError(f"第二项B2缺少冻结的逐条结算依据：{row.get('ruler_name')}")
        distribution[grade] += 1
        for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
            if any(item.get("M") not in {"M0", "M2", "M3"} for item in row.get(key) or []):
                raise ValueError(f"第二项B2仍有非法M档：{row.get('ruler_name')}")

    if payload.get("grade_distribution") != distribution:
        raise ValueError("第二项B2档位分布元数据不一致")
    sorted_scores = sorted((float(row["direction_index"]) for row in records), reverse=True)
    for row in records:
        if row.get("rank") != sorted_scores.index(float(row["direction_index"])) + 1:
            raise ValueError(f"第二项B2竞争排名不一致：{row.get('ruler_name')}")

    audit_path = path.with_name("05-B2审查整改复核.json")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_records = audit.get("records") or []
    indexed = {row["ruler_id"]: row for row in records}
    if audit.get("review_table_count") != 142 or len(audit_records) != 142:
        raise ValueError("第二项B2整改复核未覆盖142人最终裁决表")
    if len({row.get("ruler_id") for row in audit_records}) != 142:
        raise ValueError("第二项B2整改复核存在重复人物")
    for item in audit_records:
        current = indexed.get(item.get("ruler_id"))
        after = item.get("after") or {}
        if current is None or any(
            current.get(key) != after.get(key)
            for key in (
                "grade", "position", "direction_index", "grade_basis",
                "settlement_basis", "material_basis",
            )
        ):
            raise ValueError(f"第二项B2整改复核与正式记录不一致：{item.get('ruler_name')}")
        settlement_basis = current.get("settlement_basis") or []
        if not settlement_basis or not all(
            isinstance(line, str) and line.strip() for line in settlement_basis
        ):
            raise ValueError(f"第二项B2审查人物缺少冻结的逐条结算依据：{item.get('ruler_name')}")
        active_mechanisms = [
            profile.get("mechanism")
            for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
            for profile in current.get(key) or []
            if profile.get("signed_weight") != 0
        ]
        if len(active_mechanisms) != len(set(active_mechanisms)):
            raise ValueError(f"第二项B2审查人物仍有重复计权机制：{item.get('ruler_name')}")

    markdown = path.with_suffix(".md").read_text(encoding="utf-8")
    sections = markdown.split("\n### ")[1:]
    section_names = [section.split("（", 1)[0] for section in sections]
    if len(section_names) != 185 or len(set(section_names)) != 185:
        raise ValueError("第二项B2 Markdown仍有重复或缺失人物裁决块")
    if any("【裁决说明】" in section or "\n- 结算依据：\n" not in section for section in sections):
        raise ValueError("第二项B2 Markdown仍有旧式或缺失的逐人结算依据")
    untranslated_terms = (
        "cross_level_ingress", "external_constraint", "information_ingress",
        "sovereign_self_correction", "external_advice", "mixed_positive",
        "mixed_negative", "event_scale", "sanction_intensity", "irreversibility",
        "highest_power_directness",
    )
    if any(term in markdown for term in untranslated_terms) or re.search(
        r"(?<![A-Za-z0-9])[A-Za-z]+(?:_[A-Za-z0-9]+)+", markdown
    ):
        raise ValueError("第二项B2 Markdown仍含未翻译机器审计词")
    sections_by_name = {section.split("（", 1)[0]: section for section in sections}
    for item in audit_records:
        current = indexed[item["ruler_id"]]
        section = sections_by_name[item["ruler_name"]]
        if "\n- 结算依据：\n" not in section or "【裁决说明】" in section:
            raise ValueError(f"第二项B2审查人物仍沿用旧裁决说明：{item['ruler_name']}")
        if any(f"  - {line.rstrip('。')}。" not in section for line in current["settlement_basis"]):
            raise ValueError(f"第二项B2 Markdown结算依据未逐条同步：{item['ruler_name']}")
        if any(f"  - {line.rstrip('。')}。" not in section for line in current["material_basis"]):
            raise ValueError(f"第二项B2 Markdown材料依据未逐条同步：{item['ruler_name']}")
    material_blocks = re.findall(
        r"^- 材料依据：\n(?P<lines>(?:  - .*\n?)+)", markdown, flags=re.MULTILINE
    )
    if len(material_blocks) != 185 or any(
        re.search(r"https?://|\]\(|\b(?:material_id|source_url|revision_ref|sha256)\b", block)
        for block in material_blocks
    ):
        raise ValueError("第二项B2材料依据仍含引用或机器审计字段")
    return {
        "status": "PASS",
        "record_count": len(records),
        "review_adjudication_count": len(audit_records),
        "person_patch_count": len(audit_records),
        "settlement_basis_count": len(records),
        "grade_distribution": distribution,
        "invalid_M1_count": 0,
        "duplicate_markdown_ruler_count": 0,
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
    b2_report = verify_second_item_b2_snapshot(workspace_root)
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
        "B2_review_adjudication_count": b2_report["review_adjudication_count"],
        "B2_duplicate_markdown_ruler_count": b2_report["duplicate_markdown_ruler_count"],
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
