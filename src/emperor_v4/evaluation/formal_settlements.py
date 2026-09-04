from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.canonical_ruler_pool import verify_canonical_ruler_pool
from emperor_v4.evaluation.composite_ranking import verify_composite_ranking
from emperor_v4.evaluation.first_item_markdown_settlement import (
    verify_first_item_markdown_settlement,
)
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_b1_settlement import (
    _structured_basis,
    active_groups,
    index_from_grade_position,
    position_from_residual,
    position_residual,
    validate_gate_references,
)
from emperor_v4.evaluation.third_item_current_settlement import (
    verify_current_third_item_settlement,
)
from emperor_v4.evaluation.third_item_d_settlement import (
    verify_third_item_d_formal_settlement,
)


SETTLEMENT_SPECS = {
    "second_item": {
        "path": "docs/评分结算/第二项治国净收益/01-第二项治国净收益正式结算.json",
        "schema": "i2_total_387_signed_formal_v5_da6",
        "score": "second_item_score",
        "rank": "rank",
        "range": (-27.5, 387),
    },
    "third_item": {
        "path": "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json",
        "schema": "emperor-v4-third-item-formal-settlement-v7-fixed-cost-debit",
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
    "result": "docs/评分结算/第二项治国净收益/财政民生/05-治理结果正式结算.json",
    "D1": "docs/评分结算/第二项治国净收益/政权交接稳定/01-D1继任行政连续性方向卡.json",
    "D3": "docs/评分结算/第二项治国净收益/政权交接稳定/02-D3政权交接稳定方向卡.json",
    "handoff": "docs/评分结算/第二项治国净收益/政权交接稳定/03-交接质量20分正式结算.json",
}
SECOND_ITEM_RESULT_CONTRACT = (
    "docs/分项规则/第二项治国净收益/财政民生/00-规则与结算合同.md"
)
REQUIRED_C4_DA_CONTRACT_CLAUSES = (
    "C1/C2/C3绝对状态与C4可归责恶化可以共同使用同一事实",
    "只有C1—C3主态、K折损和C4可归责恶化均未消费的主动成本才可计DA",
    "纯军队伤亡不得直接转入第二项",
    "一次行为只要残余成本量级足够高，也可直接进入DA2或DA3",
    "一次超大型动员、战争或工程即可成立",
    "一次灾难性选择即可成立",
    "DA5",
    "DA6",
    "NEW_BUILD",
    "仁寿宫",
    "DA只结算尚未被这些项目吸收的剩余主动成本",
)

IMPORTANT_INSTITUTION_REGISTRY = (
    "docs/公共成果/制度行政/03-重要制度发展节点链.json"
)


def _competition_rank(sorted_scores: list[float], index: int) -> int:
    return sorted_scores.index(sorted_scores[index]) + 1


def _records_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = payload.get("records") or payload.get("scores") or []
    return {str(row["ruler_id"]): row for row in records}


def verify_second_item_a_snapshot(workspace_root: Path) -> dict[str, Any]:
    a_payload = load_json(workspace_root / SECOND_ITEM_COMPONENT_PATHS["A"])
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


def verify_second_item_b1_snapshot(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / SECOND_ITEM_COMPONENT_PATHS["B1"]
    payload = load_json(path)
    records = payload.get("records") or []
    if len(records) != 185 or payload.get("record_count") != 185:
        raise ValueError("第二项B1正式记录数不是185")
    if payload.get("direction_card_ready_count") != 185:
        raise ValueError("第二项B1方向卡未全部就绪")
    if len({row.get("ruler_id") for row in records}) != 185 or len(
        {row.get("ruler_name") for row in records}
    ) != 185:
        raise ValueError("第二项B1人物ID或姓名不唯一")

    position_q = {"lower": 0.1, "lower-middle": 0.3, "middle": 0.5, "middle-upper": 0.7, "upper": 0.9}
    intervals = {
        "G0": (0.0, 19.9), "G1": (20.0, 39.9), "G2": (40.0, 54.9),
        "G3": (55.0, 69.9), "G4": (70.0, 84.9), "G5": (85.0, 100.0),
    }
    gate_codes = {
        "G0": "B1_G0_SYSTEMIC_ADMIN_BREAKDOWN",
        "G1": "B1_G1_DYSFUNCTION_DOMINANT",
        "G2": "B1_G2_LIMITED_OR_MIXED",
        "G3": "B1_G3_MAIN_STAGE_USABLE",
        "G4": "B1_G4_BROAD_STABLE_DELIVERY",
        "G5": "B1_G5_RARE_RELIABILITY",
    }
    direct_roles = {
        "B1_NEGATIVE_DIRECT", "B1_POSITIVE_DIRECT", "B1_MIXED_DIRECT",
        "DIRECT_SCORE", "B1_DIRECT_SCORE", "B1_DIRECT_POSITIVE",
        "B1_DIRECT_NEGATIVE", "B1_DIRECT",
    }
    registry_roles: dict[str, list[tuple[str, str]]] = {}
    material_ids: set[str] = set()
    registry_root = workspace_root / "docs/公共成果/制度行政/01-制度行政计分材料登记"
    for registry_path in sorted(registry_root.glob("*.json")):
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        for material in registry.get("records") or []:
            material_id = str(material.get("material_id") or "")
            if not material_id or material_id in material_ids:
                raise ValueError(f"第二项B1公共登记材料ID缺失或重复：{material_id}")
            material_ids.add(material_id)
            for target, role in (material.get("usage_roles") or {}).items():
                if target.endswith(":B1"):
                    registry_roles.setdefault(target.split(":", 1)[0], []).append((material_id, str(role)))

    distribution = {grade: 0 for grade in intervals}
    reviewed_count = direct_count = verification_count = 0
    for row in records:
        name = str(row.get("ruler_name"))
        grade, position = str(row.get("grade")), str(row.get("position"))
        if grade not in intervals or position not in position_q:
            raise ValueError(f"第二项B1非法档位或position：{name}")
        if float(row.get("direction_index")) != index_from_grade_position(grade, position):
            raise ValueError(f"第二项B1档位、position与index不一致：{name}")
        if row.get("grade_gate_code") != gate_codes[grade]:
            raise ValueError(f"第二项B1仍有旧门禁代码：{name}")
        if not isinstance(row.get("grade_basis"), str) or not row["grade_basis"].strip():
            raise ValueError(f"第二项B1缺少逐人结算依据：{name}")
        distribution[grade] += 1

        role_rows = registry_roles.get(name, [])
        expected_direct = {material_id for material_id, role in role_rows if role in direct_roles}
        expected_verification = {material_id for material_id, role in role_rows if role not in direct_roles}
        direct = set(row.get("direct_material_ids") or [])
        verification = set(row.get("verification_material_ids") or [])
        if direct != expected_direct or verification != expected_verification:
            raise ValueError(f"第二项B1材料角色与公共登记不一致：{name}")
        if direct & verification:
            raise ValueError(f"第二项B1 direct与verification重叠：{name}")
        profile_ids: set[str] = set()
        profile_refs: set[tuple[str, str]] = set()
        profiles: list[dict[str, Any]] = []
        for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
            for profile in row.get(key) or []:
                if profile.get("M") not in {"M0", "M2", "M3"}:
                    raise ValueError(f"第二项B1仍有非法M档：{name}")
                material_id = str(profile.get("material_id") or "")
                if not material_id:
                    raise ValueError(f"第二项B1 M-profile材料缺失：{name}")
                evidence_slice = str(profile.get("evidence_slice") or "PRIMARY")
                profile_ref = (material_id, evidence_slice)
                if profile_ref in profile_refs:
                    raise ValueError(f"第二项B1 M-profile材料切片重复：{name}")
                profile_refs.add(profile_ref)
                profile_ids.add(material_id)
                profiles.append(profile)
        if profile_ids != direct:
            raise ValueError(f"第二项B1 direct材料与M-profile不一致：{name}")

        expected_residual = position_residual(row)
        expected_position = "middle" if grade == "G0" and not active_groups(row) else position_from_residual(expected_residual)
        if (
            float(row.get("position_residual")) != expected_residual
            or position != expected_position
            or "同档横向比较" in str(row.get("position_basis") or "")
            or "position_depth_bonus" in json.dumps(row, ensure_ascii=False)
        ):
            raise ValueError(f"第二项B1净余量、position或旧手工逻辑不一致：{name}")
        semantic_status = row.get("profile_semantic_review_status")
        if semantic_status != "B1_CONTRACT_V54_LOW_GATE_NEGATIVE_PURITY_REVIEWED":
            raise ValueError(f"第二项B1缺少M-profile逐人语义复核状态：{name}")
        review_material_basis = row.get("review_material_basis")
        if not isinstance(review_material_basis, list) or any(
            item.get("version") not in {"v20", "v50"}
            or not isinstance(item.get("line"), int)
            or not str(item.get("basis") or "").strip()
            or item.get("status") not in {
                "ABSORBED_INPUT_V50_PRECEDENCE", "ABSORBED_ACTIVE", "ABSORBED_ACTIVE_PRECEDENCE",
            }
            for item in review_material_basis
        ):
            raise ValueError(f"第二项B1 v20/v50材料吸收留痕不完整：{name}")
        structured_basis = row.get("structured_grade_basis")
        if not isinstance(structured_basis, list) or not structured_basis or any(
            not isinstance(point, dict)
            or not str(point.get("role") or "").strip()
            or not str(point.get("text") or "").strip()
            for point in structured_basis
        ):
            raise ValueError(f"第二项B1缺少逐人结构化结算依据：{name}")
        if structured_basis != _structured_basis(row):
            raise ValueError(f"第二项B1统一裁决说明与正式值不一致：{name}")
        evidence_roles = [str(point["role"]) for point in structured_basis[2:]]
        if not evidence_roles or any(
            not re.fullmatch(r"(?:正向|负向)依据（(?:M[023](?:，(?:cross|terminal))?|无可计M档)）", role)
            for role in evidence_roles
        ):
            raise ValueError(f"第二项B1结算依据未统一为正向与负向M档罗列：{name}")
        if not any(role.startswith("正向依据") for role in evidence_roles) or not any(
            role.startswith("负向依据") for role in evidence_roles
        ):
            raise ValueError(f"第二项B1结算依据缺少正向或负向栏目：{name}")
        expected_basis_levels: dict[str, set[str]] = {"正向": set(), "负向": set()}
        for profile in active_groups(row):
            direction_label = "正向" if float(profile.get("signed_weight") or 0.0) > 0 else "负向"
            expected_basis_levels[direction_label].add(str(profile["M"]))
        actual_basis_levels: dict[str, set[str]] = {"正向": set(), "负向": set()}
        no_count_directions: set[str] = set()
        for evidence_role in evidence_roles:
            direction_label = evidence_role[:2]
            level_match = re.search(r"（(M[023])", evidence_role)
            if level_match:
                actual_basis_levels[direction_label].add(level_match.group(1))
            elif "无可计M档" in evidence_role:
                no_count_directions.add(direction_label)
        if actual_basis_levels != expected_basis_levels or any(
            bool(expected_basis_levels[direction]) == (direction in no_count_directions)
            for direction in ("正向", "负向")
        ):
            raise ValueError(f"第二项B1结算依据方向或M档与正式profile不一致：{name}")
        expected_subtypes: set[str] = set()
        for profile in row.get("M_negative_profile") or []:
            if profile.get("position_weight_override") == 0 or profile.get("position_count_mode") == "absorbed_same_lifecycle":
                continue
            raw_severity = str(profile.get("severity") or "") + " " + str(profile.get("mechanism") or "")
            for subtype in ("cross", "terminal"):
                if subtype in raw_severity:
                    expected_subtypes.add(subtype)
                    if profile.get("M") != "M3" or not str(profile.get("severity_basis") or "").strip():
                        raise ValueError(f"第二项B1负向M3缺少{subtype}严重度数据：{name}")
                    if f"负向依据（M3，{subtype}）" not in evidence_roles:
                        raise ValueError(f"第二项B1负向M3未注明{subtype}：{name}")
        role_subtypes = {
            subtype
            for subtype in ("cross", "terminal")
            if any(subtype in role for role in evidence_roles)
        }
        if role_subtypes != expected_subtypes:
            raise ValueError(f"第二项B1负向M3严重度标签与profile不一致：{name}")
        reader_basis_text = " ".join(str(point["text"]) for point in structured_basis[1:])
        if re.search(
            r"(?<![A-Za-z])(?:distributed|central|support|core|personnel|externalized_power|position|N3-)",
            reader_basis_text,
        ):
            raise ValueError(f"第二项B1阅读版结算依据仍含机器裁决术语：{name}")
        direct_count += len(direct)
        verification_count += len(verification)

        reviewed_count += 1

    if payload.get("grade_distribution") != distribution:
        raise ValueError("第二项B1档位分布元数据不一致")
    if payload.get("profile_semantic_review_count") != reviewed_count:
        raise ValueError("第二项B1 M-profile语义复核计数不一致")
    if payload.get("structured_basis_count") != len(records):
        raise ValueError("第二项B1结构化结算依据计数不一致")
    if (
        payload.get("contract_recalculation_status") != "FORMAL_COMPLETE"
        or payload.get("contract_recalculation_count") != 185
        or reviewed_count != 185
    ):
        raise ValueError("第二项B1 V5.3两清单材料并集重裁元数据不一致")
    absorption = payload.get("review_material_absorption") or {}
    if (
        absorption.get("policy") != "v20_v50_union_with_v50_precedence_then_current_contract_adjudication"
        or absorption.get("v20_reviewed_count") != 174
        or absorption.get("v50_reviewed_count") != 164
        or absorption.get("overlap_count") != 164
        or absorption.get("v20_only_count") != 10
        or absorption.get("v50_only_count") != 0
        or absorption.get("not_listed_count") != 11
        or not re.fullmatch(r"[0-9a-f]{64}", str(absorption.get("v20_sha256") or ""))
        or not re.fullmatch(r"[0-9a-f]{64}", str(absorption.get("v50_sha256") or ""))
    ):
        raise ValueError("第二项B1 v20/v50材料并集与优先级元数据不一致")
    validate_gate_references(payload)
    sorted_scores = sorted((float(row["direction_index"]) for row in records), reverse=True)
    for row in records:
        if row.get("rank") != sorted_scores.index(float(row["direction_index"])) + 1:
            raise ValueError(f"第二项B1竞争排名不一致：{row.get('ruler_name')}")

    markdown = path.with_suffix(".md").read_text(encoding="utf-8")
    expected_order = [
        str(row["ruler_name"])
        for row in sorted(records, key=lambda item: (int(item["rank"]), str(item["ruler_id"])))
    ]
    table_names = re.findall(r"^\| \d+ \| ([^|]+?) \|", markdown, flags=re.M)
    detail_names = re.findall(r"^### (.+?)（.*?分项第\d+名）$", markdown, flags=re.M)
    if table_names != expected_order or detail_names != expected_order:
        raise ValueError("第二项B1阅读版未按正式rank稳定排序或人物覆盖不全")
    if re.search(
        r"(?<![A-Za-z])(?:distributed|central|support|core|personnel|capture|major-stage|mixed|N3-)",
        markdown,
    ):
        raise ValueError("第二项B1阅读版仍含机器裁决术语")
    position_cn = {
        "lower": "下位",
        "lower-middle": "中下位",
        "middle": "中位",
        "middle-upper": "中上位",
        "upper": "上位",
    }
    for row in records:
        expected_table_prefix = (
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | "
            f"{row['grade']}（{position_cn[row['position']]}） | "
        )
        expected_table_suffix = f" | **{float(row['direction_index']):.1f}** |"
        table_synced = any(
            line.startswith(expected_table_prefix) and line.endswith(expected_table_suffix)
            for line in markdown.splitlines()
        )
        structured_basis = "\n".join(
            f"  - **{point['role']}**：{str(point['text']).rstrip('。')}。"
            for point in row["structured_grade_basis"]
        )
        expected_detail = (
            f"### {row['ruler_name']}（{row['polity']}，分项第{row['rank']}名）\n\n"
            f"- 档位：{row['grade']}（{position_cn[row['position']]}）\n"
            f"- 内部指数：{float(row['direction_index']):.1f}/100\n"
            "- 结算依据：\n"
            f"{structured_basis}"
        )
        if not table_synced or expected_detail not in markdown:
            raise ValueError(f"第二项B1 JSON与Markdown逐人展示不同步：{row['ruler_name']}")
    material_blocks = re.findall(
        r"^- 材料依据：\n(?P<lines>(?:  - .*\n?)+)", markdown, flags=re.MULTILINE
    )
    if len(material_blocks) != 185 or any(
        re.search(r"https?://|\b(?:material_id|source_url|revision_ref|sha256)\b", block)
        or "  - 《" not in block or "》：" not in block
        for block in material_blocks
    ):
        raise ValueError("第二项B1材料依据未统一为书名接direct原文")
    return {
        "status": "PASS_V54_LOW_GATE_NEGATIVE_PURITY_CONTRACT_READJUDICATED",
        "record_count": len(records),
        "reviewed_count": reviewed_count,
        "direct_material_count": direct_count,
        "verification_material_count": verification_count,
        "invalid_M1_count": 0,
        "duplicate_markdown_ruler_count": 0,
        "profile_semantic_review_count": reviewed_count,
        "grade_distribution": distribution,
        "contract_recalculation_count": int(payload.get("contract_recalculation_count") or 0),
        "position_basis_refresh_count": int(payload.get("position_basis_refresh_count") or 0),
        "structured_basis_count": int(payload.get("structured_basis_count") or 0),
    }


def verify_second_item_b2_snapshot(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / SECOND_ITEM_COMPONENT_PATHS["B2"]
    payload = load_json(path)
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
    result_contract = (workspace_root / SECOND_ITEM_RESULT_CONTRACT).read_text(encoding="utf-8")
    if any(clause not in result_contract for clause in REQUIRED_C4_DA_CONTRACT_CLAUSES):
        raise ValueError("第二项C4 DA成本量级合同缺失")
    payloads = {
        key: load_json(workspace_root / path)
        for key, path in SECOND_ITEM_COMPONENT_PATHS.items()
    }
    indexed = {key: _records_by_id(payload) for key, payload in payloads.items()}

    d3_payload = payloads["D3"]
    d3_records = list(d3_payload.get("records") or [])
    d3_markdown = (workspace_root / SECOND_ITEM_COMPONENT_PATHS["D3"]).with_suffix(".md").read_text(encoding="utf-8")
    d3_intervals = {
        "D3-0": (0.0, 2.85), "D3-1": (3.0, 5.85), "D3-2": (6.0, 8.85),
        "D3-3": (9.0, 11.85), "D3-4": (12.0, 14.10), "D3-5": (14.25, 15.0),
    }
    if (
        d3_payload.get("record_count") != len(d3_records)
        or d3_payload.get("direction_card_ready_count") != len(d3_records)
        or len({str(row.get("ruler_id")) for row in d3_records}) != len(d3_records)
        or len({str(row.get("ruler_name")) for row in d3_records}) != len(d3_records)
    ):
        raise ValueError("第二项D3正式名单或动态覆盖计数不一致")
    d3_scores = sorted((float(row["direction_index"]) for row in d3_records), reverse=True)
    for row in d3_records:
        grade = str(row.get("D3_grade"))
        index = float(row.get("direction_index"))
        if grade not in d3_intervals or not d3_intervals[grade][0] <= index <= d3_intervals[grade][1]:
            raise ValueError(f"第二项D3档位与内部指数不一致：{row.get('ruler_name')}")
        if int(row.get("rank")) != d3_scores.index(index) + 1:
            raise ValueError(f"第二项D3竞争排名不一致：{row.get('ruler_name')}")
        expected_table = (
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {grade}（"
        )
        expected_detail = f"### {row['ruler_name']}（{row['polity']}，分项第{row['rank']}名）"
        if expected_table not in d3_markdown or expected_detail not in d3_markdown:
            raise ValueError(f"第二项D3 Markdown未同步：{row.get('ruler_name')}")

    handoff_records = list(payloads["handoff"].get("records") or [])
    handoff_scores = sorted((float(row["score"]) for row in handoff_records), reverse=True)
    caps = {0: 4.0, 1: 8.0, 2: 12.0, 3: 16.0, 4: 20.0, 5: 20.0}
    for row in handoff_records:
        ruler_id = str(row["ruler_id"])
        d1_level = int(str(indexed["D1"][ruler_id]["grade"])[-1])
        d3_level = int(str(indexed["D3"][ruler_id]["D3_grade"])[-1])
        expected_cap = caps[min(d1_level, d3_level)]
        expected_score = min(2.0 * (d1_level + d3_level), expected_cap)
        if (
            int(row.get("D1_level")) != d1_level
            or int(row.get("D3_level")) != d3_level
            or float(row.get("low_side_cap")) != expected_cap
            or float(row.get("score")) != expected_score
            or int(row.get("rank")) != handoff_scores.index(float(row["score"])) + 1
        ):
            raise ValueError(f"第二项20分交接结算与D1/D3公式不一致：{row.get('ruler_name')}")

    a_report = verify_second_item_a_snapshot(workspace_root)
    verify_second_item_b1_snapshot(workspace_root)
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
        load_json(workspace_root / str(SETTLEMENT_SPECS["second_item"]["path"]))
    )
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
        "D3_formal_record_count": len(d3_records),
        "handoff_formula_record_count": len(handoff_records),
    }


def verify_formal_settlements(workspace_root: Path) -> dict[str, Any]:
    reports: dict[str, Any] = {
        "first_item": verify_first_item_markdown_settlement(workspace_root)
    }
    for item, spec in SETTLEMENT_SPECS.items():
        path = workspace_root / str(spec["path"])
        payload = load_json(path)
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
