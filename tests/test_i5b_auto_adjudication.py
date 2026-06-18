import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AUTO_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人自动结算草案.md"
AUTO_RULES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B自动结算规则敏感点清单.md"
FORMAL_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人正式定档落地表.md"

AUTO_SPEC = importlib.util.spec_from_file_location(
    "export_i5b_auto_adjudication",
    ROOT / "scripts" / "export_i5b_auto_adjudication.py",
)
assert AUTO_SPEC is not None
auto = importlib.util.module_from_spec(AUTO_SPEC)
assert AUTO_SPEC.loader is not None
AUTO_SPEC.loader.exec_module(auto)


def run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def make_card(
    *,
    evidence_id: str,
    person: str,
    polarity: str,
    strength: int,
    object_anchor: str,
    evidence_role: str,
    trigger_family: str,
    quote_short: str,
    mitigation_flag: str = "",
    upper_bound_flag: str = "",
    cluster_role: str = "正向核心",
    cross_item_split: str = "本项直接证据",
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "person": person,
        "item": "第五项",
        "subitem": "第五项B",
        "polarity": polarity,
        "strength": strength,
        "human_level": "强正" if polarity == "positive" and strength >= 3 else "中正" if polarity == "positive" else "中负" if strength == 2 else "弱负",
        "source_id": f"SRC-{evidence_id}",
        "quote_short": quote_short,
        "interpretation": quote_short,
        "trigger_family": trigger_family,
        "trigger_terms": [trigger_family],
        "cross_item_split": cross_item_split,
        "scoring_effect": "测试用候选证据；不得直接入分，待人工裁判。",
        "verification_status": "source_verified",
        "case_classification": "other",
        "risk_status": "not_applicable",
        "mitigating_factors": [],
        "aggravating_factors": [],
        "reversal_or_rehabilitation": [],
        "adjudication_status": "source_verified_pending_human_adjudication",
        "object_anchor": object_anchor,
        "evidence_role": evidence_role,
        "mitigation_flag": mitigation_flag,
        "upper_bound_flag": upper_bound_flag,
        "cluster_role": cluster_role,
    }


def make_cluster(
    *,
    cluster_id: str,
    person: str,
    polarity: str,
    linked_evidence_ids: list[str],
    candidate_strength: int,
    summary: str,
    cluster_type: str = "talent_ecosystem",
    cross_item_split: str = "本项直接证据",
) -> dict[str, object]:
    return {
        "cluster_id": cluster_id,
        "person": person,
        "item": "第五项",
        "subitem": "第五项B",
        "cluster_type": cluster_type,
        "polarity": polarity,
        "linked_evidence_ids": linked_evidence_ids,
        "summary": summary,
        "five_axis_assessment": {"directness": "high"},
        "candidate_strength": candidate_strength,
        "upper_probe": "pending",
        "cross_item_split": cross_item_split,
        "adjudication_status": "source_verified_pending_human_adjudication",
        "note": "",
    }


