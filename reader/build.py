"""Build the static reading layer from registered settlements; never adjudicate."""
from pathlib import Path
from copy import deepcopy
import json
import sys
import argparse
import re
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
DETAILS_DIR = ROOT / "reader/data/people"
SECOND_ITEM_READER_SUMMARIES = "reader/second-item-summaries.json"
sys.path.insert(0, str(ROOT / "src"))
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.first_item_public_outcomes import (
    load_first_item_public_outcomes,
    public_outcome_for_name,
)
from emperor_v4.evaluation.profile_parent_schema import parent_chains
from emperor_v4.evaluation.composite_details import load_detail_sources, SECOND

NET_READER_EXTRA_SOURCES = {
    "D1": SECOND + "政权交接稳定/01-D1继任行政连续性方向卡.json",
    "D3": SECOND + "政权交接稳定/02-D3政权交接稳定方向卡.json",
    "ML": "config/third-item/third-item-military-net-loss-penalties.json",
}


def index(rows):
    result = {r["ruler_id"]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate ruler_id")
    return result


def pick(row, fields):
    return {k: row[k] for k in fields if k in row}


def local_sources(value):
    """Resolve local reference availability without inventing replacement evidence."""
    if isinstance(value, dict):
        return {p for child in value.values() for p in local_sources(child)}
    if isinstance(value, list):
        return {p for child in value for p in local_sources(child)}
    if isinstance(value, str) and value.startswith(("docs/", "config/", "archive/")) and "\n" not in value:
        return {value}
    return set()


def source_file(ref):
    """Accept both Markdown fragments and existing path:line citations."""
    return re.sub(r":\d+(?:-\d+)?$", "", unquote(ref.split("#", 1)[0]))


def apply_public_copy(template):
    """Apply reader-only wording without changing any settlement payload."""
    path = ROOT / "reader/public-copy.json"
    replacements = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(replacements, list):
        raise ValueError("Reader public copy must be a list")
    for i, item in enumerate(replacements):
        if not isinstance(item, dict) or not isinstance(item.get("from"), str) or not isinstance(item.get("to"), str):
            raise ValueError(f"Invalid reader public copy entry: {i}")
        old, new = item["from"], item["to"]
        if old not in template:
            raise ValueError(f"Reader public copy source is stale: {old}")
        template = template.replace(old, new)
    return template


def axis_projection(row, fields):
    result = pick(row, fields)
    chains = parent_chains(row)
    result["source_refs"] = list(dict.fromkeys(
        ref for owner in [row, *chains]
        for ref in owner.get("source_refs", []) if isinstance(ref, str)
    ))
    counter = row.get("counterpattern")
    if isinstance(counter, dict):
        ids = {ref for values in counter.values() if isinstance(values, list) for ref in values if isinstance(ref, str)}
        result["context_lookup"] = {
            p["parent_id"]: pick(p, ["parent_id", "cycle_basis", "basis", "source_refs", "direction"])
            for p in chains if p.get("parent_id") in ids
        }
        missing = ids - result["context_lookup"].keys()
        if missing:
            raise ValueError(f"Unresolved context references: {sorted(missing)}")

    # Reader-only projection: consume existing formal fields without creating a second adjudication source.
    if row.get("axis_code") == "C4":
        representative_ids = [x for x in row.get("representative_parent_ids", []) if isinstance(x, str)]
        chain_by_id = {p.get("parent_id"): p for p in chains if p.get("parent_id")}
        result["representative_contexts"] = [
            pick(chain_by_id[parent_id], ["parent_id", "title", "mechanism", "cycle_basis", "basis", "attribution", "direction"])
            for parent_id in representative_ids if parent_id in chain_by_id
        ]
    if row.get("axis_code") == "C5" and isinstance(row.get("public_evidence_points"), list):
        result["public_evidence_points"] = [
            pick(point, ["title", "details"])
            for point in row["public_evidence_points"] if isinstance(point, dict)
        ]
    return result


def _clean_text(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _first_text(*values):
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _unique_texts(values, limit=4):
    result = []
    seen = set()
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return result


def _state_summary(record):
    state = record.get("state_adjudication")
    if not isinstance(state, dict):
        return ""
    preferred = []
    for key in ("main_review", "loss_review", "result_review", "recovery_review"):
        block = state.get(key)
        if isinstance(block, dict):
            preferred.extend([
                block.get("main_representativeness"),
                block.get("summary"),
                block.get("basis"),
            ])
    return _first_text(*preferred)


def _formal_summary(record):
    if not isinstance(record, dict):
        return ""
    return _first_text(
        record.get("public_summary"),
        record.get("adjudication_reason"),
        _state_summary(record),
        record.get("strategy_chain_review_basis"),
        record.get("grade_basis"),
        record.get("attribution_basis"),
        record.get("basis"),
        record.get("reason"),
    )


def _lead_sentences(text, limit=2):
    text = _clean_text(text)
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"(?<=[。！？；])", text) if part.strip()]
    if not parts:
        return text
    return "".join(parts[:limit])


