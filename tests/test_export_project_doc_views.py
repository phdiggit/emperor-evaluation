from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCAFFOLD_SPEC = importlib.util.spec_from_file_location(
    "export_md_scaffold",
    ROOT / "scripts" / "export_md_scaffold.py",
)
assert SCAFFOLD_SPEC is not None
scaffold = importlib.util.module_from_spec(SCAFFOLD_SPEC)
sys.modules[SCAFFOLD_SPEC.name] = scaffold
assert SCAFFOLD_SPEC.loader is not None
SCAFFOLD_SPEC.loader.exec_module(scaffold)

DOC_VIEWS_SPEC = importlib.util.spec_from_file_location(
    "export_project_doc_views",
    ROOT / "scripts" / "export_project_doc_views.py",
)
assert DOC_VIEWS_SPEC is not None
doc_views = importlib.util.module_from_spec(DOC_VIEWS_SPEC)
sys.modules[DOC_VIEWS_SPEC.name] = doc_views
assert DOC_VIEWS_SPEC.loader is not None
DOC_VIEWS_SPEC.loader.exec_module(doc_views)


def test_export_global_scale_decision_brief_docs_dual_writes_identical_content(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs" / "brief.md"
    export_path = tmp_path / "exports" / "brief.md"
    doc_views.GLOBAL_SCALE_BRIEF_DOC_PATH = doc_path
    doc_views.GLOBAL_SCALE_BRIEF_EXPORT_PATH = export_path

    result_paths = doc_views.export_global_scale_decision_brief_docs()

    doc_content = doc_path.read_text(encoding="utf-8")
    export_content = export_path.read_text(encoding="utf-8")
    assert result_paths == (doc_path, export_path)
    assert doc_content == export_content
    assert "全局总标尺决策简报" in doc_content
    assert "方案 C 已规则级确认" in doc_content
    assert "推荐的下一步规则确认顺序" in doc_content


def test_export_expanded_i5b_candidate_pool_docs_dual_writes_identical_content(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs" / "candidate-pool.md"
    export_path = tmp_path / "exports" / "candidate-pool.md"
    doc_views.CANDIDATE_POOL_DOC_PATH = doc_path
    doc_views.CANDIDATE_POOL_EXPORT_PATH = export_path

    result_paths = doc_views.export_expanded_i5b_candidate_pool_docs()

    doc_content = doc_path.read_text(encoding="utf-8")
    export_content = export_path.read_text(encoding="utf-8")
    assert result_paths == (doc_path, export_path)
    assert doc_content == export_content
    assert "第五项B扩展试点候选池设计" in doc_content
    assert "候选池按类型抽样，不按名气或预期高低抽样" in doc_content
    assert "赵匡胤" in doc_content
    assert "武则天" in doc_content
    assert "recommended_priority" in doc_content
