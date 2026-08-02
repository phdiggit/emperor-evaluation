from __future__ import annotations

import copy
from hashlib import sha256
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
    compare_historical_quality_gold,
    compare_historical_quality_gold_files,
    load_historical_quality_gold,
    run_historical_quality_gold_blind_gate,
    verify_historical_quality_gold_sources,
)
from emperor_v4.evaluation.historical_outcome_registry import (
    load_configured_dynasty_outcome_packs,
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


@pytest.mark.parametrize("ruler", ["刘邦", "李世民", "李渊"])
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
    assert validation["kind_counts"]["statecraft"] == {
        "刘邦": 5,
        "李世民": 1,
        "李渊": 1,
    }[ruler]
    for cluster in pack["outcome_registry"]["clusters"]:
        episode = build_outcome_episode(cluster, facts=facts)
        assert episode.episode_id == cluster["episode_refs"][0]
        assert episode.assertion_links
        if cluster["outcome_kind"] == "governance":
            judgment = cluster["payload"]["value_judgment"]
            assert judgment["overall_direction"] == cluster["result_direction"]
            assert judgment["basis"]


def test_outcome_identity_and_fact_lineage_fail_closed() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    registry = copy.deepcopy(pack["outcome_registry"])
    same_kind = [
        row for row in registry["clusters"] if row["outcome_kind"] == "campaign"
    ][:2]
    same_kind[1]["independent_key"] = same_kind[0]["independent_key"]
    with pytest.raises(ValueError, match="重复"):
        validate_historical_outcome_registry(
            registry,
            schema_path=SCHEMA,
            facts={row["record_ref"]: row for row in pack["facts"]},
        )


def test_governance_value_judgment_must_match_result_direction() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    registry = copy.deepcopy(pack["outcome_registry"])
    governance = next(
        row for row in registry["clusters"] if row["outcome_kind"] == "governance"
    )
    governance["payload"]["value_judgment"]["overall_direction"] = "negative"
    governance["semantic_fingerprint"] = cluster_semantic_fingerprint(governance)
    with pytest.raises(ValueError, match="价值方向与成果方向不一致"):
        validate_historical_outcome_registry(
            registry,
            schema_path=SCHEMA,
            facts={row["record_ref"]: row for row in pack["facts"]},
        )


def test_tang_governance_progress_calibrations_are_pinned() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    governance = {
        row["canonical_label"]: row
        for row in pack["outcome_registry"]["clusters"]
        if row["outcome_kind"] == "governance"
    }
    clan = governance["考订并颁行氏族志"]["payload"]["value_judgment"]
    assert clan["overall_direction"] == "positive"
    assert clan["overall_magnitude"] == "significant"
    assert clan["axes"]["civilization_institutions"]["magnitude"] == "significant"
    assert clan["axes"]["culture_education_thought"]["magnitude"] == "limited"

    macro = governance[
        "贞观初中期丰稔、低粮价与跨区域治安改善"
    ]["payload"]["value_judgment"]
    assert macro["overall_magnitude"] == "era_shaping"
    assert macro["axes"]["productivity_livelihood"]["magnitude"] == "era_shaping"
    assert macro["axes"]["state_people_security"]["magnitude"] == "structural"
    assert (
        macro["axes"]["culture_education_thought"]["direction"]
        == "not_established"
    )

    granary = governance["建立州县义仓并用于赈给"]["payload"]["value_judgment"]
    assert granary["overall_direction"] == "positive"
    assert granary["overall_magnitude"] == "structural"


def test_campaign_registry_separates_ruler_control_land_axis_and_failures() -> None:
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
        and any(
            member["actor_kind"] == "ruler"
            and member["actor_ref"] == pack["ruler_ref"]
            for member in row["members"]
        )
        and any(member["actor_kind"] == "person" for member in row["members"])
    )
    ruler_member = next(
        member for member in campaign["members"] if member["actor_kind"] == "ruler"
    )
    ruler_member["sovereign_at_event"] = True
    ruler_member["ruler_campaign_relation"] = "frontline_command"
    ruler_member["authorization_mode"] = "explicit"
    ruler_member["control_extent"] = "sustained"
    ruler_member["obstruction_status"] = "none"
    ruler_member["role_code"] = "commander_in_chief"
    campaign["payload"].update(
        {
            "campaign_tier": "A",
            "strategic_result_class": "major_stage_or_crisis",
            "campaign_tier_basis": "土地轴=strategic_gateway；对手轴=external_hegemony/weakened；结果轴=victory/complete，取得重大阶段结果，定A。",
            "land_strategic_value": "strategic_gateway",
        }
    )
    campaign["semantic_fingerprint"] = cluster_semantic_fingerprint(campaign)

    validation = validate_historical_outcome_registry(
        registry,
        schema_path=SCHEMA,
        facts={row["record_ref"]: row for row in pack["facts"]},
    )
    assert validation["status"] == "passed"

    planned_from_rear = copy.deepcopy(registry)
    planned_campaign = next(
        row
        for row in planned_from_rear["clusters"]
        if row["outcome_ref"] == campaign["outcome_ref"]
    )
    planned_ruler = next(
        member
        for member in planned_campaign["members"]
        if member["actor_kind"] == "ruler"
    )
    planned_ruler["ruler_campaign_relation"] = "operational_direction"
    planned_ruler["role_code"] = "not_in_command_chain"
    planned_campaign["semantic_fingerprint"] = cluster_semantic_fingerprint(
        planned_campaign
    )
    validation = validate_historical_outcome_registry(
        planned_from_rear,
        schema_path=SCHEMA,
        facts={row["record_ref"]: row for row in pack["facts"]},
    )
    assert validation["status"] == "passed"

    campaign["source_war_event_refs"] = ["WAR-LEAD-TEST-001"]
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
    person_member["ruler_campaign_relation"] = "authorization_only"
    invalid_campaign["semantic_fingerprint"] = cluster_semantic_fingerprint(
        invalid_campaign
    )
    with pytest.raises(ValueError, match="只有事件发生时的实际统治者"):
        validate_historical_outcome_registry(
            invalid,
            schema_path=SCHEMA,
            facts={row["record_ref"]: row for row in pack["facts"]},
        )


