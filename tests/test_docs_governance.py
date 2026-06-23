from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_AGENTS = ROOT / "docs" / "AGENTS.md"
DOCS_REGISTRY = ROOT / "docs" / "agent_rules" / "docs_registry.json"
DOCS_TOOL = ROOT / "scripts" / "dev" / "docs_tool.py"
REPORT = ROOT / "docs" / "文档治理盘点报告.md"
PROJECT_DRIVER = "docs/皇帝综合评价体系评分标准.md"
ARCHIVE_MAP = {
    "docs/canonical_data_integrity_validation_note_20260620.md": "docs/archive/audits/canonical_data_integrity_validation_note_20260620.md",
    "docs/file_governance_final_audit_20260620.md": "docs/archive/audits/file_governance_final_audit_20260620.md",
    "docs/hardcoded_content_configuration_inventory_20260620.md": "docs/archive/audits/hardcoded_content_configuration_inventory_20260620.md",
    "docs/i5b_formal_result_leavebehind_archive_note_20260620.md": "docs/archive/audits/i5b_formal_result_leavebehind_archive_note_20260620.md",
    "docs/i5b_formal_result_leavebehind_review_20260620.md": "docs/archive/audits/i5b_formal_result_leavebehind_review_20260620.md",
    "docs/liubang_pregrade_checklist_archive_note_20260620.md": "docs/archive/audits/liubang_pregrade_checklist_archive_note_20260620.md",
    "docs/query_search_batch_canonical_import_note_20260620.md": "docs/archive/audits/query_search_batch_canonical_import_note_20260620.md",
}
RETIRED_GENERATED_MAP = {
    "docs/全局总标尺决策简报_讨论版.md": "exports/markdown_views/综合汇总/全局总标尺决策简报_讨论版.md",
    "docs/第五项B三人试点内部闭环收尾.md": "exports/markdown_views/第五项B/人工审核/自动裁判链/试点闭环/第五项B三人试点内部闭环收尾.md",
    "docs/第五项B扩展试点候选池设计.md": "exports/markdown_views/第五项B/人工审核/自动裁判链/试点闭环/第五项B扩展试点候选池设计.md",
    "docs/第五项B评分标尺与档位映射草案.md": "exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B评分标尺与档位映射草案.md",
}
NEEDS_HUMAN_CONFIRMATION = {
    "docs/多余文件候选确认报告.md",
    "docs/多余文件第三批敏感候选复核.md",
    "docs/多余文件第二批最终引用复核.md",
}


