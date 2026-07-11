from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v3_coverage_runner import fetch_coverage_contract, run_contract
from scripts.dev.retrieval_v3_evidence_sufficiency import build_evidence_sufficiency, render_markdown as render_evidence_markdown
from scripts.dev.retrieval_v3_material_density_sensitivity import build_sensitivity_report, render_markdown as render_density_markdown
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor
from scripts.dev.retrieval_v3_rule_scorer import (
    DEFAULT_FORMULA_CODE,
    apply_rule_scores,
    build_judgments,
    fetch_judgment_rows,
    fetch_material_policy,
    stable_hash,
)
from scripts.dev.retrieval_v3_run_events import RunEventLogger


class ScoringRunnerError(ValueError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ScoringRunnerError(f"{path}: expected JSON object")
    return dict(value)


def validate_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    item_code = text(value.get("item_code"))
    rule_code = text(value.get("rule_code"))
    formula_code = text(value.get("formula_code")) or DEFAULT_FORMULA_CODE
    if not item_code or not rule_code:
        raise ScoringRunnerError("manifest requires item_code and rule_code")
    targets: list[dict[str, Any]] = []
    seen_emperors: set[str] = set()
    seen_targets: set[str] = set()
    for index, raw in enumerate(value.get("targets") or []):
        if not isinstance(raw, Mapping):
            raise ScoringRunnerError(f"targets[{index}]: expected object")
        emperor_name = text(raw.get("emperor_name"))
        target_code = text(raw.get("target_code"))
        pack_codes = tuple(dict.fromkeys(text(code) for code in raw.get("source_pack_codes") or [] if text(code)))
        if not emperor_name or not target_code or not pack_codes:
            raise ScoringRunnerError(f"targets[{index}]: emperor_name, target_code and source_pack_codes are required")
        if emperor_name in seen_emperors or target_code in seen_targets:
            raise ScoringRunnerError(f"targets[{index}]: duplicate emperor or target")
        seen_emperors.add(emperor_name)
        seen_targets.add(target_code)
        targets.append({
            "emperor_name": emperor_name,
            "target_code": target_code,
            "source_pack_codes": list(pack_codes),
        })
    if not targets:
        raise ScoringRunnerError("manifest requires at least one target")
    return {
        "manifest_version": text(value.get("manifest_version")) or "1.0",
        "scope_code": text(value.get("scope_code")) or f"{item_code}__{rule_code}",
        "item_code": item_code,
        "rule_code": rule_code,
        "formula_code": formula_code,
        "targets": targets,
    }


def input_snapshot(
    *, dsn: str, schema_name: str, manifest: Mapping[str, Any], target: Mapping[str, Any]
) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            policy = fetch_material_policy(
                cur, item_code=text(manifest.get("item_code")), rule_code=text(manifest.get("rule_code")))
            rows = fetch_judgment_rows(
                cur,
                item_code=text(manifest.get("item_code")),
                rule_code=text(manifest.get("rule_code")),
                formula_code=text(manifest.get("formula_code")),
                target_code=text(target.get("target_code")),
                source_pack_codes=target.get("source_pack_codes") or [],
            )
            judgments = build_judgments(rows)
        conn.rollback()
    if judgments and {row.emperor_name for row in judgments} != {text(target.get("emperor_name"))}:
        raise ScoringRunnerError(f"{target.get('target_code')}: emperor lineage mismatch")
    semantic_judgments = [asdict(row) for row in judgments]
    snapshot = {
        "schema_name": schema_name,
        "item_code": text(manifest.get("item_code")),
        "rule_code": text(manifest.get("rule_code")),
        "formula_code": text(manifest.get("formula_code")),
        "target_code": text(target.get("target_code")),
        "emperor_name": text(target.get("emperor_name")),
        "source_pack_codes": list(target.get("source_pack_codes") or []),
        "material_policy": policy,
        "judgments": semantic_judgments,
    }
    return {
        "input_fingerprint": stable_hash(snapshot, length=64),
        "judgment_count": len(judgments),
        "score_judgment_count": sum(row.target_action == "score" for row in judgments),
        "supporting_judgment_count": sum(row.target_action == "supporting_only" for row in judgments),
        "exclude_judgment_count": sum(row.target_action == "exclude" for row in judgments),
    }


def score_summary(payload: Mapping[str, Any], target_code: str) -> dict[str, Any]:
    matches = [row for row in payload.get("clusters") or [] if text(row.get("target_code")) == target_code]
    if len(matches) != 1:
        raise ScoringRunnerError(f"{target_code}: scorer returned {len(matches)} clusters")
    return dict(matches[0])


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 增量评分运行报告", "",
        f"- scope: `{report.get('scope_code')}`",
        f"- mode: `{report.get('mode')}`",
        f"- write_db: `{str(report.get('write_db', False)).lower()}`",
        f"- elapsed_seconds: `{report.get('elapsed_seconds')}`",
        f"- manifest_fingerprint: `{report.get('manifest_fingerprint')}`", "",
        "| 皇帝 | 状态 | 输入 judgments | 正向 | 负向 | 入分材料 | fingerprint time | scorer time |", 
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("targets") or []:
        score = row.get("score") or {}
        timing = row.get("timing") or {}
        lines.append(
            f"| {row.get('emperor_name')} | {row.get('status')} | {row.get('judgment_count', 0)} | "
            f"{score.get('positive_signal', '')} | {score.get('negative_signal', '')} | "
            f"{score.get('material_scores', '')} | {timing.get('fingerprint_seconds', 0)} | "
            f"{timing.get('scorer_seconds', 0)} |"
        )
    lines.extend(["", "## 阶段耗时", ""])
    for key, value in (report.get("stage_timings") or {}).items():
        lines.append(f"- {key}: `{value}` seconds")
    return "\n".join(lines) + "\n"


def run(
    *, dsn: str, schema_name: str, manifest: Mapping[str, Any], output_root: Path,
    previous_report_path: Path | None = None, execute_scorer: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    events = RunEventLogger(output_root / "run_events.jsonl")
    manifest_fingerprint = stable_hash(manifest, length=64)
    previous = read_json(previous_report_path) if previous_report_path and previous_report_path.exists() else {}
    previous_targets = {text(row.get("target_code")): row for row in previous.get("targets") or []}
    previous_details: dict[str, Any] = {}
    if previous_report_path and previous_report_path.exists():
        candidate = previous_report_path.parent / "score_details.json"
        if candidate.exists():
            previous_details = read_json(candidate)

    stage_started = time.perf_counter()
    target_reports: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    for target in manifest.get("targets") or []:
        target_code = text(target.get("target_code"))
        fingerprint_started = time.perf_counter()
        snapshot = input_snapshot(dsn=dsn, schema_name=schema_name, manifest=manifest, target=target)
        fingerprint_seconds = round(time.perf_counter() - fingerprint_started, 3)
        prior = previous_targets.get(target_code) or {}
        unchanged = (
            not execute_scorer
            and text(previous.get("manifest_fingerprint")) == manifest_fingerprint
            and text(prior.get("input_fingerprint")) == snapshot["input_fingerprint"]
            and isinstance(prior.get("score"), Mapping)
        )
        scorer_seconds = 0.0
        if unchanged:
            status = "skipped_unchanged"
            score = dict(prior["score"])
            if target_code in previous_details:
                details[target_code] = previous_details[target_code]
        else:
            scorer_started = time.perf_counter()
            payload = apply_rule_scores(
                dsn=dsn,
                schema_name=schema_name,
                item_code=text(manifest.get("item_code")),
                rule_code=text(manifest.get("rule_code")),
                formula_code=text(manifest.get("formula_code")),
                target_code=target_code,
                source_pack_codes=target.get("source_pack_codes") or [],
                allow_source_pack_execute=execute_scorer,
                execute=execute_scorer,
            )
            scorer_seconds = round(time.perf_counter() - scorer_started, 3)
            status = "executed" if execute_scorer else "calculated_dirty_dry_run"
            score = score_summary(payload, target_code)
            detail_matches = [
                row for row in payload.get("detailed_clusters") or [] if text(row.get("target_code")) == target_code]
            if detail_matches:
                details[target_code] = detail_matches[0]
        target_report = {
            **target,
            **snapshot,
            "status": status,
            "score": score,
            "timing": {
                "fingerprint_seconds": fingerprint_seconds,
                "scorer_seconds": scorer_seconds,
                "total_seconds": round(fingerprint_seconds + scorer_seconds, 3),
            },
        }
        target_reports.append(target_report)
        events.emit("target_complete", emperor_name=target.get("emperor_name"), target_code=target_code, status=status, **target_report["timing"])
    scoring_seconds = round(time.perf_counter() - stage_started, 3)

    coverage_started = time.perf_counter()
    contract = fetch_coverage_contract(
        dsn=dsn,
        schema_name=schema_name,
        emperors=[text(row.get("emperor_name")) for row in manifest.get("targets") or []],
        items=[text(manifest.get("item_code"))],
        rules=[text(manifest.get("rule_code"))],
    )
    previous_coverage = previous_report_path.parent / "coverage" if previous_report_path else None
    coverage = run_contract(
        dsn=dsn,
        schema_name=schema_name,
        contract_rows=contract,
        output_root=output_root / "coverage",
        previous_root=previous_coverage if previous_coverage and previous_coverage.exists() else None,
        scope_inputs={
            f"{manifest.get('item_code')}__{manifest.get('rule_code')}": {
                "source_pack_codes": [
                    code
                    for target in manifest.get("targets") or []
                    for code in target.get("source_pack_codes") or []
                ],
            }
        },
    )
    coverage_seconds = round(time.perf_counter() - coverage_started, 3)

    evidence_started = time.perf_counter()
    coverage_detail_path = output_root / "coverage" / f"{manifest.get('item_code')}__{manifest.get('rule_code')}.json"
    coverage_detail = read_json(coverage_detail_path)
    evidence_sufficiency = build_evidence_sufficiency(
        coverage=coverage_detail,
        score_details=details,
        emperors=[text(row.get("emperor_name")) for row in manifest.get("targets") or []],
    )
    (output_root / "evidence_sufficiency.json").write_text(
        json.dumps(evidence_sufficiency, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    (output_root / "evidence_sufficiency.md").write_text(
        render_evidence_markdown(evidence_sufficiency), encoding="utf-8", newline="\n")
    evidence_seconds = round(time.perf_counter() - evidence_started, 3)
    operational_score_ready = all(
        bool(row.get("operational_score_ready")) for row in evidence_sufficiency.get("emperors") or []
    )

    density_started = time.perf_counter()
    material_density_sensitivity = build_sensitivity_report(
        score_details=details,
        emperors=[text(row.get("emperor_name")) for row in manifest.get("targets") or []],
    )
    (output_root / "material_density_sensitivity.json").write_text(
        json.dumps(material_density_sensitivity, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    (output_root / "material_density_sensitivity.md").write_text(
        render_density_markdown(material_density_sensitivity), encoding="utf-8", newline="\n")
    density_seconds = round(time.perf_counter() - density_started, 3)
    elapsed = round(time.perf_counter() - started, 3)
    report = {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_scoring_runner.py",
        "mode": "execute_scorer" if execute_scorer else "read_only_incremental",
        "write_db": execute_scorer,
        "operational_score_ready": operational_score_ready,
        "schema_name": schema_name,
        "scope_code": text(manifest.get("scope_code")),
        "manifest_fingerprint": manifest_fingerprint,
        "target_count": len(target_reports),
        "dirty_target_count": sum(row["status"] != "skipped_unchanged" for row in target_reports),
        "skipped_target_count": sum(row["status"] == "skipped_unchanged" for row in target_reports),
        "targets": target_reports,
        "coverage_summary": coverage,
        "evidence_sufficiency": evidence_sufficiency,
        "material_density_sensitivity": {
            "mode": material_density_sensitivity["mode"],
            "formal_score_changed": False,
            "scenario_count": len(material_density_sensitivity["scenarios"]),
        },
        "stage_timings": {
            "scoring": scoring_seconds,
            "coverage": coverage_seconds,
            "evidence_sufficiency": evidence_seconds,
            "material_density_sensitivity": density_seconds,
        },
        "elapsed_seconds": elapsed,
        "artifacts": {
            "score_details_json": str(output_root / "score_details.json"),
            "evidence_sufficiency_json": str(output_root / "evidence_sufficiency.json"),
            "evidence_sufficiency_md": str(output_root / "evidence_sufficiency.md"),
            "material_density_sensitivity_json": str(output_root / "material_density_sensitivity.json"),
            "material_density_sensitivity_md": str(output_root / "material_density_sensitivity.md"),
            "coverage_root": str(output_root / "coverage"),
            "run_events_jsonl": str(output_root / "run_events.jsonl"),
        },
    }
    (output_root / "score_details.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    (output_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    (output_root / "report.md").write_text(render_markdown(report), encoding="utf-8", newline="\n")
    events.emit("run_complete", dirty_target_count=report["dirty_target_count"], skipped_target_count=report["skipped_target_count"], elapsed_seconds=elapsed)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run manifest-pinned incremental retrieval_v3 scoring and coverage.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--previous-report", type=Path)
    parser.add_argument("--execute-scorer", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    manifest = validate_manifest(read_json(args.manifest))
    report = run(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        manifest=manifest,
        output_root=args.output_root,
        previous_report_path=args.previous_report,
        execute_scorer=args.execute_scorer,
    )
    print(json.dumps({
        "ok": report["ok"],
        "write_db": report["write_db"],
        "dirty_target_count": report["dirty_target_count"],
        "skipped_target_count": report["skipped_target_count"],
        "elapsed_seconds": report["elapsed_seconds"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
