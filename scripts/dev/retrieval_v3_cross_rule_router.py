from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import json_param, reason_hash, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v3_review_worklists import object_group_key  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV


FORMAL_CANDIDATE_RULES = {
    "appointment_delegation",
    "team_building",
    "talent_discovery",
    "tolerate_talent",
    "anti_nepotism",
}
FUTURE_HINT_RULES = {
    "central_military_power_control",
    "regional_clan_power_control",
    "inner_favorite_power_control",
    "institutional_constraint_correction",
    "political_character",
    "cognition_learning",
    "key_decision",
    "military_frontier_result",
    "historical_debt",
}
DISPOSITION_TERMS = (
    "疑", "夺", "降封", "诛", "诛族", "杀", "斩", "处死", "赐死", "下狱", "械系", "籍没",
    "流放", "安置", "废", "罢", "免", "禁锢", "圈禁", "伏诛", "反",
)


class CrossRuleRouterError(RuntimeError):
    pass


@dataclass(frozen=True)
class RouteSpec:
    rule_code: str
    signals: tuple[str, ...]
    terms: tuple[str, ...]
    future_hint: bool = False
    caution: str = ""

    @property
    def reason(self) -> str:
        signal_text = "、".join(self.signals)
        term_text = "、".join(self.terms[:8])
        base = f"appointment_delegation claim 可复用于 {self.rule_code} 复核：{signal_text}"
        if term_text:
            base = f"{base}；命中词：{term_text}"
        if self.caution:
            base = f"{base}；{self.caution}"
        return base

    @property
    def route_status(self) -> str:
        return "future_rule_hint" if self.future_hint else "current_rule_candidate"


def contains_any(haystack: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term and term in haystack)


def add_route(routes: dict[str, RouteSpec], route: RouteSpec) -> None:
    existing = routes.get(route.rule_code)
    if existing is None:
        routes[route.rule_code] = route
        return
    routes[route.rule_code] = RouteSpec(
        rule_code=route.rule_code,
        signals=tuple(dict.fromkeys((*existing.signals, *route.signals))),
        terms=tuple(dict.fromkeys((*existing.terms, *route.terms))),
        future_hint=existing.future_hint or route.future_hint,
        caution=existing.caution or route.caution,
    )


