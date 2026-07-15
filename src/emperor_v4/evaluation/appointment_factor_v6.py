from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash
from emperor_v4.evaluation.appointment_delegation_v3_parity import FACTOR_OPTIONS


WORKLIST_SCHEMA_VERSION = "appointment-factor-observation-worklist-v6"
RESPONSE_SCHEMA_VERSION = "appointment-factor-observation-response-v6"
GOLD_SCHEMA_VERSION = "appointment-factor-observation-gold-v6"
REPORT_SCHEMA_VERSION = "appointment-factor-observation-qualification-v6"
CONTRACT_VERSION = "appointment-delegation-factor-observation-v6"

SOURCE_FACTOR = "source_factor"
MODEL_FACTOR_NAMES = tuple(name for name in FACTOR_OPTIONS if name != SOURCE_FACTOR)
SIDE_VALUES = frozenset({"positive", "negative"})
DECISION_STATUSES = frozenset({"resolved", "insufficient_coverage"})
MECHANICAL_OBSERVATION_FIELDS = frozenset(
    {
        "jurisdiction_scope",
        "cross_domain",
        "institution_forming",
        "duration",
        "one_off_basis",
        "explicit_ruler_action",
        "scoped_responsibility",
        "linked_feedback",
        "distinct_authorization_count",
        "distinct_observation_count",
        "predecision_pressure_refs",
    }
)
JURISDICTION_SCOPES = frozenset(
    {"nominal", "local_bounded", "major_affairs", "national_or_strategic"}
)
DURATION_VALUES = frozenset({"one_off", "bounded", "long_term"})
ONE_OFF_BASIS_VALUES = frozenset(
    {"explicit_one_off", "bounded_absence", "not_established"}
)


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} 字段必须精确为 {sorted(expected)}")


