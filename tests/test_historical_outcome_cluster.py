from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.historical_outcome_cluster import (
    assess_person_talent_grade,
    build_outcome_episode,
    cluster_semantic_fingerprint,
    validate_historical_outcome_registry,
)
from emperor_v4.evaluation.historical_quality_gold import (
    compare_historical_quality_gold_files,
    load_historical_quality_gold,
    verify_historical_quality_gold_sources,
)
from emperor_v4.adapters.source_text_index import (
    LocalSourceTextIndex,
    build_local_source_index,
)
from emperor_v4.evaluation.i5b_current_value_runner import (
    build_i5b_current_value,
    build_outcome_database_dry_run,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config/historical-outcome-cluster-registry.schema.json"
GOLD_SCHEMA = ROOT / "config/historical-quality-gold-manifest.schema.json"


@pytest.mark.parametrize("ruler", ["刘邦", "李世民"])
def test_current_outcomes_validate_and_have_deterministic_episodes(ruler: str) -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value" / ruler / "source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    facts = {row["record_ref"]: row for row in pack["facts"]}
    validation = validate_historical_outcome_registry(
        pack["outcome_registry"], schema_path=SCHEMA, facts=facts
    )
    assert validation["status"] == "passed"
    assert validation["kind_counts"]["campaign"] > 0
    assert validation["kind_counts"]["governance"] > 0
    for cluster in pack["outcome_registry"]["clusters"]:
        episode = build_outcome_episode(cluster, facts=facts)
        assert episode.episode_id == cluster["episode_refs"][0]
        assert episode.assertion_links


def test_outcome_identity_and_fact_lineage_fail_closed() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    registry = copy.deepcopy(pack["outcome_registry"])
    registry["clusters"][1]["independent_key"] = registry["clusters"][0][
        "independent_key"
    ]
    registry["clusters"][1]["outcome_kind"] = registry["clusters"][0][
        "outcome_kind"
    ]
    with pytest.raises(ValueError, match="重复"):
        validate_historical_outcome_registry(
            registry,
            schema_path=SCHEMA,
            facts={row["record_ref"]: row for row in pack["facts"]},
        )


def test_campaign_registry_separates_ruler_relation_land_axis_and_process_adversity() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    registry = copy.deepcopy(pack["outcome_registry"])
    campaign = next(
        row
        for row in registry["clusters"]
        if row["outcome_kind"] == "campaign"
        and any(member["actor_kind"] == "ruler" for member in row["members"])
        and any(member["actor_kind"] == "person" for member in row["members"])
    )
    ruler_member = next(
        member for member in campaign["members"] if member["actor_kind"] == "ruler"
    )
    ruler_member["ruler_campaign_relation"] = "personal_command"
    campaign["payload"].update(
        {
            "campaign_tier": "A",
            "campaign_tier_basis": "战略门户争夺，面对主要区域对手并取得阶段结果。",
            "land_strategic_value": "strategic_gateway",
            "process_adversity": "material",
            "process_adversity_basis": "阶段目标未全部实现，但已有战果仍可保留。",
        }
    )
    campaign["semantic_fingerprint"] = cluster_semantic_fingerprint(campaign)

    validation = validate_historical_outcome_registry(
        registry,
        schema_path=SCHEMA,
        facts={row["record_ref"]: row for row in pack["facts"]},
    )
    assert validation["status"] == "passed"

    invalid = copy.deepcopy(registry)
    invalid_campaign = next(
        row for row in invalid["clusters"] if row["outcome_ref"] == campaign["outcome_ref"]
    )
    person_member = next(
        member
        for member in invalid_campaign["members"]
        if member["actor_kind"] == "person"
    )
    person_member["ruler_campaign_relation"] = "authorized"
    invalid_campaign["semantic_fingerprint"] = cluster_semantic_fingerprint(
        invalid_campaign
    )
    with pytest.raises(ValueError, match="只有战役中的皇帝"):
        validate_historical_outcome_registry(
            invalid,
            schema_path=SCHEMA,
            facts={row["record_ref"]: row for row in pack["facts"]},
        )


def test_grade_reason_is_derived_from_registered_role_and_scale() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    hanxin = next(row for row in pack["members"] if row["person"] == "韩信")
    grade = assess_person_talent_grade(
        person_ref=hanxin["person_ref"],
        clusters=pack["outcome_registry"]["clusters"],
    )
    assert grade["grade"] == "top"
    assert "作为主帅" in grade["basis"]
    assert "S级战役群" in grade["basis"]
    assert len(grade["outcome_refs"]) == 3


def test_single_s_plus_main_command_establishes_top_grade() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    campaign = copy.deepcopy(
        next(
            cluster
            for cluster in pack["outcome_registry"]["clusters"]
            if cluster["outcome_kind"] == "campaign"
            and any(
                member["actor_kind"] == "person"
                and member["role_code"] in {"commander_in_chief", "principal_commander"}
                for member in cluster["members"]
            )
        )
    )
    member = next(
        member
        for member in campaign["members"]
        if member["actor_kind"] == "person"
        and member["role_code"] in {"commander_in_chief", "principal_commander"}
    )
    campaign["payload"]["campaign_tier"] = "S+"
    campaign["scale"]["decisiveness"] = "decisive"

    grade = assess_person_talent_grade(
        person_ref=member["actor_ref"],
        clusters=[campaign],
    )

    assert grade["grade"] == "top"
    assert grade["rule_path"] == "top_fallback"
    assert grade["outcome_refs"] == [campaign["outcome_ref"]]


def test_military_top_support_cannot_be_borrowed_from_governance() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    campaign = copy.deepcopy(
        next(
            cluster
            for cluster in pack["outcome_registry"]["clusters"]
            if cluster["outcome_kind"] == "campaign"
        )
    )
    governance = copy.deepcopy(
        next(
            cluster
            for cluster in pack["outcome_registry"]["clusters"]
            if cluster["outcome_kind"] == "governance"
        )
    )
    person_ref = "PERSON-TEST-DOMAIN-SEPARATION"
    campaign["members"] = [
        {
            "actor_ref": person_ref,
            "actor_name": "测试人物",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "contribution_scope": "独立军事成果",
        }
    ]
    campaign["payload"]["campaign_tier"] = "S-"
    campaign["stable_delivery"] = False
    campaign["important_method_or_legacy"] = False
    governance["members"] = [
        {
            "actor_ref": person_ref,
            "actor_name": "测试人物",
            "actor_kind": "person",
            "role_code": "lead",
            "contribution_scope": "独立治理成果",
        }
    ]
    governance["scale"]["level"] = "regional"
    governance["stable_delivery"] = False
    governance["important_method_or_legacy"] = False

    grade = assess_person_talent_grade(
        person_ref=person_ref,
        clusters=[campaign, governance],
    )

    assert grade["grade"] == "important"
    assert grade["rule_path"] == "domain_important_threshold"


def test_mixed_professional_result_keeps_talent_scope_distinct_from_ruler_net() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    dai_zhou = next(row for row in pack["members"] if row["person"] == "戴胄")
    grade = assess_person_talent_grade(
        person_ref=dai_zhou["person_ref"],
        clusters=pack["outcome_registry"]["clusters"],
    )

    assert grade["grade"] == "top"
    assert "专业目标已实现" in grade["basis"]
    assert "整体混合结果及跨领域代价另行结算" in grade["basis"]


@pytest.mark.parametrize("person", ["李靖", "李勣"])
def test_two_decisive_national_commands_activate_historic_path(person: str) -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    member = next(row for row in pack["members"] if row["person"] == person)
    grade = assess_person_talent_grade(
        person_ref=member["person_ref"],
        clusters=pack["outcome_registry"]["clusters"],
    )

    assert grade["grade"] == "historic"
    assert grade["rule_path"] == "military_exceptional_two_s_command"
    assert len(grade["outcome_refs"]) == 2


def test_zhenguan_law_responsibility_keeps_leads_above_clause_contributor() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    cluster = next(
        row
        for row in pack["outcome_registry"]["clusters"]
        if row["canonical_label"] == "贞观律令与刑罚体系修订"
    )
    roles = {row["actor_name"]: row["role_code"] for row in cluster["members"]}

    assert roles["房玄龄"] == "lead"
    assert roles["长孙无忌"] == "lead"
    assert roles["裴弘献"] == "governance_participant"
    assert "PFACT-LSM-ZHENGUAN-LAW-RESPONSIBILITY" in cluster["fact_refs"]
    assert next(row for row in pack["members"] if row["person"] == "房玄龄")[
        "effective_talent_grade"
    ] == "top"
    assert next(row for row in pack["members"] if row["person"] == "长孙无忌")[
        "effective_talent_grade"
    ] == "top"


@pytest.mark.parametrize("ruler", ["刘邦", "李世民"])
def test_database_dry_run_never_opens_or_writes_database(ruler: str) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    )
    dry_run = build_outcome_database_dry_run(report)
    assert dry_run["status"] == "ready_before_database_write"
    assert dry_run["database_connection_opened"] is False
    assert dry_run["database_write_count"] == 0
    assert dry_run["planned_current_rows"]["historical_outcome_clusters"] == report[
        "declarations"
    ]["historical_outcome_cluster_count"]


