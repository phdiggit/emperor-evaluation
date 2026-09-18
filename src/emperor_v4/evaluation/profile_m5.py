"""Read and validate current M5 decisions; never infer grades from evidence text."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_registry import profile_axis_entry


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# M5 组织驾驭与执行编排正式结算", "",
        "> 正式JSON是唯一裁决真源；本页为同值阅读视图。独立于五项评分，不设画像总分或轴内排名。", "",
        "## 阅读说明", "",
        "C4评价长期组织结构，M5评价具体任务中的多中心分工、协调监督与替补。以下按雷达值及稳定人物ID展示，不设名次；逐人列出裁档依据、事实限制和代表过程。", "",
        "## 全池结算表", "",
        "| 人物 | 政权 | 档位 | 雷达值 | 证据 | 置信度 |", "|---|---|---|---:|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ruler_name']} | {row['polity']} | {row['axis_grade']}-{row['position']} | {row['radar_value']} | {row['axis_evidence_level']} | {row['confidence']} |")
    lines.extend(["", "## 逐人裁决依据", ""])
    for row in payload["records"]:
        lines.extend([
            f"### {row['ruler_name']}（{row['ruler_id']}）", "",
            f"- **结算**：{row['axis_grade']}-{row['position']} / {row['radar_value']}；{row['axis_evidence_level']} / {row['confidence']} / {row['output_mode']} / {row['score_status']}。",
            f"- **实际权力窗口**：{row['actual_power_window']}。",
            f"- **主模式**：{row['typical_pattern']}",
            "- **裁档理由**：", "",
            row["grade_basis"], "",
        ])
        if row["position_basis"] != row["grade_basis"]:
            lines.extend(["**档内限制：**", "", row["position_basis"], ""])
        lines.extend(["**限制**：", "", "\n\n".join(row["limitations"]), ""])
        lines.extend(["**代表过程（节选）：**", ""])
        selected = set(row["representative_parent_ids"])
        for parent in row["parent_chains"]:
            if parent["parent_id"] in selected:
                lines.extend([f"- **{parent['title']}**：{parent['process_narrative'].splitlines()[0]}"])
        lines.extend(["", "**来源与定位：**", ""])
        for ref in row["source_refs"]:
            lines.append(f"- `{ref}`")
        for description in row["historical_source_descriptions"]:
            lines.extend(["", description])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def verify(root: Path) -> dict[str, Any]:
    from emperor_v4.evaluation.maintenance import verify_profile_current

    entry = profile_axis_entry("M5")
    path = root / entry["json"]
    payload = load_json(path)
    if payload["schema_version"] != entry["payload_schema_version"]:
        raise ValueError("M5 schema与注册不一致")
    if payload["contract_version"] != entry["axis_contract_version"]:
        raise ValueError("M5合同版本与注册不一致")
    if any(payload[key] for key in ("profile_total_enabled", "profile_ranking_enabled", "composite_ranking_write", "database_write")):
        raise ValueError("M5不得生成总分、排名或写入综合榜/数据库")
    pool = {r["ruler_id"]: r for r in load_json(root / "config/common/canonical-ruler-pool.json")["records"] if r["pool_status"] == "INCLUDED"}
    records = payload["records"]
    if payload["record_count"] != len(records):
        raise ValueError("M5记录数声明不一致")
    if records != sorted(records, key=lambda r: (-r["radar_value"], r["ruler_id"])):
        raise ValueError("M5展示顺序不符合合同")
    cache: dict[str, set[str]] = {}
    parent_ids: set[str] = set()
    for row in records:
        rid = row["ruler_id"]
        person = pool[rid]
        for key in ("ruler_name", "polity", "actual_power_window"):
            if row[key] != person[key]:
                raise ValueError(f"M5身份/窗口不一致: {rid}/{key}")
        if row["task_code"] != f"PROFILE-M5-{rid}" or row["axis_code"] != "M5":
            raise ValueError(f"M5任务ID不一致: {rid}")
        if row["axis_evidence_level"] not in {"E1", "E2", "E3"} or row["score_status"] not in {"FINAL", "EVIDENCE_LIMITED"}:
            raise ValueError(f"M5证据或正式状态未闭合: {rid}")
        expected_mode = {"HIGH": "FULL_GRADE", "MEDIUM": "BOUNDED_PROFILE", "LOW": "EPISODE_TAG"}
        if row["output_mode"] != expected_mode.get(row["confidence"]):
            raise ValueError(f"M5置信度/输出模式不一致: {rid}")
        for key in ("source_refs", "historical_source_descriptions", "parent_chains", "limitations", "axis_relevance_check", "applicability"):
            if not row.get(key):
                raise ValueError(f"M5必要依据缺失: {rid}/{key}")
        grading_text = "\n".join([
            str(row.get("grade_basis") or ""),
            str(row.get("position_basis") or ""),
            *[str(value) for value in row.get("limitations") or []],
        ])
        anti_gate = re.compile(
            r"(?:不再参与升降档|不再作为.{0,16}(?:升降档|准入)|不作为.{0,16}(?:升降档|准入)|"
            r"本身不作(?:为)?.{0,12}(?:升降档|准入)|不以.{0,24}为前置条件)"
        )
        forbidden_window_gate_patterns = (
            r"(?:短|长|极短|太短|较短|偏短)窗口",
            r"(?:窗口|亲政|在位|实际统治|摄政|掌权|主政).{0,12}(?:太短|极短|较短|偏短|只有|仅有|不足|足够长)",
            r"(?:观察窗口|统治窗口|权力窗口).{0,8}(?:更长|超过|足够)",
            r"(?:实际统治|亲政|在位|摄政|掌权|主政).{0,8}(?:仅|只有).{0,6}[0-9一二三四五六七八九十百]+年",
            r"(?:[0-9一二三四五六七八九十百]+|二十余|三十余|四十余|五十余)年.{0,18}(?:足以|稳居|稳定|封顶|阻断|限制|不进|不能|取G|加权)",
            r"(?:持续时间|观察时长|统治时长).{0,10}(?:长|短|足|不足)",
        )
        grading_sentences = [
            sentence.strip()
            for sentence in re.split(r"[。；\n]+", grading_text)
            if sentence.strip()
        ]
        if any(
            not anti_gate.search(sentence)
            and any(re.search(pattern, sentence) for pattern in forbidden_window_gate_patterns)
            for sentence in grading_sentences
        ):
            raise ValueError(f"M5裁档不得以人物时间窗口长度为门: {rid}")
        applicability_text = str(row["applicability"].get("basis") or "")
        forbidden_scope_patterns = (
            r"适用。.{0,40}(?:实际最高权力窗口|最高权力窗口|亲政窗口)",
            r"适用。.{0,40}(?:严格只看|只计算|只计).{0,24}(?:亲政|在位|实际权力|最高权力)",
            r"适用。.{0,40}以.{0,24}亲政窗口为主",
            r"适用。.{0,40}严格按.{0,24}亲政窗口",
        )
        if any(re.search(pattern, applicability_text) for pattern in forbidden_scope_patterns):
            raise ValueError(f"M5证据准入不得由最高身份或时间窗口切死: {rid}")
        own_ids = {p["parent_id"] for p in row["parent_chains"]}
        if len(own_ids) != len(row["parent_chains"]) or parent_ids & own_ids:
            raise ValueError(f"M5父链ID重复: {rid}")
        parent_ids.update(own_ids)
        if not set(row["representative_parent_ids"]) <= own_ids:
            raise ValueError(f"M5代表父链不存在: {rid}")
        for parent in row["parent_chains"]:
            if not all(parent.get(k) for k in ("title", "process_narrative", "attribution_basis", "source_refs", "secondary_projection_reason")):
                raise ValueError(f"M5父链不完整: {parent['parent_id']}")
            attribution_text = str(parent["attribution_basis"])
            if any(re.search(pattern, attribution_text) for pattern in forbidden_scope_patterns):
                raise ValueError(f"M5父链归责不得由最高身份或时间窗口切死: {parent['parent_id']}")
            if not set(parent["source_refs"]) <= set(row["source_refs"]):
                raise ValueError(f"M5父链来源不在完整集合: {rid}")
        for ref in row["source_refs"]:
            source_path, sep, anchor = ref.partition("#ruler_id=")
            if not sep or anchor != rid:
                raise ValueError(f"M5来源归人错误: {ref}")
            resolved = (root / source_path).resolve()
            if not resolved.is_relative_to(root.resolve()):
                raise ValueError(f"M5来源越界: {ref}")
            if source_path not in cache:
                cache[source_path] = {r["ruler_id"] for r in load_json(resolved)["records"]}
            if rid not in cache[source_path]:
                raise ValueError(f"M5来源人物不存在: {ref}")
    common = verify_profile_current(root, "M5")
    return {**common, "validation_scope": "CURRENT_M5_IDENTITY_PROJECTION_LINEAGE_AND_READER_CONTRACTS", "parent_count": len(parent_ids), "source_entry_count": len(cache)}
