from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_AGENTS = ROOT / "docs" / "AGENTS.md"
DOCS_REGISTRY = ROOT / "docs" / "文档与脚本登记" / "docs_registry.json"
DOCS_TOOL = ROOT / "scripts" / "dev" / "docs_tool.py"
REPORT = ROOT / "exports" / "governance" / "文档治理盘点报告.md"
PROJECT_DRIVER = "docs/皇帝综合评价体系评分标准.md"
LEGACY_DOCS_ARCHIVE_ROOT = "docs/" + "archive/"
METHODOLOGY_NAVIGATION_READMES = {
    "docs/README.md": ("operational_guide", "stable_operational_guide"),
    "docs/项目总纲/README.md": ("canonical_spec", "rule_or_method"),
    "docs/证据规则/README.md": ("canonical_spec", "rule_or_method"),
    "docs/分项规则/README.md": ("canonical_spec", "rule_or_method"),
    "docs/分项规则/第五项统治者政治素质/B用人与授权.md": ("canonical_spec", "rule_or_method"),
    "docs/展示与协作/README.md": ("operational_guide", "stable_operational_guide"),
}
ARCHIVE_MAP = {
    "docs/证据规则/证据强度四级与五轴裁量规则.md": "archive/docs/证据规则/证据强度四级与五轴裁量规则.md",
    "docs/证据规则/证据链总流程与文档索引.md": "archive/docs/证据规则/证据链总流程与文档索引.md",
    "docs/batch_canonical_absorption_audit_20260620.md": "archive/docs/audits/batch_canonical_absorption_audit_20260620.md",
    "docs/canonical_data_integrity_validation_note_20260620.md": "archive/docs/audits/canonical_data_integrity_validation_note_20260620.md",
    "docs/config_granularity_redesign_20260620.md": "archive/docs/audits/config_granularity_redesign_20260620.md",
    "docs/config_loaders迁移前依赖审计.md": "archive/docs/audits/config_loaders迁移前依赖审计.md",
    "docs/file_governance_final_audit_20260620.md": "archive/docs/audits/file_governance_final_audit_20260620.md",
    "docs/hardcoded_content_configuration_inventory_20260620.md": "archive/docs/audits/hardcoded_content_configuration_inventory_20260620.md",
    "docs/i5b_markdown_display迁移前依赖审计.md": "archive/docs/audits/i5b_markdown_display迁移前依赖审计.md",
    "docs/i5b_formal_result_leavebehind_archive_note_20260620.md": "archive/docs/audits/i5b_formal_result_leavebehind_archive_note_20260620.md",
    "docs/i5b_formal_result_leavebehind_review_20260620.md": "archive/docs/audits/i5b_formal_result_leavebehind_review_20260620.md",
    "docs/liubang_pregrade_checklist_archive_note_20260620.md": "archive/docs/audits/liubang_pregrade_checklist_archive_note_20260620.md",
    "docs/post_file_governance_consistency_audit_20260620.md": "archive/docs/audits/post_file_governance_consistency_audit_20260620.md",
    "docs/query_search_batch_canonical_import_note_20260620.md": "archive/docs/audits/query_search_batch_canonical_import_note_20260620.md",
    "docs/scripts共享工具依赖盘点.md": "archive/docs/audits/scripts共享工具依赖盘点.md",
    "docs/validation_entrypoints_20260620.md": "archive/docs/audits/validation_entrypoints_20260620.md",
    "docs/view_config_externalization_audit_20260620.md": "archive/docs/audits/view_config_externalization_audit_20260620.md",
    "docs/多余文件候选确认报告.md": "archive/docs/docs_governance/多余文件候选确认报告.md",
    "docs/多余文件第三批敏感候选复核.md": "archive/docs/docs_governance/多余文件第三批敏感候选复核.md",
    "docs/多余文件第二批最终引用复核.md": "archive/docs/docs_governance/多余文件第二批最终引用复核.md",
    "docs/第五项B三人试点检索线索说明.md": "archive/docs/audits/第五项B三人试点检索线索说明.md",
    "docs/第五项B评分映射总标尺对齐审计.md": "archive/docs/audits/第五项B评分映射总标尺对齐审计.md",
    "docs/项目文件治理诊断报告.md": "archive/docs/audits/项目文件治理诊断报告.md",
    "docs/项目重启决议.md": "archive/docs/audits/项目重启决议.md",
    "docs/i5b_cluster_warning_display_integration_design_20260621.md": "archive/docs/design_snapshots/i5b_cluster_warning_display_integration_design_20260621.md",
    "docs/i5b_evidence_cluster_adjudication_config_design_20260621.md": "archive/docs/design_snapshots/i5b_evidence_cluster_adjudication_config_design_20260621.md",
    "docs/i5b_warning_export_guarded_integration_design_20260621.md": "archive/docs/design_snapshots/i5b_warning_export_guarded_integration_design_20260621.md",
    "docs/manual_review_config_layer_design_20260620.md": "archive/docs/design_snapshots/manual_review_config_layer_design_20260620.md",
    "docs/thematic_anchor_multigranularity_schema_plan_20260620.md": "archive/docs/design_snapshots/thematic_anchor_multigranularity_schema_plan_20260620.md",
    "docs/thematic_anchor_schema_decision_20260620.md": "archive/docs/design_snapshots/thematic_anchor_schema_decision_20260620.md",
}
RETIRED_GENERATED_MAP = {
    "docs/文档治理盘点报告.md": "exports/governance/文档治理盘点报告.md",
    "docs/全局总标尺决策简报_讨论版.md": "exports/markdown_views/综合汇总/全局总标尺决策简报_讨论版.md",
    "docs/第五项B三人试点内部闭环收尾.md": "exports/markdown_views/第五项B/人工审核/自动裁判链/试点闭环/第五项B三人试点内部闭环收尾.md",
    "docs/第五项B扩展试点候选池设计.md": "exports/markdown_views/第五项B/人工审核/自动裁判链/试点闭环/第五项B扩展试点候选池设计.md",
    "docs/第五项B评分标尺与档位映射草案.md": "exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B评分标尺与档位映射草案.md",
}
RETIRED_MIXED_MAP = {
    "docs/第五项B三人专人审核入口.md": "exports/markdown_views/第五项B/人工审核/入口/第五项B三人专人审核入口.md",
    "docs/第五项B三人试点人工复核工作台.md": "exports/markdown_views/第五项B/人工审核/入口/第五项B三人试点人工复核工作台.md",
    "docs/第五项B三人试点矩阵说明.md": "exports/markdown_views/第五项B/人工审核/入口/第五项B三人试点矩阵说明.md",
    "docs/第五项B试点计划.md": "exports/markdown_views/第五项B/人工审核/入口/第五项B试点计划.md",
}
NEEDS_HUMAN_CONFIRMATION = {
    "docs/多余文件候选确认报告.md",
    "docs/多余文件第三批敏感候选复核.md",
    "docs/多余文件第二批最终引用复核.md",
}
NORMALIZED_RULE_METHOD_DOCS = {
    "docs/证据规则/史料检索与回源工作流.md",
    "docs/分项规则/第五项统治者政治素质/B用人与授权.md",
    "docs/证据规则/负证触发式裁判通用规则.md",
}
DELETED_COMPLETED_SOURCE_REVIEW_DOCS = {
    "docs/第五项B_刘庄负证回源说明.md",
    "docs/第五项B_刘秀负证回源说明.md",
    "docs/第五项B_李世民正证回源说明.md",
    "docs/第五项B_李世民负证回源说明.md",
}