def test_lishimin_goguryeo_gold_exposes_current_campaign_chain_gaps() -> None:
    report = compare_historical_quality_gold_files(
        manifest_path=ROOT / "eval/historical_quality_gold/李世民.json",
        result_path=ROOT / "eval/i5b_current_value/李世民/result.json",
    )

    cases = {row["gold_ref"]: row for row in report["cases"]}
    assert report["status"] == "failed"
    assert report["comparison_mode"] == "post_run_gold_only"
    assert report["recall"]["major"] == {"matched": 3, "total": 6, "rate": 0.5}
    assert report["accepted_episode_precision"] is None
    assert cases["GOLD-LSM-CAMPAIGN-GOGURYEO-645"]["matched_refs"] == []
    assert cases["GOLD-LSM-CAMPAIGN-BAIYAN"]["matched_refs"] == []
    assert cases["GOLD-LSM-CAMPAIGN-ZHUBISHAN"]["matched_refs"] == []
    assert any(
        diff["kind"] == "parent_link"
        for diff in cases["GOLD-LSM-CAMPAIGN-ANSHI"]["differences"]
    )
    assert report["database_write_count"] == 0
    assert report["formal_score_write_count"] == 0


def test_gold_manifest_rejects_generated_outcome_identity_selector(tmp_path: Path) -> None:
    manifest = json.loads(
        (ROOT / "eval/historical_quality_gold/李世民.json").read_text(
            encoding="utf-8"
        )
    )
    manifest["cases"][0]["selector"]["outcome_ref"] = "OUTCOME-CURRENT"
    path = tmp_path / "invalid-gold.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="额外字段|outcome_ref"):
        load_historical_quality_gold(path, schema_path=GOLD_SCHEMA)


def test_gold_source_verification_requires_same_revision_and_exact_quote(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷198",
                "work_title": "資治通鑑",
                "source_url": "fixture://tongjian-198",
                "revision_ref": "1502841",
                "raw_text": "六月，丁酉，李世勣攻白巖城西南，上臨其西北。",
            }
        ],
        index_path,
    )
    manifest = {
        "ruler": "李世民",
        "scope_code": "fixture",
        "cases": [
            {
                "source_refs": [
                    "資治通鑑/卷198@1502841#六月，丁酉，李世勣攻白巖城西南，上臨其西北。",
                    "資治通鑑/卷198@wrong#不存在的句子",
                ]
            }
        ],
    }

    report = verify_historical_quality_gold_sources(
        manifest, source_index=LocalSourceTextIndex(index_path)
    )

    assert report["status"] == "failed"
    assert report["verified_count"] == 1
    assert report["sources"][1]["errors"] == [
        "revision_mismatch",
        "exact_quote_missing",
    ]
    assert report["database_write_count"] == 0
