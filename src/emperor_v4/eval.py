from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from emperor_v4.evaluation.first_item_a_registry import write_first_item_a_registry
from emperor_v4.evaluation.first_item_b_registry import write_first_item_b_registry
from emperor_v4.evaluation.first_item_c_registry import write_first_item_c_registry
from emperor_v4.evaluation.formal_settlements import verify_formal_settlements
from emperor_v4.evaluation.third_item_current_settlement import (
    build_current_third_item_settlement,
    write_current_third_item_settlement,
)
from emperor_v4.evaluation.third_item_d_settlement import (
    write_third_item_d_formal_settlement,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="皇帝综合评价体系 V4 评分命令")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("formal-settlements-verify")
    for name in (
        "first-item-a-registry",
        "first-item-b-registry",
        "first-item-c-registry",
    ):
        command = commands.add_parser(name)
        command.add_argument("--workspace-root", type=Path, default=Path("."))
    third_d = commands.add_parser("third-item-d-settlement")
    third_d.add_argument("--workspace-root", type=Path, default=Path("."))
    third_current = commands.add_parser("third-item-current-settlement")
    third_current.add_argument("--workspace-root", type=Path, default=Path("."))
    third_current.add_argument("--write", action="store_true")
    return parser


def _print_written(written: dict[str, Path]) -> int:
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "formal-settlements-verify":
        report = verify_formal_settlements(Path(".").resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    workspace_root = args.workspace_root.resolve()
    if args.command == "first-item-a-registry":
        return _print_written(write_first_item_a_registry(workspace_root))
    if args.command == "first-item-b-registry":
        return _print_written(write_first_item_b_registry(workspace_root))
    if args.command == "first-item-c-registry":
        return _print_written(write_first_item_c_registry(workspace_root))
    if args.command == "third-item-d-settlement":
        payload = write_third_item_d_formal_settlement(workspace_root)
        print(f"D正式主体：{payload['record_count']}")
        return 0
    if args.command == "third-item-current-settlement":
        payload = (
            write_current_third_item_settlement(workspace_root)
            if args.write
            else build_current_third_item_settlement(workspace_root)
        )
        print(json.dumps(payload["component_coverage_counts"], ensure_ascii=False))
        return 0
    raise AssertionError(f"未处理命令：{args.command}")
