from __future__ import annotations

from scripts.dev import retrieval_v2_candidate_promoter as tool


def candidate_row(**overrides):
    row = {
        "candidate_id": 10,
        "candidate_code": "CRBC-001",
        "claim_id": 100,
        "claim_code": "SPK::CLM-001",
        "candidate_contract_rule_id": 20,
        "source_item_code": "I5B",
        "source_rule_code": "i5b_item_wide",
        "candidate_item_code": "I5B",
        "candidate_rule_code": "appointment_delegation",
        "candidate_reason": "I5B-wide claim 可复用于 appointment_delegation 复核：任用、信任、授权、误任事实",
        "candidate_confidence": None,
        "review_status": "pending",
        "resolved_binding_id": None,
        "candidate_payload": {
            "route_status": "formal_candidate",
            "candidate_role": "military_commander",
            "scoring_candidate": True,
            "usable_for_scoring_cluster": True,
            "appointment_delegation_chain": {
                "has_appointment_or_authorization": True,
                "has_named_actor": True,
                "has_task_or_responsibility": True,
                "has_result_or_feedback": True,
                "has_continuity_or_reuse": False,
            },
            "source_binding": {
                "predicate": "delegated_authority",
                "object_role": "military_commander",
                "direction": "positive",
            },
        },
        "claim_direction": "positive",
        "claim_summary": "刘邦拜韩信为大将军，给兵北举燕赵、东击齐。",
        "object_name": "韩信",
        "source_link_review_status": "accepted",
        "object_id": 200,
        "target_object_id": 300,
        "object_identity_key": "person:韩信",
        "target_object_index": {
            "韩信": {
                "object_id": 200,
                "target_object_id": 300,
                "object_identity_key": "person:韩信",
                "canonical_name": "韩信",
            },
            "萧何": {
                "object_id": 201,
                "target_object_id": 301,
                "object_identity_key": "person:萧何",
                "canonical_name": "萧何",
            },
        },
        "source_link_id": 400,
        "source_link_role": "military_commander",
        "source_link_confidence": None,
        "source_pack_id": 500,
        "source_pack_code": "SPK",
        "target_id": 600,
        "target_code": "TGT-I5B-LB",
        "emperor_name": "刘邦",
    }
    payload_override = overrides.pop("candidate_payload", None)
    row.update(overrides)
    if payload_override is not None:
        row["candidate_payload"] = {**row["candidate_payload"], **payload_override}
    return row


def test_resolve_candidate_promotes_clear_appointment_delegation() -> None:
    spec, reason = tool.resolve_candidate(candidate_row(candidate_payload={"candidate_role": "delegated_actor"}))

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "appointed_or_delegated_authority"
    assert spec.object_role == "delegated_actor"
    assert spec.direction == "positive"


def test_future_hint_is_not_promoted_even_with_contract_like_fields() -> None:
    row = candidate_row(
        candidate_rule_code="power_control",
        candidate_payload={
            "hint_status": "future_rule_hint",
            "source_binding": {"predicate": "delegated_authority", "object_role": "military_delegate", "direction": "positive"},
        },
    )

    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "non_formal_rule"


def test_column_future_hint_is_not_promoted_for_formal_rule() -> None:
    row = candidate_row(
        candidate_rule_code="team_building",
        hint_status="future_rule_hint",
        candidate_payload={
            "source_binding": {"predicate": "delegated_authority", "object_role": "military_delegate", "direction": "positive"},
        },
    )

    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "future_rule_hint"


def test_disposition_only_tolerate_talent_is_left_unresolved() -> None:
    row = candidate_row(
        candidate_rule_code="tolerate_talent",
        candidate_reason="处置性材料只作为候选，不单凭处置结果定为负向",
        claim_summary="胡惟庸以谋反伏诛，随后中书省被罢、丞相等官被废。",
        candidate_payload={
            "route_status": "formal_candidate",
            "source_binding": {"predicate": "revoked_authority", "object_role": "revoked_or_failed_delegate", "direction": "negative"},
        },
        source_rule_code="appointment_delegation",
        source_link_role="revoked_or_failed_delegate",
    )

    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "unresolved_tolerate_talent"


