from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Mapping, Sequence


COVERAGE_SCHEMA_VERSION = "rule-factor-evidence-coverage-v1"
COVERAGE_STATUSES = frozenset(
    {"open_snapshot", "minimum_sufficient", "reviewed_bounded_complete"}
)
INFERENCE_BASES = frozenset(
    {"direct_evidence", "bounded_absence", "coverage_insufficient"}
)
DECISION_STATUSES = frozenset({"resolved", "insufficient_coverage"})


def scope_coverage_to_sources(
    coverage: Mapping[str, Any], source_families: Sequence[str]
) -> dict[str, Any]:
    scoped = deepcopy(dict(coverage))
    scoped["source_families"] = sorted(set(source_families))
    validate_coverage_declaration(scoped)
    return scoped


def validate_coverage_declaration(coverage: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "scope_as_of",
        "coverage_status",
        "absence_inference_allowed",
        "covered_time_window",
        "source_families",
        "stop_reason",
    }
    if set(coverage) != expected:
        raise ValueError("evidence_coverage 字段必须严格匹配合同")
    if coverage.get("schema_version") != COVERAGE_SCHEMA_VERSION:
        raise ValueError("evidence_coverage schema_version 非法")
    try:
        date.fromisoformat(str(coverage.get("scope_as_of") or ""))
    except ValueError as exc:
        raise ValueError("evidence_coverage scope_as_of 非法") from exc
    status = coverage.get("coverage_status")
    if status not in COVERAGE_STATUSES:
        raise ValueError("evidence_coverage coverage_status 非法")
    absence_allowed = coverage.get("absence_inference_allowed")
    if not isinstance(absence_allowed, bool):
        raise ValueError("evidence_coverage absence_inference_allowed 必须为布尔值")
    if absence_allowed and status != "reviewed_bounded_complete":
        raise ValueError("只有 reviewed_bounded_complete 才允许根据缺失作推断")
    window = coverage.get("covered_time_window")
    if window is not None:
        if (
            not isinstance(window, Mapping)
            or set(window) != {"start", "end"}
            or not all(window.values())
        ):
            raise ValueError("evidence_coverage covered_time_window 非法")
    if absence_allowed and window is None:
        raise ValueError("允许缺失推断时必须声明有界时间窗")
    families = coverage.get("source_families")
    if (
        not isinstance(families, Sequence)
        or isinstance(families, (str, bytes))
        or not families
        or any(not isinstance(value, str) or not value.strip() for value in families)
        or len(set(families)) != len(families)
    ):
        raise ValueError("evidence_coverage source_families 必须非空且唯一")
    if not str(coverage.get("stop_reason") or "").strip():
        raise ValueError("evidence_coverage stop_reason 缺失")


def validate_factor_resolution(
    *,
    coverage: Mapping[str, Any],
    decision_status: str,
    option_code: str | None,
    inference_basis: str,
    allowed_options: Sequence[str],
    absence_sensitive_options: Sequence[str] = (),
) -> None:
    """通用因子门禁；规则只声明值域和哪些选项可能依赖缺失推断。"""

    validate_coverage_declaration(coverage)
    if decision_status not in DECISION_STATUSES or inference_basis not in INFERENCE_BASES:
        raise ValueError("factor resolution 状态或推断依据非法")
    if decision_status == "insufficient_coverage":
        if option_code is not None or inference_basis != "coverage_insufficient":
            raise ValueError("覆盖不足时不得强行提交 option_code")
        return
    if option_code not in allowed_options or inference_basis == "coverage_insufficient":
        raise ValueError("resolved factor resolution 缺少合法 option_code 或推断依据")
    if inference_basis == "bounded_absence":
        if option_code not in set(absence_sensitive_options):
            raise ValueError("该因子选项未声明允许使用有界缺失推断")
        if coverage.get("absence_inference_allowed") is not True:
            raise ValueError("开放覆盖不得根据未发现材料选择缺失敏感档位")