@pytest.fixture()
def temp_auto_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    export_dir = tmp_path / "exports" / "markdown_views"
    export_dir.mkdir(parents=True)

    targets = ["测试甲"]
    config_path = tmp_path / "i5b_trial_targets.json"
    config_path.write_text(
        json.dumps({"item": "第五项", "subitem": "第五项B", "targets": targets}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(auto, "DATA_DIR", data_dir)
    monkeypatch.setattr(auto, "CONFIG_PATH", config_path)
    monkeypatch.setattr(auto, "EXPORT_PATH", export_dir / "第五项B三人自动结算草案.md")
    monkeypatch.setattr(auto, "RULES_EXPORT_PATH", export_dir / "第五项B自动结算规则敏感点清单.md")

    return data_dir


def build_temp_auto_dataset(
    data_dir: Path,
    cards: list[dict[str, object]],
    clusters: list[dict[str, object]],
) -> None:
    write_jsonl(data_dir / "evidence_cards.jsonl", cards)
    write_jsonl(data_dir / "evidence_clusters.jsonl", clusters)


def test_export_i5b_auto_adjudication_generates_rule_views() -> None:
    result = run_script("export_i5b_auto_adjudication.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert AUTO_EXPORT_PATH.exists()
    assert AUTO_RULES_EXPORT_PATH.exists()
    assert FORMAL_EXPORT_PATH.exists()

    auto_content = AUTO_EXPORT_PATH.read_text(encoding="utf-8")
    rules_content = AUTO_RULES_EXPORT_PATH.read_text(encoding="utf-8")
    formal_content = FORMAL_EXPORT_PATH.read_text(encoding="utf-8")

    assert "第五项B三人自动结算草案" in auto_content
    assert "negative_boundary_tier" in auto_content
    assert "negative_boundary_blocking" in auto_content
    assert "weak_to_medium" in auto_content
    assert "medium_to_strong" in auto_content
    assert "高位强正，上探极正候选" in auto_content
    assert "强正受压制，不上探极正" in auto_content
    assert "中正受中负压制" in auto_content
    assert "RULE-I5B-BOUNDARY-WEAK-TO-MEDIUM" in rules_content
    assert "RULE-I5B-BOUNDARY-MEDIUM-TO-STRONG" in rules_content
    assert "RULE-I5B-SINGLE-DIMENSION-STRONG-POS-THREE-CORE" in rules_content
    assert "RULE-I5B-ADJACENT-STRONG-NEG-RESIDUAL-DETAIL" in rules_content
    assert "RULE-I5B-STRONG-NEG-CORE-SUPPRESSES-STRONG-POS" in rules_content
    assert "第五项B三人正式定档落地表" in formal_content
    assert "formal_band_draft" in formal_content
    assert "not_scored_flag" in formal_content
    assert "ranking_suppressed_flag" in formal_content
    assert "score_stage_prerequisites" in formal_content
    assert "需另建第五项B档位到分值映射，并经规则级确认；本表不得直接推分。" in formal_content
    assert "| score |" not in formal_content
    assert "| ranking |" not in formal_content
    assert "| rank |" not in formal_content
    assert "李世民" in formal_content and "极正候选 / 高位强正上探极正" in formal_content
    assert "刘秀" in formal_content and "强正受压制" in formal_content
    assert "刘庄" in formal_content and "中正受中负压制" in formal_content


def test_real_data_reflects_issue46_rule_decisions() -> None:
    config = auto.read_json(auto.CONFIG_PATH)
    evidence_cards = auto.read_jsonl(auto.DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = auto.read_jsonl(auto.DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    reports = {
        person: auto.evaluate_person(person, evidence_clusters, evidence_lookup)
        for person in config["targets"]
    }
    cluster_lookup = {row["cluster_id"]: row for row in evidence_clusters if row.get("cluster_id")}

    assert reports["李世民"]["auto_band_direction"] == "高位强正，上探极正候选"
    assert reports["李世民"]["negative_boundary_tier"] == "weak_to_medium"
    assert reports["李世民"]["negative_boundary_blocking"] is False
    assert reports["李世民"]["rule_sensitive_points"] == [
        {
            "rule": "弱负上调中负边界",
            "decision": "不阻断极正或高位上探；只降低置信度，不进入强负核心。",
        }
    ]

    assert reports["刘秀"]["auto_band_direction"] == "强正受压制，不上探极正"
    assert reports["刘秀"]["negative_boundary_tier"] == "medium_to_strong"
    assert reports["刘秀"]["negative_boundary_blocking"] is True
    assert reports["刘秀"]["rule_sensitive_points"] == [
        {
            "rule": "中负上调强负边界",
            "decision": "阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。",
        },
        {
            "rule": "强负核心压制强正",
            "decision": "保留强正基础，但自动标记为强正受压制，不上探极正。",
        },
    ]

    assert reports["刘庄"]["auto_band_direction"] == "中正受中负压制"
    assert reports["刘庄"]["negative_boundary_tier"] == "adjacent_item_medium_residual"
    assert reports["刘庄"]["cross_item_split_residual_level"] == "medium"
    assert reports["刘庄"]["rule_sensitive_points"] == [
        {
            "rule": "相邻项主导剥离",
            "decision": "大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。",
        },
        {
            "rule": "B项剩余默认中负",
            "decision": "默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。",
        },
    ]

    liuzhuang_cluster = auto.evaluate_cluster(
        cluster_lookup["ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001"],
        evidence_lookup,
    )
    assert liuzhuang_cluster["residual_level"] == "medium"
    assert liuzhuang_cluster["boundary_tier"] == "adjacent_item_medium_residual"
    assert liuzhuang_cluster["auto_cluster_result"] == "中负边界"


def test_formal_landing_table_reflects_auto_drafts() -> None:
    result = run_script("export_i5b_auto_adjudication.py")

    assert result.returncode == 0, result.stdout + result.stderr
    formal_content = FORMAL_EXPORT_PATH.read_text(encoding="utf-8")

    assert "person | auto_band_direction | formal_band_draft" in formal_content
    assert "李世民 | 高位强正，上探极正候选 | 极正候选 / 高位强正上探极正" in formal_content
    assert "刘秀 | 强正受压制，不上探极正 | 强正受压制" in formal_content
    assert "刘庄 | 中正受中负压制 | 中正受中负压制" in formal_content
    assert "remaining_rule_questions" in formal_content
    assert "score_stage_prerequisites" in formal_content
    assert "not_scored_flag" in formal_content
    assert "ranking_suppressed_flag" in formal_content


def test_weak_boundary_negative_does_not_block_extreme(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
            upper_bound_flag="不得因战功上探",
            mitigation_flag="不回填后效",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
            upper_bound_flag="不得因战功上探",
            mitigation_flag="不回填后效",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
            upper_bound_flag="不得因战功上探",
            mitigation_flag="不回填后效",
        ),
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=1,
            object_anchor="边界负证",
            evidence_role="弱负边界",
            trigger_family="疑忌杀害",
            quote_short="轻微外溢，不成寒意",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探中负",
            cluster_role="边界负证",
            cross_item_split="事件主因切第五项C/D",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单维强正三核心",
        ),
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=1,
            summary="弱负升中负边界",
            cluster_type="talent_security",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)
    cluster = auto.evaluate_cluster(clusters[1], evidence_lookup)

    assert report["auto_band_direction"] == "高位强正，上探极正候选"
    assert report["confidence"] == "high_mid"
    assert report["negative_boundary_tier"] == "weak_to_medium"
    assert report["negative_boundary_blocking"] is False
    assert cluster["residual_level"] == "weak"
    assert cluster["boundary_tier"] == "weak_to_medium"
    assert cluster["auto_cluster_result"] == "弱负边界"


def test_medium_boundary_negative_blocks_extreme_and_becomes_core(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
        ),
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="中负边界",
            trigger_family="容谏纳言",
            quote_short="群臣莫敢正言",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探强负",
            cluster_role="边界负证",
            cross_item_split="表达安全直接受损",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单维强正三核心",
        ),
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="中负升强负边界",
            cluster_type="talent_security",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)
    cluster = auto.evaluate_cluster(clusters[1], evidence_lookup)

    assert report["auto_band_direction"] == "强正受压制，不上探极正"
    assert report["negative_boundary_tier"] == "medium_to_strong"
    assert report["negative_boundary_blocking"] is True
    assert report["has_strong_negative_core"] is True
    assert cluster["residual_level"] == "strong"
    assert cluster["boundary_tier"] == "medium_to_strong"
    assert cluster["blocking_extreme"] is True
    assert cluster["negative_core"] is True
    assert cluster["auto_cluster_result"] == "强负候选"


def test_single_dimension_three_strong_positives_can_probe_extreme(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单一维度三强正核心",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)

    assert report["single_dimension_flag"] is True
    assert report["strong_positive_count"] == 3
    assert report["auto_band_direction"] == "高位强正，上探极正候选"
    assert report["confidence"] == "high"


def test_single_dimension_below_three_strong_positives_is_capped(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002"],
            candidate_strength=3,
            summary="单一维度两强正核心",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)

    assert report["single_dimension_flag"] is True
    assert report["strong_positive_count"] == 2
    assert report["auto_band_direction"] == "强正封顶，不上探极正"
    assert report["confidence"] == "medium_high"


def test_adjacent_item_strong_negative_defaults_to_medium_residual(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=3,
            object_anchor="楚狱边界负证",
            evidence_role="强负核心",
            trigger_family="疑忌杀害",
            quote_short="楚獄遂至累年，其辭語相連，坐死徙者以千數。",
            mitigation_flag="剥离政权安全与司法严酷",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="宗室控制、司法严酷、政治残酷性切相邻项",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=3,
            summary="大案剥离后的中负残余",
            cluster_type="talent_security_and_political_implication_risk",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    cluster = auto.evaluate_cluster(clusters[0], evidence_lookup)

    assert cluster["residual_level"] == "medium"
    assert cluster["boundary_tier"] == "adjacent_item_medium_residual"
    assert cluster["blocking_extreme"] is False
    assert cluster["auto_cluster_result"] == "中负边界"


def test_direct_expression_hard_evidence_keeps_strong_negative_core(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="强负核心",
            trigger_family="容谏纳言",
            quote_short="群臣莫敢正言",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="表达安全直接受损",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="表达安全硬证",
            cluster_type="remonstrance_safety_and_expression_risk",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    cluster = auto.evaluate_cluster(clusters[0], evidence_lookup)

    assert cluster["residual_level"] == "strong"
    assert cluster["boundary_tier"] == "medium_to_strong"
    assert cluster["blocking_extreme"] is True
    assert cluster["negative_core"] is True
    assert cluster["auto_cluster_result"] == "强负候选"


def test_extended_direct_safety_keywords_cover_variants(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="强负核心",
            trigger_family="容谏纳言",
            quote_short="人才退缩，授权可信度破坏，表达入口被破坏",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="表达安全直接受损",
        )
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="寒蝉与授权可信度破坏",
            cluster_type="remonstrance_safety_and_expression_risk",
        )
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    cluster = auto.evaluate_cluster(clusters[0], evidence_lookup)

    assert auto.has_direct_safety_hard_evidence(cards) is True
    assert cluster["boundary_tier"] == "medium_to_strong"
    assert cluster["blocking_extreme"] is True
    assert cluster["negative_core"] is True


def test_strong_positive_base_with_strong_negative_core_is_suppressed(temp_auto_data: Path) -> None:
    cards = [
        make_card(
            evidence_id="EVD-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证一",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-002",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证二",
        ),
        make_card(
            evidence_id="EVD-TEST-POS-003",
            person="测试甲",
            polarity="positive",
            strength=3,
            object_anchor="创业期军政授权",
            evidence_role="强正核心",
            trigger_family="授权专任",
            quote_short="测试正证三",
        ),
        make_card(
            evidence_id="EVD-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            strength=2,
            object_anchor="表达安全边界",
            evidence_role="强负核心",
            trigger_family="容谏纳言",
            quote_short="群臣莫敢正言",
            mitigation_flag="剥离相邻项",
            upper_bound_flag="不得上探极负",
            cluster_role="强负核心",
            cross_item_split="表达安全直接受损",
        ),
    ]
    clusters = [
        make_cluster(
            cluster_id="ADJ-TEST-POS-001",
            person="测试甲",
            polarity="positive",
            linked_evidence_ids=["EVD-TEST-POS-001", "EVD-TEST-POS-002", "EVD-TEST-POS-003"],
            candidate_strength=3,
            summary="单一维度三强正核心",
        ),
        make_cluster(
            cluster_id="ADJ-TEST-NEG-001",
            person="测试甲",
            polarity="negative",
            linked_evidence_ids=["EVD-TEST-NEG-001"],
            candidate_strength=2,
            summary="强负核心压制强正",
            cluster_type="remonstrance_safety_and_expression_risk",
        ),
    ]
    build_temp_auto_dataset(temp_auto_data, cards, clusters)

    evidence_lookup = {row["evidence_id"]: row for row in cards}
    report = auto.evaluate_person("测试甲", clusters, evidence_lookup)

    assert report["auto_band_direction"] == "强正受压制，不上探极正"
    assert report["negative_boundary_tier"] == "medium_to_strong"
    assert report["negative_boundary_blocking"] is True
    assert report["has_strong_negative_core"] is True