def _formal_highlights(record):
    if not isinstance(record, dict):
        return []
    values = []
    for item in record.get("important_institutions", []):
        if isinstance(item, dict):
            values.append(item.get("reason") or item.get("label_zh"))
    for item in record.get("structured_grade_basis", []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        if any(token in role for token in ("正向", "负向", "反例", "边界")):
            values.append(item.get("text"))
    for key in ("M_positive_profile", "M_negative_profile", "M_mixed_profile"):
        for item in record.get(key, []):
            if isinstance(item, dict):
                values.append(item.get("mechanism"))
    for key in (
        "maintenance_basis", "reversal_basis", "within_band_deterioration_basis",
        "direction_reason", "recovery_basis",
    ):
        values.append(record.get(key))
    return _unique_texts(values, limit=3)


def _formal_boundary(record):
    if not isinstance(record, dict):
        return ""
    values = []
    for key in ("material_limitations", "unresolved_gaps", "limitations"):
        value = record.get(key)
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)
    return "；".join(_unique_texts(values, limit=2))


def _formal_source_refs(record, *extra):
    refs = []
    for ref in extra:
        if isinstance(ref, str) and ref.startswith(("docs/", "config/", "archive/")):
            refs.append(ref)
    if isinstance(record, dict):
        refs.extend(sorted(local_sources(record)))
    return list(dict.fromkeys(refs))[:8]


def _attach_reader(item, *, kind, summary="", how="", record=None, boundary="", source_refs=(), highlights=()):
    result = dict(item)
    result["reader_kind"] = kind
    formal_summary = _formal_summary(record)
    final_summary = _first_text(summary, _lead_sentences(formal_summary))
    final_highlights = _unique_texts([*highlights, *_formal_highlights(record)], limit=3)
    final_boundary = _first_text(boundary, _formal_boundary(record))
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if final_summary:
        result["reader_summary"] = final_summary
    if formal_summary and _clean_text(final_summary) != _clean_text(formal_summary):
        result["reader_full_basis"] = formal_summary
    if final_highlights:
        result["reader_highlights"] = final_highlights
    if final_boundary:
        result["reader_boundary"] = final_boundary
    if how:
        result["reader_how"] = how
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_b2_public_reader(item, *, record, how="", source_refs=()):
    """Project B2's explicit public fields without semantic fallback guessing."""

    if not isinstance(record, dict):
        raise ValueError("B2 reader projection requires a formal record")
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"B2 formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"B2 formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["reader_highlights"] = _unique_texts(
        [
            f"{entry.get('public_label')}：{entry.get('public_basis')}"
            for entry in evidence
            if isinstance(entry, dict)
        ],
        limit=None,
    )
    boundaries = _unique_texts(
        [entry.get("public_boundary") for entry in evidence if isinstance(entry, dict)]
    )
    if boundaries:
        result["reader_boundary"] = "；".join(boundaries)
    if how:
        result["reader_how"] = how
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_d1_d3_public_reader(item, *, record, axis, how="", source_refs=()):
    """Project D1/D3's explicit public fields without generic fallback guessing."""

    if not isinstance(record, dict):
        raise ValueError(f"{axis} reader projection requires a formal record")
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{axis} formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["reader_highlights"] = _unique_texts(
        [
            f"{entry.get('public_role')}：{entry.get('public_basis')}"
            for entry in evidence
            if isinstance(entry, dict)
        ],
        limit=None,
    )
    boundaries = _unique_texts(
        [entry.get("public_boundary") for entry in evidence if isinstance(entry, dict)],
        limit=None,
    )
    if boundaries:
        result["reader_boundary"] = "；".join(boundaries)
    if how:
        result["reader_how"] = how
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def load_net_reader_sources(root):
    """Load formal subitem evidence for reader-only explanations."""
    sources = load_detail_sources(root)
    for key, path in NET_READER_EXTRA_SOURCES.items():
        payload = load_json(root / path)
        rows = payload["records"]
        sources[key] = index(rows)
        sources[f"{key}_path"] = path
    return sources


