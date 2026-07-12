from __future__ import annotations

import argparse
import json
from pathlib import Path

from emperor_v4.evaluation.episode_pilot import evaluate_episode_pilot


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
    pilot.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command != "episode-pilot":
        raise AssertionError("unreachable")
    report = evaluate_episode_pilot(args.manifest, args.fixture_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
