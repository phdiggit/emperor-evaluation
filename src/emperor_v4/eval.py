from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="皇帝综合评价体系 V4 评分命令")
    commands = parser.add_subparsers(dest="command", required=True)
    maintenance = commands.add_parser("maintenance", help="定位当前裁决、下游影响与必要校验")
    maintenance.add_argument("--component", action="append", required=True)
    maintenance.add_argument("--ruler-id", action="append", default=[])
    maintenance.add_argument("--polity", action="append", default=[])
    maintenance.add_argument("--verify", action="store_true")
    maintenance.add_argument("--related", action="store_true", help="同时执行关联轴的组件校验")
    maintenance.add_argument("--sync", action="store_true", help="校验源后刷新报告列出的确定性下游")
    for name in ("project-entries-verify", "canonical-ruler-pool-verify", "composite-ranking-verify", "second-item-b1-verify", "profile-m1-verify", "profile-c1-verify", "profile-c2-verify", "profile-c5-verify"):
        commands.add_parser(name)
    first_cost = commands.add_parser("first-item-cost-verify")
    first_cost.add_argument("--workspace-root", type=Path, default=Path("."))
    formal = commands.add_parser("formal-settlements-verify")
    formal.add_argument("--item", action="append", choices=["first_item", "second_item", "third_item", "fourth_item", "fifth_item"])
    totals = commands.add_parser("second-item-totals")
    totals.add_argument("--write", action="store_true")
    profile_current = commands.add_parser("profile-current-verify")
    profile_current.add_argument("--axis", required=True, choices=["M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5"])
    fourth_a = commands.add_parser("fourth-item-a-verify")
    fourth_a.add_argument("--workspace-root", type=Path, default=Path("."))
    fourth_a_views = commands.add_parser("fourth-item-a-views")
    fourth_a_views.add_argument("--workspace-root", type=Path, default=Path("."))
    fourth_a_views.add_argument("--write", action="store_true")
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
    profile_markdown.add_argument("--axis", action="append", choices=["C1", "C2", "C3", "C5", "M1", "M2", "M3", "M4"])
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
    third_b1 = commands.add_parser("third-item-b1-settlement")
    third_b1.add_argument("--workspace-root", type=Path, default=Path("."))
    third_b1.add_argument("--write", action="store_true")
    return parser


def _print_written(written: dict[str, Path]) -> int:
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from emperor_v4.evaluation.formal_json_store import json_read_session
    with json_read_session():
        return _dispatch(args)


