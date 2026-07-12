from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_rule_scorer as tool


def judgment(
    judgment_id: int,
    *,
    value: str,
    object_id: int = 100,
    binding_code: str | None = None,
    claim_id: int | None = None,
    predicate: str = "appointed_or_delegated_authority",
    object_role: str = "civil_delegate",
    rule_code: str = "appointment_delegation",
    side: str = "positive",
    choices: tuple[tool.FactorChoice, ...] | None = None,
) -> tool.JudgmentInput:
    return tool.JudgmentInput(
        factor_judgment_id=judgment_id,
        binding_id=judgment_id + 1000,
        binding_code=binding_code or f"BND-{judgment_id}",
        claim_id=claim_id if claim_id is not None else judgment_id + 2000,
        target_id=1,
        target_code="RT-I5B-LB",
        emperor_name="刘邦",
        source_pack_id=10,
        item_code="I5B",
        rule_code=rule_code,
        formula_code="evidence_cluster_signal_v3",
        target_action="score",
        side=side,
        predicate=predicate,
        object_role=object_role,
        object_id=object_id,
        target_object_id=object_id + 5000,
        object_name="萧何",
        claim_key=f"CLMK-{judgment_id}",
        event_group_keys=(f"CEG-{judgment_id}",),
        source_document_codes=(f"DOC-{judgment_id}",),
        choices=choices or (tool.FactorChoice("source_factor", "基础史源", "SRC", Decimal(value)),),
    )


def test_compute_target_cluster_applies_same_object_decay() -> None:
    cluster = tool.compute_target_cluster([judgment(1, value="2.0"), judgment(2, value="1.0")])

    assert cluster["positive_signal"] == Decimal("2.350")
    assert cluster["negative_signal"] == Decimal("0.000")
    assert cluster["action_counts"] == {"score": 2}
    assert cluster["calc_detail"]["object_side_scores"]["positive"]["100"]["score"] == "2.350"


def test_appointment_policy_uses_all_material_rank_decay_without_aggregation_cap() -> None:
    cluster = tool.compute_target_cluster(
        [judgment(1, value="2.0", claim_id=2001), judgment(2, value="1.0", claim_id=2002)],
        material_policy={
            "policy_code": "POL-I5B-APPOINTMENT",
            "policy_version": "v3-native-density-decay-20260711",
            "carrier_mode": "claim_materials",
            "policy_payload": {"side_aggregation": {
                "mode": "hierarchical_rank_decay",
                "material_decay": "1",
                "event_decay": "1",
                "object_decay": "0.5",
                "positive_lane_scale": "1.5",
                "negative_lane_scale": "1.0",
            }},
        },
    )

    assert cluster["positive_signal"] == Decimal("3.750")
    assert cluster["action_counts"]["score"] == 2
    assert cluster["calc_detail"]["aggregation_policy"]["all_scored_materials_contribute"] is True
    assert cluster["calc_detail"]["aggregation_policy"]["hard_aggregation_cap"] is False
    assert cluster["calc_detail"]["aggregation_policy"]["policy_version"] == "v3-native-density-decay-20260711"
    assert cluster["calc_detail"]["rank_decay_detail"]["positive"]["material_count"] == 2


def test_rank_decay_activation_is_policy_driven_not_rule_code_driven() -> None:
    cluster = tool.compute_target_cluster(
        [judgment(1, value="2.0", rule_code="talent_discovery")],
        material_policy={
            "policy_code": "POL-I5B-TALENT",
            "policy_version": "test-density-decay",
            "carrier_mode": "claim_materials",
            "policy_payload": {"side_aggregation": {
                "mode": "hierarchical_rank_decay",
                "material_decay": "1",
                "event_decay": "1",
                "object_decay": "0.5",
                "positive_lane_scale": "1.5",
                "negative_lane_scale": "1",
            }},
        },
    )

    assert cluster["rule_code"] == "talent_discovery"
    assert cluster["positive_signal"] == Decimal("3.000")
    assert cluster["calc_detail"]["aggregation_policy"]["mode"] == "hierarchical_rank_decay"


def test_compute_target_cluster_sums_across_objects_without_rule_level_compression() -> None:
    cluster = tool.compute_target_cluster(
        [
            judgment(1, value="3.0", object_id=100),
            judgment(2, value="4.0", object_id=200),
        ]
    )

    assert cluster["calc_detail"]["object_side_scores"]["positive"]["100"]["score"] == "3.000"
    assert cluster["calc_detail"]["object_side_scores"]["positive"]["200"]["score"] == "4.000"
    assert cluster["positive_signal"] == Decimal("7.000")
    assert cluster["negative_signal"] == Decimal("0.000")


