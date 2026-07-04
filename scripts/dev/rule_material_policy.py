from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class RuleMaterialPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RuleMaterialPolicy:
    item_code: str
    rule_code: str
    policy_code: str
    policy_version: str = "v1"
    selection_priority: int = 100
    carrier_mode: str = "obj_src_material"
    material_source: str = "obj_srcs"
    allowed_scoring_roles: frozenset[str] = frozenset()
    context_roles: frozenset[str] = frozenset()
    disallowed_scored_obj_types: frozenset[str] = frozenset()
    discouraged_scored_obj_types: frozenset[str] = frozenset()
    candidate_obj_types: frozenset[str] = frozenset()
    require_attrs: frozenset[str] = frozenset()
    calc_detail_component_paths: tuple[str, ...] = ()
    single_scored_per_chain: bool = False
    policy_payload: Mapping[str, Any] = field(default_factory=dict)


RuleMaterialPolicyMap = Mapping[str, RuleMaterialPolicy]


def _text(value: object) -> str:
    return str(value or "").strip()


def _text_values(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item).strip() for item in value if str(item or "").strip())
    return ()


def _text_set(value: object) -> frozenset[str]:
    return frozenset(_text_values(value))


def _payload(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def policy_from_mapping(row: Mapping[str, object]) -> RuleMaterialPolicy:
    return RuleMaterialPolicy(
        item_code=_text(row.get("item_code")),
        rule_code=_text(row.get("rule_code")),
        policy_code=_text(row.get("policy_code") or "default_material_policy"),
        policy_version=_text(row.get("policy_version") or "v1"),
        selection_priority=int(row.get("selection_priority") or 100),
        carrier_mode=_text(row.get("carrier_mode") or "obj_src_material"),
        material_source=_text(row.get("material_source") or "obj_srcs"),
        allowed_scoring_roles=_text_set(row.get("allowed_scoring_roles")),
        context_roles=_text_set(row.get("context_roles")),
        disallowed_scored_obj_types=_text_set(row.get("disallowed_scored_obj_types")),
        discouraged_scored_obj_types=_text_set(row.get("discouraged_scored_obj_types")),
        candidate_obj_types=_text_set(row.get("candidate_obj_types")),
        require_attrs=_text_set(row.get("require_attrs")),
        calc_detail_component_paths=_text_values(row.get("calc_detail_component_paths")),
        single_scored_per_chain=bool(row.get("single_scored_per_chain")),
        policy_payload=_payload(row.get("policy_payload")),
    )


def policy_map_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, RuleMaterialPolicy]:
    policies: dict[str, RuleMaterialPolicy] = {}
    for row in rows:
        policy = policy_from_mapping(row)
        if not policy.rule_code:
            continue
        existing = policies.get(policy.rule_code)
        if existing is None or policy.selection_priority < existing.selection_priority:
            policies[policy.rule_code] = policy
    return policies


def fetch_policy_map(
    cur: Any,
    *,
    item_code: str,
    rule_codes: Sequence[str] = (),
) -> dict[str, RuleMaterialPolicy]:
    clauses = ["status = 'active'", "(item_code = %s or item_code = '')"]
    params: list[object] = [item_code]
    if rule_codes:
        clauses.append("rule_code = any(%s)")
        params.append(list(rule_codes))
    cur.execute(
        f"""
        select
            item_code,
            rule_code,
            policy_code,
            policy_version,
            selection_priority,
            carrier_mode,
            material_source,
            allowed_scoring_roles,
            context_roles,
            disallowed_scored_obj_types,
            discouraged_scored_obj_types,
            candidate_obj_types,
            require_attrs,
            calc_detail_component_paths,
            single_scored_per_chain,
            policy_payload
          from eval_rule_material_policies
         where {" and ".join(clauses)}
         order by
            case when item_code = %s then 0 else 1 end,
            selection_priority,
            id
        """,
        tuple(params + [item_code]),
    )
    columns = [desc.name for desc in cur.description]
    return policy_map_from_rows([dict(zip(columns, row)) for row in cur.fetchall()])


def fetch_policy_map_from_dsn(
    *,
    dsn: str,
    item_code: str,
    rule_codes: Sequence[str] = (),
) -> dict[str, RuleMaterialPolicy]:
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            return fetch_policy_map(cur, item_code=item_code, rule_codes=rule_codes)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    if value in (None, ""):
        return ()
    return (value,)


def _matches_condition(
    condition: Mapping[str, object],
    *,
    side: str,
    obj_type: str,
    obj_name: str,
) -> bool:
    expected_side = _text(condition.get("side"))
    if expected_side and side != expected_side:
        return False
    sides = {_text(value) for value in _sequence(condition.get("sides")) if _text(value)}
    if sides and side not in sides:
        return False
    expected_type = _text(condition.get("obj_type"))
    if expected_type and obj_type != expected_type:
        return False
    obj_types = {_text(value) for value in _sequence(condition.get("obj_types")) if _text(value)}
    if obj_types and obj_type not in obj_types:
        return False
    names = {_text(value) for value in _sequence(condition.get("names")) if _text(value)}
    if names and obj_name not in names:
        return False
    prefixes = tuple(_text(value) for value in _sequence(condition.get("name_prefixes")) if _text(value))
    if prefixes and not obj_name.startswith(prefixes):
        return False
    return True


def _role_from_direction_defaults(defaults: Mapping[str, object], side: str) -> str:
    if side != "negative" and _text(defaults.get("non_negative")):
        return _text(defaults.get("non_negative"))
    for key in (side, "default"):
        role = _text(defaults.get(key))
        if role:
            return role
    return ""


def candidate_scoring_role_from_policy(
    policy: RuleMaterialPolicy,
    *,
    side: str,
    obj_type: str,
    obj_name: str,
) -> str:
    payload = _mapping(policy.policy_payload)
    context_by_type = _mapping(payload.get("context_roles_by_obj_type"))
    context_role = _text(context_by_type.get(obj_type))
    if context_role:
        return context_role

    raw_rules = payload.get("candidate_role_rules")
    if isinstance(raw_rules, list):
        for raw_rule in raw_rules:
            rule = _mapping(raw_rule)
            role = _text(rule.get("role"))
            if not role:
                continue
            if _matches_condition(_mapping(rule.get("when")), side=side, obj_type=obj_type, obj_name=obj_name):
                return role

    default_role = _role_from_direction_defaults(
        _mapping(payload.get("default_scoring_roles_by_direction")),
        side,
    )
    if default_role:
        return default_role
    if policy.allowed_scoring_roles:
        return sorted(policy.allowed_scoring_roles)[0]
    if policy.context_roles:
        return sorted(policy.context_roles)[0]
    return "source_context"