def route_claim(row: Mapping[str, Any]) -> list[RouteSpec]:
    summary = text(row.get("claim_summary"))
    object_name = text(row.get("object_name"))
    predicate = text(row.get("predicate"))
    object_role = text(row.get("object_role"))
    binding_payload = row.get("binding_payload") if isinstance(row.get("binding_payload"), Mapping) else {}
    haystack = " ".join(
        value
        for value in (
            summary,
            object_name,
            predicate,
            object_role,
            json.dumps(binding_payload, ensure_ascii=False, sort_keys=True, default=str),
        )
        if value
    )
    routes: dict[str, RouteSpec] = {}

    appointment_terms = contains_any(
        haystack,
        ("任", "拜", "委", "授", "命", "用", "信", "心膂", "左丞相", "给兵", "将兵", "封", "误任"),
    )
    if appointment_terms or predicate in {"delegated_authority", "revoked_authority", "misdelegated_authority"}:
        add_route(
            routes,
            RouteSpec(
                "appointment_delegation",
                ("任用/信任/撤任事实",),
                appointment_terms,
            ),
        )

    team_terms = contains_any(
        haystack,
        (
            "丞相",
            "大司徒",
            "大将军",
            "将军",
            "太尉",
            "中书",
            "枢密",
            "宰相",
            "参知",
            "内阁",
            "大学士",
            "总督",
            "巡抚",
            "监护诸将",
            "经略",
            "核心",
        ),
    )
    if team_terms or object_role in {"civil_delegate", "military_delegate", "frontier_delegate"}:
        add_route(
            routes,
            RouteSpec(
                "team_building",
                ("核心团队/军政成员材料",),
                team_terms,
            ),
        )

    discovery_terms = contains_any(
        haystack,
        ("荐", "举", "拔", "擢", "识", "知其才", "推荐", "延揽", "访求", "举为", "召见", "召至", "试用", "赏识", "异之", "器重"),
    )
    if discovery_terms:
        add_route(
            routes,
            RouteSpec(
                "talent_discovery",
                ("荐举/识别/拔擢人才材料",),
                discovery_terms,
            ),
        )

    tolerance_positive_terms = contains_any(
        haystack,
        (
            "容",
            "赦",
            "保全",
            "不杀",
            "复用",
            "召还",
            "宽",
            "贷",
            "宥",
            "谏",
            "諫",
            "诤",
            "諍",
            "直言",
            "上疏",
            "纳谏",
            "納諫",
            "受金",
            "盗嫂",
            "盜嫂",
            "谗",
            "讒",
            "谮",
            "譖",
            "短",
            "毁",
            "毀",
        ),
    )
    disposition_terms = contains_any(haystack, DISPOSITION_TERMS)
    if tolerance_positive_terms or disposition_terms:
        caution = ""
        if disposition_terms:
            caution = "处置性材料只作为候选，不单凭处置结果定为负向"
        add_route(
            routes,
            RouteSpec(
                "tolerate_talent",
                ("容才/疑忌/处置边界材料",),
                tuple(dict.fromkeys((*tolerance_positive_terms, *disposition_terms))),
                caution=caution,
            ),
        )

    nepotism_terms = contains_any(
        haystack,
        ("亲", "外戚", "宗室", "家族", "近臣", "私", "党", "朋党", "结党", "纳贿", "贿", "专擅", "骄纵", "欺罔", "谮"),
    )
    if nepotism_terms:
        add_route(
            routes,
            RouteSpec(
                "anti_nepotism",
                ("亲私/朋党/近臣风险材料",),
                nepotism_terms,
            ),
        )

    central_military_power_terms = contains_any(
        haystack,
        (
            "收兵权",
            "收兵權",
            "夺兵权",
            "奪兵權",
            "军权",
            "軍權",
            "兵权",
            "兵權",
            "禁军",
            "禁軍",
            "军头",
            "軍頭",
            "宿卫",
            "宿衛",
        ),
    )
    if central_military_power_terms:
        add_route(
            routes,
            RouteSpec(
                "central_military_power_control",
                ("中央军权控制 future/current candidate",),
                central_military_power_terms,
                future_hint=True,
            ),
        )

    regional_clan_power_terms = contains_any(
        haystack,
        (
            "撤藩",
            "削藩",
            "藩",
            "外戚",
            "宗室",
            "强宗",
            "豪族",
            "封国",
            "封國",
            "地方",
            "反叛",
            "谋反",
            "起兵",
            "聚兵",
            "作乱",
        ),
    )
    if regional_clan_power_terms:
        add_route(
            routes,
            RouteSpec(
                "regional_clan_power_control",
                ("地方/宗族权力控制 future/current candidate",),
                regional_clan_power_terms,
                future_hint=True,
            ),
        )

    inner_favorite_power_terms = contains_any(
        haystack,
        (
            "宦官",
            "近臣",
            "宠臣",
            "寵臣",
            "内廷",
            "內廷",
            "私门",
            "私門",
            "矫诏",
            "矯詔",
            "专擅",
            "擅权",
            "擅權",
            "权臣",
            "權臣",
        ),
    )
    if inner_favorite_power_terms:
        add_route(
            routes,
            RouteSpec(
                "inner_favorite_power_control",
                ("内廷近幸权力控制 future/current candidate",),
                inner_favorite_power_terms,
                future_hint=True,
            ),
        )

    institutional_constraint_terms = contains_any(
        haystack,
        (
            "收权",
            "收權",
            "限权",
            "限權",
            "制衡",
            "纠偏",
            "糾偏",
            "问责",
            "問責",
            "罢相",
            "罷相",
            "废相",
            "廢相",
            "中书",
            "中書",
            "丞相",
            "法制",
            "制度",
            "台谏",
            "臺諫",
            "御史",
            "监察",
            "監察",
            "专政",
        ),
    )
    if institutional_constraint_terms:
        add_route(
            routes,
            RouteSpec(
                "institutional_constraint_correction",
                ("制度约束纠偏 future/current candidate",),
                institutional_constraint_terms,
                future_hint=True,
            ),
        )

    character_terms = contains_any(
        haystack,
        (
            "滥杀",
            "濫殺",
            "妄杀",
            "妄殺",
            "冤杀",
            "冤殺",
            "勿焚掠",
            "冤",
            "怒杀",
            "诛族",
            "族诛",
            "族誅",
            "株连",
            "株連",
            "牵连",
            "牽連",
            "罗织",
            "羅織",
            "构陷",
            "構陷",
            "大狱",
            "大獄",
            "功被抑",
            "称冤",
            "克制",
            "猜忌",
        ),
    )
    if character_terms:
        add_route(
            routes,
            RouteSpec(
                "political_character",
                ("政治品格 future hint",),
                character_terms,
                future_hint=True,
            ),
        )

    cognition_terms = contains_any(
        haystack,
        ("从谏", "從諫", "拒谏", "拒諫", "纳谏", "納諫", "问策", "問策", "谏", "諫", "诤", "諍", "直言", "上疏", "改过", "改過", "弊政"),
    )
    if cognition_terms:
        add_route(
            routes,
            RouteSpec(
                "cognition_learning",
                ("认知纠错 future hint",),
                cognition_terms,
                future_hint=True,
            ),
        )

    decision_terms = contains_any(
        haystack,
        ("迁都", "遷都", "废立", "廢立", "立太子", "废太子", "廢太子", "继承", "繼承", "罢兵", "罷兵", "休兵", "班师", "班師", "议和", "議和", "和亲", "和親"),
    )
    if decision_terms:
        add_route(
            routes,
            RouteSpec(
                "key_decision",
                ("关键决策 future hint",),
                decision_terms,
                future_hint=True,
            ),
        )

    military_frontier_terms = contains_any(
        haystack,
        ("边疆", "邊疆", "边镇", "邊鎮", "设治", "設治", "羁縻", "羈縻", "都护", "都護", "关隘", "關隘", "屯田", "收复", "收復", "失地", "入寇"),
    )
    if military_frontier_terms:
        add_route(
            routes,
            RouteSpec(
                "military_frontier_result",
                ("军事边疆 future hint",),
                military_frontier_terms,
                future_hint=True,
            ),
        )

    debt_terms = contains_any(
        haystack,
        ("屠", "坑", "连坐", "連坐", "告发", "告發", "诏狱", "詔獄", "徭役", "横征", "橫征", "民变", "民變", "崩坏", "崩壞"),
    )
    if debt_terms:
        add_route(
            routes,
            RouteSpec(
                "historical_debt",
                ("历史负债 future hint",),
                debt_terms,
                future_hint=True,
            ),
        )

    return [route for route in routes.values() if route.rule_code != text(row.get("source_rule_code") or row.get("rule_code"))]


