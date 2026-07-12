from __future__ import annotations

import argparse
import json
from pathlib import Path

from emperor_v4.evaluation.episode_pilot import evaluate_episode_pilot
from emperor_v4.evaluation.source_gap import (
    check_source_gap_request,
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
    pilot.add_argument("--output", type=Path)
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
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "episode-pilot":
        report = evaluate_episode_pilot(
            args.manifest,
            args.fixture_dir,
            args.linkage,
            args.source_supplement,
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
