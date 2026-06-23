from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export import export_i5b_expanded_batch1 as expanded_batch1


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_export_expanded_i5b_batch1_review_falls_back_to_batch_files_and_sorts_rows(tmp_path: Path) -> None:
    export_path = tmp_path / "review.md"
    evidence_batch_path = tmp_path / "evidence.jsonl"
    cluster_batch_path = tmp_path / "clusters.jsonl"

    expanded_batch1.DB_PATH = tmp_path / "missing.sqlite"
    expanded_batch1.EXPANDED_BATCH1_REVIEW_EXPORT_PATH = export_path
    expanded_batch1.EVIDENCE_CARDS_PATH = evidence_batch_path
    expanded_batch1.EVIDENCE_CLUSTERS_PATH = cluster_batch_path

    write_jsonl(
        evidence_batch_path,
        [
            {
                "evidence_id": "EVD-ZZ-NEG-001",
                "person": "朱元璋",
                "subitem": "第五项B",
                "polarity": "negative",
                "strength": 1,
                "human_level": "弱负",
                "source_id": "SRC-3",
                "quote_short": "后置",
                "object_anchor": "对象3",
                "evidence_role": "旁证",
                "cluster_candidate_id": "CLUSTER-ZZ",
                "cross_item_split": "有",
                "scoring_effect": "负向",
                "verification_status": "source_verified",
                "adjudication_status": "pending",
            },
            {
                "evidence_id": "EVD-LB-POS-002",
                "person": "刘邦",
                "subitem": "第五项B",
                "polarity": "positive",
                "strength": 1,
                "human_level": "中正",
                "source_id": "SRC-2",
                "quote_short": "较弱正向",
                "object_anchor": "对象2",
                "evidence_role": "辅证",
                "cluster_candidate_id": "CLUSTER-LB",
                "cross_item_split": "无",
                "scoring_effect": "正向",
                "verification_status": "source_verified",
                "adjudication_status": "pending",
            },
            {
                "evidence_id": "EVD-LB-POS-001",
                "person": "刘邦",
                "subitem": "第五项B",
                "polarity": "positive",
                "strength": 3,
                "human_level": "强正",
                "source_id": "SRC-1",
                "quote_short": "较强正向",
                "object_anchor": "对象1",
                "evidence_role": "主证",
                "cluster_candidate_id": "CLUSTER-LB",
                "cross_item_split": "无",
                "scoring_effect": "正向",
                "verification_status": "source_verified",
                "adjudication_status": "pending",
            },
        ],
    )
    write_jsonl(
        cluster_batch_path,
        [
            {
                "cluster_id": "CLUSTER-ZZ",
                "person": "朱元璋",
                "subitem": "第五项B",
                "polarity": "negative",
                "linked_evidence_ids": ["EVD-ZZ-NEG-001"],
                "summary": "后置簇",
                "five_axis_assessment": "五轴3",
                "candidate_strength": 1,
                "upper_probe": "none",
                "cross_item_split": "有",
                "adjudication_status": "pending",
                "status": "batch_draft",
            },
            {
                "cluster_id": "CLUSTER-LB-B",
                "person": "刘邦",
                "subitem": "第五项B",
                "polarity": "positive",
                "linked_evidence_ids": ["EVD-LB-POS-002"],
                "summary": "较弱正向簇",
                "five_axis_assessment": "五轴2",
                "candidate_strength": 1,
                "upper_probe": "none",
                "cross_item_split": "无",
                "adjudication_status": "pending",
                "status": "batch_draft",
            },
            {
                "cluster_id": "CLUSTER-LB-A",
                "person": "刘邦",
                "subitem": "第五项B",
                "polarity": "positive",
                "linked_evidence_ids": ["EVD-LB-POS-001"],
                "summary": "较强正向簇",
                "five_axis_assessment": "五轴1",
                "candidate_strength": 3,
                "upper_probe": "none",
                "cross_item_split": "无",
                "adjudication_status": "pending",
                "status": "batch_draft",
            },
        ],
    )

    result_path = expanded_batch1.export_expanded_i5b_batch1_review()

    content = result_path.read_text(encoding="utf-8")
    cluster_section = content.split("## 证据簇", 1)[1]
    assert result_path == export_path
    assert "# 第五项B扩展试点第一批证据卡与证据簇草案" in content
    assert content.index("EVD-LB-POS-001") < content.index("EVD-LB-POS-002")
    assert content.index("EVD-LB-POS-002") < content.index("EVD-ZZ-NEG-001")
    assert cluster_section.index("CLUSTER-LB-A") < cluster_section.index("CLUSTER-LB-B")
    assert cluster_section.index("CLUSTER-LB-B") < cluster_section.index("CLUSTER-ZZ")


