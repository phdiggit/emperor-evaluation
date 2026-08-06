from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = "chronicle-source-summary-v1"
EVENT_TYPES = {"WAR", "FISCAL", "WORKS", "POLITICAL", "CONTEXT"}
WAR_DETAIL_FIELDS = (
    "parties_and_chain",
    "personnel_by_side",
    "threat_control_by_side",
    "mobilization_transport",
    "assets",
    "region_production",
    "security_control",
    "acquisitions",
    "ruler_window",
)
_ANCHOR_RE = re.compile(r"^\[(SRC-[A-Z0-9-]+-P\d{4})\]$")
_EVENT_ID_RE = re.compile(r"^EVT-(\d{3})-(\d{3})$")
_ELLIPSIS = ("…", "……")


class SummaryValidationError(ValueError):
    """Raised when a web-authored source summary is not mechanically usable."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SummaryValidationError(f"无法读取 JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise SummaryValidationError("总结顶层必须是 JSON object")
    return value


def _front_matter(source_text: str) -> dict[str, str]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", source_text, re.DOTALL)
    if not match:
        raise SummaryValidationError("原文缺少 YAML front matter")
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def _paragraphs(source_text: str) -> dict[str, str]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in source_text.splitlines():
        match = _ANCHOR_RE.match(line)
        if match:
            current = match.group(1)
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return {anchor: "\n".join(lines) for anchor, lines in result.items()}


def _need(mapping: Mapping[str, Any], key: str, path: str, errors: list[str]) -> Any:
    if key not in mapping:
        errors.append(f"{path}.{key}: 缺少字段")
        return None
    return mapping[key]


def _nonempty_string(value: Any, path: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: 必须是非空字符串")
        return None
    return value.strip()


def _require_mapping(value: Any, path: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{path}: 必须是 object")
        return None
    return value


def _validate_source(
    source: Mapping[str, Any], metadata: Mapping[str, str], paragraphs: Mapping[str, str], errors: list[str]
) -> None:
    for key in ("work_title", "volume", "source_unit_id", "source_url", "revision_ref", "raw_sha256"):
        value = _nonempty_string(_need(source, key, "source", errors), f"source.{key}", errors)
        if value is not None and metadata.get(key) != value:
            errors.append(f"source.{key}: 与原文 front matter 不一致")
    paragraph_count = _need(source, "paragraph_count", "source", errors)
    if not isinstance(paragraph_count, int) or paragraph_count != len(paragraphs):
        errors.append("source.paragraph_count: 必须等于原文锚点数")
    if _need(source, "complete_linear_read", "source", errors) is not True:
        errors.append("source.complete_linear_read: 必须为 true")
    read_range = _require_mapping(_need(source, "read_range", "source", errors), "source.read_range", errors)
    if read_range is not None:
        first = _nonempty_string(_need(read_range, "first_anchor", "source.read_range", errors), "source.read_range.first_anchor", errors)
        last = _nonempty_string(_need(read_range, "last_anchor", "source.read_range", errors), "source.read_range.last_anchor", errors)
        anchors = list(paragraphs)
        if first is not None and anchors and first != anchors[0]:
            errors.append("source.read_range.first_anchor: 不是原文首锚点")
        if last is not None and anchors and last != anchors[-1]:
            errors.append("source.read_range.last_anchor: 不是原文末锚点")
    for key in ("previous_boundary_consumed", "next_boundary", "extraction_limits"):
        _nonempty_string(_need(source, key, "source", errors), f"source.{key}", errors)


def _validate_refs(
    refs: Any, path: str, paragraphs: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(refs, list) or not refs:
        errors.append(f"{path}: 必须是非空数组")
        return
    for index, ref in enumerate(refs):
        ref_path = f"{path}[{index}]"
        mapping = _require_mapping(ref, ref_path, errors)
        if mapping is None:
            continue
        anchor = _nonempty_string(_need(mapping, "anchor", ref_path, errors), f"{ref_path}.anchor", errors)
        quote = _nonempty_string(_need(mapping, "quote", ref_path, errors), f"{ref_path}.quote", errors)
        if anchor is None or quote is None:
            continue
        if anchor not in paragraphs:
            errors.append(f"{ref_path}.anchor: 不属于本卷原文")
        if any(marker in quote for marker in _ELLIPSIS):
            errors.append(f"{ref_path}.quote: 不得含省略号")
        if len(quote) > 25:
            errors.append(f"{ref_path}.quote: 超过 25 字限制")
        if anchor in paragraphs and quote not in paragraphs[anchor]:
            errors.append(f"{ref_path}.quote: 不是该锚点的连续原文")


def _validate_war_details(value: Any, path: str, errors: list[str]) -> None:
    details = _require_mapping(value, path, errors)
    if details is None:
        return
    for key in WAR_DETAIL_FIELDS:
        raw = _need(details, key, path, errors)
        if key in {"personnel_by_side", "threat_control_by_side"}:
            if not isinstance(raw, Mapping) or not raw:
                errors.append(f"{path}.{key}: 必须是非空 object，键为已命名阵营")
                continue
            for side, fact in raw.items():
                if side in {"己方", "敌方"} or not isinstance(side, str) or not side.strip():
                    errors.append(f"{path}.{key}: 不得使用未定义的己方/敌方")
                _nonempty_string(fact, f"{path}.{key}.{side}", errors)
        else:
            _nonempty_string(raw, f"{path}.{key}", errors)
    parties = details.get("parties_and_chain")
    if isinstance(parties, str) and ("己方" in parties or "敌方" in parties):
        errors.append(f"{path}.parties_and_chain: 必须写出实际阵营名称")


def validate_summary(summary: Mapping[str, Any], source_text: str) -> dict[str, Any]:
    """Validate web JSON against fixed original text and return a machine report."""

    errors: list[str] = []
    metadata = _front_matter(source_text)
    paragraphs = _paragraphs(source_text)
    if summary.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: 必须为 {SCHEMA_VERSION}")
    source = _require_mapping(_need(summary, "source", "$", errors), "source", errors)
    if source is not None:
        _validate_source(source, metadata, paragraphs, errors)

    events_value = _need(summary, "events", "$", errors)
    event_ids: set[str] = set()
    event_count_by_type = {event_type: 0 for event_type in sorted(EVENT_TYPES)}
    if not isinstance(events_value, list) or not events_value:
        errors.append("events: 必须是非空数组")
        events: list[Any] = []
    else:
        events = events_value
    source_volume = metadata.get("volume", "")
    for index, event_value in enumerate(events):
        path = f"events[{index}]"
        event = _require_mapping(event_value, path, errors)
        if event is None:
            continue
        event_id = _nonempty_string(_need(event, "event_id", path, errors), f"{path}.event_id", errors)
        if event_id is not None:
            match = _EVENT_ID_RE.match(event_id)
            if not match or match.group(1) != source_volume:
                errors.append(f"{path}.event_id: 必须为本卷 EVT-<卷号>-<序号>")
            if event_id in event_ids:
                errors.append(f"{path}.event_id: 重复")
            event_ids.add(event_id)
        event_type = _nonempty_string(_need(event, "type", path, errors), f"{path}.type", errors)
        if event_type not in EVENT_TYPES:
            errors.append(f"{path}.type: 必须是 {sorted(EVENT_TYPES)} 之一")
        elif event_type is not None:
            event_count_by_type[event_type] += 1
        for key in ("title", "time_location", "action", "result", "impact", "relations", "uncertainty", "fiscal_works_note"):
            _nonempty_string(_need(event, key, path, errors), f"{path}.{key}", errors)
        _validate_refs(_need(event, "source_refs", path, errors), f"{path}.source_refs", paragraphs, errors)
        details = _need(event, "war_details", path, errors)
        if event_type == "WAR":
            _validate_war_details(details, f"{path}.war_details", errors)
        elif details is not None:
            errors.append(f"{path}.war_details: 非 WAR 必须为 null")

    boundaries_value = _need(summary, "boundaries", "$", errors)
    if not isinstance(boundaries_value, list):
        errors.append("boundaries: 必须是数组")
    else:
        for index, item in enumerate(boundaries_value):
            path = f"boundaries[{index}]"
            boundary = _require_mapping(item, path, errors)
            if boundary is None:
                continue
            event_id = _nonempty_string(_need(boundary, "event_id", path, errors), f"{path}.event_id", errors)
            if event_id is not None and event_id not in event_ids:
                errors.append(f"{path}.event_id: 不存在于 events")
            status = _nonempty_string(_need(boundary, "status", path, errors), f"{path}.status", errors)
            if status not in {"closed", "open", "unknown"}:
                errors.append(f"{path}.status: 必须为 closed/open/unknown")
            _nonempty_string(_need(boundary, "next_check", path, errors), f"{path}.next_check", errors)
            anchor = _nonempty_string(_need(boundary, "last_anchor", path, errors), f"{path}.last_anchor", errors)
            if anchor is not None and anchor not in paragraphs:
                errors.append(f"{path}.last_anchor: 不属于本卷")

    coverage = _require_mapping(_need(summary, "coverage", "$", errors), "coverage", errors)
    if coverage is not None:
        for key in ("sensitive_anchors_reviewed", "fiscal_works_reviewed"):
            if _need(coverage, key, "coverage", errors) is not True:
                errors.append(f"coverage.{key}: 必须为 true")
        for key in ("unregistered_substantive_actions", "unverifiable_quotes"):
            _nonempty_string(_need(coverage, key, "coverage", errors), f"coverage.{key}", errors)

    report = {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "errors": errors,
        "source_anchor_count": len(paragraphs),
        "event_count": len(events),
        "event_count_by_type": event_count_by_type,
    }
    if errors:
        raise SummaryValidationError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _markdown_escape(value: str) -> str:
    return value.replace("\n", "<br>").replace("|", "\\|")


def render_markdown(summary: Mapping[str, Any]) -> str:
    source = summary["source"]
    lines = [
        f"# {source['work_title']} 卷{source['volume']}原文通读总结",
        "",
        "## 0. 原文身份与覆盖回执",
        "",
    ]
    for key in (
        "source_unit_id", "source_url", "revision_ref", "raw_sha256", "read_range",
        "paragraph_count", "complete_linear_read", "previous_boundary_consumed", "next_boundary", "extraction_limits",
    ):
        value = source[key]
        if key == "read_range":
            value = f"{value['first_anchor']} 至 {value['last_anchor']}"
        elif key == "complete_linear_read":
            value = "yes" if value else "no"
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 1. 时间顺序总索引", "", "| 顺序 | 时间 | 事件 ID | 类型 | 一句话中性事实 | 锚点 |", "| --- | --- | --- | --- | --- | --- |"])
    for index, event in enumerate(summary["events"], start=1):
        anchors = ", ".join(ref["anchor"].rsplit("-", 1)[-1] for ref in event["source_refs"])
        lines.append(f"| {index:03d} | {_markdown_escape(event['time_location'])} | {event['event_id']} | {event['type']} | {_markdown_escape(event['title'])} | {anchors} |")
    lines.extend(["", "## 2. 事件事实", ""])
    for event in summary["events"]:
        lines.extend([
            f"### {event['event_id']}｜{event['title']}", "",
            f"- 类型：`{event['type']}`",
            f"- 时间与地点：{event['time_location']}",
            f"- 主体与实际行动：{event['action']}",
            f"- 直接结果：{event['result']}",
            f"- 影响对象：{event['impact']}",
            "- 原文锚点与短引：" + "；".join(f"`{ref['anchor']}`：‘{ref['quote']}’" for ref in event["source_refs"]),
            f"- 前后关系：{event['relations']}",
            f"- 不确定性与未载：{event['uncertainty']}",
        ])
        if event["fiscal_works_note"] != "无":
            lines.append(f"- 财政民生/工程归属：{event['fiscal_works_note']}")
        if event["type"] == "WAR":
            details = event["war_details"]
            lines.extend(["", "#### 武装行动线索（仅类型为 `WAR` 时必填）", ""])
            labels = {
                "parties_and_chain": "参战方、目标、指挥链",
                "mobilization_transport": "动员、服役、运输",
                "assets": "军资、财政资产",
                "region_production": "地区与生产体系",
                "security_control": "安全状态与控制权",
                "acquisitions": "当期获得物",
                "ruler_window": "当时统治/继承/政权变化线索",
            }
            lines.append(f"- {labels['parties_and_chain']}：{details['parties_and_chain']}")
            lines.append("- 各方人员损害：" + "；".join(f"{side}：{fact}" for side, fact in details["personnel_by_side"].items()))
            lines.append("- 各方威胁与控制变化：" + "；".join(f"{side}：{fact}" for side, fact in details["threat_control_by_side"].items()))
            for key in ("mobilization_transport", "assets", "region_production", "security_control", "acquisitions", "ruler_window"):
                lines.append(f"- {labels[key]}：{details[key]}")
        lines.append("")
    lines.extend(["## 3. 卷末连续事件与跨卷提示", "", "| 本卷事件 ID | 状态 | 下一步只需核对什么 | 末锚点 |", "| --- | --- | --- | --- |"])
    for boundary in summary["boundaries"]:
        lines.append(f"| {boundary['event_id']} | {boundary['status']} | {_markdown_escape(boundary['next_check'])} | {boundary['last_anchor']} |")
    coverage = summary["coverage"]
    lines.extend(["", "## 4. 覆盖自检", "", "- 首尾锚点已读：yes", "- 敏感锚点已复查：yes" if coverage["sensitive_anchors_reviewed"] else "- 敏感锚点已复查：no", "- 已实施的 FISCAL/WORKS 行动已复查：yes" if coverage["fiscal_works_reviewed"] else "- 已实施的 FISCAL/WORKS 行动已复查：no", f"- 未被纳入事件的实质行动：{coverage['unregistered_substantive_actions']}", f"- 不可核验引用或疑似误读：{coverage['unverifiable_quotes']}", ""])
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验并渲染编年体逐卷结构化总结")
    parser.add_argument("command", choices=("validate", "render"))
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "render" and args.output is None:
        raise SystemExit("render 需要 --output")
    summary = _load_json(args.summary)
    source_text = args.source.read_text(encoding="utf-8")
    try:
        report = validate_summary(summary, source_text)
    except SummaryValidationError as error:
        print(str(error))
        return 1
    if args.command == "render":
        args.output.write_text(render_markdown(summary), encoding="utf-8", newline="\n")
        report["output"] = str(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