def test_compute_target_cluster_dedupes_same_claim_object_side() -> None:
    cluster = tool.compute_target_cluster(
        [
            judgment(1, value="2.0", claim_id=2000, object_role="revoked_or_failed_delegate"),
            judgment(2, value="2.0", claim_id=2000, object_role="military_delegate"),
        ]
    )

    assert cluster["positive_signal"] == Decimal("2.000")
    assert cluster["action_counts"]["score"] == 1
    assert len(cluster["material_scores"]) == 1
    assert cluster["calc_detail"]["scored_factor_judgment_ids"] == [1]
    assert cluster["calc_detail"]["deduped_factor_judgment_ids"] == [2]
    assert cluster["calc_detail"]["deduped_material_scores"][0]["reason"] == "same_claim_object_side"


def test_material_score_caps_single_material_at_four() -> None:
    score = tool.score_material(judgment(1, value="5.5"))

    assert score.raw_score == Decimal("5.500")
    assert score.abs_score == Decimal("4.000")


def test_compute_target_cluster_routes_negative_raw_score_to_negative_side() -> None:
    cluster = tool.compute_target_cluster(
        [
            judgment(
                1,
                value="1.0",
                rule_code="talent_discovery",
                choices=(tool.FactorChoice("discovery_level", "识人失败", "BAD", Decimal("-2.0")),),
            )
        ]
    )

    assert cluster["positive_signal"] == Decimal("0.000")
    assert cluster["negative_signal"] == Decimal("2.000")
    assert cluster["material_scores"][0].score_side == "negative"
    assert cluster["calc_detail"]["materials"][0]["side"] == "negative"
    assert cluster["calc_detail"]["materials"][0]["judgment_side"] == "positive"
    assert cluster["calc_detail"]["object_side_scores"]["negative"]["100"]["score"] == "2.000"


def test_compute_target_cluster_keeps_negative_side_for_positive_severity_score() -> None:
    cluster = tool.compute_target_cluster(
        [
            judgment(
                1,
                value="1.5",
                rule_code="tolerate_talent",
                side="negative",
                choices=(tool.FactorChoice("handling_severity", "严重处置", "BAD", Decimal("1.5")),),
            )
        ]
    )

    assert cluster["positive_signal"] == Decimal("0.000")
    assert cluster["negative_signal"] == Decimal("1.500")
    assert cluster["material_scores"][0].score_side == "negative"


def test_compute_team_building_cluster_uses_team_quality_formula() -> None:
    choices = (
        tool.FactorChoice("role_complementarity_factor", "较强互补", "COMP", Decimal("1.15")),
        tool.FactorChoice("long_term_stability_factor", "长期稳定核心班底", "STABLE", Decimal("1.15")),
    )
    cluster = tool.compute_target_cluster(
        [
            judgment(
                1,
                value="1.0",
                object_id=10,
                rule_code="team_building",
                choices=(
                    tool.FactorChoice("talent_quality_factor", "历史级人才。", "T1", Decimal("2.00")),
                    *choices,
                ),
            ),
            judgment(
                2,
                value="1.0",
                object_id=20,
                rule_code="team_building",
                choices=(
                    tool.FactorChoice("talent_quality_factor", "顶级人才。", "T2", Decimal("1.35")),
                    *choices,
                ),
            ),
            judgment(
                3,
                value="1.0",
                object_id=30,
                rule_code="team_building",
                choices=(
                    tool.FactorChoice("talent_quality_factor", "重要人才。", "T3", Decimal("1.00")),
                    *choices,
                ),
            ),
        ],
        material_policy={"carrier_mode": "team_core_members"},
    )

    assert cluster["positive_signal"] == Decimal("5.753")
    assert cluster["negative_signal"] == Decimal("0.000")
    assert [item["object_contribution"] for item in cluster["calc_detail"]["team_object_components"]] == ["2.000", "1.350", "1.000"]
    assert cluster["calc_detail"]["team_pool_values"] == {"positive": "4.350", "negative": "0.000"}