def load_second_item_reader_summaries(root, eligible_ids):
    """Load persisted reader-only conclusions for the currently ranked pool."""
    path = root / SECOND_ITEM_READER_SUMMARIES
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing reader-only Second Item summaries: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_id") != "reader-second-item-conclusion-v1":
        raise ValueError("Invalid reader-only Second Item summary schema")
    summaries = payload.get("summaries")
    if not isinstance(summaries, dict):
        raise ValueError("Reader-only Second Item summaries must be an object")
    eligible = set(eligible_ids)
    outside = sorted(set(summaries) - eligible)
    if outside:
        raise ValueError(f"Reader-only Second Item summaries reference unranked rulers: {outside}")
    result = {}
    for ruler_id, summary in summaries.items():
        if not isinstance(ruler_id, str) or not ruler_id:
            raise ValueError("Reader-only Second Item summary has an invalid ruler_id")
        if not isinstance(summary, str):
            raise ValueError(f"Reader-only Second Item summary is not text: {ruler_id}")
        summary = _clean_text(summary)
        if not 35 <= len(summary) <= 120:
            raise ValueError(f"Reader-only Second Item summary length is outside 35-120: {ruler_id}")
        if any(mark in summary for mark in ("<", ">")):
            raise ValueError(f"Reader-only Second Item summary must be plain text: {ruler_id}")
        if re.search(r"\d|\b(?:A|B1|B2|C[1-4]|D[13]|G[0-5]|DA[0-4])\b", summary):
            raise ValueError(f"Reader-only Second Item summary exposes internal scoring language: {ruler_id}")
        if re.search(r"推动|带来|因而|使(?:生产|财政|民生|社会|家庭|普通|秩序|行政)|让(?:生产|财政|民生|社会|家庭|普通|秩序|行政)|令(?:生产|财政|民生|社会|家庭|普通|秩序|行政)", summary):
            raise ValueError(f"Reader-only Second Item summary asserts an unqualified method-result causality: {ruler_id}")
        if re.search(r"缺少高风险检验|压力检验不足|风险检验不足|没有经历.*风险|缺乏高风险|评分门槛|相对最强|相对最弱|最强|最弱", summary):
            raise ValueError(f"Reader-only Second Item summary contains a forbidden reader conclusion: {ruler_id}")
        if re.search(r"军事|边疆|边防|统一功业|北伐|远征|军队|军费|军粮|兵变|战争|战乱|战后", summary):
            raise ValueError(f"Reader-only Second Item summary crosses into the military/unification item: {ruler_id}")
        result[ruler_id] = summary
    skipped = payload.get("skipped", [])
    if not isinstance(skipped, list):
        raise ValueError("Reader-only Second Item skipped must be a list")
    skipped_ids = set()
    for item in skipped:
        if not isinstance(item, dict) or not isinstance(item.get("ruler_id"), str) or not isinstance(item.get("reason"), str):
            raise ValueError("Reader-only Second Item skipped entries need ruler_id and reason")
        if not item["reason"].strip():
            raise ValueError(f"Reader-only Second Item skipped entry has an empty reason: {item['ruler_id']}")
        if item["ruler_id"] in result:
            raise ValueError(f"Reader-only Second Item ruler is both summarized and skipped: {item['ruler_id']}")
        if item["ruler_id"] in eligible:
            raise ValueError(f"Reader-only Second Item eligible ruler is skipped: {item['ruler_id']}")
        if item["ruler_id"] in skipped_ids:
            raise ValueError(f"Reader-only Second Item ruler is skipped more than once: {item['ruler_id']}")
        skipped_ids.add(item["ruler_id"])
    return result