def candidate_code_for(row: Mapping[str, Any], route: RouteSpec) -> str:
    seed = "|".join(
        [
            text(row.get("claim_code")),
            text(row.get("source_rule_code") or row.get("rule_code")),
            route.rule_code,
            reason_hash(route.reason),
        ]
    )
    return f"CRBC-BF-{stable_hash(seed, length=20)}"


def candidate_row(row: Mapping[str, Any], route: RouteSpec) -> dict[str, Any]:
    formal = route.rule_code in FORMAL_CANDIDATE_RULES and not route.future_hint
    candidate_item_code = text(row.get("item_code")) if formal else ""
    candidate_lane = f"{candidate_item_code}.{route.rule_code}" if candidate_item_code else route.rule_code
    hint_status = route.route_status
    required_facts_present = {
        "source_claim": True,
        "source_binding": True,
        "matched_signal": bool(route.signals),
        "matched_term": bool(route.terms),
    }
    payload: dict[str, Any] = {
        "created_from": "retrieval_v3_cross_rule_router",
        "route_status": hint_status,
        "candidate_lane": candidate_lane,
        "hint_status": hint_status,
        "required_facts_present": required_facts_present,
        "routed_by_profile": "retrieval_v3_cross_rule_router",
        "matched_signals": list(route.signals),
        "matched_terms": list(route.terms),
        "source_rule_code": text(row.get("source_rule_code") or row.get("rule_code")),
        "source_binding": {
            "predicate": text(row.get("predicate")),
            "object_role": text(row.get("object_role")),
            "direction": text(row.get("binding_direction")),
        },
    }
    if isinstance(row.get("source_bindings"), list):
        payload["source_bindings"] = row["source_bindings"]
    if route.caution:
        payload["caution"] = route.caution
    return {
        "candidate_code": candidate_code_for(row, route),
        "claim_id": int(row["claim_id"]),
        "claim_code": text(row.get("claim_code")),
        "source_pack_id": int(row["source_pack_id"]),
        "source_pack_code": text(row.get("source_pack_code")),
        "target_id": int(row["target_id"]),
        "target_code": text(row.get("target_code")),
        "emperor_name": text(row.get("emperor_name")),
        "object_name": text(row.get("object_name")),
        "object_group_key": text(row.get("object_group_key")) or object_group_key(text(row.get("object_name"))),
        "claim_summary_hash": text(row.get("claim_summary_hash")),
        "claim_summary": text(row.get("claim_summary")),
        "source_contract_rule_id": row.get("source_contract_rule_id"),
        "candidate_contract_rule_id": row.get("candidate_contract_rule_id") if formal else None,
        "source_item_code": text(row.get("item_code")),
        "source_rule_code": text(row.get("source_rule_code") or row.get("rule_code")),
        "candidate_item_code": candidate_item_code,
        "candidate_rule_code": route.rule_code,
        "candidate_lane": candidate_lane,
        "hint_status": hint_status,
        "required_facts_present": required_facts_present,
        "routed_by_profile": "retrieval_v3_cross_rule_router",
        "candidate_predicate": "",
        "candidate_object_role": "",
        "candidate_direction": None,
        "reason_hash": reason_hash(route.reason),
        "candidate_reason": route.reason,
        "confidence": None,
        "review_status": "pending",
        "candidate_payload": payload,
    }