def test_compute_team_building_cluster_dedupes_same_object_once() -> None:
    choices = (
        tool.FactorChoice("role_complementarity_factor", "常规互补", "COMP", Decimal("1.00")),
        tool.FactorChoice("long_term_stability_factor", "稳定团队", "STABLE", Decimal("1.00")),
    )
    cluster = tool.compute_target_cluster(
        [
            judgment(
                1,
                value="1.0",
                object_id=10,
                rule_code="team_building",
                choices=(tool.FactorChoice("talent_quality_factor", "重要人才。", "T3", Decimal("0.90")), *choices),
            ),
            judgment(
                2,
                value="1.0",
                object_id=10,
                rule_code="team_building",
                choices=(tool.FactorChoice("talent_quality_factor", "顶级人才。", "T2", Decimal("1.20")), *choices),
            ),
        ],
        material_policy={"carrier_mode": "team_core_members"},
    )

    assert cluster["positive_signal"] == Decimal("1.200")
    assert cluster["calc_detail"]["duplicate_team_objects"] == [
        {
            "object_key": "10",
            "kept_binding_code": "BND-2",
            "dropped_binding_code": "BND-1",
            "reason": "same_team_object",
        }
    ]


def test_material_score_rejects_positive_side_negative_appointment_effect() -> None:
    bad = judgment(
        1,
        value="1.0",
        choices=(
            tool.FactorChoice("appointment_effect", "效果较差", "BAD", Decimal("-0.700")),
        ),
    )

    with pytest.raises(tool.RetrievalV3RuleScorerError, match="positive side cannot use negative appointment_effect"):
        tool.score_material(bad)


def flat_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for judgment_id, value in [(1, "2.0"), (2, "1.0")]:
        rows.append(
            {
                "factor_judgment_id": judgment_id,
                "binding_id": judgment_id + 1000,
                "binding_code": f"BND-{judgment_id}",
                "claim_id": judgment_id + 2000,
                "target_id": 1,
                "target_code": "RT-I5B-LB",
                "emperor_name": "刘邦",
                "source_pack_id": 10,
                "item_code": "I5B",
                "rule_code": "appointment_delegation",
                "formula_code": "evidence_cluster_signal_v3",
                "target_action": "score",
                "side": "positive",
                "object_role": "civil_delegate",
                "object_id": 100,
                "target_object_id": 5100,
                "object_name": "萧何",
                "factor_name": "source_factor",
                "option_label": "基础史源",
                "option_code": "SRC",
                "value_num": value,
                "active_factor_option_id": judgment_id + 3000,
                "active_value_num": value,
            }
        )
    rows.append(
        {
            "factor_judgment_id": 3,
            "binding_id": 1003,
            "binding_code": "BND-3",
            "claim_id": 2003,
            "target_id": 1,
            "target_code": "RT-I5B-LB",
            "emperor_name": "刘邦",
            "source_pack_id": 10,
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "target_action": "supporting_only",
            "side": "positive",
            "object_role": "civil_delegate",
            "object_id": 100,
            "target_object_id": 5100,
            "object_name": "萧何",
            "factor_name": "",
            "option_label": "",
            "option_code": "",
            "value_num": None,
            "active_factor_option_id": None,
            "active_value_num": None,
        }
    )
    return rows


def test_build_judgments_rejects_stale_factor_choice() -> None:
    rows = flat_rows()
    rows[0]["active_factor_option_id"] = None

    with pytest.raises(tool.RetrievalV3RuleScorerError, match="stale or unknown factor option"):
        tool.build_judgments(rows)


def test_build_judgments_rejects_stale_factor_value() -> None:
    rows = flat_rows()
    rows[0]["active_value_num"] = "1.0"

    with pytest.raises(tool.RetrievalV3RuleScorerError, match="stale factor value"):
        tool.build_judgments(rows)


