"""Read-only component details for the composite ranking."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.first_item_cost import COST_PATH
from emperor_v4.evaluation.first_item_markdown_settlement import (
    COMPONENT_SETTLEMENTS, TOTAL_SETTLEMENT, load_first_item_markdown_settlement,
)

SECOND = "docs/评分结算/第二项治国净收益/"
THIRD = "docs/评分结算/第三项军事与边疆净收益/"
FOURTH = "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json"
SOURCES = {
    "method": SECOND + "制度行政/04-治理手段165分正式结算.json",
    "A": SECOND + "制度行政/01-A制度建设与实际运行方向卡.json",
    "B1": SECOND + "制度行政/02-B1官僚治理与行政执行方向卡.json",
    "B2": SECOND + "制度行政/03-B2反馈纠错与权力约束方向卡.json",
    **{f"C{i}": SECOND + f"财政民生/0{i}-C{i}正式结算.json" for i in range(1, 5)},
    "handoff": SECOND + "政权交接稳定/03-交接质量20分正式结算.json",
    "second": SECOND + "01-第二项治国净收益正式结算.json",
    "AB": THIRD + "国防安全/01-皇帝AB项正式结算.json",
    "credit": "config/third-item/third-item-result-credit-adjudications.json",
    "C": THIRD + "军事体系有效性/01-皇帝C项正式结算.json",
    "third": THIRD + "02-第三项正式结算.json",
    "fourth": FOURTH,
}

SECTIONS = (
    ("first", "第一项：政权奠基与统一贡献及能力", "五轴合计减去军事成本扣分得到第一项净分，最低为0，再按总榜公式折算F。成本栏列正式成本档、档内位置和扣分；不适用保留为不适用。B1、B2在单元格中继续拆出内部等级及分数。"),
    ("method", "第二项：制度行政", "A、B1、B2列方向指数及正式档位、档内位置。A与B1不能直接相加：AB=round1(0.8×[max(A,B1)+0.5×min(A,B1)])；B2折算=round1(45/80×B2指数)。治理手段=AB+B2折算。"),
    ("finance", "第二项：财政民生", "C1—C3列主档、K诊断标签和最终分；K标签不是额外扣分。C4列正式档、DA档及正向保留−恶化−DA扣分。治理结果为C1至C4之和。"),
    ("handoff", "第二项：交接质量与合计", "D1、D3为0—5级输入，没有独立可加分；交接得分=min[2×(D1+D3),低侧封顶]。第二项=治理手段+治理结果+交接得分。"),
    ("strategic", "第三项：战略安全与边疆控制", "A1、A2列起点→终点档及现行归责后的分数，各上限60。B1、B2、B4列原档位、原得分率及边界裁决后的合成采用率，二者不一致时不反推新档位。B80=80×(0.55×B1率+0.45×B2率)×(0.70+0.30×B4率)，采用率换为0—1后参与计算。"),
    ("military", "第三项：军事体系、成本与合计", "C1、C2、C3是C50的能力档与上限，不分别加分。成本列全局成本档、档内位置和普通扣分；ML列净毁损档及扣分。实际扣分取两者较大值，第三项=A120+B80+C50−实际扣分。"),
    ("civilization", "第四项：文明与国家整合", "各轴列方向、幅度档、档内位置及有符号调整，三轴相加为第四项。空集零调整保留正式处置状态，不虚构档位。第五项与独立人物画像不参与本榜合成。"),
)


def _table(path: Path) -> dict[str, list[str]]:
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0].isdigit():
            if cells[1] in result:
                raise ValueError(f"第一项明细人物重复：{path} {cells[1]}")
            result[cells[1]] = cells
    return result


def load_detail_sources(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, path in SOURCES.items():
        payload = load_json(root / path)
        rows = payload["scores"] if "scores" in payload else payload["records"]
        indexed = {r["ruler_id"]: r for r in rows}
        if len(indexed) != len(rows):
            raise ValueError(f"子项明细人物ID重复：{path}")
        result[key] = indexed
    result["first"] = {r["name"]: r for r in load_first_item_markdown_settlement(root)}
    result["first_cost"] = {r["ruler_name"]: r for r in load_json(root / COST_PATH)["records"]}
    result["first_tables"] = [_table(root / p) for p in COMPONENT_SETTLEMENTS]
    return result


def component_details(sources: dict[str, Any], pool: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    ids = pool["source_item_ids"]
    name = row["ruler_name"]
    sid, tid, fid = (ids[k] for k in ("second_item", "third_item", "fourth_item"))

    def cell(label: str, value: float | None, grade: str, source: str, unit: str = "分", note: str = "") -> dict[str, Any]:
        return dict(label=label, value=value, grade=grade, unit=unit, note=note, source=source)

    def equal(a: float, b: float, label: str) -> None:
        if abs(a - b) > 0.011:
            raise ValueError(f"{name}子项明细与合成结果不一致：{label} {a} != {b}")

    details: dict[str, Any] = {}
    first = sources["first"].get(name)
    first_cells = []
    labels = ("A统一贡献", "B1创业难度与效率", "B2组织与整合", "C1军事统帅", "C2前线指挥")
    for i, (key, label) in enumerate(zip(("a", "b1", "b2", "c1", "c2"), labels)):
        if first is None:
            first_cells.append(cell(label, None, "不适用", COMPONENT_SETTLEMENTS[i]))
            continue
        values = sources["first_tables"][i][name]
        equal(float(values[-1]), first[key], label)
        grade, note = "按公式计分", ""
        if key == "a":
            note = f"成果信用U={values[4]}"
        elif key == "b1":
            grade = f"起点{values[2]}；对手{values[4]}/{values[5]}"
            note = f"起点{values[3]}＋对手{values[6]}＋效率{values[7]}"
            equal(sum(float(values[j]) for j in (3, 6, 7)), first[key], "B1内部合计")
        elif key == "b2":
            grade = f"并行{values[2]}；覆盖{values[4]}；整合{values[6]}"
            note = f"并行{values[3]}＋覆盖{values[5]}＋整合{values[7]}"
            equal(sum(float(values[j]) for j in (3, 5, 7)), first[key], "B2内部合计")
        elif key == "c1":
            grade = values[2]
        else:
            grade = values[5]
            note = f"P={values[2]}；R={values[3]}；N={values[4]}"
            equal(max(0, min(20, sum(float(values[j]) for j in (2, 3, 4)))), first[key], "C2内部合计")
            note += "；合计限0—20"
        first_cells.append(cell(label, first[key], grade, COMPONENT_SETTLEMENTS[i], note=note))
    cost_grade = "不适用"
    if first is not None:
        cost = sources["first_cost"][name]
        cost_grade = f"{cost['cost_band']} / {cost['cost_position']}"
        equal(max(0, first["gross"] - first["cost_debit"]), row["first_item_raw_score"], "第一项净分")
    first_cells += [
        cell("五轴合计", first["gross"] if first else None, "合计" if first else "不适用", TOTAL_SETTLEMENT),
        cell("军事成本扣分", first["cost_debit"] if first else None, cost_grade, COST_PATH),
        cell("第一项净分", row["first_item_raw_score"], "扣后净分" if first else "不适用", TOTAL_SETTLEMENT),
        cell("附加F", row["first_item_add_on"], "折算", TOTAL_SETTLEMENT),
    ]
    details["first"] = first_cells

    method = sources["method"][sid]
    method_cells = []
    for key, label in (("A", "A制度建设"), ("B1", "B1官僚治理"), ("B2", "B2反馈与约束")):
        r = sources[key][sid]
        equal(r["direction_index"], method[f"{key}_direction_index"], key)
        method_cells.append(cell(label, r["direction_index"], f"{r['grade']} / {r['position']}", SOURCES[key], "指数"))
    method_cells += [cell("AB计分块", method["AB_block_120"], "合成", SOURCES["method"]), cell("B2折算", method["B2_45"], "折算", SOURCES["method"]), cell("治理手段", method["score"], "小计", SOURCES["method"])]
    equal(method["AB_block_120"] + method["B2_45"], method["score"], "治理手段")
    details["method"] = method_cells
    second = sources["second"][sid]
    finance = []
    for key, label in (("C1", "C1民生"), ("C2", "C2经济财政"), ("C3", "C3社会安全"), ("C4", "C4恢复与成本")):
        r = sources[key][sid]
        equal(r["score"], second[f"{key}_score"], key)
        if r["main_band"] != second[f"{key}_band"]:
            raise ValueError(f"{name} {key}档位与第二项不一致")
        grade = r["main_band"]
        note = ""
        if key == "C4":
            grade += f" / {r['destructive_amplification_grade']}"
            note = f"{r['positive_score_retained']:g}−{r['deterioration_penalty']:g}−{r['destructive_amplification_penalty']:g}"
            equal(r['positive_score_retained']-r['deterioration_penalty']-r['destructive_amplification_penalty'], r['score'], "C4拆分")
        else:
            grade += f" / {r['stability_class_diagnostic_only']}"
        finance.append(cell(label, r["score"], grade, SOURCES[key], note=note))
    equal(sum(c["value"] for c in finance), second["governance_result_score"], "治理结果")
    finance.append(cell("治理结果", second["governance_result_score"], "小计", SOURCES["second"]))
    details["finance"] = finance
    handoff = sources["handoff"][sid]
    details["handoff"] = [cell(label, handoff[f"{k}_level"], "等级输入", SOURCES["handoff"], "级") for k, label in (("D1", "D1继任行政连续性"), ("D3", "D3政权交接稳定"))]
    details["handoff"] += [cell("低侧封顶", handoff["low_side_cap"], "上限", SOURCES["handoff"]), cell("交接得分", handoff["score"], "合成", SOURCES["handoff"]), cell("第二项合计", second["second_item_score"], "合计", SOURCES["second"])]
    equal(method["score"], second["governance_method_score"], "治理手段入口")
    equal(handoff["score"], second["handoff_score"], "交接入口")
    equal(method["score"]+second["governance_result_score"]+handoff["score"], row["second_item_score"], "第二项")

    ab, credit, c, third = (sources[k][tid] for k in ("AB", "credit", "C", "third"))
    strategic = []
    for key in ("A1", "A2"):
        axis = credit["axes"][key]
        strategic.append(cell(key, axis["axis_points"], f"{axis['start_grade']}→{axis['end_grade']}档", SOURCES["credit"]))
    equal(sum(x['value'] for x in strategic), third["A120_score_points"], "A120")
    strategic.append(cell("A120", third["A120_score_points"], "小计", SOURCES["third"]))
    for key in ("B1", "B2", "B4"):
        axis = ab["axes"][key]
        rate = credit["B80_adjudication"][f"adjudicated_{key}_rate"]
        entry = cell(key, axis["score_rate"], f"{axis['grade']} / {axis['band_position']}", SOURCES["AB"], "%", note=f"合成采用{rate:g}%")
        entry["applied_value"] = rate
        entry["applied_source"] = SOURCES["credit"]
        strategic.append(entry)
    equal(credit["B80_adjudication"]["B80_points"], third["B80_score_points"], "B80")
    strategic.append(cell("B80", third["B80_score_points"], "合成", SOURCES["third"]))
    details["strategic"] = strategic
    military = [cell(label, None, c[key], SOURCES["C"], "不单独计分") for label, key in (
        ("C1实战交付", "combat_delivery_grade"), ("C2持续作战", "operational_sustainability_cap"), ("C3体系可靠性", "system_reliability_cap"))]
    equal(c["C_score_points"], third["C50_score_points"], "C50")
    cost = third["global_cost_credit_profile"]
    military += [cell("C50", third["C50_score_points"], c["C_overall_grade"], SOURCES["C"]), cell("普通成本扣分", third["cost_debit_points"], f"{cost['cost_band']} / {cost['position']}", SOURCES["third"]), cell("ML扣分", abs(third["military_net_loss_penalty"]), third["military_net_loss_grade"], SOURCES["third"]), cell("实际扣分", third["applied_military_debit_points"], "取较大值", SOURCES["third"]), cell("第三项合计", third["third_item_score_points"], "合计", SOURCES["third"])]
    equal(third["A120_score_points"]+third["B80_score_points"]+third["C50_score_points"]-third["applied_military_debit_points"], row["third_item_score"], "第三项")
    details["military"] = military
    fourth = sources["fourth"][fid]
    axes = {r["axis"]: r for r in fourth["axis_results"]}
    civilization = []
    for key, label in (("A", "A国家共同体"), ("B", "B教育与人才"), ("C", "C文化知识")):
        r = axes[key]
        grade = " / ".join(str(r[k]) for k in ("direction", "magnitude_grade", "band") if r.get(k) is not None)
        civilization.append(cell(label, r["signed_adjustment"], grade or r["disposition"], FOURTH))
    equal(sum(x["value"] for x in civilization), row["fourth_item_adjustment"], "第四项")
    civilization.append(cell("第四项调整", row["fourth_item_adjustment"], "合计", FOURTH))
    details["civilization"] = civilization
    return details


def render_component_details(records: list[dict[str, Any]]) -> list[str]:
    labels = {
        "upper": "上位", "middle-upper": "中上位", "middle": "中位",
        "middle-lower": "中下位", "lower": "下位",
        "HIGH": "高位", "MID": "中位", "LOW": "低位",
        "POSITIVE": "正向", "NEGATIVE": "负向", "BALANCED": "正负相抵",
        "NO_ELIGIBLE_CIVILIZATION_INCREMENT": "无合格文明增量",
        "NO_ELIGIBLE_INCREMENT_AFTER_EVIDENCE_REVIEW": "证据复核后无合格增量",
    }
    lines = ["", "## 分项明细", "", "各表均按总榜基准顺序排列。单元格先列档位、位置或计分性质，再列分数或指数；各档位沿用所属合同，不跨项等同。第一项档位后缀HIGH/MID/LOW分别为高位/中位/低位。", ""]
    for key, title, explanation in SECTIONS:
        columns = [c["label"] for c in records[0]["component_details"][key]]
        lines += [f"### {title}", "", explanation, "", "| 人物 | " + " | ".join(columns) + " |", "|---|" + "---|" * len(columns)]
        for row in records:
            cells = []
            for c in row["component_details"][key]:
                grade = " / ".join(labels.get(part, part) for part in c["grade"].split(" / "))
                value = "" if c["value"] is None else (f"{c['value']:+.2f}" if key == "civilization" else f"{c['value']:.2f}")
                text = f"{grade}；{value}{c['unit']}" if value else f"{grade}（{c['unit']}）" if c['unit'] == '不单独计分' else grade
                if c["note"]:
                    text += f"；{c['note']}"
                cells.append(text.replace("|", "\\|").replace("\n", " "))
            lines.append(f"| {row['ruler_name']} | " + " | ".join(cells) + " |")
        paths = list(dict.fromkeys(c["source"] for row in records for c in row["component_details"][key]))
        lines += ["", "正式来源：" + "、".join(f"[{Path(p).stem}]({Path('../../' + p).as_posix()})" for p in paths) + "。", ""]
    return lines
