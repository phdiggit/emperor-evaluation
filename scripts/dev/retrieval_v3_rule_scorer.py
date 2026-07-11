from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_factorization_worklists import DEFAULT_FORMULA_CODE, DEFAULT_ITEM_CODE, DEFAULT_RULE_CODE  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import ImportPlanError, json_param  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor, table_label  # noqa: E402
from scripts.dev.retrieval_v3_score_lane import classify_score_lane  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
MATERIAL_SCORE_CAP = Decimal("4.0")
SAME_OBJECT_SECONDARY_FACTOR = Decimal("0.35")
SAME_OBJECT_CAP_MULTIPLIER = Decimal("1.5")
TEAM_CORE_CARRIER_MODE = "team_core_members"


class RetrievalV3RuleScorerError(ImportPlanError):
    pass


@dataclass(frozen=True)
class FactorChoice:
    factor_name: str
    option_label: str
    option_code: str
    value_num: Decimal


@dataclass(frozen=True)
class JudgmentInput:
    factor_judgment_id: int
    binding_id: int
    binding_code: str
    claim_id: int
    target_id: int
    target_code: str
    emperor_name: str
    source_pack_id: int
    item_code: str
    rule_code: str
    formula_code: str
    target_action: str
    side: str | None
    predicate: str
    object_role: str
    object_id: int | None
    target_object_id: int | None
    object_name: str
    choices: tuple[FactorChoice, ...]