def load_docs_tool():
    spec = importlib.util.spec_from_file_location("docs_tool_real_repo", DOCS_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    assert "docs/agent_rules/docs_registry.json" in registry["registry_exclusions"]
    assert set(registry["allowed_content_roles"]) == load_docs_tool().ALLOWED_CONTENT_ROLES
    assert set(registry["allowed_placement_actions"]) == load_docs_tool().ALLOWED_PLACEMENT_ACTIONS

    result = subprocess.run(
        [sys.executable, str(DOCS_TOOL), "check", "--registry", "docs/agent_rules/docs_registry.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_registry_covers_every_tracked_docs_file_except_itself() -> None:
    registry = load_registry()
    expected = {path for path in git_lines("ls-files", "docs") if path != "docs/agent_rules/docs_registry.json"}
    actual = {doc["path"] for doc in registry["documents"]}

    assert actual == expected


def test_docs_registry_candidate_safety_rules() -> None:
    registry = load_registry()
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
            assert doc["path"].startswith("docs/archive/")
        if doc["placement_action"] == "keep_governance_exception":
            assert doc["path"].startswith("docs/agent_rules/")
        if doc["placement_action"] not in {"keep_in_docs", "keep_governance_exception", "keep_archive_exception", "review"}:
            assert doc["placement_targets"]
        if doc["replacement_path"]:
            assert (ROOT / doc["replacement_path"]).exists()
        for field in ("generator_candidates", "referenced_by_tests", "inbound_references"):
            for rel_path in doc[field]:
                assert (ROOT / rel_path).exists(), f"{doc['path']} has missing {field}: {rel_path}"


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

    for rel_path in ["README.md", "AGENTS.md", "docs/AGENTS.md", "docs/总规则.md"]:
        assert PROJECT_DRIVER in (ROOT / rel_path).read_text(encoding="utf-8")


def test_archive_batch_lifecycle_and_mapping_are_exact() -> None:
    registry = load_registry()
    by_path = {doc["path"]: doc for doc in registry["documents"]}

    assert registry["archived_document_paths"] == ARCHIVE_MAP
    assert sum(1 for doc in registry["documents"] if doc["proposed_action"] == "archive") == 0
    assert sum(1 for doc in registry["documents"] if doc["proposed_action"] == "delete") == 0

    for old_path, new_path in ARCHIVE_MAP.items():
        assert not (ROOT / old_path).exists()
        assert (ROOT / new_path).is_file()
        doc = by_path[new_path]
        assert doc["document_type"] == "audit_record"
        assert doc["lifecycle_status"] == "historical"
        assert doc["proposed_action"] == "keep"
        assert doc["content_role"] == "historical_record"
        assert doc["placement_action"] == "keep_archive_exception"
        assert doc["human_confirmation_required"] is False

    for path in NEEDS_HUMAN_CONFIRMATION:
        doc = by_path[path]
        assert (ROOT / path).is_file()
        assert doc["lifecycle_status"] == "needs_human_confirmation"
        assert doc["proposed_action"] == "review"
        assert doc["placement_action"] == "review"
        assert doc["human_confirmation_required"] is True


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


def test_governance_report_exists_and_lists_candidate_classes() -> None:
    assert REPORT.is_file()
    content = REPORT.read_text(encoding="utf-8")
    for needle in [
        "### 内容角色统计",
        "### 推荐归置动作统计",
        "## 项目驱动文档",
        PROJECT_DRIVER,
        "## 7. 仅保留 exports 候选",
        "## 8. 已迁出 docs 的生成文档",
        "## 9. 需要拆分的混合文档",
        "## 10. 吸收后归档候选",
        "## 11. 内容归置待确认项",
        "## 12. 生命周期 archive candidates",
        "## 13. 生命周期 delete candidates",
        "## 14. 生命周期 review / needs human confirmation",
        "## 15. 已归档文档",
        "## 20. 后续执行批次",
        "当前治理报告仅描述 docs 生命周期、内容角色与推荐归置状态",
    ]:
        assert needle in content
    batch6 = content.split("Batch 6：needs-human-confirmation 历史材料", 1)[1].split("Batch 7：active design 语义核验", 1)[0]
    batch7 = content.split("Batch 7：active design 语义核验", 1)[1].split("## 21. 范围声明", 1)[0]
    assert "docs/manual_review_config_layer_design_20260620.md" not in batch6
    assert "docs/manual_review_config_layer_design_20260620.md" in batch7
    assert "data/configs/" in batch7
    assert not re.search(r"PR #\d+", content)
    assert "#207" not in content
    assert "本 PR" not in content
    for old_path, new_path in ARCHIVE_MAP.items():
        assert content.count(old_path) == 1
        assert content.count(new_path) >= 1
    for old_path, target_path in RETIRED_GENERATED_MAP.items():
        assert old_path in content
        assert target_path in content
    batch1 = content.split("Batch 1：generated docs -> export-only", 1)[1].split("Batch 2：混合审核文档拆分", 1)[0]
    assert "已完成" in batch1


def test_archive_readme_exists_and_links_batch_documents() -> None:
    readme = ROOT / "docs" / "archive" / "README.md"

    assert readme.is_file()
    content = readme.read_text(encoding="utf-8")
    for new_path in ARCHIVE_MAP.values():
        rel = new_path.removeprefix("docs/archive/")
        assert f"]({rel})" in content


def test_governance_report_matches_generator() -> None:
    docs_tool = load_docs_tool()

    assert REPORT.read_text(encoding="utf-8") == docs_tool.build_report("docs/agent_rules/docs_registry.json")


