from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from emperor_v4.evaluation.i5b_civil_discovery_compass import (
    record_discovery_compass,
)
from emperor_v4.evaluation.i5b_current_value_runner import (
    build_outcome_database_dry_run,
    build_i5b_current_value,
    render_scoring_detail_markdown,
)
from emperor_v4.evaluation.i5b_factor_semantics import evaluate_i5b_factor_semantics
from emperor_v4.evaluation.i5b_joint_projection_scored_shadow import (
    build_i5b_joint_projection_scored_shadow,
)
from emperor_v4.evaluation.i5b_ruler_rule_coverage import (
    evaluate_i5b_ruler_rule_coverage,
)
from emperor_v4.evaluation.i5b_ruler_rule_net import build_i5b_ruler_rule_net_report
from emperor_v4.evaluation.i5b_scoring_policy import evaluate_i5b_scoring_policy
from emperor_v4.evaluation.i5b_unified_raw_signal_runner import (
    build_i5b_unified_raw_signal_readiness,
)
from emperor_v4.evaluation.model_policy import resolve_agent_route, validate_model_policy
from emperor_v4.evaluation.current_source_pack_compiler import apply_source_pack_increment
from emperor_v4.runtime.emperor_rebuild import RebuildLimits, rebuild_emperor


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="皇帝综合评价体系 V4 当前命令")
    commands = parser.add_subparsers(dest="command", required=True)

    factor_semantics = commands.add_parser("i5b-factor-semantics")
    factor_semantics.add_argument("--contract", type=Path, required=True)
    factor_semantics.add_argument("--output", type=Path)

    scoring_policy = commands.add_parser("i5b-scoring-policy")
    scoring_policy.add_argument("--policy", type=Path, required=True)
    scoring_policy.add_argument("--output", type=Path)

    current_value = commands.add_parser("i5b-current-value")
    current_value.add_argument("--ruler", required=True)
    current_value.add_argument("--workspace-root", type=Path, default=Path("."))
    current_value.add_argument("--source-pack", type=Path)
    current_value.add_argument("--output-dir", type=Path)

    i5b_run = commands.add_parser("i5b-run")
    i5b_run.add_argument("--ruler", required=True)
    i5b_run.add_argument("--workspace-root", type=Path, default=Path("."))
    i5b_run.add_argument("--detail-output", type=Path)

    scoring_detail = commands.add_parser("i5b-scoring-detail")
    scoring_detail.add_argument("--ruler", required=True)
    scoring_detail.add_argument("--workspace-root", type=Path, default=Path("."))
    scoring_detail.add_argument("--result", type=Path)
    scoring_detail.add_argument("--person")
    scoring_detail.add_argument("--output", type=Path)

    outcome_dry_run = commands.add_parser("historical-outcome-dry-run")
    outcome_dry_run.add_argument("--ruler", required=True)
    outcome_dry_run.add_argument("--workspace-root", type=Path, default=Path("."))
    outcome_dry_run.add_argument("--output", type=Path)

    model_policy = commands.add_parser("model-policy")
    model_policy.add_argument("--policy", type=Path, required=True)
    model_policy.add_argument("--stage")
    model_policy.add_argument("--escalation-reason", action="append", default=[])
    model_policy.add_argument("--output", type=Path)

    joint = commands.add_parser("i5b-joint-projection-scored-shadow")
    joint.add_argument(
        "--rule-code",
        choices=("talent_discovery", "tolerate_talent", "anti_nepotism"),
        required=True,
    )
    joint.add_argument("--projection-input", type=Path, required=True)
    joint.add_argument("--scoring-policy", type=Path, required=True)
    joint.add_argument("--assertion-review", type=Path)
    joint.add_argument("--output", type=Path, required=True)

    unified = commands.add_parser("i5b-unified-raw-signal-readiness")
    unified.add_argument("--appointment-report", type=Path, required=True)
    unified.add_argument("--team-report", type=Path, required=True)
    unified.add_argument("--joint-report", type=Path, action="append", required=True)
    unified.add_argument("--coverage-report", type=Path, action="append", required=True)
    unified.add_argument("--calibration-version", required=True)
    unified.add_argument("--output", type=Path, required=True)

    coverage = commands.add_parser("i5b-ruler-rule-coverage")
    coverage.add_argument("--manifest", type=Path, required=True)
    coverage.add_argument("--output", type=Path, required=True)

    rule_net = commands.add_parser("i5b-ruler-rule-net")
    rule_net.add_argument("--manifest", type=Path, required=True)
    rule_net.add_argument("--output", type=Path, required=True)

    compass = commands.add_parser("i5b-discovery-compass-record")
    compass.add_argument("--ruler", required=True)
    compass.add_argument("--record", type=Path, required=True)
    compass.add_argument("--workspace-root", type=Path, default=Path("."))
    compass.add_argument("--compass", type=Path)
    rebuild = commands.add_parser("emperor-rebuild")
    rebuild.add_argument("--ruler", required=True)
    rebuild.add_argument("--workspace-root", type=Path, default=Path("."))
    rebuild.add_argument("--source-index", type=Path)
    rebuild.add_argument("--source-index-root", type=Path)
    rebuild.add_argument("--dynasty-governance-root", type=Path)
    rebuild.add_argument("--runtime-root", type=Path)
    rebuild.add_argument("--wall-clock-seconds", type=int, default=900)
    rebuild.add_argument("--source-workers", type=int, default=8)
    rebuild.add_argument("--export-workers", type=int, default=4)
    rebuild.add_argument("--max-pages-per-subject", type=int, default=32)
    rebuild.add_argument("--model-workers", type=int, default=4)
    rebuild.add_argument("--model-timeout-seconds", type=int, default=120)
    increment = commands.add_parser("source-pack-apply-increment")
    increment.add_argument("--ruler", required=True)
    increment.add_argument("--workspace-root", type=Path, default=Path("."))
    increment.add_argument("--increment", type=Path, required=True)
    return parser