def test_talent_discovery_does_not_treat_city_capture_as_promotion() -> None:
    row = candidate_row(
        candidate_rule_code="talent_discovery",
        claim_summary="张掖太守彭晃叛吕光，东结康宁、西通王穆，吕光攻拔其城并诛彭晃。",
        candidate_payload={
            "route_status": "formal_candidate",
            "source_binding": {"predicate": "delegated_authority", "object_role": "military_delegate", "direction": "positive"},
        },
    )

    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "unresolved_talent_discovery"


def test_talent_discovery_recommended_chain_scores_recommended_person() -> None:
    row = candidate_row(
        candidate_rule_code="talent_discovery",
        candidate_reason="萧何识别并荐举韩信，直接触发拜大将军。",
        claim_summary="萧何追还韩信并向汉王荐举，汉王拜韩信为大将军。",
        object_name="萧何",
        object_id=201,
        target_object_id=301,
        object_identity_key="person:萧何",
        object_canonical_name="萧何",
        source_link_role="claim_object",
    )

    plan = tool.build_plan([row])

    assert plan["totals"]["promotions"] == 1
    promotion = plan["promotions"][0]
    assert promotion["object_name"] == "韩信"
    assert promotion["object_id"] == 200
    assert promotion["target_object_id"] == 300
    assert promotion["object_role"] == "recommended_talent"
    assert promotion["source_object_name"] == "萧何"
    assert promotion["link_code"] == tool.material_link_code_for(row, "recommended_talent", object_identity_key="person:韩信")
    assert promotion["link_code"] != tool.material_link_code_for(row, "recommended_talent")


def test_talent_discovery_uses_explicit_target_talent_payload() -> None:
    row = candidate_row(
        candidate_rule_code="talent_discovery",
        candidate_reason="王陵识别张苍并向沛公进言使其免死。",
        claim_summary="王陵见张苍为美士，乃言沛公，赦勿斩。",
        object_name="王陵",
        object_id=210,
        target_object_id=310,
        object_identity_key="person:王陵",
        object_canonical_name="王陵",
        candidate_payload={
            "target_object": "张苍",
            "source_binding": {"rule_code": "talent_discovery"},
        },
        target_object_index={
            "张苍": {
                "object_id": 211,
                "target_object_id": 311,
                "object_identity_key": "person:张苍",
                "canonical_name": "张苍",
            }
        },
    )

    plan = tool.build_plan([row])

    assert plan["totals"]["promotions"] == 1
    assert plan["promotions"][0]["object_name"] == "张苍"
    assert plan["promotions"][0]["object_role"] == "recognized_talent"


def test_anti_nepotism_does_not_promote_generic_family_aftermath() -> None:
    row = candidate_row(
        candidate_rule_code="anti_nepotism",
        claim_summary="霍光久摄不归政，家族后被夷灭，显示授权后果有负面争议。",
        candidate_payload={
            "route_status": "formal_candidate",
            "source_binding": {"predicate": "revoked_authority", "object_role": "revoked_or_failed_delegate", "direction": "negative"},
        },
        source_link_role="revoked_or_failed_delegate",
    )

    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "unresolved_anti_nepotism"


def test_team_building_promotes_non_core_pool_member() -> None:
    row = candidate_row(
        candidate_rule_code="team_building",
        claim_summary="泰定年间王翀迁国子司业，后出任河南左右司郎中。",
        candidate_payload={
            "route_status": "formal_candidate",
            "source_binding": {"predicate": "delegated_authority", "object_role": "civil_delegate", "direction": "positive"},
        },
        source_link_role="civil_delegate",
    )

    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "team_member"
    assert spec.object_role == "team_member"
    assert spec.direction == "positive"
    assert spec.reason_code == "team_pool_member"


def test_team_building_promotes_negative_pool_member() -> None:
    row = candidate_row(
        candidate_rule_code="team_building",
        claim_summary="某近臣久居要地，任用污染人才结构。",
        candidate_payload={
            "route_status": "formal_candidate",
            "source_binding": {"predicate": "misappointed_person", "object_role": "misappointed_person", "direction": "negative"},
        },
        source_link_role="misappointed_person",
    )

    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "team_member"
    assert spec.object_role == "team_member"
    assert spec.direction == "negative"
    assert spec.reason_code == "team_pool_member"