def load_docs_tool():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    module = importlib.import_module("scripts.dev.docs_governance")
    module.constants.ROOT = ROOT
    return module


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        capture_output=True,
        text=False,
        check=True,
    )
    return result.stdout.decode("utf-8").splitlines()


def load_registry() -> dict:
    return json.loads(DOCS_REGISTRY.read_text(encoding="utf-8"))


def test_docs_agents_exists_and_stays_inside_budget() -> None:
    registry = load_registry()
    budget = registry["docs_agents_budget"]

    assert DOCS_AGENTS.is_file()
    assert len(DOCS_AGENTS.read_text(encoding="utf-8").splitlines()) <= budget["max_lines"]
    assert len(DOCS_AGENTS.read_bytes()) <= budget["max_bytes"]


def test_root_agents_routes_to_docs_agents() -> None:
    content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "docs/AGENTS.md" in content


def test_docs_registry_is_valid_and_tool_check_passes() -> None:
    assert not DOCS_REGISTRY.read_bytes().startswith(b"\xef\xbb\xbf")
    registry = load_registry()

    assert registry["schema_version"] == 1
    assert "docs/文档与脚本登记/docs_registry.json" in registry["registry_exclusions"]
    assert set(registry["allowed_content_roles"]) == load_docs_tool().ALLOWED_CONTENT_ROLES
    assert set(registry["allowed_placement_actions"]) == load_docs_tool().ALLOWED_PLACEMENT_ACTIONS

    result = subprocess.run(
        [sys.executable, str(DOCS_TOOL), "check", "--registry", "docs/文档与脚本登记/docs_registry.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_registry_covers_every_tracked_docs_file_except_itself() -> None:
    registry = load_registry()
    expected = {
        path
        for path in git_lines("ls-files", "docs", "archive/docs")
        if path != "docs/文档与脚本登记/docs_registry.json"
    }
    actual = {doc["path"] for doc in registry["documents"]}

    assert actual == expected


def test_docs_registry_candidate_safety_rules() -> None:
    registry = load_registry()
    current_doc_roles = {"rule_or_method", "stable_operational_guide", "governance_state"}
    for doc in registry["documents"]:
        assert doc["content_role"] in registry["allowed_content_roles"]
        assert doc["placement_action"] in registry["allowed_placement_actions"]
        assert isinstance(doc["placement_targets"], list)
        assert isinstance(doc["semantic_verification_required"], bool)
        assert doc["placement_reason"].strip()
        if doc["proposed_action"] == "delete" or doc["lifecycle_status"] == "delete_candidate":
            assert doc["human_confirmation_required"] is True
            assert doc["reason"].strip()
        if doc["unique_source_risk"]:
            assert doc["proposed_action"] != "delete"
        if doc["content_role"] == "generated_output":
            assert doc["placement_action"] != "keep_in_docs"
        if doc["content_role"] == "mixed":
            assert doc["placement_action"] in {"split_keep_rules_generate_state", "review"}
        if doc["content_role"] == "instance_record" and doc["placement_action"] == "absorb_into_canonical_data_then_export":
            assert doc["semantic_verification_required"] is True
        if doc["placement_action"] == "keep_archive_exception":
            assert doc["path"].startswith("archive/docs/")
        if doc["placement_action"] == "keep_governance_exception":
            assert doc["path"].startswith("docs/文档与脚本登记/")
        if doc["placement_action"] not in {"keep_in_docs", "keep_governance_exception", "keep_archive_exception", "review"}:
            assert doc["placement_targets"]
        if doc["replacement_path"]:
            assert (ROOT / doc["replacement_path"]).exists()
        for field in ("generator_candidates", "referenced_by_tests", "inbound_references"):
            for rel_path in doc[field]:
                assert (ROOT / rel_path).exists(), f"{doc['path']} has missing {field}: {rel_path}"
        if doc["path"].startswith("docs/") and doc["placement_action"] != "keep_governance_exception":
            assert doc["content_role"] in current_doc_roles
            assert doc["lifecycle_status"] != "historical"


def test_docs_registry_has_no_current_active_design_docs() -> None:
    registry = load_registry()
    by_path = {doc["path"]: doc for doc in registry["documents"]}

    assert [doc for doc in registry["documents"] if doc["document_type"] == "active_design"] == []
    assert NORMALIZED_RULE_METHOD_DOCS <= set(by_path)
    for path in NORMALIZED_RULE_METHOD_DOCS:
        doc = by_path[path]
        assert (ROOT / path).is_file()
        assert doc["document_type"] == "canonical_spec"
        assert doc["lifecycle_status"] == "active"
        assert doc["content_role"] == "rule_or_method"
        assert doc["placement_action"] == "keep_in_docs"
        assert doc["proposed_action"] == "keep"
        assert doc["human_confirmation_required"] is False
        assert doc["semantic_verification_required"] is False


def test_methodology_navigation_readmes_exist_and_are_registered() -> None:
    registry = load_registry()
    by_path = {doc["path"]: doc for doc in registry["documents"]}

    assert set(METHODOLOGY_NAVIGATION_READMES) <= set(by_path)
    for path, (document_type, content_role) in METHODOLOGY_NAVIGATION_READMES.items():
        doc = by_path[path]
        assert (ROOT / path).is_file()
        assert doc["document_type"] == document_type
        assert doc["lifecycle_status"] == "active"
        assert doc["proposed_action"] == "keep"
        assert doc["content_role"] == content_role
        assert doc["placement_action"] == "keep_in_docs"
        assert doc["unique_source_risk"] is True
        assert doc["semantic_verification_required"] is False
        assert doc["human_confirmation_required"] is False

    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for needle in [
        "`docs/` 根目录只保留受保护的最高层评分标准",
        "每个子项目最多一个分项规则文档",
        "不手改 generated export",
        "不在目录治理 PR 中修改评分、档位、证据、排名或榜单等业务语义",
    ]:
        assert needle in readme

    assert not (ROOT / "docs" / "archive").exists()
    assert (ROOT / "archive" / "docs").is_dir()


def test_project_driver_is_registered_and_protected() -> None:
    registry = load_registry()
    drivers = registry["project_driver_paths"]
    by_path = {doc["path"]: doc for doc in registry["documents"]}

    assert drivers == [PROJECT_DRIVER]
    driver = by_path[PROJECT_DRIVER]
    assert (ROOT / PROJECT_DRIVER).is_file()
    assert driver["document_type"] == "canonical_spec"
    assert driver["lifecycle_status"] == "active"
    assert driver["proposed_action"] == "keep"
    assert driver["content_role"] == "rule_or_method"
    assert driver["placement_action"] == "keep_in_docs"
    assert driver["unique_source_risk"] is True
    assert PROJECT_DRIVER not in registry.get("archived_document_paths", {})
    assert PROJECT_DRIVER not in registry.get("archived_document_paths", {}).values()

    text = (ROOT / PROJECT_DRIVER).read_text(encoding="utf-8")
    for marker in [
        "中国古代皇帝综合评价体系 V3.2",
        "正收益总分 − 历史负债",
        "正收益合计",
        "历史负债",
    ]:
        assert marker in text

    for rel_path in ["README.md", "AGENTS.md", "docs/AGENTS.md", "docs/项目总纲/总规则.md"]:
        assert PROJECT_DRIVER in (ROOT / rel_path).read_text(encoding="utf-8")


def test_archive_batch_lifecycle_and_mapping_are_exact() -> None:
    registry = load_registry()
    by_path = {doc["path"]: doc for doc in registry["documents"]}

    assert not (ROOT / "docs" / "archive").exists()
    assert (ROOT / "archive" / "docs").is_dir()
    assert registry["archived_document_paths"] == ARCHIVE_MAP
    assert LEGACY_DOCS_ARCHIVE_ROOT not in json.dumps(registry, ensure_ascii=False)
    assert sum(1 for doc in registry["documents"] if doc["proposed_action"] == "archive") == 0
    assert sum(1 for doc in registry["documents"] if doc["proposed_action"] == "delete") == 0

    for old_path, new_path in ARCHIVE_MAP.items():
        assert not (ROOT / old_path).exists()
        assert (ROOT / new_path).is_file()
        doc = by_path[new_path]
        assert doc["document_type"] in {"audit_record", "historical_snapshot", "migration_record"}
        assert doc["lifecycle_status"] == "historical"
        assert doc["proposed_action"] == "keep"
        assert doc["content_role"] == "historical_record"
        assert doc["placement_action"] == "keep_archive_exception"
        assert doc["human_confirmation_required"] is False

    assert sum(1 for doc in registry["documents"] if doc["lifecycle_status"] == "needs_human_confirmation") == 0
    for path in NEEDS_HUMAN_CONFIRMATION:
        assert path not in by_path

    for path in DELETED_COMPLETED_SOURCE_REVIEW_DOCS:
        assert path not in by_path
        assert not (ROOT / path).exists()
        assert path not in registry.get("archived_document_paths", {})
        assert path not in registry.get("retired_generated_document_paths", {})
        assert path not in registry.get("retired_mixed_document_paths", {})


def test_generated_views_have_generators_or_need_human_confirmation() -> None:
    registry = load_registry()
    for doc in registry["documents"]:
        if doc["document_type"] == "generated_view":
            assert doc["generator_candidates"] or doc["lifecycle_status"] == "needs_human_confirmation"
        if doc["content_role"] == "generated_output" and doc["placement_action"] == "move_to_exports":
            assert all(target.startswith("exports/") for target in doc["placement_targets"])


def test_retired_generated_document_paths_are_exact_and_export_only() -> None:
    registry = load_registry()
    by_path = {doc["path"] for doc in registry["documents"]}
    drivers = set(registry["project_driver_paths"])

    assert registry["retired_generated_document_paths"] == RETIRED_GENERATED_MAP
    for old_path, target_path in RETIRED_GENERATED_MAP.items():
        assert not (ROOT / old_path).exists()
        assert (ROOT / target_path).is_file()
        assert old_path not in by_path
        assert old_path not in drivers
        assert old_path not in registry.get("archived_document_paths", {})
    assert len(set(RETIRED_GENERATED_MAP.values())) == len(RETIRED_GENERATED_MAP)
    assert not (ROOT / "docs" / "文档治理盘点报告.md").exists()
    assert (ROOT / "exports" / "governance" / "文档治理盘点报告.md").is_file()


def test_retired_mixed_document_paths_are_exact_and_export_backed() -> None:
    registry = load_registry()
    by_path = {doc["path"] for doc in registry["documents"]}
    drivers = set(registry["project_driver_paths"])

    assert registry["retired_mixed_document_paths"] == RETIRED_MIXED_MAP
    for old_path, target_path in RETIRED_MIXED_MAP.items():
        assert not (ROOT / old_path).exists()
        assert (ROOT / target_path).is_file()
        assert old_path not in by_path
        assert old_path not in drivers
        assert old_path not in registry.get("archived_document_paths", {})
        assert old_path not in registry.get("retired_generated_document_paths", {})
    assert len(set(RETIRED_MIXED_MAP.values())) == len(RETIRED_MIXED_MAP)


def test_governance_report_exists_and_lists_candidate_classes() -> None:
    assert REPORT.is_file()
    content = REPORT.read_text(encoding="utf-8")
    for needle in [
        "docs registry 覆盖文档数：65，其中当前 `docs/` 层 34 份，历史归档区 31 份。",
        "### 内容角色统计",
        "### 推荐归置动作统计",
        "## 2. 项目驱动文档",
        PROJECT_DRIVER,
        "## 当前仅保留 exports 候选",
        "## 已迁出 docs 的生成文档摘要",
        "## 已迁出 docs 的混合审核文档摘要",
        "## 当前待拆分的混合文档",
        "## 当前吸收后归档候选",
        "## 当前内容归置待确认项",
        "## 当前生命周期 archive candidates",
        "## 当前生命周期 delete candidates",
        "## 当前生命周期 review / needs human confirmation",
        "## 历史归档摘要",
        "## 当前候选摘要",
        "当前治理报告仅描述 docs 生命周期、内容角色与推荐归置状态",
    ]:
        assert needle in content
    assert LEGACY_DOCS_ARCHIVE_ROOT not in content
    assert "archive root | archive/docs/" in content
    assert "historical archive documents" in content
    assert "retired generated docs" in content
    assert "retired mixed docs" in content
    summary = content.split("## 当前候选摘要", 1)[1].split("## 9. 范围声明", 1)[0]
    fact_source_section = content.split("## 6. 事实源对账待办", 1)[1].split("## 当前仅保留 exports 候选", 1)[0]
    assert "当前无待办候选" in summary
    assert "Batch 6：needs-human-confirmation 历史材料" not in content
    assert "Batch 7：规则方法层归置核对" not in content
    assert "已完成：历史治理材料已归档，不再等待逐份确认。" not in content
    assert "docs/manual_review_config_layer_design_20260620.md" not in summary
    assert "| active_design |" not in content
    assert "已完成：长期研究方法、裁判机制或上下文机制已归入 docs 当前规则方法层。" not in content
    for path in DELETED_COMPLETED_SOURCE_REVIEW_DOCS:
        assert path not in content
        assert path not in fact_source_section
    assert not re.search(r"PR #\d+", content)
    assert "#207" not in content
    assert "本 PR" not in content
    for old_path, new_path in ARCHIVE_MAP.items():
        assert old_path not in content
        assert new_path not in content
    for old_path, target_path in RETIRED_GENERATED_MAP.items():
        assert old_path not in content
        assert target_path not in content
    assert "Batch 1：generated docs -> export-only" not in content
    assert "已完成" not in summary
    for old_path, target_path in RETIRED_MIXED_MAP.items():
        assert old_path not in content
        assert target_path not in content
    retired_mixed_section = content.split("## 已迁出 docs 的混合审核文档摘要", 1)[1].split("## 当前待拆分的混合文档", 1)[0]
    pending_mixed_section = content.split("## 当前待拆分的混合文档", 1)[1].split("## 当前吸收后归档候选", 1)[0]
    assert "retired mixed docs" in retired_mixed_section
    assert "docs/第五项B三人专人审核入口.md" not in pending_mixed_section
    assert "Batch 2：混合审核文档拆分" not in content


def test_archive_readme_exists_and_links_batch_documents() -> None:
    readme = ROOT / "archive" / "docs" / "README.md"

    assert readme.is_file()
    content = readme.read_text(encoding="utf-8")
    assert "# archive/docs" in content
    for new_path in ARCHIVE_MAP.values():
        rel = new_path.removeprefix("archive/docs/")
        assert f"]({rel})" in content


def test_tracked_tmp_governance_inventory_is_removed() -> None:
    assert ".tmp/docs_governance/i5b_mixed_docs_split_inventory.md" not in git_lines(
        "ls-files",
        ".tmp/docs_governance/i5b_mixed_docs_split_inventory.md",
    )


def test_governance_report_matches_generator() -> None:
    docs_tool = load_docs_tool()

    assert REPORT.read_text(encoding="utf-8") == docs_tool.build_report("docs/文档与脚本登记/docs_registry.json")