def _load(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_report(report: Mapping[str, Any], output: Path | None) -> int:
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 1 if report.get("status") == "failed" else 0


def _run_current_value(args: argparse.Namespace) -> int:
    if any(value in args.ruler for value in ("/", "\\", "..")):
        raise ValueError("--ruler 不得包含路径字符")
    workspace_root = args.workspace_root.resolve()
    source_pack = args.source_pack or (
        Path("eval/i5b_current_value") / args.ruler / "source-pack.json"
    )
    if not source_pack.is_absolute():
        source_pack = workspace_root / source_pack
    output_dir = args.output_dir or source_pack.parent
    if not output_dir.is_absolute():
        output_dir = workspace_root / output_dir

    report = build_i5b_current_value(source_pack, workspace_root=workspace_root)
    if report["ruler"] != args.ruler:
        raise ValueError("当前 I5B source pack 与 --ruler 不匹配")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "result.json"
    markdown_path = output_dir / "result.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        render_scoring_detail_markdown(report),
        encoding="utf-8",
        newline="\n",
    )
    print(f"皇帝：{report['ruler']}")
    print(
        "Episode / REU："
        f"{report['declarations']['episode_count']} / "
        f"{report['declarations']['rule_evidence_unit_count']}"
    )
    print(f"加权净信号：{report['net_signal']}")
    print(f"当前结果：{markdown_path}")
    return 0


def _run_i5b(args: argparse.Namespace) -> int:
    if any(value in args.ruler for value in ("/", "\\", "..")):
        raise ValueError("--ruler 不得包含路径字符")
    workspace_root = args.workspace_root.resolve()
    project = _load(workspace_root / "config/project.yml")
    rulers = (project.get("i5b_current_value") or {}).get("rulers") or {}
    configured = rulers.get(args.ruler)
    if not isinstance(configured, Mapping):
        raise ValueError(f"皇帝尚未进入当前 I5B 运行目录: {args.ruler}")
    source_pack = workspace_root / str(configured["source_pack"])
    result_path = workspace_root / str(configured["result"])
    report = build_i5b_current_value(source_pack, workspace_root=workspace_root)
    if report["ruler"] != args.ruler:
        raise ValueError("当前 I5B source pack 与 --ruler 不匹配")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path = result_path.with_suffix(".md")
    markdown_path.write_text(
        render_scoring_detail_markdown(report),
        encoding="utf-8",
        newline="\n",
    )
    if args.detail_output:
        detail_output = args.detail_output
        if not detail_output.is_absolute():
            detail_output = workspace_root / detail_output
        detail_output.parent.mkdir(parents=True, exist_ok=True)
        detail_output.write_text(
            render_scoring_detail_markdown(report),
            encoding="utf-8",
            newline="\n",
        )
    print(f"皇帝：{report['ruler']}")
    print(f"I5B 净信号：{report['net_signal']}")
    print(f"画像状态：{report['net_signal_status']}")
    print(f"当前结果：{markdown_path}")
    return 0


def _run_scoring_detail(args: argparse.Namespace) -> int:
    if any(value in args.ruler for value in ("/", "\\", "..")):
        raise ValueError("--ruler 不得包含路径字符")
    if args.person and any(value in args.person for value in ("/", "\\", "..")):
        raise ValueError("--person 不得包含路径字符")
    workspace_root = args.workspace_root.resolve()
    if args.result is None:
        source_pack = (
            workspace_root
            / "eval"
            / "i5b_current_value"
            / args.ruler
            / "source-pack.json"
        )
        report = build_i5b_current_value(
            source_pack,
            workspace_root=workspace_root,
        )
    else:
        result_path = args.result
        if not result_path.is_absolute():
            result_path = workspace_root / result_path
        report = _load(result_path)
    if not isinstance(report, Mapping) or report.get("ruler") != args.ruler:
        raise ValueError("当前 I5B 结果与 --ruler 不匹配")
    output = args.output
    if output is None:
        output_dir = Path("tmp/i5b_scoring_detail") / args.ruler
        output = (
            output_dir / "persons" / f"{args.person}.md"
            if args.person
            else output_dir / "scoring-detail.md"
        )
    if not output.is_absolute():
        output = workspace_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_scoring_detail_markdown(report, person=args.person),
        encoding="utf-8",
        newline="\n",
    )
    print(f"皇帝：{report['ruler']}")
    if args.person:
        print(f"臣子：{args.person}")
    print(f"计分详情：{output}")
    return 0


