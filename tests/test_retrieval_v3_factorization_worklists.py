from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_factorization_worklists as tool
from scripts.dev import retrieval_v3_factorization_tasks as task_tool


def test_factorization_batch_flattening_has_one_shared_implementation() -> None:
    assert tool.flatten_batch_materials is task_tool.flatten_batch_materials
    assert task_tool.task_code({"batch_id": "B1", "groups": []}).startswith("RV3F-")


def material_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "target_code": "TGT-I5B-LB",
        "emperor_name": "刘邦",
        "item_code": "I5B",
        "source_pack_code": "SPK-I5B-LB",
        "claim_id": 10,
        "claim_code": "CLM-001",
        "raw_claim_code": "RAW-CLM-001",
        "claim_object_name": "萧何",
        "claim_object_type": "person",
        "claim_direction": "positive",
        "claim_summary": "刘邦委任萧何镇守关中并主持后方供给。",
        "binding_id": 20,
        "binding_code": "BND-001",
        "raw_binding_code": "RAW-BND-001",
        "rule_code": "appointment_delegation",
        "predicate": "appointed_or_delegated_authority",
        "direction": "positive",
        "object_role": "civil_delegate",
        "binding_confidence": "0.9200",
        "binding_review_status": "pending",
        "material_object_link_id": 30,
        "link_code": "MOL-001",
        "material_role": "civil_delegate",
        "object_link_confidence": "0.9200",
        "target_object_id": 40,
        "target_object_code": "TOB-001",
        "object_id": 50,
        "object_code": "OBJ-001",
        "canonical_name": "萧何",
        "normalized_name": "萧何",
        "object_type": "person",
        "talent_grade": "historic_talent",
        "talent_grade_basis": "萧何，汉初重臣。",
        "talent_quality_factor_label": "历史级人才。",
        "person_roles": [{"role_kind": "minister", "dynasty_label": "西汉"}],
        "person_affiliations": [{"affiliation_kind": "dynasty", "dynasty_label": "西汉"}],
        "source_passages": [{"source_title": "史记", "title": "萧相国世家", "quote": "镇国家，抚百姓。"}],
    }
    row.update(overrides)
    return row


def factor_rows() -> list[dict[str, object]]:
    return [
        {
            "rule_code": "",
            "factor_name": "source_factor",
            "factor_scope": "shared",
            "factor_option_id": 1,
            "label": "基础史源",
            "value_num": "1.0000",
        },
        {
            "rule_code": "appointment_delegation",
            "factor_name": "appointment_importance",
            "factor_scope": "rule",
            "factor_option_id": 2,
            "label": "有实际职责的任用、信任或单一领域真实授权。",
            "value_num": "1.2000",
        },
        {
            "rule_code": "appointment_delegation",
            "factor_name": "appointment_effect",
            "factor_scope": "rule",
            "factor_option_id": 3,
            "label": "人岗匹配成立，有明确任后表现、职责履行、政策、军事、行政成果或持续复用反馈。",
            "value_num": "1.1000",
        },
        {
            "rule_code": "appointment_delegation",
            "factor_name": "continuity_factor",
            "factor_scope": "rule",
            "factor_option_id": 4,
            "label": "稳定任用授权。",
            "value_num": "1.1000",
        },
        {
            "rule_code": "appointment_delegation",
            "factor_name": "appointment_effect",
            "factor_scope": "rule",
            "factor_option_id": 7,
            "label": "错任、错信、偏信、弱匹配或授权后结果较差，显示任用授权判断有问题。",
            "value_num": "-0.7000",
        },
        {
            "rule_code": "",
            "factor_name": "attribution_factor",
            "factor_scope": "shared",
            "factor_option_id": 5,
            "label": "可归因于皇帝授权",
            "value_num": "1.0000",
        },
        {
            "rule_code": "",
            "factor_name": "context_factor",
            "factor_scope": "shared",
            "factor_option_id": 6,
            "label": "语境清楚",
            "value_num": "1.0000",
        },
        {
            "rule_code": "",
            "factor_name": "directness_factor",
            "factor_scope": "default",
            "factor_option_id": 12,
            "label": "核心结构材料",
            "value_num": "1.2000",
        },
        {
            "rule_code": "",
            "factor_name": "object_weight",
            "factor_scope": "shared",
            "factor_option_id": 13,
            "label": "国家级关键人才、继承或储备人才、历史级能臣名将、核心施害对象；该对象的任用、保全或受损足以显著改变本 rule 结构。",
            "value_num": "1.6000",
        },
        {
            "rule_code": "team_building",
            "factor_name": "talent_quality_factor",
            "factor_scope": "team",
            "factor_option_id": 8,
            "label": "历史级人才。",
            "value_num": "2.0000",
        },
        {
            "rule_code": "team_building",
            "factor_name": "role_complementarity_factor",
            "factor_scope": "team",
            "factor_option_id": 9,
            "label": "常规互补。",
            "value_num": "1.0000",
        },
        {
            "rule_code": "team_building",
            "factor_name": "long_term_stability_factor",
            "factor_scope": "team",
            "factor_option_id": 10,
            "label": "稳定团队。",
            "value_num": "1.0000",
        },
        {
            "rule_code": "team_building",
            "factor_name": "rank_decay",
            "factor_scope": "team",
            "factor_option_id": 11,
            "label": "第 1 位",
            "value_num": "1.0000",
        },
    ]


