from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_factorization_worklists import (  # noqa: E402
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    build_factor_key_catalog,
    factor_keys_for_material,
)
from scripts.dev.retrieval_v2_candidate_promoter import (  # noqa: E402
    appointment_delegation_protocol_allows_scoring,
)
from scripts.dev.retrieval_v2_import_plan import ImportPlanError, json_param  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor, table_label  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
TARGET_ACTIONS = {"score", "supporting_only", "exclude"}
SIDES = {"positive", "negative"}
TEAM_BUILDING_FACTOR_KEYS = ("talent_quality_factor", "role_complementarity_factor", "long_term_stability_factor")
FACTOR_LABEL_ALIASES: dict[str, dict[str, str]] = {
    "appointment_importance": {
        "高强度授权": "国家级、危局或长期关键授权。",
        "有明确授权": "单一领域的真实授权。",
        "重大军政事务授权": "重大军政事务授权。",
        "国家级、危局或长期关键授权": "国家级、危局或长期关键授权。",
        "单一领域的真实授权": "单一领域的真实授权。",
        "名义授权或职责不清": "名义授权或职责不清。",
    },
    "appointment_effect": {
        "人岗匹配": "人岗匹配成立。",
        "人岗高度匹配": "顶级专长与岗位高度匹配。",
        "顶级专长与岗位高度匹配": "顶级专长与岗位高度匹配。",
        "人岗匹配成立": "人岗匹配成立。",
        "匹配关系较弱或只是普通称职": "匹配关系较弱或只是普通称职。",
        "人岗明显不匹配": "人岗明显不匹配。",
        "结果有效": "正常成功或职责履行良好。",
        "结果明确正向": "正常成功或职责履行良好。",
        "重大成功强烈体现授权合理": "重大成功强烈体现授权合理。",
        "正常成功或职责履行良好": "正常成功或职责履行良好。",
        "履职反馈较弱": "履职反馈较弱，不足以支撑高强度授权正证。",
        "效果较差": "授权后任务结果较差，显示匹配或授权判断有问题。",
        "授权后任务结果较差": "授权后任务结果较差，显示匹配或授权判断有问题。",
        "重大错授、长期错用或对人才结构造成明显损害": "授权直接造成重大军政失败、治理损害或关键职责失守。",
        "授权直接造成重大军政失败": "授权直接造成重大军政失败、治理损害或关键职责失守。",
        "授权直接造成重大军政失败、治理损害或关键职责失守": "授权直接造成重大军政失败、治理损害或关键职责失守。",
        "错授或撤权造成连续性人才安全灾难、关键团队崩坏或大规模后续损害": "错误授权直接造成连续性、结构性或大规模后续损害。",
        "错误授权直接造成连续性、结构性或大规模后续损害": "错误授权直接造成连续性、结构性或大规模后续损害。",
    },
    "attribution_factor": {
        "可归因": "皇帝决策链清楚",
        "可归因于皇帝授权": "皇帝决策链清楚",
    },
    "source_factor": {
        "正史明载": "标准史源且事件链清楚",
        "基础史源": "标准史源且事件链清楚",
    },
    "context_factor": {
        "语境明确": "中性",
        "语境清楚": "中性",
    },
}


