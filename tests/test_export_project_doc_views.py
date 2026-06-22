from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export import export_project_doc_views as doc_views


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


def test_export_expanded_i5b_candidate_pool_docs_reads_chinese_person_pool_config(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "第五项B_人物池.json"
    config_path.write_text(
        json.dumps(
            [
                {
                    "person": "Temp Person",
                    "subitem": "第五项B",
                    "candidate_type": "Temp Type",
                    "why_selected": "Temp Why",
                    "expected_rule_pressure": "Temp Pressure",
                    "required_evidence_focus": "Temp Focus",
                    "adjacent_item_risk": "Temp Risk",
                    "negative_scan_focus": "Temp Negative",
                    "recommended_priority": "P9",
                }
            ],
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    doc_path = tmp_path / "docs" / "candidate-pool.md"
    export_path = tmp_path / "exports" / "candidate-pool.md"
    monkeypatch.setattr(doc_views.config_loaders, "I5B_PERSON_POOL_PATH", config_path)
    doc_views.CANDIDATE_POOL_DOC_PATH = doc_path
    doc_views.CANDIDATE_POOL_EXPORT_PATH = export_path

    rendered = doc_views.render_expanded_i5b_candidate_pool()
    assert "Temp Person" in rendered
    assert "Temp Type" in rendered
    assert "Temp Why" in rendered
    assert "P9" in rendered


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
