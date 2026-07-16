from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Sequence

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

    detail_export = commands.add_parser("i5b-scoring-detail-export")
    detail_export.add_argument("--ruler", required=True)
    detail_export.add_argument(
        "--catalog",
        type=Path,
        default=Path("eval/i5b_scoring_detail/catalog.yml"),
    )
    detail_export.add_argument("--workspace-root", type=Path, default=Path("."))
    detail_export.add_argument(
        "--output-dir", type=Path, default=Path("tmp/i5b_scoring_detail")
    )
    detail_export.add_argument("--person", action="append", default=[])
    detail_export.add_argument("--rule", action="append", default=[])

    closeout = commands.add_parser("i5b-historical-closeout")
    closeout.add_argument("--ruler", required=True)
    closeout.add_argument(
        "--catalog",
        type=Path,
        default=Path("eval/i5b_scoring_detail/catalog.yml"),
    )
    closeout.add_argument("--workspace-root", type=Path, default=Path("."))
    closeout.add_argument(
        "--output-dir", type=Path, default=Path("tmp/i5b_historical_closeout")
    )
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


def _catalog_reports(
    catalog: dict[str, Any], workspace_root: Path
) -> dict[str, dict[str, Any]]:
    return {
        entry["ruler"]: _build_detail(
            _load(workspace_root / entry["manifest"]), workspace_root
        )
        for entry in catalog["entries"]
    }


