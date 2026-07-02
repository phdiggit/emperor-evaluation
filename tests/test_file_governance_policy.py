from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from _git_helpers import changed_files_against_base, git_changed_files, skip_unless_pr_diff_checks_enabled

ALLOWED_CHANGED_FILES = {
    "README.md",
    "archive/docs/README.md",
    "db/schema.sql",
    "db/postgres/001_init.sql",
    "db/postgres/README.md",
    "db/postgres/bench_search.sql",
    "docs/AGENTS.md",
    "docs/README.md",
    "docs/项目总纲/README.md",
    "docs/项目总纲/总规则.md",
    "docs/数据结构与生成库/批次文件生命周期规则.md",
    "docs/证据规则/README.md",
    "docs/证据规则/史料检索与回源工作流.md",
    "docs/数据结构与生成库/SQLite生成库说明.md",
    "docs/数据结构与生成库/数据主表字段规范.md",
    "docs/数据结构与生成库/query_profile与search_log字段规范.md",
    "docs/数据结构与生成库/史料上下文管理机制.md",
    "docs/证据规则/证据链总流程与文档索引.md",
    "docs/证据规则/证据强度四级与五轴裁量规则.md",
    "docs/证据规则/证据裁量总则.md",
    "docs/证据规则/负证触发式裁判通用规则.md",
    "archive/docs/证据规则/证据链总流程与文档索引.md",
    "archive/docs/证据规则/证据强度四级与五轴裁量规则.md",
    "docs/数据结构与生成库/配置说明文件规范.md",
    "docs/分项规则/README.md",
    "docs/分项规则/第一项创业与政权取得能力/README.md",
    "docs/分项规则/第二项治国净收益/README.md",
    "docs/分项规则/第三项军事与边疆净收益/README.md",
    "docs/分项规则/第四项文明与国家整合收益/README.md",
    "docs/分项规则/第五项统治者政治素质/README.md",
    "docs/分项规则/第五项统治者政治素质/B用人与授权.md",
    "docs/分项规则/第六项关键历史决策能力/README.md",
    "docs/分项规则/第七项历史负债/README.md",
    "docs/展示与协作/README.md",
    "docs/展示与协作/GitHub发布与认证规范.md",
    "docs/展示与协作/scripts目录规范.md",
    "docs/展示与协作/人工阅读型Markdown导出规范.md",
    "archive/docs/adr/ADR-anchors-schema-proposal.md",
    "archive/docs/adr/ADR-formal-target-schema-draft.md",
    "archive/docs/adr/ADR-formal-migration-proposal.md",
    "archive/docs/adr/ADR-migration-sql-draft-renderer.md",
    "archive/docs/adr/ADR-schema-diff-draft-renderer.md",
    "archive/docs/adr/ADR-migration-bundle-review-pack.md",
    "archive/docs/adr/ADR-guarded-executable-migration-pr.md",
    "archive/docs/adr/ADR-schema-change-pr-prep-pack.md",
    "archive/docs/adr/ADR-schema-change-candidate-review-bundle.md",
    "archive/docs/adr/ADR-schema-change-approval-gate-package.md",
    "archive/docs/adr/ADR-schema-change-explicit-approval-request-handoff.md",
    "archive/docs/adr/ADR-schema-changing-formal-schema-update.md",
    "archive/docs/adr/ADR-production-schema-live-apply-entrypoint-guard.md",
    "archive/docs/adr/ADR-production-schema-live-apply-execution-pr-scaffold.md",
    "archive/docs/adr/ADR-production-schema-live-apply-execution-preflight.md",
    "archive/docs/adr/ADR-production-schema-live-apply-execution.md",
    "archive/docs/adr/ADR-production-seed-data-apply-execution.md",
    "archive/docs/adr/ADR-production-migration-freeze-checklist.md",
    "archive/docs/adr/ADR-production-migration-pr-scaffold.md",
    "archive/docs/adr/ADR-production-migration-dry-run-package.md",
    "archive/docs/adr/ADR-production-migration-pr-admission.md",
    "archive/docs/adr/ADR-jsonl-to-target-cutover-plan.md",
    "archive/docs/adr/ADR-platform-rollback-backup-seed-strategy.md",
    "archive/docs/adr/ADR-postgres-formal-migration-plan.md",
    "docs/数据结构与生成库/README.md",
    "docs/数据结构与生成库/稳定ID命名规范.md",
    "docs/数据结构与生成库/史源数据平台架构决策.md",
    "docs/数据结构与生成库/史源数据平台实现设计.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/docs_registry.json",
    "docs/文档与脚本登记/Post-G10脚本治理效果审计.md",
    "docs/文档与脚本登记/README.md",
    "docs/文档与脚本登记/scripts_registry.json",
    "exports/governance/文档治理盘点报告.md",
    "docs/数据结构与生成库/史源数据平台迁移决策.md",
    "docs/文档与脚本登记/docs_registry.json",
    "docs/文档与脚本登记/scripts_registry.json",
    "scripts/dev/docs_governance/constants.py",
    "scripts/dev/docs_governance/registry_check.py",
    "scripts/export/export_md.py",
    "tests/test_docs_governance.py",
    "tests/test_docs_tool.py",
    "tests/test_file_governance_policy.py",
    "tests/test_schema.py",
    "tests/test_postgres_schema_contract.py",
}

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def changed_files() -> set[str]:
    return (
        changed_files_against_base()
        | git_changed_files("diff", "--name-only")
        | git_changed_files("diff", "--cached", "--name-only")
    )