def project_net_explanations(person, row, sources, first_item_public_outcomes=None):
    """Add reader-only explanation metadata without changing any scoring value."""
    details = deepcopy(row.get("component_details", {}))
    if not details:
        return details
    ids = person["source_item_ids"]
    name = row["ruler_name"]
    sid, tid, fid = (ids[k] for k in ("second_item", "third_item", "fourth_item"))

    first = {item["label"]: item for item in details.get("first", [])}
    for label, item in list(first.items()):
        if label == "A统一贡献":
            first[label] = _attach_reader(
                item, kind="judgment",
                summary="只评价本人在建国、复国或统一主链中最终留下的稳定控制成果；起点、对手强弱和完成速度不在这里重复计分。",
                how=f"{item.get('note') or '按正式A项控制信用与项目归属'}；单人项目按统一贡献曲线计算，共同项目先生成项目A池再按正式个人信用分账，最终为 {item.get('value')} 分。",
            )
            if item.get("value") is not None:
                if first_item_public_outcomes is None:
                    raise ValueError("第一项A缺少正式公开成果投影")
                first[label]["reader_public_outcome"] = public_outcome_for_name(
                    first_item_public_outcomes, name
                )
        elif label == "B1创业难度与效率":
            first[label] = _attach_reader(
                item, kind="judgment",
                summary="评价从什么起点出发、面对多强的主要对手，以及完成创业或统一主链的效率。",
                how=f"{item.get('grade', '')}；{item.get('note', '')}，合计 {item.get('value')} 分。",
            )
        elif label == "B2组织与整合":
            first[label] = _attach_reader(
                item, kind="judgment",
                summary="评价创业或统一过程中同时处理多线任务、覆盖关键区域并完成组织整合的能力。",
                how=f"{item.get('grade', '')}；{item.get('note', '')}，合计 {item.get('value')} 分。",
            )
        elif label == "C军事统帅与战争解题":
            first[label] = _attach_reader(
                item, kind="judgment",
                summary="只评价本人在创业或统一主链中的军事统帅与战争解题能力，团队作用按正式归责路线处理。",
                how=f"正式能力档与归责路线共同换算为 {item.get('value')} 分；{item.get('note', '')}",
            )
        elif label == "军事成本扣分":
            cost = sources["first_cost"].get(name, {})
            first[label] = _attach_reader(
                item, kind="judgment", record=cost,
                how=f"正式军事成本档与档内位置按成本表换算为扣 {item.get('value')} 分。",
                boundary=cost.get("responsibility_window", ""),
            )
        else:
            first[label] = _attach_reader(item, kind="calculation")
    if first:
        values = {label: item.get("value") for label, item in first.items()}
        if "四轴合计" in first:
            first["四轴合计"]["reader_how"] = (
                f"A统一贡献 + B1创业难度与效率 + B2组织与整合 + C军事统帅与战争解题 = {values.get('四轴合计')} 分。"
            )
        if "第一项净分" in first:
            first["第一项净分"]["reader_how"] = (
                f"四轴合计 {values.get('四轴合计')} − 军事成本扣分 {values.get('军事成本扣分')}，最低按0计，得到 {values.get('第一项净分')} 分。"
            )
        if "附加F" in first:
            first["附加F"]["reader_how"] = (
                f"第一项净分再按总榜附加F曲线折算，得到 {values.get('附加F')} 分。"
            )
        details["first"] = [first[item["label"]] for item in details["first"]]

    method_records = {"A制度建设": "A", "B1官僚治理": "B1", "B2反馈与约束": "B2"}
    method = {item["label"]: item for item in details.get("method", [])}
    for label, key in method_records.items():
        if label in method:
            item = method[label]
            record = sources[key][sid]
            how = f"正式方向指数为 {item.get('value')}；该指数随后进入治理手段合成公式。"
            if key == "B2":
                method[label] = _attach_b2_public_reader(item, record=record, how=how)
            else:
                method[label] = _attach_reader(item, kind="judgment", record=record, how=how)
    if method:
        values = {label: item.get("value") for label, item in method.items()}
        for label in ("AB计分块", "B2折算", "治理手段"):
            if label in method:
                method[label] = _attach_reader(method[label], kind="calculation")
        if "AB计分块" in method:
            method["AB计分块"]["reader_how"] = (
                f"0.8 × [max(A制度建设, B1官僚治理) + 0.5 × min(A制度建设, B1官僚治理)] = {values.get('AB计分块')} 分。"
            )
        if "B2折算" in method:
            method["B2折算"]["reader_how"] = f"45 / 80 × B2反馈与约束指数 = {values.get('B2折算')} 分。"
        if "治理手段" in method:
            method["治理手段"]["reader_how"] = (
                f"AB计分块 {values.get('AB计分块')} + B2折算 {values.get('B2折算')} = {values.get('治理手段')} 分。"
            )
        details["method"] = [method[item["label"]] for item in details["method"]]

    finance_keys = {"C1民生": "C1", "C2经济财政": "C2", "C3社会安全": "C3", "C4恢复与成本": "C4"}
    finance = {item["label"]: item for item in details.get("finance", [])}
    for label, key in finance_keys.items():
        if label not in finance:
            continue
        item = finance[label]
        record = sources[key][sid]
        if key == "C4" and item.get("note"):
            how = f"正向保留 − 恶化扣分 − 破坏放大扣分 = {item.get('note')} = {item.get('value')} 分。"
        else:
            how = f"正式状态判断与损失修正按本轴合同换算为 {item.get('value')} 分。"
        finance[label] = _attach_reader(item, kind="judgment", record=record, how=how)
    if "治理结果" in finance:
        values = {label: item.get("value") for label, item in finance.items()}
        finance["治理结果"] = _attach_reader(
            finance["治理结果"], kind="calculation",
            how=(
                f"C1民生 {values.get('C1民生')} + C2经济财政 {values.get('C2经济财政')} + "
                f"C3社会安全 {values.get('C3社会安全')} + C4恢复与成本 {values.get('C4恢复与成本')} "
                f"= {values.get('治理结果')} 分。"
            ),
        )
    if finance:
        details["finance"] = [finance[item["label"]] for item in details["finance"]]

    handoff = {item["label"]: item for item in details.get("handoff", [])}
    for label, key in (("D1继任行政连续性", "D1"), ("D3政权交接稳定", "D3")):
        if label in handoff:
            item = handoff[label]
            record = sources[key][sid]
            handoff[label] = _attach_d1_d3_public_reader(
                item, record=record, axis=key,
                how=f"正式交班裁决换算为 {item.get('value')} 级输入；该级本身不是独立可加分。",
                source_refs=(sources[f"{key}_path"],),
            )
    if handoff:
        values = {label: item.get("value") for label, item in handoff.items()}
        for label in ("低侧封顶", "交接得分", "第二项合计"):
            if label in handoff:
                handoff[label] = _attach_reader(handoff[label], kind="calculation")
        if "低侧封顶" in handoff:
            handoff["低侧封顶"]["reader_how"] = (
                f"交接短板决定本项最高可得 {values.get('低侧封顶')} 分；这是上限，不是额外得分。"
            )
        if "交接得分" in handoff:
            handoff["交接得分"]["reader_how"] = (
                f"min[2 × (D1 {values.get('D1继任行政连续性')} + D3 {values.get('D3政权交接稳定')}), "
                f"低侧封顶 {values.get('低侧封顶')}] = {values.get('交接得分')} 分。"
            )
        if "第二项合计" in handoff:
            method_score = next((x.get("value") for x in details.get("method", []) if x.get("label") == "治理手段"), None)
            result_score = next((x.get("value") for x in details.get("finance", []) if x.get("label") == "治理结果"), None)
            handoff["第二项合计"]["reader_how"] = (
                f"治理手段 {method_score} + 治理结果 {result_score} + 交接得分 {values.get('交接得分')} "
                f"= {values.get('第二项合计')} 分。"
            )
        details["handoff"] = [handoff[item["label"]] for item in details["handoff"]]

    credit = sources["credit"][tid]
    ab = sources["AB"][tid]
    strategic = {item["label"]: item for item in details.get("strategic", [])}
    for key in ("A1", "A2"):
        if key in strategic:
            axis = credit["axes"][key]
            strategic[key] = _attach_reader(
                strategic[key], kind="judgment", record=axis,
                summary=axis.get("attribution_basis", ""),
                how=f"起点状态、终点状态、改善或恶化及本人归责共同换算为 {strategic[key].get('value')} 分。",
            )
    for key in ("B1", "B2", "B4"):
        if key in strategic:
            axis = ab["axes"][key]
            rate = credit["B80_adjudication"][f"adjudicated_{key}_rate"]
            strategic[key] = _attach_reader(
                strategic[key], kind="judgment", record=axis,
                how=f"正式结果先得到 {strategic[key].get('value')}% 的原始得分率；边界复核后合成采用 {rate:g}%。",
            )
    for label in ("A120", "B80"):
        if label in strategic:
            strategic[label] = _attach_reader(strategic[label], kind="calculation")
    if "A120" in strategic:
        strategic["A120"]["reader_how"] = (
            f"A1 {strategic.get('A1', {}).get('value')} + A2 {strategic.get('A2', {}).get('value')} = "
            f"{strategic['A120'].get('value')} 分。"
        )
    if "B80" in strategic:
        strategic["B80"]["reader_how"] = (
            "B1控制规模与B2战略价值按55%/45%合成，再由B4交班成熟度修正，"
            f"得到 {strategic['B80'].get('value')} 分。"
        )
    if strategic:
        details["strategic"] = [strategic[item["label"]] for item in details["strategic"]]

    c_record = sources["C"][tid]
    third = sources["third"][tid]
    military = {item["label"]: item for item in details.get("military", [])}
    specific_reason_keys = {
        "C1实战交付": ("combat_delivery_basis", "C1_basis"),
        "C2持续作战": ("operational_sustainability_basis", "C2_basis"),
        "C3体系可靠性": ("system_reliability_basis", "C3_basis"),
    }
    for label, keys in specific_reason_keys.items():
        if label in military:
            summary = _first_text(*(c_record.get(key) for key in keys), c_record.get("strategy_chain_review_basis"))
            military[label] = _attach_reader(
                military[label], kind="judgment", record=c_record, summary=summary,
                how="这是军事体系能力档输入，不单独加分；三项共同决定C50。",
            )
    if "C50" in military:
        military["C50"] = _attach_reader(
            military["C50"], kind="calculation", record=c_record,
            summary=_formal_summary(c_record),
            how=f"C1、C2、C3共同确定军事体系总档，再按固定表换算为 {military['C50'].get('value')} 分。",
        )
    if "普通成本扣分" in military:
        cost_profile = third.get("global_cost_credit_profile", {})
        military["普通成本扣分"] = _attach_reader(
            military["普通成本扣分"], kind="judgment", record=cost_profile,
            summary=_formal_summary(cost_profile) or "按本人正式统治窗口内的军队、军事资产、后勤与持续再动员成本裁定全局军事成本档。",
            how=f"全局军事成本档按固定换分表折算为扣 {military['普通成本扣分'].get('value')} 分。",
        )
    if "ML扣分" in military:
        ml_record = sources["ML"].get(person["ruler_id"], {})
        military["ML扣分"] = _attach_reader(
            military["ML扣分"], kind="judgment", record=ml_record,
            summary=_formal_summary(ml_record) or "未触发额外军事净毁损扣分门。",
            how=f"军事净毁损按ML0—ML4固定表换算为扣 {military['ML扣分'].get('value')} 分。",
            source_refs=(sources["ML_path"],),
        )
    for label in ("实际扣分", "第三项合计"):
        if label in military:
            military[label] = _attach_reader(military[label], kind="calculation")
    if "实际扣分" in military:
        military["实际扣分"]["reader_how"] = (
            f"普通成本扣分 {military.get('普通成本扣分', {}).get('value')} 与ML扣分 "
            f"{military.get('ML扣分', {}).get('value')} 取较大值 = {military['实际扣分'].get('value')} 分。"
        )
    if "第三项合计" in military:
        a120 = strategic.get("A120", {}).get("value")
        b80 = strategic.get("B80", {}).get("value")
        c50 = military.get("C50", {}).get("value")
        debit = military.get("实际扣分", {}).get("value")
        military["第三项合计"]["reader_how"] = (
            f"A120 {a120} + B80 {b80} + C50 {c50} − 实际扣分 {debit} "
            f"= {military['第三项合计'].get('value')} 分。"
        )
    if military:
        details["military"] = [military[item["label"]] for item in details["military"]]

    fourth = sources["fourth"][fid]
    fourth_axes = {axis["axis"]: axis for axis in fourth.get("axis_results", [])}
    civilization = {item["label"]: item for item in details.get("civilization", [])}
    label_to_axis = {"A国家共同体": "A", "B教育与人才": "B", "C文化知识": "C"}
    civ_names = {"A": "国家共同体与社会整合", "B": "教育可及与人才流动", "C": "知识生产与文化生态"}
    for label, key in label_to_axis.items():
        if label not in civilization:
            continue
        item = civilization[label]
        axis = fourth_axes.get(key, {})
        if item.get("value") == 0:
            summary = f"现有材料复核后，没有满足“{civ_names[key]}”本轴计分门槛的独立文明增量，因此本轴调整为0。"
        else:
            direction = {"POSITIVE": "正向", "NEGATIVE": "负向", "BALANCED": "正负相抵"}.get(axis.get("direction"), "有符号")
            summary = f"正式结算认定本人窗口在“{civ_names[key]}”形成可归责的{direction}净变化。"
        civilization[label] = _attach_reader(
            item, kind="judgment", summary=summary,
            how=f"按本轴影响量级、档内位置和方向换算为 {item.get('value')} 分调整。",
            record=axis,
        )
    if "第四项调整" in civilization:
        values = [civilization[label].get("value") for label in label_to_axis if label in civilization]
        civilization["第四项调整"] = _attach_reader(
            civilization["第四项调整"], kind="calculation",
            how=f"三轴有符号调整相加：{' + '.join(str(v) for v in values)} = {civilization['第四项调整'].get('value')} 分。",
        )
    if civilization:
        details["civilization"] = [civilization[item["label"]] for item in details["civilization"]]

    return details