def test_item_wide_candidate_uses_claim_direction_when_source_binding_direction_missing() -> None:
    row = candidate_row(
        source_rule_code="i5b_item_wide",
        candidate_rule_code="team_building",
        candidate_payload={
            "source_binding": {
                "rule_code": "team_building",
                "reason": "高祖明言萧何能镇国家、抚百姓、给饷馈，是取天下三名人杰之一。",
            }
        },
        claim_summary="高祖明言萧何能镇国家、抚百姓、给饷馈、不绝粮道，是取天下的三名人杰之一。",
        claim_direction="positive",
        source_link_role="claim_object",
    )

    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "team_member"


def test_tolerate_talent_does_not_promote_generic_protect_city_text() -> None:
    row = candidate_row(
        candidate_rule_code="tolerate_talent",
        claim_summary="完颜承晖将兵事委付抹撚尽忠，自总持大纲保全都城。",
        candidate_payload={
            "route_status": "formal_candidate",
            "source_binding": {"predicate": "delegated_authority", "object_role": "military_delegate", "direction": "positive"},
        },
        source_link_role="military_delegate",
    )

    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "unresolved_tolerate_talent"


def test_item_wide_tolerate_talent_promotes_harmed_talent_for_factorization() -> None:
    row = candidate_row(
        source_rule_code="i5b_item_wide",
        candidate_rule_code="tolerate_talent",
        claim_direction="negative",
        object_name="彭越",
        claim_summary="汉诛杀彭越后，英布因恐惧同功者相继被杀而起疑聚兵。",
        candidate_payload={"source_binding": {"rule_code": "tolerate_talent"}},
    )

    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "harmed_talent"
    assert spec.object_role == "harmed_talent"
    assert spec.direction == "negative"
    assert spec.reason_code == "item_wide_harmed_talent"


def test_item_wide_harmed_talent_uses_fact_object_as_victim() -> None:
    row = candidate_row(
        source_rule_code="i5b_item_wide",
        candidate_rule_code="tolerate_talent",
        claim_direction="negative",
        object_name="吕后",
        claim_summary="吕后与萧相国合谋诈召韩信入贺，并使武士缚斩韩信，夷其三族。",
        claim_payload={
            "fact_payload": {
                "action_type": "处置",
                "actor": "吕后",
                "object": "韩信",
                "outcome": "韩信被斩并夷三族",
            }
        },
        candidate_payload={"source_binding": {"rule_code": "tolerate_talent"}},
    )

    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.object_name_override == "韩信"


def test_missing_candidate_id_is_not_promoted() -> None:
    row = candidate_row(
        candidate_id=None,
        candidate_rule_code="appointment_delegation",
        source_rule_code="i5b_item_wide",
        claim_direction="positive",
        candidate_payload={"route_status": "formal_candidate"},
    )
    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "missing_candidate_id"


def test_item_wide_appointment_delegation_protocol_candidate_is_usable_for_scoring() -> None:
    row = candidate_row(
        candidate_rule_code="appointment_delegation",
        source_rule_code="i5b_item_wide",
        claim_direction="positive",
        candidate_payload={
            "candidate_role": "entrusted_actor",
            "scoring_candidate": True,
            "usable_for_scoring_cluster": True,
            "appointment_delegation_chain": {
                "has_appointment_or_authorization": True,
                "has_named_actor": True,
                "has_task_or_responsibility": True,
                "has_result_or_feedback": True,
                "has_continuity_or_reuse": False,
            },
        },
    )
    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.object_role == "entrusted_actor"
    assert tool.promotion_usable_for_scoring(row, spec) is True


def test_item_wide_appointment_delegation_protocol_requires_complete_chain_for_scoring() -> None:
    row = candidate_row(
        candidate_rule_code="appointment_delegation",
        source_rule_code="i5b_item_wide",
        claim_direction="positive",
        candidate_payload={
            "candidate_role": "delegated_actor",
            "scoring_candidate": True,
            "usable_for_scoring_cluster": True,
            "appointment_delegation_chain": {
                "has_appointment_or_authorization": True,
                "has_named_actor": True,
                "has_task_or_responsibility": True,
                "has_result_or_feedback": False,
                "has_continuity_or_reuse": False,
            },
        },
    )
    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "appointment_delegation_not_scoring_candidate"