def test_configured_dynasty_battle_pack_is_unbound_and_validated(
    tmp_path: Path,
) -> None:
    source = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    cluster = copy.deepcopy(
        next(
            row
            for row in source["outcome_registry"]["clusters"]
            if row["outcome_kind"] == "statecraft"
        )
    )
    cluster["ruler_window_status"] = "unresolved"
    cluster["origin"] = "dynasty_battle"
    cluster["source_war_event_refs"] = ["WAR-LEAD-HAN-TEST"]
    cluster.pop("ruler_context_refs", None)
    cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(cluster)
    fact_refs = set(cluster["fact_refs"])
    pack = {
        "schema_version": "dynasty-battle-outcome-pack-v1",
        "pack_scope": "dynasty_battle",
        "dynasty_token": "HAN",
        "status": "current_human_adjudicated",
        "facts": [
            row for row in source["facts"] if row["record_ref"] in fact_refs
        ],
        "members": [],
        "outcome_registry": {
            "schema_version": source["outcome_registry"]["schema_version"],
            "status": source["outcome_registry"]["status"],
            "clusters": [cluster],
        },
    }
    pack["source_pack_sha256"] = sha256(
        json.dumps(
            pack, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "historical-outcome-cluster-registry.schema.json").write_bytes(
        SCHEMA.read_bytes()
    )
    pack_path = tmp_path / "han-battle.json"
    pack_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    loaded = load_configured_dynasty_outcome_packs(
        tmp_path,
        {
            "historical_outcome_registry": {
                "dynasty_outcome_packs": {"HAN": "han-battle.json"}
            }
        },
    )
    assert loaded["HAN"]["source_pack_sha256"]
    assert loaded["HAN"]["outcome_registry"]["clusters"][0][
        "ruler_window_status"
    ] == "unresolved"

    pack["outcome_registry"]["clusters"][0]["ruler_window_status"] = (
        "within_window"
    )
    pack_without_sha = dict(pack)
    pack_without_sha.pop("source_pack_sha256")
    pack["source_pack_sha256"] = sha256(
        json.dumps(
            pack_without_sha,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    pack_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="不得携带皇帝窗口"):
        load_configured_dynasty_outcome_packs(
            tmp_path,
            {
                "historical_outcome_registry": {
                    "dynasty_outcome_packs": {"HAN": "han-battle.json"}
                }
            },
        )


def test_campaign_result_class_controls_tier_but_difficulty_does_not() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    facts = {row["record_ref"]: row for row in pack["facts"]}
    registry = copy.deepcopy(pack["outcome_registry"])
    liuheita = next(
        row
        for row in registry["clusters"]
        if row["canonical_label"] == "洺水击破刘黑闼战役群"
    )
    assert liuheita["payload"]["campaign_tier"] == "A"
    assert liuheita["payload"]["combat_difficulty"] == "D3"
    assert liuheita["result_status"] == "completed"
    assert liuheita["result_direction"] == "positive"
    assert liuheita["payload"]["battle_result"] == "victory"
    assert liuheita["payload"]["objective_completion"] == "complete"
    assert liuheita["stable_delivery"] is False
    assert "后续独立事件" in liuheita["payload"]["campaign_tier_basis"]

    hulao = next(
        row
        for row in registry["clusters"]
        if row["canonical_label"] == "洛阳—虎牢灭王世充窦建德战役群"
    )
    hulao["payload"]["strategic_result_class"] = "single_pole_or_state_terminal"
    hulao["semantic_fingerprint"] = cluster_semantic_fingerprint(hulao)
    with pytest.raises(ValueError, match="必须映射为 S"):
        validate_historical_outcome_registry(
            registry,
            schema_path=SCHEMA,
            facts=facts,
        )


def test_single_state_terminal_requires_first_tier_or_national_external_opponent() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    facts = {row["record_ref"]: row for row in pack["facts"]}
    registry = copy.deepcopy(pack["outcome_registry"])
    xiaoxian = next(
        row
        for row in registry["clusters"]
        if row["canonical_label"] == "李靖实际统帅平定萧铣"
    )
    xiaoxian["payload"]["opponent_strategic_weight"] = "regional_major"
    xiaoxian["payload"]["campaign_tier_basis"] = xiaoxian["payload"][
        "campaign_tier_basis"
    ].replace("first_tier_pole", "regional_major")
    xiaoxian["semantic_fingerprint"] = cluster_semantic_fingerprint(xiaoxian)

    with pytest.raises(ValueError, match="高档战略终局与对手竞争位置不匹配"):
        validate_historical_outcome_registry(
            registry,
            schema_path=SCHEMA,
            facts=facts,
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
    assert grade["grade"] == "historic"
    assert "作为主帅" in grade["basis"]
    assert "S+级战役群" in grade["basis"]
    assert grade["rule_path"] == "military_peak_pair"
    assert grade["outcome_refs"]


@pytest.mark.parametrize(
    ("person", "expected_grade", "expected_path", "expected_count"),
    [
        ("张良", "historic", "statecraft_three_national_results", 3),
        ("陈平", "top", "statecraft_two_national_results", 2),
    ],
)
def test_statecraft_results_grade_people_without_becoming_governance(
    person: str,
    expected_grade: str,
    expected_path: str,
    expected_count: int,
) -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    member = next(row for row in pack["members"] if row["person"] == person)
    grade = assess_person_talent_grade(
        person_ref=member["person_ref"],
        clusters=pack["outcome_registry"]["clusters"],
    )
    credited = {
        row["outcome_ref"]: row
        for row in pack["outcome_registry"]["clusters"]
        if row["outcome_ref"] in grade["outcome_refs"]
    }

    assert grade["grade"] == expected_grade
    assert grade["rule_path"] == expected_path
    assert len(credited) == expected_count
    assert {row["outcome_kind"] for row in credited.values()} == {"statecraft"}
    assert {
        row["settlement_scope"] for row in credited.values()
    } == {"person_statecraft_result"}


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
                "contribution_types": ["implementation_lead"],
                "contribution_basis_fact_refs": list(governance["fact_refs"]),
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


def test_governance_grade_reason_uses_registered_role_and_scale() -> None:
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
    assert "作为主导" in grade["basis"]
    assert "national级治理结果" in grade["basis"]


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
    assert grade["rule_path"] == "military_peak_pair"
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
    ] == "historic"
    assert next(row for row in pack["members"] if row["person"] == "长孙无忌")[
        "effective_talent_grade"
    ] == "historic"


@pytest.mark.parametrize("ruler", ["刘邦", "李世民", "李渊"])
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


def test_lishimin_full_ruler_gold_closes_outcomes_and_profiles() -> None:
    report = compare_historical_quality_gold_files(
        manifest_path=ROOT / "eval/historical_quality_gold/李世民.json",
        result_path=ROOT / "eval/i5b_current_value/李世民/result.json",
    )

    cases = {row["gold_ref"]: row for row in report["cases"]}
    assert report["status"] == "passed"
    assert report["comparison_mode"] == "post_run_gold_only"
    assert report["recall"]["major"]["total"] >= 27
    assert report["recall"]["major"]["rate"] == 1.0
    assert report["precision_status"] == "measured_full_ruler"
    assert report["accepted_episode_precision"] == 1.0
    assert report["actual_disposition_coverage"]["missing_refs"] == []
    assert report["actual_disposition_coverage"]["unexpected_refs"] == []
    assert cases["GOLD-LSM-CAMPAIGN-GOGURYEO-645"]["matched_refs"] == [
        "OUTCOME-LSM-CAMPAIGN-GOGURYEO-645"
    ]
    assert cases["GOLD-LSM-CAMPAIGN-GOGURYEO-645"]["differences"] == []
    assert report["database_write_count"] == 0
    assert report["formal_score_write_count"] == 0


@pytest.mark.parametrize(
    ("ruler", "expected_signal", "expected_complementarity", "expected_stability"),
    [
        ("李世民", "19.210646", "balanced_four", "durable_multi_stage"),
        ("李渊", "5.617151", "strong_three", "stable_but_narrow"),
        ("刘邦", "13.526371", "balanced_four", "durable_multi_stage"),
    ],
)
def test_current_i5b_gold_freezes_rule_projection_and_shadow_signal(
    ruler: str,
    expected_signal: str,
    expected_complementarity: str,
    expected_stability: str,
) -> None:
    report = compare_historical_quality_gold_files(
        manifest_path=ROOT / "eval/historical_quality_gold" / f"{ruler}.json",
        result_path=ROOT / "eval/i5b_current_value" / ruler / "result.json",
    )

    assert report["status"] == "passed"
    assert report["i5b_projection"] == {
        "required": True,
        "status": "matched",
        "differences": [],
    }
    manifest = load_historical_quality_gold(
        ROOT / "eval/historical_quality_gold" / f"{ruler}.json",
        schema_path=GOLD_SCHEMA,
    )
    assert manifest["i5b_expectation"]["weighted_raw_signal"] == expected_signal
    assert manifest["i5b_expectation"]["team_projection"][
        "functional_complementarity"
    ] == expected_complementarity
    assert manifest["i5b_expectation"]["team_projection"][
        "long_term_stability"
    ] == expected_stability
    if ruler == "李渊":
        assert manifest["i5b_expectation"]["team_projection"]["positive_members"] == [
            "李世民",
            "李勣",
            "李靖",
            "刘文静",
        ]


def test_i5b_gold_rejects_shadow_signal_drift() -> None:
    manifest = load_historical_quality_gold(
        ROOT / "eval/historical_quality_gold/李世民.json",
        schema_path=GOLD_SCHEMA,
    )
    result = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/result.json").read_text(
            encoding="utf-8"
        )
    )
    result["net_signal"] = "0.000000"

    comparison = compare_historical_quality_gold(manifest, result)

    assert comparison["status"] == "failed"
    assert "i5b_projection_mismatch" in comparison["blocking_refs"]
    assert comparison["i5b_projection"]["differences"] == [
        {
            "path": "net_signal",
                "expected": "19.210646",
            "actual": "0.000000",
        }
    ]