def _dispatch(args: argparse.Namespace) -> int:
    from emperor_v4.evaluation.first_item_a_registry import write_first_item_a_registry
    from emperor_v4.evaluation.first_item_b_registry import write_first_item_b_registry
    from emperor_v4.evaluation.first_item_c_registry import write_first_item_c_registry
    from emperor_v4.evaluation.first_item_cost import build_first_item_cost_report
    from emperor_v4.evaluation.fourth_item_a import verify as verify_fourth_item_a, write_views as write_fourth_item_a_views
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
    from emperor_v4.evaluation.third_item_b1_settlement import rebuild_third_item_b1
    from emperor_v4.evaluation.third_item_d_settlement import (
        verify_third_item_d_formal_settlement,
    )

    if args.command == "maintenance":
        import contextlib
        import io
        from emperor_v4.evaluation.maintenance import inspect
        report = inspect(Path(".").resolve(), args.component, args.ruler_id, args.polity)
        failures = []
        if args.verify or args.sync:
            report["checks"] = []
            commands = report["validation_commands"] + (report["related_validation_commands"] if args.related else [])
            for command in dict.fromkeys(commands):
                output = io.StringIO()
                try:
                    with contextlib.redirect_stdout(output):
                        if command in {"profile-m3-verify", "second-item-b2-verify"} and (args.ruler_id or args.polity):
                            from emperor_v4.evaluation.maintenance import selected_rulers
                            from emperor_v4.evaluation.profile_m3_verifier import verify_selected, verify_payload, M3_SETTLEMENT
                            ids, polities = selected_rulers(Path(".").resolve(), args.ruler_id, args.polity)
                            if command == "profile-m3-verify":
                                if args.sync:
                                    from emperor_v4.evaluation.formal_json_store import load_json
                                    result = verify_payload(load_json(M3_SETTLEMENT, polities=polities), ruler_ids=ids, polities=polities)
                                else:
                                    result = verify_selected(ids, polities)
                            else:
                                result = verify_second_item_b2_snapshot(Path(".").resolve(), ruler_ids=ids, polities=polities)
                            print(json.dumps(result, ensure_ascii=False))
                            code = 0
                        else:
                            code = main(command.split())
                    if code:
                        raise ValueError(f"exit={code}")
                    report["checks"].append({"command": command, "status": "PASS", "result": json.loads(output.getvalue())})
                except (AssertionError, ValueError, KeyError) as exc:
                    failures.append({"command": command, "error": str(exc) or type(exc).__name__})
            report["failed_checks"] = failures
        if args.sync and not failures and not report["current_link_gaps"]:
            report["refreshed"] = []
            for command in report["refresh_commands"]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(command.split())
                if code:
                    failures.append({"command": command, "error": f"exit={code}"})
                    break
                report["refreshed"].append(command)
            for command in dict.fromkeys(report["downstream_validation_commands"] + report["validation_commands"]):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = main(command.split())
                    if code:
                        raise ValueError(f"exit={code}")
                except (AssertionError, ValueError, KeyError) as exc:
                    failures.append({"command": command, "error": str(exc) or type(exc).__name__})
            report["failed_checks"] = failures
        if failures:
            report["status"] = "FAILED"
        elif args.sync:
            report["status"] = "SYNCED" if not report["current_link_gaps"] else "REVIEW_REQUIRED"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if failures or report["current_link_gaps"] else 0
    if args.command == "second-item-totals":
        report = rebuild_second_item_b1(Path(".").resolve(), write=args.write, refresh_source=False)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "profile-current-verify":
        from emperor_v4.evaluation.maintenance import verify_profile_current
        print(json.dumps(verify_profile_current(Path(".").resolve(), args.axis), ensure_ascii=False, indent=2))
        return 0
    standalone = {
        "canonical-ruler-pool-verify": ("canonical_ruler_pool", "verify_canonical_ruler_pool", True),
        "composite-ranking-verify": ("composite_ranking", "verify_composite_ranking", True),
        "project-entries-verify": ("project_entries", "verify", True),
        "second-item-b1-verify": ("formal_settlements", "verify_second_item_b1_snapshot", True),
        "profile-m1-verify": ("profile_m1_verifier", "verify", False),
        "profile-c1-verify": ("profile_c1_verifier", "verify", True),
        "profile-c2-verify": ("profile_c2_verifier", "verify", False),
        "profile-c5-verify": ("profile_c2_c5_verifier", "verify", False),
    }
    if args.command in standalone:
        from importlib import import_module
        module, function, needs_root = standalone[args.command]
        verify = getattr(import_module(f"emperor_v4.evaluation.{module}"), function)
        result = verify(Path(".").resolve()) if needs_root else verify()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command in ("fourth-item-a-verify", "fourth-item-a-views"):
        if args.command == "fourth-item-a-views" and args.write:
            report = write_fourth_item_a_views(args.workspace_root.resolve())
        else:
            report = verify_fourth_item_a(args.workspace_root.resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "formal-settlements-verify":
        report = verify_formal_settlements(Path(".").resolve(), items=set(args.item) if args.item else None)
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
    if args.command == "first-item-cost-verify":
        report = build_first_item_cost_report(workspace_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['status'] == 'READY' else 1
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
    if args.command == "third-item-b1-settlement":
        print(json.dumps(
            rebuild_third_item_b1(workspace_root, write=args.write),
            ensure_ascii=False,
            indent=2,
        ))
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
