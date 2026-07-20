from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.historical_outcome_cluster import (
    assess_person_talent_grade,
    build_outcome_episode,
    validate_historical_outcome_registry,
)
from emperor_v4.evaluation.i5b_current_value_runner import (
    build_i5b_current_value,
    build_outcome_database_dry_run,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config/historical-outcome-cluster-registry.schema.json"


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
    assert "national级结果" in grade["basis"]
    assert len(grade["outcome_refs"]) == 3


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
