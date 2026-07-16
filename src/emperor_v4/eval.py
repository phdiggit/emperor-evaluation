from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.i5b_factor_semantics import evaluate_i5b_factor_semantics
from emperor_v4.evaluation.i5b_joint_projection_scored_shadow import (
    build_i5b_joint_projection_scored_shadow,
)
from emperor_v4.evaluation.i5b_ruler_rule_coverage import (
    evaluate_i5b_ruler_rule_coverage,
)
from emperor_v4.evaluation.i5b_ruler_rule_net import build_i5b_ruler_rule_net_report
from emperor_v4.evaluation.i5b_scoring_detail import (
    build_i5b_scoring_detail,
    build_i5b_scoring_detail_selection,
    render_i5b_scoring_detail_markdown,
    render_i5b_scoring_detail_selection_markdown,
)
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

    detail = commands.add_parser("i5b-scoring-detail")
    detail.add_argument("--manifest", type=Path, required=True)
    detail.add_argument("--workspace-root", type=Path, default=Path("."))
    detail.add_argument("--format", choices=("json", "markdown"), required=True)
    detail.add_argument("--output", type=Path, required=True)

    selection = commands.add_parser("i5b-scoring-detail-select")
    selection.add_argument("--catalog", type=Path, required=True)
    selection.add_argument("--selection", type=Path, required=True)
    selection.add_argument("--workspace-root", type=Path, default=Path("."))
    selection.add_argument("--format", choices=("json", "markdown"), required=True)
    selection.add_argument("--output", type=Path, required=True)
    return parser


def _load(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _build_detail(manifest: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    def load_relative(path_value: str) -> Any:
        return _load(workspace_root / path_value)

    return build_i5b_scoring_detail(
        manifest=manifest,
        rule_net=load_relative(manifest["ruler_rule_net"]),
        scoring_policy=load_relative(manifest["scoring_policy"]),
        display_catalog=load_relative(manifest["display_catalog"]),
        detail_sources=[
            {"payload": load_relative(source["path"])}
            for source in manifest["detail_sources"]
        ],
    )


def main() -> int:
    args = _parser().parse_args()
    output_format = "json"

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
    elif args.command == "i5b-scoring-detail":
        report = _build_detail(_load(args.manifest), args.workspace_root.resolve())
        output_format = args.format
    elif args.command == "i5b-scoring-detail-select":
        workspace_root = args.workspace_root.resolve()
        catalog = _load(args.catalog)
        reports = {
            entry["ruler"]: _build_detail(
                _load(workspace_root / entry["manifest"]), workspace_root
            )
            for entry in catalog["entries"]
        }
        report = build_i5b_scoring_detail_selection(
            catalog=catalog,
            selection=_load(args.selection),
            ruler_reports=reports,
        )
        output_format = args.format
    else:
        raise AssertionError("unreachable")

    if output_format == "markdown" and args.command == "i5b-scoring-detail":
        rendered = render_i5b_scoring_detail_markdown(report)
    elif output_format == "markdown":
        rendered = render_i5b_scoring_detail_selection_markdown(report)
    else:
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 1 if report.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
