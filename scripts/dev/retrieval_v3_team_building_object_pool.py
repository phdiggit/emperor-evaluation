from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import write_json  # noqa: E402
from scripts.dev.retrieval_v3_rule_scorer import (  # noqa: E402
    DEFAULT_FORMULA_CODE,
    quant,
    side_signal,
    upsert_rule_score_cluster,
)


class TeamBuildingObjectPoolError(ValueError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def normalized_option_label(value: Any) -> str:
    return text(value).rstrip("。；;")


def read_factor_choices(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TeamBuildingObjectPoolError("team factor file must be an object")
    choices: dict[str, dict[str, str]] = {}
    for emperor, raw in payload.items():
        if not isinstance(raw, Mapping):
            raise TeamBuildingObjectPoolError(f"{emperor}: team factor choice must be an object")
        choices[text(emperor)] = {
            "role_complementarity_factor": text(raw.get("role_complementarity_factor")),
            "long_term_stability_factor": text(raw.get("long_term_stability_factor")),
            "basis": text(raw.get("basis")),
        }
    return choices


def fetch_factor_options(cur: Any, *, formula_code: str) -> dict[str, dict[str, dict[str, Any]]]:
    cur.execute(
        """
        select f.factor_name,o.option_code,o.label,o.value_num
          from retrieval_v3.eval_rule_factors f
          join retrieval_v3.eval_rule_factor_options o on o.factor_id=f.id and o.option_status='active'
         where f.item_code='I5B' and f.rule_code='team_building' and f.formula_code=%s
        """,
        (formula_code,),
    )
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for raw in cur.fetchall():
        row = dict(raw)
        result.setdefault(text(row["factor_name"]), {})[text(row["option_code"])] = row
    return result


def fetch_people(cur: Any, *, emperors: Sequence[str]) -> list[dict[str, Any]]:
    cur.execute(
        """
        select rt.emperor_name,o.id as object_id,o.canonical_name,pp.talent_grade::text,
               pp.talent_grade_version,pp.readiness_status::text,
               array_agg(distinct rt.id order by rt.id) as source_target_ids,
               array_agg(distinct tob.id order by tob.id) as target_object_ids
          from retrieval_v3.retrieval_targets rt
          join retrieval_v3.target_objects tob on tob.target_id=rt.id
          join retrieval_v3.objects o on o.id=tob.object_id
          join retrieval_v3.person_profiles pp on pp.object_id=o.id
         where rt.item_code='I5B' and rt.target_status='active'
           and rt.emperor_name=any(%s::text[])
           and tob.object_role<>'target_emperor'
           and o.object_type='person' and o.identity_status='active'
         group by rt.emperor_name,o.id,o.canonical_name,pp.talent_grade,pp.talent_grade_version,pp.readiness_status
         order by rt.emperor_name,o.canonical_name,o.id
        """,
        (list(emperors),),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_canonical_targets(cur: Any, *, emperors: Sequence[str]) -> dict[str, dict[str, Any]]:
    cur.execute(
        """
        select distinct on (emperor_name) id as target_id,target_code,emperor_name,item_code
          from retrieval_v3.retrieval_targets
         where item_code='I5B' and target_status='active' and emperor_name=any(%s::text[])
         order by emperor_name,
                  case when target_payload->>'source'='retrieval_v3_contract_reanchor' then 0 else 1 end,
                  id desc
        """,
        (list(emperors),),
    )
    return {text(row["emperor_name"]): dict(row) for row in cur.fetchall()}


def option(options: Mapping[str, Mapping[str, Mapping[str, Any]]], factor: str, code: str) -> dict[str, Any]:
    factor_options = options.get(factor, {})
    if code in factor_options:
        return dict(factor_options[code])
    matches = [dict(row) for row in factor_options.values() if normalized_option_label(row.get("label")) == normalized_option_label(code)]
    if len(matches) == 1:
        return matches[0]
    raise TeamBuildingObjectPoolError(f"unsupported {factor} option: {code}")


def build_clusters(
    *, people: Sequence[Mapping[str, Any]], targets: Mapping[str, Mapping[str, Any]],
    options: Mapping[str, Mapping[str, Mapping[str, Any]]], choices: Mapping[str, Mapping[str, str]],
    formula_code: str,
) -> list[dict[str, Any]]:
    by_emperor: dict[str, list[Mapping[str, Any]]] = {}
    for row in people:
        by_emperor.setdefault(text(row.get("emperor_name")), []).append(row)
    clusters: list[dict[str, Any]] = []
    for emperor in sorted(targets):
        members = by_emperor.get(emperor, [])
        if not members:
            raise TeamBuildingObjectPoolError(f"{emperor}: empty active person pool")
        if emperor not in choices:
            raise TeamBuildingObjectPoolError(f"{emperor}: missing team factor choices")
        seen_ids: set[int] = set()
        components: list[dict[str, Any]] = []
        side_scores: dict[str, Decimal] = {}
        grade_counts: Counter[str] = Counter()
        duplicate_target_rows = 0
        for raw in members:
            object_id = int(raw["object_id"])
            if object_id in seen_ids:
                raise TeamBuildingObjectPoolError(f"{emperor}: duplicate canonical object_id={object_id}")
            seen_ids.add(object_id)
            if text(raw.get("readiness_status")) != "profile_complete" or not text(raw.get("talent_grade")):
                raise TeamBuildingObjectPoolError(f"{emperor}/{raw.get('canonical_name')}: incomplete profile")
            grade = text(raw["talent_grade"])
            talent_label = {
                "historic_talent": "历史级人才。", "top_talent": "顶级人才。",
                "important_talent": "重要人才。", "usable_talent": "可用人才。",
                "ordinary_talent": "普通人才。",
            }.get(grade)
            if not talent_label:
                raise TeamBuildingObjectPoolError(f"{emperor}/{raw.get('canonical_name')}: unsupported talent grade {grade}")
            talent = next(
                (dict(row) for row in options["talent_quality_factor"].values() if normalized_option_label(row.get("label")) == normalized_option_label(talent_label)),
                None,
            )
            if talent is None:
                raise TeamBuildingObjectPoolError(f"missing talent option for {talent_label}")
            value = quant(Decimal(str(talent["value_num"])))
            side_scores[str(object_id)] = value
            grade_counts[grade] += 1
            source_target_ids = list(raw.get("source_target_ids") or [])
            target_object_ids = list(raw.get("target_object_ids") or [])
            duplicate_target_rows += max(0, len(target_object_ids) - 1)
            components.append({
                "object_id": object_id,"object_name": text(raw.get("canonical_name")),
                "talent_grade": grade,"talent_grade_version": text(raw.get("talent_grade_version")),
                "talent_quality_factor": str(value),"talent_quality_option_code": text(talent.get("option_code")),
                "source_target_ids": source_target_ids,"target_object_ids": target_object_ids,
            })
        choice = choices[emperor]
        role = option(options,"role_complementarity_factor",text(choice.get("role_complementarity_factor")))
        stability = option(options,"long_term_stability_factor",text(choice.get("long_term_stability_factor")))
        pool = side_signal(list(side_scores.values()))
        positive = quant(pool * Decimal(str(role["value_num"])) * Decimal(str(stability["value_num"])))
        target = targets[emperor]
        calc_detail = {
            "source": "retrieval_v3_team_building_object_pool",
            "aggregation_family": "object_pool",
            "item_code": "I5B","rule_code": "team_building","formula_code": formula_code,
            "team_formula": "sum(unique canonical person talent_quality_factor) * role_complementarity_factor * long_term_stability_factor",
            "canonical_person_count": len(components),"duplicate_target_rows_collapsed": duplicate_target_rows,
            "talent_grade_counts": dict(sorted(grade_counts.items())),"team_pool_value": str(pool),
            "team_factor_values": {
                "role_complementarity_factor": str(role["value_num"]),
                "long_term_stability_factor": str(stability["value_num"]),
            },
            "team_factor_refs": {
                "role_complementarity_factor": {"option_code": role["option_code"],"label": role["label"]},
                "long_term_stability_factor": {"option_code": stability["option_code"],"label": stability["label"]},
                "basis": text(choice.get("basis")),
            },
            "team_object_components": components,
            "object_side_scores": {"positive": {key: str(value) for key,value in side_scores.items()},"negative": {}},
            "positive_signal": str(positive),"negative_signal": "0.000",
        }
        clusters.append({
            **dict(target),"rule_code": "team_building","formula_code": formula_code,
            "positive_signal": positive,"negative_signal": Decimal("0"),
            "action_counts": {"score": len(components),"supporting_only": 0,"exclude": 0},
            "object_side_scores": {"positive": side_scores,"negative": {}},"calc_detail": calc_detail,
        })
    return clusters


def run(*, dsn: str, emperors: Sequence[str], factor_choices: Mapping[str, Mapping[str, str]], formula_code: str, execute: bool) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn,row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            targets=fetch_canonical_targets(cur,emperors=emperors)
            options=fetch_factor_options(cur,formula_code=formula_code)
            people=fetch_people(cur,emperors=emperors)
            clusters=build_clusters(people=people,targets=targets,options=options,choices=factor_choices,formula_code=formula_code)
            if execute:
                for cluster in clusters:
                    upsert_rule_score_cluster(cur,cluster)
                    cur.execute(
                        "delete from retrieval_v3.target_rule_score_clusters where rule_code='team_building' and formula_code=%s and target_id in (select id from retrieval_v3.retrieval_targets where emperor_name=%s and item_code='I5B' and id<>%s)",
                        (formula_code,cluster["emperor_name"],cluster["target_id"]),
                    )
                conn.commit()
            else:
                conn.rollback()
    return {"ok": True,"write_db": execute,"clusters": [
        {"emperor_name": c["emperor_name"],"target_code": c["target_code"],"positive_signal": str(c["positive_signal"]),
         "negative_signal": str(c["negative_signal"]),"canonical_person_count": c["calc_detail"]["canonical_person_count"],
         "duplicate_target_rows_collapsed": c["calc_detail"]["duplicate_target_rows_collapsed"],
         "talent_grade_counts": c["calc_detail"]["talent_grade_counts"]} for c in clusters
    ]}


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="Rebuild team_building directly from the complete canonical person pool.")
    parser.add_argument("--env-file",type=Path)
    parser.add_argument("--dsn-env",default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--emperor",action="append",required=True)
    parser.add_argument("--team-factors",type=Path,required=True)
    parser.add_argument("--formula-code",default=DEFAULT_FORMULA_CODE)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--output-json",type=Path,required=True)
    return parser


def main(argv: Sequence[str] | None=None) -> int:
    args=build_parser().parse_args(argv)
    if args.env_file is not None: load_env_file(args.env_file)
    payload=run(dsn=resolve_dsn(args.dsn_env),emperors=args.emperor,factor_choices=read_factor_choices(args.team_factors),formula_code=args.formula_code,execute=args.execute)
    write_json(args.output_json,payload)
    print(json.dumps(payload,ensure_ascii=False,sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