@pytest.mark.parametrize("ruler", ["李世民", "李渊", "刘邦"])
def test_current_i5b_gold_blind_gate_builds_before_gold_and_has_no_side_effects(
    ruler: str,
) -> None:
    report = run_historical_quality_gold_blind_gate(
        source_pack_path=ROOT / "eval/i5b_current_value" / ruler / "source-pack.json",
        manifest_path=ROOT / "eval/historical_quality_gold" / f"{ruler}.json",
        workspace_root=ROOT,
    )

    assert report["status"] == "passed"
    assert report["comparison_mode"] == "post_run_gold_only"
    assert report["i5b_projection"]["status"] == "matched"
    assert report["blind_generation"] == {
        "status": "generated_before_gold_access",
        "result_persisted": False,
        "runtime_model_call_count": 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }


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


def test_full_ruler_gold_requires_complete_actual_dispositions() -> None:
    manifest = load_historical_quality_gold(
        ROOT / "eval/historical_quality_gold/李世民.json",
        schema_path=GOLD_SCHEMA,
    )
    result = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/result.json").read_text(
            encoding="utf-8"
        )
    )
    manifest["scope_completeness"] = "full_ruler"
    manifest["actual_dispositions"] = [
        {
            "collection": "historical_outcome_clusters",
            "actual_ref": result["historical_outcome_clusters"][0]["outcome_ref"],
            "disposition": "accepted",
            "gold_refs": [manifest["cases"][0]["gold_ref"]],
            "basis": "fixture accepted",
        }
    ]

    comparison = compare_historical_quality_gold(manifest, result)

    assert comparison["status"] == "failed"
    assert comparison["accepted_episode_precision"] is None
    assert comparison["precision_status"] == "blocked_incomplete_actual_dispositions"
    assert comparison["actual_disposition_coverage"]["covered"] == 1
    assert comparison["actual_disposition_coverage"]["actual"] > 1
    assert "missing_actual_dispositions" in comparison["blocking_refs"]


