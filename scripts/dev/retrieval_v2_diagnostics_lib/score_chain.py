from __future__ import annotations

from typing import Any, Mapping, Sequence

from scripts.dev.retrieval_v2_diagnostics_lib.common import (
    DEFAULT_TOP_MATERIALS_PER_TARGET,
    check_entry,
    decimal_text,
    fetch_rows,
    json_array,
    json_object,
    numeric_sort_value,
    scoped_with,
    short_text,
    text,
)
from scripts.dev.retrieval_v2_diagnostics_lib.selectors import build_score_chain_selectors, score_chain_params

def normalize_passages(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in json_array(value):
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "source_title": text(row.get("source_title")),
                "title": text(row.get("title")),
                "locator": text(row.get("locator")),
                "passage_code": text(row.get("passage_code")),
                "quote": short_text(row.get("quote"), max_chars=180),
            }
        )
    return rows

def normalize_factor_choices(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in json_array(value):
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "factor_name": text(row.get("factor_name")),
                "option_code": text(row.get("option_code")),
                "option_label": text(row.get("option_label")),
                "value_num": decimal_text(row.get("value_num")),
            }
        )
    return rows


def factor_choices_from_refs(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    refs = json_object(value)
    for factor_name in sorted(refs):
        ref = refs.get(factor_name)
        if not isinstance(ref, Mapping):
            continue
        rows.append(
            {
                "factor_name": text(factor_name),
                "option_code": text(ref.get("option_code")),
                "option_label": text(ref.get("label")) or text(ref.get("option_label")) or text(ref.get("option_code")),
                "value_num": decimal_text(ref.get("value_num")),
            }
        )
    return rows


def normalize_rule_scorer_material(
    row: Mapping[str, Any],
    *,
    target_code: str,
    emperor_name: str,
) -> dict[str, Any]:
    claim_summary = text(row.get("claim_summary")) or text(row.get("patch_note"))
    return {
        "target_code": target_code,
        "emperor_name": emperor_name,
        "factor_judgment_id": int(row.get("factor_judgment_id") or 0),
        "binding_id": int(row.get("binding_id") or 0),
        "binding_code": text(row.get("binding_code")),
        "claim_id": int(row.get("claim_id") or 0),
        "claim_code": text(row.get("claim_code")),
        "claim_summary": claim_summary,
        "claim_summary_short": short_text(claim_summary, max_chars=120),
        "claim_object_name": text(row.get("object_name")),
        "claim_direction": text(row.get("judgment_side")),
        "predicate": text(row.get("predicate")),
        "binding_direction": text(row.get("binding_direction")),
        "object_role": text(row.get("object_role")),
        "object_id": int(row["object_id"]) if row.get("object_id") is not None else None,
        "target_object_id": int(row["target_object_id"]) if row.get("target_object_id") is not None else None,
        "object_name": text(row.get("object_name")),
        "side": text(row.get("side")),
        "judgment_side": text(row.get("judgment_side")),
        "raw_score": decimal_text(row.get("raw_score")),
        "abs_score": decimal_text(row.get("abs_score")),
        "factor_values": json_object(row.get("factor_values")),
        "factor_choices": factor_choices_from_refs(row.get("factor_refs")),
        "passages": normalize_passages(row.get("passages")),
    }


def normalize_material_score_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_code": text(row.get("target_code")),
        "emperor_name": text(row.get("emperor_name")),
        "factor_judgment_id": int(row.get("factor_judgment_id") or 0),
        "binding_id": int(row.get("binding_id") or 0),
        "binding_code": text(row.get("binding_code")),
        "claim_id": int(row.get("claim_id") or 0),
        "claim_code": text(row.get("claim_code")),
        "claim_summary": text(row.get("claim_summary")),
        "claim_summary_short": short_text(row.get("claim_summary"), max_chars=120),
        "claim_object_name": text(row.get("claim_object_name")),
        "claim_direction": text(row.get("claim_direction")),
        "predicate": text(row.get("predicate")),
        "binding_direction": text(row.get("binding_direction")),
        "object_role": text(row.get("object_role")),
        "object_id": int(row["object_id"]) if row.get("object_id") is not None else None,
        "target_object_id": int(row["target_object_id"]) if row.get("target_object_id") is not None else None,
        "object_name": text(row.get("object_name")) or text(row.get("claim_object_name")),
        "side": text(row.get("side")),
        "judgment_side": text(row.get("judgment_side")),
        "raw_score": decimal_text(row.get("raw_score")),
        "abs_score": decimal_text(row.get("abs_score")),
        "factor_values": json_object(row.get("factor_values")),
        "factor_choices": normalize_factor_choices(row.get("factor_choices")),
        "passages": normalize_passages(row.get("passages")),
    }