@dataclass(frozen=True)
class MaterialScore:
    judgment: JudgmentInput
    score_side: str
    raw_score: Decimal
    abs_score: Decimal
    factor_values: dict[str, str]


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def quant(value: Decimal, places: str = "0.001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def decimal_value(value: Any, *, path: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - Decimal raises several small exception types
        raise RetrievalV3RuleScorerError(f"{path}: expected decimal value") from exc


def material_raw_score(choices: Sequence[FactorChoice]) -> Decimal:
    raw_score = Decimal("1")
    for choice in choices:
        raw_score *= choice.value_num
    return quant(raw_score)


def material_abs_score(raw_score: Decimal) -> Decimal:
    return quant(min(abs(raw_score), MATERIAL_SCORE_CAP))


def score_side_for_raw_score(raw_score: Decimal, fallback_side: str | None) -> str:
    normalized = text(fallback_side)
    if normalized == "negative":
        return "negative"
    if raw_score < 0:
        return "negative"
    if raw_score > 0:
        return "positive"
    if normalized == "positive":
        return normalized
    return "positive"


def appointment_effect_sign_issue(*, side: str | None, value: Decimal) -> str:
    if value == 0:
        return ""
    if side == "positive" and value < 0:
        return "positive side cannot use negative appointment_effect"
    if side == "negative" and value > 0:
        return "negative side cannot use positive appointment_effect"
    return ""


def validate_material_factor_signs(judgment: JudgmentInput) -> None:
    if judgment.rule_code != "appointment_delegation" or judgment.target_action != "score":
        return
    for choice in judgment.choices:
        if choice.factor_name != "appointment_effect":
            continue
        issue = appointment_effect_sign_issue(side=judgment.side, value=choice.value_num)
        if issue:
            raise RetrievalV3RuleScorerError(
                f"{judgment.binding_code}: {issue}: appointment_effect={choice.option_label}"
            )


def object_side_score(scores: Sequence[Decimal]) -> Decimal:
    if not scores:
        return Decimal("0.000")
    ordered = sorted(scores, reverse=True)
    strongest = ordered[0]
    total = strongest + SAME_OBJECT_SECONDARY_FACTOR * sum(ordered[1:], Decimal("0"))
    capped = min(total, strongest * SAME_OBJECT_CAP_MULTIPLIER, MATERIAL_SCORE_CAP)
    return quant(capped)


def side_signal(object_scores: Sequence[Decimal]) -> Decimal:
    if not object_scores:
        return Decimal("0.000")
    return quant(sum(object_scores, Decimal("0")))


def source_pack_predicate(
    source_pack_codes: Sequence[str] = (),
    supplemental_source_pack_codes: Sequence[str] = (),
) -> str:
    codes = [text(code) for code in source_pack_codes if text(code)]
    if codes:
        return "sp.pack_code = any(%s) and sp.coverage_status = 'passed'"
    supplemental = [text(code) for code in supplemental_source_pack_codes if text(code)]
    if supplemental:
        return """
           (
               sp.id in (
                    select distinct on (sp2.target_id, sp2.contract_id) sp2.id
                      from retrieval_v3.source_packs sp2
                     where sp2.status = 'accepted'
                       and sp2.coverage_status = 'passed'
                     order by sp2.target_id, sp2.contract_id, sp2.updated_at desc, sp2.id desc
               )
               or sp.pack_code = any(%s)
           )
           and sp.coverage_status = 'passed'
        """
    return """
           sp.id in (
                select distinct on (sp2.target_id, sp2.contract_id) sp2.id
                  from retrieval_v3.source_packs sp2
                 where sp2.status = 'accepted'
                   and sp2.coverage_status = 'passed'
                 order by sp2.target_id, sp2.contract_id, sp2.updated_at desc, sp2.id desc
           )
        """


def fetch_judgment_rows(
    cur: Any,
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    target_code: str,
    source_pack_codes: Sequence[str] = (),
    supplemental_source_pack_codes: Sequence[str] = (),
) -> list[dict[str, Any]]:
    target_filter = "and (%s = '' or rt.target_code = %s)"
    codes = [text(code) for code in source_pack_codes if text(code)]
    supplemental = [text(code) for code in supplemental_source_pack_codes if text(code)]
    source_pack_params: list[Any] = [codes or supplemental] if (codes or supplemental) else []
    cur.execute(
        f"""
        select
            j.id as factor_judgment_id,
            j.binding_id,
            b.binding_code,
            b.usable_for_scoring_cluster as binding_usable_for_scoring_cluster,
            b.binding_payload,
            cand.id as candidate_id,
            cand.candidate_code,
            cand.candidate_payload,
            j.claim_id,
            j.target_id,
            rt.target_code,
            rt.emperor_name,
            j.source_pack_id,
            j.item_code,
            j.rule_code,
            j.formula_code,
            j.target_action::text as target_action,
            j.side::text as side,
            b.predicate,
            b.object_role,
            mol.object_id,
            mol.target_object_id,
            o.canonical_name as object_name,
            c.factor_name,
            c.option_label,
            c.option_code,
            c.value_num::text as value_num,
            active.factor_option_id as active_factor_option_id,
            active.active_value::text as active_value_num
          from retrieval_v3.claim_rule_binding_factor_judgments j
          join retrieval_v3.claim_rule_bindings b on b.id = j.binding_id
          left join lateral (
              select c0.*
                from retrieval_v3.claim_rule_binding_candidates c0
               where c0.resolved_binding_id = b.id
                  or (
                      coalesce(b.binding_payload->>'candidate_id', '') ~ '^[0-9]+$'
                      and c0.id = (b.binding_payload->>'candidate_id')::bigint
                  )
               order by case when c0.resolved_binding_id = b.id then 0 else 1 end, c0.id
               limit 1
          ) cand on true
          join retrieval_v3.retrieval_targets rt on rt.id = j.target_id
          join retrieval_v3.source_packs sp on sp.id = j.source_pack_id
          left join lateral (
              select mol1.*
                from retrieval_v3.material_object_links mol1
               where mol1.claim_id = j.claim_id
                 and mol1.review_status = 'accepted'
                 and (
                      (
                          coalesce(b.binding_payload->>'promoted_material_object_link_id', '') ~ '^[0-9]+$'
                          and mol1.id = (b.binding_payload->>'promoted_material_object_link_id')::bigint
                      )
                      or (
                          not (coalesce(b.binding_payload->>'promoted_material_object_link_id', '') ~ '^[0-9]+$')
                          and mol1.role = b.object_role
                      )
                 )
               order by case
                   when coalesce(b.binding_payload->>'promoted_material_object_link_id', '') ~ '^[0-9]+$'
                    and mol1.id = (b.binding_payload->>'promoted_material_object_link_id')::bigint
                       then 0
                   else 1
               end,
               mol1.id
               limit 1
          ) mol on true
          left join retrieval_v3.objects o on o.id = mol.object_id
          left join retrieval_v3.claim_rule_binding_factor_choices c on c.factor_judgment_id = j.id
          left join lateral (
              select
                  o2.id as factor_option_id,
                  o2.value_num as active_value
                from retrieval_v3.eval_rule_factors f2
                join retrieval_v3.eval_rule_factor_options o2 on o2.factor_id = f2.id
               where f2.item_code = j.item_code
                 and f2.formula_code = j.formula_code
                 and f2.factor_name = c.factor_name
                 and f2.factor_status = 'active'
                 and f2.rule_code in (j.rule_code, '')
                 and o2.option_status = 'active'
                 and o2.label = c.option_label
               order by case when f2.rule_code = j.rule_code then 0 else 1 end, o2.id
               limit 1
          ) active on true
         where j.item_code = %s
           and j.rule_code = %s
          and j.formula_code = %s
           and j.review_status = 'accepted'
           and b.usable_for_scoring_cluster
           and not exists (
                select 1
                  from retrieval_v3.material_review_queue mrq
                 where mrq.claim_id = j.claim_id
                   and mrq.queue_status in ('ready', 'needs_review', 'running', 'blocked')
           )
           and {source_pack_predicate(codes, supplemental)}
           {target_filter}
         order by j.target_id, j.id, c.factor_name
        """,
        (item_code, rule_code, formula_code, *source_pack_params, target_code, target_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_scoring_target_rows(
    cur: Any,
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    target_code: str,
    source_pack_codes: Sequence[str] = (),
    supplemental_source_pack_codes: Sequence[str] = (),
) -> list[dict[str, Any]]:
    target_filter = "and (%s = '' or rt.target_code = %s)"
    codes = [text(code) for code in source_pack_codes if text(code)]
    supplemental = [text(code) for code in supplemental_source_pack_codes if text(code)]
    source_pack_params: list[Any] = [codes or supplemental] if (codes or supplemental) else []
    cur.execute(
        f"""
        select distinct
            rt.id as target_id,
            rt.target_code,
            rt.emperor_name,
            rt.item_code
          from retrieval_v3.retrieval_targets rt
          join retrieval_v3.source_packs sp on sp.target_id = rt.id
         where (%s = '' or rt.item_code = %s)
           and {source_pack_predicate(codes, supplemental)}
           {target_filter}
         order by rt.emperor_name, rt.target_code
        """,
        (item_code, item_code, *source_pack_params, target_code, target_code),
    )
    rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["rule_code"] = rule_code
        row["formula_code"] = formula_code
    return rows


def fetch_alternate_formula_counts(
    cur: Any,
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    target_code: str,
    source_pack_codes: Sequence[str] = (),
    supplemental_source_pack_codes: Sequence[str] = (),
) -> list[dict[str, Any]]:
    target_filter = "and (%s = '' or rt.target_code = %s)"
    codes = [text(code) for code in source_pack_codes if text(code)]
    supplemental = [text(code) for code in supplemental_source_pack_codes if text(code)]
    source_pack_params: list[Any] = [codes or supplemental] if (codes or supplemental) else []
    cur.execute(
        f"""
        select
            j.formula_code,
            count(distinct j.id) as judgment_count,
            count(distinct rt.id) as target_count
          from retrieval_v3.claim_rule_binding_factor_judgments j
          join retrieval_v3.retrieval_targets rt on rt.id = j.target_id
          join retrieval_v3.source_packs sp on sp.id = j.source_pack_id
         where j.item_code = %s
           and j.rule_code = %s
           and j.formula_code <> %s
           and j.review_status = 'accepted'
           and {source_pack_predicate(codes, supplemental)}
           {target_filter}
         group by j.formula_code
         order by j.formula_code
        """,
        (item_code, rule_code, formula_code, *source_pack_params, target_code, target_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_material_policy(cur: Any, *, item_code: str, rule_code: str) -> dict[str, Any]:
    cur.execute(
        """
        select
            id,
            policy_code,
            selection_priority,
            carrier_mode,
            material_source,
            policy_payload
          from retrieval_v3.eval_rule_material_policies
         where item_code = %s
           and rule_code = %s
           and policy_status = 'active'
         order by selection_priority, id
         limit 1
        """,
        (item_code, rule_code),
    )
    rows = [dict(row) for row in cur.fetchall()]
    if not rows:
        raise RetrievalV3RuleScorerError(f"{item_code}/{rule_code}: missing active material policy")
    return rows[0]


def validate_appointment_delegation_scoring_gate_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    checked: set[int] = set()
    issues: list[str] = []
    for row in rows:
        if text(row.get("rule_code")) != "appointment_delegation" or text(row.get("target_action")) != "score":
            continue
        judgment_id = int(row["factor_judgment_id"])
        if judgment_id in checked:
            continue
        checked.add(judgment_id)
        binding_code = text(row.get("binding_code"))
        decision = classify_score_lane(row)
        if decision.reason == "binding_not_scoring":
            issues.append(f"{binding_code}: binding usable_for_scoring_cluster=false")
        elif decision.reason == "identity_not_ready":
            issues.append(f"{binding_code}: accepted identity anchor is missing")
        elif decision.reason == "missing_candidate_payload":
            issues.append(f"{binding_code}: missing candidate_payload")
        elif decision.reason == "candidate_not_scoring":
            candidate_code = text(row.get("candidate_code"))
            suffix = f" candidate={candidate_code}" if candidate_code else ""
            issues.append(f"{binding_code}: candidate_payload is not scoring_candidate{suffix}")
    if issues:
        raise RetrievalV3RuleScorerError("appointment_delegation scoring gate violations: " + "; ".join(issues[:20]))


def build_judgments(rows: Sequence[Mapping[str, Any]]) -> list[JudgmentInput]:
    validate_appointment_delegation_scoring_gate_rows(rows)
    grouped: dict[int, dict[str, Any]] = {}
    choices_by_judgment: dict[int, list[FactorChoice]] = defaultdict(list)
    for row in rows:
        judgment_id = int(row["factor_judgment_id"])
        grouped.setdefault(judgment_id, dict(row))
        factor_name = text(row.get("factor_name"))
        if factor_name:
            if row.get("active_factor_option_id") is None:
                raise RetrievalV3RuleScorerError(
                    f"{row.get('binding_code')}: stale or unknown factor option {factor_name}={row.get('option_label')}"
                )
            value_num = decimal_value(row.get("value_num"), path=f"{judgment_id}.{factor_name}.value_num")
            active_value = decimal_value(row.get("active_value_num"), path=f"{judgment_id}.{factor_name}.active_value_num")
            if value_num != active_value:
                raise RetrievalV3RuleScorerError(
                    f"{row.get('binding_code')}: stale factor value {factor_name}={row.get('option_label')} "
                    f"judgment={value_num} active={active_value}"
                )
            choices_by_judgment[judgment_id].append(
                FactorChoice(
                    factor_name=factor_name,
                    option_label=text(row.get("option_label")),
                    option_code=text(row.get("option_code")),
                    value_num=value_num,
                )
            )
    judgments: list[JudgmentInput] = []
    for judgment_id, row in grouped.items():
        target_action = text(row.get("target_action"))
        side = text(row.get("side")) or None
        object_id = row.get("object_id")
        target_object_id = row.get("target_object_id")
        choices = tuple(sorted(choices_by_judgment.get(judgment_id, []), key=lambda item: item.factor_name))
        if target_action == "score":
            if side not in {"positive", "negative"}:
                raise RetrievalV3RuleScorerError(f"{row.get('binding_code')}: score judgment missing side")
            if object_id is None:
                raise RetrievalV3RuleScorerError(f"{row.get('binding_code')}: score judgment missing role-matched object link")
            if not choices:
                raise RetrievalV3RuleScorerError(f"{row.get('binding_code')}: score judgment has no factor choices")
        judgments.append(
            JudgmentInput(
                factor_judgment_id=judgment_id,
                binding_id=int(row["binding_id"]),
                binding_code=text(row.get("binding_code")),
                claim_id=int(row["claim_id"]),
                target_id=int(row["target_id"]),
                target_code=text(row.get("target_code")),
                emperor_name=text(row.get("emperor_name")),
                source_pack_id=int(row["source_pack_id"]),
                item_code=text(row.get("item_code")),
                rule_code=text(row.get("rule_code")),
                formula_code=text(row.get("formula_code")),
                target_action=target_action,
                side=side,
                predicate=text(row.get("predicate")),
                object_role=text(row.get("object_role")),
                object_id=int(object_id) if object_id is not None else None,
                target_object_id=int(target_object_id) if target_object_id is not None else None,
                object_name=text(row.get("object_name")) or text(row.get("binding_code")),
                choices=choices,
            )
        )
    return sorted(judgments, key=lambda item: (item.target_id, item.factor_judgment_id))


def score_material(judgment: JudgmentInput) -> MaterialScore:
    validate_material_factor_signs(judgment)
    raw_score = material_raw_score(judgment.choices)
    return MaterialScore(
        judgment=judgment,
        score_side=score_side_for_raw_score(raw_score, judgment.side),
        raw_score=raw_score,
        abs_score=material_abs_score(raw_score),
        factor_values={choice.factor_name: str(choice.value_num) for choice in judgment.choices},
    )


def choice_by_factor(judgment: JudgmentInput) -> dict[str, FactorChoice]:
    return {choice.factor_name: choice for choice in judgment.choices}


def require_choice(judgment: JudgmentInput, factor_name: str) -> FactorChoice:
    choices = choice_by_factor(judgment)
    if factor_name not in choices:
        raise RetrievalV3RuleScorerError(f"{judgment.binding_code}: missing {factor_name}")
    return choices[factor_name]


def compute_team_building_cluster(judgments: Sequence[JudgmentInput]) -> dict[str, Any]:
    if not judgments:
        raise RetrievalV3RuleScorerError("team_building cluster requires at least one judgment")
    scored = [judgment for judgment in judgments if judgment.target_action == "score"]
    action_counts = Counter(judgment.target_action for judgment in judgments)
    role_values: set[Decimal] = set()
    role_refs: dict[str, Any] = {}
    stability_values: set[Decimal] = set()
    stability_refs: dict[str, Any] = {}
    candidates: dict[str, dict[str, Any]] = {}
    duplicate_team_objects: list[dict[str, Any]] = []

    for judgment in scored:
        talent = require_choice(judgment, "talent_quality_factor")
        role = require_choice(judgment, "role_complementarity_factor")
        stability = require_choice(judgment, "long_term_stability_factor")
        role_values.add(role.value_num)
        role_refs = {"label": role.option_label, "option_code": role.option_code, "value_num": str(role.value_num)}
        stability_values.add(stability.value_num)
        stability_refs = {"label": stability.option_label, "option_code": stability.option_code, "value_num": str(stability.value_num)}
        object_key = str(judgment.object_id or judgment.binding_id)
        candidate = {
            "judgment": judgment,
            "object_key": object_key,
            "talent_quality_factor": talent.value_num,
            "talent_quality_ref": {"label": talent.option_label, "option_code": talent.option_code, "value_num": str(talent.value_num)},
        }
        current = candidates.get(object_key)
        if current is None:
            candidates[object_key] = candidate
            continue
        current_value = abs(current["talent_quality_factor"])
        candidate_value = abs(candidate["talent_quality_factor"])
        replace = candidate_value > current_value or (
            candidate_value == current_value
            and judgment.factor_judgment_id < current["judgment"].factor_judgment_id
        )
        kept = candidate if replace else current
        dropped = current if replace else candidate
        duplicate_team_objects.append(
            {
                "object_key": object_key,
                "kept_binding_code": kept["judgment"].binding_code,
                "dropped_binding_code": dropped["judgment"].binding_code,
                "reason": "same_team_object",
            }
        )
        if replace:
            candidates[object_key] = candidate

    if len(role_values) > 1:
        raise RetrievalV3RuleScorerError("team_building role_complementarity_factor must be consistent within target/rule cluster")
    if len(stability_values) > 1:
        raise RetrievalV3RuleScorerError("team_building long_term_stability_factor must be consistent within target/rule cluster")
    role_value = next(iter(role_values), Decimal("1.000"))
    stability_value = next(iter(stability_values), Decimal("1.000"))

    team_objects = sorted(
        candidates.values(),
        key=lambda item: (-abs(item["talent_quality_factor"]), item["judgment"].object_name, item["object_key"]),
    )
    material_scores: list[MaterialScore] = []
    team_object_components: list[dict[str, Any]] = []
    object_side_scores: dict[str, dict[str, Decimal]] = {"positive": {}, "negative": {}}
    for item in team_objects:
        judgment = item["judgment"]
        contribution = quant(item["talent_quality_factor"] * role_value * stability_value)
        side = "negative" if contribution < 0 else "positive"
        object_side_scores[side][item["object_key"]] = quant(abs(contribution))
        factor_values = {
            "talent_quality_factor": str(item["talent_quality_factor"]),
            "role_complementarity_factor": str(role_value),
            "long_term_stability_factor": str(stability_value),
        }
        material_scores.append(
            MaterialScore(
                judgment=judgment,
                score_side=side,
                raw_score=contribution,
                abs_score=quant(abs(contribution)),
                factor_values=factor_values,
            )
        )
        team_object_components.append(
            {
                "binding_code": judgment.binding_code,
                "claim_id": judgment.claim_id,
                "object_id": judgment.object_id,
                "target_object_id": judgment.target_object_id,
                "object_name": judgment.object_name,
                "talent_quality_factor": str(item["talent_quality_factor"]),
                "talent_quality_ref": item["talent_quality_ref"],
                "role_complementarity_factor": str(role_value),
                "long_term_stability_factor": str(stability_value),
                "object_contribution": str(contribution),
            }
        )

    positive_signal = side_signal(list(object_side_scores["positive"].values()))
    negative_signal = side_signal(list(object_side_scores["negative"].values()))
    calc_detail = {
        "item_code": judgments[0].item_code,
        "formula_code": judgments[0].formula_code,
        "team_formula": "sum(positive object_contribution) and sum(abs(negative object_contribution)); object_contribution = talent_quality_factor * role_complementarity_factor * long_term_stability_factor",
        "team_object_components": team_object_components,
        "duplicate_team_objects": duplicate_team_objects,
        "team_factor_values": {
            "role_complementarity_factor": str(role_value),
            "long_term_stability_factor": str(stability_value),
        },
        "team_factor_refs": {
            "role_complementarity_factor": role_refs,
            "long_term_stability_factor": stability_refs,
        },
        "materials": [material_detail(score) for score in material_scores],
        "object_side_scores": {
            side: {
                object_key: {"object_name": next((score.judgment.object_name for score in material_scores if str(score.judgment.object_id or score.judgment.binding_id) == object_key), object_key), "score": str(score)}
                for object_key, score in side_scores.items()
            }
            for side, side_scores in object_side_scores.items()
        },
        "covered_factor_judgment_ids": [judgment.factor_judgment_id for judgment in judgments],
        "scored_factor_judgment_ids": [score.judgment.factor_judgment_id for score in material_scores],
        "supporting_factor_judgment_ids": [
            judgment.factor_judgment_id for judgment in judgments if judgment.target_action == "supporting_only"
        ],
        "excluded_factor_judgment_ids": [judgment.factor_judgment_id for judgment in judgments if judgment.target_action == "exclude"],
        "raw_action_counts": dict(action_counts),
        "positive_signal": str(positive_signal),
        "negative_signal": str(negative_signal),
    }
    return {
        "target_id": judgments[0].target_id,
        "target_code": judgments[0].target_code,
        "emperor_name": judgments[0].emperor_name,
        "item_code": judgments[0].item_code,
        "rule_code": judgments[0].rule_code,
        "formula_code": judgments[0].formula_code,
        "positive_signal": positive_signal,
        "negative_signal": negative_signal,
        "action_counts": dict(action_counts),
        "material_scores": material_scores,
        "object_side_scores": object_side_scores,
        "calc_detail": calc_detail,
    }


def group_by_target(judgments: Sequence[JudgmentInput]) -> dict[int, list[JudgmentInput]]:
    grouped: dict[int, list[JudgmentInput]] = defaultdict(list)
    for judgment in judgments:
        grouped[judgment.target_id].append(judgment)
    return dict(sorted(grouped.items()))


def material_detail(score: MaterialScore) -> dict[str, Any]:
    judgment = score.judgment
    capped = abs(score.raw_score) > score.abs_score
    return {
        "factor_judgment_id": judgment.factor_judgment_id,
        "binding_code": judgment.binding_code,
        "claim_id": judgment.claim_id,
        "object_id": judgment.object_id,
        "target_object_id": judgment.target_object_id,
        "object_role": judgment.object_role,
        "predicate": judgment.predicate,
        "object_name": judgment.object_name,
        "side": score.score_side,
        "judgment_side": judgment.side,
        "raw_score": str(score.raw_score),
        "abs_score": str(score.abs_score),
        "capped": capped,
        "material_score_cap": str(MATERIAL_SCORE_CAP) if capped else "",
        "factor_values": score.factor_values,
        "factor_refs": {
            choice.factor_name: {
                "label": choice.option_label,
                "option_code": choice.option_code,
                "value_num": str(choice.value_num),
            }
            for choice in score.judgment.choices
        },
    }


def material_dedup_key(score: MaterialScore) -> tuple[int, int | None, str]:
    judgment = score.judgment
    return (judgment.claim_id, judgment.object_id, score.score_side)


def dedupe_material_scores(scores: Sequence[MaterialScore]) -> tuple[list[MaterialScore], list[dict[str, Any]]]:
    grouped: dict[tuple[int, int | None, str], list[MaterialScore]] = defaultdict(list)
    for score in scores:
        grouped[material_dedup_key(score)].append(score)
    kept: list[MaterialScore] = []
    deduped: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        if len(rows) == 1:
            kept.append(rows[0])
            continue
        ordered = sorted(rows, key=lambda item: (-item.abs_score, item.judgment.factor_judgment_id))
        winner = ordered[0]
        kept.append(winner)
        claim_id, object_id, side = key
        for loser in ordered[1:]:
            deduped.append(
                {
                    "factor_judgment_id": loser.judgment.factor_judgment_id,
                    "binding_id": loser.judgment.binding_id,
                    "binding_code": loser.judgment.binding_code,
                    "claim_id": claim_id,
                    "object_id": object_id,
                    "object_name": loser.judgment.object_name,
                    "side": side,
                    "predicate": loser.judgment.predicate,
                    "object_role": loser.judgment.object_role,
                    "dedupe_key": {
                        "claim_id": claim_id,
                        "object_id": object_id,
                        "side": side,
                    },
                    "kept_factor_judgment_id": winner.judgment.factor_judgment_id,
                    "kept_binding_id": winner.judgment.binding_id,
                    "kept_binding_code": winner.judgment.binding_code,
                    "kept_predicate": winner.judgment.predicate,
                    "kept_object_role": winner.judgment.object_role,
                    "reason": "same_claim_object_side",
                }
            )
    return sorted(kept, key=lambda item: item.judgment.factor_judgment_id), sorted(
        deduped, key=lambda item: int(item["factor_judgment_id"])
    )


def compute_target_cluster(
    judgments: Sequence[JudgmentInput],
    *,
    material_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not judgments:
        raise RetrievalV3RuleScorerError("target cluster requires at least one judgment")
    carrier_mode = text((material_policy or {}).get("carrier_mode"))
    if carrier_mode == TEAM_CORE_CARRIER_MODE:
        return compute_team_building_cluster(judgments)
    raw_material_scores = [score_material(judgment) for judgment in judgments if judgment.target_action == "score"]
    material_scores, deduped_material_scores = dedupe_material_scores(raw_material_scores)
    grouped_scores: dict[str, dict[str, list[Decimal]]] = {"positive": defaultdict(list), "negative": defaultdict(list)}
    object_names: dict[str, str] = {}
    for score in material_scores:
        judgment = score.judgment
        side = score.score_side
        object_key = str(judgment.object_id)
        grouped_scores[side][object_key].append(score.abs_score)
        object_names[object_key] = judgment.object_name

    object_side_scores = {
        side: {object_key: object_side_score(scores) for object_key, scores in side_scores.items()}
        for side, side_scores in grouped_scores.items()
    }
    positive_signal = side_signal(list(object_side_scores["positive"].values()))
    negative_signal = side_signal(list(object_side_scores["negative"].values()))
    raw_action_counts = Counter(judgment.target_action for judgment in judgments)
    action_counts = Counter(raw_action_counts)
    action_counts["score"] = len(material_scores)
    calc_detail = {
        "item_code": judgments[0].item_code,
        "rule_code": judgments[0].rule_code,
        "formula_code": judgments[0].formula_code,
        "formula_params": {
            "material_score_cap": str(MATERIAL_SCORE_CAP),
            "same_object_secondary_factor": str(SAME_OBJECT_SECONDARY_FACTOR),
            "same_object_cap_multiplier": str(SAME_OBJECT_CAP_MULTIPLIER),
            "rule_side_aggregation": "sum_object_side_scores",
            "coverage": {"positive": "1.0", "negative": "1.0"},
        },
        "materials": [material_detail(score) for score in material_scores],
        "deduped_material_scores": deduped_material_scores,
        "object_side_scores": {
            side: {
                object_key: {"object_name": object_names.get(object_key, object_key), "score": str(score)}
                for object_key, score in side_scores.items()
            }
            for side, side_scores in object_side_scores.items()
        },
        "covered_factor_judgment_ids": [judgment.factor_judgment_id for judgment in judgments],
        "scored_factor_judgment_ids": [score.judgment.factor_judgment_id for score in material_scores],
        "deduped_factor_judgment_ids": [int(row["factor_judgment_id"]) for row in deduped_material_scores],
        "raw_action_counts": dict(raw_action_counts),
        "supporting_factor_judgment_ids": [
            judgment.factor_judgment_id for judgment in judgments if judgment.target_action == "supporting_only"
        ],
        "excluded_factor_judgment_ids": [judgment.factor_judgment_id for judgment in judgments if judgment.target_action == "exclude"],
        "positive_signal": str(positive_signal),
        "negative_signal": str(negative_signal),
    }
    return {
        "target_id": judgments[0].target_id,
        "target_code": judgments[0].target_code,
        "emperor_name": judgments[0].emperor_name,
        "item_code": judgments[0].item_code,
        "rule_code": judgments[0].rule_code,
        "formula_code": judgments[0].formula_code,
        "positive_signal": positive_signal,
        "negative_signal": negative_signal,
        "action_counts": dict(action_counts),
        "material_scores": material_scores,
        "object_side_scores": object_side_scores,
        "calc_detail": calc_detail,
    }


def empty_target_cluster(target: Mapping[str, Any], *, rule_code: str, formula_code: str) -> dict[str, Any]:
    calc_detail = {
        "item_code": text(target.get("item_code")),
        "rule_code": rule_code,
        "formula_code": formula_code,
        "formula_params": {
            "material_score_cap": str(MATERIAL_SCORE_CAP),
            "same_object_secondary_factor": str(SAME_OBJECT_SECONDARY_FACTOR),
            "same_object_cap_multiplier": str(SAME_OBJECT_CAP_MULTIPLIER),
            "rule_side_aggregation": "sum_object_side_scores",
            "coverage": {"positive": "1.0", "negative": "1.0"},
        },
        "materials": [],
        "deduped_material_scores": [],
        "object_side_scores": {"positive": {}, "negative": {}},
        "covered_factor_judgment_ids": [],
        "scored_factor_judgment_ids": [],
        "deduped_factor_judgment_ids": [],
        "raw_action_counts": {},
        "supporting_factor_judgment_ids": [],
        "excluded_factor_judgment_ids": [],
        "positive_signal": "0",
        "negative_signal": "0",
        "empty_reason": "no_usable_factor_judgments",
    }
    return {
        "target_id": int(target["target_id"]),
        "target_code": text(target.get("target_code")),
        "emperor_name": text(target.get("emperor_name")),
        "item_code": text(target.get("item_code")),
        "rule_code": rule_code,
        "formula_code": formula_code,
        "positive_signal": Decimal("0"),
        "negative_signal": Decimal("0"),
        "action_counts": {"score": 0, "supporting_only": 0, "exclude": 0},
        "material_scores": [],
        "object_side_scores": {"positive": {}, "negative": {}},
        "calc_detail": calc_detail,
    }


def material_score_idem_key(judgment: JudgmentInput) -> str:
    return "|".join([judgment.binding_code, judgment.formula_code, "material_score"])


def rule_score_idem_key(cluster: Mapping[str, Any]) -> str:
    return "|".join([text(cluster.get("target_code")), text(cluster.get("rule_code")), text(cluster.get("formula_code")), "rule_score"])


def upsert_material_score(cur: Any, score: MaterialScore) -> None:
    judgment = score.judgment
    idem_key = material_score_idem_key(judgment)
    payload = {
        "source": "retrieval_v3_rule_scorer",
        "binding_code": judgment.binding_code,
        "object_name": judgment.object_name,
        "judgment_side": judgment.side,
        "score_side": score.score_side,
        "factor_values": score.factor_values,
    }
    cur.execute(
        """
        insert into retrieval_v3.claim_rule_binding_material_scores (
            material_score_code, idem_key, factor_judgment_id, binding_id, claim_id,
            target_id, source_pack_id, object_id, target_object_id, item_code,
            rule_code, formula_code, side, raw_score, abs_score, factor_values,
            score_payload
        )
        values (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s::retrieval_v3.rv3_factor_side, %s, %s, %s::jsonb,
            %s::jsonb
        )
        on conflict on constraint rv3_claim_rule_binding_material_scores_idem_uk do update set
            object_id = excluded.object_id,
            target_object_id = excluded.target_object_id,
            side = excluded.side,
            raw_score = excluded.raw_score,
            abs_score = excluded.abs_score,
            factor_values = excluded.factor_values,
            score_payload = excluded.score_payload,
            updated_at = now()
        """,
        (
            "RV3MS-" + stable_hash(idem_key, length=16),
            idem_key,
            judgment.factor_judgment_id,
            judgment.binding_id,
            judgment.claim_id,
            judgment.target_id,
            judgment.source_pack_id,
            judgment.object_id,
            judgment.target_object_id,
            judgment.item_code,
            judgment.rule_code,
            judgment.formula_code,
            score.score_side,
            score.raw_score,
            score.abs_score,
            json_param(score.factor_values),
            json_param(payload),
        ),
    )


def delete_obsolete_material_scores(cur: Any, *, cluster: Mapping[str, Any]) -> int:
    material_scores = list(cluster.get("material_scores") or [])
    scored_ids = [score.judgment.factor_judgment_id for score in material_scores if isinstance(score, MaterialScore)]
    if scored_ids:
        cur.execute(
            """
            delete from retrieval_v3.claim_rule_binding_material_scores
             where target_id = %s
               and item_code = %s
               and rule_code = %s
               and formula_code = %s
               and not (factor_judgment_id = any(%s))
            """,
            (
                int(cluster["target_id"]),
                text(cluster.get("item_code")),
                text(cluster.get("rule_code")),
                text(cluster.get("formula_code")),
                scored_ids,
            ),
        )
    else:
        cur.execute(
            """
            delete from retrieval_v3.claim_rule_binding_material_scores
             where target_id = %s
               and item_code = %s
               and rule_code = %s
               and formula_code = %s
            """,
            (
                int(cluster["target_id"]),
                text(cluster.get("item_code")),
                text(cluster.get("rule_code")),
                text(cluster.get("formula_code")),
            ),
        )
    return int(getattr(cur, "rowcount", 0) or 0)


def upsert_rule_score_cluster(cur: Any, cluster: Mapping[str, Any]) -> None:
    idem_key = rule_score_idem_key(cluster)
    action_counts = cluster.get("action_counts") or {}
    object_side_scores = {
        side: {object_id: str(score) for object_id, score in scores.items()}
        for side, scores in (cluster.get("object_side_scores") or {}).items()
    }
    cur.execute(
        """
        insert into retrieval_v3.target_rule_score_clusters (
            rule_score_code, idem_key, target_id, item_code, rule_code, formula_code,
            positive_signal, negative_signal, scored_judgment_count, supporting_judgment_count,
            excluded_judgment_count, object_side_scores, calc_detail, review_status
        )
        values (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s::jsonb, %s::jsonb, %s::retrieval_v3.rv3_review_status
        )
        on conflict on constraint rv3_target_rule_score_clusters_idem_uk do update set
            positive_signal = excluded.positive_signal,
            negative_signal = excluded.negative_signal,
            scored_judgment_count = excluded.scored_judgment_count,
            supporting_judgment_count = excluded.supporting_judgment_count,
            excluded_judgment_count = excluded.excluded_judgment_count,
            object_side_scores = excluded.object_side_scores,
            calc_detail = excluded.calc_detail,
            review_status = excluded.review_status,
            updated_at = now()
        """,
        (
            "RV3RS-" + stable_hash(idem_key, length=16),
            idem_key,
            int(cluster["target_id"]),
            text(cluster.get("item_code")),
            text(cluster.get("rule_code")),
            text(cluster.get("formula_code")),
            cluster["positive_signal"],
            cluster["negative_signal"],
            int(action_counts.get("score", 0)),
            int(action_counts.get("supporting_only", 0)),
            int(action_counts.get("exclude", 0)),
            json_param(object_side_scores),
            json_param(cluster.get("calc_detail") or {}),
            "accepted",
        ),
    )


def apply_rule_scores(
    *,
    dsn: str,
    schema_name: str = DEFAULT_PG_SCHEMA,
    item_code: str,
    rule_code: str,
    formula_code: str,
    target_code: str = "",
    source_pack_codes: Sequence[str] = (),
    supplemental_source_pack_codes: Sequence[str] = (),
    allow_source_pack_execute: bool = False,
    execute: bool,
) -> dict[str, Any]:
    source_pack_codes = tuple(text(code) for code in source_pack_codes if text(code))
    supplemental_source_pack_codes = tuple(text(code) for code in supplemental_source_pack_codes if text(code))
    if source_pack_codes and supplemental_source_pack_codes:
        raise RetrievalV3RuleScorerError("explicit and supplemental source-pack scopes cannot be combined")
    if execute and (source_pack_codes or supplemental_source_pack_codes) and not allow_source_pack_execute:
        raise RetrievalV3RuleScorerError(
            "explicit source-pack scoring is dry-run by default; pass --allow-source-pack-execute to write DB"
        )
    psycopg, dict_row = import_psycopg()
    counts: Counter[str] = Counter()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            material_policy = fetch_material_policy(cur, item_code=item_code, rule_code=rule_code)
            judgments = build_judgments(
                fetch_judgment_rows(
                    cur,
                    item_code=item_code,
                    rule_code=rule_code,
                    formula_code=formula_code,
                    target_code=target_code,
                    source_pack_codes=source_pack_codes,
                    supplemental_source_pack_codes=supplemental_source_pack_codes,
                )
            )
            scoring_targets = fetch_scoring_target_rows(
                cur,
                item_code=item_code,
                rule_code=rule_code,
                formula_code=formula_code,
                target_code=target_code,
                source_pack_codes=source_pack_codes,
                supplemental_source_pack_codes=supplemental_source_pack_codes,
            )
            if not judgments:
                alternates = fetch_alternate_formula_counts(
                    cur,
                    item_code=item_code,
                    rule_code=rule_code,
                    formula_code=formula_code,
                    target_code=target_code,
                    source_pack_codes=source_pack_codes,
                    supplemental_source_pack_codes=supplemental_source_pack_codes,
                )
                if alternates:
                    available = ", ".join(
                        f"{text(row.get('formula_code'))}({row.get('judgment_count')} judgments/{row.get('target_count')} targets)"
                        for row in alternates
                    )
                    raise RetrievalV3RuleScorerError(
                        f"no accepted factor judgments for formula_code={formula_code}; available formula judgments: {available}"
                    )
            clusters = [
                compute_target_cluster(rows, material_policy=material_policy)
                for rows in group_by_target(judgments).values()
            ]
            clustered_target_ids = {int(cluster["target_id"]) for cluster in clusters}
            clusters.extend(
                empty_target_cluster(target, rule_code=rule_code, formula_code=formula_code)
                for target in scoring_targets
                if int(target["target_id"]) not in clustered_target_ids
            )
            for cluster in clusters:
                delete_obsolete_material_scores(cur, cluster=cluster)
                for score in cluster.get("material_scores") or []:
                    upsert_material_score(cur, score)
                    counts[table_label("claim_rule_binding_material_scores", schema_name=schema_name)] += 1
                upsert_rule_score_cluster(cur, cluster)
                counts[table_label("target_rule_score_clusters", schema_name=schema_name)] += 1
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "generated_by": "scripts/dev/retrieval_v3_rule_scorer.py",
        "command": "apply",
        "write_db": execute,
        "executed": execute,
        "ok": True,
        "item_code": item_code,
        "rule_code": rule_code,
        "formula_code": formula_code,
        "target_code": target_code,
        "source_pack_codes": list(source_pack_codes),
        "supplemental_source_pack_codes": list(supplemental_source_pack_codes),
        "material_policy": {
            "policy_code": text(material_policy.get("policy_code")),
            "selection_priority": material_policy.get("selection_priority"),
            "carrier_mode": text(material_policy.get("carrier_mode")),
            "material_source": text(material_policy.get("material_source")),
        },
        "applied_counts": dict(sorted(counts.items())),
        "totals": {
            "targets": len(clusters),
            "judgments": len(judgments),
            "material_scores": sum(len(cluster.get("material_scores") or []) for cluster in clusters),
            "deduped_material_scores": sum(
                len((cluster.get("calc_detail") or {}).get("deduped_material_scores") or []) for cluster in clusters
            ),
        },
        "clusters": [
            {
                "target_code": cluster["target_code"],
                "emperor_name": cluster["emperor_name"],
                "positive_signal": str(cluster["positive_signal"]),
                "negative_signal": str(cluster["negative_signal"]),
                "action_counts": cluster["action_counts"],
                "material_scores": len(cluster.get("material_scores") or []),
                "deduped_material_scores": len((cluster.get("calc_detail") or {}).get("deduped_material_scores") or []),
            }
            for cluster in clusters
        ],
        "detailed_clusters": [
            {
                "target_id": cluster["target_id"],
                "target_code": cluster["target_code"],
                "emperor_name": cluster["emperor_name"],
                "item_code": cluster["item_code"],
                "rule_code": cluster["rule_code"],
                "formula_code": cluster["formula_code"],
                "positive_signal": str(cluster["positive_signal"]),
                "negative_signal": str(cluster["negative_signal"]),
                "action_counts": cluster["action_counts"],
                "material_scores": len(cluster.get("material_scores") or []),
                "deduped_material_scores": len((cluster.get("calc_detail") or {}).get("deduped_material_scores") or []),
                "calc_detail": cluster.get("calc_detail") or {},
            }
            for cluster in clusters
        ],
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 rule scorer report",
        "",
        f"- command: `{payload.get('command', '')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db', False)).lower()}`",
        f"- executed: `{str(payload.get('executed', False)).lower()}`",
        f"- item_code: `{payload.get('item_code', '')}`",
        f"- rule_code: `{payload.get('rule_code', '')}`",
        f"- formula_code: `{payload.get('formula_code', '')}`",
        f"- target_code: `{payload.get('target_code', '')}`",
        f"- source_pack_codes: `{', '.join(payload.get('source_pack_codes') or [])}`",
        "",
    ]
    totals = payload.get("totals")
    if isinstance(totals, Mapping):
        lines.extend(["## Totals", "", "| key | value |", "| --- | ---: |"])
        for key, value in totals.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    clusters = payload.get("clusters")
    if isinstance(clusters, list) and clusters:
        lines.extend(["## Clusters", "", "| target | emperor | positive | negative | material_scores |", "| --- | --- | ---: | ---: | ---: |"])
        for cluster in clusters:
            lines.append(
                f"| `{cluster.get('target_code')}` | {cluster.get('emperor_name')} | "
                f"{cluster.get('positive_signal')} | {cluster.get('negative_signal')} | {cluster.get('material_scores')} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(output_json: Path, output_md: Path | None, payload: Mapping[str, Any]) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(markdown_report(payload), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate retrieval_v3 rule score clusters; dry-run unless --execute.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Calculate and optionally write target rule score clusters.")
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    apply.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    apply.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    apply.add_argument("--rule-code", default=DEFAULT_RULE_CODE)
    apply.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE)
    apply.add_argument("--target-code", default="")
    apply.add_argument("--source-pack-code", action="append", default=[], help="Restrict scoring to explicit source pack code. Repeatable; dry-run by default for safety.")
    apply.add_argument(
        "--supplemental-source-pack-code",
        action="append",
        default=[],
        help="Add reviewed supplemental packs to the latest accepted primary packs. Repeatable; dry-run by default.",
    )
    apply.add_argument("--allow-source-pack-execute", action="store_true", help="Allow --execute with --source-pack-code, which writes formal score tables.")
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path)
    apply.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    if args.command != "apply":
        raise RetrievalV3RuleScorerError(f"unsupported command: {args.command}")
    payload = apply_rule_scores(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        item_code=args.item_code,
        rule_code=args.rule_code,
        formula_code=args.formula_code,
        target_code=args.target_code,
        source_pack_codes=args.source_pack_code,
        supplemental_source_pack_codes=args.supplemental_source_pack_code,
        allow_source_pack_execute=args.allow_source_pack_execute,
        execute=args.execute,
    )
    write_report(args.output_json, args.output_md, payload)
    print(json.dumps({"ok": payload["ok"], "command": args.command, "output_json": str(args.output_json)}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