def git_check_ignore(paths: list[str]) -> set[str]:
    result = subprocess.run(
        ["git", "check-ignore", "--stdin", "--no-index"],
        cwd=ROOT,
        input=("\n".join(paths) + "\n").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    return set(result.stdout.decode("utf-8").splitlines())


def test_agents_md_contains_file_governance_rules() -> None:
    content = read_text(ROOT / "docs" / "AGENTS.md")
    for needle in [
        "展示优化不得改变源数据、评分、定档、排名、warning 语义或裁判结论",
        "人工复核型 Markdown 默认纯 Markdown，不用 HTML details",
        "细则见 `docs/展示与协作/人工阅读型Markdown导出规范.md`",
    ]:
        assert needle in content


def test_human_readable_markdown_spec_contains_detailed_rules() -> None:
    content = read_text(ROOT / "docs" / "展示与协作" / "人工阅读型Markdown导出规范.md")
    for needle in [
        "不使用 `<details>`、`<summary>`、`</details>`",
        "详情页不要使用宽表承载长字段、裁判说明、相邻项剥离说明、warning `matched_fields` 或 linked evidence 长字段",
        "`linked_*` 字段必须全量展示，不得隐藏",
        "`cross_item_split_signals / 相邻项剥离说明` 必须全量展示，不得隐藏",
        "warning `matched_fields / 命中字段` 必须全量展示，不得截断",
        "不使用 `……（共N项）` 或类似文案截断长列表",
        "详情页不要使用宽表承载长字段",
    ]:
        assert needle in content


def test_readme_mentions_governance_baseline_and_no_external_stack() -> None:
    content = read_text(ROOT / "README.md")
    assert "exports/governance/文档治理盘点报告.md" in content
    assert "archive/docs/" in content
    assert "当前不引入新的缓存或中间件" in content
    assert "PostgreSQL schema 已作为平台基线存在，但业务写源仍是 `data/*.jsonl`" in content
    assert "多余文件、归档候选和删除候选必须另开专门 Issue 处理" in content


def test_governance_rules_document_contains_batch_statuses_and_prerequisites() -> None:
    content = read_text(ROOT / "docs" / "数据结构与生成库" / "批次文件生命周期规则.md")
    for needle in [
        "active_batch",
        "review_only_batch",
        "merge_pending_batch",
        "archive_candidate",
        "delete_candidate",
        "needs_human_confirmation",
        "删除或归档前必须确认是否唯一数据源",
        "若文件仍被测试、脚本、导出、README、治理文档引用，不得删除",
        "第一轮只允许诊断，第二轮才允许小范围归档或删除",
        "后续应支持指定导出，避免全量重写",
        "PR 白名单外导出变更必须还原",
        "canonical branch / mergeable PR",
        "review branch / review PR",
        "默认不得包含 `exports/**` 生成物",
        "分支名使用 `review/*`",
        "`data/batches/*/source_evidence_specs.jsonl`",
        "`data/batches/*/source_review_log.jsonl`",
        "关键词补齐、补搜词、对象锚点扩展和相邻项切分线不得写入 `project_config.yml`",
        "正向、负向、相邻项 query lanes 的覆盖、转卡、未决和排除理由",
    ]:
        assert needle in content


def test_i5b_grading_rubric_guards_object_anchors_and_extreme_positive() -> None:
    content = read_text(ROOT / "docs" / "分项规则" / "第五项统治者政治素质" / "B用人与授权.md")
    for needle in [
        "第五项B当前计分链只认对象、史源、规则和公式因子",
        "`raw_objs` 保持原始对象粒度，不能合并加工",
        "每个 `raw_objs` 至少有一条 `obj_srcs` 史料链",
        "`talent_quality` 等对象属性必须来自 `obj_attrs`",
        "第五项B当前计算链为 `obj_srcs` / `obj_attrs` → `evd_clusters` / `evd_cluster_calc_details` → `emp_item_results` / `emp_item_result_calc_details`",
        "`calc_detail.covered_material_ids`、`scored_material_ids` 和 `supporting_material_ids`",
        "`query_profiles` / `data/query_profile_batches/**`",
        "`search_logs`",
        "`source_review_log`",
        "正向、负向、相邻项 query lanes 的覆盖、对象化、入库、未决和排除理由",
        "不得直接手写人物级分数或单人 override",
        "本公式不设置严重负向硬上限",
    ]:
        assert needle in content
    assert "刘恒当前已见材料" not in content


def test_file_governance_allowlist_has_no_one_off_migration_paths() -> None:
    allowed_archive_paths = {
        "archive/docs/README.md",
        "archive/docs/证据规则/证据链总流程与文档索引.md",
        "archive/docs/证据规则/证据强度四级与五轴裁量规则.md",
    }
    allowed_archive_prefixes = (
        "archive/docs/adr/",
    )
    forbidden_prefixes = (
        ".tmp/",
        "archive/docs/",
        "data/",
        "exports/markdown_views/",
    )
    forbidden_exact_paths = {
        "docs/文档治理盘点报告.md",
    }
    forbidden_fragments = (
        "_20260620",
        "_20260621",
    )

    offenders = {
        path
        for path in ALLOWED_CHANGED_FILES
        if path not in allowed_archive_paths
        and not path.startswith(allowed_archive_prefixes)
        and (path in forbidden_exact_paths
        or path.startswith(forbidden_prefixes)
        or any(fragment in path for fragment in forbidden_fragments))
    }

    assert offenders == set()


def test_gitignore_covers_generated_artifacts_without_hiding_sources() -> None:
    generated_paths = [
        "__pycache__/module.cpython-313.pyc",
        "scripts/export/__pycache__/export_md.cpython-313.pyc",
        ".pytest_cache/v/cache/nodeids",
        ".coverage",
        "coverage.xml",
        "htmlcov/index.html",
        ".mypy_cache/3.13/cache.db",
        ".ruff_cache/content",
        ".hypothesis/examples",
        ".tox/py313/.gitignore",
        ".nox/tests/tmp",
        ".venv/pyvenv.cfg",
        "venv/pyvenv.cfg",
        "ENV/pyvenv.cfg",
        "dist/package.whl",
        "build/temp.txt",
        "package.egg-info/PKG-INFO",
        "evidence_cache.sqlite",
        "evidence_cache.sqlite-journal",
        "local.db",
        "local.db-wal",
        "logs/test.log",
        "tmp-result.tmp",
        "backup.bak",
        ".tmp/export.md",
    ]
    source_paths = [
        "tests/test_new_policy.py",
        "scripts/build/new_builder.py",
        "scripts/export/new_exporter.py",
        "docs/展示与协作/tests目录规范.md",
        "data/events.jsonl",
        "exports/markdown_views/人工阅读视图.md",
    ]

    assert git_check_ignore(generated_paths) == set(generated_paths)
    assert git_check_ignore(source_paths) == set()


def test_pr_diff_stays_inside_issue_82_whitelist() -> None:
    skip_unless_pr_diff_checks_enabled()
    assert changed_files() <= ALLOWED_CHANGED_FILES