def dedupe_candidates(candidates: Iterable[dict[str, Any]], *, canonical_only: bool = True) -> tuple[list[dict[str, Any]], int]:
    if not canonical_only:
        rows = list(candidates)
        return rows, 0
    selected: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    skipped = 0
    for row in sorted(
        candidates,
        key=lambda item: (
            text(item.get("target_code")),
            text(item.get("object_group_key")),
            text(item.get("claim_summary_hash")),
            text(item.get("candidate_rule_code")),
            -int(item.get("source_pack_id") or 0),
            -int(item.get("claim_id") or 0),
        ),
    ):
        key = (
            text(row.get("target_code")),
            text(row.get("object_group_key")),
            text(row.get("claim_summary_hash")),
            text(row.get("candidate_rule_code")),
        )
        if key in selected:
            skipped += 1
            continue
        selected[key] = row
    return list(selected.values()), skipped


def fetch_source_rows(cur: Any, *, item_code: str, source_rule_code: str, emperors: Sequence[str]) -> list[dict[str, Any]]:
    clauses = ["t.item_code = %s", "sp.status = 'accepted'", "crb.rule_code = %s"]
    params: list[Any] = [item_code, source_rule_code]
    if emperors:
        clauses.append("t.emperor_name = any(%s)")
        params.append(list(emperors))
    cur.execute(
        f"""
        select
            t.id as target_id,
            t.target_code,
            t.emperor_name,
            t.item_code,
            sp.id as source_pack_id,
            sp.pack_code as source_pack_code,
            mc.id as claim_id,
            mc.claim_code,
            mc.object_name,
            mc.object_group_key,
            mc.claim_summary,
            mc.claim_summary_hash,
            mc.direction::text as claim_direction,
            mc.claim_payload,
            crb.id as binding_id,
            crb.contract_rule_id as source_contract_rule_id,
            crb.rule_code as source_rule_code,
            crb.predicate,
            crb.object_role,
            crb.direction::text as binding_direction,
            crb.binding_payload
          from retrieval_v3.retrieval_targets t
          join retrieval_v3.source_packs sp on sp.target_id = t.id
          join retrieval_v3.material_claims mc on mc.source_pack_id = sp.id
          join retrieval_v3.claim_rule_bindings crb on crb.claim_id = mc.id
         where {" and ".join(clauses)}
         order by t.emperor_name, sp.id desc, mc.id, crb.id
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def grouped_source_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(int(row["claim_id"]), []).append(row)
    grouped: list[dict[str, Any]] = []
    for claim_rows in groups.values():
        base = dict(claim_rows[0])
        base["source_bindings"] = [
            {
                "binding_id": row.get("binding_id"),
                "predicate": text(row.get("predicate")),
                "object_role": text(row.get("object_role")),
                "direction": text(row.get("binding_direction")),
            }
            for row in claim_rows
        ]
        route_map: dict[str, RouteSpec] = {}
        for row in claim_rows:
            for route in route_claim(row):
                add_route(route_map, route)
        base["_routes"] = list(route_map.values())
        grouped.append(base)
    return grouped


def fetch_candidate_rule_ids(cur: Any, rows: Sequence[dict[str, Any]], *, formal_rule_codes: set[str]) -> dict[tuple[int, str], int]:
    target_contracts: dict[int, int] = {}
    if not rows:
        return {}
    cur.execute(
        """
        select id, target_code, contract_id
          from retrieval_v3.retrieval_targets
         where id = any(%s)
        """,
        ([int(row["target_id"]) for row in rows],),
    )
    target_contracts = {int(row["id"]): int(row["contract_id"]) for row in cur.fetchall()}
    contract_ids_list = sorted(set(target_contracts.values()))
    if not contract_ids_list:
        return {}
    cur.execute(
        """
        select contract_id, rule_code, id
          from retrieval_v3.rule_contract_rules
         where contract_id = any(%s)
           and rule_code = any(%s)
        """,
        (contract_ids_list, sorted(formal_rule_codes)),
    )
    by_contract_rule = {(int(row["contract_id"]), text(row["rule_code"])): int(row["id"]) for row in cur.fetchall()}
    return {
        (target_id, rule_code): rule_id
        for target_id, contract_id in target_contracts.items()
        for rule_code in formal_rule_codes
        if (rule_id := by_contract_rule.get((contract_id, rule_code))) is not None
    }


def build_plan(
    cur: Any,
    *,
    item_code: str,
    source_rule_code: str,
    emperors: Sequence[str] = (),
    canonical_only: bool = True,
) -> dict[str, Any]:
    rows = fetch_source_rows(cur, item_code=item_code, source_rule_code=source_rule_code, emperors=emperors)
    rule_ids = fetch_candidate_rule_ids(cur, rows, formal_rule_codes=FORMAL_CANDIDATE_RULES)
    raw_candidates: list[dict[str, Any]] = []
    grouped_rows = grouped_source_rows(rows)
    for row in grouped_rows:
        for route in row.get("_routes") or []:
            enriched = dict(row)
            enriched["candidate_contract_rule_id"] = rule_ids.get((int(row["target_id"]), route.rule_code))
            raw_candidates.append(candidate_row(enriched, route))
    candidates, skipped = dedupe_candidates(raw_candidates, canonical_only=canonical_only)
    counter = Counter(text(row.get("candidate_rule_code")) for row in candidates)
    formal_missing = [
        row
        for row in candidates
        if row["candidate_rule_code"] in FORMAL_CANDIDATE_RULES and row.get("candidate_contract_rule_id") is None
    ]
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_cross_rule_router.py",
        "item_code": item_code,
        "source_rule_code": source_rule_code,
        "canonical_only": canonical_only,
        "write_db": False,
        "executed": False,
        "totals": {
            "source_rows": len(rows),
            "source_claims": len(grouped_rows),
            "raw_candidates": len(raw_candidates),
            "candidates": len(candidates),
            "skipped_duplicate_candidates": skipped,
            "formal_candidates_missing_contract_rule": len(formal_missing),
        },
        "candidate_rule_counts": dict(sorted(counter.items())),
        "sample_candidates": candidates[:20],
        "candidates": candidates,
    }


def upsert_candidate(cur: Any, row: Mapping[str, Any]) -> int | None:
    cur.execute(
        """
        insert into retrieval_v3.claim_rule_binding_candidates (
            candidate_code, claim_id, source_contract_rule_id, candidate_contract_rule_id,
            source_item_code, source_rule_code, candidate_item_code, candidate_rule_code,
            candidate_lane, hint_status, required_facts_present, routed_by_profile,
            candidate_predicate, candidate_object_role, candidate_direction, reason_hash,
            candidate_reason, confidence, review_status, resolved_binding_id, candidate_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, null, %s, %s, null, 'pending', null, %s::jsonb)
        on conflict on constraint rv3_claim_rule_binding_candidates_uk do update set
            candidate_contract_rule_id = coalesce(retrieval_v3.claim_rule_binding_candidates.candidate_contract_rule_id, excluded.candidate_contract_rule_id),
            candidate_lane = excluded.candidate_lane,
            hint_status = excluded.hint_status,
            required_facts_present = excluded.required_facts_present,
            routed_by_profile = excluded.routed_by_profile,
            candidate_reason = excluded.candidate_reason,
            candidate_payload = excluded.candidate_payload,
            review_status = case
                when retrieval_v3.claim_rule_binding_candidates.review_status = 'pending' then excluded.review_status
                else retrieval_v3.claim_rule_binding_candidates.review_status
            end,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("candidate_code")),
            int(row["claim_id"]),
            row.get("source_contract_rule_id"),
            row.get("candidate_contract_rule_id"),
            text(row.get("source_item_code")),
            text(row.get("source_rule_code")),
            text(row.get("candidate_item_code")),
            text(row.get("candidate_rule_code")),
            text(row.get("candidate_lane")),
            text(row.get("hint_status") or "current_rule_candidate"),
            json_param(row.get("required_facts_present") or {}),
            text(row.get("routed_by_profile")),
            text(row.get("candidate_predicate")),
            text(row.get("candidate_object_role")),
            text(row.get("reason_hash")),
            text(row.get("candidate_reason")),
            json_param(row.get("candidate_payload") or {}),
        ),
    )
    fetched = cur.fetchone()
    return int(fetched["id"]) if fetched and fetched.get("id") is not None else None


