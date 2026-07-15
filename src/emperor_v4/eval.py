from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from emperor_v4.evaluation.episode_pilot import evaluate_episode_pilot
from emperor_v4.evaluation.reconciliation_review import (
    build_reconciliation_review_package,
)
from emperor_v4.evaluation.oracle_acceptance import (
    build_oracle_assisted_acceptance_package,
)
from emperor_v4.evaluation.blind_holdout import (
    run_blind_holdout,
    run_blind_holdout_with_semantic_review,
    score_blind_holdout,
)
from emperor_v4.evaluation.boundary_review import (
    build_boundary_review_plan,
    execute_boundary_review_payload,
    materialize_boundary_review_payload,
)
from emperor_v4.evaluation.boundary_score import score_boundary_graph
from emperor_v4.evaluation.graph_holdout import (
    draft_rule_evidence_units_payload,
    materialize_boundary_graph_payload,
    score_graph_blind_holdout,
)
from emperor_v4.evaluation.passage_support import materialize_passage_scoped_blind_input
from emperor_v4.evaluation.assertion_handoff import (
    build_assertion_repair_payloads,
    build_assertion_candidate_payloads,
    check_assertion_extraction_response,
    check_assertion_gap_repair_chain,
    check_assertion_repair_response,
)
from emperor_v4.evaluation.source_gap import (
    check_source_gap_request,
    check_source_segmentation_repair_response,
    check_source_supplement_response,
)
from emperor_v4.evaluation.qualification import (
    evaluate_downstream_development_qualification,
    evaluate_source_development_sets,
)
from emperor_v4.evaluation.relation_review import (
    build_relation_review_plan,
    materialize_relation_review,
    revise_relation_gold_from_audit,
)
from emperor_v4.evaluation.source_development import (
    fetch_source_development_snapshots,
    materialize_source_development_from_blind_input,
    materialize_source_development_input,
)
from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_appointment_delegation_shadow,
)
from emperor_v4.application.appointment_delegation_shadow_diff import (
    run_appointment_delegation_shadow_diff,
)
from emperor_v4.application.appointment_delegation_roster_runner import (
    run_appointment_delegation_roster_shadow,
    run_persistent_appointment_delegation_roster_shadow,
)
from emperor_v4.application.appointment_delegation_v3_parity_runner import (
    run_appointment_delegation_v3_parity_shadow,
)
from emperor_v4.application.factor_observation_qualification_runner import (
    run_factor_observation_batch_plan,
    run_factor_observation_batch_merge,
    run_factor_observation_qualification,
    run_factor_observation_qualification_gold,
    run_factor_observation_worklist,
)
from emperor_v4.evaluation.factor_representativeness import (
    evaluate_factor_representativeness_plan,
)
from emperor_v4.evaluation.rule_test_set_admission import (
    evaluate_rule_test_set_admission,
)
from emperor_v4.evaluation.i5b_factor_qualification import (
    build_i5b_factor_batch_plan,
    build_i5b_factor_worklist,
    evaluate_i5b_factor_qualification,
    merge_i5b_factor_responses,
)
from emperor_v4.evaluation.i5b_opened_regression import (
    evaluate_i5b_opened_regression_contract,
)
from emperor_v4.evaluation.i5b_factor_semantics import (
    evaluate_i5b_factor_semantics,
)
from emperor_v4.evaluation.i5b_scoring_policy import (
    evaluate_i5b_scoring_policy,
)
from emperor_v4.evaluation.i5b_joint_projection_scored_shadow import (
    build_i5b_joint_projection_scored_shadow,
)
from emperor_v4.evaluation.i5b_unified_raw_signal_runner import (
    build_i5b_unified_raw_signal_readiness,
)
from emperor_v4.evaluation.i5b_ruler_rule_coverage import (
    evaluate_i5b_ruler_rule_coverage,
)
from emperor_v4.evaluation.i5b_ruler_rule_net import build_i5b_ruler_rule_net_report
from emperor_v4.evaluation.i5b_scoring_detail import (
    build_i5b_scoring_detail,
    build_i5b_scoring_detail_selection,
    render_i5b_scoring_detail_markdown,
    render_i5b_scoring_detail_selection_markdown,
)
from emperor_v4.evaluation.v3_person_profile_export import (
    build_v3_person_profile_report,
    export_v3_person_profile_package,
)
from emperor_v4.evaluation.v3_claim_migration import (
    build_v3_claim_pilot_report,
    export_v3_claim_pilot_package,
)
from emperor_v4.evaluation.v3_claim_triage import (
    build_v3_claim_pre_source_review_report,
    build_v3_claim_triage,
)
from emperor_v4.evaluation.v3_person_identity_crosswalk import (
    add_candidate_identity_manifest,
    build_capability_domain_reviews,
    build_person_identity_crosswalk,
    build_team_profile_migration_readiness,
    build_user_authorized_identity_crosswalk,
    build_v4_person_identity_registry,
    load_identity_registry_profile_sets,
)
from emperor_v4.evaluation.v3_person_profile_import import (
    build_v4_profile_import_review_package,
)
from emperor_v4.evaluation.v3_authorized_profile_promotion import (
    promote_authorized_v3_person_profiles,
)
from emperor_v4.evaluation.v3_team_window_promotion import (
    build_v3_team_window_promotion_package,
)
from emperor_v4.evaluation.supplemental_team_profile_evaluation import (
    build_supplemental_team_profiles,
)
from emperor_v4.evaluation.talent_grade_v6_calibration import (
    build_talent_grade_v6_calibration,
)
from emperor_v4.evaluation.talent_grade_v7_important_calibration import (
    build_talent_grade_v7_important_calibration,
)
from emperor_v4.evaluation.talent_grade_v8_final_calibration import (
    build_talent_grade_v8_final_calibration,
)
from emperor_v4.evaluation.talent_grade_v9_high_tier_calibration import (
    build_talent_grade_v9_high_tier_calibration,
)
from emperor_v4.evaluation.talent_grade_v10_targeted_correction import (
    build_talent_grade_v10_targeted_correction,
)
from emperor_v4.evaluation.team_building_v8_scored_shadow import (
    build_team_building_v8_scored_shadow,
)
from emperor_v4.evaluation.talent_discovery_factor_qualification import (
    build_talent_discovery_factor_batch_plan,
    build_talent_discovery_factor_worklist,
    evaluate_talent_discovery_factor_qualification,
    merge_talent_discovery_factor_responses,
)
from emperor_v4.application.talent_discovery_shadow_runner import (
    run_talent_discovery_shadow,
)
from emperor_v4.application.talent_discovery_roster_runner import (
    run_persistent_talent_discovery_roster_shadow,
    run_talent_discovery_roster_shadow,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m emperor_v4.eval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    pilot = subparsers.add_parser("episode-pilot")
    pilot.add_argument("--manifest", type=Path, required=True)
    pilot.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/episode_pilot_v1"),
    )
    pilot.add_argument(
        "--linkage",
        type=Path,
        default=Path("eval/episode_pilot_v1_linkage.yml"),
    )
    pilot.add_argument(
        "--source-supplement",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/source-cache-supplement-response.json"
        ),
    )
    pilot.add_argument(
        "--claim-supplement",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/claim-extractor-supplement-response.json"
        ),
    )
    pilot.add_argument(
        "--source-segmentation-repair",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/"
            "source-cache-segmentation-repair-response.json"
        ),
    )
    pilot.add_argument(
        "--claim-repair",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/claim-extractor-repair-response.json"
        ),
    )
    pilot.add_argument(
        "--source-segmentation-gap-repair",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/"
            "source-cache-segmentation-gap-repair-response.json"
        ),
    )
    pilot.add_argument(
        "--claim-gap-repair",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/claim-extractor-gap-repair-response.json"
        ),
    )
    pilot.add_argument(
        "--claim-gap-repair2",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/claim-extractor-gap-repair2-response.json"
        ),
    )
    pilot.add_argument(
        "--assertion-gold-coverage",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_gold_coverage.yml"),
    )
    pilot.add_argument("--output", type=Path)
    reconciliation_review = subparsers.add_parser("episode-reconciliation-review")
    reconciliation_review.add_argument(
        "--manifest",
        type=Path,
        default=Path("eval/episode_pilot_v1.yml"),
    )
    reconciliation_review.add_argument(
        "--boundary-review",
        type=Path,
        default=Path("eval/episode_pilot_v1_review.yml"),
    )
    reconciliation_review.add_argument("--output", type=Path)
    oracle_accept = subparsers.add_parser("episode-oracle-acceptance")
    oracle_accept.add_argument(
        "--manifest", type=Path, default=Path("eval/episode_pilot_v1.yml")
    )
    oracle_accept.add_argument(
        "--review-package",
        type=Path,
        default=Path("eval/episode_pilot_v1_reconciliation_review_package.json"),
    )
    oracle_accept.add_argument(
        "--identity-manifest",
        type=Path,
        default=Path("eval/episode_pilot_v1_identity_resolution.yml"),
    )
    oracle_accept.add_argument(
        "--decisions",
        type=Path,
        default=Path("eval/episode_pilot_v1_oracle_assisted_decisions.yml"),
    )
    oracle_accept.add_argument("--output", type=Path)
    blind_run = subparsers.add_parser("blind-holdout-run")
    blind_run.add_argument("--input", type=Path, required=True)
    blind_run.add_argument("--output", type=Path)
    reviewed_run = subparsers.add_parser("blind-holdout-run-reviewed")
    reviewed_run.add_argument("--input", type=Path, required=True)
    reviewed_run.add_argument("--semantic-review", type=Path, required=True)
    reviewed_run.add_argument("--semantic-review-cache-hit", action="store_true")
    reviewed_run.add_argument("--output", type=Path)
    blind_score = subparsers.add_parser("blind-holdout-score")
    blind_score.add_argument("--candidates", type=Path, required=True)
    blind_score.add_argument("--sealed-gold", type=Path, required=True)
    blind_score.add_argument("--output", type=Path)
    boundary_plan = subparsers.add_parser("boundary-review-plan")
    boundary_plan.add_argument("--input", type=Path, required=True)
    boundary_plan.add_argument("--cache-index", type=Path)
    boundary_plan.add_argument("--output", type=Path)
    boundary_materialize = subparsers.add_parser("boundary-review-materialize")
    boundary_materialize.add_argument("--input", type=Path, required=True)
    boundary_materialize.add_argument("--review", type=Path, required=True)
    boundary_materialize.add_argument("--output", type=Path)
    boundary_execute = subparsers.add_parser("boundary-review-execute")
    boundary_execute.add_argument("--input", type=Path, required=True)
    boundary_execute.add_argument("--cache-results", type=Path)
    boundary_execute.add_argument("--output", type=Path)
    boundary_score = subparsers.add_parser("boundary-graph-score")
    boundary_score.add_argument("--candidates", type=Path, required=True)
    boundary_score.add_argument("--gold", type=Path, required=True)
    boundary_score.add_argument("--output", type=Path)
    graph_materialize = subparsers.add_parser("boundary-graph-materialize")
    graph_materialize.add_argument("--input", type=Path, required=True)
    graph_materialize.add_argument("--boundary-review", type=Path, required=True)
    graph_materialize.add_argument("--output", type=Path)
    rule_units = subparsers.add_parser("rule-evidence-draft")
    rule_units.add_argument("--graph", type=Path, required=True)
    rule_units.add_argument("--output", type=Path)
    graph_score = subparsers.add_parser("graph-blind-score")
    graph_score.add_argument("--graph", type=Path, required=True)
    graph_score.add_argument("--historical-gold", type=Path, required=True)
    graph_score.add_argument("--rule-candidates", type=Path, required=True)
    graph_score.add_argument("--rule-gold", type=Path, required=True)
    graph_score.add_argument("--runtime-audit", type=Path, required=True)
    graph_score.add_argument("--output", type=Path)
    passage_support = subparsers.add_parser("passage-support-materialize")
    passage_support.add_argument("--snapshot", type=Path, required=True)
    passage_support.add_argument("--review", type=Path, required=True)
    passage_support.add_argument("--output", type=Path)
    source_gap = subparsers.add_parser("source-gap-check")
    source_gap.add_argument("--manifest", type=Path, required=True)
    source_gap.add_argument(
        "--source-fixture",
        type=Path,
        default=Path("tests/fixtures/episode_pilot_v1/source-cache-response.json"),
    )
    source_gap.add_argument(
        "--request",
        type=Path,
        default=Path("eval/episode_pilot_v1_source_supplement.yml"),
    )
    source_gap.add_argument("--output", type=Path)
    supplement = subparsers.add_parser("source-supplement-check")
    supplement.add_argument(
        "--request",
        type=Path,
        default=Path("eval/episode_pilot_v1_source_supplement.yml"),
    )
    supplement.add_argument(
        "--response",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/source-cache-supplement-response.json"
        ),
    )
    supplement.add_argument(
        "--execution",
        type=Path,
        default=Path("eval/episode_pilot_v1_source_supplement_execution.yml"),
    )
    supplement.add_argument("--output", type=Path)
    assertion_handoff = subparsers.add_parser("assertion-handoff-build")
    assertion_handoff.add_argument(
        "--source-fixture",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/source-cache-supplement-response.json"
        ),
    )
    assertion_handoff.add_argument(
        "--handoff",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_extraction.yml"),
    )
    assertion_handoff.add_argument(
        "--output-root",
        type=Path,
        default=Path("tests/fixtures/episode_pilot_v1"),
    )
    assertion_handoff.add_argument("--output", type=Path)
    assertion_check = subparsers.add_parser("assertion-extraction-check")
    assertion_check.add_argument(
        "--handoff",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_extraction.yml"),
    )
    assertion_check.add_argument(
        "--execution",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_extraction_execution.yml"),
    )
    assertion_check.add_argument(
        "--response",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/claim-extractor-supplement-response.json"
        ),
    )
    assertion_check.add_argument("--output", type=Path)
    assertion_repair = subparsers.add_parser("assertion-repair-handoff-build")
    assertion_repair.add_argument(
        "--handoff",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_repair.yml"),
    )
    assertion_repair.add_argument(
        "--output-root",
        type=Path,
        default=Path("tests/fixtures/episode_pilot_v1"),
    )
    assertion_repair.add_argument("--output", type=Path)
    source_repair_check = subparsers.add_parser("source-segmentation-repair-check")
    source_repair_check.add_argument(
        "--request",
        type=Path,
        default=Path("eval/episode_pilot_v1_source_segmentation_repair.yml"),
    )
    source_repair_check.add_argument(
        "--execution",
        type=Path,
        default=Path(
            "eval/episode_pilot_v1_source_segmentation_repair_execution.yml"
        ),
    )
    source_repair_check.add_argument(
        "--response",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/"
            "source-cache-segmentation-repair-response.json"
        ),
    )
    source_repair_check.add_argument("--output", type=Path)
    assertion_repair_check = subparsers.add_parser("assertion-repair-check")
    assertion_repair_check.add_argument(
        "--handoff",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_repair.yml"),
    )
    assertion_repair_check.add_argument(
        "--execution",
        type=Path,
        default=Path("eval/episode_pilot_v1_assertion_repair_execution.yml"),
    )
    assertion_repair_check.add_argument(
        "--response",
        type=Path,
        default=Path(
            "tests/fixtures/episode_pilot_v1/claim-extractor-repair-response.json"
        ),
    )
    assertion_repair_check.add_argument("--output", type=Path)
    gap_repair_check = subparsers.add_parser("assertion-gap-repair-check")
    gap_repair_check.add_argument("--output", type=Path)
    source_qualification = subparsers.add_parser("source-development-qualification")
    source_qualification.add_argument(
        "--input",
        action="append",
        type=Path,
        required=True,
        help="可重复指定既有开放开发集；不会读取 Gold 或启动 Boundary reviewer。",
    )
    source_qualification.add_argument("--output", type=Path)
    source_fetch = subparsers.add_parser("source-development-fetch")
    source_fetch.add_argument("--manifest", type=Path, required=True)
    source_fetch.add_argument("--snapshot-dir", type=Path, required=True)
    source_fetch.add_argument("--output", type=Path)
    source_materialize = subparsers.add_parser("source-development-materialize")
    source_materialize.add_argument("--manifest", type=Path, required=True)
    source_materialize.add_argument("--claim-snapshot", type=Path, required=True)
    source_materialize.add_argument("--snapshot-dir", type=Path, required=True)
    source_materialize.add_argument("--output", type=Path)
    source_rebind = subparsers.add_parser("source-development-rebind")
    source_rebind.add_argument("--manifest", type=Path, required=True)
    source_rebind.add_argument("--blind-input", type=Path, required=True)
    source_rebind.add_argument("--snapshot-dir", type=Path, required=True)
    source_rebind.add_argument("--output", type=Path)
    downstream_qualification = subparsers.add_parser(
        "development-downstream-qualification"
    )
    downstream_qualification.add_argument(
        "--candidate-graph", type=Path, required=True
    )
    downstream_qualification.add_argument(
        "--historical-gold", type=Path, required=True
    )
    downstream_qualification.add_argument("--rule-gold", type=Path)
    downstream_qualification.add_argument("--output", type=Path)
    relation_plan = subparsers.add_parser("relation-review-plan")
    relation_plan.add_argument("--candidate-graph", type=Path, required=True)
    relation_plan.add_argument("--blind-input", type=Path, required=True)
    relation_plan.add_argument("--output", type=Path)
    relation_materialize = subparsers.add_parser("relation-review-materialize")
    relation_materialize.add_argument("--candidate-graph", type=Path, required=True)
    relation_materialize.add_argument("--blind-input", type=Path, required=True)
    relation_materialize.add_argument("--relation-review", type=Path, required=True)
    relation_materialize.add_argument("--output", type=Path)
    relation_gold_revise = subparsers.add_parser("relation-gold-revise")
    relation_gold_revise.add_argument("--historical-gold", type=Path, required=True)
    relation_gold_revise.add_argument("--audit", type=Path, required=True)
    relation_gold_revise.add_argument("--output", type=Path)
    scored_shadow = subparsers.add_parser("appointment-delegation-shadow")
    scored_shadow.add_argument("--manifest", type=Path, required=True)
    scored_shadow.add_argument("--output", type=Path)
    parity_shadow = subparsers.add_parser(
        "appointment-delegation-v3-parity-shadow"
    )
    parity_shadow.add_argument("--manifest", type=Path, required=True)
    parity_shadow.add_argument("--prior-report", type=Path)
    parity_shadow.add_argument("--output", type=Path)
    factor_worklist = subparsers.add_parser(
        "appointment-delegation-factor-worklist"
    )
    factor_worklist.add_argument("--source-manifest", type=Path, required=True)
    factor_worklist.add_argument("--output", type=Path)
    factor_batch_plan = subparsers.add_parser(
        "appointment-delegation-factor-batch-plan"
    )
    factor_batch_plan.add_argument("--source-manifest", type=Path, required=True)
    factor_batch_plan.add_argument("--max-units-per-batch", type=int, default=4)
    factor_batch_plan.add_argument("--max-workers", type=int, default=4)
    factor_batch_plan.add_argument("--output", type=Path)
    factor_batch_merge = subparsers.add_parser(
        "appointment-delegation-factor-batch-merge"
    )
    factor_batch_merge.add_argument("--batch-plan", type=Path, required=True)
    factor_batch_merge.add_argument(
        "--response", type=Path, action="append", required=True
    )
    factor_batch_merge.add_argument("--source-manifest", type=Path, required=True)
    factor_batch_merge.add_argument("--output", type=Path)
    factor_qualification = subparsers.add_parser(
        "appointment-delegation-factor-qualification"
    )
    factor_qualification.add_argument("--worklist", type=Path, required=True)
    factor_qualification.add_argument("--response", type=Path, required=True)
    factor_qualification.add_argument("--gold-manifest", type=Path, required=True)
    factor_qualification.add_argument("--source-manifest", type=Path, required=True)
    factor_qualification.add_argument("--output", type=Path)
    factor_gold = subparsers.add_parser("appointment-delegation-factor-gold")
    factor_gold.add_argument("--worklist", type=Path, required=True)
    factor_gold.add_argument("--parity-gold-manifest", type=Path, required=True)
    factor_gold.add_argument("--source-manifest", type=Path, required=True)
    factor_gold.add_argument(
        "--sample-role",
        choices=("open_development", "sealed_holdout"),
        default="open_development",
    )
    factor_gold.add_argument("--output", type=Path)
    factor_representativeness = subparsers.add_parser(
        "appointment-delegation-factor-representativeness"
    )
    factor_representativeness.add_argument("--manifest", type=Path, required=True)
    factor_representativeness.add_argument("--output", type=Path)
    rule_test_set_admission = subparsers.add_parser("rule-test-set-admission")
    rule_test_set_admission.add_argument("--policy", type=Path, required=True)
    rule_test_set_admission.add_argument("--output", type=Path)
    i5b_worklist = subparsers.add_parser("i5b-factor-worklist")
    i5b_worklist.add_argument("--manifest", type=Path, required=True)
    i5b_worklist.add_argument("--output", type=Path)
    i5b_batch = subparsers.add_parser("i5b-factor-batch-plan")
    i5b_batch.add_argument("--worklist", type=Path, required=True)
    i5b_batch.add_argument("--max-units-per-batch", type=int, default=4)
    i5b_batch.add_argument("--output", type=Path)
    i5b_merge = subparsers.add_parser("i5b-factor-merge")
    i5b_merge.add_argument("--worklist", type=Path, required=True)
    i5b_merge.add_argument("--response", type=Path, action="append", required=True)
    i5b_merge.add_argument("--output", type=Path)
    i5b_qualification = subparsers.add_parser("i5b-factor-qualification")
    i5b_qualification.add_argument("--worklist", type=Path, required=True)
    i5b_qualification.add_argument("--response", type=Path, required=True)
    i5b_qualification.add_argument("--gold", type=Path, required=True)
    i5b_qualification.add_argument("--output", type=Path)
    i5b_opened_regression = subparsers.add_parser(
        "i5b-opened-regression-contract"
    )
    i5b_opened_regression.add_argument("--contract", type=Path, required=True)
    i5b_opened_regression.add_argument(
        "--artifact-root", type=Path, default=Path(".")
    )
    i5b_opened_regression.add_argument("--output", type=Path)
    i5b_factor_semantics = subparsers.add_parser("i5b-factor-semantics")
    i5b_factor_semantics.add_argument("--contract", type=Path, required=True)
    i5b_factor_semantics.add_argument("--output", type=Path)
    i5b_scoring_policy = subparsers.add_parser("i5b-scoring-policy")
    i5b_scoring_policy.add_argument("--policy", type=Path, required=True)
    i5b_scoring_policy.add_argument("--output", type=Path)
    v3_person_profiles = subparsers.add_parser("v3-person-profile-export")
    v3_person_profiles.add_argument(
        "--source-freeze-ref", default="v3-freeze-20260712"
    )
    v3_person_profiles.add_argument("--env-file", type=Path, default=Path(".env"))
    v3_person_profiles.add_argument("--report", type=Path, required=True)
    v3_person_profiles.add_argument("--output", type=Path, required=True)
    v3_person_crosswalk = subparsers.add_parser("v3-person-identity-crosswalk")
    v3_person_crosswalk.add_argument("--source-package", type=Path, required=True)
    v3_person_crosswalk.add_argument(
        "--registry-profile", type=Path, action="append", required=True
    )
    v3_person_crosswalk.add_argument(
        "--candidate-identity-manifest", type=Path, action="append", default=[]
    )
    v3_person_crosswalk.add_argument(
        "--crosswalk-version", default="v3-to-v4-person-crosswalk-v1"
    )
    v3_person_crosswalk.add_argument("--output", type=Path, required=True)
    v3_profile_import = subparsers.add_parser("v3-person-profile-import-review")
    v3_profile_import.add_argument("--source-package", type=Path, required=True)
    v3_profile_import.add_argument("--crosswalk", type=Path, required=True)
    v3_profile_import.add_argument("--output", type=Path, required=True)
    v3_migration = subparsers.add_parser("v3-person-profile-migration")
    v3_migration.add_argument(
        "--source-freeze-ref", default="v3-freeze-20260712"
    )
    v3_migration.add_argument("--env-file", type=Path, default=Path(".env"))
    v3_migration.add_argument(
        "--registry-profile", type=Path, action="append", required=True
    )
    v3_migration.add_argument(
        "--candidate-identity-manifest", type=Path, action="append", default=[]
    )
    v3_migration.add_argument("--team-worklist", type=Path, action="append", default=[])
    v3_migration.add_argument("--artifact-dir", type=Path, required=True)
    v3_migration.add_argument("--authorization-ref")
    v3_migration.add_argument("--supplemental-evaluations", type=Path)
    v3_migration.add_argument("--output", type=Path, required=True)
    talent_calibration = subparsers.add_parser("talent-grade-v6-calibration")
    talent_calibration.add_argument("--authorized-promotion", type=Path, required=True)
    talent_calibration.add_argument("--supplemental-promotion", type=Path, required=True)
    talent_calibration.add_argument("--decisions", type=Path, required=True)
    talent_calibration.add_argument("--output", type=Path, required=True)
    important_calibration = subparsers.add_parser(
        "talent-grade-v7-important-calibration"
    )
    important_calibration.add_argument(
        "--authorized-promotion", type=Path, required=True
    )
    important_calibration.add_argument(
        "--supplemental-promotion", type=Path, required=True
    )
    important_calibration.add_argument(
        "--prior-calibration", type=Path, required=True
    )
    important_calibration.add_argument("--decisions", type=Path, required=True)
    important_calibration.add_argument("--output", type=Path, required=True)
    final_calibration = subparsers.add_parser("talent-grade-v8-final-calibration")
    final_calibration.add_argument("--authorized-promotion", type=Path, required=True)
    final_calibration.add_argument("--supplemental-promotion", type=Path, required=True)
    final_calibration.add_argument(
        "--prior-calibration", type=Path, action="append", required=True
    )
    final_calibration.add_argument("--decisions", type=Path, required=True)
    final_calibration.add_argument("--output", type=Path, required=True)
    high_tier_calibration = subparsers.add_parser(
        "talent-grade-v9-high-tier-calibration"
    )
    high_tier_calibration.add_argument(
        "--authorized-promotion", type=Path, required=True
    )
    high_tier_calibration.add_argument(
        "--supplemental-promotion", type=Path, required=True
    )
    high_tier_calibration.add_argument(
        "--prior-calibration", type=Path, action="append", required=True
    )
    high_tier_calibration.add_argument("--decisions", type=Path, required=True)
    high_tier_calibration.add_argument("--output", type=Path, required=True)
    targeted_correction = subparsers.add_parser(
        "talent-grade-v10-targeted-correction"
    )
    targeted_correction.add_argument("--prior-calibration", type=Path, required=True)
    targeted_correction.add_argument("--decisions", type=Path, required=True)
    targeted_correction.add_argument("--output", type=Path, required=True)
    team_scored_shadow = subparsers.add_parser("team-building-v8-scored-shadow")
    team_scored_shadow.add_argument("--team-windows", type=Path, required=True)
    team_scored_shadow.add_argument("--authorized-promotion", type=Path, required=True)
    team_scored_shadow.add_argument("--supplemental-promotion", type=Path, required=True)
    team_scored_shadow.add_argument(
        "--calibration", type=Path, action="append", required=True
    )
    team_scored_shadow.add_argument("--scoring-policy", type=Path, required=True)
    team_scored_shadow.add_argument(
        "--structural-observations", type=Path, required=True
    )
    team_scored_shadow.add_argument("--output", type=Path, required=True)
    joint_scored_shadow = subparsers.add_parser(
        "i5b-joint-projection-scored-shadow"
    )
    joint_scored_shadow.add_argument(
        "--rule-code",
        choices=("talent_discovery", "tolerate_talent", "anti_nepotism"),
        required=True,
    )
    joint_scored_shadow.add_argument("--projection-input", type=Path, required=True)
    joint_scored_shadow.add_argument("--scoring-policy", type=Path, required=True)
    joint_scored_shadow.add_argument("--assertion-review", type=Path)
    joint_scored_shadow.add_argument("--output", type=Path, required=True)
    unified_raw_signal = subparsers.add_parser("i5b-unified-raw-signal-readiness")
    unified_raw_signal.add_argument("--appointment-report", type=Path, required=True)
    unified_raw_signal.add_argument("--team-report", type=Path, required=True)
    unified_raw_signal.add_argument(
        "--joint-report", type=Path, action="append", required=True
    )
    unified_raw_signal.add_argument(
        "--coverage-report", type=Path, action="append", required=True
    )
    unified_raw_signal.add_argument("--calibration-version", required=True)
    unified_raw_signal.add_argument("--output", type=Path, required=True)
    ruler_rule_coverage = subparsers.add_parser("i5b-ruler-rule-coverage")
    ruler_rule_coverage.add_argument("--manifest", type=Path, required=True)
    ruler_rule_coverage.add_argument("--output", type=Path, required=True)
    ruler_rule_net = subparsers.add_parser("i5b-ruler-rule-net")
    ruler_rule_net.add_argument("--manifest", type=Path, required=True)
    ruler_rule_net.add_argument("--output", type=Path, required=True)
    scoring_detail = subparsers.add_parser("i5b-scoring-detail")
    scoring_detail.add_argument("--manifest", type=Path, required=True)
    scoring_detail.add_argument("--workspace-root", type=Path, default=Path("."))
    scoring_detail.add_argument("--format", choices=("json", "markdown"), required=True)
    scoring_detail.add_argument("--output", type=Path, required=True)
    scoring_detail_select = subparsers.add_parser("i5b-scoring-detail-select")
    scoring_detail_select.add_argument("--catalog", type=Path, required=True)
    scoring_detail_select.add_argument("--selection", type=Path, required=True)
    scoring_detail_select.add_argument("--workspace-root", type=Path, default=Path("."))
    scoring_detail_select.add_argument(
        "--format", choices=("json", "markdown"), required=True
    )
    scoring_detail_select.add_argument("--output", type=Path, required=True)
    v3_claim_pilot = subparsers.add_parser("v3-claim-pilot")
    v3_claim_pilot.add_argument("--ruler", required=True)
    v3_claim_pilot.add_argument("--source-freeze-ref", required=True)
    v3_claim_pilot.add_argument(
        "--profile-package", type=Path, action="append", required=True
    )
    v3_claim_pilot.add_argument("--env-file", type=Path, default=Path(".env"))
    v3_claim_pilot.add_argument("--output", type=Path, required=True)
    v3_claim_pilot.add_argument("--report", type=Path, required=True)
    v3_claim_triage = subparsers.add_parser("v3-claim-triage")
    v3_claim_triage.add_argument("--package", type=Path, required=True)
    v3_claim_triage.add_argument(
        "--workset",
        action="append",
        required=True,
        help="rule_code=path-to-existing-workset-json",
    )
    v3_claim_triage.add_argument("--per-rule-quota", type=int, default=8)
    v3_claim_triage.add_argument("--semantic-collision-review", type=Path)
    v3_claim_triage.add_argument("--worklist", type=Path, required=True)
    v3_claim_triage.add_argument("--report", type=Path, required=True)
    v3_claim_review = subparsers.add_parser("v3-claim-pre-source-review")
    v3_claim_review.add_argument("--worklist", type=Path, required=True)
    v3_claim_review.add_argument("--review", type=Path, required=True)
    v3_claim_review.add_argument("--output", type=Path, required=True)
    talent_factor_worklist = subparsers.add_parser(
        "talent-discovery-factor-worklist"
    )
    talent_factor_worklist.add_argument("--source-manifest", type=Path, required=True)
    talent_factor_worklist.add_argument("--output", type=Path)
    talent_factor_batch = subparsers.add_parser("talent-discovery-factor-batch-plan")
    talent_factor_batch.add_argument("--worklist", type=Path, required=True)
    talent_factor_batch.add_argument("--max-units-per-batch", type=int, default=4)
    talent_factor_batch.add_argument("--output", type=Path)
    talent_factor_merge = subparsers.add_parser("talent-discovery-factor-merge")
    talent_factor_merge.add_argument("--worklist", type=Path, required=True)
    talent_factor_merge.add_argument("--response", type=Path, action="append", required=True)
    talent_factor_merge.add_argument("--output", type=Path)
    talent_factor_qualification = subparsers.add_parser(
        "talent-discovery-factor-qualification"
    )
    talent_factor_qualification.add_argument("--worklist", type=Path, required=True)
    talent_factor_qualification.add_argument("--response", type=Path, required=True)
    talent_factor_qualification.add_argument("--gold", type=Path, required=True)
    talent_factor_qualification.add_argument("--output", type=Path)
    talent_shadow = subparsers.add_parser("talent-discovery-shadow")
    talent_shadow.add_argument("--manifest", type=Path, required=True)
    talent_shadow.add_argument("--output", type=Path)
    talent_roster = subparsers.add_parser("talent-discovery-roster-shadow")
    talent_roster.add_argument("--manifest", type=Path, required=True)
    talent_roster.add_argument("--prior-record", type=Path)
    talent_roster.add_argument("--state", type=Path)
    talent_roster.add_argument("--output", type=Path)
    shadow_diff = subparsers.add_parser("appointment-delegation-shadow-diff")
    shadow_diff.add_argument("--request", type=Path, required=True)
    shadow_diff.add_argument("--output", type=Path)
    roster_shadow = subparsers.add_parser("appointment-delegation-roster-shadow")
    roster_shadow.add_argument("--manifest", type=Path, required=True)
    roster_shadow.add_argument("--prior-record", type=Path)
    roster_shadow.add_argument("--state", type=Path)
    roster_shadow.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "episode-pilot":
        report = evaluate_episode_pilot(
            args.manifest,
            args.fixture_dir,
            args.linkage,
            args.source_supplement,
            args.claim_supplement,
            args.source_segmentation_repair,
            args.claim_repair,
            args.source_segmentation_gap_repair,
            args.claim_gap_repair,
            args.claim_gap_repair2,
            args.assertion_gold_coverage,
        )
    elif args.command == "source-gap-check":
        report = check_source_gap_request(
            args.manifest,
            args.source_fixture,
            args.request,
        )
    elif args.command == "source-supplement-check":
        report = check_source_supplement_response(
            args.request,
            args.response,
            args.execution,
        )
    elif args.command == "assertion-handoff-build":
        report = build_assertion_candidate_payloads(
            args.source_fixture,
            args.handoff,
            args.output_root,
        )
    elif args.command == "assertion-extraction-check":
        report = check_assertion_extraction_response(
            args.handoff,
            args.execution,
            args.response,
        )
    elif args.command == "assertion-repair-handoff-build":
        report = build_assertion_repair_payloads(
            args.handoff,
            args.output_root,
        )
    elif args.command == "source-segmentation-repair-check":
        report = check_source_segmentation_repair_response(
            args.request,
            args.execution,
            args.response,
        )
    elif args.command == "assertion-repair-check":
        report = check_assertion_repair_response(
            args.handoff,
            args.execution,
            args.response,
        )
    elif args.command == "assertion-gap-repair-check":
        report = check_assertion_gap_repair_chain(
            (
                Path("eval/episode_pilot_v1_assertion_gap_repair.yml"),
                Path("eval/episode_pilot_v1_assertion_gap_repair2.yml"),
            ),
            (
                Path("eval/episode_pilot_v1_assertion_gap_repair_execution.yml"),
                Path("eval/episode_pilot_v1_assertion_gap_repair2_execution.yml"),
            ),
            (
                Path(
                    "tests/fixtures/episode_pilot_v1/"
                    "claim-extractor-gap-repair-response.json"
                ),
                Path(
                    "tests/fixtures/episode_pilot_v1/"
                    "claim-extractor-gap-repair2-response.json"
                ),
            ),
        )
    elif args.command == "source-development-qualification":
        payloads = {
            path.parent.name: json.loads(path.read_text(encoding="utf-8"))
            for path in args.input
        }
        if len(payloads) != len(args.input):
            raise ValueError("source qualification 输入目录名必须唯一")
        report = evaluate_source_development_sets(payloads)
    elif args.command == "source-development-fetch":
        report = fetch_source_development_snapshots(
            args.manifest,
            args.snapshot_dir,
        )
    elif args.command == "source-development-materialize":
        report = materialize_source_development_input(
            manifest_path=args.manifest,
            claim_snapshot=json.loads(
                args.claim_snapshot.read_text(encoding="utf-8")
            ),
            snapshot_dir=args.snapshot_dir,
        )
    elif args.command == "source-development-rebind":
        report = materialize_source_development_from_blind_input(
            manifest_path=args.manifest,
            blind_input=json.loads(args.blind_input.read_text(encoding="utf-8")),
            snapshot_dir=args.snapshot_dir,
        )
    elif args.command == "development-downstream-qualification":
        report = evaluate_downstream_development_qualification(
            json.loads(args.candidate_graph.read_text(encoding="utf-8")),
            yaml.safe_load(args.historical_gold.read_text(encoding="utf-8")),
            (
                yaml.safe_load(args.rule_gold.read_text(encoding="utf-8"))
                if args.rule_gold
                else None
            ),
        )
    elif args.command == "relation-review-plan":
        report = build_relation_review_plan(
            json.loads(args.candidate_graph.read_text(encoding="utf-8")),
            json.loads(args.blind_input.read_text(encoding="utf-8")),
        )
    elif args.command == "relation-review-materialize":
        report = materialize_relation_review(
            json.loads(args.candidate_graph.read_text(encoding="utf-8")),
            yaml.safe_load(args.relation_review.read_text(encoding="utf-8")),
            json.loads(args.blind_input.read_text(encoding="utf-8")),
        )
    elif args.command == "relation-gold-revise":
        report = revise_relation_gold_from_audit(
            yaml.safe_load(args.historical_gold.read_text(encoding="utf-8")),
            yaml.safe_load(args.audit.read_text(encoding="utf-8")),
        )
    elif args.command == "appointment-delegation-shadow":
        report = run_appointment_delegation_shadow(args.manifest)
    elif args.command == "appointment-delegation-v3-parity-shadow":
        report = run_appointment_delegation_v3_parity_shadow(
            args.manifest, prior_report_path=args.prior_report
        )
    elif args.command == "appointment-delegation-factor-worklist":
        report = run_factor_observation_worklist(args.source_manifest)
    elif args.command == "appointment-delegation-factor-batch-plan":
        report = run_factor_observation_batch_plan(
            args.source_manifest,
            max_units_per_batch=args.max_units_per_batch,
            max_workers=args.max_workers,
        )
    elif args.command == "appointment-delegation-factor-batch-merge":
        report = run_factor_observation_batch_merge(
            args.batch_plan,
            tuple(args.response),
            args.source_manifest,
        )
    elif args.command == "appointment-delegation-factor-qualification":
        report = run_factor_observation_qualification(
            args.worklist,
            args.response,
            args.gold_manifest,
            args.source_manifest,
        )
    elif args.command == "appointment-delegation-factor-gold":
        report = run_factor_observation_qualification_gold(
            args.worklist,
            args.parity_gold_manifest,
            args.source_manifest,
            sample_role=args.sample_role,
        )
    elif args.command == "appointment-delegation-factor-representativeness":
        report = evaluate_factor_representativeness_plan(
            yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        )
    elif args.command == "rule-test-set-admission":
        report = evaluate_rule_test_set_admission(
            yaml.safe_load(args.policy.read_text(encoding="utf-8"))
        )
    elif args.command == "i5b-factor-worklist":
        report = build_i5b_factor_worklist(
            yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        )
    elif args.command == "i5b-factor-batch-plan":
        report = build_i5b_factor_batch_plan(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            max_units_per_batch=args.max_units_per_batch,
        )
    elif args.command == "i5b-factor-merge":
        report = merge_i5b_factor_responses(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            [json.loads(path.read_text(encoding="utf-8")) for path in args.response],
        )
    elif args.command == "i5b-factor-qualification":
        report = evaluate_i5b_factor_qualification(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            json.loads(args.response.read_text(encoding="utf-8")),
            yaml.safe_load(args.gold.read_text(encoding="utf-8")),
        )
    elif args.command == "i5b-opened-regression-contract":
        report = evaluate_i5b_opened_regression_contract(
            yaml.safe_load(args.contract.read_text(encoding="utf-8")),
            artifact_root=args.artifact_root,
        )
    elif args.command == "i5b-factor-semantics":
        report = evaluate_i5b_factor_semantics(
            yaml.safe_load(args.contract.read_text(encoding="utf-8"))
        )
    elif args.command == "i5b-scoring-policy":
        report = evaluate_i5b_scoring_policy(
            yaml.safe_load(args.policy.read_text(encoding="utf-8"))
        )
    elif args.command == "v3-person-profile-export":
        report = export_v3_person_profile_package(
            source_freeze_ref=args.source_freeze_ref,
            env_file=args.env_file,
        )
        migration_report = build_v3_person_profile_report(report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                migration_report, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "v3-person-identity-crosswalk":
        source_package = json.loads(
            args.source_package.read_text(encoding="utf-8")
        )
        registry = build_v4_person_identity_registry(
            load_identity_registry_profile_sets(args.registry_profile)
        )
        for path in args.candidate_identity_manifest:
            add_candidate_identity_manifest(
                registry,
                source_ref=path.as_posix(),
                payload=yaml.safe_load(path.read_text(encoding="utf-8")),
            )
        report = build_person_identity_crosswalk(
            source_package,
            registry=registry,
            crosswalk_version=args.crosswalk_version,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "v3-person-profile-import-review":
        source_package = json.loads(
            args.source_package.read_text(encoding="utf-8")
        )
        crosswalk = json.loads(args.crosswalk.read_text(encoding="utf-8"))
        report = build_v4_profile_import_review_package(
            source_package,
            crosswalk_decisions=crosswalk["decisions"],
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "v3-person-profile-migration":
        source_package = export_v3_person_profile_package(
            source_freeze_ref=args.source_freeze_ref,
            env_file=args.env_file,
        )
        profile_sets = load_identity_registry_profile_sets(args.registry_profile)
        registry = build_v4_person_identity_registry(profile_sets)
        for path in args.candidate_identity_manifest:
            add_candidate_identity_manifest(
                registry,
                source_ref=path.as_posix(),
                payload=yaml.safe_load(path.read_text(encoding="utf-8")),
            )
        crosswalk = (
            build_user_authorized_identity_crosswalk(
                source_package,
                legacy_registry=registry,
                authorization_ref=args.authorization_ref,
                crosswalk_version="v3-to-v4-person-crosswalk-v2",
            )
            if args.authorization_ref
            else build_person_identity_crosswalk(
                source_package,
                registry=registry,
                crosswalk_version="v3-to-v4-person-crosswalk-v1",
            )
        )
        import_review = build_v4_profile_import_review_package(
            source_package, crosswalk["decisions"]
        )
        worklists = [
            (path.as_posix(), json.loads(path.read_text(encoding="utf-8")))
            for path in args.team_worklist
        ]
        readiness = build_team_profile_migration_readiness(
            source_package,
            profile_sets=profile_sets,
            worklists=worklists,
        )
        args.artifact_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {
            "source_snapshot.json": source_package,
            "identity_crosswalk_candidates.json": crosswalk,
            "profile_import_review.json": import_review,
            "team_profile_migration_readiness.json": readiness,
        }
        authorized_profile_promotion = None
        team_window_promotion = None
        supplemental_profile_promotion = None
        if args.authorization_ref:
            capability_map = build_capability_domain_reviews(
                source_package,
                crosswalk=crosswalk,
                profile_sets=profile_sets,
            )
            authorized_profile_promotion = promote_authorized_v3_person_profiles(
                source_package,
                crosswalk,
                capability_map,
                args.authorization_ref,
            )
            name_by_source_ref = {
                entry["identity_source"]["source_object_ref"]: entry[
                    "identity_source"
                ]["canonical_name"]
                for entry in source_package["entries"]
            }
            promoted_profiles = {
                name_by_source_ref[item["source_object_ref"]]: item[
                    "person_profile_snapshot"
                ]
                for item in authorized_profile_promotion["items"]
                if item["person_profile_snapshot"] is not None
            }
            if args.supplemental_evaluations:
                supplemental_profile_promotion = build_supplemental_team_profiles(
                    yaml.safe_load(
                        args.supplemental_evaluations.read_text(encoding="utf-8")
                    )
                )
                promoted_profiles.update(
                    {
                        item["person"]: item["person_profile_snapshot"]
                        for item in supplemental_profile_promotion["items"]
                    }
                )
            team_window_promotion = build_v3_team_window_promotion_package(
                [payload for _, payload in worklists], promoted_profiles
            )
            artifacts.update(
                {
                    "authorized_identity_crosswalk.json": crosswalk,
                    "authorized_profile_promotion.json": authorized_profile_promotion,
                    "supplemental_profile_promotion.json": supplemental_profile_promotion,
                    "team_window_promotion.json": team_window_promotion,
                }
            )
        for name, payload in artifacts.items():
            (args.artifact_dir / name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
        report = {
            "schema_version": "v3-person-profile-migration-run-v1",
            "status": "migration_review_packages_complete",
            "source_package_sha256": source_package["package_sha256"],
            "crosswalk_package_sha256": crosswalk["crosswalk_package_sha256"],
            "profile_import_review_sha256": import_review["review_package_sha256"],
            "source_summary": source_package["summary"],
            "crosswalk_summary": crosswalk["summary"],
            "profile_import_summary": import_review["summary"],
            "team_building_readiness": readiness,
            "authorized_profile_promotion_summary": (
                authorized_profile_promotion["summary"]
                if authorized_profile_promotion
                else None
            ),
            "team_window_promotion_summary": (
                team_window_promotion["summary"] if team_window_promotion else None
            ),
            "supplemental_profile_promotion_summary": (
                supplemental_profile_promotion["summary"]
                if supplemental_profile_promotion
                else None
            ),
            "declarations": {
                "v3_database_write_count": 0,
                "v4_database_write_count": 0,
                "model_call_count": (
                    supplemental_profile_promotion["summary"][
                        "research_agent_run_count"
                    ]
                    if supplemental_profile_promotion
                    else 0
                ),
                "human_frozen_profile_generated_count": (
                    authorized_profile_promotion["summary"][
                        "human_frozen_profile_count"
                    ]
                    if authorized_profile_promotion
                    else 0
                )
                + (
                    supplemental_profile_promotion["summary"][
                        "human_frozen_profile_count"
                    ]
                    if supplemental_profile_promotion
                    else 0
                ),
                "formal_scoring_allowed": False,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "talent-grade-v6-calibration":
        report = build_talent_grade_v6_calibration(
            json.loads(args.authorized_promotion.read_text(encoding="utf-8")),
            json.loads(args.supplemental_promotion.read_text(encoding="utf-8")),
            yaml.safe_load(args.decisions.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "talent-grade-v7-important-calibration":
        report = build_talent_grade_v7_important_calibration(
            json.loads(args.authorized_promotion.read_text(encoding="utf-8")),
            json.loads(args.supplemental_promotion.read_text(encoding="utf-8")),
            json.loads(args.prior_calibration.read_text(encoding="utf-8")),
            yaml.safe_load(args.decisions.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "talent-grade-v8-final-calibration":
        report = build_talent_grade_v8_final_calibration(
            json.loads(args.authorized_promotion.read_text(encoding="utf-8")),
            json.loads(args.supplemental_promotion.read_text(encoding="utf-8")),
            [
                json.loads(path.read_text(encoding="utf-8"))
                for path in args.prior_calibration
            ],
            yaml.safe_load(args.decisions.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "talent-grade-v9-high-tier-calibration":
        report = build_talent_grade_v9_high_tier_calibration(
            json.loads(args.authorized_promotion.read_text(encoding="utf-8")),
            json.loads(args.supplemental_promotion.read_text(encoding="utf-8")),
            [
                json.loads(path.read_text(encoding="utf-8"))
                for path in args.prior_calibration
            ],
            yaml.safe_load(args.decisions.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "talent-grade-v10-targeted-correction":
        report = build_talent_grade_v10_targeted_correction(
            json.loads(args.prior_calibration.read_text(encoding="utf-8")),
            yaml.safe_load(args.decisions.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "team-building-v8-scored-shadow":
        report = build_team_building_v8_scored_shadow(
            json.loads(args.team_windows.read_text(encoding="utf-8")),
            json.loads(args.authorized_promotion.read_text(encoding="utf-8")),
            json.loads(args.supplemental_promotion.read_text(encoding="utf-8")),
            [
                json.loads(path.read_text(encoding="utf-8"))
                for path in args.calibration
            ],
            yaml.safe_load(args.scoring_policy.read_text(encoding="utf-8")),
            yaml.safe_load(args.structural_observations.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "i5b-joint-projection-scored-shadow":
        report = build_i5b_joint_projection_scored_shadow(
            rule_code=args.rule_code,
            projection_payload=json.loads(
                args.projection_input.read_text(encoding="utf-8")
            ),
            scoring_policy=yaml.safe_load(
                args.scoring_policy.read_text(encoding="utf-8")
            ),
            assertion_payload=(
                json.loads(args.assertion_review.read_text(encoding="utf-8"))
                if args.assertion_review
                else None
            ),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "i5b-unified-raw-signal-readiness":
        report = build_i5b_unified_raw_signal_readiness(
            appointment_report=json.loads(
                args.appointment_report.read_text(encoding="utf-8")
            ),
            team_report=json.loads(args.team_report.read_text(encoding="utf-8")),
            joint_reports=[
                json.loads(path.read_text(encoding="utf-8"))
                for path in args.joint_report
            ],
            coverage_reports=[
                json.loads(path.read_text(encoding="utf-8"))
                for path in args.coverage_report
            ],
            calibration_version=args.calibration_version,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "i5b-ruler-rule-coverage":
        report = evaluate_i5b_ruler_rule_coverage(
            yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "i5b-ruler-rule-net":
        report = build_i5b_ruler_rule_net_report(
            yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "i5b-scoring-detail":
        detail_manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        workspace_root = args.workspace_root.resolve()

        def load_detail(path_value: str) -> dict:
            path = workspace_root / path_value
            if path.suffix.lower() == ".json":
                return json.loads(path.read_text(encoding="utf-8"))
            return yaml.safe_load(path.read_text(encoding="utf-8"))

        report = build_i5b_scoring_detail(
            manifest=detail_manifest,
            rule_net=load_detail(detail_manifest["ruler_rule_net"]),
            scoring_policy=load_detail(detail_manifest["scoring_policy"]),
            display_catalog=load_detail(detail_manifest["display_catalog"]),
            detail_sources=[
                {"payload": load_detail(source["path"])}
                for source in detail_manifest["detail_sources"]
            ],
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "i5b-scoring-detail-select":
        workspace_root = args.workspace_root.resolve()
        catalog = yaml.safe_load(args.catalog.read_text(encoding="utf-8"))
        selection = yaml.safe_load(args.selection.read_text(encoding="utf-8"))

        def load_payload(path_value: str) -> dict:
            path = workspace_root / path_value
            if path.suffix.lower() == ".json":
                return json.loads(path.read_text(encoding="utf-8"))
            return yaml.safe_load(path.read_text(encoding="utf-8"))

        ruler_reports = {}
        for entry in catalog["entries"]:
            ruler_manifest = load_payload(entry["manifest"])
            ruler_reports[entry["ruler"]] = build_i5b_scoring_detail(
                manifest=ruler_manifest,
                rule_net=load_payload(ruler_manifest["ruler_rule_net"]),
                scoring_policy=load_payload(ruler_manifest["scoring_policy"]),
                display_catalog=load_payload(ruler_manifest["display_catalog"]),
                detail_sources=[
                    {"payload": load_payload(source["path"])}
                    for source in ruler_manifest["detail_sources"]
                ],
            )
        report = build_i5b_scoring_detail_selection(
            catalog=catalog,
            selection=selection,
            ruler_reports=ruler_reports,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.command == "v3-claim-pilot":
        report = export_v3_claim_pilot_package(
            ruler=args.ruler,
            source_freeze_ref=args.source_freeze_ref,
            profile_packages=[
                json.loads(path.read_text(encoding="utf-8"))
                for path in args.profile_package
            ],
            env_file=args.env_file,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        pilot_report = build_v3_claim_pilot_report(report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(pilot_report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return 0
    elif args.command == "v3-claim-triage":
        worksets: dict[str, list[dict[str, object]]] = {}
        for specification in args.workset:
            rule_code, separator, raw_path = specification.partition("=")
            if not separator or not rule_code or not raw_path:
                raise ValueError("--workset must use rule_code=path")
            worksets.setdefault(rule_code, []).append(
                json.loads(Path(raw_path).read_text(encoding="utf-8"))
            )
        worklist, report = build_v3_claim_triage(
            json.loads(args.package.read_text(encoding="utf-8")),
            worksets=worksets,
            semantic_collision_reviews=(
                json.loads(args.semantic_collision_review.read_text(encoding="utf-8"))[
                    "review_groups"
                ]
                if args.semantic_collision_review
                else ()
            ),
            per_rule_quota=args.per_rule_quota,
        )
        args.worklist.parent.mkdir(parents=True, exist_ok=True)
        args.worklist.write_text(
            json.dumps(worklist, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return 0
    elif args.command == "v3-claim-pre-source-review":
        report = build_v3_claim_pre_source_review_report(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            json.loads(args.review.read_text(encoding="utf-8")),
        )
    elif args.command == "talent-discovery-factor-worklist":
        report = build_talent_discovery_factor_worklist(
            yaml.safe_load(args.source_manifest.read_text(encoding="utf-8"))
        )
    elif args.command == "talent-discovery-factor-batch-plan":
        report = build_talent_discovery_factor_batch_plan(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            max_units_per_batch=args.max_units_per_batch,
        )
    elif args.command == "talent-discovery-factor-merge":
        report = merge_talent_discovery_factor_responses(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            [json.loads(path.read_text(encoding="utf-8")) for path in args.response],
        )
    elif args.command == "talent-discovery-factor-qualification":
        report = evaluate_talent_discovery_factor_qualification(
            json.loads(args.worklist.read_text(encoding="utf-8")),
            json.loads(args.response.read_text(encoding="utf-8")),
            yaml.safe_load(args.gold.read_text(encoding="utf-8")),
        )
    elif args.command == "talent-discovery-shadow":
        report = run_talent_discovery_shadow(args.manifest)
    elif args.command == "talent-discovery-roster-shadow":
        report = (
            run_persistent_talent_discovery_roster_shadow(
                args.manifest,
                args.state,
                prior_record_path=args.prior_record,
            )
            if args.state
            else run_talent_discovery_roster_shadow(
                args.manifest, prior_record_path=args.prior_record
            )
        )
    elif args.command == "appointment-delegation-shadow-diff":
        report = run_appointment_delegation_shadow_diff(args.request)
    elif args.command == "appointment-delegation-roster-shadow":
        report = (
            run_persistent_appointment_delegation_roster_shadow(
                args.manifest,
                args.state,
                prior_record_path=args.prior_record,
            )
            if args.state
            else run_appointment_delegation_roster_shadow(
                args.manifest, prior_record_path=args.prior_record
            )
        )
    elif args.command == "episode-reconciliation-review":
        pilot_report = evaluate_episode_pilot(
            manifest_path=args.manifest,
            fixture_dir=Path("tests/fixtures/episode_pilot_v1"),
            linkage_path=Path("eval/episode_pilot_v1_linkage.yml"),
            source_supplement_path=Path(
                "tests/fixtures/episode_pilot_v1/"
                "source-cache-supplement-response.json"
            ),
            claim_supplement_path=Path(
                "tests/fixtures/episode_pilot_v1/"
                "claim-extractor-supplement-response.json"
            ),
            source_segmentation_repair_path=Path(
                "tests/fixtures/episode_pilot_v1/"
                "source-cache-segmentation-repair-response.json"
            ),
            claim_repair_path=Path(
                "tests/fixtures/episode_pilot_v1/claim-extractor-repair-response.json"
            ),
            source_segmentation_gap_repair_path=Path(
                "tests/fixtures/episode_pilot_v1/"
                "source-cache-segmentation-gap-repair-response.json"
            ),
            claim_gap_repair_path=Path(
                "tests/fixtures/episode_pilot_v1/"
                "claim-extractor-gap-repair-response.json"
            ),
            claim_gap_repair2_path=Path(
                "tests/fixtures/episode_pilot_v1/"
                "claim-extractor-gap-repair2-response.json"
            ),
            assertion_gold_coverage_path=Path(
                "eval/episode_pilot_v1_assertion_gold_coverage.yml"
            ),
        )
        report = build_reconciliation_review_package(
            args.manifest,
            args.boundary_review,
            pilot_report,
        )
    elif args.command == "episode-oracle-acceptance":
        report = build_oracle_assisted_acceptance_package(
            args.manifest,
            args.review_package,
            args.identity_manifest,
            args.decisions,
        )
    elif args.command == "blind-holdout-run":
        report = run_blind_holdout(
            json.loads(args.input.read_text(encoding="utf-8"))
        )
    elif args.command == "blind-holdout-run-reviewed":
        report = run_blind_holdout_with_semantic_review(
            json.loads(args.input.read_text(encoding="utf-8")),
            yaml.safe_load(args.semantic_review.read_text(encoding="utf-8")),
            review_cache_hit=args.semantic_review_cache_hit,
        )
    elif args.command == "blind-holdout-score":
        report = score_blind_holdout(
            json.loads(args.candidates.read_text(encoding="utf-8")),
            yaml.safe_load(args.sealed_gold.read_text(encoding="utf-8")),
        )
    elif args.command == "boundary-review-plan":
        cached_review_keys = ()
        if args.cache_index:
            cache_payload = json.loads(args.cache_index.read_text(encoding="utf-8"))
            cached_review_keys = (
                cache_payload.get("cache_keys")
                if isinstance(cache_payload, dict)
                else cache_payload
            )
        report = build_boundary_review_plan(
            json.loads(args.input.read_text(encoding="utf-8")),
            cached_review_keys=cached_review_keys or (),
        )
    elif args.command == "boundary-review-materialize":
        report = materialize_boundary_review_payload(
            json.loads(args.input.read_text(encoding="utf-8")),
            yaml.safe_load(args.review.read_text(encoding="utf-8")),
        )
    elif args.command == "boundary-review-execute":
        cache_results = ()
        if args.cache_results:
            cache_payload = yaml.safe_load(
                args.cache_results.read_text(encoding="utf-8")
            )
            cache_results = (
                cache_payload.get("review_results")
                if isinstance(cache_payload, dict)
                else cache_payload
            )
        report = execute_boundary_review_payload(
            json.loads(args.input.read_text(encoding="utf-8")),
            cached_review_payloads=cache_results or (),
        )
    elif args.command == "boundary-graph-score":
        report = score_boundary_graph(
            yaml.safe_load(args.candidates.read_text(encoding="utf-8")),
            yaml.safe_load(args.gold.read_text(encoding="utf-8")),
        )
    elif args.command == "boundary-graph-materialize":
        report = materialize_boundary_graph_payload(
            json.loads(args.input.read_text(encoding="utf-8")),
            yaml.safe_load(args.boundary_review.read_text(encoding="utf-8")),
        )
    elif args.command == "rule-evidence-draft":
        report = draft_rule_evidence_units_payload(
            json.loads(args.graph.read_text(encoding="utf-8"))
        )
    elif args.command == "graph-blind-score":
        report = score_graph_blind_holdout(
            json.loads(args.graph.read_text(encoding="utf-8")),
            yaml.safe_load(args.historical_gold.read_text(encoding="utf-8")),
            json.loads(args.rule_candidates.read_text(encoding="utf-8")),
            yaml.safe_load(args.rule_gold.read_text(encoding="utf-8")),
            json.loads(args.runtime_audit.read_text(encoding="utf-8")),
        )
    elif args.command == "passage-support-materialize":
        report = materialize_passage_scoped_blind_input(
            json.loads(args.snapshot.read_text(encoding="utf-8")),
            yaml.safe_load(args.review.read_text(encoding="utf-8")),
        )
    else:
        raise AssertionError("unreachable")
    if args.command == "i5b-scoring-detail" and args.format == "markdown":
        rendered = render_i5b_scoring_detail_markdown(report)
    elif args.command == "i5b-scoring-detail-select" and args.format == "markdown":
        rendered = render_i5b_scoring_detail_selection_markdown(report)
    else:
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 1 if report.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