def test_appointment_delegation_factor_keys_match_pending_material_contract() -> None:
    catalog = tool.build_factor_key_catalog(factor_rows())

    assert tool.factor_keys_for_material("appointment_delegation", "positive", catalog) == (
        "appointment_importance",
        "appointment_effect",
        "continuity_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    )
    talent_catalog = tool.build_factor_key_catalog(
        [
            {"rule_code": "talent_discovery", "factor_name": "discovery_level", "factor_scope": "rule"},
            {"rule_code": "talent_discovery", "factor_name": "talent_quality_factor", "factor_scope": "attribute_mapping"},
            {"rule_code": "talent_discovery", "factor_name": "channel_factor", "factor_scope": "rule"},
            {"rule_code": "", "factor_name": "attribution_factor", "factor_scope": "default"},
            {"rule_code": "", "factor_name": "source_factor", "factor_scope": "default"},
            {"rule_code": "", "factor_name": "context_factor", "factor_scope": "default"},
            {"rule_code": "", "factor_name": "directness_factor", "factor_scope": "default"},
            {"rule_code": "", "factor_name": "object_weight", "factor_scope": "shared"},
        ]
    )
    assert tool.factor_keys_for_material("talent_discovery", "positive", talent_catalog) == (
        "discovery_level",
        "talent_quality_factor",
        "channel_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    )
    appointment_catalog = tool.build_factor_key_catalog(
        [
            {"rule_code": "appointment_delegation", "factor_name": "appointment_importance", "factor_scope": "rule"},
            {"rule_code": "appointment_delegation", "factor_name": "appointment_effect", "factor_scope": "rule"},
            {"rule_code": "appointment_delegation", "factor_name": "continuity_factor", "factor_scope": "rule"},
            {"rule_code": "", "factor_name": "object_weight", "factor_scope": "shared"},
            {"rule_code": "", "factor_name": "attribution_factor", "factor_scope": "shared"},
            {"rule_code": "", "factor_name": "source_factor", "factor_scope": "shared"},
            {"rule_code": "", "factor_name": "context_factor", "factor_scope": "shared"},
        ]
    )
    assert tool.factor_keys_for_material("appointment_delegation", "positive", appointment_catalog) == (
        "appointment_importance",
        "appointment_effect",
        "continuity_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    )
    tolerate_catalog = tool.build_factor_key_catalog(
        [
            {"rule_code": "tolerate_talent", "factor_name": "handling_severity", "factor_scope": "rule"},
            {"rule_code": "tolerate_talent", "factor_name": "target_fault_factor", "factor_scope": "rule"},
            {"rule_code": "", "factor_name": "object_weight", "factor_scope": "shared"},
            {"rule_code": "", "factor_name": "attribution_factor", "factor_scope": "shared"},
            {"rule_code": "", "factor_name": "source_factor", "factor_scope": "shared"},
            {"rule_code": "", "factor_name": "context_factor", "factor_scope": "shared"},
        ]
    )
    assert tool.factor_keys_for_material("tolerate_talent", "negative", tolerate_catalog) == (
        "handling_severity",
        "target_fault_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    )
    team_catalog = tool.build_factor_key_catalog(
        [
            {"rule_code": "team_building", "factor_name": "talent_quality_factor", "factor_scope": "team"},
            {"rule_code": "team_building", "factor_name": "rank_decay", "factor_scope": "team"},
            {"rule_code": "team_building", "factor_name": "role_complementarity_factor", "factor_scope": "team"},
            {"rule_code": "team_building", "factor_name": "long_term_stability_factor", "factor_scope": "team"},
        ]
    )
    assert tool.factor_keys_for_material("team_building", "positive", team_catalog) == (
        "talent_quality_factor",
        "role_complementarity_factor",
        "long_term_stability_factor",
    )


def test_factor_options_prefer_rule_catalog_and_drop_legacy_routing_labels() -> None:
    catalog = tool.build_factor_option_catalog(
        [
            {
                "rule_code": "",
                "factor_name": "context_factor",
                "option_code": "shared-weak",
                "label": "相邻项剩余很弱",
                "value_num": "0.5000",
            },
            {
                "rule_code": "appointment_delegation",
                "factor_name": "context_factor",
                "option_code": "adjacent",
                "label": "与本 rule 相关但边界较弱，容易被相邻 rule 吸收。",
                "value_num": "0.7000",
            },
            {
                "rule_code": "appointment_delegation",
                "factor_name": "context_factor",
                "option_code": "clear",
                "label": "本 rule 语境成立，事实和对象关系清楚。",
                "value_num": "1.0000",
            },
        ]
    )

    assert tool.factor_option_candidates(
        catalog,
        rule_code="appointment_delegation",
        factor_name="context_factor",
    ) == [
        {
            "factor_option_id": None,
            "option_code": "clear",
            "label": "本 rule 语境成立，事实和对象关系清楚。",
            "value_num": "1.0000",
            "source_doc": "",
            "source_line": None,
            "option_note": "",
        }
    ]


def test_prompt_slimming_drops_legacy_routing_labels_from_existing_worklist() -> None:
    batch = {
        "batch_id": "legacy-worklist",
        "groups": [
            {
                "materials": [
                    {
                        "binding_code": "BND-LEGACY",
                        "rule_code": "appointment_delegation",
                        "factor_patch_template": {
                            "factor_refs": {"context_factor": {"label": ""}},
                            "factor_option_candidates": {
                                "context_factor": [
                                    {"label": "相邻项剩余很弱", "value_num": "0.5000"},
                                    {"label": "本 rule 语境成立，事实和对象关系清楚。", "value_num": "1.0000"},
                                ]
                            },
                        },
                    }
                ]
            }
        ],
    }

    payload = task_tool.slim_batch_for_prompt(batch)

    assert payload["factor_options_by_factor"]["context_factor"] == [
        {"label": "本 rule 语境成立，事实和对象关系清楚。", "value_num": "1.0000"}
    ]


def test_accepted_pack_scope_uses_latest_passed_pack_per_target_contract() -> None:
    predicate = tool.scope_predicate("accepted-packs")

    assert "distinct on (sp2.target_id, sp2.contract_id)" in predicate
    assert "sp2.status = 'accepted'" in predicate
    assert "sp2.coverage_status = 'passed'" in predicate
    assert "sp2.updated_at desc" in predicate


def test_source_pack_predicate_allows_explicit_passed_shadow_pack() -> None:
    predicate = tool.source_pack_predicate("accepted-packs", ["SPK-I5B-SHADOW"])

    assert "sp.pack_code = any(%s)" in predicate
    assert "sp.coverage_status = 'passed'" in predicate
    assert "sp2.status = 'accepted'" not in predicate


def test_fetch_material_rows_excludes_open_material_reviews() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""
            self.params = ()

        def execute(self, sql: str, params=()) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self) -> list[dict[str, object]]:
            return []

    cur = FakeCursor()
    rows = tool.fetch_material_rows(
        cur,
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    assert rows == []
    assert "from retrieval_v3.material_review_queue mrq" in cur.sql
    assert "mrq.claim_id = mc.id" in cur.sql
    assert "mrq.queue_status in ('ready', 'needs_review', 'running', 'blocked')" in cur.sql


def test_fetch_material_rows_filters_by_source_pack_code_without_accepted_scope() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""
            self.params = ()

        def execute(self, sql: str, params=()) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self) -> list[dict[str, object]]:
            return []

    cur = FakeCursor()
    rows = tool.fetch_material_rows(
        cur,
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        source_pack_codes=["SPK-I5B-SHADOW"],
    )

    assert rows == []
    assert "sp.pack_code = any(%s)" in cur.sql
    assert "sp2.status = 'accepted'" not in cur.sql
    assert "existing_judgment.binding_id = crb.id" in cur.sql
    assert cur.params == (
        "evidence_cluster_signal_v3",
        "appointment_delegation",
        ["SPK-I5B-SHADOW"],
        "I5B",
        "I5B",
        "evidence_cluster_signal_v3",
    )


def test_fetch_material_rows_full_review_mode_can_include_existing_judgments() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""

        def execute(self, sql: str, params=()) -> None:
            self.sql = sql

        def fetchall(self) -> list[dict[str, object]]:
            return []

    cur = FakeCursor()
    tool.fetch_material_rows(
        cur,
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="active-targets",
        include_judged=True,
    )

    assert "existing_judgment.binding_id = crb.id" not in cur.sql


def test_fetch_material_rows_includes_promoter_review_candidates() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""

        def execute(self, sql: str, params=()) -> None:
            self.sql = sql

        def fetchall(self) -> list[dict[str, object]]:
            return []

    cur = FakeCursor()
    tool.fetch_material_rows(
        cur,
        item_code="I5B",
        rule_code="tolerate_talent",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    assert "crb.usable_for_scoring_cluster" in cur.sql
    assert "crb.rule_code <> 'appointment_delegation'" in cur.sql
    assert "crb.binding_payload->>'source' = 'retrieval_v3_candidate_promoter'" in cur.sql
    assert "nullif(crb.binding_payload->>'candidate_id', '') is not null" in cur.sql


def test_fetch_material_rows_blocks_appointment_delegation_promoter_review_wide_entry() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""

        def execute(self, sql: str, params=()) -> None:
            self.sql = sql

        def fetchall(self) -> list[dict[str, object]]:
            return []

    cur = FakeCursor()
    tool.fetch_material_rows(
        cur,
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    promoter_gate = cur.sql.split("crb.binding_payload->>'source' = 'retrieval_v3_candidate_promoter'")[0]
    assert "crb.rule_code <> 'appointment_delegation'" in promoter_gate



def test_fetch_material_rows_prefers_promoted_material_object_link_id() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""

        def execute(self, sql: str, params=()) -> None:
            self.sql = sql

        def fetchall(self) -> list[dict[str, object]]:
            return []

    cur = FakeCursor()
    tool.fetch_material_rows(
        cur,
        item_code="I5B",
        rule_code="talent_discovery",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    assert "join lateral" in cur.sql
    assert "promoted_material_object_link_id" in cur.sql
    assert "coalesce(crb.binding_payload->>'promoted_material_object_link_id', '')" in cur.sql
    assert "mol1.id = (crb.binding_payload->>'promoted_material_object_link_id')::bigint" in cur.sql
    assert "mol1.role = crb.object_role" in cur.sql


def test_factor_patch_template_merges_generic_and_rule_options() -> None:
    catalog = tool.build_factor_option_catalog(factor_rows())
    factor_key_catalog = tool.build_factor_key_catalog(factor_rows())
    item = tool.material_item(material_row(), catalog, factor_key_catalog)
    template = item["factor_patch_template"]

    assert template["target_action"] == "review"
    assert template["side"] == "positive"
    assert template["factor_refs"]["appointment_importance"] == {"label": ""}
    assert template["factor_option_candidates"]["appointment_importance"][0]["label"] == "有实际职责的任用、信任或单一领域真实授权。"
    assert template["factor_option_candidates"]["source_factor"][0]["label"] == "基础史源"
    assert item["object"]["talent_grade"] == "historic_talent"
    assert item["claim"]["source_passages"][0]["source_title"] == "史记"


def test_appointment_delegation_factor_hints_prefill_only_trusted_refs() -> None:
    rows = [
        {"rule_code": "appointment_delegation", "factor_name": "appointment_importance", "factor_scope": "rule", "factor_option_id": 1, "option_code": "AD-IMP-KEY", "label": "中枢、军政关键岗位、核心职掌或重大军政事务授权。", "value_num": "1.2500"},
        {"rule_code": "appointment_delegation", "factor_name": "appointment_effect", "factor_scope": "rule", "factor_option_id": 2, "option_code": "AD-EFF-STRONG", "label": "高风险、关键岗位或高强度授权高度适配，并产生重大成功或强烈体现任用授权合理。", "value_num": "1.5000"},
        {"rule_code": "appointment_delegation", "factor_name": "continuity_factor", "factor_scope": "rule", "factor_option_id": 3, "option_code": "AD-CONT-SHORT", "label": "短期、单次、临时任用授权，或未形成持续复用。", "value_num": "0.8500"},
        {"rule_code": "", "factor_name": "attribution_factor", "factor_scope": "shared", "factor_option_id": 4, "label": "皇帝决策链清楚", "value_num": "1.0000"},
        {"rule_code": "", "factor_name": "source_factor", "factor_scope": "shared", "factor_option_id": 5, "label": "标准史源，事实链清楚。", "value_num": "1.0000"},
        {"rule_code": "", "factor_name": "context_factor", "factor_scope": "shared", "factor_option_id": 6, "label": "本 rule 语境成立，事实和对象关系清楚。", "value_num": "1.0000"},
    ]
    catalog = tool.build_factor_option_catalog(rows)
    factor_key_catalog = tool.build_factor_key_catalog(rows)
    item = tool.material_item(
        material_row(
            candidate_payload={
                "appointment_delegation_factor_hints": {
                    "importance_hint": "key_military_political",
                    "effect_hint": "strong_success",
                    "continuity_hint": "single_short",
                    "hint_confidence": {"importance": "high", "effect": "medium", "continuity": "high"},
                    "uncertainty_flags": [],
                }
            }
        ),
        catalog,
        factor_key_catalog,
    )

    template = item["factor_patch_template"]

    assert template["factor_refs"]["appointment_importance"]["label"] == "中枢、军政关键岗位、核心职掌或重大军政事务授权。"
    assert template["factor_refs"]["appointment_effect"]["label"] == "高风险、关键岗位或高强度授权高度适配，并产生重大成功或强烈体现任用授权合理。"
    assert template["factor_refs"]["continuity_factor"]["label"] == "短期、单次、临时任用授权，或未形成持续复用。"
    assert template["factor_refs"]["appointment_effect"]["prefill_source"] == "appointment_delegation_factor_hints"
    assert template["factor_hint_suggestions"]["mapped_refs"]["appointment_effect"]["hint_value"] == "strong_success"
    assert template["factor_hint_suggestions"]["mapped_refs"]["appointment_effect"]["option_code"]
    assert "raw_hints" in template["factor_hint_suggestions"]


def test_appointment_delegation_factor_hints_withhold_low_or_uncertain_refs() -> None:
    rows = [
        {"rule_code": "appointment_delegation", "factor_name": "appointment_importance", "factor_scope": "rule", "factor_option_id": 1, "label": "中枢、军政关键岗位、核心职掌或重大军政事务授权。", "value_num": "1.2500"},
        {"rule_code": "appointment_delegation", "factor_name": "appointment_effect", "factor_scope": "rule", "factor_option_id": 2, "label": "高风险、关键岗位或高强度授权高度适配，并产生重大成功或强烈体现任用授权合理。", "value_num": "1.5000"},
        {"rule_code": "appointment_delegation", "factor_name": "continuity_factor", "factor_scope": "rule", "factor_option_id": 3, "label": "长期复用、多阶段持续信任，或同一对象跨阶段承担关键职责。", "value_num": "1.1500"},
        {"rule_code": "", "factor_name": "attribution_factor", "factor_scope": "shared", "factor_option_id": 4, "label": "皇帝决策链清楚", "value_num": "1.0000"},
        {"rule_code": "", "factor_name": "source_factor", "factor_scope": "shared", "factor_option_id": 5, "label": "标准史源，事实链清楚。", "value_num": "1.0000"},
        {"rule_code": "", "factor_name": "context_factor", "factor_scope": "shared", "factor_option_id": 6, "label": "本 rule 语境成立，事实和对象关系清楚。", "value_num": "1.0000"},
    ]
    catalog = tool.build_factor_option_catalog(rows)
    factor_key_catalog = tool.build_factor_key_catalog(rows)
    item = tool.material_item(
        material_row(
            candidate_payload={
                "appointment_delegation_factor_hints": {
                    "importance_hint": "key_military_political",
                    "effect_hint": "strong_success",
                    "continuity_hint": "long_multi_stage",
                    "hint_confidence": {"importance_hint": "low", "effect_hint": "high", "continuity_hint": "high"},
                    "uncertainty_flags": ["effect_strength_needs_review"],
                }
            }
        ),
        catalog,
        factor_key_catalog,
    )

    template = item["factor_patch_template"]

    assert template["factor_refs"]["appointment_importance"] == {"label": ""}
    assert template["factor_refs"]["appointment_effect"] == {"label": ""}
    assert template["factor_refs"]["continuity_factor"]["label"] == "长期复用、多阶段持续信任，或同一对象跨阶段承担关键职责。"
    assert template["factor_hint_suggestions"]["withheld_refs"]["appointment_importance"]["reason"] == "low_or_missing_confidence"
    assert template["factor_hint_suggestions"]["withheld_refs"]["appointment_effect"]["reason"] == "uncertainty_flag"


def test_team_building_template_prefills_talent_grade_factor() -> None:
    catalog = tool.build_factor_option_catalog(
        [
            {
                "rule_code": "team_building",
                "factor_name": "talent_quality_factor",
                "factor_scope": "team",
                "factor_option_id": 1,
                "label": "历史级人才。",
                "value_num": "2.0000",
            },
            {
                "rule_code": "team_building",
                "factor_name": "role_complementarity_factor",
                "factor_scope": "team",
                "factor_option_id": 2,
                "label": "常规互补。",
                "value_num": "1.0000",
            },
            {
                "rule_code": "team_building",
                "factor_name": "long_term_stability_factor",
                "factor_scope": "team",
                "factor_option_id": 3,
                "label": "稳定团队。",
                "value_num": "1.0000",
            },
        ]
    )
    factor_key_catalog = tool.build_factor_key_catalog(
        [
            {"rule_code": "team_building", "factor_name": "talent_quality_factor", "factor_scope": "team"},
            {"rule_code": "team_building", "factor_name": "role_complementarity_factor", "factor_scope": "team"},
            {"rule_code": "team_building", "factor_name": "long_term_stability_factor", "factor_scope": "team"},
        ]
    )
    item = tool.material_item(
        material_row(rule_code="team_building", talent_grade="historic_talent"),
        catalog,
        factor_key_catalog,
    )

    template = item["factor_patch_template"]

    assert template["factor_refs"]["talent_quality_factor"] == {"label": "历史级人才。"}
    assert set(template["factor_keys"]) == {
        "talent_quality_factor",
        "role_complementarity_factor",
        "long_term_stability_factor",
    }


def test_team_building_worklist_rejects_missing_talent_grade() -> None:
    with pytest.raises(tool.FactorizationWorklistError, match="requires accepted person_profiles.talent_grade"):
        tool.build_worklist_from_rows(
            [material_row(rule_code="team_building", talent_grade=None)],
            factor_rows(),
            item_code="I5B",
            rule_code="team_building",
            formula_code="evidence_cluster_signal_v3",
            scope="accepted-packs",
            batch_size=40,
        )


def test_team_building_validation_rejects_talent_grade_override() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row(rule_code="team_building", talent_grade="historic_talent")],
        factor_rows(),
        item_code="I5B",
        rule_code="team_building",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    patch_rows = [
        {
            "binding_code": "BND-001",
            "target_action": "score",
            "side": "positive",
            "factor_refs": {
                "talent_quality_factor": {"label": "顶级人才。"},
                "role_complementarity_factor": {"label": "常规互补。"},
                "long_term_stability_factor": {"label": "稳定团队。"},
            },
            "patch_note": "故意覆盖人物画像中的历史级人才，用于验证画像预填不可被改写。",
        }
    ]

    report = tool.validate_patch(payload["suggested_batches"][0], patch_rows)

    assert report["ok"] is False
    assert any(issue["status"] == "team_talent_grade_prefill_mismatch" for issue in report["issues"])


def test_team_building_validation_requires_consistent_team_factors() -> None:
    payload = tool.build_worklist_from_rows(
        [
            material_row(binding_code="BND-001", rule_code="team_building", talent_grade="historic_talent"),
            material_row(binding_code="BND-002", rule_code="team_building", talent_grade="top_talent"),
        ],
        factor_rows(),
        item_code="I5B",
        rule_code="team_building",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_rows = [
        {
            "binding_code": "BND-001",
            "target_action": "score",
            "side": "positive",
            "factor_refs": {
                "talent_quality_factor": {"label": "历史级人才。"},
                "role_complementarity_factor": {"label": "常规互补。"},
                "long_term_stability_factor": {"label": "稳定团队。"},
            },
            "patch_note": "该材料可作为团队成员入分，团队级互补和稳定因子用于一致性测试。",
        },
        {
            "binding_code": "BND-002",
            "target_action": "score",
            "side": "positive",
            "factor_refs": {
                "talent_quality_factor": {"label": "顶级人才。"},
                "role_complementarity_factor": {"label": "高度互补。"},
                "long_term_stability_factor": {"label": "稳定团队。"},
            },
            "patch_note": "该材料可作为团队成员入分，但团队互补因子故意与前行不同。",
        },
    ]

    report = tool.validate_patch(batch, patch_rows)

    assert report["ok"] is False
    assert any(issue["status"] == "inconsistent_team_factor_label" for issue in report["issues"])


def test_build_worklist_groups_materials_and_suggests_batches() -> None:
    payload = tool.build_worklist_from_rows(
        [
            material_row(binding_code="BND-001"),
            material_row(binding_code="BND-002", emperor_name="朱元璋", target_code="TGT-I5B-ZYZ", direction="negative"),
        ],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=1,
    )

    assert payload["totals"]["materials"] == 2
    assert payload["totals"]["groups"] == 2
    assert payload["direction_counts"] == {"negative": 1, "positive": 1}
    assert [batch["material_count"] for batch in payload["suggested_batches"]] == [1, 1]


def test_suggest_batches_splits_single_oversized_group() -> None:
    payload = tool.build_worklist_from_rows(
        [
            material_row(binding_code="BND-001"),
            material_row(binding_code="BND-002"),
            material_row(binding_code="BND-003"),
        ],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=2,
    )

    batches = payload["suggested_batches"]

    assert [batch["material_count"] for batch in batches] == [2, 1]
    assert [group["binding_codes"] for group in batches[0]["groups"]] == [["BND-001", "BND-002"]]
    assert [group["binding_codes"] for group in batches[1]["groups"]] == [["BND-003"]]


def test_filter_material_rows_restricts_by_target_name_or_code() -> None:
    rows = [
        material_row(binding_code="BND-001", emperor_name="刘邦", target_code="TGT-I5B-LB"),
        material_row(binding_code="BND-002", emperor_name="朱元璋", target_code="TGT-I5B-ZYZ"),
    ]

    by_name = tool.filter_material_rows(rows, target_names=["朱元璋"])
    by_code = tool.filter_material_rows(rows, target_codes=["TGT-I5B-LB"])

    assert [row["binding_code"] for row in by_name] == ["BND-002"]
    assert [row["binding_code"] for row in by_code] == ["BND-001"]


def test_patch_template_and_validation_require_complete_coverage() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    template_rows = tool.patch_template_rows(batch)

    assert template_rows == [
        {
            "binding_code": "BND-001",
            "target_action": "review",
            "side": "positive",
            "factor_refs": {
                "appointment_importance": {"label": ""},
                "appointment_effect": {"label": ""},
                "continuity_factor": {"label": ""},
                "attribution_factor": {"label": ""},
                "source_factor": {"label": ""},
                "context_factor": {"label": ""},
            },
            "patch_note": "",
        }
    ]

    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"},
            "appointment_effect": {"label": "人岗匹配成立，有明确任后表现、职责履行、政策、军事、行政成果或持续复用反馈。"},
            "continuity_factor": {"label": "稳定任用授权。"},
            "attribution_factor": {"label": "可归因于皇帝授权"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "语境清楚"},
        },
        "patch_note": "萧何材料直接说明后方委任与供给成效，可作为正向授权材料。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is True
    assert report["action_counts"] == {"score": 1}


def test_validation_flags_unknown_labels_and_missing_rows() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row(binding_code="BND-001"), material_row(binding_code="BND-002")],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "不存在的标签"},
            "appointment_effect": {"label": "人岗匹配成立，有明确任后表现、职责履行、政策、军事、行政成果或持续复用反馈。"},
            "continuity_factor": {"label": "稳定任用授权。"},
            "attribution_factor": {"label": "可归因于皇帝授权"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "语境清楚"},
        },
        "patch_note": "萧何材料直接说明后方委任与供给成效，可作为正向授权材料。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is False
    statuses = {issue["status"] for issue in report["issues"]}
    assert {"unknown_factor_label", "missing_patch_row"} <= statuses


def test_validation_rejects_appointment_delegation_side_appointment_effect_sign_mismatch() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"},
            "appointment_effect": {"label": "错任、错信、偏信、弱匹配或授权后结果较差，显示任用授权判断有问题。"},
            "continuity_factor": {"label": "稳定任用授权。"},
            "attribution_factor": {"label": "可归因于皇帝授权"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "语境清楚"},
        },
        "patch_note": "萧何材料是正向任用事实，不能在正向行里选择负值结果反馈。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is False
    statuses = {issue["status"] for issue in report["issues"]}
    assert "side_appointment_effect_sign_mismatch" in statuses
    assert "side_raw_score_sign_mismatch" in statuses


def test_validation_rejects_strong_success_hint_downgraded_to_weak_feedback() -> None:
    rows = [
        {"rule_code": "appointment_delegation", "factor_name": "appointment_importance", "factor_scope": "rule", "factor_option_id": 1, "label": "中枢、军政关键岗位、核心职掌或重大军政事务授权。", "value_num": "1.2500"},
        {"rule_code": "appointment_delegation", "factor_name": "appointment_effect", "factor_scope": "rule", "factor_option_id": 2, "label": "任用、信任、授权关系存在，但只见任官、亲近、名望、任务交付或弱反馈，缺少充分结果或岗位适配证明。", "value_num": "0.4000"},
        {"rule_code": "appointment_delegation", "factor_name": "appointment_effect", "factor_scope": "rule", "factor_option_id": 3, "label": "高风险、关键岗位或高强度授权高度适配，并产生重大成功或强烈体现任用授权合理。", "value_num": "1.5000"},
        {"rule_code": "appointment_delegation", "factor_name": "continuity_factor", "factor_scope": "rule", "factor_option_id": 4, "label": "短期、单次、临时任用授权，或未形成持续复用。", "value_num": "0.8500"},
        {"rule_code": "", "factor_name": "attribution_factor", "factor_scope": "shared", "factor_option_id": 5, "label": "皇帝决策链清楚", "value_num": "1.0000"},
        {"rule_code": "", "factor_name": "source_factor", "factor_scope": "shared", "factor_option_id": 6, "label": "标准史源且关键事实链完整、对象和动作均明确。", "value_num": "1.1000"},
        {"rule_code": "", "factor_name": "context_factor", "factor_scope": "shared", "factor_option_id": 7, "label": "本 rule 语境强，材料直接展示该 rule 的核心机制。", "value_num": "1.1000"},
    ]
    payload = tool.build_worklist_from_rows(
        [
            material_row(
                candidate_payload={
                    "appointment_delegation_factor_hints": {
                        "importance_hint": "key_military_political",
                        "effect_hint": "strong_success",
                        "continuity_hint": "single_short",
                        "hint_confidence": {"importance": "high", "effect": "high", "continuity": "medium"},
                        "uncertainty_flags": [],
                    }
                },
                source_passages=[
                    {
                        "source_title": "明史",
                        "title": "太祖本纪",
                        "quote": "以曹国公李文忠为左副将军出应昌。李文忠克应昌，降众五万余人。",
                    }
                ],
            )
        ],
        rows,
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "中枢、军政关键岗位、核心职掌或重大军政事务授权。"},
            "appointment_effect": {"label": "任用、信任、授权关系存在，但只见任官、亲近、名望、任务交付或弱反馈，缺少充分结果或岗位适配证明。"},
            "continuity_factor": {"label": "短期、单次、临时任用授权，或未形成持续复用。"},
            "attribution_factor": {"label": "皇帝决策链清楚"},
            "source_factor": {"label": "标准史源且关键事实链完整、对象和动作均明确。"},
            "context_factor": {"label": "本 rule 语境强，材料直接展示该 rule 的核心机制。"},
        },
        "patch_note": "材料中已经出现任命与克应昌战果，但本测试故意降成弱反馈以触发校验。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is False
    assert any(issue["status"] == "strong_success_hint_downgraded_to_weak_feedback" for issue in report["issues"])


