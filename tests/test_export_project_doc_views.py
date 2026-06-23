from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export import export_project_doc_views as doc_views


def test_export_global_scale_decision_brief_writes_canonical_export_only(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs" / "brief.md"
    export_path = tmp_path / "exports" / "brief.md"
    doc_views.GLOBAL_SCALE_BRIEF_EXPORT_PATH = export_path

    result_path = doc_views.export_global_scale_decision_brief()

    assert result_path == export_path
    assert not doc_path.exists()
    export_content = export_path.read_text(encoding="utf-8")
    assert "全局总标尺执行简报" in export_content
    assert "V3.2" in export_content
    assert "方案 C 是发布门槛和实施顺序" in export_content


def test_export_expanded_i5b_candidate_pool_reads_internal_defaults(
    tmp_path: Path, monkeypatch, project_config_writer
) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
    )
    monkeypatch.setattr(doc_views.config_loaders, "PROJECT_CONFIG_PATH", config_path)
    monkeypatch.setattr(
        doc_views.config_loaders,
        "default_i5b_candidate_pool_rows",
        lambda: [
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
    )

    export_path = tmp_path / "exports" / "candidate-pool.md"
    doc_views.CANDIDATE_POOL_EXPORT_PATH = export_path

    rendered = doc_views.render_expanded_i5b_candidate_pool()
    assert "Temp Person" in rendered
    assert "Temp Type" in rendered
    assert "Temp Why" in rendered
    assert "P9" in rendered


def test_export_expanded_i5b_candidate_pool_writes_canonical_export_only(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs" / "candidate-pool.md"
    export_path = tmp_path / "exports" / "candidate-pool.md"
    doc_views.CANDIDATE_POOL_EXPORT_PATH = export_path

    result_path = doc_views.export_expanded_i5b_candidate_pool()

    assert result_path == export_path
    assert not doc_path.exists()
    export_content = export_path.read_text(encoding="utf-8")
    assert "第五项B扩展试点候选池设计" in export_content
    assert "候选池按类型抽样，不按名气或预期高低抽样" in export_content
    assert "赵匡胤" in export_content
    assert "武则天" in export_content
    assert "recommended_priority" in export_content