def detail_ref(ruler_id):
    """Use stable ruler ids as deterministic static shard names."""
    if not ruler_id or any(x in ruler_id for x in ("/", "\\")) or ruler_id in {".", ".."}:
        raise ValueError(f"Unsafe ruler_id for reader detail shard: {ruler_id!r}")
    return f"data/people/{ruler_id}.json"


def axis_summary(axis):
    """Keep only fields needed by overview grade rendering before detail fetch."""
    return pick(axis, [
        "axis_grade", "position", "output_mode", "applicability_status",
        "adjudication_state", "display_point_only",
    ])


def record_summary(record):
    """Project a small, self-sufficient overview row without evidence prose."""
    net = record.get("net")
    impact = record["impact"]
    summary_impact = pick(impact, [
        "identity_label", "public_grade", "impact_nature", "confidence", "reading_start_year",
    ])
    summary_impact["dimensions"] = {
        key: pick(value, ["grade"])
        for key, value in impact.get("dimensions", {}).items()
        if isinstance(value, dict)
    }
    summary = pick(record, [
        "ruler_id", "ruler_name", "polity", "actual_power_window",
        "settlement_readiness", "supplementary",
    ])
    summary["net"] = pick(net, [
        "rank", "total_score", "first_item_status", "first_item_raw_score", "first_item_add_on",
        "second_item_score", "third_item_score", "fourth_item_adjustment",
    ]) if net else None
    summary["impact"] = summary_impact
    summary["axes"] = {code: axis_summary(axis) for code, axis in record.get("axes", {}).items()}
    summary["detail_ref"] = detail_ref(record["ruler_id"])
    summary["detail_loaded"] = False
    return summary


