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
    build_i5b_current_value,
    render_markdown as render_i5b_current_value_markdown,
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

    scoring_detail = commands.add_parser("i5b-scoring-detail")
    scoring_detail.add_argument("--ruler", required=True)
    scoring_detail.add_argument("--workspace-root", type=Path, default=Path("."))
    scoring_detail.add_argument("--result", type=Path)
    scoring_detail.add_argument("--output", type=Path, required=True)

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

    report = build_i5b_current_value(source_pack)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "result.json"
    markdown_path = output_dir / "result.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        render_i5b_current_value_markdown(report),
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


def _run_scoring_detail(args: argparse.Namespace) -> int:
    if any(value in args.ruler for value in ("/", "\\", "..")):
        raise ValueError("--ruler 不得包含路径字符")
    workspace_root = args.workspace_root.resolve()
    result_path = args.result or (
        Path("eval/i5b_current_value") / args.ruler / "result.json"
    )
    if not result_path.is_absolute():
        result_path = workspace_root / result_path
    report = _load(result_path)
    if not isinstance(report, Mapping) or report.get("ruler") != args.ruler:
        raise ValueError("当前 I5B 结果与 --ruler 不匹配")
    output = args.output
    if not output.is_absolute():
        output = workspace_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_scoring_detail_markdown(report),
        encoding="utf-8",
        newline="\n",
    )
    print(f"皇帝：{report['ruler']}")
    print(f"计分详情：{output}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "i5b-current-value":
        return _run_current_value(args)
    if args.command == "i5b-scoring-detail":
        return _run_scoring_detail(args)
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