def test_public_outcome_gold_measures_all_outcome_dispositions_only() -> None:
    manifest = load_historical_quality_gold(
        ROOT / "eval/historical_quality_gold/李世民.json",
        schema_path=GOLD_SCHEMA,
    )
    result = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/result.json").read_text(
            encoding="utf-8"
        )
    )
    accepted_gold = next(
        case["gold_ref"]
        for case in manifest["cases"]
        if case["unit_kind"] in {"campaign_group", "campaign_operation"}
    )
    manifest["scope_completeness"] = "public_outcomes"
    manifest["actual_dispositions"] = [
        {
            "collection": "historical_outcome_clusters",
            "actual_ref": row["outcome_ref"],
            "disposition": "accepted" if index == 0 else "false_positive",
            "gold_refs": [accepted_gold] if index == 0 else [],
            "basis": "fixture disposition",
        }
        for index, row in enumerate(result["historical_outcome_clusters"])
    ]

    comparison = compare_historical_quality_gold(manifest, result)

    assert comparison["precision_status"] == "measured_public_outcomes"
    assert comparison["accepted_episode_precision"] == pytest.approx(
        1 / len(result["historical_outcome_clusters"])
    )
    assert comparison["actual_disposition_coverage"]["covered"] == len(
        result["historical_outcome_clusters"]
    )
    assert comparison["actual_disposition_coverage"]["missing_refs"] == []
    assert comparison["actual_disposition_coverage"]["unexpected_refs"] == []
