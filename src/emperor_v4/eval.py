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
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 1 if report.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