def test_item_wide_appointment_delegation_protocol_reads_nested_source_binding_payload() -> None:
    row = candidate_row(
        candidate_rule_code="appointment_delegation",
        source_rule_code="i5b_item_wide",
        claim_direction="positive",
        candidate_payload={
            "source_binding": {
                "rule_code": "appointment_delegation",
                "candidate_payload": {
                    "candidate_role": "military_commander",
                    "scoring_candidate": True,
                    "usable_for_scoring_cluster": True,
                    "appointment_delegation_chain": {
                        "has_appointment_or_authorization": True,
                        "has_named_actor": True,
                        "has_task_or_responsibility": True,
                        "has_result_or_feedback": True,
                        "has_continuity_or_reuse": False,
                    },
                },
            }
        },
    )
    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.object_role == "military_commander"
    assert tool.promotion_usable_for_scoring(row, spec) is True


def test_item_wide_appointment_delegation_protocol_rejects_neutral_direction() -> None:
    row = candidate_row(
        candidate_rule_code="appointment_delegation",
        source_rule_code="i5b_item_wide",
        claim_direction="neutral",
        candidate_payload={
            "source_binding": {
                "rule_code": "appointment_delegation",
                "direction": "neutral",
                "candidate_payload": {
                    "candidate_role": "strategic_advisor",
                    "scoring_candidate": True,
                    "usable_for_scoring_cluster": True,
                    "appointment_delegation_chain": {
                        "has_appointment_or_authorization": True,
                        "has_named_actor": True,
                        "has_task_or_responsibility": True,
                        "has_result_or_feedback": True,
                        "has_continuity_or_reuse": False,
                    },
                },
            }
        },
    )
    spec, reason = tool.resolve_candidate(row)

    assert spec is None
    assert reason == "appointment_delegation_not_scoring_candidate"


def test_item_wide_harmed_talent_promotion_is_usable_for_factorization_review() -> None:
    row = candidate_row(
        source_rule_code="i5b_item_wide",
        candidate_rule_code="tolerate_talent",
        claim_direction="negative",
        object_name="彭越",
        claim_summary="汉诛杀彭越后，英布因恐惧同功者相继被杀而起疑聚兵。",
        candidate_payload={"source_binding": {"rule_code": "tolerate_talent"}},
    )
    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert spec.reason_code == "item_wide_harmed_talent"
    assert tool.promotion_usable_for_scoring(row, spec) is True


def test_candidate_payload_can_block_scoring_promotion() -> None:
    row = candidate_row(
        candidate_rule_code="appointment_delegation",
        candidate_payload={
            "source_binding": {
                "predicate": "delegated_authority",
                "direction": "positive",
                "candidate_payload": {"usable_for_scoring_cluster": False},
            }
        },
    )
    spec, reason = tool.resolve_candidate(row)

    assert reason == ""
    assert spec is not None
    assert tool.promotion_usable_for_scoring(row, spec) is False


def test_scope_predicate_defaults_to_latest_accepted_passed_pack() -> None:
    predicate = tool.scope_predicate("accepted-packs")

    assert "distinct on (sp2.target_id, sp2.contract_id)" in predicate
    assert "coverage_status = 'passed'" in predicate


def test_fetch_candidate_rows_uses_fallback_object_link_when_source_role_blank() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""
            self.params = None

        def execute(self, sql: str, params=None) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self):
            return []

    cur = FakeCursor()

    rows = tool.fetch_candidate_rows(
        cur,
        item_code="I5B",
        source_rule_code="i5b_item_wide",
        scope="accepted-packs",
        candidate_rule_codes=[],
        emperors=[],
        source_pack_codes=[],
    )

    assert rows == []
    assert "left join lateral" in cur.sql
    assert "mol1.role = 'claim_object'" in cur.sql


