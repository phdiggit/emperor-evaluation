from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SCAFFOLD_SPEC = importlib.util.spec_from_file_location(
    "export_md_scaffold",
    ROOT / "scripts" / "export_md_scaffold.py",
)
assert SCAFFOLD_SPEC is not None
scaffold = importlib.util.module_from_spec(SCAFFOLD_SPEC)
sys.modules[SCAFFOLD_SPEC.name] = scaffold
assert SCAFFOLD_SPEC.loader is not None
SCAFFOLD_SPEC.loader.exec_module(scaffold)

NET_EVIDENCE_SPEC = importlib.util.spec_from_file_location(
    "export_i5b_net_evidence",
    ROOT / "scripts" / "export_i5b_net_evidence.py",
)
assert NET_EVIDENCE_SPEC is not None
net_evidence = importlib.util.module_from_spec(NET_EVIDENCE_SPEC)
sys.modules[NET_EVIDENCE_SPEC.name] = net_evidence
assert NET_EVIDENCE_SPEC.loader is not None
NET_EVIDENCE_SPEC.loader.exec_module(net_evidence)


def test_export_i5b_net_evidence_pool_renders_person_scoped_clusters_and_cards(tmp_path: Path) -> None:
    db_path = tmp_path / "evidence_cache.sqlite"
    export_path = tmp_path / "net-evidence.md"
    appendix_dir = tmp_path / "附录"
    net_evidence.DB_PATH = db_path
    net_evidence.APPENDIX_DIR = appendix_dir

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE evidence_clusters (
                person TEXT,
                subitem TEXT,
                polarity TEXT,
                candidate_strength INTEGER,
                cluster_id TEXT,
                raw_json TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE evidence_cards (
                person TEXT,
                subitem TEXT,
                polarity TEXT,
                strength INTEGER,
                evidence_id TEXT,
                raw_json TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO evidence_clusters (person, subitem, polarity, candidate_strength, cluster_id, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "测试人物",
                "第五项B",
                "positive",
                3,
                "CLUSTER-001",
                '{"cluster_id":"CLUSTER-001","person":"测试人物","subitem":"第五项B","polarity":"positive","cluster_type":"talent","linked_evidence_ids":["CARD-001"],"candidate_strength":3,"upper_probe":"none","adjudication_status":"pending","summary":"正向总结"}',
            ),
        )
        connection.execute(
            "INSERT INTO evidence_clusters (person, subitem, polarity, candidate_strength, cluster_id, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "其他人物",
                "第五项B",
                "positive",
                4,
                "CLUSTER-999",
                '{"cluster_id":"CLUSTER-999","person":"其他人物","subitem":"第五项B","polarity":"positive","cluster_type":"other","linked_evidence_ids":["CARD-999"],"candidate_strength":4,"upper_probe":"none","adjudication_status":"pending","summary":"不应出现"}',
            ),
        )
        connection.execute(
            "INSERT INTO evidence_cards (person, subitem, polarity, strength, evidence_id, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "测试人物",
                "第五项B",
                "positive",
                3,
                "CARD-001",
                json.dumps(
                    {
                        "evidence_id": "CARD-001",
                        "person": "测试人物",
                        "subitem": "第五项B",
                        "polarity": "positive",
                        "human_level": "强正",
                        "trigger_family": "任使",
                        "source_id": "SRC-001",
                        "quote_short": "引文|含分隔符",
                        "quote_context": "这是需要完整保留的上下文摘录，包含前因后果与后续限定，不能在表格内截断。",
                        "context_summary": "上下文说明该短摘必须结合前后事件才能定证。",
                        "context_scope": "同段前后两句",
                        "context_required": True,
                        "context_status": "source_verified",
                        "context_effect": "strengthen",
                        "source_locator": "测试卷一：测试传",
                        "adjudication_bridge": "该上下文说明任用行为与第五项B授权标签直接相关。",
                        "object_anchor": "对象A",
                        "evidence_role": "主证",
                        "mitigation_flag": "",
                        "upper_bound_flag": "",
                        "cluster_role": "core",
                        "cross_item_split": "无",
                        "scoring_effect": "正向",
                        "adjudication_status": "pending",
                        "strength": 3,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO evidence_cards (person, subitem, polarity, strength, evidence_id, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "其他人物",
                "第五项B",
                "negative",
                1,
                "CARD-999",
                '{"evidence_id":"CARD-999","person":"其他人物","subitem":"第五项B","polarity":"negative","human_level":"弱负","trigger_family":"其他","source_id":"SRC-999","quote_short":"不应出现","object_anchor":"对象B","evidence_role":"旁证","mitigation_flag":"","upper_bound_flag":"","cluster_role":"edge","cross_item_split":"有","scoring_effect":"负向","adjudication_status":"pending","strength":1}',
            ),
        )
        connection.execute(
            "INSERT INTO evidence_cards (person, subitem, polarity, strength, evidence_id, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "测试人物",
                "第五项B",
                "negative",
                1,
                "CARD-002",
                json.dumps(
                    {
                        "evidence_id": "CARD-002",
                        "person": "测试人物",
                        "subitem": "第五项B",
                        "polarity": "negative",
                        "human_level": "弱负",
                        "trigger_family": "回源测试",
                        "source_id": "SRC-002",
                        "quote_short": "单句不足",
                        "context_required": True,
                        "context_status": "pending",
                        "object_anchor": "对象C",
                        "evidence_role": "待定",
                        "mitigation_flag": "",
                        "upper_bound_flag": "",
                        "cluster_role": "edge",
                        "cross_item_split": "待回源后判断",
                        "scoring_effect": "待人工裁判",
                        "adjudication_status": "needs_more_source_review",
                        "strength": 1,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        connection.commit()

    result_path = net_evidence.export_i5b_net_evidence_pool("测试人物", export_path)

    content = result_path.read_text(encoding="utf-8")
    appendix_content = (appendix_dir / "测试人物_净证据池长字段附录.md").read_text(encoding="utf-8")
    assert result_path == export_path
    assert "# 第五项B_测试人物净证据池" in content
    assert "本文件为定档前净证据池视图" in content
    assert "| 证据簇ID（cluster_id） | 人物（person） | 方向（polarity） | 簇类型（cluster_type） | 关联证据ID（linked_evidence_ids） |" in content
    assert "| 证据ID（evidence_id） | 人物（person） | 方向（polarity） | 人工强度（human_level） | 触发类型（trigger_family） |" in content
    assert "CLUSTER-001" in content
    assert "CARD-001" in content
    assert "CARD-002" in content
    assert "[见附录：短摘（quote_short）]" in content
    assert "上下文摘录（quote_context）" in content
    assert "上下文摘要（context_summary）" in content
    assert "上下文范围（context_scope）" in content
    assert "上下文影响（context_effect）" in content
    assert "裁判桥接说明（adjudication_bridge）" in content
    assert "[见附录：上下文摘录（quote_context）]" in content
    assert "[见附录：上下文摘要（context_summary）]" in content
    assert "[见附录：裁判桥接说明（adjudication_bridge）]" in content
    assert "上下文处理队列（context_review_queue）" in content
    assert "需回源 / 需上下文" in content
    assert "引文|含分隔符" in appendix_content
    assert "这是需要完整保留的上下文摘录，包含前因后果与后续限定，不能在表格内截断。" in appendix_content
    assert "## card-001-quote_short" in appendix_content
    assert "## card-001-quote_context" in appendix_content
    assert "CLUSTER-999" not in content
    assert "CARD-999" not in content


def test_load_i5b_net_evidence_targets_prefers_chinese_view_group_config(
    tmp_path: Path, monkeypatch
) -> None:
    group_path = tmp_path / "第五项B_视图分组.json"
    group_path.write_text(
        json.dumps(
            [
                {
                    "group_id": "第五项B_净证据导出目标",
                    "group_name": "净证据导出目标",
                    "group_type": "导出人物组",
                    "subitem": "第五项B",
                    "persons": ["测试人物"],
                    "path_template": "exports/markdown_views/test-{person}.md",
                    "note": "测试",
                }
            ],
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(net_evidence.config_loaders, "I5B_VIEW_GROUPS_PATH", group_path)

    targets = net_evidence.load_i5b_net_evidence_targets()

    assert targets == [("测试人物", net_evidence.ROOT / "exports" / "markdown_views" / "test-测试人物.md")]