def execute_plan(cur: Any, plan: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in plan.get("candidates") or []:
        upsert_candidate(cur, row)
        counts["retrieval_v3.claim_rule_binding_candidates"] += 1
    return dict(sorted(counts.items()))


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v3 cross-rule router",
        "",
        f"- item_code: `{payload.get('item_code', '')}`",
        f"- source_rule_code: `{payload.get('source_rule_code', '')}`",
        f"- mode: `{'execute' if payload.get('executed') else 'dry_run'}`",
        f"- write_db: `{bool(payload.get('write_db'))}`",
        "",
        "## Totals",
        "",
    ]
    for key, value in sorted(totals.items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Candidate Rule Counts", ""])
    for rule_code, count in sorted((payload.get("candidate_rule_counts") or {}).items()):
        lines.append(f"- {rule_code}: `{count}`")
    lines.extend(["", "## Sample Candidates", ""])
    for row in payload.get("sample_candidates") or []:
        lines.append(
            f"- `{row.get('emperor_name')}` / `{row.get('candidate_rule_code')}` / `{row.get('object_name')}`: {row.get('claim_summary')}"
        )
    return "\n".join(lines) + "\n"


def run_router(
    *,
    env_file: Path | None,
    dsn_env: str,
    item_code: str,
    source_rule_code: str,
    emperors: Sequence[str],
    canonical_only: bool,
    execute: bool,
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            plan = build_plan(
                cur,
                item_code=item_code,
                source_rule_code=source_rule_code,
                emperors=emperors,
                canonical_only=canonical_only,
            )
            plan["write_db"] = execute
            if not execute:
                conn.rollback()
                return plan
            plan["executed_counts"] = execute_plan(cur, plan)
            plan["executed"] = True
        conn.commit()
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill cross-rule candidates from accepted retrieval_v3 claims.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--item-code", default="I5B")
    parser.add_argument("--source-rule-code", default="appointment_delegation")
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--all-duplicates", action="store_true", help="Do not collapse semantic duplicate candidates.")
    parser.add_argument("--execute", action="store_true", help="Actually write claim_rule_binding_candidates. Omit for dry-run.")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_router(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        item_code=args.item_code,
        source_rule_code=args.source_rule_code,
        emperors=tuple(args.emperor or ()),
        canonical_only=not args.all_duplicates,
        execute=args.execute,
        schema_name=args.pg_schema,
    )
    write_json(args.output_json, payload)
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
