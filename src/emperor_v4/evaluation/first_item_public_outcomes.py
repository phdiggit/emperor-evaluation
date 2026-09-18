"""Load and validate the formal public-outcome companion for first-item A."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


PUBLIC_OUTCOME_PATH = Path(
    "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/"
    "01-第一项A统一主链客观贡献正式公开成果.json"
)
SOURCE_MARKDOWN_PATH = Path(
    "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/"
    "01-第一项A统一主链客观贡献正式结算.md"
)
PUBLIC_OUTCOME_SCHEMA = "first-item-a-public-outcome-v1"
PUBLIC_FIELDS = (
    "public_outcome_basis",
    "public_scope",
    "public_boundary",
)
PUBLIC_RECORD_FIELDS = (*PUBLIC_FIELDS, "public_project")
PUBLIC_NAME_ALIASES = {
    "完颜晟": "完颜吴乞买",
}

_PERSON_HEADING = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)
_BULLET = re.compile(r"^-\s+\*\*(.+?)\**[：:]\s*(.*)$")
_SHARE_PERCENT = re.compile(r"全国核心统一尺度的\s*(\d+(?:\.\d+)?)%")
_SHARE_CREDIT = re.compile(r"(?:有效控制信用|个人分得)\s*(?:为|是)?\s*(\d+(?:\.\d+)?)")
_FORBIDDEN_PUBLIC_TEXT = re.compile(
    r"(?:项目池|控制信用|有效控制信用|个人分得|分账|倒算|回填|"
    r"旧版本|重审|复裁|审计|门禁|内部指标|正式代入|档位|折算|"
    r"(?:^|[；。])\s*A(?:项)?(?:[；。]|$)|"
    r"reader[- ]?(?:only|层)?|public_outcome)",
    re.IGNORECASE,
)


def _parse_source_sections(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    matches = list(_PERSON_HEADING.finditer(text))
    result: dict[str, dict[str, str]] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        if name in result:
            raise ValueError(f"第一项A正式来源人物重复：{name}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        fields: dict[str, str] = {}
        for line in text[match.end():end].splitlines():
            bullet = _BULLET.match(line)
            if not bullet:
                continue
            key = bullet.group(1).strip()
            fields[key] = bullet.group(2).replace("**", "").replace("`", "").strip()
        result[name] = fields
    return result


def _share_percent(fields: Mapping[str, str]) -> float:
    text = fields.get("本人取得/归属成果") or fields.get("取得/恢复成果") or ""
    match = _SHARE_PERCENT.search(text)
    if match:
        return round(float(match.group(1)), 1)
    match = _SHARE_CREDIT.search(text)
    if match:
        return round(float(match.group(1)) / 10, 1)
    raise ValueError("第一项A正式来源缺少可投影的成果占比")


def _public_name(name: str) -> str:
    return PUBLIC_NAME_ALIASES.get(name, name)


def _validate_public_text(name: str, field: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"第一项A公开成果字段必须是文字：{name}/{field}")
    text = re.sub(r"\s+", " ", value).strip()
    if not text or len(text) < 8 or len(text) > 240:
        raise ValueError(f"第一项A公开成果字段长度不合要求：{name}/{field}")
    if "\n" in value or "\r" in value or "`" in value or "[" in value or "]" in value:
        raise ValueError(f"第一项A公开成果字段不得带格式标记：{name}/{field}")
    if _FORBIDDEN_PUBLIC_TEXT.search(text):
        raise ValueError(f"第一项A公开成果字段含内部结算术语：{name}/{field}")
    return text


def load_first_item_public_outcomes(
    workspace_root: Path,
    *,
    expected_names: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load public prose and prove that it covers the current formal A source."""

    source_path = workspace_root / SOURCE_MARKDOWN_PATH
    if not source_path.is_file():
        raise ValueError(f"第一项A公开成果来源缺失：{SOURCE_MARKDOWN_PATH.as_posix()}")
    source_sections = _parse_source_sections(source_path)
    if not source_sections:
        raise ValueError("第一项A正式来源没有人物条目")

    path = workspace_root / PUBLIC_OUTCOME_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"第一项A公开成果伴随数据缺失：{PUBLIC_OUTCOME_PATH.as_posix()}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != PUBLIC_OUTCOME_SCHEMA:
        raise ValueError("第一项A公开成果伴随数据schema错误")
    if tuple(payload.get("fields") or ()) != PUBLIC_RECORD_FIELDS:
        raise ValueError("第一项A公开成果字段登记不一致")
    source_ref = str(payload.get("source_markdown") or "").replace("\\", "/")
    if source_ref != SOURCE_MARKDOWN_PATH.as_posix():
        raise ValueError("第一项A公开成果伴随数据未登记当前正式A来源")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("第一项A公开成果records为空或类型错误")
    if payload.get("record_count") != len(records):
        raise ValueError("第一项A公开成果record_count与records长度不一致")

    by_name: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("第一项A公开成果record必须是对象")
        name = str(record.get("ruler_name") or "").strip()
        if not name or name in by_name:
            raise ValueError(f"第一项A公开成果人物缺失或重复：{name or '<empty>'}")
        if name not in source_sections:
            raise ValueError(f"第一项A公开成果人物不在正式A来源：{name}")
        result: dict[str, Any] = {
            field: _validate_public_text(name, field, record.get(field))
            for field in PUBLIC_FIELDS
        }
        project = record.get("public_project")
        if project is not None:
            if not isinstance(project, str) or not 2 <= len(project.strip()) <= 80:
                raise ValueError(f"第一项A共同项目公开标签长度不合要求：{name}")
            project = _validate_public_text(name, "public_project", f"共同项目：{project}")
            project = project.removeprefix("共同项目：").strip()
        result["public_project"] = project
        result["public_share_percent"] = _share_percent(source_sections[name])
        by_name[name] = result

    source_names = set(source_sections)
    if expected_names is None:
        expected = source_names
    else:
        expected = {_public_name(name) for name in expected_names}
    if set(by_name) != expected:
        raise ValueError(
            "第一项A公开成果覆盖不一致："
            f"missing={sorted(expected - set(by_name))}, extra={sorted(set(by_name) - expected)}"
        )

    project_groups: dict[str, list[str]] = {}
    for name, fields in source_sections.items():
        project = fields.get("项目总成果")
        if project:
            project_groups.setdefault(project, []).append(name)
    for project, names in project_groups.items():
        labels = {by_name[name].get("public_project") for name in names}
        if len(names) < 2 or len(labels) != 1 or not next(iter(labels)):
            raise ValueError(f"第一项A共同项目公开标签不完整：{project[:80]}")
        scopes = {by_name[name]["public_scope"] for name in names}
        if len(scopes) != len(names):
            raise ValueError(f"第一项A共同项目个人成果范围重复：{project[:80]}")

    return by_name


def public_outcome_for_name(
    outcomes: Mapping[str, Mapping[str, Any]], name: str
) -> dict[str, Any]:
    """Resolve a reader identity name to the formal A public record."""

    formal_name = _public_name(name)
    try:
        return dict(outcomes[formal_name])
    except KeyError as exc:
        raise ValueError(f"第一项A公开成果缺少人物：{name}") from exc


def verify_first_item_public_outcomes(workspace_root: Path) -> dict[str, Any]:
    outcomes = load_first_item_public_outcomes(workspace_root)
    projects: dict[str, int] = {}
    for outcome in outcomes.values():
        project = outcome.get("public_project")
        if project:
            projects[project] = projects.get(project, 0) + 1
    return {
        "status": "PASS",
        "record_count": len(outcomes),
        "shared_project_count": sum(1 for count in projects.values() if count > 1),
        "shared_project_people": sum(count for count in projects.values() if count > 1),
        "source_markdown": SOURCE_MARKDOWN_PATH.as_posix(),
        "path": PUBLIC_OUTCOME_PATH.as_posix(),
    }
