"""Read current historical-impact decisions; never infer grades from evidence text."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from urllib.parse import urlparse
from emperor_v4.evaluation.formal_json_store import load_json, json_read_session

PUBLIC_GRADES = ("S+", "S", "A", "B", "C", "D", "E")
DIMENSION_GRADES = ("S+", "S", "S-", "A+", "A", "B", "C")
LABEL_MAPPING = dict(zip(DIMENSION_GRADES, PUBLIC_GRADES))
DIMENSIONS = {"scope": "范围", "depth_duration": "深度/持续", "personal_causality": "个人因果", "paradigm": "范式"}
PUBLIC_MEANINGS = dict(zip(PUBLIC_GRADES, ("文明／国家主路径重塑", "超重大历史影响", "重大长期历史影响", "重大历史影响", "显著历史影响", "有限但真实影响", "弱历史影响")))


def _source_label(source: dict) -> str:
    kind = source["kind"]
    if kind == "IMPORTED_ADJUDICATION":
        return f"采纳段落：{source['document']}，{source['section']}／{source.get('subsection', '')}"
    if kind == "HISTORICAL_WEB_SOURCE":
        return f"[{source['title']}]({source['url']})：{source['evidence_note']}"
    locator = "、".join(source.get("parent_ids", [])) or "、".join(source.get("field_paths", [])) or source.get("ruler_id", source.get("ruler_name", ""))
    return f"本地事实：`{source['path']}`；定位：{locator}"


def _entry(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/project.yml").read_text(encoding="utf-8"))["historical_impact_assessment"]


def _dimension(row: dict, key: str) -> str:
    value = row["dimensions"][key]
    return value["grade"] + (f"（{value['boundary_note']}）" if value["boundary_note"] else "")


def render(payload: dict[str, Any]) -> str:
    lines = ["# 历史影响量级正式结算", "",
        "> 与人物画像、净收益并列的第三套评价体系；不计分、不进入九轴雷达或综合榜。正式JSON保存当前裁决，本页为同值阅读视图。", "",
        "公众总档为S+、S、A、B、C、D、E，均表示影响量级，不是成绩优劣；四维使用独立七档标尺。性质与量级分开，同档不设名次，人物按时代阅读。", "",
        "主链注明实际采纳段落；仅能定位人物的本地入口另列为相关资料。旧会话引用不再作为史源，采纳裁决段落不等于重新通读原始史料。工程只作宏观转型的过程，不能单列抬档。", "",
        "[主池总表](#main-table) · [主池逐人依据](#main-records) · [补充样本](#supplementary-table)", "",
        "范围看实际改变的政治空间，深度看结构后效，个人因果看本人归责，范式看后世实际使用。总档不是四维平均；完整论证与来源可在各人卡片内展开。", "",
        "## 主池覆盖", "",
        f"规范人物池已覆盖{payload['record_count']}人；另列{payload['supplementary_record_count']}个既有补充样本，不计入主池分布。", "",
        "| 总档 | 主池人数 |", "|---|---:|"]
    counts = Counter(r["public_grade"] for r in payload["records"])
    lines.extend(f"| {g}·{PUBLIC_MEANINGS[g]} | {counts[g]} |" for g in PUBLIC_GRADES)
    for key, title in (("records", "主池"), ("supplementary_records", "补充样本")):
        section = "main" if key == "records" else "supplementary"
        lines.extend(["", f'<a id="{section}-table"></a>', "", f"## {title}总表", "", "点击人物查看结论与依据。总档释义见上表；置信度在逐人卡片展示。", "", "| 人物及身份 | 政权 | 总档 | 性质 | 范围 | 深度/持续 | 个人因果 | 范式 |", "|---|---|---|---|---|---|---|---|"])
        for row in payload[key]:
            cells = [f"[{row['identity_label']}](#person-{row['ruler_id'].lower()})", row["polity"], row["public_grade"], row["impact_nature"], *(row["dimensions"][d]["grade"] for d in DIMENSIONS)]
            lines.append("| " + " | ".join(cells) + " |")
        lines.extend(["", f'<a id="{section}-records"></a>', "", f"## {title}逐人依据", ""])
        for row in payload[key]:
            confidence = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}[row["confidence"]]
            lines.extend([f'<a id="person-{row["ruler_id"].lower()}"></a>', "", f"### {row['identity_label']}", "",
                f"**总档：{row['public_grade']}·{PUBLIC_MEANINGS[row['public_grade']]}｜{row['impact_nature']}｜置信度：{confidence}**", "",
                "；".join(f"{label}：{_dimension(row, d)}" for d, label in DIMENSIONS.items()) + "。", ""])
            lines.extend(["**核心足迹：**" + "；".join(c["title"] for c in row["macro_chains"]), ""])
            scope = row.get("scope_assessment")
            if scope:
                lines.extend(["**范围为何取此档：**" + scope["actual_changes"], "",
                    "**继承与排除：**" + scope["baseline_and_exclusions"], ""])
            depth = row.get("depth_review", {})
            if depth.get("basis"):
                lines.extend(["**深度与持续：**" + depth["basis"], "", "**持续性边界：**" + depth["limits"], ""])
            foundation = row.get("foundation")
            if foundation:
                lines.extend([f"**总档依据：**基础{foundation['base_band']}。{foundation['joint_footprint_basis']}", ""])
            lines.extend([f"[返回{title}总表](#{section}-table)", "", "<details>", "<summary>展开完整裁决、反事实与来源</summary>", "",
                f"人物标识：`{row['ruler_id']}`", "",
                f"**参考掌权/活动窗口：**{row['reference_power_window']}。反事实起点以关键行动主链为准。", ""])
            if row.get("scope_assessment", {}).get("observation_window") and row["scope_assessment"]["observation_window"] != row.get("counterfactual_entry", {}).get("anchor"):
                lines.extend(["**范围观察窗口：**" + row["scope_assessment"]["observation_window"], ""])
            entry = row.get("counterfactual_entry")
            if entry:
                lines.extend(["**反事实起点：**" + entry["anchor"], "", "**保留条件：**" + entry["retained_conditions"], ""])
            foundation = row.get("foundation")
            if foundation:
                lines.extend([f"**归责与修正：**{foundation['causal_adjustment']}{foundation['paradigm_adjustment']}最终按已裁边界落内部{foundation['decided_internal_band']}，对应公众{foundation['decided_public_grade']}。", ""])
            displayed = {p.strip() for c in row["macro_chains"] for p in c["narrative"].split("\n\n")}
            displayed.update((scope or {}).get(k, "") for k in ("actual_changes", "baseline_and_exclusions"))
            displayed.add((foundation or {}).get("joint_footprint_basis", ""))
            displayed.update((foundation or {}).get(k, "") for k in ("causal_adjustment", "paradigm_adjustment"))
            displayed.update(p.strip() for p in row["personal_causal_boundary"].split("\n\n"))
            displayed.update(depth.get(k, "") for k in ("basis", "limits"))
            additional = [p for p in row["grade_basis"].split("\n\n") if p.strip() and p.strip() not in displayed]
            if additional:
                lines.extend(["**补充裁决依据：**", "", "\n\n".join(additional), ""])
            for chain in row["macro_chains"]:
                lines.extend([f"**影响主链：{chain['title']}**", "", chain["narrative"], ""])
                lines.extend("- " + _source_label(row["source_refs"][i]) for i in chain["source_ref_indices"])
                lines.append("")
            if row.get("contextual_evidence"):
                lines.extend(["**非独立计档的过程事实：**", ""])
                lines.extend("- " + e["basis"] for e in row["contextual_evidence"])
                lines.append("")
            lines.extend(["**最近可行反事实：**", "", row["nearest_feasible_counterfactual"], ""])
            if row["personal_causal_boundary"] != row["nearest_feasible_counterfactual"]:
                lines.extend(["**个人因果边界：**", "", row["personal_causal_boundary"], ""])
            shown_refs = {i for c in row["macro_chains"] for i in c["source_ref_indices"]}
            shown_refs.update(row.get("paradigm_review", {}).get("source_ref_indices", []))
            causal_refs = [i for i in row.get("causal_review", {}).get("source_ref_indices", []) if i not in shown_refs]
            if causal_refs:
                lines.extend(["**归责核对来源：**", ""])
                lines.extend("- " + _source_label(row["source_refs"][i]) for i in causal_refs)
                lines.append("")
            lines.extend(["**范式与示范：**", "", row["paradigm_analysis"], "", "**来源与核对范围：**", "", *row["historical_source_notes"]])
            review = row.get("paradigm_review")
            if review:
                statuses = {"LOCATED_RECEPTION": "已定位接收", "IMAGE_ONLY": "目前仅有形象传播", "NOT_LOCATED": "当前未定位接收"}
                lines.extend([statuses[review["evidence_status"]] + "。" + review["limitation"], ""])
                for reception in review["receptions"]:
                    lines.append(f"- {reception['receiver']}｜{reception['carrier']}｜{reception['actual_use']}")
                for i in review.get("source_ref_indices", []):
                    lines.append("- " + _source_label(row["source_refs"][i]))
            lines.extend(["", "**置信度边界：**" + row.get("confidence_basis", "仅表示当前量级判断稳定性，不保证替代年表唯一。"), ""])
            if row.get("related_fact_entries"):
                lines.extend(["<details>", "<summary>相关事实入口（不自动充当本主链证据）</summary>", ""])
                lines.extend("- " + _source_label(s) for s in row["related_fact_entries"])
                lines.extend(["", "</details>"])
            lines.extend(["", "</details>", ""])
    return "\n".join(line.rstrip() for line in "\n".join(lines).splitlines()).rstrip() + "\n"


def write_views(root: Path) -> dict[str, Any]:
    verify(root, check_reader=False)
    entry = _entry(root)
    payload = load_json(root / entry["json"])
    (root / entry["markdown"]).write_text(render(payload), encoding="utf-8", newline="\n")
    return {"status": "WRITTEN", "markdown": entry["markdown"]}


@json_read_session()
def verify(root: Path, *, check_reader: bool = True) -> dict[str, Any]:
    entry = _entry(root)
    payload = load_json(root / entry["json"])
    if payload["schema_version"] != entry["payload_schema_version"] or payload["contract_version"] != entry["contract_version"]:
        raise ValueError("历史影响版本与注册不一致")
    if payload["public_label_mapping"] != LABEL_MAPPING:
        raise ValueError("历史影响标签映射与合同不一致")
    for obj in (entry, payload):
        if any(obj[k] for k in ("numerical_scoring_enabled", "composite_ranking_write", "profile_radar_write")):
            raise ValueError("历史影响不得写入数值评分、综合榜或画像雷达")
    pool = {r["ruler_id"]: r for r in load_json(root / entry["canonical_pool"])["records"] if r["pool_status"] == "INCLUDED"}
    main, extra = payload["records"], payload["supplementary_records"]
    ids = [r["ruler_id"] for r in main + extra]
    if len(ids) != len(set(ids)) or {r["ruler_id"] for r in main} != set(pool):
        raise ValueError("历史影响主池覆盖或跨池ID冲突")
    if len(main) != payload["record_count"] or len(extra) != payload["supplementary_record_count"]:
        raise ValueError("历史影响记录数声明不一致")
    sources: dict[str, dict[str, Any]] = {}
    for rows, scope in ((main, "MAIN_POOL"), (extra, "SUPPLEMENTARY")):
        if rows != sorted(rows, key=lambda r: (r["reading_start_year"], r["ruler_id"])):
            raise ValueError("历史影响时代阅读顺序不一致")
        for row in rows:
            rid = row["ruler_id"]
            if row["pool_relation"] != scope or row["formal_status"] != "FORMAL_CURRENT" or row["task_code"] != f"HISTORICAL-IMPACT-{rid}":
                raise ValueError(f"历史影响范围、身份或状态错误: {rid}")
            if scope == "MAIN_POOL":
                person = pool[rid]
                if any(row[k] != person[k] for k in ("ruler_name", "polity")) or row["reference_power_window"] != person["actual_power_window"]:
                    raise ValueError(f"历史影响规范身份/参考窗口不一致: {rid}")
            if LABEL_MAPPING.get(row["internal_band"]) != row["public_grade"]:
                raise ValueError(f"历史影响公众标签错误: {rid}")
            if set(row["dimensions"]) != set(DIMENSIONS) or any(v["grade"] not in DIMENSION_GRADES for v in row["dimensions"].values()):
                raise ValueError(f"历史影响四维不完整: {rid}")
            if row["dimensions"]["scope"]["boundary_note"]:
                raise ValueError(f"范围只发布主档，边界须写为事实说明: {rid}")
            if "scope_assessment" in row and not all(row["scope_assessment"].get(k) for k in ("actual_changes", "baseline_and_exclusions", "overall_grade_reasoning", "method")):
                raise ValueError(f"范围复核未闭合实际变化、基线或总档: {rid}")
            if row["confidence"] not in {"HIGH", "MEDIUM", "LOW"} or (row["public_grade"] == "S+" and row["confidence"] == "LOW"):
                raise ValueError(f"历史影响置信度不符合合同: {rid}")
            for key in ("nearest_feasible_counterfactual", "personal_causal_boundary", "paradigm_analysis", "grade_basis", "source_refs", "impact_nature", "counterfactual_entry", "foundation", "paradigm_review", "confidence_basis", "source_trace"):
                if not row.get(key):
                    raise ValueError(f"历史影响必要依据缺失: {rid}/{key}")
            if not all(row["counterfactual_entry"].get(k) for k in ("anchor", "retained_conditions", "functional_alternative", "identity_exclusion")):
                raise ValueError(f"反事实删除点或保留条件不完整: {rid}")
            chains = row["macro_chains"]
            if not 1 <= len(chains) <= 3 or len({c["chain_id"] for c in chains}) != len(chains):
                raise ValueError(f"历史影响宏观主链不符合合同: {rid}")
            for chain in chains:
                if not chain["title"] or not chain["narrative"] or not chain["source_ref_indices"] or any(i < 0 or i >= len(row["source_refs"]) for i in chain["source_ref_indices"]):
                    raise ValueError(f"历史影响主链来源错误: {rid}")
                if chain.get("chain_kind") != "MACRO_TRANSFORMATION":
                    raise ValueError(f"工程或其他非宏观事实不能独立作为主链: {rid}")
            foundation = row["foundation"]
            if foundation.get("base_band") not in DIMENSION_GRADES or not foundation.get("chain_ids") or not set(foundation["chain_ids"]) <= {c["chain_id"] for c in chains}:
                raise ValueError(f"基础档缺少有效宏观主链: {rid}")
            if not all(foundation.get(k) for k in ("joint_footprint_basis", "causal_adjustment", "causal_application", "paradigm_adjustment")):
                raise ValueError(f"基础档或修正理由不完整: {rid}")
            if foundation.get("decided_internal_band") != row["internal_band"] or foundation.get("decided_public_grade") != row["public_grade"]:
                raise ValueError(f"基础档记录与当前总档声明不同值: {rid}")
            review = row["paradigm_review"]
            if review.get("evidence_status") not in {"LOCATED_RECEPTION", "IMAGE_ONLY", "NOT_LOCATED"} or not review.get("limitation") or not review.get("depth_separation"):
                raise ValueError(f"范式证据状态或去重说明缺失: {rid}")
            receptions = review.get("receptions", [])
            if any(not all(c.get(k) for k in ("receiver", "carrier", "actual_use", "source_basis")) for c in receptions):
                raise ValueError(f"范式接收闭环不完整: {rid}")
            pgrade = row["dimensions"]["paradigm"]["grade"]
            if pgrade in {"A", "A+", "S-", "S", "S+"} and not receptions:
                raise ValueError(f"已发布范式档缺少接收案例: {rid}")
            if pgrade in {"S-", "S", "S+"} and len({c["receiver"] for c in receptions}) < 2:
                raise ValueError(f"高范式缺少独立接收者: {rid}")
            for key in ("paradigm_review", "scope_assessment", "depth_review", "causal_review"):
                if any(i < 0 or i >= len(row["source_refs"]) for i in row.get(key, {}).get("source_ref_indices", [])):
                    raise ValueError(f"专项依据来源索引越界: {rid}/{key}")
            if any(s["kind"] not in {"LOCAL_FORMAL_RECORD", "LOCAL_FORMAL_DOCUMENT"} for s in row.get("related_fact_entries", [])):
                raise ValueError(f"相关事实入口类型错误: {rid}")
            for source in row["source_refs"] + row.get("related_fact_entries", []):
                if source["kind"] == "LOCAL_FORMAL_RECORD":
                    path = (root / source["path"]).resolve()
                    if not path.is_relative_to(root.resolve()) or source["ruler_id"] != rid:
                        raise ValueError(f"历史影响来源路径或归人错误: {rid}")
                    if source["path"] not in sources:
                        sources[source["path"]] = {r["ruler_id"]: r for r in load_json(path)["records"]}
                    if rid not in sources[source["path"]]:
                        raise ValueError(f"历史影响来源人物不存在: {rid}")
                    source_row = sources[source["path"]][rid]
                    if not set(source.get("parent_ids", [])) <= {p["parent_id"] for p in source_row.get("parent_chains", [])}:
                        raise ValueError(f"历史影响引用的正式父链不存在: {rid}")
                    if any(k not in source_row for k in source.get("field_paths", [])):
                        raise ValueError(f"历史影响引用的事实字段不存在: {rid}")
                elif source["kind"] == "LOCAL_FORMAL_DOCUMENT":
                    path = (root / source["path"]).resolve()
                    if not path.is_relative_to(root.resolve()) or source.get("ruler_name") != row["ruler_name"] or row["ruler_name"] not in path.read_text(encoding="utf-8"):
                        raise ValueError(f"历史影响文档来源归人错误: {rid}")
                elif source["kind"] == "HISTORICAL_WEB_SOURCE":
                    if urlparse(source.get("url", "")).scheme != "https" or not all(source.get(k) for k in ("title", "evidence_note", "verification_mode")):
                        raise ValueError(f"历史影响外部来源缺少离线证据说明: {rid}")
                elif source["kind"] != "IMPORTED_ADJUDICATION" or not all(source.get(k) for k in ("document", "section", "subsection", "adopted_excerpt", "evidence_role")):
                    raise ValueError(f"历史影响导入段落定位不完整: {rid}")
    if check_reader and (root / entry["markdown"]).read_text(encoding="utf-8") != render(payload):
        raise ValueError("历史影响JSON与阅读视图不同值")
    return {"status": "PASS", "validation_scope": "IDENTITY_COVERAGE_LABELS_LINEAGE_AND_READER_NOT_HISTORICAL_READJUDICATION", "main_pool_count": len(main), "supplementary_count": len(extra)}
