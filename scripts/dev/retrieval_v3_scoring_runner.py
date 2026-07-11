from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev import retrieval_v3_claim_chain_candidates as claim_chain_candidates
from scripts.dev import retrieval_v3_claim_rule_route_plan as claim_rule_route_plan
from scripts.dev import retrieval_v3_cross_rule_router as cross_rule_router
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
    raw_rules = value.get("rules") or ([value.get("rule_code")] if value.get("rule_code") else [])
    rules: list[dict[str, str]] = []
    seen_rules: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        rule = raw_rule if isinstance(raw_rule, Mapping) else {"rule_code": raw_rule}
        rule_code = text(rule.get("rule_code"))
        if not rule_code:
            raise ScoringRunnerError(f"rules[{index}]: rule_code is required")
        if rule_code in seen_rules:
            raise ScoringRunnerError(f"rules[{index}]: duplicate rule_code")
        seen_rules.add(rule_code)
        rules.append({"rule_code": rule_code, "aggregation_family": text(rule.get("aggregation_family"))})
    rule_code = rules[0]["rule_code"] if len(rules) == 1 else ""
    formula_code = text(value.get("formula_code")) or DEFAULT_FORMULA_CODE
    if not item_code or not rules:
        raise ScoringRunnerError("manifest requires item_code and at least one rule")
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
        "scope_code": text(value.get("scope_code")) or (
            f"{item_code}__{rule_code}" if rule_code else f"{item_code}__{len(rules)}_rules"),
        "item_code": item_code,
        "rule_code": rule_code,
        "rules": rules,
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