def test_build_judgments_rejects_appointment_delegation_non_scoring_candidate() -> None:
    rows = flat_rows()
    for row in rows:
        if row["binding_code"] == "BND-1":
            row["binding_payload"] = {"source": "retrieval_v3_candidate_promoter", "candidate_id": 10}
            row["candidate_id"] = 10
            row["candidate_code"] = "CRBC-BLOCKED"
            row["candidate_payload"] = {
                "scoring_candidate": False,
                "usable_for_scoring_cluster": False,
                "appointment_delegation_chain": {
                    "has_appointment_or_authorization": False,
                    "has_named_actor": True,
                    "has_task_or_responsibility": False,
                    "has_result_or_feedback": False,
                },
            }

    with pytest.raises(tool.RetrievalV3RuleScorerError, match="candidate_payload is not scoring_candidate"):
        tool.build_judgments(rows)


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn
        self.rows: list[dict] = []
        self.rowcount = 0

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        lowered = sql.lower()
        routed = lowered.replace("retrieval_v3", "retrieval_v3")
        self.conn.statements.append(lowered)
        self.conn.params.append(params or ())
        if "from retrieval_v3.eval_rule_material_policies" in routed:
            self.rows = [dict(row) for row in self.conn.material_policy_rows]
            self.rowcount = len(self.rows)
            return
        if "group by j.formula_code" in routed:
            self.rows = [dict(row) for row in self.conn.alternate_formula_rows]
            self.rowcount = len(self.rows)
            return
        if "select distinct" in routed and "rt.id as target_id" in routed:
            self.rows = [dict(row) for row in self.conn.scoring_target_rows]
            self.rowcount = len(self.rows)
            return
        if "from retrieval_v3.claim_rule_binding_factor_judgments j" in routed:
            self.rows = [dict(row) for row in self.conn.judgment_rows]
            self.rowcount = len(self.rows)
            return
        self.rows = []
        self.rowcount = 1

    def fetchall(self) -> list[dict]:
        return self.rows


class FakeConnection:
    def __init__(self) -> None:
        self.judgment_rows = flat_rows()
        self.alternate_formula_rows: list[dict[str, object]] = []
        self.scoring_target_rows: list[dict[str, object]] = [
            {
                "target_id": 1,
                "target_code": "RT-I5B-LB",
                "emperor_name": "刘邦",
                "item_code": "I5B",
            }
        ]
        self.material_policy_rows: list[dict[str, object]] = [
            {
                "id": 1,
                "policy_code": "person_material_policy",
                "selection_priority": 100,
                "carrier_mode": "obj_src_material",
                "material_source": "obj_srcs",
                "policy_payload": {},
            }
        ]
        self.statements: list[str] = []
        self.params: list[object] = []
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakePsycopg:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def connect(self, *args, **kwargs) -> FakeConnection:
        return self.conn


def patch_fake_db(monkeypatch) -> FakeConnection:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))
    return conn


