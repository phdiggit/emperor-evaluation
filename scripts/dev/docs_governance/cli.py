from __future__ import annotations

import argparse

from . import constants as c
from .inventory import build_inventory
from .paths import _emit_stderr, write_json
from .registry_check import check_registry
from .report import write_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Docs lifecycle inventory and governance checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory", help="Build docs inventory JSON.")
    inventory.add_argument("--ref", default="origin/GPT")
    inventory.add_argument("--output")
    check = subparsers.add_parser("check", help="Validate docs registry and docs governance rules.")
    check.add_argument("--registry", default=c.REGISTRY_PATH)
    check.add_argument("--worktree", action="store_true", help="Validate against the current working tree, including unstaged and untracked docs.")
    report = subparsers.add_parser("report", help="Build Markdown docs governance report from registry.")
    report.add_argument("--registry", default=c.REGISTRY_PATH)
    report.add_argument("--output", default=c.DEFAULT_REPORT_OUTPUT)
    report.add_argument("--worktree", action="store_true", help="Include working tree docs state in registry problem checks.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            write_json(build_inventory(args.ref), args.output)
        elif args.command == "check":
            problems = check_registry(args.registry, worktree=args.worktree)
            if problems:
                for problem in problems:
                    _emit_stderr(problem)
                return 1
        elif args.command == "report":
            write_report(args.registry, args.output, worktree=args.worktree)
        else:  # pragma: no cover
            raise AssertionError(f"unknown command: {args.command}")
    except Exception as exc:
        _emit_stderr(f"error: {exc}")
        return 1
    return 0