def test_load_expanded_batch1_persons_reads_project_config(
    tmp_path: Path, monkeypatch, project_config_writer
) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        view_groups=[
            {
                "group_id": "第五项B_扩展第一批",
                "group_name": "扩展第一批",
                "group_type": "扩展人物组",
                "subitem": "第五项B",
                "persons": ["甲", "乙"],
                "note": "测试",
            }
        ],
    )
    monkeypatch.setattr(expanded_batch1.config_loaders, "PROJECT_CONFIG_PATH", config_path)

    persons = expanded_batch1.load_expanded_batch1_persons()

    assert persons == ["甲", "乙"]


def test_export_expanded_i5b_batch1_targeted_supplement_renders_counts_and_sweep_lists(tmp_path: Path) -> None:
    export_path = tmp_path / "supplement.md"
    source_batch_path = tmp_path / "sources.jsonl"
    evidence_batch_path = tmp_path / "evidence.jsonl"
    sweep_batch_path = tmp_path / "sweep.jsonl"

    expanded_batch1.TARGETED_SUPPLEMENT_EXPORT_PATH = export_path
    expanded_batch1.TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH = source_batch_path
    expanded_batch1.TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH = evidence_batch_path
    expanded_batch1.TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_BATCH_PATH = sweep_batch_path

    write_jsonl(
        source_batch_path,
        [
            {
                "source_id": "SRC-TS-001",
                "title": "补证来源",
                "author": "作者",
                "dynasty": "朝代",
                "volume": "卷一",
                "location": "位置A",
                "url": "https://example.test/source",
                "note": "说明",
            }
        ],
    )
    write_jsonl(
        evidence_batch_path,
        [
            {
                "evidence_id": "EVD-LB-SUPP-001",
                "person": "刘邦",
                "polarity": "positive",
                "strength": 2,
                "human_level": "中正",
                "source_id": "SRC-TS-001",
                "quote_short": "补证引文",
                "object_anchor": "对象A",
                "evidence_role": "主证",
                "cluster_candidate_id": "ADJ-001",
                "supplement_gap_addressed": "缺口A",
                "supplement_for_adjudication_id": "ADJ-001",
                "verification_status": "source_verified",
                "adjudication_status": "pending",
            }
        ],
    )
    write_jsonl(
        sweep_batch_path,
        [
            {
                "sweep_id": "SWEEP-001",
                "item": "第五项",
                "subitem": "第五项B",
                "role_class": "督抚",
                "candidate_people": ["甲", "乙"],
                "carded_people": ["甲"],
                "linked_evidence_ids": ["EVD-LB-SUPP-001"],
                "not_carded_people": ["乙"],
                "not_carded_reason": "未回源",
                "source_status": "checked",
                "fifth_b_relevance": "high",
                "adjacent_item_risk": "medium",
                "status": "done",
            }
        ],
    )

    result_path = expanded_batch1.export_expanded_i5b_batch1_targeted_supplement()

    content = result_path.read_text(encoding="utf-8")
    assert result_path == export_path
    assert "# 第五项B扩展试点第一批定向补证" in content
    assert "| 刘邦 | 1 |" in content
    assert "| 雍正 | 0 |" in content
    assert "| 朱元璋 | 0 |" in content
    assert "甲" in content
    assert "乙" in content
    assert "EVD-LB-SUPP-001" in content
    assert "结语：不定档，不出分，不排名，不出总榜。" in content