def test_apply_rule_scores_defaults_to_db_backed_dry_run(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.apply_rule_scores(
        dsn="postgresql://fake",
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["write_db"] is False
    assert payload["totals"] == {"targets": 1, "judgments": 3, "material_scores": 2, "deduped_material_scores": 0}
    assert payload["clusters"][0]["positive_signal"] == "2.350"
    assert payload["detailed_clusters"][0]["calc_detail"]["materials"][0]["binding_code"] == "BND-1"
    assert payload["detailed_clusters"][0]["calc_detail"]["object_side_scores"]["positive"]["100"]["score"] == "2.350"
    assert payload["applied_counts"]["retrieval_v3.claim_rule_binding_material_scores"] == 2
    assert payload["applied_counts"]["retrieval_v3.target_rule_score_clusters"] == 1
    assert conn.rolled_back is True
    assert any("insert into retrieval_v3.claim_rule_binding_material_scores" in statement for statement in conn.statements)
    assert any("insert into retrieval_v3.target_rule_score_clusters" in statement for statement in conn.statements)
    assert any("from retrieval_v3.material_review_queue mrq" in statement for statement in conn.statements)
    assert any("from retrieval_v3.eval_rule_material_policies" in statement for statement in conn.statements)
    assert any("mrq.claim_id = j.claim_id" in statement for statement in conn.statements)
    assert any("b.usable_for_scoring_cluster" in statement for statement in conn.statements)
    assert any("claim_rule_binding_candidates c0" in statement for statement in conn.statements)
    assert any("c0.resolved_binding_id = b.id" in statement for statement in conn.statements)
    assert any("promoted_material_object_link_id" in statement for statement in conn.statements)
    assert any("coalesce(b.binding_payload->>'promoted_material_object_link_id', '')" in statement for statement in conn.statements)
    assert any("mol1.id = (b.binding_payload->>'promoted_material_object_link_id')::bigint" in statement for statement in conn.statements)
    assert any("sp.coverage_status = 'passed'" in statement for statement in conn.statements)
    assert any("from retrieval_v3.claim_rule_binding_factor_judgments j" in statement for statement in conn.statements)
    assert any("j.target_id = rt.id" in statement for statement in conn.statements)
    generated_codes = [value for params in conn.params for value in params if isinstance(value, str)]
    assert any(value.startswith("RV3MS-") for value in generated_codes)
    assert any(value.startswith("RV3RS-") for value in generated_codes)


def test_apply_rule_scores_can_read_explicit_source_pack_without_accepted_scope(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.apply_rule_scores(
        dsn="postgresql://fake",
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        source_pack_codes=["SPK-I5B-SHADOW"],
        execute=False,
    )

    assert payload["source_pack_codes"] == ["SPK-I5B-SHADOW"]
    assert conn.rolled_back is True
    assert any("sp.pack_code = any(%s)" in statement for statement in conn.statements)
    assert not any("sp2.status = 'accepted'" in statement for statement in conn.statements)
    assert any(params == ("I5B", "appointment_delegation", "evidence_cluster_signal_v3", ["SPK-I5B-SHADOW"], "", "") for params in conn.params)


def test_apply_rule_scores_blocks_explicit_source_pack_execute_by_default(monkeypatch) -> None:
    patch_fake_db(monkeypatch)

    with pytest.raises(tool.RetrievalV3RuleScorerError, match="dry-run by default"):
        tool.apply_rule_scores(
            dsn="postgresql://fake",
            item_code="I5B",
            rule_code="appointment_delegation",
            formula_code="evidence_cluster_signal_v3",
            source_pack_codes=["SPK-I5B-SHADOW"],
            execute=True,
        )


def test_apply_rule_scores_can_add_supplemental_pack_to_latest_accepted_scope(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)

    payload = tool.apply_rule_scores(
        dsn="postgresql://fake",
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        supplemental_source_pack_codes=["SPK-I5B-SUPPLEMENT"],
        execute=False,
    )

    assert payload["source_pack_codes"] == []
    assert payload["supplemental_source_pack_codes"] == ["SPK-I5B-SUPPLEMENT"]
    assert any("distinct on (sp2.target_id, sp2.contract_id)" in statement for statement in conn.statements)
    assert any("or sp.pack_code = any(%s)" in statement for statement in conn.statements)
    assert any(
        params == ("I5B", "appointment_delegation", "evidence_cluster_signal_v3", ["SPK-I5B-SUPPLEMENT"], "", "")
        for params in conn.params
    )


def test_apply_rule_scores_rejects_empty_wrong_formula_when_alternates_exist(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.judgment_rows = []
    conn.alternate_formula_rows = [
        {"formula_code": "evidence_cluster_signal_v3", "judgment_count": 18, "target_count": 1}
    ]

    with pytest.raises(tool.RetrievalV3RuleScorerError, match="available formula judgments"):
        tool.apply_rule_scores(
            dsn="postgresql://fake",
            item_code="I5B",
            rule_code="appointment_delegation",
            formula_code="standard",
            execute=False,
        )


def test_apply_rule_scores_writes_zero_cluster_when_no_usable_judgments(monkeypatch) -> None:
    conn = patch_fake_db(monkeypatch)
    conn.judgment_rows = []
    conn.alternate_formula_rows = []

    payload = tool.apply_rule_scores(
        dsn="postgresql://fake",
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        execute=False,
    )

    assert payload["totals"] == {"targets": 1, "judgments": 0, "material_scores": 0, "deduped_material_scores": 0}
    assert payload["clusters"][0]["positive_signal"] == "0"
    assert payload["clusters"][0]["negative_signal"] == "0"
    assert payload["clusters"][0]["action_counts"] == {"score": 0, "supporting_only": 0, "exclude": 0}
    assert any("delete from retrieval_v3.claim_rule_binding_material_scores" in statement for statement in conn.statements)
    assert any("insert into retrieval_v3.target_rule_score_clusters" in statement for statement in conn.statements)


def test_cli_apply_writes_report(tmp_path: Path, monkeypatch, capsys) -> None:
    conn = patch_fake_db(monkeypatch)
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "postgresql://fake")
    output_json = tmp_path / "score.json"

    assert tool.main([
        "apply",
        "--output-json",
        str(output_json),
    ]) == 0

    assert conn.rolled_back is True
    totals = json.loads(output_json.read_text(encoding="utf-8"))["totals"]
    assert totals["material_scores"] == 2
    assert totals["deduped_material_scores"] == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