def _refs(value: Any, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    refs = tuple(str(ref).strip() for ref in value or ())
    if (not allow_empty and not refs) or "" in refs or len(refs) != len(set(refs)):
        raise ValueError(f"{label} 必须为非空且唯一的引用列表")
    return refs


def _validate_resolution(
    factor_name: str,
    resolution: Mapping[str, Any],
    *,
    allowed_assertion_refs: frozenset[str] | None,
) -> None:
    _require_exact_keys(
        resolution,
        {"decision_status", "option_code", "reason", "assertion_refs"},
        f"{factor_name} resolution",
    )
    status = resolution.get("decision_status")
    option = resolution.get("option_code")
    if status not in DECISION_STATUSES:
        raise ValueError(f"{factor_name} decision_status 非法")
    if status == "resolved" and option not in FACTOR_OPTIONS[factor_name]:
        raise ValueError(f"{factor_name} option_code 非法")
    if status == "insufficient_coverage" and option is not None:
        raise ValueError(f"{factor_name} 证据不足时 option_code 必须为空")
    if not str(resolution.get("reason") or "").strip():
        raise ValueError(f"{factor_name} reason 缺失")
    refs = frozenset(
        _refs(
            resolution.get("assertion_refs"),
            label=f"{factor_name}.assertion_refs",
            allow_empty=status == "insufficient_coverage",
        )
    )
    if allowed_assertion_refs is not None and not refs <= allowed_assertion_refs:
        raise ValueError(f"{factor_name} Assertion lineage 越出冻结 slot")


def _validate_mechanical_observations(
    observations: Mapping[str, Any], *, assertion_refs: frozenset[str]
) -> None:
    _require_exact_keys(
        observations,
        set(MECHANICAL_OBSERVATION_FIELDS),
        "mechanical_observations",
    )
    if observations.get("jurisdiction_scope") not in JURISDICTION_SCOPES:
        raise ValueError("jurisdiction_scope 非法")
    if observations.get("duration") not in DURATION_VALUES:
        raise ValueError("duration 非法")
    if observations.get("one_off_basis") not in ONE_OFF_BASIS_VALUES:
        raise ValueError("one_off_basis 非法")
    for field in (
        "cross_domain",
        "institution_forming",
        "explicit_ruler_action",
        "scoped_responsibility",
        "linked_feedback",
    ):
        if type(observations.get(field)) is not bool:
            raise ValueError(f"{field} 必须为布尔值")
    for field in ("distinct_authorization_count", "distinct_observation_count"):
        value = observations.get(field)
        if type(value) is not int or value < 0:
            raise ValueError(f"{field} 必须为非负整数")
    pressure_refs = frozenset(
        _refs(
            observations.get("predecision_pressure_refs"),
            label="predecision_pressure_refs",
            allow_empty=True,
        )
    )
    if not pressure_refs <= assertion_refs:
        raise ValueError("predecision_pressure_refs 越出冻结 slot")


def _validate_mechanical_factor_support(
    factor_name: str,
    resolution: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> None:
    if resolution["decision_status"] == "insufficient_coverage":
        return
    option = resolution["option_code"]
    scope = observations["jurisdiction_scope"]
    duration = observations["duration"]
    supported = True
    if factor_name == "appointment_importance":
        supported = {
            "nominal_or_light": scope == "nominal",
            "real_bounded": (
                scope == "local_bounded"
                and observations["cross_domain"] is False
                and observations["institution_forming"] is False
            ),
            "major_affairs": scope == "major_affairs" or (
                observations["cross_domain"] is True and duration != "long_term"
            ),
            "critical_national_or_long_term": (
                scope == "national_or_strategic"
                or observations["institution_forming"] is True
                or duration == "long_term"
            ),
        }[option]
    elif factor_name == "appointment_effect":
        supported = observations["linked_feedback"] is True
    elif factor_name == "continuity_factor":
        supported = {
            "short_or_one_off": (
                observations["distinct_authorization_count"] <= 1
                and observations["distinct_observation_count"] <= 1
                and observations["one_off_basis"]
                in {"explicit_one_off", "bounded_absence"}
            ),
            "stable": (
                observations["distinct_authorization_count"] == 1
                and observations["distinct_observation_count"] >= 2
            ),
            "long_term_multi_stage": observations[
                "distinct_authorization_count"
            ]
            >= 2,
        }[option]
    elif factor_name == "attribution_factor":
        supported = {
            "indirect": True,
            "direct": observations["explicit_ruler_action"] is True,
            "direct_under_pressure": (
                observations["explicit_ruler_action"] is True
                and bool(observations["predecision_pressure_refs"])
            ),
        }[option]
    elif factor_name == "context_factor":
        supported = {
            "weak_but_applicable": observations["explicit_ruler_action"] is True,
            "clear": (
                observations["explicit_ruler_action"] is True
                and observations["scoped_responsibility"] is True
            ),
            "core_mechanism_direct": (
                observations["explicit_ruler_action"] is True
                and observations["scoped_responsibility"] is True
                and observations["linked_feedback"] is True
            ),
        }[option]
    if not supported:
        raise ValueError(f"{factor_name}.{option} 缺少 mechanical_observations 支撑")


def build_appointment_factor_v6_worklist(
    *,
    task_code: str,
    units: Sequence[Mapping[str, Any]],
    deterministic_source_factors: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """冻结 canonical observation slots，并合入确定性的史源因子。"""

    if not str(task_code).strip() or not units:
        raise ValueError("v6 worklist 需要 task_code 和至少一个 unit")
    frozen_units: list[dict[str, Any]] = []
    seen_slots: set[str] = set()
    for unit in units:
        _require_exact_keys(unit, {"unit_ref", "slots"}, "v6 upstream unit")
        unit_ref = str(unit.get("unit_ref") or "").strip()
        slots = tuple(unit.get("slots") or ())
        if not unit_ref or not slots:
            raise ValueError("v6 upstream unit 缺少 unit_ref 或 slots")
        frozen_slots = []
        for slot in slots:
            _require_exact_keys(
                slot,
                {
                    "slot_id",
                    "side",
                    "episode_refs",
                    "assertion_refs",
                    "mechanical_observations",
                },
                f"{unit_ref} upstream slot",
            )
            slot_id = str(slot.get("slot_id") or "").strip()
            if not slot_id or slot_id in seen_slots:
                raise ValueError("slot_id 必须全局非空且唯一")
            if slot.get("side") not in SIDE_VALUES:
                raise ValueError(f"{slot_id} side 非法")
            episode_refs = _refs(slot.get("episode_refs"), label=f"{slot_id}.episode_refs")
            assertion_refs = _refs(
                slot.get("assertion_refs"), label=f"{slot_id}.assertion_refs"
            )
            _validate_mechanical_observations(
                slot.get("mechanical_observations") or {},
                assertion_refs=frozenset(assertion_refs),
            )
            source_factor = deterministic_source_factors.get(slot_id)
            if source_factor is None:
                raise ValueError(f"{slot_id} 缺少 deterministic source_factor")
            _validate_resolution(
                SOURCE_FACTOR,
                source_factor,
                allowed_assertion_refs=frozenset(assertion_refs),
            )
            if source_factor["decision_status"] != "resolved":
                raise ValueError("deterministic source_factor 必须已解析")
            frozen_slots.append(
                {
                    "slot_id": slot_id,
                    "side": slot["side"],
                    "episode_refs": list(episode_refs),
                    "assertion_refs": list(assertion_refs),
                    "mechanical_observations": deepcopy(
                        slot["mechanical_observations"]
                    ),
                    "deterministic_factors": {SOURCE_FACTOR: deepcopy(source_factor)},
                }
            )
            seen_slots.add(slot_id)
        frozen_units.append({"unit_ref": unit_ref, "slots": frozen_slots})
    if set(deterministic_source_factors) != seen_slots:
        raise ValueError("deterministic source_factor 必须精确覆盖冻结 slots")
    worklist = {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "status": "canonical_observation_slots_frozen",
        "contract_version": CONTRACT_VERSION,
        "task_code": task_code,
        "rule_code": "appointment_delegation",
        "qualification_join_key": "slot_id",
        "model_factor_names": list(MODEL_FACTOR_NAMES),
        "source_factor_owner": "deterministic_lineage",
        "units": frozen_units,
        "runtime_policy": {
            "mode": "offline_report_only",
            "score_computation_allowed": False,
            "database_writes_allowed": False,
            "formal_acceptance_allowed": False,
        },
    }
    worklist["worklist_sha256"] = canonical_hash(worklist)
    validate_appointment_factor_v6_worklist(worklist)
    return worklist


def validate_appointment_factor_v6_worklist(worklist: Mapping[str, Any]) -> None:
    _require_exact_keys(
        worklist,
        {
            "schema_version",
            "status",
            "contract_version",
            "task_code",
            "rule_code",
            "qualification_join_key",
            "model_factor_names",
            "source_factor_owner",
            "units",
            "runtime_policy",
            "worklist_sha256",
        },
        "appointment factor v6 worklist",
    )
    unsigned = dict(worklist)
    stored_hash = unsigned.pop("worklist_sha256", None)
    if (
        worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION
        or worklist.get("status") != "canonical_observation_slots_frozen"
        or worklist.get("contract_version") != CONTRACT_VERSION
        or worklist.get("rule_code") != "appointment_delegation"
        or worklist.get("qualification_join_key") != "slot_id"
        or worklist.get("model_factor_names") != list(MODEL_FACTOR_NAMES)
        or worklist.get("source_factor_owner") != "deterministic_lineage"
        or worklist.get("runtime_policy")
        != {
            "mode": "offline_report_only",
            "score_computation_allowed": False,
            "database_writes_allowed": False,
            "formal_acceptance_allowed": False,
        }
        or stored_hash != canonical_hash(unsigned)
    ):
        raise ValueError("appointment factor v6 worklist 绑定或版本非法")
    slot_ids: list[str] = []
    unit_refs: list[str] = []
    for unit in worklist.get("units") or ():
        _require_exact_keys(unit, {"unit_ref", "slots"}, "v6 worklist unit")
        unit_refs.append(str(unit.get("unit_ref") or ""))
        for slot in unit.get("slots") or ():
            slot_ids.append(str(slot.get("slot_id") or ""))
            if set(slot) != {
                "slot_id",
                "side",
                "episode_refs",
                "assertion_refs",
                "mechanical_observations",
                "deterministic_factors",
            }:
                raise ValueError("v6 slot 字段非法")
            if slot.get("side") not in SIDE_VALUES:
                raise ValueError("v6 slot side 非法")
            assertions = frozenset(
                _refs(slot.get("assertion_refs"), label="slot.assertion_refs")
            )
            _refs(slot.get("episode_refs"), label="slot.episode_refs")
            _validate_mechanical_observations(
                slot.get("mechanical_observations") or {}, assertion_refs=assertions
            )
            factors = slot.get("deterministic_factors") or {}
            if set(factors) != {SOURCE_FACTOR}:
                raise ValueError("v6 slot 只能携带 deterministic source_factor")
            _validate_resolution(
                SOURCE_FACTOR,
                factors[SOURCE_FACTOR],
                allowed_assertion_refs=assertions,
            )
    if not slot_ids or "" in slot_ids or len(slot_ids) != len(set(slot_ids)):
        raise ValueError("v6 slot_id 必须全局非空且唯一")
    if "" in unit_refs or len(unit_refs) != len(set(unit_refs)):
        raise ValueError("v6 unit_ref 必须非空且唯一")


def build_appointment_factor_v6_gold(
    worklist: Mapping[str, Any], gold_slots: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """冻结只包含模型负责因子的 Gold；source_factor 不进入模型比较。"""

    validate_appointment_factor_v6_worklist(worklist)
    slots = _validate_candidate_slots(worklist, gold_slots, require_exact=True)
    gold = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "status": "human_factor_gold_frozen",
        "contract_version": CONTRACT_VERSION,
        "worklist_sha256": worklist["worklist_sha256"],
        "slots": deepcopy(slots),
    }
    gold["gold_sha256"] = canonical_hash(gold)
    return gold


def _validate_candidate_slots(
    worklist: Mapping[str, Any],
    slots: Sequence[Mapping[str, Any]],
    *,
    require_exact: bool,
) -> list[dict[str, Any]]:
    canonical = {
        slot["slot_id"]: slot
        for unit in worklist["units"]
        for slot in unit["slots"]
    }
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for slot in slots:
        _require_exact_keys(slot, {"slot_id", "side", "factors"}, "v6 candidate slot")
        slot_id = str(slot.get("slot_id") or "")
        if not slot_id or slot_id in seen:
            raise ValueError("response slot_id 必须非空且唯一")
        if slot.get("side") not in SIDE_VALUES:
            raise ValueError("response slot side 非法")
        factors = slot.get("factors") or {}
        if set(factors) != set(MODEL_FACTOR_NAMES):
            raise ValueError("模型必须只填写且完整覆盖允许的模型因子")
        allowed_refs = (
            frozenset(canonical[slot_id]["assertion_refs"])
            if slot_id in canonical
            else None
        )
        for factor_name, resolution in factors.items():
            _validate_resolution(
                factor_name,
                resolution,
                allowed_assertion_refs=allowed_refs,
            )
            if slot_id in canonical:
                _validate_mechanical_factor_support(
                    factor_name,
                    resolution,
                    canonical[slot_id]["mechanical_observations"],
                )
        validated.append(deepcopy(dict(slot)))
        seen.add(slot_id)
    if require_exact and seen != set(canonical):
        raise ValueError("Gold slots 必须精确唯一覆盖 canonical slots")
    if require_exact and any(
        slot["side"] != canonical[slot["slot_id"]]["side"] for slot in validated
    ):
        raise ValueError("Gold slot side 必须与 canonical slot 一致")
    return validated


def evaluate_appointment_factor_v6_qualification(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> dict[str, Any]:
    """按 slot_id join；结构不一致时保留诊断，且不比较该槽因子。"""

    validate_appointment_factor_v6_worklist(worklist)
    unsigned_gold = dict(gold)
    stored_gold_hash = unsigned_gold.pop("gold_sha256", None)
    if (
        gold.get("schema_version") != GOLD_SCHEMA_VERSION
        or gold.get("status") != "human_factor_gold_frozen"
        or gold.get("contract_version") != CONTRACT_VERSION
        or gold.get("worklist_sha256") != worklist.get("worklist_sha256")
        or stored_gold_hash != canonical_hash(unsigned_gold)
    ):
        raise ValueError("appointment factor v6 Gold 绑定或版本非法")
    gold_slots = _validate_candidate_slots(worklist, gold.get("slots") or (), require_exact=True)

    _require_exact_keys(
        response,
        {
            "schema_version",
            "status",
            "contract_version",
            "worklist_sha256",
            "response_origin",
            "slots",
        },
        "appointment factor v6 response",
    )
    if (
        response.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or response.get("status") != "factor_observation_response_complete"
        or response.get("contract_version") != CONTRACT_VERSION
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or not str(response.get("response_origin") or "").strip()
    ):
        raise ValueError("appointment factor v6 response 绑定或版本非法")
    response_slots = _validate_candidate_slots(
        worklist, response.get("slots") or (), require_exact=False
    )

    canonical = {
        slot["slot_id"]: slot
        for unit in worklist["units"]
        for slot in unit["slots"]
    }
    candidate_by_id = {slot["slot_id"]: slot for slot in response_slots}
    gold_by_id = {slot["slot_id"]: slot for slot in gold_slots}
    missing = sorted(set(canonical) - set(candidate_by_id))
    extra = sorted(set(candidate_by_id) - set(canonical))
    side_mismatches = [
        {
            "slot_id": slot_id,
            "expected_side": canonical[slot_id]["side"],
            "candidate_side": candidate_by_id[slot_id]["side"],
        }
        for slot_id in sorted(set(canonical) & set(candidate_by_id))
        if candidate_by_id[slot_id]["side"] != canonical[slot_id]["side"]
    ]
    side_mismatch_ids = {row["slot_id"] for row in side_mismatches}
    comparisons = []
    classes: Counter[str] = Counter()
    for slot_id in sorted(set(canonical) & set(candidate_by_id) - side_mismatch_ids):
        candidate = candidate_by_id[slot_id]
        expected = gold_by_id[slot_id]
        for factor_name in MODEL_FACTOR_NAMES:
            candidate_factor = candidate["factors"][factor_name]
            gold_factor = expected["factors"][factor_name]
            if candidate_factor["decision_status"] != gold_factor["decision_status"]:
                classification = "decision_status_mismatch"
            elif candidate_factor["decision_status"] == "insufficient_coverage":
                classification = "exact_abstention"
            elif candidate_factor["option_code"] == gold_factor["option_code"]:
                classification = "exact"
            else:
                options = tuple(FACTOR_OPTIONS[factor_name])
                distance = abs(
                    options.index(candidate_factor["option_code"])
                    - options.index(gold_factor["option_code"])
                )
                classification = "adjacent" if distance == 1 else "nonadjacent"
                if factor_name == "appointment_effect":
                    positive = {"major_success", "normal_success", "weak_feedback"}
                    if (candidate_factor["option_code"] in positive) != (
                        gold_factor["option_code"] in positive
                    ):
                        classification = "direction_error"
            classes[classification] += 1
            comparisons.append(
                {
                    "slot_id": slot_id,
                    "side": canonical[slot_id]["side"],
                    "factor_name": factor_name,
                    "candidate_decision_status": candidate_factor["decision_status"],
                    "gold_decision_status": gold_factor["decision_status"],
                    "candidate_option": candidate_factor["option_code"],
                    "gold_option": gold_factor["option_code"],
                    "classification": classification,
                }
            )

    structure_exact = not missing and not extra and not side_mismatches
    factor_exact = all(
        row["classification"] in {"exact", "exact_abstention"} for row in comparisons
    )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "appointment_factor_v6_qualification_report_ready",
        "contract_version": CONTRACT_VERSION,
        "worklist_sha256": worklist["worklist_sha256"],
        "gold_sha256": gold["gold_sha256"],
        "qualification_join_key": "slot_id",
        "structure_diagnostics": {
            "missing_slot_ids": missing,
            "extra_slot_ids": extra,
            "side_mismatches": side_mismatches,
            "structure_exact": structure_exact,
        },
        "factor_comparisons": comparisons,
        "factor_classification_counts": dict(sorted(classes.items())),
        "threshold_passed": structure_exact and factor_exact,
        "execution_audit": {
            "report_only": True,
            "model_call_count": 0,
            "score_computation_performed": False,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
            "source_factor_compared_as_model_output": False,
        },
    }
    report["report_sha256"] = canonical_hash(report)
    return report