def object_side_summary(
    cluster: Mapping[str, Any],
    materials: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    detail = json_object(cluster.get("calc_detail"))
    detail_scores = json_object(detail.get("object_side_scores"))
    raw_scores = json_object(cluster.get("object_side_scores"))
    material_counts: dict[tuple[str, str], int] = {}
    for material in materials:
        side = text(material.get("side"))
        object_id = text(material.get("object_id"))
        if side and object_id:
            material_counts[(side, object_id)] = material_counts.get((side, object_id), 0) + 1

    result: dict[str, list[dict[str, Any]]] = {"positive": [], "negative": []}
    for side in ("positive", "negative"):
        side_detail = json_object(detail_scores.get(side))
        side_raw = json_object(raw_scores.get(side))
        object_ids = sorted(set(side_detail) | set(side_raw), key=lambda value: numeric_sort_value(side_raw.get(value)), reverse=True)
        rows: list[dict[str, Any]] = []
        for object_id in object_ids:
            detail_entry = side_detail.get(object_id)
            if isinstance(detail_entry, Mapping):
                score = detail_entry.get("score")
                object_name = text(detail_entry.get("object_name"))
            else:
                score = detail_entry or side_raw.get(object_id)
                object_name = ""
            rows.append(
                {
                    "object_id": int(object_id) if object_id.isdigit() else object_id,
                    "object_name": object_name,
                    "side": side,
                    "score": decimal_text(score or side_raw.get(object_id)),
                    "material_count": material_counts.get((side, object_id), 0),
                }
            )
        result[side] = sorted(rows, key=lambda row: numeric_sort_value(row.get("score")), reverse=True)
    return result

def top_materials(materials: Sequence[Mapping[str, Any]], limit: int) -> list[dict[str, Any]]:
    sorted_rows = sorted(materials, key=lambda row: numeric_sort_value(row.get("abs_score")), reverse=True)
    if limit <= 0:
        return [dict(row) for row in sorted_rows]
    return [dict(row) for row in sorted_rows[:limit]]


def build_score_chain_from_rule_scorer_payload(
    rule_scorer_payload: Mapping[str, Any],
    *,
    target_code: str = "",
    target_codes: Sequence[str] | None = None,
    emperors: Sequence[str] | None = None,
    selector_type: str = "",
    selector_role: str = "",
    names: Sequence[str] | None = None,
    top_materials_per_target: int = DEFAULT_TOP_MATERIALS_PER_TARGET,
) -> dict[str, Any]:
    selector_payload = build_score_chain_selectors(
        target_code=target_code,
        target_codes=target_codes,
        emperors=emperors,
        selector_type=selector_type,
        selector_role=selector_role,
        names=names,
    )
    selected_target_codes = set(selector_payload["target_codes"])
    selected_emperors = set(selector_payload["emperors"])
    targets: list[dict[str, Any]] = []
    formula_params: dict[str, Any] = {}
    for cluster in json_array(rule_scorer_payload.get("detailed_clusters")):
        if not isinstance(cluster, Mapping):
            continue
        cluster_target_code = text(cluster.get("target_code"))
        emperor_name = text(cluster.get("emperor_name"))
        if selected_target_codes and cluster_target_code not in selected_target_codes:
            continue
        if selected_emperors and emperor_name not in selected_emperors:
            continue
        calc_detail = json_object(cluster.get("calc_detail"))
        target_materials = [
            normalize_rule_scorer_material(row, target_code=cluster_target_code, emperor_name=emperor_name)
            for row in json_array(calc_detail.get("materials"))
            if isinstance(row, Mapping)
        ]
        if not formula_params:
            formula_params = json_object(calc_detail.get("formula_params"))
        action_counts = json_object(cluster.get("action_counts")) or json_object(calc_detail.get("raw_action_counts"))
        target_entry = {
            "target_id": int(cluster.get("target_id") or 0),
            "target_code": cluster_target_code,
            "emperor_name": emperor_name,
            "item_code": text(cluster.get("item_code") or rule_scorer_payload.get("item_code")),
            "rule_code": text(cluster.get("rule_code") or rule_scorer_payload.get("rule_code")),
            "formula_code": text(cluster.get("formula_code") or rule_scorer_payload.get("formula_code")),
            "positive_signal": decimal_text(cluster.get("positive_signal")),
            "negative_signal": decimal_text(cluster.get("negative_signal")),
            "scored_judgment_count": int(action_counts.get("score") or len(target_materials)),
            "supporting_judgment_count": int(action_counts.get("supporting_only") or 0),
            "excluded_judgment_count": int(action_counts.get("exclude") or 0),
            "review_status": text(cluster.get("review_status")) or "dry_run",
            "formula_params": json_object(calc_detail.get("formula_params")),
            "object_side_scores": object_side_summary({"object_side_scores": {}, "calc_detail": calc_detail}, target_materials),
            "top_materials": top_materials(target_materials, top_materials_per_target),
            "materials": target_materials,
        }
        targets.append(target_entry)
    totals = {
        "targets": len(targets),
        "clusters": len(targets),
        "material_scores": sum(len(target.get("materials") or []) for target in targets),
        "scored_judgments": sum(int(target.get("scored_judgment_count") or 0) for target in targets),
        "supporting_judgments": sum(int(target.get("supporting_judgment_count") or 0) for target in targets),
        "excluded_judgments": sum(int(target.get("excluded_judgment_count") or 0) for target in targets),
    }
    observations = build_score_chain_observations(targets)
    totals["observations"] = sum(1 for row in observations if int(row.get("count") or 0) > 0)
    return {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "score-chain",
        "ok": True,
        "source": {
            "kind": "rule_scorer_json",
            "generated_by": text(rule_scorer_payload.get("generated_by")),
            "write_db": bool(rule_scorer_payload.get("write_db")),
        },
        "scope": {
            "item_code": text(rule_scorer_payload.get("item_code")),
            "rule_code": text(rule_scorer_payload.get("rule_code")),
            "formula_code": text(rule_scorer_payload.get("formula_code")),
            "scope": "rule-scorer-json",
            "target_code": target_code,
            "target_codes": selector_payload["target_codes"],
            "emperors": selector_payload["emperors"],
            "selectors": selector_payload["selectors"],
        },
        "render_options": {"top_materials_per_target": top_materials_per_target},
        "formula_params": formula_params,
        "observations": observations,
        "totals": totals,
        "targets": targets,
    }


def enrich_score_chain_claim_details(cur: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    targets = [dict(target) for target in payload.get("targets") or [] if isinstance(target, Mapping)]
    claim_ids = sorted(
        {
            int(material.get("claim_id") or 0)
            for target in targets
            for material in target.get("materials") or []
            if isinstance(material, Mapping) and int(material.get("claim_id") or 0) > 0
        }
    )
    if not claim_ids:
        result["targets"] = targets
        return result
    rows = fetch_rows(
        cur,
        """
        select
            mc.id as claim_id,
            mc.claim_code,
            mc.claim_summary,
            mc.object_name as claim_object_name,
            mc.direction as claim_direction,
            coalesce(ev.passages, '[]'::jsonb) as passages
          from retrieval_v2.material_claims mc
          left join lateral (
                select jsonb_agg(
                    jsonb_build_object(
                        'source_title', sd.source_title,
                        'title', sd.title,
                        'locator', spg.locator,
                        'passage_code', spg.passage_code,
                        'quote', left(spg.raw_text, 220)
                    )
                    order by csp.id
                ) as passages
                  from retrieval_v2.claim_source_passages csp
                  join retrieval_v2.source_passages spg on spg.id = csp.source_passage_id
                  join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
                 where csp.claim_id = mc.id
          ) ev on true
         where mc.id = any(%s)
        """,
        (claim_ids,),
    )
    lookup = {int(row.get("claim_id") or 0): row for row in rows}

    def enrich_material(material: Mapping[str, Any]) -> dict[str, Any]:
        enriched = dict(material)
        row = lookup.get(int(enriched.get("claim_id") or 0))
        if not row:
            return enriched
        enriched["claim_code"] = text(row.get("claim_code")) or text(enriched.get("claim_code"))
        enriched["claim_summary"] = text(row.get("claim_summary")) or text(enriched.get("claim_summary"))
        enriched["claim_summary_short"] = short_text(enriched.get("claim_summary"), max_chars=120)
        enriched["claim_object_name"] = text(row.get("claim_object_name")) or text(enriched.get("claim_object_name"))
        enriched["claim_direction"] = text(row.get("claim_direction")) or text(enriched.get("claim_direction"))
        passages = normalize_passages(row.get("passages"))
        if passages:
            enriched["passages"] = passages
        return enriched

    enriched_targets: list[dict[str, Any]] = []
    for target in targets:
        enriched_target = dict(target)
        enriched_target["materials"] = [
            enrich_material(material) for material in target.get("materials") or [] if isinstance(material, Mapping)
        ]
        enriched_target["top_materials"] = [
            enrich_material(material) for material in target.get("top_materials") or [] if isinstance(material, Mapping)
        ]
        enriched_targets.append(enriched_target)
    result["targets"] = enriched_targets
    source = dict(result.get("source") or {})
    source["claim_details_enriched"] = True
    result["source"] = source
    return result


def build_score_chain_observations(targets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    duplicate_examples: list[dict[str, Any]] = []
    capped_examples: list[dict[str, Any]] = []
    balance_examples: list[dict[str, Any]] = []
    side_mismatch_examples: list[dict[str, Any]] = []
    for target in targets:
        positive_signal = numeric_sort_value(target.get("positive_signal"))
        negative_signal = numeric_sort_value(target.get("negative_signal"))
        if negative_signal >= positive_signal and negative_signal > 0:
            balance_examples.append(
                {
                    "target_code": text(target.get("target_code")),
                    "emperor_name": text(target.get("emperor_name")),
                    "positive_signal": text(target.get("positive_signal")),
                    "negative_signal": text(target.get("negative_signal")),
                }
            )
        grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
        for material in target.get("materials") or []:
            if not isinstance(material, Mapping):
                continue
            key = (text(material.get("claim_id")), text(material.get("object_id")), text(material.get("side")))
            grouped.setdefault(key, []).append(material)
            raw_score = numeric_sort_value(material.get("raw_score"))
            abs_score = numeric_sort_value(material.get("abs_score"))
            side = text(material.get("side"))
            judgment_side = text(material.get("judgment_side"))
            if judgment_side and judgment_side != side:
                side_mismatch_examples.append(
                    {
                        "target_code": text(target.get("target_code")),
                        "emperor_name": text(target.get("emperor_name")),
                        "object_name": text(material.get("object_name")),
                        "judgment_side": judgment_side,
                        "score_side": side,
                        "raw_score": text(material.get("raw_score")),
                        "abs_score": text(material.get("abs_score")),
                        "claim_summary": short_text(material.get("claim_summary"), max_chars=100),
                    }
                )
            if abs(raw_score) > abs_score + 0.0005:
                capped_examples.append(
                    {
                        "target_code": text(target.get("target_code")),
                        "emperor_name": text(target.get("emperor_name")),
                        "object_name": text(material.get("object_name")),
                        "side": text(material.get("side")),
                        "raw_score": text(material.get("raw_score")),
                        "abs_score": text(material.get("abs_score")),
                        "claim_summary": short_text(material.get("claim_summary"), max_chars=100),
                    }
                )
        for rows in grouped.values():
            if len(rows) <= 1:
                continue
            first = rows[0]
            duplicate_examples.append(
                {
                    "target_code": text(target.get("target_code")),
                    "emperor_name": text(target.get("emperor_name")),
                    "claim_id": int(first.get("claim_id") or 0),
                    "object_id": first.get("object_id"),
                    "object_name": text(first.get("object_name")),
                    "side": text(first.get("side")),
                    "material_count": len(rows),
                    "binding_codes": [text(row.get("binding_code")) for row in rows],
                    "claim_summary": short_text(first.get("claim_summary"), max_chars=120),
                }
            )
    return [
        check_entry(
            "score_chain_duplicate_claim_object_side",
            count=len(duplicate_examples),
            severity="warning",
            owner="human",
            description="同一 target、claim、object 和 side 产生多条 material score；可能是多 predicate 合理入分，也可能是同一事实重复计入。",
            examples=duplicate_examples[:10],
        ),
        check_entry(
            "score_chain_negative_ge_positive",
            count=len(balance_examples),
            severity="info",
            owner="human",
            description="负向 appointment_delegation 信号大于或等于正向信号；不一定错误，但应优先抽查材料语义。",
            examples=balance_examples[:10],
        ),
        check_entry(
            "score_chain_material_score_capped",
            count=len(capped_examples),
            severity="info",
            owner="human",
            description="单条材料 raw_score 超过材料封顶，abs_score 已按公式封顶；用于观察高强度材料集中度。",
            examples=capped_examples[:10],
        ),
        check_entry(
            "score_chain_judgment_side_score_side_mismatch",
            count=len(side_mismatch_examples),
            severity="info",
            owner="human",
            description="因子化原始 side 与最终入分 side 不一致；通常表示候选方向为任用事实，但因子乘积转为负向入分。",
            examples=side_mismatch_examples[:10],
        ),
    ]

def fetch_score_chain(
    cur: Any,
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    target_code: str = "",
    target_codes: Sequence[str] | None = None,
    emperors: Sequence[str] | None = None,
    selector_type: str = "",
    selector_role: str = "",
    names: Sequence[str] | None = None,
    top_materials_per_target: int = DEFAULT_TOP_MATERIALS_PER_TARGET,
) -> dict[str, Any]:
    with_cte = scoped_with(scope)
    selector_payload = build_score_chain_selectors(
        target_code=target_code,
        target_codes=target_codes,
        emperors=emperors,
        selector_type=selector_type,
        selector_role=selector_role,
        names=names,
    )
    selected_target_codes = selector_payload["target_codes"]
    selected_emperors = selector_payload["emperors"]
    params = score_chain_params(item_code, rule_code, formula_code, selected_target_codes, selected_emperors)
    clusters = fetch_rows(
        cur,
        with_cte
        + """
        select
            c.target_id,
            rt.target_code,
            rt.emperor_name,
            c.item_code,
            c.rule_code,
            c.formula_code,
            c.positive_signal::text as positive_signal,
            c.negative_signal::text as negative_signal,
            c.scored_judgment_count,
            c.supporting_judgment_count,
            c.excluded_judgment_count,
            c.object_side_scores,
            c.calc_detail,
            c.review_status::text as review_status
          from retrieval_v2.target_rule_score_clusters c
          join retrieval_v2.retrieval_targets rt on rt.id = c.target_id
          join scoped_targets st on st.id = c.target_id
         where c.item_code = %s
           and (%s = '' or c.rule_code = %s)
           and c.formula_code = %s
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.target_code = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
         order by rt.target_code
        """,
        params,
    )
    material_rows = fetch_rows(
        cur,
        with_cte
        + """
        select
            rt.target_code,
            rt.emperor_name,
            ms.factor_judgment_id,
            ms.binding_id,
            b.binding_code,
            ms.claim_id,
            mc.claim_code,
            mc.claim_summary,
            mc.object_name as claim_object_name,
            mc.direction as claim_direction,
            j.side::text as judgment_side,
            b.predicate,
            b.direction as binding_direction,
            b.object_role,
            ms.object_id,
            ms.target_object_id,
            coalesce(o.canonical_name, mc.object_name) as object_name,
            ms.side::text as side,
            ms.raw_score::text as raw_score,
            ms.abs_score::text as abs_score,
            ms.factor_values,
            coalesce(fc.factor_choices, '[]'::jsonb) as factor_choices,
            coalesce(ev.passages, '[]'::jsonb) as passages
          from retrieval_v2.claim_rule_binding_material_scores ms
          join retrieval_v2.retrieval_targets rt on rt.id = ms.target_id
          join scoped_targets st on st.id = ms.target_id
          join retrieval_v2.claim_rule_binding_factor_judgments j on j.id = ms.factor_judgment_id
          join retrieval_v2.claim_rule_bindings b on b.id = ms.binding_id
          join retrieval_v2.material_claims mc on mc.id = ms.claim_id
          left join retrieval_v2.objects o on o.id = ms.object_id
          left join lateral (
                select jsonb_agg(
                    jsonb_build_object(
                        'factor_name', c.factor_name,
                        'option_code', c.option_code,
                        'option_label', c.option_label,
                        'value_num', c.value_num::text
                    )
                    order by c.factor_name
                ) as factor_choices
                  from retrieval_v2.claim_rule_binding_factor_choices c
                 where c.factor_judgment_id = ms.factor_judgment_id
          ) fc on true
          left join lateral (
                select jsonb_agg(
                    jsonb_build_object(
                        'source_title', sd.source_title,
                        'title', sd.title,
                        'locator', spg.locator,
                        'passage_code', spg.passage_code,
                        'quote', left(spg.raw_text, 220)
                    )
                    order by csp.id
                ) as passages
                  from retrieval_v2.claim_source_passages csp
                  join retrieval_v2.source_passages spg on spg.id = csp.source_passage_id
                  join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
                 where csp.claim_id = ms.claim_id
          ) ev on true
         where ms.item_code = %s
           and (%s = '' or ms.rule_code = %s)
           and ms.formula_code = %s
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.target_code = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
         order by rt.target_code, ms.side, ms.abs_score desc, ms.factor_judgment_id
        """,
        params,
    )
    materials_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in material_rows:
        material = normalize_material_score_row(row)
        materials_by_target.setdefault(material["target_code"], []).append(material)

    targets: list[dict[str, Any]] = []
    formula_params: dict[str, Any] = {}
    for row in clusters:
        target_materials = materials_by_target.get(text(row.get("target_code")), [])
        calc_detail = json_object(row.get("calc_detail"))
        if not formula_params:
            formula_params = json_object(calc_detail.get("formula_params"))
        target_entry = {
            "target_id": int(row.get("target_id") or 0),
            "target_code": text(row.get("target_code")),
            "emperor_name": text(row.get("emperor_name")),
            "item_code": text(row.get("item_code")),
            "rule_code": text(row.get("rule_code")),
            "formula_code": text(row.get("formula_code")),
            "positive_signal": decimal_text(row.get("positive_signal")),
            "negative_signal": decimal_text(row.get("negative_signal")),
            "scored_judgment_count": int(row.get("scored_judgment_count") or 0),
            "supporting_judgment_count": int(row.get("supporting_judgment_count") or 0),
            "excluded_judgment_count": int(row.get("excluded_judgment_count") or 0),
            "review_status": text(row.get("review_status")),
            "formula_params": json_object(calc_detail.get("formula_params")),
            "object_side_scores": object_side_summary(row, target_materials),
            "top_materials": top_materials(target_materials, top_materials_per_target),
            "materials": target_materials,
        }
        targets.append(target_entry)
    totals = {
        "targets": len(targets),
        "clusters": len(clusters),
        "material_scores": len(material_rows),
        "scored_judgments": sum(int(row.get("scored_judgment_count") or 0) for row in clusters),
        "supporting_judgments": sum(int(row.get("supporting_judgment_count") or 0) for row in clusters),
        "excluded_judgments": sum(int(row.get("excluded_judgment_count") or 0) for row in clusters),
    }
    observations = build_score_chain_observations(targets)
    totals["observations"] = sum(1 for row in observations if int(row.get("count") or 0) > 0)
    return {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "score-chain",
        "ok": True,
        "scope": {
            "item_code": item_code,
            "rule_code": rule_code,
            "formula_code": formula_code,
            "scope": scope,
            "target_code": target_code,
            "target_codes": selected_target_codes,
            "emperors": selected_emperors,
            "selectors": selector_payload["selectors"],
        },
        "render_options": {"top_materials_per_target": top_materials_per_target},
        "formula_params": formula_params,
        "observations": observations,
        "totals": totals,
        "targets": targets,
    }

