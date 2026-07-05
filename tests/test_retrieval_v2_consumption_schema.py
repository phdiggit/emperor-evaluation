from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260705_retrieval_v2_consumption.sql"


def migration_sql() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def created_tables(sql: str) -> set[str]:
    return set(re.findall(r"create table if not exists retrieval_v2\.([a-z_]+)\s*\(", sql, flags=re.IGNORECASE))


def created_table_columns(sql: str) -> dict[str, set[str]]:
    columns_by_table: dict[str, set[str]] = {}
    table_pattern = re.compile(
        r"create table if not exists retrieval_v2\.([a-z_]+)\s*\((.*?)\n\);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in table_pattern.finditer(sql):
        table = match.group(1)
        columns: set[str] = set()
        for raw_line in match.group(2).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("constraint "):
                break
            columns.add(line.split()[0].rstrip(","))
        columns_by_table[table] = columns
    return columns_by_table


def commented_tables(sql: str) -> set[str]:
    return set(re.findall(r"comment on table retrieval_v2\.([a-z_]+)\s+is\s+", sql, flags=re.IGNORECASE))


def commented_columns(sql: str) -> set[tuple[str, str]]:
    return set(
        re.findall(
            r"comment on column retrieval_v2\.([a-z_]+)\.([a-z0-9_]+)\s+is\s+",
            sql,
            flags=re.IGNORECASE,
        )
    )


def enum_types(sql: str) -> set[str]:
    return set(re.findall(r"create type retrieval_v2\.(rv2_[a-z_]+)\s+as enum", sql, flags=re.IGNORECASE))


def commented_types(sql: str) -> set[str]:
    return set(re.findall(r"comment on type retrieval_v2\.(rv2_[a-z_]+)\s+is\s+", sql, flags=re.IGNORECASE))


def test_consumption_schema_creates_only_retrieval_v2_consumption_tables() -> None:
    tables = created_tables(migration_sql())

    assert tables == {
        "claim_source_passages",
        "claim_rule_binding_candidates",
        "objects",
        "person_profiles",
        "person_affiliations",
        "person_roles",
        "object_names",
        "target_objects",
        "material_object_links",
        "target_object_attributes",
        "object_resolution_queue",
        "material_review_queue",
        "claim_rule_binding_factor_judgments",
        "claim_rule_binding_factor_choices",
        "claim_rule_binding_material_scores",
        "target_rule_score_clusters",
    }
    assert not (tables & {"raw_objs", "emp_objs", "obj_srcs", "obj_attrs", "evd_clusters", "emp_item_results"})


def test_consumption_schema_uses_enums_for_finite_value_fields() -> None:
    sql = migration_sql()

    assert enum_types(sql) == {
        "rv2_claim_direction",
        "rv2_review_status",
        "rv2_object_identity_status",
        "rv2_queue_status",
        "rv2_object_type",
        "rv2_person_talent_grade",
        "rv2_person_role_kind",
        "rv2_person_affiliation_kind",
        "rv2_object_name_kind",
        "rv2_target_object_scope",
        "rv2_target_object_attribute_kind",
        "rv2_claim_passage_relation_kind",
        "rv2_factor_target_action",
        "rv2_factor_side",
    }
    assert commented_types(sql) == enum_types(sql)
    assert "candidate_direction retrieval_v2.rv2_claim_direction" in sql
    assert "review_status retrieval_v2.rv2_review_status" in sql
    assert "identity_status retrieval_v2.rv2_object_identity_status" in sql
    assert "queue_status retrieval_v2.rv2_queue_status" in sql
    assert "object_type retrieval_v2.rv2_object_type" in sql
    assert "'person_group'" in sql
    assert "alter type retrieval_v2.rv2_object_type add value 'person_group'" in sql
    assert "talent_grade retrieval_v2.rv2_person_talent_grade" in sql
    assert "talent_grade retrieval_v2.rv2_person_talent_grade not null" not in sql
    assert "alter column talent_grade drop not null" in sql
    assert "role_kind retrieval_v2.rv2_person_role_kind" in sql
    assert "affiliation_kind retrieval_v2.rv2_person_affiliation_kind" in sql
    assert "name_kind retrieval_v2.rv2_object_name_kind" in sql
    assert "'art_name'" in sql
    assert "alter type retrieval_v2.rv2_object_name_kind add value 'art_name'" in sql
    assert "scope_code retrieval_v2.rv2_target_object_scope" in sql
    assert "attribute_kind retrieval_v2.rv2_target_object_attribute_kind" in sql
    assert "relation_kind retrieval_v2.rv2_claim_passage_relation_kind" in sql
    assert "target_action retrieval_v2.rv2_factor_target_action" in sql
    assert "side retrieval_v2.rv2_factor_side" in sql
    assert "不用 text + check 承载状态机" in sql


def test_consumption_schema_augments_existing_clean_tables_with_raw_idempotency_keys() -> None:
    sql = migration_sql()

    for column in [
        "accepted_run_fingerprint",
        "intake_manifest_path",
        "raw_document_code",
        "raw_passage_code",
        "deduped_raw_passage_codes",
        "raw_claim_code",
        "claim_summary_hash",
        "object_group_key",
        "binding_code",
        "raw_binding_code",
    ]:
        assert f"add column if not exists {column}" in sql
        assert f"comment on column retrieval_v2." in sql
        assert f".{column} is" in sql

    assert "rv2_source_documents_pack_raw_doc_uk" in sql
    assert "rv2_source_passages_doc_raw_passage_uk" in sql
    assert "rv2_material_claims_pack_raw_claim_uk" in sql
    assert "rv2_claim_rule_bindings_binding_code_uk" in sql
    assert "add constraint rv2_claim_rule_bindings_uk unique (claim_id, contract_rule_id, predicate, direction, object_role)" in sql


def test_consumption_schema_has_idempotent_review_and_candidate_keys() -> None:
    sql = migration_sql()

    assert "constraint rv2_claim_rule_binding_candidates_code_uk unique (candidate_code)" in sql
    assert "constraint rv2_claim_rule_binding_candidates_uk unique" in sql
    assert "claim_id,\n        source_rule_code,\n        candidate_item_code,\n        candidate_rule_code,\n        reason_hash" in sql
    assert "constraint rv2_objects_identity_key_uk unique (object_identity_key)" in sql
    assert "constraint rv2_person_profiles_code_uk unique (person_profile_code)" in sql
    assert "constraint rv2_person_profiles_object_uk unique (object_id)" in sql
    assert "constraint rv2_person_affiliations_code_uk unique (person_affiliation_code)" in sql
    assert "constraint rv2_person_affiliations_key_uk unique (person_affiliation_key)" in sql
    assert "constraint rv2_person_roles_code_uk unique (person_role_code)" in sql
    assert "constraint rv2_person_roles_key_uk unique (person_role_key)" in sql
    assert "constraint rv2_object_names_name_uk unique (object_id, normalized_name, name_kind)" in sql
    assert "constraint rv2_target_objects_scope_uk unique (target_id, object_id, scope_code)" in sql
    assert "constraint rv2_material_object_links_uk unique (claim_id, object_id, role)" in sql
    assert "constraint rv2_target_object_attributes_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_target_object_attributes_natural_uk unique (target_object_id, rule_code, attribute_kind, attribute_code)" in sql
    assert "constraint rv2_object_resolution_queue_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_material_review_queue_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_claim_rule_binding_factor_judgments_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_claim_rule_binding_factor_judgments_binding_uk unique (binding_id, formula_code)" in sql
    assert "constraint rv2_claim_rule_binding_factor_choices_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_claim_rule_binding_factor_choices_factor_uk unique (factor_judgment_id, factor_name)" in sql
    assert "constraint rv2_claim_rule_binding_material_scores_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_claim_rule_binding_material_scores_judgment_uk unique (factor_judgment_id)" in sql
    assert "constraint rv2_target_rule_score_clusters_idem_uk unique (idem_key)" in sql
    assert "constraint rv2_target_rule_score_clusters_target_rule_uk unique (target_id, rule_code, formula_code)" in sql


def test_consumption_schema_has_team_building_talent_adapter_view() -> None:
    sql = migration_sql()

    assert "create or replace view retrieval_v2.v_team_building_talent_candidates" in sql
    assert "from retrieval_v2.eval_rule_material_policies p" in sql
    assert "join retrieval_v2.person_profiles pp" in sql
    assert "p.rule_code = 'team_building'" in sql
    assert "p.require_attrs @> array['talent_quality']::text[]" in sql
    assert "pp.talent_grade is not null" in sql
    assert "'rule_requirement'::retrieval_v2.rv2_target_object_attribute_kind as attribute_kind" in sql
    assert "'talent_quality'::text as attribute_code" in sql
    assert "comment on view retrieval_v2.v_team_building_talent_candidates is" in sql


def test_consumption_schema_has_person_profile_name_adapter_view() -> None:
    sql = migration_sql()

    assert "create or replace view retrieval_v2.v_person_profile_names" in sql
    assert "join retrieval_v2.objects o on o.id = pp.object_id and o.object_type = 'person'" in sql
    assert "left join retrieval_v2.object_names onm on onm.object_id = o.id" in sql
    assert "onm.name_kind::text = 'courtesy_name'" in sql
    assert "onm.name_kind::text = 'art_name'" in sql
    assert "as courtesy_names" in sql
    assert "as art_names" in sql
    assert "comment on view retrieval_v2.v_person_profile_names is" in sql


def test_consumption_schema_comments_every_created_table_column_and_added_column() -> None:
    sql = migration_sql()
    tables = created_tables(sql)
    table_comments = commented_tables(sql)
    columns_by_table = created_table_columns(sql)
    column_comments = commented_columns(sql)

    assert tables - table_comments == set()
    assert table_comments - tables == set()

    missing_column_comments = sorted(
        f"{table}.{column}"
        for table, columns in columns_by_table.items()
        for column in columns
        if (table, column) not in column_comments
    )
    assert missing_column_comments == []


def test_consumption_schema_avoids_generic_note_columns_and_low_information_comment_contracts() -> None:
    sql = migration_sql()

    assert re.search(r"^\s*note\s+", sql, flags=re.MULTILINE) is None
    assert "candidate_reason is '候选原因；只写中文高信息判断，模板式原因留空。'" in sql
    assert "talent_grade_basis is '人物评价简介；非空时以 canonical 人名加中文逗号开头，只写中文具体判断和关键材料，不写模板文本。'" in sql
    assert "affiliation_basis is '归属阶段依据；只写中文具体判断和关键材料，不写模板文本。'" in sql
    assert "role_basis is '身份阶段依据；只写中文具体判断和关键材料，不写模板文本。'" in sql
    assert "attribute_basis is '规则语境属性依据；只写中文具体判断和关键材料，不写模板文本。'" in sql
    assert "diagnosis is '对象复核诊断；只写中文具体冲突、缺源或同名风险。'" in sql
    assert "review_note is '人工复核结论；只写中文具体判断，未复核时留空。'" in sql
    assert "patch_note is '因子化判断说明；只写中文具体判断和关键材料，不写模板文本。'" in sql
    assert "calc_detail is '规则信号聚合明细；保存材料分、覆盖 judgment 和公式参数。'" in sql
