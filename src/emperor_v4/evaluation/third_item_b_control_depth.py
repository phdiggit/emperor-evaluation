"""Validate evidence-backed B control packages without reclassifying historical facts."""

from typing import Any, Mapping
from urllib.parse import urlparse


def control_depth_package_ids(row: Mapping[str, Any]) -> set[str]:
    packages = row.get("control_depth_packages") or []
    if not isinstance(packages, list):
        raise ValueError("同域实控升级须为证据包列表")
    allowed = set(row.get("parent_cycle_refs") or []) | set(row.get("evidence_event_refs") or [])
    excluded = set(row.get("excluded_founding_unification_refs") or [])
    result: set[str] = set()
    for package in packages:
        if not isinstance(package, Mapping):
            raise ValueError("同域实控升级证据包格式不合法")
        for key in (
            "package_id", "object_name", "assessment_window", "entry_control",
            "handover_control", "ruler_action", "cross_item_boundary", "all_results_review",
        ):
            if not isinstance(package.get(key), str) or not package[key].strip():
                raise ValueError(f"同域实控升级缺少{key}")
        package_id = package["package_id"]
        if not package_id.startswith("B-DEPTH-") or package_id in result or package_id in allowed:
            raise ValueError("同域实控升级证据包ID重复或混用战争父链")
        refs = package.get("context_parent_refs")
        if (not isinstance(refs, list) or not refs or len(set(refs)) != len(refs)
                or not set(refs).issubset(allowed) or set(refs) & excluded):
            raise ValueError("同域实控升级的背景父链缺失、越界或重复统一成果")
        sources = package.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("同域实控升级缺少已核原文的史源")
        for source in sources:
            if any(not isinstance(source.get(key), str) or not source[key].strip()
                   for key in ("title", "url", "locator", "evidence")):
                raise ValueError("同域实控升级史源标题、定位与事实摘述不完整")
            if urlparse(source["url"]).scheme not in {"https", "http"}:
                raise ValueError("同域实控升级史源地址不合法")
        if package.get("spatial_increment_claimed") is not False:
            raise ValueError("同域实控升级不得重复申报B1空间增量")
        result.add(package_id)
    return result


def render_control_depth_packages(row: Mapping[str, Any]) -> list[str]:
    control_depth_package_ids(row)
    lines = []
    for package in row.get("control_depth_packages") or []:
        lines.extend([
            f"- 同域实控升级：**{package['object_name']}**（{package['assessment_window']}）。"
            f"接班：{package['entry_control']}；交班：{package['handover_control']}。",
            f"- 本人归责与边界：{package['ruler_action']}；{package['cross_item_boundary']}",
            f"- 全部主要成果复核：{package['all_results_review']}",
            "- 实控升级史源：" + "；".join(
                f"[{s['title']}]({s['url']})（{s['locator']}）" for s in package['sources']
            ),
        ])
    return lines