def test_fetch_candidate_rows_can_filter_explicit_source_pack() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self.sql = ""
            self.params = None

        def execute(self, sql: str, params=None) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self):
            return []

    cur = FakeCursor()

    rows = tool.fetch_candidate_rows(
        cur,
        item_code="I5B",
        source_rule_code="i5b_item_wide",
        scope="accepted-packs",
        candidate_rule_codes=["tolerate_talent"],
        emperors=["刘邦"],
        source_pack_codes=["SPK-I5B-SHADOW"],
    )

    assert rows == []
    assert "sp.pack_code = any(%s)" in cur.sql
    assert "sp2.status = 'accepted'" not in cur.sql
    assert cur.params[-1] == ["SPK-I5B-SHADOW"]


def test_resolve_item_wide_appointment_delegation_promotes_claim_direction() -> None:
    spec, reason = tool.resolve_candidate(
        candidate_row(
            candidate_rule_code="appointment_delegation",
            source_rule_code="i5b_item_wide",
            claim_direction="negative",
            candidate_payload={"candidate_role": "misdelegated_actor"},
        )
    )

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "misappointed_or_misdelegated_authority"
    assert spec.object_role == "misdelegated_actor"
    assert spec.direction == "negative"


def test_build_plan_promotes_and_skips_with_counts() -> None:
    rows = [
        candidate_row(),
        candidate_row(candidate_code="CRBC-002", resolved_binding_id=99),
        candidate_row(candidate_code="CRBC-003", has_open_material_review=True),
    ]

    plan = tool.build_plan(rows)

    assert plan["totals"]["candidate_rows"] == 3
    assert plan["totals"]["promotions"] == 2
    assert plan["totals"]["skipped"] == 1
    assert plan["promoted_by_rule"] == {"appointment_delegation": 2}
    assert plan["skipped_by_reason"] == {"material_review_pending": 1}


def test_resolved_candidate_can_be_replayed_for_idempotent_repair() -> None:
    spec, reason = tool.resolve_candidate(candidate_row(review_status="resolved", resolved_binding_id=99))

    assert reason == ""
    assert spec is not None
    assert spec.predicate == "appointed_or_delegated_authority"


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[object] = []
        self.next_id = 1000
        self.fetchall_rows: list[dict[str, object]] = []

    def execute(self, sql: str, params=None) -> None:
        self.statements.append(sql)
        self.params.append(params)

    def fetchone(self):
        self.next_id += 1
        return {"id": self.next_id}

    def fetchall(self):
        return self.fetchall_rows


def test_execute_promotions_writes_binding_link_and_resolves_candidate() -> None:
    row = candidate_row()
    plan = tool.build_plan([row])
    cur = FakeCursor()

    counts = tool.execute_promotions(cur, plan["promotions"])

    assert counts == {
        "retrieval_v2.claim_rule_binding_candidates": 1,
        "retrieval_v2.claim_rule_bindings": 1,
        "retrieval_v2.material_object_links": 1,
    }
    joined = "\n".join(cur.statements)
    assert "insert into retrieval_v2.claim_rule_bindings" in joined
    assert "retrieval_v2.claim_rule_bindings.usable_for_scoring_cluster" in joined
    assert "or excluded.usable_for_scoring_cluster" in joined
    assert "binding_payload = retrieval_v2.claim_rule_bindings.binding_payload || excluded.binding_payload" in joined
    assert "update retrieval_v2.claim_rule_bindings" in joined
    assert "promoted_material_object_link_id" in str(cur.params)
    assert "promoted_object_name" in str(cur.params)


def test_reconcile_scoring_gates_updates_existing_promoter_bindings() -> None:
    cur = FakeCursor()
    cur.fetchall_rows = [{"id": 1}, {"id": 2}]

    updated = tool.reconcile_scoring_gates(
        cur,
        item_code="I5B",
        scope="accepted-packs",
        emperors=["刘邦"],
        source_pack_codes=["SPK-I5B-WIDE"],
    )

    assert updated == 2
    sql = cur.statements[-1]
    assert "update retrieval_v2.claim_rule_bindings crb" in sql
    assert "reason_code" in sql and "review" in sql
    assert "usable_for_scoring_cluster' = 'false'" in sql
    assert "sp.pack_code = any(%s)" in sql
    assert cur.params[-1] == [["SPK-I5B-WIDE"], "I5B", "I5B", ["刘邦"]]
