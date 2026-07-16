from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import yaml

from emperor_v4.evaluation.i5b_factor_semantics import evaluate_i5b_factor_semantics
from emperor_v4.evaluation.i5b_civil_candidate_retrieval import (
    build_civil_browser_worklist,
    run_civil_candidate_retrieval,
)
from emperor_v4.evaluation.i5b_joint_projection_scored_shadow import (
    build_i5b_joint_projection_scored_shadow,
)
from emperor_v4.evaluation.i5b_material_budget_scored_shadow import (
    build_i5b_material_budget_shadow,
    render_i5b_material_budget_shadow_markdown,
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
from emperor_v4.persistence.person_profile_read import read_current_person_profiles


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
    detail_export.add_argument("--civil-source-pack", type=Path)

    closeout = commands.add_parser("i5b-historical-closeout")
    closeout.add_argument("--ruler", required=True)
    closeout.add_argument(
        "--catalog",
        type=Path,
        default=Path("eval/i5b_scoring_detail/catalog.yml"),
    )
    closeout.add_argument("--workspace-root", type=Path, default=Path("."))
    closeout.add_argument("--person", action="append", default=[])
    closeout.add_argument("--rule", action="append", default=[])
    closeout.add_argument("--civil-source-pack", type=Path)
    closeout.add_argument(
        "--output-dir", type=Path, default=Path("tmp/i5b_historical_closeout")
    )
    return parser


def _load(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_civil_source_pack(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = _load(path)
    if not isinstance(payload, Mapping):
        raise ValueError("浏览器文官候选包必须是 JSON object")
    return payload


def _build_detail(
    manifest: dict[str, Any],
    workspace_root: Path,
    *,
    payload_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    def load_relative(path_value: str) -> Any:
        if payload_overrides is not None and path_value in payload_overrides:
            return payload_overrides[path_value]
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


def _v4_dsn(workspace_root: Path) -> str:
    if value := os.environ.get("EMPEROR_EVAL_V4_DSN"):
        return value
    env_path = workspace_root / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("EMPEROR_EVAL_V4_DSN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("未配置 EMPEROR_EVAL_V4_DSN，无法读取唯一人物画像表")


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
        forwarded = [
            "i5b-historical-closeout",
            "--ruler", args.ruler,
            "--catalog", str(args.catalog),
            "--workspace-root", str(args.workspace_root),
            "--output-dir", str(args.output_dir),
        ]
        for person in args.person:
            forwarded.extend(("--person", person))
        for rule in args.rule:
            forwarded.extend(("--rule", rule))
        if args.civil_source_pack:
            forwarded.extend(("--civil-source-pack", str(args.civil_source_pack)))
        return main(forwarded)
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
        for obsolete_name in (
            "preflight.json",
            "civil-retrieval.json",
            "civil-retrieval-cache.json",
            "civil-materials.json",
        ):
            obsolete_path = output_dir / obsolete_name
            if obsolete_path.is_file():
                obsolete_path.unlink()
        entries = [
            row
            for row in catalog.get("entries") or ()
            if row.get("ruler") == args.ruler
        ]
        if not entries:
            print(f"皇帝：{args.ruler}")
            print("未配置该皇帝")
            return 2
        fresh_material_report = None
        fresh_detail_report = None
        civil_retrieval_report = None
        if len(entries) == 1:
            entry = entries[0]
            closeout = entry.get("closeout") or {}
            profiles = read_current_person_profiles(_v4_dsn(workspace_root))
            material_manifest_path = (
                workspace_root / closeout["material_budget_manifest"]
            )
            material_manifest = _load(material_manifest_path)
            work_budget = _load(workspace_root / closeout["work_budget"])
            team_source = _load(
                workspace_root
                / material_manifest["rules"]["team_building"]["source"]
            )
            source_pack_path = args.civil_source_pack or closeout.get(
                "civil_source_pack"
            ) or (workspace_root / "tmp/i5b_browser_sources" / f"{args.ruler}.json")
            source_pack_path = Path(source_pack_path)
            if not source_pack_path.is_absolute():
                source_pack_path = workspace_root / source_pack_path
            try:
                source_pack = _load_civil_source_pack(source_pack_path)
            except FileNotFoundError:
                worklist = build_civil_browser_worklist(
                    ruler=args.ruler,
                    ruler_names=tuple(closeout["retrieval_names"]),
                    team_source=team_source,
                    current_profiles=profiles,
                    max_candidate_judge_items=int(
                        work_budget["per_rule_run"]["max_candidate_judge_items"]
                    ),
                )
                print(f"皇帝：{args.ruler}")
                print(f"缺少浏览器文官候选包：{source_pack_path}")
                print("待检索：" + "；".join(row["query"] for row in worklist))
                print("请先在 Codex 主会话完成每人一次、最多等待10秒的 Google 宽检索与史料回源")
                return 3
            civil_retrieval_report = run_civil_candidate_retrieval(
                ruler=args.ruler,
                ruler_names=tuple(closeout["retrieval_names"]),
                team_source=team_source,
                current_profiles=profiles,
                max_candidate_judge_items=int(
                    work_budget["per_rule_run"]["max_candidate_judge_items"]
                ),
                source_pack=source_pack,
            )
            appointment = material_manifest["rules"]["appointment_delegation"]
            appointment.setdefault("direct_materials", []).extend(
                civil_retrieval_report["materials"]
            )
            appointment.setdefault("eligible", {}).setdefault("positive", []).extend(
                civil_retrieval_report["eligible"]
            )
            appointment.setdefault("excluded", []).extend(
                civil_retrieval_report["excluded"]
            )
            fresh_material_report = build_i5b_material_budget_shadow(
                material_manifest_path,
                current_profiles=profiles,
                manifest_payload=material_manifest,
            )
            detail_manifest = _load(workspace_root / entry["manifest"])
            material_paths = {
                str(detail_manifest["ruler_rule_net"]),
                *(
                    str(source["path"])
                    for source in detail_manifest["detail_sources"]
                    if source.get("adapter") == "material_budget_report"
                ),
            }
            payload_overrides: dict[str, Any] = {
                path: fresh_material_report for path in material_paths
            }
            for source in detail_manifest["detail_sources"]:
                if source.get("adapter") != "appointment_parity_report":
                    continue
                path = str(source["path"])
                appointment_payload = deepcopy(_load(workspace_root / path))
                trace = appointment_payload.setdefault(
                    "assertion_episode_reu_trace", {}
                )
                episodes = trace.setdefault("episodes", [])
                episodes.extend(civil_retrieval_report.get("episodes") or ())
                trace["episode_count"] = len(episodes)
                payload_overrides[path] = appointment_payload
            fresh_detail_report = _build_detail(
                detail_manifest,
                workspace_root,
                payload_overrides=payload_overrides,
            )
        elapsed_seconds = round(time.monotonic() - started, 6)
        detail_json_path = output_dir / "scoring-detail.json"
        detail_markdown_path = output_dir / "scoring-detail.md"
        material_json_path = output_dir / "material-budget-shadow.json"
        material_markdown_path = output_dir / "material-budget-shadow.md"
        if fresh_material_report is not None:
            material_json_path.write_text(
                json.dumps(
                    fresh_material_report,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            material_markdown_path.write_text(
                render_i5b_material_budget_shadow_markdown(fresh_material_report),
                encoding="utf-8",
                newline="\n",
            )
        if fresh_detail_report is not None:
            closeout_ruler_reports = _catalog_reports(catalog, workspace_root)
            if fresh_detail_report is not None:
                closeout_ruler_reports[args.ruler] = fresh_detail_report
            detail_report = build_i5b_scoring_detail_selection(
                catalog=catalog,
                selection={
                    "schema_version": "i5b-scoring-detail-selection-v1",
                    "rulers": [args.ruler],
                    "people": list(args.person),
                    "rules": list(args.rule),
                    "person_scope": "selected_rulers",
                    "strict": True,
                },
                ruler_reports=closeout_ruler_reports,
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
        print(f"皇帝：{args.ruler}")
        if args.person:
            print(f"臣子：{'、'.join(args.person)}")
        if civil_retrieval_report is not None:
            print(
                "文官材料："
                f"{len(civil_retrieval_report['eligible'])}条通过，"
                f"{len(civil_retrieval_report['excluded'])}条排除，"
                f"{civil_retrieval_report['deferred_candidate_count']}人未领取"
            )
        if fresh_detail_report is not None:
            print(f"计分详情：{detail_markdown_path}")
            print(f"机器结果：{detail_json_path}")
        print(f"耗时：{elapsed_seconds}秒")
        return 0
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
