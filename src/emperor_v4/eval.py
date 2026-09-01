from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from emperor_v4.evaluation.first_item_a_registry import write_first_item_a_registry
from emperor_v4.evaluation.first_item_b_registry import write_first_item_b_registry
from emperor_v4.evaluation.first_item_c_registry import write_first_item_c_registry
from emperor_v4.evaluation.canonical_ruler_pool import (
    build_canonical_ruler_pool,
    write_canonical_ruler_pool,
)
from emperor_v4.evaluation.composite_ranking import (
    build_composite_ranking,
    write_composite_ranking,
)
from emperor_v4.evaluation.formal_settlements import (
    verify_formal_settlements,
    verify_second_item_a_snapshot,
    verify_second_item_b2_snapshot,
)
from emperor_v4.evaluation.profile_c2_c5_cross_axis_audit import (
    inspect_cross_axis_drift as inspect_profile_c2_c5_cross_axis_drift,
)
from emperor_v4.evaluation.profile_c3_settlement import build as build_profile_c3_settlement
from emperor_v4.evaluation.profile_c3_verifier import verify as verify_profile_c3_settlement
from emperor_v4.evaluation.profile_m3_settlement import build as build_profile_m3_settlement
from emperor_v4.evaluation.profile_m3_verifier import verify as verify_profile_m3_settlement
from emperor_v4.evaluation.profile_m4_settlement import build as build_profile_m4_settlement
from emperor_v4.evaluation.profile_m4_verifier import verify as verify_profile_m4_settlement
from emperor_v4.evaluation.profile_markdown import AXIS_FILES, write_axes as write_profile_markdown_axes
from emperor_v4.evaluation.profile_radar import write_samples as write_profile_radar_samples
from emperor_v4.evaluation.profile_video_card import write_samples as write_profile_video_card_samples
from emperor_v4.evaluation.profile_video_copy import write_samples as write_profile_video_copy_samples
from emperor_v4.evaluation.second_item_b1_settlement import rebuild_derived as rebuild_second_item_b1
from emperor_v4.evaluation.third_item_current_settlement import (
    verify_current_third_item_settlement,
    write_current_third_item_settlement,
)
from emperor_v4.evaluation.third_item_d_settlement import (
    verify_third_item_d_formal_settlement,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="皇帝综合评价体系 V4 评分命令")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("formal-settlements-verify")
    second_item_a = commands.add_parser("second-item-a-verify")
    second_item_a.add_argument("--workspace-root", type=Path, default=Path("."))
    second_item_b2 = commands.add_parser("second-item-b2-verify")
    second_item_b2.add_argument("--workspace-root", type=Path, default=Path("."))
    second_item_b1 = commands.add_parser("second-item-b1-settlement")
    second_item_b1.add_argument("--workspace-root", type=Path, default=Path("."))
    second_item_b1.add_argument("--write", action="store_true")
    profile_c3 = commands.add_parser("profile-c3-settlement")
    profile_c3.add_argument("--write", action="store_true")
    commands.add_parser("profile-c3-verify")
    commands.add_parser("profile-c2-c5-cross-axis-audit")
    profile_m3 = commands.add_parser("profile-m3-settlement")
    profile_m3.add_argument("--write", action="store_true")
    commands.add_parser("profile-m3-verify")
    profile_m4 = commands.add_parser("profile-m4-settlement")
    profile_m4.add_argument("--write", action="store_true")
    commands.add_parser("profile-m4-verify")
    profile_markdown = commands.add_parser("profile-markdown")
    profile_markdown.add_argument("--write", action="store_true")
    profile_markdown.add_argument("--axis", action="append", choices=sorted(AXIS_FILES))
    profile_radar = commands.add_parser("profile-radar-samples")
    profile_radar.add_argument("--write", action="store_true")
    profile_radar.add_argument("--output-dir", type=Path)
    video_card = commands.add_parser("profile-video-card-samples")
    video_card.add_argument("--write", action="store_true")
    video_card.add_argument("--output-dir", type=Path)
    video_copy = commands.add_parser("profile-video-copy-samples")
    video_copy.add_argument("--write", action="store_true")
    video_copy.add_argument("--output-dir", type=Path)
    composite = commands.add_parser("composite-ranking")
    composite.add_argument("--workspace-root", type=Path, default=Path("."))
    composite.add_argument("--write", action="store_true")
    canonical_pool = commands.add_parser("canonical-ruler-pool")
    canonical_pool.add_argument("--workspace-root", type=Path, default=Path("."))
    canonical_pool.add_argument("--write", action="store_true")
    for name in (
        "first-item-a-registry",
        "first-item-b-registry",
        "first-item-c-registry",
    ):
        command = commands.add_parser(name)
        command.add_argument("--workspace-root", type=Path, default=Path("."))
    third_d = commands.add_parser("third-item-d-verify")
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
    if args.command == "second-item-a-verify":
        report = verify_second_item_a_snapshot(args.workspace_root.resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "second-item-b2-verify":
        report = verify_second_item_b2_snapshot(args.workspace_root.resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "second-item-b1-settlement":
        report = rebuild_second_item_b1(args.workspace_root.resolve(), write=args.write)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-c3-settlement":
        payload = build_profile_c3_settlement(write=args.write)["settlement"]
        print(json.dumps({"record_count": payload["record_count"], "summary": payload["summary"]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-c3-verify":
        print(json.dumps(verify_profile_c3_settlement(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-c2-c5-cross-axis-audit":
        print(json.dumps(inspect_profile_c2_c5_cross_axis_drift(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-m3-settlement":
        payload = build_profile_m3_settlement(write=args.write)["settlement"]
        print(json.dumps({"record_count": payload["record_count"], "summary": payload["summary"]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-m3-verify":
        print(json.dumps(verify_profile_m3_settlement(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-m4-settlement":
        payload = build_profile_m4_settlement(write=args.write)["settlement"]
        print(json.dumps({"record_count": payload["record_count"], "summary": payload["summary"]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-m4-verify":
        print(json.dumps(verify_profile_m4_settlement(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-markdown":
        if not args.write:
            raise SystemExit("profile-markdown 必须显式传入 --write")
        for path in write_profile_markdown_axes(args.axis or AXIS_FILES):
            print(path.relative_to(Path(".").resolve()).as_posix())
        return 0
    if args.command == "profile-radar-samples":
        if not args.write:
            raise SystemExit("profile-radar-samples 必须显式传入 --write")
        report = write_profile_radar_samples(args.output_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-video-card-samples":
        if not args.write:
            raise SystemExit("profile-video-card-samples 必须显式传入 --write")
        report = write_profile_video_card_samples(args.output_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-video-copy-samples":
        if not args.write:
            raise SystemExit("profile-video-copy-samples 必须显式传入 --write")
        report = write_profile_video_copy_samples(args.output_dir)
        print(json.dumps({"people": len(report["people"]), "axis_order": report["axis_order"]}, ensure_ascii=False, indent=2))
        return 0

    workspace_root = args.workspace_root.resolve()
    if args.command == "composite-ranking":
        if args.write:
            return _print_written(write_composite_ranking(workspace_root))
        payload = build_composite_ranking(workspace_root)
        print(
            json.dumps(
                {
                    "record_count": payload["record_count"],
                    "pending_second_item_count": payload["pending_second_item_count"],
                    "mean_score": payload["mean_score"],
                    "median_score": payload["median_score"],
                    "min_score": payload["min_score"],
                    "max_score": payload["max_score"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "canonical-ruler-pool":
        if args.write:
            return _print_written(write_canonical_ruler_pool(workspace_root))
        payload = build_canonical_ruler_pool(workspace_root)
        print(
            json.dumps(
                {
                    "candidate_pool_count": payload["candidate_pool_count"],
                    "included_count": payload["included_count"],
                    "composite_ready_count": payload["composite_ready_count"],
                    "pending_second_item_count": payload["pending_second_item_count"],
                    "pending_first_item_scope_count": payload["pending_first_item_scope_count"],
                    "pending_first_item_formal_settlement_count": payload[
                        "pending_first_item_formal_settlement_count"
                    ],
                    "first_item_outside_candidate_pool_count": payload[
                        "first_item_outside_candidate_pool_count"
                    ],
                    "excluded_count": payload["excluded_count"],
                    "exclusion_reason_counts": payload["exclusion_reason_counts"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "first-item-a-registry":
        return _print_written(write_first_item_a_registry(workspace_root))
    if args.command == "first-item-b-registry":
        return _print_written(write_first_item_b_registry(workspace_root))
    if args.command == "first-item-c-registry":
        return _print_written(write_first_item_c_registry(workspace_root))
    if args.command == "third-item-d-verify":
        result = verify_third_item_d_formal_settlement(workspace_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "third-item-current-settlement":
        payload = (
            write_current_third_item_settlement(workspace_root)
            if args.write
            else verify_current_third_item_settlement(workspace_root)
        )
        print(json.dumps(
            payload["component_coverage_counts"] if args.write else payload,
            ensure_ascii=False,
        ))
        return 0
    raise AssertionError(f"未处理命令：{args.command}")
