"""Read and validate current M5 decisions; never infer grades from evidence text."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import M5_SHARED_FIELDS, load_json
from emperor_v4.evaluation.profile_registry import profile_axis_entry


_SHARED_FIELDS_VERSION = "same-as-v1"
_COMMON_SCOPE_REASONS = (
    "只取多责任中心的任务、权责资源、协调监督与替补过程；C3个人识配、C4长期结构、B1运行结果不转档。",
    "仅消费本人任务分派、权责资源、协调监督和接续；识配、制度创制、外交交换、作战成败与惩罚伦理分别剥离。",
)
SCOPE_GUIDE = (
    "组织执行看本人如何分派多个责任中心的任务、配置权责和资源、协调监督，以及发生故障时怎样安排替补和接续。"
    "识人授权、长期制度设计、外交交换和惩罚伦理各按所属项目判断。治理运行与作战结果用于核验执行，组织档位依据本人编排过程。"
)


def uses_shared_scope(parent: dict[str, Any]) -> bool:
    return parent.get("secondary_projection_reason") in _COMMON_SCOPE_REASONS


def compact_shared_fields(shard: dict[str, Any]) -> None:
    """Replace exact copies in the private shard records before writing."""
    changed = False
    for row in shard["collections"].get("records", {}).get("records", []):
        scope = row.get("search_scope")
        if isinstance(scope, list) and scope == row.get("source_refs"):
            row["search_scope"] = {"same_as": "source_refs"}
            changed = True
        parents = row.get("parent_chains", [])
        packed = [
            {**parent, "basis": {"same_as": "process_narrative"}}
            if isinstance(parent.get("basis"), str) and parent["basis"] == parent.get("process_narrative")
            else parent
            for parent in parents
        ]
        if packed != parents:
            row["parent_chains"] = packed
            changed = True
    if changed:
        shard[M5_SHARED_FIELDS] = _SHARED_FIELDS_VERSION


def _restore_shared_field(record: dict[str, Any], field: str, source: str, kind: type, context: str) -> None:
    value = record.get(field)
    if not isinstance(value, dict) or "same_as" not in value:
        return
    original = record.get(source)
    if value != {"same_as": source} or not isinstance(original, kind):
        raise ValueError(f"M5字段引用无效: {context}/{field}")
    record[field] = deepcopy(original)


def expand_shared_fields(shard: dict[str, Any]) -> dict[str, Any]:
    """Restore the original fields in a freshly loaded M5 shard."""
    records = shard.get("collections", {}).get("records", {}).get("records")
    if shard.pop(M5_SHARED_FIELDS) != _SHARED_FIELDS_VERSION or not isinstance(records, list):
        raise ValueError("M5字段引用分片格式无效")
    for row in records:
        _restore_shared_field(row, "search_scope", "source_refs", list, row.get("ruler_id", ""))
        for parent in row.get("parent_chains", []):
            _restore_shared_field(parent, "basis", "process_narrative", str, parent.get("parent_id", ""))
    return shard


def validate_text_fields(row: dict[str, Any]) -> None:
    """Check field responsibilities without interpreting prose or choosing a grade."""
    rid = row.get("ruler_id", "unknown")
    fields = ("typical_pattern", "counterpattern", "grade_basis", "position_basis")
    for key in fields:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"M5裁决文本缺失: {rid}/{key}")
    limitations = row.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        raise ValueError(f"M5材料限制缺失: {rid}")
    if any(not isinstance(value, str) or not value.strip() for value in limitations):
        raise ValueError(f"M5材料限制必须为非空文本列表: {rid}")


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# M5 组织驾驭与执行编排正式结算", "",
        "> 正式JSON是唯一裁决真源；本页为同值阅读视图。", "",
        "## 阅读说明", "",
        "全池表按雷达值和稳定人物ID展示。逐人条目列出代表过程、裁档理由与限制。", "",
        '<a id="m5-scope-guide"></a>', "",
        "### 组织执行的评价范围", "", SCOPE_GUIDE, "",
        "## 全池结算表", "",
        "| 人物 | 政权 | 档位 | 雷达值 | 证据 | 置信度 |", "|---|---|---|---:|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ruler_name']} | {row['polity']} | {row['axis_grade']}-{row['position']} | {row['radar_value']} | {row['axis_evidence_level']} | {row['confidence']} |")
    lines.extend(["", "## 逐人裁决依据", ""])
    for row in payload["records"]:
        selected = set(row["representative_parent_ids"])
        parents = [parent for parent in row["parent_chains"] if parent["parent_id"] in selected]
        pattern = row["typical_pattern"]
        pattern_in_process = any(
            pattern.strip() in [line.strip() for line in parent["process_narrative"].splitlines()]
            for parent in parents
        )
        attributions = {parent["attribution_basis"] for parent in parents}
        shared_attribution = len(parents) > 1 and len(attributions) == 1
        lines.extend([
            f"### {row['ruler_name']}（{row['ruler_id']}）", "",
            f"- **结算**：{row['axis_grade']}-{row['position']} / {row['radar_value']}；{row['axis_evidence_level']} / {row['confidence']} / {row['output_mode']} / {row['score_status']}。",
            *([f"- **主模式**：{pattern}"] if not pattern_in_process else []),
            "- **裁档理由**：", "",
            row["grade_basis"], "",
        ])
        if row["position_basis"] != row["grade_basis"]:
            lines.extend(["**档内限制：**", "", row["position_basis"], ""])
        lines.extend(["**反例与判断边界：**", "", row["counterpattern"], ""])
        lines.extend(["**限制**：", "", "\n\n".join(row["limitations"]), ""])
        lines.extend(["**正式过程与边界：**", ""])
        for parent in parents:
            lines.extend([f"#### {parent['title']}", "",
                          "\n\n".join(line.strip() for line in parent['process_narrative'].splitlines() if line.strip()), ""])
            if not shared_attribution:
                lines.append(f"- **本人归责**：{parent['attribution_basis']}")
            if not uses_shared_scope(parent):
                lines.append(f"- **跨轴边界**：{parent['secondary_projection_reason']}")
            lines.append("")
        if shared_attribution:
            lines.extend([f"- **以上代表过程的共同归责**：{parents[0]['attribution_basis']}", ""])
        if any(uses_shared_scope(parent) for parent in parents):
            lines.extend(["[查看组织执行的通用评价范围](#m5-scope-guide)", ""])
        lines.extend(["", "**来源与定位：**", ""])
        for ref in row["source_refs"]:
            lines.append(f"- `{ref}`")
        for description in row["historical_source_descriptions"]:
            lines.extend(["", description])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def verify(root: Path) -> dict[str, Any]:
    from emperor_v4.evaluation.maintenance import verify_profile_current
    from emperor_v4.evaluation.profile_record_integrity import verify_current_records

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
    verify_current_records(payload)
    if payload["record_count"] != len(records):
        raise ValueError("M5记录数声明不一致")
    if records != sorted(records, key=lambda r: (-r["radar_value"], r["ruler_id"])):
        raise ValueError("M5展示顺序不符合合同")
    cache: dict[str, set[str]] = {}
    parent_ids: set[str] = set()
    for row in records:
        rid = row["ruler_id"]
        validate_text_fields(row)
        person = pool[rid]
        for key in ("ruler_name", "polity"):
            if row[key] != person[key]:
                raise ValueError(f"M5身份不一致: {rid}/{key}")
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
        own_ids = {p["parent_id"] for p in row["parent_chains"]}
        if len(own_ids) != len(row["parent_chains"]) or parent_ids & own_ids:
            raise ValueError(f"M5父链ID重复: {rid}")
        parent_ids.update(own_ids)
        if not set(row["representative_parent_ids"]) <= own_ids:
            raise ValueError(f"M5代表父链不存在: {rid}")
        for parent in row["parent_chains"]:
            if not all(parent.get(k) for k in ("title", "process_narrative", "attribution_basis", "source_refs", "secondary_projection_reason")):
                raise ValueError(f"M5父链不完整: {parent['parent_id']}")
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