class FactorizationConsumerError(ImportPlanError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def read_patch_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise FactorizationConsumerError(f"{path}:{line_no}: expected JSON object")
        payload["_source_path"] = str(path)
        payload["_line_no"] = line_no
        rows.append(payload)
    return rows


def has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def line_ref(row: Mapping[str, Any]) -> str:
    source = text(row.get("_source_path"))
    line_no = text(row.get("_line_no"))
    return f"{source}:{line_no}" if source or line_no else "patch row"


def require_high_information_note(value: Any, *, ref: str) -> str:
    note = text(value)
    if not note:
        raise FactorizationConsumerError(f"{ref}: patch_note is required")
    if len(note) < 24 or not has_cjk(note):
        raise FactorizationConsumerError(f"{ref}: patch_note must be high-information Chinese text")
    low_information_notes = {"入分", "不入分", "保留上下文", "排除", "同意", "见材料", "材料有效"}
    if note in low_information_notes:
        raise FactorizationConsumerError(f"{ref}: patch_note is too generic")
    return note


def factor_label(refs: Mapping[str, Any], factor_name: str, *, ref: str) -> str:
    raw = refs.get(factor_name)
    if not isinstance(raw, Mapping):
        raise FactorizationConsumerError(f"{ref}: factor_refs.{factor_name} must be an object")
    label = text(raw.get("label"))
    if not label:
        raise FactorizationConsumerError(f"{ref}: factor_refs.{factor_name}.label is required")
    return label


def validate_patch_row_shape(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = line_ref(row)
    binding_code = text(row.get("binding_code"))
    if not binding_code:
        raise FactorizationConsumerError(f"{ref}: binding_code is required")
    target_action = text(row.get("target_action"))
    if target_action not in TARGET_ACTIONS:
        raise FactorizationConsumerError(f"{ref}: unsupported target_action {target_action}")
    side = text(row.get("side"))
    if target_action == "score" and side not in SIDES:
        raise FactorizationConsumerError(f"{ref}: score rows must use side positive or negative")
    if target_action != "score" and side and side not in SIDES:
        raise FactorizationConsumerError(f"{ref}: unsupported side {side}")
    factor_refs = row.get("factor_refs") or {}
    if not isinstance(factor_refs, Mapping):
        raise FactorizationConsumerError(f"{ref}: factor_refs must be an object")
    patch_note = require_high_information_note(row.get("patch_note"), ref=ref)
    return {
        "binding_code": binding_code,
        "target_action": target_action,
        "side": side if side else None,
        "factor_refs": dict(factor_refs),
        "patch_note": patch_note,
        "_source_path": text(row.get("_source_path")),
        "_line_no": row.get("_line_no"),
    }


def validate_patch_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    validated = [validate_patch_row_shape(row) for row in rows]
    counts = Counter(row["binding_code"] for row in validated)
    duplicates = sorted(code for code, count in counts.items() if count > 1)
    if duplicates:
        raise FactorizationConsumerError(f"duplicate binding_code in patch: {', '.join(duplicates)}")
    return validated


def fetch_factor_option_rows(cur: Any, *, item_code: str, formula_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            f.id as factor_id,
            f.item_code,
            f.rule_code,
            f.formula_code,
            f.factor_name,
            o.id as factor_option_id,
            o.option_code,
            o.label,
            o.value_num::text as value_num
          from retrieval_v2.eval_rule_factors f
          join retrieval_v2.eval_rule_factor_options o on o.factor_id = f.id
         where f.item_code = %s
           and f.formula_code = %s
           and f.factor_status = 'active'
           and o.option_status = 'active'
         order by f.rule_code, f.factor_name, o.sort_no, o.id
        """,
        (item_code, formula_code),
    )
    return [dict(row) for row in cur.fetchall()]


def build_option_catalog(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    catalog: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (text(row.get("rule_code")), text(row.get("factor_name")), text(row.get("label")))
        catalog.setdefault(key, []).append(dict(row))
    return catalog


def available_labels(
    catalog: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]],
    *,
    rule_code: str,
    factor_name: str,
) -> set[str]:
    labels: set[str] = set()
    for catalog_rule_code, catalog_factor_name, label in catalog:
        if catalog_factor_name == factor_name and catalog_rule_code in {"", rule_code}:
            labels.add(label)
    return labels


def canonical_factor_label(
    catalog: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]],
    *,
    rule_code: str,
    factor_name: str,
    label: str,
) -> tuple[str, str]:
    labels = available_labels(catalog, rule_code=rule_code, factor_name=factor_name)
    if label in labels:
        return label, ""
    stripped = label.rstrip("。")
    punctuation_matches = sorted(candidate for candidate in labels if candidate.rstrip("。") == stripped)
    if len(punctuation_matches) == 1:
        return punctuation_matches[0], "punctuation"
    alias = FACTOR_LABEL_ALIASES.get(factor_name, {}).get(label)
    if alias and alias in labels:
        return alias, "alias"
    if alias:
        alias_stripped = alias.rstrip("。")
        alias_matches = sorted(candidate for candidate in labels if candidate.rstrip("。") == alias_stripped)
        if len(alias_matches) == 1:
            return alias_matches[0], "alias"
    return label, ""


def resolve_factor_option(
    catalog: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]],
    *,
    rule_code: str,
    factor_name: str,
    label: str,
    ref: str,
    canonicalizations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    original_label = label
    label, reason = canonical_factor_label(catalog, rule_code=rule_code, factor_name=factor_name, label=label)
    matches = list(catalog.get((rule_code, factor_name, label), ()))
    if not matches:
        matches = list(catalog.get(("", factor_name, label), ()))
    if not matches:
        raise FactorizationConsumerError(f"{ref}: unknown factor option {factor_name}={label}")
    if len(matches) > 1:
        raise FactorizationConsumerError(f"{ref}: ambiguous factor option {factor_name}={label}")
    if reason and canonicalizations is not None:
        canonicalizations.append(
            {
                "ref": ref,
                "factor_name": factor_name,
                "from": original_label,
                "to": label,
                "reason": reason,
            }
        )
    return dict(matches[0])


def appointment_effect_sign_issue(*, side: str, value: Decimal) -> str:
    if value == 0:
        return ""
    if side == "positive" and value < 0:
        return "positive side cannot use negative appointment_effect"
    if side == "negative" and value > 0:
        return "negative side cannot use positive appointment_effect"
    return ""


def validate_appointment_effect_side(
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    choices: Sequence[Mapping[str, Any]],
) -> None:
    if text(context.get("rule_code")) != "appointment_delegation" or row["target_action"] != "score":
        return
    side = text(row.get("side"))
    for choice in choices:
        if text(choice.get("factor_name")) != "appointment_effect":
            continue
        value = Decimal(str(choice.get("value_num")))
        issue = appointment_effect_sign_issue(side=side, value=value)
        if issue:
            raise FactorizationConsumerError(
                f"{line_ref(row)}: {issue}: {row['binding_code']} appointment_effect={choice.get('option_label')}"
            )


def validate_appointment_delegation_scoring_gate(*, row: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    if text(context.get("rule_code")) != "appointment_delegation" or row["target_action"] != "score":
        return
    if context.get("binding_usable_for_scoring_cluster") is False:
        raise FactorizationConsumerError(f"{line_ref(row)}: appointment_delegation score patch targets non-scoring binding {row['binding_code']}")
    candidate_id = context.get("candidate_id")
    binding_payload = context.get("binding_payload") if isinstance(context.get("binding_payload"), Mapping) else {}
    from_promoter = text(binding_payload.get("source")) == "retrieval_v2_candidate_promoter" or candidate_id is not None
    if not from_promoter:
        return
    candidate_payload = context.get("candidate_payload") if isinstance(context.get("candidate_payload"), Mapping) else {}
    if not candidate_payload:
        raise FactorizationConsumerError(f"{line_ref(row)}: appointment_delegation promoted binding lacks candidate_payload gate {row['binding_code']}")
    if not appointment_delegation_protocol_allows_scoring({"candidate_payload": candidate_payload}):
        raise FactorizationConsumerError(
            f"{line_ref(row)}: appointment_delegation candidate_payload is not a scoring candidate {row['binding_code']}"
        )


def fetch_binding_context(cur: Any, binding_code: str) -> dict[str, Any]:
    cur.execute(
        """
        select
            crb.id as binding_id,
            crb.binding_code,
            crb.claim_id,
            crb.rule_code,
            crb.direction as binding_direction,
            crb.usable_for_scoring_cluster as binding_usable_for_scoring_cluster,
            crb.binding_payload,
            mc.source_pack_id,
            sp.target_id,
            rt.item_code,
            cand.id as candidate_id,
            cand.candidate_code,
            cand.candidate_payload
          from retrieval_v2.claim_rule_bindings crb
          join retrieval_v2.material_claims mc on mc.id = crb.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join lateral (
              select c.*
                from retrieval_v2.claim_rule_binding_candidates c
               where c.resolved_binding_id = crb.id
                  or (
                      coalesce(crb.binding_payload->>'candidate_id', '') ~ '^[0-9]+$'
                      and c.id = (crb.binding_payload->>'candidate_id')::bigint
                  )
               order by case when c.resolved_binding_id = crb.id then 0 else 1 end, c.id
               limit 1
          ) cand on true
         where crb.binding_code = %s
        """,
        (binding_code,),
    )
    row = cur.fetchone()
    if not row:
        raise FactorizationConsumerError(f"binding_code not found: {binding_code}")
    return dict(row)


def judgment_idem_key(*, binding_code: str, formula_code: str) -> str:
    return "|".join([binding_code, formula_code, "factor_judgment"])


def factor_choices_for_row(
    row: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    catalog: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]],
    factor_key_catalog: Mapping[str, Sequence[Mapping[str, Any]]],
    canonicalizations: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    if row["target_action"] != "score":
        return []
    ref = line_ref(row)
    rule_code = text(context.get("rule_code"))
    side = text(row.get("side"))
    if rule_code == "team_building":
        expected = list(TEAM_BUILDING_FACTOR_KEYS)
    else:
        expected = list(factor_keys_for_material(rule_code, side, factor_key_catalog))
    refs = row.get("factor_refs") or {}
    extras = sorted(set(refs) - set(expected))
    missing = [factor_name for factor_name in expected if factor_name not in refs]
    if missing:
        raise FactorizationConsumerError(f"{ref}: missing factor_refs {', '.join(missing)}")
    if extras:
        raise FactorizationConsumerError(f"{ref}: unknown factor_refs {', '.join(extras)}")
    choices: list[dict[str, Any]] = []
    for factor_name in expected:
        label = factor_label(refs, factor_name, ref=ref)
        option = resolve_factor_option(
            catalog,
            rule_code=rule_code,
            factor_name=factor_name,
            label=label,
            ref=ref,
            canonicalizations=canonicalizations,
        )
        choices.append(
            {
                "factor_name": factor_name,
                "factor_id": int(option["factor_id"]),
                "factor_option_id": int(option["factor_option_id"]),
                "option_code": text(option.get("option_code")),
                "option_label": text(option.get("label")),
                "value_num": text(option.get("value_num")) or None,
            }
        )
    return choices


def upsert_factor_judgment(
    cur: Any,
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    formula_code: str,
) -> int:
    idem_key = judgment_idem_key(binding_code=text(row["binding_code"]), formula_code=formula_code)
    payload = {
        "source": "retrieval_v2_factorization_consumer",
        "patch": {key: value for key, value in row.items() if not str(key).startswith("_")},
    }
    cur.execute(
        """
        insert into retrieval_v2.claim_rule_binding_factor_judgments (
            factor_judgment_code, idem_key, binding_id, claim_id, target_id, source_pack_id,
            item_code, rule_code, formula_code, target_action, side, factor_summary,
            patch_note, review_status, judgment_payload
        )
        values (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s::retrieval_v2.rv2_factor_target_action, %s::retrieval_v2.rv2_factor_side, %s::jsonb,
            %s, %s::retrieval_v2.rv2_review_status, %s::jsonb
        )
        on conflict on constraint rv2_claim_rule_binding_factor_judgments_idem_uk do update set
            target_action = excluded.target_action,
            side = excluded.side,
            factor_summary = excluded.factor_summary,
            patch_note = excluded.patch_note,
            review_status = excluded.review_status,
            judgment_payload = excluded.judgment_payload,
            updated_at = now()
        returning id
        """,
        (
            "RV2FJ-" + stable_hash(idem_key, length=16),
            idem_key,
            int(context["binding_id"]),
            int(context["claim_id"]),
            int(context["target_id"]),
            int(context["source_pack_id"]),
            text(context["item_code"]),
            text(context["rule_code"]),
            formula_code,
            text(row["target_action"]),
            text(row.get("side")) or None,
            json_param(row.get("factor_refs") or {}),
            text(row["patch_note"]),
            "accepted",
            json_param(payload),
        ),
    )
    result = cur.fetchone()
    if not result:
        raise FactorizationConsumerError(f"factor judgment insert did not return id: {row['binding_code']}")
    return int(result["id"])


def replace_factor_choices(
    cur: Any,
    *,
    judgment_id: int,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    formula_code: str,
    choices: Sequence[Mapping[str, Any]],
) -> None:
    cur.execute(
        """
        delete from retrieval_v2.claim_rule_binding_factor_choices
         where factor_judgment_id = %s
        """,
        (judgment_id,),
    )
    base_idem = judgment_idem_key(binding_code=text(row["binding_code"]), formula_code=formula_code)
    for choice in choices:
        idem_key = "|".join([base_idem, text(choice.get("factor_name"))])
        payload = {
            "source": "retrieval_v2_factorization_consumer",
            "binding_code": text(row["binding_code"]),
            "factor_name": text(choice.get("factor_name")),
            "patch_label": text(choice.get("option_label")),
        }
        cur.execute(
            """
            insert into retrieval_v2.claim_rule_binding_factor_choices (
                factor_choice_code, idem_key, factor_judgment_id, binding_id, factor_id,
                factor_option_id, factor_name, option_code, option_label, value_num,
                choice_payload
            )
            values (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s::jsonb
            )
            on conflict on constraint rv2_claim_rule_binding_factor_choices_idem_uk do update set
                factor_option_id = excluded.factor_option_id,
                option_code = excluded.option_code,
                option_label = excluded.option_label,
                value_num = excluded.value_num,
                choice_payload = excluded.choice_payload,
                updated_at = now()
            """,
            (
                "RV2FC-" + stable_hash(idem_key, length=16),
                idem_key,
                judgment_id,
                int(context["binding_id"]),
                int(choice["factor_id"]),
                int(choice["factor_option_id"]),
                text(choice.get("factor_name")),
                text(choice.get("option_code")),
                text(choice.get("option_label")),
                choice.get("value_num"),
                json_param(payload),
            ),
        )


def mark_binding_scoring_gate_accepted(cur: Any, *, row: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    usable_for_scoring = row["target_action"] == "score"
    payload = {
        "source": "retrieval_v2_factorization_consumer",
        "target_action": text(row.get("target_action")),
        "usable_for_scoring_cluster": usable_for_scoring,
        "review_status": "accepted",
    }
    cur.execute(
        """
        update retrieval_v2.claim_rule_bindings
           set usable_for_scoring_cluster = %s,
               binding_payload = coalesce(binding_payload, '{}'::jsonb)
                   || jsonb_build_object('scoring_gate', %s::jsonb),
               updated_at = now()
         where id = %s
        """,
        (usable_for_scoring, json_param(payload), int(context["binding_id"])),
    )


def apply_patch_rows(
    *,
    dsn: str,
    schema_name: str = DEFAULT_PG_SCHEMA,
    rows: Sequence[Mapping[str, Any]],
    item_code: str,
    formula_code: str,
    execute: bool,
) -> dict[str, Any]:
    validated = validate_patch_rows(rows)
    psycopg, dict_row = import_psycopg()
    counts: Counter[str] = Counter()
    judgments: list[dict[str, Any]] = []
    canonicalizations: list[dict[str, str]] = []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            option_rows = fetch_factor_option_rows(cur, item_code=item_code, formula_code=formula_code)
            catalog = build_option_catalog(option_rows)
            factor_key_catalog = build_factor_key_catalog(option_rows)
            for row in validated:
                context = fetch_binding_context(cur, text(row["binding_code"]))
                if text(context.get("item_code")) != item_code:
                    raise FactorizationConsumerError(
                        f"{row['binding_code']}: item_code mismatch, expected {item_code}, got {context.get('item_code')}"
                    )
                choices = factor_choices_for_row(
                    row,
                    context=context,
                    catalog=catalog,
                    factor_key_catalog=factor_key_catalog,
                    canonicalizations=canonicalizations,
                )
                validate_appointment_delegation_scoring_gate(row=row, context=context)
                validate_appointment_effect_side(row=row, context=context, choices=choices)
                judgment_id = upsert_factor_judgment(cur, row=row, context=context, formula_code=formula_code)
                mark_binding_scoring_gate_accepted(cur, row=row, context=context)
                replace_factor_choices(
                    cur,
                    judgment_id=judgment_id,
                    row=row,
                    context=context,
                    formula_code=formula_code,
                    choices=choices,
                )
                counts[table_label("claim_rule_binding_factor_judgments", schema_name=schema_name)] += 1
                counts[f"{table_label('claim_rule_bindings', schema_name=schema_name)}_scoring_gate"] += 1
                counts[table_label("claim_rule_binding_factor_choices", schema_name=schema_name)] += len(choices)
                judgments.append(
                    {
                        "binding_code": row["binding_code"],
                        "target_action": row["target_action"],
                        "side": row.get("side"),
                        "choice_count": len(choices),
                    }
                )
        if execute:
            conn.commit()
        else:
            conn.rollback()
    action_counts = Counter(text(row.get("target_action")) for row in validated)
    return {
        "generated_by": "scripts/dev/retrieval_v2_factorization_consumer.py",
        "command": "apply-patch",
        "write_db": execute,
        "executed": execute,
        "ok": True,
        "item_code": item_code,
        "formula_code": formula_code,
        "rows": len(validated),
        "action_counts": dict(sorted(action_counts.items())),
        "applied_counts": dict(sorted(counts.items())),
        "canonicalized_label_count": len(canonicalizations),
        "canonicalized_labels": canonicalizations[:200],
        "judgments": judgments,
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 factorization consumer report",
        "",
        f"- command: `{payload.get('command', '')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db', False)).lower()}`",
        f"- executed: `{str(payload.get('executed', False)).lower()}`",
        f"- item_code: `{payload.get('item_code', '')}`",
        f"- formula_code: `{payload.get('formula_code', '')}`",
        f"- rows: `{payload.get('rows', 0)}`",
        "",
    ]
    if payload.get("action_counts"):
        lines.extend(["## Actions", "", "| action | rows |", "| --- | ---: |"])
        for action, count in (payload.get("action_counts") or {}).items():
            lines.append(f"| {action} | {count} |")
        lines.append("")
    if payload.get("applied_counts"):
        lines.extend(["## Applied", "", "| table | rows |", "| --- | ---: |"])
        for table, count in (payload.get("applied_counts") or {}).items():
            lines.append(f"| {table} | {count} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(output_json: Path, output_md: Path | None, payload: Mapping[str, Any]) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(markdown_report(payload), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume retrieval_v2 factorization JSONL patches; dry-run unless --execute.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", type=Path)
    common.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    common.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    common.add_argument("--output-json", type=Path, required=True)
    common.add_argument("--output-md", type=Path)

    apply = subparsers.add_parser("apply-patch", parents=[common], help="Apply factorization patch JSONL.")
    apply.add_argument("--patch-jsonl", type=Path, action="append", required=True)
    apply.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    apply.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE)
    apply.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    if args.command == "apply-patch":
        rows = [row for path in args.patch_jsonl for row in read_patch_jsonl(path)]
        payload = apply_patch_rows(
            dsn=resolve_dsn(args.dsn_env),
            schema_name=args.pg_schema,
            rows=rows,
            item_code=args.item_code,
            formula_code=args.formula_code,
            execute=args.execute,
        )
    else:
        raise FactorizationConsumerError(f"unsupported command: {args.command}")
    write_report(args.output_json, args.output_md, payload)
    print(json.dumps({"ok": payload["ok"], "command": args.command, "output_json": str(args.output_json)}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