def fetch_audit_matrix(
    *, dsn: str, schema_name: str, manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return one read-only consumption-chain audit row per emperor/rule cell."""
    target_codes = [text(row.get("target_code")) for row in manifest.get("targets") or []]
    rule_codes = [text(row.get("rule_code")) for row in manifest.get("rules") or []]
    pack_codes = [
        text(code)
        for target in manifest.get("targets") or []
        for code in target.get("source_pack_codes") or []
        if text(code)
    ]
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                with cells as (
                    select rt.id as target_id, rt.target_code, rt.emperor_name, rt.item_code, r.rule_code
                      from retrieval_v3.retrieval_targets rt
                      cross join unnest(%s::text[]) as r(rule_code)
                     where rt.target_code = any(%s::text[])
                       and rt.item_code = %s
                ), allowed_claims as (
                    select mc.*, sp.target_id
                      from retrieval_v3.material_claims mc
                      join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
                     where sp.pack_code = any(%s::text[])
                       and sp.coverage_status = 'passed'
                       and mc.review_status::text not in ('rejected', 'retired')
                ), candidate_stats as (
                    select ac.target_id, c.candidate_rule_code as rule_code,
                           count(distinct ac.id)::int as material_claims,
                           count(*)::int as scoring_candidates,
                           count(*) filter (where c.review_status::text in ('accepted', 'resolved'))::int as accepted_candidates,
                           count(*) filter (where c.resolved_binding_id is null)::int as unresolved_candidates
                      from allowed_claims ac
                      join retrieval_v3.claim_rule_binding_candidates c on c.claim_id = ac.id
                     where c.review_status::text not in ('rejected', 'retired')
                       and coalesce(c.candidate_payload->>'scoring_candidate', 'false') = 'true'
                     group by ac.target_id, c.candidate_rule_code
                ), binding_stats as (
                    select ac.target_id, b.rule_code,
                           count(*) filter (where b.review_status = 'accepted' and b.usable_for_scoring_cluster)::int as accepted_bindings,
                           count(*) filter (where b.review_status in ('pending', 'accepted') and b.usable_for_scoring_cluster)::int as scoring_bindings,
                           count(*) filter (
                               where b.review_status in ('pending', 'accepted') and b.usable_for_scoring_cluster
                                 and not exists (
                                     select 1 from retrieval_v3.claim_rule_binding_factor_judgments j
                                      where j.binding_id = b.id and j.formula_code = %s
                                 )
                           )::int as factorization_gaps,
                           max(b.updated_at) as latest_binding_at
                      from allowed_claims ac
                      join retrieval_v3.claim_rule_bindings b on b.claim_id = ac.id
                     group by ac.target_id, b.rule_code
                ), judgment_stats as (
                    select j.target_id, j.rule_code,
                           count(distinct j.id) filter (where j.review_status::text = 'accepted')::int as factor_judgments,
                           count(distinct j.id) filter (where j.review_status::text = 'accepted' and j.target_action::text = 'score')::int as score_judgments,
                           count(distinct j.id) filter (
                               where j.review_status::text = 'accepted' and j.target_action::text = 'score'
                                 and not exists (
                                     select 1 from retrieval_v3.claim_rule_binding_material_scores ms
                                      where ms.factor_judgment_id = j.id
                                 )
                                and not coalesce(
                                    cluster.calc_detail->'deduped_factor_judgment_ids' @> to_jsonb(array[j.id]), false)
                           )::int as material_score_gaps,
                           count(distinct j.id) filter (
                               where j.review_status::text = 'accepted' and j.target_action::text = 'score'
                                 and not exists (
                                     select 1
                                       from retrieval_v3.claim_rule_bindings b
                                       join retrieval_v3.material_object_links mol
                                         on mol.claim_id = j.claim_id and mol.role = b.object_role
                                        and mol.review_status::text = 'accepted'
                                      where b.id = j.binding_id
                                 )
                           )::int as object_lineage_gaps,
                           count(distinct coalesce(mc.claim_payload->>'cached_claim_key', mc.raw_claim_code, mc.claim_code))::int as claim_lineage_count,
                           count(distinct gm.group_key)::int as event_group_lineage_count,
                           count(distinct css.document_code)::int as source_document_lineage_count,
                           count(distinct mol.object_id)::int as object_lineage_count,
                           max(j.updated_at) as latest_factor_at
                      from retrieval_v3.claim_rule_binding_factor_judgments j
                      join allowed_claims mc on mc.id = j.claim_id and mc.target_id = j.target_id
                      join retrieval_v3.claim_rule_bindings b on b.id = j.binding_id
                      left join retrieval_v3.target_rule_score_clusters cluster
                        on cluster.target_id = j.target_id and cluster.rule_code = j.rule_code
                       and cluster.formula_code = j.formula_code
                      left join retrieval_v3.claim_event_group_members gm
                        on gm.claim_key = coalesce(mc.claim_payload->>'cached_claim_key', mc.raw_claim_code, mc.claim_code)
                      left join retrieval_v3.claim_evidence ce
                        on ce.claim_key = coalesce(mc.claim_payload->>'cached_claim_key', mc.raw_claim_code, mc.claim_code)
                      left join retrieval_v3.claim_source_slices css on css.slice_hash = ce.slice_hash
                      left join retrieval_v3.material_object_links mol
                        on mol.claim_id = j.claim_id and mol.role = b.object_role and mol.review_status::text = 'accepted'
                     where j.item_code = %s and j.formula_code = %s
                     group by j.target_id, j.rule_code
                ), score_stats as (
                    select ms.target_id, ms.rule_code, count(*)::int as material_scores,
                           max(ms.updated_at) as latest_material_score_at
                      from retrieval_v3.claim_rule_binding_material_scores ms
                      join allowed_claims ac on ac.id = ms.claim_id and ac.target_id = ms.target_id
                     where ms.item_code = %s and ms.formula_code = %s
                     group by ms.target_id, ms.rule_code
                ), blocked_stats as (
                    select ac.target_id, c.candidate_rule_code as rule_code, count(distinct q.id)::int as blocked_reviews
                      from allowed_claims ac
                      join retrieval_v3.claim_rule_binding_candidates c on c.claim_id = ac.id
                      join retrieval_v3.material_review_queue q on q.claim_id = ac.id
                     where q.queue_status::text in ('ready', 'needs_review', 'running', 'blocked')
                     group by ac.target_id, c.candidate_rule_code
                )
                select cells.*,
                       greatest(coalesce(cs.material_claims, 0), coalesce(js.claim_lineage_count, 0)) as material_claims,
                       coalesce(cs.scoring_candidates, 0) as scoring_candidates,
                       coalesce(cs.accepted_candidates, 0) as accepted_candidates,
                       coalesce(cs.unresolved_candidates, 0) as unresolved_candidates,
                       coalesce(bs.accepted_bindings, 0) as accepted_bindings,
                       coalesce(bs.scoring_bindings, 0) as scoring_bindings,
                       coalesce(bs.factorization_gaps, 0) as factorization_gaps,
                       coalesce(js.factor_judgments, 0) as factor_judgments,
                       coalesce(js.score_judgments, 0) as score_judgments,
                       coalesce(ss.material_scores, 0) as material_scores,
                       coalesce(js.material_score_gaps, 0) as material_score_gaps,
                       coalesce(js.object_lineage_gaps, 0) as object_lineage_gaps,
                       coalesce(js.claim_lineage_count, 0) as claim_lineage_count,
                       coalesce(js.event_group_lineage_count, 0) as event_group_lineage_count,
                       coalesce(js.source_document_lineage_count, 0) as source_document_lineage_count,
                       coalesce(js.object_lineage_count, 0) as object_lineage_count,
                       coalesce(bl.blocked_reviews, 0) as blocked_reviews,
                       p.id as material_policy_id, p.policy_code, p.policy_version, p.carrier_mode,
                       coalesce(p.policy_payload->'side_aggregation'->>'mode', '') as aggregation_mode,
                       c.id as cluster_id, c.positive_signal::text, c.negative_signal::text,
                       (c.positive_signal - c.negative_signal)::text as net_signal,
                       c.scored_judgment_count, c.supporting_judgment_count, c.excluded_judgment_count,
                       coalesce(c.calc_detail->>'policy_code', '') as cluster_policy_code,
                       coalesce(c.calc_detail->>'policy_version', '') as cluster_policy_version,
                       c.updated_at as cluster_updated_at,
                       greatest(bs.latest_binding_at, js.latest_factor_at, ss.latest_material_score_at) as latest_input_at
                  from cells
                  left join candidate_stats cs using (target_id, rule_code)
                  left join binding_stats bs using (target_id, rule_code)
                  left join judgment_stats js using (target_id, rule_code)
                  left join score_stats ss using (target_id, rule_code)
                  left join blocked_stats bl using (target_id, rule_code)
                  left join retrieval_v3.eval_rule_material_policies p
                    on p.item_code = cells.item_code and p.rule_code = cells.rule_code and p.policy_status::text = 'active'
                  left join retrieval_v3.target_rule_score_clusters c
                    on c.target_id = cells.target_id and c.item_code = cells.item_code
                   and c.rule_code = cells.rule_code and c.formula_code = %s
                 order by array_position(%s::text[], cells.rule_code), array_position(%s::text[], cells.target_code)
                """,
                (
                    rule_codes, target_codes, text(manifest.get("item_code")), pack_codes,
                    text(manifest.get("formula_code")),
                    text(manifest.get("item_code")), text(manifest.get("formula_code")),
                    text(manifest.get("item_code")), text(manifest.get("formula_code")),
                    text(manifest.get("formula_code")), rule_codes, target_codes,
                ),
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    aggregation_families = {
        text(rule.get("rule_code")): text(rule.get("aggregation_family"))
        for rule in manifest.get("rules") or []
    }
    for row in rows:
        cluster_missing = row.get("cluster_id") is None
        cluster_stale = bool(
            not cluster_missing
            and (
                (row.get("latest_input_at") and row.get("cluster_updated_at") < row.get("latest_input_at"))
                or text(row.get("cluster_policy_code")) != text(row.get("policy_code"))
                or text(row.get("cluster_policy_version")) != text(row.get("policy_version"))
            )
        )
        gaps = {
            "unresolved_candidates": int(row.get("unresolved_candidates") or 0),
            "factorization": int(row.get("factorization_gaps") or 0),
            "material_scores": int(row.get("material_score_gaps") or 0),
            "object_lineage": int(row.get("object_lineage_gaps") or 0),
            "blocked_reviews": int(row.get("blocked_reviews") or 0),
        }
        missing_stage = ""
        if not int(row.get("material_claims") or 0):
            missing_stage = "material_claims"
        elif not int(row.get("scoring_bindings") or 0) and not int(row.get("factor_judgments") or 0):
            missing_stage = "scoring_bindings"
        elif not int(row.get("factor_judgments") or 0):
            missing_stage = "factor_judgments"
        row["aggregation_family"] = aggregation_families.get(text(row.get("rule_code")), "")
        row["missing_stage"] = missing_stage
        row["gaps"] = gaps
        row["cluster_state"] = "missing" if cluster_missing else ("stale" if cluster_stale else "current")
        row["dirty_state"] = "dirty" if cluster_missing or cluster_stale or missing_stage or any(gaps.values()) else "clean"
        row["scorer_ready"] = bool(
            row.get("material_policy_id")
            and int(row.get("factor_judgments") or 0) > 0
            and not gaps["factorization"]
            and not gaps["object_lineage"]
            and not gaps["blocked_reviews"]
        )
    return rows


def combine_reuse_candidates(
    *, rules: Sequence[str], emperors: Sequence[str],
    claim_routes: Sequence[Mapping[str, Any]], cross_candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    selected_rules = [text(rule) for rule in rules if text(rule) and text(rule) != "appointment_delegation"]
    for rule_code in selected_rules:
        for emperor_name in emperors:
            mechanical = [
                dict(row) for row in claim_routes
                if text(row.get("candidate_rule_code")) == rule_code
                and text(row.get("emperor_name")) == emperor_name
            ]
            formal = [
                dict(row) for row in cross_candidates
                if text(row.get("candidate_rule_code")) == rule_code
                and text(row.get("emperor_name")) == emperor_name
            ]
            cells.append({
                "emperor_name": emperor_name,
                "rule_code": rule_code,
                "mechanical_route_count": len(mechanical),
                "appointment_reuse_candidate_count": len(formal),
                "mechanical_object_count": len({text(row.get("object_name")) for row in mechanical if text(row.get("object_name"))}),
                "appointment_reuse_object_count": len({text(row.get("object_name")) for row in formal if text(row.get("object_name"))}),
                "route_status_counts": dict(sorted(Counter(text(row.get("route_status")) for row in mechanical).items())),
                "mechanical_routes": mechanical,
                "appointment_reuse_candidates": formal,
            })
    return {
        "ok": len(cells) == len(selected_rules) * len(emperors),
        "mode": "read_only_existing_claim_reuse_plan",
        "write_db": False,
        "write_job": False,
        "agent_called": False,
        "rules": selected_rules,
        "emperors": list(emperors),
        "cell_count": len(cells),
        "mechanical_route_count": sum(int(row["mechanical_route_count"]) for row in cells),
        "appointment_reuse_candidate_count": sum(int(row["appointment_reuse_candidate_count"]) for row in cells),
        "cells": cells,
    }


def build_reuse_candidate_report(
    *, dsn: str, schema_name: str, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    emperors = [text(row.get("emperor_name")) for row in manifest.get("targets") or []]
    rules = [text(row.get("rule_code")) for row in manifest.get("rules") or []]
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            claims = claim_chain_candidates.fetch_claim_rows(
                cur, emperor_names=emperors, statuses=("active",), owner_scopes=(),
            )
            claim_plan = claim_rule_route_plan.build_plan(claims, min_members=2)
            cross_plan = cross_rule_router.build_plan(
                cur, item_code=text(manifest.get("item_code")),
                source_rule_code="appointment_delegation", emperors=emperors,
                canonical_only=True,
            )
        conn.rollback()
    report = combine_reuse_candidates(
        rules=rules, emperors=emperors,
        claim_routes=claim_plan.get("routes") or [],
        cross_candidates=cross_plan.get("candidates") or [],
    )
    report["input_active_claim_count"] = int(claim_plan.get("input_claim_count") or 0)
    report["appointment_source_claim_count"] = int((cross_plan.get("totals") or {}).get("source_claims") or 0)
    report["formal_candidates_missing_contract_rule"] = int(
        (cross_plan.get("totals") or {}).get("formal_candidates_missing_contract_rule") or 0)
    return report


def render_reuse_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 三人 I5B 现有材料复用计划", "",
        "- mode: `read_only_existing_claim_reuse_plan`",
        "- write_db/write_job/agent_called: `false/false/false`",
        f"- input_active_claim_count: `{report.get('input_active_claim_count', 0)}`",
        f"- mechanical_route_count: `{report.get('mechanical_route_count', 0)}`",
        f"- appointment_reuse_candidate_count: `{report.get('appointment_reuse_candidate_count', 0)}`", "",
        "| 皇帝 | rule | mechanical routes | mechanical objects | appointment reuse | reuse objects |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("cells") or []:
        lines.append(
            f"| {row.get('emperor_name')} | {row.get('rule_code')} | {row.get('mechanical_route_count', 0)} | "
            f"{row.get('mechanical_object_count', 0)} | {row.get('appointment_reuse_candidate_count', 0)} | "
            f"{row.get('appointment_reuse_object_count', 0)} |"
        )
    return "\n".join(lines) + "\n"


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


def render_matrix_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 三人完整 I5B 只读审计", "",
        f"- scope: `{report.get('scope_code')}`",
        f"- mode: `{report.get('mode')}`",
        f"- write_db/write_job: `false/false`",
        f"- cells: `{report.get('cell_count')}`", "",
        "| 皇帝 | rule | claims | candidates | accepted/scoring bindings | factors | material scores | cluster | readiness | gaps |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in report.get("cells") or []:
        gap_parts = [f"{key}={value}" for key, value in (row.get("gaps") or {}).items() if value]
        if row.get("missing_stage"):
            gap_parts.insert(0, f"missing_stage={row.get('missing_stage')}")
        gaps = ", ".join(gap_parts) or "none"
        lines.append(
            f"| {row.get('emperor_name')} | {row.get('rule_code')} | {row.get('material_claims', 0)} | "
            f"{row.get('scoring_candidates', 0)} | {row.get('accepted_bindings', 0)}/{row.get('scoring_bindings', 0)} | "
            f"{row.get('factor_judgments', 0)} | {row.get('material_scores', 0)} | "
            f"{row.get('cluster_state')} | {str(row.get('scorer_ready', False)).lower()} | {gaps} |"
        )
    lines.extend(["", "## Lineage", "", "| 皇帝 | rule | claims | event groups | source docs | objects |", "| --- | --- | ---: | ---: | ---: | ---: |"])
    for row in report.get("cells") or []:
        lines.append(
            f"| {row.get('emperor_name')} | {row.get('rule_code')} | {row.get('claim_lineage_count', 0)} | "
            f"{row.get('event_group_lineage_count', 0)} | {row.get('source_document_lineage_count', 0)} | "
            f"{row.get('object_lineage_count', 0)} |"
        )
    return "\n".join(lines) + "\n"


def run_matrix(
    *, dsn: str, schema_name: str, manifest: Mapping[str, Any], output_root: Path
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    audit_started = time.perf_counter()
    cells = fetch_audit_matrix(dsn=dsn, schema_name=schema_name, manifest=manifest)
    audit_seconds = round(time.perf_counter() - audit_started, 3)

    reuse_started = time.perf_counter()
    reuse_candidates = build_reuse_candidate_report(dsn=dsn, schema_name=schema_name, manifest=manifest)
    (output_root / "reuse_candidates.json").write_text(
        json.dumps(reuse_candidates, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8", newline="\n",
    )
    (output_root / "reuse_candidates.md").write_text(
        render_reuse_markdown(reuse_candidates), encoding="utf-8", newline="\n",
    )
    reuse_seconds = round(time.perf_counter() - reuse_started, 3)

    coverage_started = time.perf_counter()
    rules = [text(row.get("rule_code")) for row in manifest.get("rules") or []]
    emperors = [text(row.get("emperor_name")) for row in manifest.get("targets") or []]
    contract = fetch_coverage_contract(
        dsn=dsn, schema_name=schema_name, emperors=emperors,
        items=[text(manifest.get("item_code"))], rules=rules,
    )
    scope_inputs = {
        f"{manifest.get('item_code')}__{rule_code}": {
            "source_pack_codes": [
                code for target in manifest.get("targets") or [] for code in target.get("source_pack_codes") or []
            ]
        }
        for rule_code in rules
    }
    coverage = run_contract(
        dsn=dsn, schema_name=schema_name, contract_rows=contract,
        output_root=output_root / "coverage", scope_inputs=scope_inputs,
    )
    coverage_seconds = round(time.perf_counter() - coverage_started, 3)
    report = {
        "ok": len(cells) == len(rules) * len(emperors),
        "generated_by": "scripts/dev/retrieval_v3_scoring_runner.py",
        "mode": "read_only_i5b_matrix_audit",
        "write_db": False,
        "write_job": False,
        "schema_name": schema_name,
        "scope_code": text(manifest.get("scope_code")),
        "manifest_fingerprint": stable_hash(manifest, length=64),
        "cell_count": len(cells),
        "ready_cell_count": sum(bool(row.get("scorer_ready")) for row in cells),
        "dirty_cell_count": sum(text(row.get("dirty_state")) == "dirty" for row in cells),
        "complete_rule_coverage": all(text(row.get("cluster_state")) == "current" for row in cells),
        "cells": cells,
        "reuse_candidates": {
            "mode": reuse_candidates["mode"],
            "mechanical_route_count": reuse_candidates["mechanical_route_count"],
            "appointment_reuse_candidate_count": reuse_candidates["appointment_reuse_candidate_count"],
            "formal_candidates_missing_contract_rule": reuse_candidates["formal_candidates_missing_contract_rule"],
        },
        "coverage_summary": coverage,
        "stage_timings": {"audit": audit_seconds, "reuse_candidates": reuse_seconds, "coverage": coverage_seconds},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "artifacts": {
            "report_json": str(output_root / "report.json"),
            "report_md": str(output_root / "report.md"),
            "reuse_candidates_json": str(output_root / "reuse_candidates.json"),
            "reuse_candidates_md": str(output_root / "reuse_candidates.md"),
            "coverage_root": str(output_root / "coverage"),
        },
    }
    (output_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8", newline="\n",
    )
    (output_root / "report.md").write_text(render_matrix_markdown(report), encoding="utf-8", newline="\n")
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
    dsn = resolve_dsn(args.dsn_env)
    if len(manifest.get("rules") or []) > 1:
        if args.execute_scorer:
            raise ScoringRunnerError("multi-rule matrix mode is read-only; scorer execution requires explicit per-rule authorization")
        report = run_matrix(dsn=dsn, schema_name=args.pg_schema, manifest=manifest, output_root=args.output_root)
    else:
        report = run(
            dsn=dsn, schema_name=args.pg_schema, manifest=manifest,
            output_root=args.output_root, previous_report_path=args.previous_report,
            execute_scorer=args.execute_scorer,
        )
    print(json.dumps({
        "ok": report["ok"],
        "write_db": report["write_db"],
        "dirty_target_count": report.get("dirty_target_count", report.get("dirty_cell_count", 0)),
        "skipped_target_count": report.get("skipped_target_count", 0),
        "elapsed_seconds": report["elapsed_seconds"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
