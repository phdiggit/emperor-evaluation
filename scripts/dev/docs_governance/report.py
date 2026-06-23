from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from . import constants as c
from .paths import _ensure_report_output, _emit_stdout, _load_json_file, _resolve_repo_path
from .registry_check import check_registry


def _count_by(documents: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(doc.get(field)) for doc in documents).items()))


def _table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["无。"]
    header = "| " + " | ".join(rows[0]) + " |"
    divider = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = ["| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |" for row in rows[1:]]
    return [header, divider, *body]


def build_report(registry_path: str = c.REGISTRY_PATH, worktree: bool = False) -> str:
    registry = _load_json_file(registry_path)
    documents = sorted(registry.get("documents", []), key=lambda item: item["path"])
    current_docs = [doc for doc in documents if str(doc["path"]).startswith("docs/")]
    archive_registry_docs = [doc for doc in documents if str(doc["path"]).startswith(c.ARCHIVE_DOCS_ROOT)]
    type_counts = _count_by(current_docs, "document_type")
    status_counts = _count_by(current_docs, "lifecycle_status")
    action_counts = _count_by(current_docs, "proposed_action")
    content_role_counts = _count_by(current_docs, "content_role")
    placement_action_counts = _count_by(current_docs, "placement_action")
    exact_groups = defaultdict(list)
    normalized_groups = defaultdict(list)
    for doc in documents:
        if doc.get("duplicate_group") or doc.get("exact_duplicate_group"):
            exact_groups[doc.get("duplicate_group") or doc.get("exact_duplicate_group")].append(doc["path"])
        if doc.get("normalized_duplicate_group"):
            normalized_groups[doc["normalized_duplicate_group"]].append(doc["path"])

    def docs_for(action: str | None = None, status: str | None = None, placement: str | None = None) -> list[dict[str, Any]]:
        return [
            doc
            for doc in documents
            if (action is None or doc.get("proposed_action") == action)
            and (status is None or doc.get("lifecycle_status") == status)
            and (placement is None or doc.get("placement_action") == placement)
        ]

    def unique_docs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_path = {doc["path"]: doc for doc in items}
        return [by_path[path] for path in sorted(by_path)]

    archive_docs = docs_for(action="archive")
    delete_docs = docs_for(action="delete")
    review_docs = unique_docs(docs_for(action="review") + docs_for(status="needs_human_confirmation"))
    archived_map = registry.get("archived_document_paths") or {}
    retired_generated_map = registry.get("retired_generated_document_paths") or {}
    retired_mixed_map = registry.get("retired_mixed_document_paths") or {}
    archived_docs = [doc for old_path, new_path in sorted(archived_map.items()) for doc in documents if doc["path"] == new_path]
    project_driver_paths = registry.get("project_driver_paths") or []
    project_driver_docs = [doc for driver_path in project_driver_paths for doc in documents if doc["path"] == driver_path]
    candidate_paths = {doc["path"] for doc in archive_docs + delete_docs + review_docs + archived_docs}

    candidate_header = [
        "path",
        "content role",
        "placement action",
        "placement targets",
        "semantic verification required",
        "inbound refs",
        "unique risk",
        "reason",
        "human confirmation",
    ]

    def candidate_rows(items: list[dict[str, Any]]) -> list[list[str]]:
        rows = [candidate_header]
        for doc in items:
            rows.append(
                [
                    doc["path"],
                    str(doc.get("content_role", "")),
                    str(doc.get("placement_action", "")),
                    "<br>".join(doc.get("placement_targets", [])) or "-",
                    str(bool(doc.get("semantic_verification_required"))).lower(),
                    str(len(doc.get("inbound_references", []))),
                    str(bool(doc.get("unique_source_risk"))).lower(),
                    doc.get("placement_reason") or doc.get("reason", ""),
                    str(bool(doc.get("human_confirmation_required"))).lower(),
                ]
            )
        if len(rows) == 1:
            rows.append(["-", "-", "-", "-", "-", "-", "-", "无当前候选。", "-"])
        return rows

    def driver_rows(items: list[dict[str, Any]]) -> list[list[str]]:
        rows = [["path", "title", "document type", "lifecycle", "content role", "placement action", "unique source risk", "reason"]]
        if not items:
            rows.append(["-", "-", "-", "-", "-", "-", "-", "project_driver_paths 未登记或无有效文档；请先修复 registry。"])
            return rows
        for doc in items:
            rows.append(
                [
                    doc["path"],
                    str(doc.get("title", "")),
                    str(doc.get("document_type", "")),
                    str(doc.get("lifecycle_status", "")),
                    str(doc.get("content_role", "")),
                    str(doc.get("placement_action", "")),
                    str(bool(doc.get("unique_source_risk"))).lower(),
                    doc.get("reason", ""),
                ]
            )
        return rows

    def placement_docs(*placements: str) -> list[dict[str, Any]]:
        return [doc for doc in documents if doc.get("placement_action") in set(placements)]

    stable_docs = [
        doc
        for doc in placement_docs("keep_in_docs", "keep_governance_exception")
        if doc["path"].startswith("docs/")
    ]
    config_absorption_docs = unique_docs(
        docs_for(placement="absorb_into_config")
        + [doc for doc in docs_for(placement="archive_after_absorption") if any("data/configs/" in target for target in doc.get("placement_targets", []))]
    )
    canonical_data_docs = docs_for(placement="absorb_into_canonical_data_then_export")
    export_only_docs = docs_for(placement="move_to_exports")
    split_docs = docs_for(placement="split_keep_rules_generate_state")
    archive_after_absorption_docs = docs_for(placement="archive_after_absorption")
    placement_review_docs = docs_for(placement="review")
    placement_problems = check_registry(registry_path, worktree=worktree)

    def retired_generated_rows() -> list[list[str]]:
        existing_targets = sum(1 for target_path in retired_generated_map.values() if _resolve_repo_path(target_path).is_file())
        return [
            ["metric", "value"],
            ["retired generated docs", str(len(retired_generated_map))],
            ["existing canonical exports", str(existing_targets)],
            ["detail source", "docs/文档与脚本登记/docs_registry.json retired_generated_document_paths"],
        ]

    def retired_mixed_rows() -> list[list[str]]:
        existing_targets = sum(1 for target_path in retired_mixed_map.values() if _resolve_repo_path(target_path).is_file())
        return [
            ["metric", "value"],
            ["retired mixed docs", str(len(retired_mixed_map))],
            ["existing canonical targets", str(existing_targets)],
            ["detail source", "docs/文档与脚本登记/docs_registry.json retired_mixed_document_paths"],
        ]

    def archived_summary_rows() -> list[list[str]]:
        return [
            ["metric", "value"],
            ["historical archive documents", str(len(archive_registry_docs))],
            ["archived old docs mappings", str(len(archived_map))],
            ["archive root", c.ARCHIVE_DOCS_ROOT],
            ["detail source", "docs/文档与脚本登记/docs_registry.json archived_document_paths and documents"],
        ]

    def unique_source_summary_rows() -> list[list[str]]:
        current_unique_docs = [
            doc
            for doc in current_docs
            if doc.get("unique_source_risk") and doc["path"] not in candidate_paths
        ]
        return [
            ["metric", "value"],
            ["current docs unique source risk", str(len(current_unique_docs))],
            ["detail source", "docs/文档与脚本登记/docs_registry.json documents"],
        ]

    def current_candidate_rows() -> list[list[str]]:
        rows = [["candidate class", "count", "paths", "primary targets", "human confirmation", "semantic verification"]]
        candidate_groups = [
            ("当前待迁出 exports", export_only_docs),
            ("当前待拆分 mixed 文档", split_docs),
            ("当前待吸收配置", config_absorption_docs),
            ("当前事实源对账待办", canonical_data_docs),
            ("当前吸收后归档候选", archive_after_absorption_docs),
            ("当前内容归置待确认", placement_review_docs),
            ("当前生命周期归档候选", archive_docs),
            ("当前生命周期删除候选", delete_docs),
            ("当前 lifecycle review / needs human confirmation", review_docs),
        ]
        for name, docs in candidate_groups:
            if not docs:
                continue
            targets = sorted({target for doc in docs for target in doc.get("placement_targets", [])})
            rows.append(
                [
                    name,
                    str(len(docs)),
                    "<br>".join(doc["path"] for doc in docs),
                    "<br>".join(targets) or "-",
                    "yes" if any(doc.get("human_confirmation_required") for doc in docs) else "no",
                    "yes" if any(doc.get("semantic_verification_required") for doc in docs) else "no",
                ]
            )
        if len(rows) == 1:
            rows.append(["当前无待办候选", "0", "-", "-", "no", "no"])
        return rows


    lines: list[str] = [
        "# 文档治理盘点报告",
        "",
        "本报告由 docs registry 生成，用于当前文档生命周期、内容角色与推荐归置状态审阅。",
        "",
        "## 1. 执行摘要",
        "",
        f"- 基线 ref：`{registry.get('baseline_ref')}`。",
        f"- 基线 commit：`{registry.get('baseline_sha')}`。",
        f"- docs registry 覆盖文档数：{len(documents)}，其中当前 `docs/` 层 {len(current_docs)} 份，历史归档区 {len(archive_registry_docs)} 份。",
        "- 候选动作和已归档映射均以 registry 当前状态为准；归档不是删除，吸收候选也不表示已经迁移。",
        "- 本报告只登记内容归置建议，不改变 data、exports、数据库、评分、证据或裁判语义。",
        "",
        "## 2. 项目驱动文档",
        "",
        *_table(driver_rows(project_driver_docs)),
        "",
        "## 3. 当前 docs 层统计",
        "",
        "### document type",
        "",
        *_table([["document_type", "count"], *[[key, str(value)] for key, value in type_counts.items()]]),
        "",
        "### lifecycle status",
        "",
        *_table([["lifecycle_status", "count"], *[[key, str(value)] for key, value in status_counts.items()]]),
        "",
        "### proposed action",
        "",
        *_table([["proposed_action", "count"], *[[key, str(value)] for key, value in action_counts.items()]]),
        "",
        "### 内容角色统计",
        "",
        *_table([["content_role", "count"], *[[key, str(value)] for key, value in content_role_counts.items()]]),
        "",
        "### 推荐归置动作统计",
        "",
        *_table([["placement_action", "count"], *[[key, str(value)] for key, value in placement_action_counts.items()]]),
        "",
        "## 分类口径",
        "",
        "- `canonical_spec`、`operational_guide` 和仍被 README、AGENTS、scripts、tests 引用的当前规则、方法论或运行说明默认保留。",
        "- `generated_view` 只登记 generator 候选；不能用手改文档替代修改生成器。",
        "- 历史审计、迁移和日期快照保留在 `archive/docs/`，作为追溯材料，不是当前 docs 规则入口。",
        "- `delete_candidate` 仅表示后续低风险删除审查对象，仍必须人工确认。",
        "- 内容归置与生命周期是正交维度；`keep` 可以同时登记后续吸收、拆分或归档建议。",
        "",
        "## 4. 当前稳定文档",
        "",
        *_table(candidate_rows(stable_docs)),
        "",
        "## 5. 当前待迁移 / 待吸收 / 待归档 / 待删除候选",
        "",
        *_table(candidate_rows(config_absorption_docs)),
        "",
        "## 6. 事实源对账待办",
        "",
        *_table(candidate_rows(canonical_data_docs)),
        "",
        "## 当前仅保留 exports 候选",
        "",
        *_table(candidate_rows(export_only_docs)),
        "",
        "## 已迁出 docs 的生成文档摘要",
        "",
        *_table(retired_generated_rows()),
        "",
        "## 已迁出 docs 的混合审核文档摘要",
        "",
        *_table(retired_mixed_rows()),
        "",
        "## 当前待拆分的混合文档",
        "",
        *_table(candidate_rows(split_docs)),
        "",
        "## 当前吸收后归档候选",
        "",
        *_table(candidate_rows(archive_after_absorption_docs)),
        "",
        "## 当前内容归置待确认项",
        "",
        *_table(candidate_rows(placement_review_docs)),
        "",
        "## 当前生命周期 archive candidates",
        "",
        *_table(candidate_rows(archive_docs)),
        "",
        "## 当前生命周期 delete candidates",
        "",
        *_table(candidate_rows(delete_docs)),
        "",
        "## 当前生命周期 review / needs human confirmation",
        "",
        *_table(candidate_rows(review_docs)),
        "",
        "## 历史归档摘要",
        "",
        *_table(archived_summary_rows()),
        "",
        "## 重复组",
        "",
        "### exact duplicates",
        "",
        *_table([["group", "paths"], *[[group, "<br>".join(paths)] for group, paths in sorted(exact_groups.items())]]),
        "",
        "### normalized duplicates",
        "",
        *_table([["group", "paths"], *[[group, "<br>".join(paths)] for group, paths in sorted(normalized_groups.items())]]),
        "",
        "## 7. 引用断链或异常",
        "",
    ]
    lines.extend(["- docs_tool check 当前通过，未发现 registry 引用断链。" if not placement_problems else "- " + "\n- ".join(placement_problems)])
    lines.extend(
        [
            "",
            "## 目标态违规或异常",
            "",
            *(
                ["- 未发现目标态违规或异常。"]
                if not placement_problems
                else [f"- {problem}" for problem in placement_problems]
            ),
            "",
            "## 8. unique source 风险摘要",
            "",
            *_table(unique_source_summary_rows()),
            "",
            "## 当前候选摘要",
            "",
            *_table(current_candidate_rows()),
            "",
            "## 9. 范围声明",
            "",
            "当前治理报告仅描述 docs 生命周期、内容角色与推荐归置状态；未将 archive 视为删除，也不改变 data、exports、数据库或 SQLite 文件。",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(registry_path: str, output: str | None, worktree: bool = False) -> None:
    text = build_report(registry_path, worktree=worktree)
    target = _ensure_report_output(output)
    if target:
        target.write_text(text, encoding="utf-8", newline="\n")
    else:
        _emit_stdout(text + "\n")