def test_validation_rejects_side_on_non_score_rows() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_row = {
        "binding_code": "BND-001",
        "target_action": "exclude",
        "side": "positive",
        "factor_refs": {},
        "patch_note": "材料没有出现目标人物和授权事实，因此排除但不得保留方向。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is False
    assert any(issue["status"] == "non_score_side_must_be_null" for issue in report["issues"])


def test_cli_writes_worklist_outputs(tmp_path: Path, monkeypatch) -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    monkeypatch.setattr(tool, "build_worklist", lambda **_: payload)
    output_json = tmp_path / "worklist.json"
    output_md = tmp_path / "worklist.md"
    batch_dir = tmp_path / "batches"

    assert tool.main([
        "worklist",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
        "--batch-output-dir",
        str(batch_dir),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["totals"]["materials"] == 1
    assert "retrieval_v3 factorization worklist" in output_md.read_text(encoding="utf-8")
    assert (batch_dir / "rv3_factor_batch_01.json").exists()


def test_cli_template_and_validate_patch(tmp_path: Path) -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch_json = tmp_path / "batch.json"
    tool.write_json(batch_json, payload["suggested_batches"][0])
    patch_jsonl = tmp_path / "patch.jsonl"

    assert tool.main(["template", "--batch-json", str(batch_json), "--output-jsonl", str(patch_jsonl)]) == 0
    assert len(patch_jsonl.read_text(encoding="utf-8").splitlines()) == 1

    output_json = tmp_path / "validation.json"
    output_md = tmp_path / "validation.md"
    assert tool.main([
        "validate-patch",
        "--batch-json",
        str(batch_json),
        "--patch-jsonl",
        str(patch_jsonl),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["ok"] is False
    assert "retrieval_v3 factorization patch validation" in output_md.read_text(encoding="utf-8")


def test_build_codex_tasks_writes_slim_prompt_and_task_jsonl(tmp_path: Path) -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch_path = tmp_path / "rv3_factor_batch_01.json"
    tool.write_json(batch_path, payload["suggested_batches"][0])

    summary = tool.write_task_outputs(batch_paths=[batch_path], output_root=tmp_path / "tasks")

    assert summary["totals"] == {"materials": 1, "tasks": 1}
    assert summary["prompt_budget_summary"]["prompt_chars_total"] > 0
    assert summary["prompt_budget_summary"]["estimated_prompt_tokens_total"] > 0
    assert summary["prompt_budget_summary"]["estimated_prompt_tokens_method"] == "ceil(prompt_chars / 2)"
    assert summary["prompt_budget_summary"]["calibration_sections"] == ["appointment_delegation"]
    assert summary["prompt_budget_summary"]["cost_attribution"]["fixed_instruction_chars"] > 0
    assert summary["prompt_budget_summary"]["cost_attribution"]["batch_json_chars"] > 0
    assert summary["prompt_budget_summary"]["cost_attribution"]["factor_options_json_chars"] > 0
    assert summary["prompt_budget_summary"]["cost_attribution"]["source_quote_text_chars"] > 0
    tasks = tool.read_jsonl(tmp_path / "tasks" / "factorization_tasks.jsonl")
    assert tasks[0]["task_kind"] == "retrieval_v3_factorization"
    assert "--dangerously-bypass-approvals-and-sandbox" in tasks[0]["argv"]
    assert "patch_path" not in tasks[0]
    assert tasks[0]["prompt_budget"]["prompt_chars"] == len((Path.cwd() / tasks[0]["prompt_path"]).read_text(encoding="utf-8"))
    assert tasks[0]["prompt_budget"]["estimated_prompt_tokens"] == (tasks[0]["prompt_budget"]["prompt_chars"] + 1) // 2
    assert tasks[0]["prompt_budget"]["batch_material_count"] == 1
    assert tasks[0]["prompt_budget"]["rule_counts"] == {"appointment_delegation": 1}
    assert tasks[0]["prompt_budget"]["factor_option_count"] > 0
    assert tasks[0]["prompt_budget"]["calibration_prompt_injected"] is True
    assert tasks[0]["prompt_budget"]["cost_attribution"]["materials_json_chars"] > 0
    assert tasks[0]["prompt_budget"]["cost_attribution"]["material_breakdown_chars"]["source_passages_json_chars"] > 0
    assert tasks[0]["prompt_budget"]["cost_attribution"]["material_breakdown_chars"]["source_quote_text_chars"] > 0
    assert tasks[0]["expected_outputs"][0]["kind"] == "jsonl_patch"
    assert tasks[0]["expected_outputs"][0]["fallback"] == "last_message_marked_block"
    assert "/patches/" in tasks[0]["expected_outputs"][0]["path"].replace("\\", "/")
    assert tasks[0]["expected_outputs"][0]["path"].endswith(".jsonl")
    assert (tmp_path / "tasks" / "patches").exists()
    assert (tmp_path / "tasks" / "logs").exists()
    prompt_text = (Path.cwd() / tasks[0]["prompt_path"]).read_text(encoding="utf-8")
    markdown = (tmp_path / "tasks" / "factorization_tasks.md").read_text(encoding="utf-8")
    assert "prompt_chars_total" in markdown
    assert "fixed_instruction_chars" in markdown
    assert "batch_json_chars" in markdown
    assert "source_quote_text_chars" in markdown
    assert "| task | batch | materials | prompt chars | est. tokens | factor options | hints | patch |" in markdown
    assert "factor_options_by_factor" in prompt_text
    assert "patch_requirements" in prompt_text
    assert "required_patch" not in prompt_text
    assert '"target_action": "score | supporting_only | exclude"' not in prompt_text
    assert '"person_roles"' not in prompt_text
    assert '"person_affiliations"' not in prompt_text
    assert '"talent_grade_basis"' not in prompt_text
    assert '"canonical_name": "萧何"' in prompt_text
    assert "factor_hint_suggestions" in prompt_text
    assert "raw_hints" not in prompt_text
    assert "usage_note" not in prompt_text
    assert '"option_code"' not in prompt_text
    assert "只是抓包端有限枚举预填建议，不是正式裁判" in prompt_text
    assert "唯一允许写入的是指定 JSONL patch 文件" in prompt_text
    assert "PATCH_JSONL_BEGIN" in prompt_text
    assert "PATCH_JSONL_END" in prompt_text
    assert "claim.summary 只作索引" in prompt_text
    assert "因子取值只能使用 source_passages.quote 明示支持的事实" in prompt_text
    assert "`attribution_factor` 最高档只用于 quote 明示皇帝亲自判断" in prompt_text
    assert "$i5b-delegation-factorization" not in prompt_text
    assert "appointment_delegation 校准" in prompt_text
    assert "包内 direction 就是本轮 side，不重新判断正负" in prompt_text
    assert "所选 factor 数值乘积为负时必须填 `negative`" in prompt_text
    assert "positive 行不得选择负值 `appointment_effect`" in prompt_text
    assert "不得把后续撤权、诛废、猜忌、清洗、谋反/反叛、自疑聚兵或功臣不保直接当作任用授权结果反馈" in prompt_text
    assert "hint_value=strong_success" in prompt_text
    assert "降为弱反馈必须在 patch_note 中说明同链不闭合的 quote 依据" in prompt_text
    assert "appointment_delegation 的 `appointment_effect` 只评价任用授权安排本身的任务收益或任务损害" in prompt_text
    assert "同功者被杀、功臣安全恐惧、猜忌或政权安全压力" in prompt_text
    assert "各 rule 独立判断" in prompt_text
    assert "同一事实也符合其他 rule 或 item，不构成本 rule 的降权或排除理由" in prompt_text
    assert "相邻战事、同人别功" not in prompt_text
    assert "相邻未给出的上下文" not in prompt_text
    assert "同一 claim/object/side 拆成多个 role binding 时，默认最多保留一个 `score`" in prompt_text
    assert "重新全量裁判正负" not in prompt_text
    assert "刘邦委任萧何镇守关中" in prompt_text


def test_talent_discovery_prompt_calibrates_promotion_proxy_signal(tmp_path: Path) -> None:
    payload = tool.build_worklist_from_rows(
        [
            material_row(
                rule_code="talent_discovery",
                predicate="discovered_talent",
                object_role="discovered_talent",
                binding_code="BND-TALENT-001",
                claim_summary="刘邦拔擢韩信为大将军。",
                canonical_name="韩信",
                source_passages=[{"source_title": "史记", "title": "淮阴侯列传", "quote": "乃拜信为大将军。"}],
            )
        ],
        factor_rows(),
        item_code="I5B",
        rule_code="talent_discovery",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=8,
    )

    prompt_text = tool.prompt_for_batch(batch=payload["suggested_batches"][0], output_jsonl=tmp_path / "patch.jsonl")

    assert "talent_discovery 校准" in prompt_text
    assert "提拔、拔擢、擢用只有在 quote 显示对象此前低位" in prompt_text
    assert "普通升迁、已知重臣任命、单纯授权办事不得纳入发现人才" in prompt_text
    assert "若只有任官而无发现性信号则 `exclude`" in prompt_text


def test_factorization_prompt_keeps_late_appointment_effect_evidence(tmp_path: Path) -> None:
    long_quote = (
        "甲申，洮州十八族番叛，命沐英移兵讨之。"
        + "中间经过。" * 80
        + "九月己亥，沐英大破西番，擒其部长三副使。"
    )
    payload = tool.build_worklist_from_rows(
        [
            material_row(
                binding_code="BND-MUYING",
                claim_object_name="沐英",
                claim_summary="朱元璋命沐英移兵讨洮州叛番，沐英后大破西番并擒其部长。",
                canonical_name="沐英",
                source_passages=[{"source_title": "明史", "title": "明史/卷2", "quote": long_quote}],
            )
        ],
        factor_rows(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=8,
    )
    prompt_text = tool.prompt_for_batch(batch=payload["suggested_batches"][0], output_jsonl=tmp_path / "patch.jsonl")

    assert "命沐英移兵讨之" in prompt_text
    assert "沐英大破西番，擒其部长三副使" in prompt_text


def test_recover_patches_from_last_message(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    last_message_path = tmp_path / "logs" / "RV3F-1.last.md"
    patch_path = tmp_path / "patches" / "RV3F-1.jsonl"
    last_message_path.parent.mkdir(parents=True)
    last_message_path.write_text(
        "\n".join(
            [
                '{"binding_code":"BND-001","target_action":"score","side":"positive","factor_refs":{},"patch_note":"材料明确呈现授权与结果反馈，可作为委任因子化测试。"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "RV3F-1",
                "batch_id": "rv3_factor_batch_01",
                "material_count": 1,
                "patch_path": str(patch_path),
                "last_message_path": str(last_message_path),
                "log_path": str(tmp_path / "logs" / "RV3F-1.jsonl"),
            }
        ],
    )
    output_json = tmp_path / "recovery.json"
    output_md = tmp_path / "recovery.md"

    payload = tool.recover_task_patches(tasks_path=tasks_path, output_json=output_json, output_md=output_md)

    assert payload["ok"] is True
    assert payload["totals"] == {"complete": 1}
    assert json.loads(patch_path.read_text(encoding="utf-8").splitlines()[0])["binding_code"] == "BND-001"
    assert "retrieval_v3 factorization patch recovery" in output_md.read_text(encoding="utf-8")


def test_recover_patches_preserves_existing_complete_patch(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    last_message_path = tmp_path / "logs" / "RV3F-1.last.md"
    patch_path = tmp_path / "patches" / "RV3F-1.jsonl"
    last_message_path.parent.mkdir(parents=True)
    complete_rows = [
        {"binding_code": "BND-001", "target_action": "score", "side": "positive", "factor_refs": {}, "patch_note": "既有完整补丁第一行。"},
        {"binding_code": "BND-002", "target_action": "score", "side": "positive", "factor_refs": {}, "patch_note": "既有完整补丁第二行。"},
    ]
    partial_rows = [
        {"binding_code": "BND-001", "target_action": "score", "side": "positive", "factor_refs": {}, "patch_note": "日志只恢复出一行。"}
    ]
    tool.write_jsonl(patch_path, complete_rows)
    last_message_path.write_text(json.dumps(partial_rows[0], ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "RV3F-1",
                "batch_id": "rv3_factor_batch_01",
                "material_count": 2,
                "patch_path": str(patch_path),
                "last_message_path": str(last_message_path),
                "log_path": str(tmp_path / "logs" / "RV3F-1.jsonl"),
            }
        ],
    )

    payload = tool.recover_task_patches(tasks_path=tasks_path, output_json=None, output_md=None)

    assert payload["ok"] is True
    assert payload["tasks"][0]["source_mode"] == "existing_preserved"
    assert payload["tasks"][0]["written"] is False
    assert [row["binding_code"] for row in tool.read_jsonl(patch_path)] == ["BND-001", "BND-002"]


def test_run_plan_dry_run_delegates_to_codex_win(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "RV3F-1",
                "task_kind": "retrieval_v3_factorization",
                "prompt_path": "tmp/no-such-prompt.md",
                "expected_outputs": [
                    {
                        "kind": "jsonl_patch",
                        "path": "tmp/no-such-patch.jsonl",
                        "fallback": "last_message_marked_block",
                        "begin": "PATCH_JSONL_BEGIN",
                        "end": "PATCH_JSONL_END",
                    }
                ],
                "argv": ["codex", "exec", "-"],
            }
        ],
    )
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> object:
        calls.append(argv)

        class Completed:
            returncode = 0
            stdout = json.dumps({"tasks": [{"task_code": "RV3F-1", "status": "planned"}], "totals": {"planned": 1}}, ensure_ascii=False)
            stderr = ""

        return Completed()

    monkeypatch.setattr(tool.task_runner.subprocess, "run", fake_run)

    payload = tool.run_codex_tasks(
        tasks_path=tasks_path,
        execute=False,
        background=False,
        limit=1,
        output=None,
        agent_output_root=tmp_path / "agent",
        codex_win_bin="codex-win-test",
        max_workers=2,
        timeout_seconds=60,
        permission_profile="tmp-jsonl-review",
        deny_policy="deny-rewrite",
        write_roots=[tmp_path / "tasks"],
        git_snapshot="none",
    )

    assert payload["totals"] == {"planned": 1}
    assert payload["runner"] == "codex-win agent run-plan"
    argv = calls[0]
    assert argv[:3] == ["codex-win-test", "agent", "run-plan"]
    assert "--dry-run" in argv
    assert argv[argv.index("--max-workers") + 1] == "2"
    assert argv[argv.index("--sandbox-profile") + 1] == "local-write"
    assert argv[argv.index("--permission-profile") + 1] == "tmp-jsonl-review"
    assert argv[argv.index("--deny-policy") + 1] == "deny-rewrite"
    assert argv[argv.index("--git-snapshot") + 1] == "none"
    assert str(tmp_path / "tasks") in argv


def test_run_plan_keeps_worklist_error_type_for_invalid_runner_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    tool.write_jsonl(tasks_path, [{"task_code": "RV3F-1"}])

    class Completed:
        returncode = 1
        stdout = "not-json"
        stderr = "runner failed"

    monkeypatch.setattr(tool.task_runner.subprocess, "run", lambda *args, **kwargs: Completed())

    with pytest.raises(tool.FactorizationWorklistError, match="non-JSON stdout"):
        tool.run_codex_tasks(tasks_path=tasks_path, execute=False, background=False, limit=0, output=None)


def test_tolerate_talent_prompt_and_gate_reject_single_person_catastrophic_severity(tmp_path: Path) -> None:
    row = material_row(
        rule_code="tolerate_talent",
        direction="negative",
        claim_object_name="张亮",
        canonical_name="张亮",
        source_passages=[{"source_title": "旧唐书", "quote": "百官议其当死，遂斩张亮于市，籍没其家。"}],
    )
    assert tool.tolerate_talent_factor_issue(
        material=row, factor_name="handling_severity", value=tool.Decimal("3.2")
    ) == "catastrophic_severity_without_group_or_ecology_harm"
    batch = {"batch_id": "B-TOL", "groups": [{"materials": [tool.material_item(row, {}, {})]}]}
    prompt = task_tool.prompt_for_batch(batch=batch, output_jsonl=tmp_path / "patch.jsonl")
    assert "单一人物被处死、下狱或籍没不得选 3.2" in prompt


def test_tolerate_talent_gate_requires_quote_support_for_disputed_fault_factor() -> None:
    unsupported = material_row(
        rule_code="tolerate_talent",
        direction="negative",
        source_passages=[{"source_title": "史书", "quote": "其人谋反伏诛。"}],
    )
    supported = material_row(
        rule_code="tolerate_talent",
        direction="negative",
        source_passages=[{"source_title": "史书", "quote": "反形未具，帝后悔之。"}],
    )
    assert tool.tolerate_talent_factor_issue(
        material=unsupported, factor_name="target_fault_factor", value=tool.Decimal("0.9")
    ) == "disputed_fault_factor_without_quote_support"
    assert not tool.tolerate_talent_factor_issue(
        material=supported, factor_name="target_fault_factor", value=tool.Decimal("0.9")
    )


def test_factorization_prompt_centers_long_quote_on_claim_relevant_event() -> None:
    quote = "无关前文" * 400 + "叔孙通谏上不可易太子，高帝曰吾听公言。" + "无关后文" * 400
    excerpt = task_tool.relevant_quote_excerpt(
        quote,
        summary="高祖欲易太子时，叔孙通进谏，高帝听从。",
        object_name="叔孙通",
    )

    assert len(excerpt) <= task_tool.PROMPT_QUOTE_LIMIT + 6
    assert "叔孙通谏上不可易太子" in excerpt
    assert "吾听公言" in excerpt