def _run_outcome_dry_run(args: argparse.Namespace) -> int:
    if any(value in args.ruler for value in ("/", "\\", "..")):
        raise ValueError("--ruler 不得包含路径字符")
    workspace_root = args.workspace_root.resolve()
    source_pack = workspace_root / "eval/i5b_current_value" / args.ruler / "source-pack.json"
    report = build_i5b_current_value(source_pack, workspace_root=workspace_root)
    dry_run = build_outcome_database_dry_run(report)
    return _write_report(dry_run, args.output)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "i5b-current-value":
        return _run_current_value(args)
    if args.command == "i5b-run":
        return _run_i5b(args)
    if args.command == "i5b-scoring-detail":
        return _run_scoring_detail(args)
    if args.command == "historical-outcome-dry-run":
        return _run_outcome_dry_run(args)
    if args.command == "emperor-rebuild":
        runtime_root = args.runtime_root or (
            args.workspace_root / "tmp" / "emperor_rebuild" / args.ruler
        )
        report = rebuild_emperor(
            workspace_root=args.workspace_root,
            ruler=args.ruler,
            source_index_path=args.source_index,
            source_index_root=args.source_index_root,
            dynasty_governance_root=args.dynasty_governance_root,
            runtime_root=runtime_root,
            limits=RebuildLimits(
                wall_clock_seconds=args.wall_clock_seconds,
                source_workers=args.source_workers,
                export_workers=args.export_workers,
                max_pages_per_subject=args.max_pages_per_subject,
                model_workers=args.model_workers,
                model_timeout_seconds=args.model_timeout_seconds,
            ),
        )
        return _write_report(report, None)
    if args.command == "source-pack-apply-increment":
        workspace_root = args.workspace_root.resolve()
        project = _load(workspace_root / "config/project.yml")
        configured = ((project.get("i5b_current_value") or {}).get("rulers") or {}).get(
            args.ruler
        )
        if not isinstance(configured, Mapping):
            raise ValueError(f"皇帝尚未进入当前链路: {args.ruler}")
        increment_payload = _load(args.increment)
        if not isinstance(increment_payload, Mapping):
            raise ValueError("source-pack increment 必须是 JSON object")
        changed = apply_source_pack_increment(
            workspace_root / str(configured["source_pack"]),
            increment_payload,
            workspace_root=workspace_root,
        )
        print("source-pack：已更新" if changed else "source-pack：无变化")
        return 0
    if args.command == "i5b-discovery-compass-record":
        workspace_root = args.workspace_root.resolve()
        compass_path = args.compass or (
            Path("tmp/i5b_discovery_compass") / f"{args.ruler}.json"
        )
        if not compass_path.is_absolute():
            compass_path = workspace_root / compass_path
        record = _load(args.record)
        if not isinstance(record, Mapping):
            raise ValueError("检索罗盘记录必须是 JSON object")
        changed = record_discovery_compass(
            compass_path,
            ruler=args.ruler,
            record=record,
        )
        print(f"检索罗盘：{compass_path}")
        print("写入：新增" if changed else "写入：已存在，无变化")
        return 0

    if args.command == "i5b-factor-semantics":
        report = evaluate_i5b_factor_semantics(_load(args.contract))
    elif args.command == "i5b-scoring-policy":
        report = evaluate_i5b_scoring_policy(_load(args.policy))
    elif args.command == "model-policy":
        policy = _load(args.policy)
        if args.stage:
            report = resolve_agent_route(
                policy,
                stage_code=args.stage,
                escalation_reasons=args.escalation_reason,
            )
        elif args.escalation_reason:
            raise ValueError("--escalation-reason 必须与 --stage 同时使用")
        else:
            report = validate_model_policy(policy)
    elif args.command == "i5b-joint-projection-scored-shadow":
        report = build_i5b_joint_projection_scored_shadow(
            rule_code=args.rule_code,
            projection_payload=_load(args.projection_input),
            scoring_policy=_load(args.scoring_policy),
            assertion_payload=(
                _load(args.assertion_review) if args.assertion_review else None
            ),
        )
    elif args.command == "i5b-unified-raw-signal-readiness":
        report = build_i5b_unified_raw_signal_readiness(
            appointment_report=_load(args.appointment_report),
            team_report=_load(args.team_report),
            joint_reports=[_load(path) for path in args.joint_report],
            coverage_reports=[_load(path) for path in args.coverage_report],
            calibration_version=args.calibration_version,
        )
    elif args.command == "i5b-ruler-rule-coverage":
        report = evaluate_i5b_ruler_rule_coverage(_load(args.manifest))
    elif args.command == "i5b-ruler-rule-net":
        report = build_i5b_ruler_rule_net_report(_load(args.manifest))
    else:
        raise AssertionError("unreachable")

    return _write_report(report, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