def source_availability(value):
    return {
        ref: (ROOT / source_file(ref)).exists()
        for ref in sorted(local_sources(value))
    }


def detail_payload(record):
    """Full per-person data fetched only when a person or comparison is opened."""
    return {
        "record": record,
        "source_availability": source_availability(record),
    }


def serialized_json(value, *, html_safe=False):
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if html_safe:
        text = text.replace("<", "\\u003c")
    return text


def build(*, check=False, write=True):
    config = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    pool = load_json(ROOT / config["canonical_ruler_pool"]["json"])
    main = [r for r in pool["records"] if r["pool_status"] == "INCLUDED"]
    main_ids = set(index(main))
    scoring = config["scoring_contract"]
    ranking = load_json(ROOT / scoring["composite_ranking_json"])
    net = index(ranking["records"])
    ready = {r["ruler_id"] for r in main if r["settlement_readiness"] == "COMPOSITE_READY"}
    if set(net) != ready:
        raise ValueError("Composite ranking does not match current ready pool")
    second_item_reader_summaries = load_second_item_reader_summaries(ROOT, ready)
    net_reader_sources = load_net_reader_sources(ROOT)
    first_item_public_outcomes = load_first_item_public_outcomes(ROOT)
    impact_config = config["historical_impact_assessment"]
    impact = load_json(ROOT / impact_config["json"])
    history = index(impact["records"])
    if set(history) != main_ids:
        raise ValueError("Historical impact coverage differs from included pool")
    profile = config["profile_assessment"]
    groups = profile["capability_axes"] + profile["independent_profile_axes"]
    if len(groups) != len(set(groups)) or set(groups) != set(profile["axis_order"]):
        raise ValueError("Profile display groups must partition the registered axes")
    axes = {}
    for code in profile["axis_order"]:
        spec = profile["settled_axes"][code]
        rows = index(load_json(ROOT / spec["json"])["records"])
        if set(rows) != main_ids:
            raise ValueError(f"{code}: coverage differs from included pool")
        axes[code] = rows
    axis_fields = ["axis_grade", "position", "radar_value", "output_mode", "confidence",
                   "applicability_status", "not_applicable_reason", "grade_basis", "typical_pattern",
                   "counterpattern", "limitations", "person_type", "score_status", "axis_evidence_level",
                   "adjudication_state", "display_point_only", "formal_status", "no_grade_closure",
                   "position_basis", "applicability_basis", "evidence_assessment_basis",
                   "assessment_basis", "final_capability_review"]
    net_fields = ["rank", "total_score", "first_item_status", "first_item_raw_score", "first_item_add_on",
                  "second_item_score", "third_item_score", "fourth_item_adjustment", "component_details",
                  "weight_sensitivity"]
    records = []
    for person in main:
        rid = person["ruler_id"]
        record = pick(person, ["ruler_id", "ruler_name", "polity", "actual_power_window", "settlement_readiness"])
        projected_net = pick(net[rid], net_fields) if rid in net else None
        if projected_net:
            projected_net["component_details"] = project_net_explanations(
                person,
                net[rid],
                net_reader_sources,
                first_item_public_outcomes,
            )
            reader_summary = second_item_reader_summaries.get(rid)
            if reader_summary:
                projected_net["reader_governance_summary"] = reader_summary
        record.update(net=projected_net,
                      impact=history[rid], axes={code: axis_projection(rows[rid], axis_fields) for code, rows in axes.items()},
                      supplementary=False)
        records.append(record)
    for row in impact.get("supplementary_records", []):
        if row["ruler_id"] in main_ids:
            raise ValueError("Supplementary sample overlaps main pool")
        records.append(dict(ruler_id=row["ruler_id"], ruler_name=row["ruler_name"], polity=row["polity"],
                            actual_power_window=row.get("reference_power_window", ""),
                            settlement_readiness="SUPPLEMENTARY", net=None, axes={}, impact=row, supplementary=True))
    index(records)

    common = dict(main_count=len(main), ranked_count=len(net),
                  weight_sensitivity=ranking.get("weight_sensitivity", {}),
                  supplementary_count=len(records)-len(main), formula=ranking["formula"],
                  capability_axes=profile["capability_axes"], independent_axes=profile["independent_profile_axes"],
                  axis_order=profile["axis_order"],
                  axis_specs={k: pick(v, ["name", "json", "markdown", "contract"]) for k,v in profile["settled_axes"].items()},
                  impact_grades=impact_config["public_grade_order"],
                  impact_dimension_grades=impact_config["dimension_grade_order"],
                  impact_labels=impact["public_label_mapping"],
                  sources=dict(net=scoring["composite_ranking_json"], impact=impact_config["json"],
                               net_reader=scoring["composite_ranking_markdown"], impact_reader=impact_config["markdown"]))

    # Full return value preserves build/test semantics. Only the browser bootstrap is slimmed.
    data = dict(records=records, **common)
    data["source_availability"] = source_availability(data)

    index_data = dict(records=[record_summary(record) for record in records], **common)
    index_data["detail_schema_version"] = "reader-person-detail-v1"
    index_data["source_availability"] = source_availability(common)

    detail_files = {}
    for record in records:
        relative = detail_ref(record["ruler_id"])
        detail_files[Path(relative).name] = serialized_json(detail_payload(record)) + "\n"

    payload = serialized_json(index_data, html_safe=True)
    template = (ROOT / "reader/index.template.html").read_text(encoding="utf-8")
    template = apply_public_copy(template)
    link_effects = (ROOT / "reader/link-effects.css").read_text(encoding="utf-8").strip()
    readability_css = (ROOT / "reader/readability.css").read_text(encoding="utf-8").strip()
    lazy_details = (ROOT / "reader/lazy-details.js").read_text(encoding="utf-8").strip()
    home_interactions = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8").strip()
    readability_js = (ROOT / "reader/readability.js").read_text(encoding="utf-8").strip()
    person_readability_js = (ROOT / "reader/person-readability.js").read_text(encoding="utf-8").strip()
    if "</style>" not in template:
        raise ValueError("Reader template must contain a style block")
    template = template.replace("</style>", f"\n{link_effects}\n{readability_css}\n</style>", 1)
    if "</body>" not in template:
        raise ValueError("Reader template must contain a body close tag")
    template = template.replace(
        "</body>",
        f"<script>\n{lazy_details}\n</script>\n<script>\n{home_interactions}\n</script>\n<script>\n{readability_js}\n</script>\n<script>\n{person_readability_js}\n</script>\n</body>",
        1,
    )
    output = ROOT / "reader/index.html"
    if template.count("__READER_DATA__") != 1:
        raise ValueError("Reader template must contain exactly one data placeholder")
    rendered = template.replace("__READER_DATA__", payload)

    expected_detail_names = set(detail_files)
    actual_detail_names = {p.name for p in DETAILS_DIR.glob("*.json")} if DETAILS_DIR.exists() else set()
    if check:
        if not output.exists() or output.read_bytes() != rendered.encode("utf-8"):
            raise ValueError("Reader is stale; run python reader/build.py")
        if actual_detail_names != expected_detail_names:
            missing = sorted(expected_detail_names - actual_detail_names)
            extra = sorted(actual_detail_names - expected_detail_names)
            raise ValueError(f"Reader detail shards are stale: missing={missing}, extra={extra}")
        for name, content in detail_files.items():
            if (DETAILS_DIR / name).read_bytes() != content.encode("utf-8"):
                raise ValueError(f"Reader detail shard is stale: {name}")
    elif write:
        output.write_text(rendered, encoding="utf-8", newline="\n")
        DETAILS_DIR.mkdir(parents=True, exist_ok=True)
        for stale in DETAILS_DIR.glob("*.json"):
            if stale.name not in expected_detail_names:
                stale.unlink()
        for name, content in detail_files.items():
            (DETAILS_DIR / name).write_text(content, encoding="utf-8", newline="\n")

    index_kib = len(rendered.encode("utf-8")) / 1024
    detail_mib = sum(len(content.encode("utf-8")) for content in detail_files.values()) / (1024 * 1024)
    print(
        f"Reader built: main={len(main)}, ranked={len(net)}, supplementary={len(records)-len(main)}, "
        f"index={index_kib:.0f}KiB, details={len(detail_files)} files/{detail_mib:.1f}MiB"
    )
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check current data/template/detail parity without writing")
    build(check=parser.parse_args().check)
