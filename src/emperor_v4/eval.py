from __future__ import annotations

import argparse
import json
from pathlib import Path

from emperor_v4.evaluation.episode_pilot import evaluate_episode_pilot
from emperor_v4.evaluation.reconciliation_review import (
    build_reconciliation_review_package,
)
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
    else:
        raise AssertionError("unreachable")
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if report.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