def _historical_closeout_preflight(
    *,
    ruler: str,
    catalog: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    entries = [row for row in catalog.get("entries") or () if row.get("ruler") == ruler]
    if len(entries) > 1:
        raise ValueError(f"historical closeout ruler 未唯一配置: {ruler}")
    if not entries:
        work_budget = _load(
            workspace_root / "config/i5b-historical-work-budget.yml"
        )
        return {
            "schema_version": "i5b-historical-closeout-preflight-v1",
            "status": "bounded_input_not_configured",
            "ruler": ruler,
            "deadline_seconds": int(
                work_budget["per_ruler_run"]["max_wall_clock_minutes"]
            )
            * 60,
            "completion_reserve_seconds": int(
                work_budget["per_ruler_run"].get("completion_reserve_seconds") or 0
            ),
            "blockers": ["ruler_work_package_missing"],
            "talent_candidate_boundary": {
                "status": "not_started_without_work_package",
                "raw_unresolved_candidate_count": 0,
                "deduplicated_boundary_candidate_count": 0,
                "deduplicated_boundary_candidates": [],
                "settled_positive_count": 0,
                "positive_budget": 3,
                "boundary_changing_candidates_remain": False,
                "stop_reason": "work_package_missing",
                "exhaustive_search_required": False,
            },
            "runtime_stages": ["check_ruler_work_package", "stop_before_retrieval"],
            "declarations": {
                "expensive_campaign_started": False,
                "model_call_count": 0,
                "database_write_count": 0,
                "network_request_count": 0,
                "formal_45_point_score": None,
                "tier": None,
                "ranking": None,
            },
        }
    entry = entries[0]
    closeout = entry.get("closeout") or {}
    if set(closeout) != {"work_budget"}:
        raise ValueError("historical closeout 输入配置不完整")
    detail_report = _build_detail(
        _load(workspace_root / entry["manifest"]), workspace_root
    )
    talent = next(
        row for row in detail_report["rules"] if row["rule_code"] == "talent_discovery"
    )
    primary = next(
        source for source in talent["detail_sources"] if source["role"] == "primary"
    )
    talent_detail = primary["detail"]
    talent_budget = int(talent_detail["positive_budget"])
    settled_positive = sum(
        row["side"] == "positive" for row in talent_detail["materials"]
    )
    boundary = {
        "status": "material_budget_saturated_stop",
        "raw_unresolved_candidate_count": 0,
        "deduplicated_boundary_candidate_count": 0,
        "deduplicated_boundary_candidates": [],
        "settled_positive_count": settled_positive,
        "positive_budget": talent_budget,
        "boundary_changing_candidates_remain": False,
        "stop_reason": "positive_material_budget_full",
        "exhaustive_search_required": False,
    }
    work_budget = _load(workspace_root / closeout["work_budget"])
    max_minutes = int(work_budget["per_ruler_run"]["max_wall_clock_minutes"])
    blockers = []
    if not detail_report["declarations"]["current_factor_contracts_satisfied"]:
        blockers.append("factor_contract_mismatch")
    if settled_positive < talent_budget:
        blockers.append("talent_positive_material_budget_not_full")
    return {
        "schema_version": "i5b-historical-closeout-preflight-v1",
        "status": (
            "blocked_before_bounded_shadow"
            if blockers
            else "bounded_shadow_ready"
        ),
        "ruler": ruler,
        "deadline_seconds": max_minutes * 60,
        "completion_reserve_seconds": int(
            work_budget["per_ruler_run"].get("completion_reserve_seconds") or 0
        ),
        "blockers": blockers,
        "talent_candidate_boundary": boundary,
        "runtime_stages": [
            "load_current_material_pool",
            "select_up_to_three_per_side",
            "export_bounded_shadow",
        ],
        "declarations": {
            "expensive_campaign_started": False,
            "model_call_count": 0,
            "database_write_count": 0,
            "network_request_count": 0,
            "formal_45_point_score": None,
            "tier": None,
            "ranking": None,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
        reports = _catalog_reports(catalog, workspace_root)
        report = build_i5b_scoring_detail_selection(
            catalog=catalog,
            selection=_load(args.selection),
            ruler_reports=reports,
        )
        output_format = args.format
    elif args.command == "i5b-scoring-detail-export":
        if any(value in args.ruler for value in ("/", "\\", "..")):
            raise ValueError("--ruler 不得包含路径字符")
        workspace_root = args.workspace_root.resolve()
        catalog_path = (
            args.catalog
            if args.catalog.is_absolute()
            else workspace_root / args.catalog
        )
        catalog = _load(catalog_path)
        report = build_i5b_scoring_detail_selection(
            catalog=catalog,
            selection={
                "schema_version": "i5b-scoring-detail-selection-v1",
                "rulers": [args.ruler],
                "people": list(args.person),
                "rules": list(args.rule),
                "person_scope": "selected_rulers",
                "strict": True,
            },
            ruler_reports=_catalog_reports(catalog, workspace_root),
        )
        output_dir = (
            args.output_dir
            if args.output_dir.is_absolute()
            else workspace_root / args.output_dir
        ) / args.ruler
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "scoring-detail.json"
        markdown_path = output_dir / "scoring-detail.md"
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        markdown_path.write_text(
            render_i5b_scoring_detail_selection_markdown(report),
            encoding="utf-8",
            newline="\n",
        )
        ruler_report = report["selected_ruler_reports"][0]
        selection_summary = ruler_report["selection_summary"]
        print(f"皇帝：{args.ruler}")
        print(f"结果状态：{ruler_report['status']}")
        print(
            "历史覆盖："
            f"{ruler_report['summary']['historical_coverage_complete_rule_count']}/5"
        )
        print(
            "完成声明："
            f"{ruler_report['declarations']['completion_claim_allowed']}"
        )
        print(
            "五条rule加权raw signal："
            f"{selection_summary['selected_rule_weighted_raw_signal']}"
        )
        print(f"Markdown：{markdown_path}")
        print(f"JSON：{json_path}")
        return 0
    elif args.command == "i5b-historical-closeout":
        started = time.monotonic()
        if any(value in args.ruler for value in ("/", "\\", "..")):
            raise ValueError("--ruler 不得包含路径字符")
        workspace_root = args.workspace_root.resolve()
        catalog_path = (
            args.catalog if args.catalog.is_absolute() else workspace_root / args.catalog
        )
        catalog = _load(catalog_path)
        output_dir = (
            args.output_dir
            if args.output_dir.is_absolute()
            else workspace_root / args.output_dir
        ) / args.ruler
        output_dir.mkdir(parents=True, exist_ok=True)
        report = _historical_closeout_preflight(
            ruler=args.ruler,
            catalog=catalog,
            workspace_root=workspace_root,
        )
        report["elapsed_wall_clock_seconds"] = round(time.monotonic() - started, 6)
        output_path = output_dir / "preflight.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        detail_json_path = output_dir / "scoring-detail.json"
        detail_markdown_path = output_dir / "scoring-detail.md"
        if not report["blockers"]:
            detail_report = build_i5b_scoring_detail_selection(
                catalog=catalog,
                selection={
                    "schema_version": "i5b-scoring-detail-selection-v1",
                    "rulers": [args.ruler],
                    "people": [],
                    "rules": [],
                    "person_scope": "selected_rulers",
                    "strict": True,
                },
                ruler_reports=_catalog_reports(catalog, workspace_root),
            )
            detail_json_path.write_text(
                json.dumps(detail_report, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            detail_markdown_path.write_text(
                render_i5b_scoring_detail_selection_markdown(detail_report),
                encoding="utf-8",
                newline="\n",
            )
        boundary = report["talent_candidate_boundary"]
        print(f"皇帝：{args.ruler}")
        print(f"状态：{report['status']}")
        print(f"15分钟昂贵流程已启动：{report['declarations']['expensive_campaign_started']}")
        print(
            "人才边界候选："
            f"{boundary['deduplicated_boundary_candidate_count']}组"
            f"（原始{boundary['raw_unresolved_candidate_count']}条）"
        )
        stop_reasons = {
            "positive_material_budget_full": "正向材料已满3条",
            "work_package_missing": "缺少该皇帝工作包，未启动检索",
        }
        print(f"人才停止原因：{stop_reasons[boundary['stop_reason']]}")
        if not report["blockers"]:
            print(f"计分详情：{detail_markdown_path}")
            print(f"机器结果：{detail_json_path}")
        print(f"运行声明：{output_path}")
        return 2 if report["blockers"] else 0
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
