from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash


RULE_CODE = "appointment_delegation"
FACTOR_SCHEMA_VERSION = "appointment-delegation-v3-parity-factors-v1"
JUDGMENT_POLICY_VERSION = "appointment-delegation-v3-parity-judgment-v1"
SCORING_FORMULA_VERSION = "appointment-delegation-v3-density-decay-v1"
SCORE_CONTRIBUTION_SCHEMA_VERSION = "score-contribution-v3-parity-shadow-v1"

FACTOR_OPTIONS: dict[str, dict[str, Decimal]] = {
    "appointment_importance": {
        "nominal_or_light": Decimal("0.6"),
        "real_bounded": Decimal("1.0"),
        "major_affairs": Decimal("1.25"),
        "critical_national_or_long_term": Decimal("1.4"),
    },
    "appointment_effect": {
        "major_success": Decimal("1.5"),
        "normal_success": Decimal("1.0"),
        "weak_feedback": Decimal("0.4"),
        "poor_result": Decimal("-0.8"),
        "major_direct_damage": Decimal("-1.8"),
        "structural_continuing_damage": Decimal("-2.6"),
    },
    "continuity_factor": {
        "short_or_one_off": Decimal("0.85"),
        "stable": Decimal("1.0"),
        "long_term_multi_stage": Decimal("1.15"),
    },
    "attribution_factor": {
        "indirect": Decimal("0.8"),
        "direct": Decimal("1.0"),
        "direct_under_pressure": Decimal("1.1"),
    },
    "source_factor": {
        "weak_or_compressed": Decimal("0.75"),
        "standard": Decimal("1.0"),
        "complete_direct_chain": Decimal("1.1"),
    },
    "context_factor": {
        "weak_but_applicable": Decimal("0.7"),
        "clear": Decimal("1.0"),
        "core_mechanism_direct": Decimal("1.1"),
    },
}
FACTOR_NAMES = tuple(FACTOR_OPTIONS)
SIDE_VALUES = frozenset({"positive", "negative"})

MATERIAL_SCORE_CAP = Decimal("4.0")
EVIDENCE_FACTOR_MIN = Decimal("0.45")
EVIDENCE_FACTOR_MAX = Decimal("1.25")
MATERIAL_DECAY = Decimal("1.0")
EVENT_DECAY = Decimal("1.0")
OBJECT_DECAY = Decimal("0.5")
POSITIVE_LANE_SCALE = Decimal("1.5")
NEGATIVE_LANE_SCALE = Decimal("1.0")


def _quant(value: Decimal, places: str = "0.0001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _number(value: Decimal) -> float:
    return float(_quant(value))


def _clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def observation_fingerprint(unit: Mapping[str, Any]) -> str:
    return canonical_hash(
        {
            "unit_ref": unit["unit_ref"],
            "factor_observations": unit["factor_observations"],
        }
    )


def validate_parity_manifest(
    manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    *,
    allowed_proposal_statuses: frozenset[str] = frozenset(
        {"human_reviewed_shadow"}
    ),
    allowed_review_bases: frozenset[str] = frozenset(
        {"existing_v4_observations_plus_v3_calibration"}
    ),
) -> None:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "frozen_v3_parity_shadow_input"
        or manifest.get("rule_code") != RULE_CODE
        or manifest.get("factor_schema_version") != FACTOR_SCHEMA_VERSION
        or manifest.get("judgment_policy_version") != JUDGMENT_POLICY_VERSION
        or manifest.get("scoring_formula_version") != SCORING_FORMULA_VERSION
    ):
        raise ValueError("V3 parity manifest 版本或状态非法")

    runtime = manifest.get("runtime_policy") or {}
    if (
        runtime.get("mode") != "offline_report_only_shadow"
        or runtime.get("model_calls_allowed") is not False
        or runtime.get("database_writes_allowed") is not False
        or runtime.get("formal_acceptance_allowed") is not False
    ):
        raise ValueError("V3 parity shadow 只允许离线、零模型、零数据库写入")

    if source_manifest.get("rule_code") != RULE_CODE:
        raise ValueError("V3 parity source manifest rule_code 非法")
    source_units = tuple(source_manifest.get("rule_evidence_units") or ())
    unit_by_ref = {str(row.get("unit_ref")): row for row in source_units}
    if not source_units or "None" in unit_by_ref or len(unit_by_ref) != len(source_units):
        raise ValueError("V3 parity source RuleEvidenceUnit identity 非法")

    assertion_by_ref = {
        str(row.get("assertion_ref")): row
        for row in source_manifest.get("assertions") or ()
    }
    episode_by_ref = {
        str(row.get("episode_ref")): row
        for row in source_manifest.get("historical_episodes") or ()
    }
    proposals = tuple(manifest.get("factor_judgment_proposals") or ())
    proposal_by_ref = {str(row.get("unit_ref")): row for row in proposals}
    if (
        "None" in proposal_by_ref
        or len(proposal_by_ref) != len(proposals)
        or set(proposal_by_ref) != set(unit_by_ref)
    ):
        raise ValueError("V3 parity proposal 必须完整且唯一覆盖 RuleEvidenceUnit")

    material_codes: set[str] = set()
    for unit_ref, proposal in proposal_by_ref.items():
        unit = unit_by_ref[unit_ref]
        if (
            proposal.get("proposal_status") not in allowed_proposal_statuses
            or proposal.get("review_basis") not in allowed_review_bases
            or not str(proposal.get("reviewer") or "").strip()
            or proposal.get("source_observation_fingerprint")
            != observation_fingerprint(unit)
        ):
            raise ValueError(f"{unit_ref} proposal 来源、状态或观察 fingerprint 非法")

        allowed_assertions = {
            str(ref)
            for episode_ref in unit.get("episode_refs") or ()
            for ref in (episode_by_ref.get(str(episode_ref)) or {}).get(
                "assertion_refs", ()
            )
        }
        if not allowed_assertions or not allowed_assertions <= set(assertion_by_ref):
            raise ValueError(f"{unit_ref} source assertion lineage 不完整")

        materials = tuple(proposal.get("factor_materials") or ())
        if not materials:
            raise ValueError(f"{unit_ref} proposal 缺少 factor_material")
        for material in materials:
            if any(key in material for key in ("score", "value_num", "raw_score")):
                raise ValueError("Factor proposal 不得携带模型或人工输入数值")
            code = str(material.get("material_code") or "")
            if not code or code in material_codes:
                raise ValueError("factor_material code 缺失或重复")
            material_codes.add(code)
            if material.get("side") not in SIDE_VALUES:
                raise ValueError(f"{code} side 非法")
            if not str(material.get("event_group") or "").strip():
                raise ValueError(f"{code} event_group 缺失")
            factors = material.get("factors") or {}
            if set(factors) != set(FACTOR_NAMES):
                raise ValueError(f"{code} factors 必须完整且唯一覆盖 V3 有限因子")
            material_refs: set[str] = set()
            for factor_name in FACTOR_NAMES:
                factor = factors[factor_name]
                if any(key in factor for key in ("score", "value_num", "numeric_value")):
                    raise ValueError("Factor proposal 不得携带数值映射")
                option_code = str(factor.get("option_code") or "")
                if option_code not in FACTOR_OPTIONS[factor_name]:
                    raise ValueError(f"{code}.{factor_name} option_code 非法")
                if not str(factor.get("reason") or "").strip():
                    raise ValueError(f"{code}.{factor_name} 缺少 reason")
                refs = tuple(str(ref) for ref in factor.get("assertion_refs") or ())
                if (
                    not refs
                    or len(refs) != len(set(refs))
                    or not set(refs) <= allowed_assertions
                ):
                    raise ValueError(f"{code}.{factor_name} Assertion lineage 非法")
                material_refs.update(refs)
            if not material_refs:
                raise ValueError(f"{code} 未消费 Assertion")


def evaluate_factor_proposal(
    proposal: Mapping[str, Any],
    unit: Mapping[str, Any],
    source_v4_judgment_fingerprint: str,
) -> dict[str, Any]:
    materials = []
    for material in proposal["factor_materials"]:
        choices = {
            name: {
                "option_code": material["factors"][name]["option_code"],
                "reason": material["factors"][name]["reason"],
                "assertion_refs": list(material["factors"][name]["assertion_refs"]),
                "deterministic_value": _number(
                    FACTOR_OPTIONS[name][material["factors"][name]["option_code"]]
                ),
            }
            for name in FACTOR_NAMES
        }
        evidence_factor = _clamp(
            FACTOR_OPTIONS["attribution_factor"][
                choices["attribution_factor"]["option_code"]
            ]
            * FACTOR_OPTIONS["source_factor"][
                choices["source_factor"]["option_code"]
            ]
            * FACTOR_OPTIONS["context_factor"][
                choices["context_factor"]["option_code"]
            ],
            EVIDENCE_FACTOR_MIN,
            EVIDENCE_FACTOR_MAX,
        )
        raw = (
            FACTOR_OPTIONS["appointment_importance"][
                choices["appointment_importance"]["option_code"]
            ]
            * FACTOR_OPTIONS["appointment_effect"][
                choices["appointment_effect"]["option_code"]
            ]
            * FACTOR_OPTIONS["continuity_factor"][
                choices["continuity_factor"]["option_code"]
            ]
            * evidence_factor
        )
        raw = _clamp(raw, -MATERIAL_SCORE_CAP, MATERIAL_SCORE_CAP)
        side = str(material["side"])
        if (raw > 0 and side != "positive") or (raw < 0 and side != "negative"):
            raise ValueError(f"{material['material_code']} side 与 appointment_effect 符号冲突")
        refs = sorted(
            {
                ref
                for choice in choices.values()
                for ref in choice["assertion_refs"]
            }
        )
        materials.append(
            {
                "material_code": material["material_code"],
                "event_group": material["event_group"],
                "side": side,
                "factor_choices": choices,
                "evidence_factor": _number(evidence_factor),
                "signed_material_score": _number(raw),
                "absolute_material_score": _number(abs(raw)),
                "supporting_assertion_refs": refs,
            }
        )

    semantic = {
        "unit_ref": unit["unit_ref"],
        "unit_observation_fingerprint": observation_fingerprint(unit),
        "source_v4_judgment_fingerprint": source_v4_judgment_fingerprint,
        "factor_materials": materials,
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "judgment_policy_version": JUDGMENT_POLICY_VERSION,
    }
    fingerprint = canonical_hash(semantic)
    return {
        "judgment_id": f"JDG-V3P-{fingerprint[:16].upper()}",
        "judgment_status": "human_reviewed_shadow_proposal",
        "rule_code": RULE_CODE,
        "ruler": unit["ruler"],
        "person": unit["person"],
        "rule_evidence_unit_ref": unit["unit_ref"],
        "source_observation_fingerprint": observation_fingerprint(unit),
        "source_v4_judgment_fingerprint": source_v4_judgment_fingerprint,
        "prior_v4_observations": unit["factor_observations"],
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "judgment_policy_version": JUDGMENT_POLICY_VERSION,
        "reviewer": proposal["reviewer"],
        "review_basis": proposal["review_basis"],
        "factor_materials": materials,
        "semantic_fingerprint": fingerprint,
        "model_call_count": 0,
        "formal_acceptance_performed": False,
    }


def build_score_contribution(judgment: Mapping[str, Any]) -> dict[str, Any]:
    positive = sum(
        (
            Decimal(str(row["absolute_material_score"]))
            for row in judgment["factor_materials"]
            if row["side"] == "positive"
        ),
        Decimal("0"),
    )
    negative = sum(
        (
            Decimal(str(row["absolute_material_score"]))
            for row in judgment["factor_materials"]
            if row["side"] == "negative"
        ),
        Decimal("0"),
    )
    semantic = {
        "judgment_ref": judgment["judgment_id"],
        "judgment_fingerprint": judgment["semantic_fingerprint"],
        "scoring_formula_version": SCORING_FORMULA_VERSION,
        "evaluation_scope": "v3_parity_shadow_only",
    }
    fingerprint = canonical_hash(semantic)
    return {
        "score_contribution_id": f"SC-V3P-{fingerprint[:16].upper()}",
        "score_contribution_schema_version": SCORE_CONTRIBUTION_SCHEMA_VERSION,
        "contribution_status": "shadow",
        "judgment_ref": judgment["judgment_id"],
        "ruler": judgment["ruler"],
        "person": judgment["person"],
        "rule_evidence_unit_ref": judgment["rule_evidence_unit_ref"],
        "primary_settlement_rule": RULE_CODE,
        "factor_materials": list(judgment["factor_materials"]),
        "positive_raw_signal_before_density": _number(positive),
        "negative_raw_signal_before_density": _number(negative),
        "raw_net_before_density": _number(positive - negative),
        "duplicate_settlement_check": "passed",
        "not_a_formal_45_point_score": True,
        "scoring_formula_version": SCORING_FORMULA_VERSION,
        "semantic_fingerprint": fingerprint,
    }


def _rank_weight(rank: int, decay: Decimal) -> Decimal:
    return Decimal(str(1 / (rank ** float(decay))))


def _aggregate_side(
    materials: Sequence[Mapping[str, Any]], side: str
) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for material in materials:
        if material["side"] == side:
            grouped[str(material["person"])][str(material["event_group"])].append(
                material
            )

    object_rows = []
    for person, events in grouped.items():
        event_rows = []
        for event_group, event_materials in events.items():
            ordered_materials = sorted(
                event_materials,
                key=lambda row: (-float(row["absolute_material_score"]), row["material_code"]),
            )
            material_rows = []
            event_value = Decimal("0")
            for rank, material in enumerate(ordered_materials, start=1):
                weight = _rank_weight(rank, MATERIAL_DECAY)
                weighted = Decimal(str(material["absolute_material_score"])) * weight
                event_value += weighted
                material_rows.append(
                    {
                        "material_code": material["material_code"],
                        "rank": rank,
                        "weight": _number(weight),
                        "absolute_material_score": material["absolute_material_score"],
                        "weighted_value": _number(weighted),
                    }
                )
            event_rows.append(
                {
                    "event_group": event_group,
                    "event_value": _number(event_value),
                    "materials": material_rows,
                }
            )
        ordered_events = sorted(
            event_rows, key=lambda row: (-float(row["event_value"]), row["event_group"])
        )
        object_value = Decimal("0")
        for rank, event in enumerate(ordered_events, start=1):
            weight = _rank_weight(rank, EVENT_DECAY)
            weighted = Decimal(str(event["event_value"])) * weight
            event.update(
                {"rank": rank, "weight": _number(weight), "weighted_value": _number(weighted)}
            )
            object_value += weighted
        object_rows.append(
            {"person": person, "object_value": _number(object_value), "events": ordered_events}
        )

    ordered_objects = sorted(
        object_rows, key=lambda row: (-float(row["object_value"]), row["person"])
    )
    lane_scale = POSITIVE_LANE_SCALE if side == "positive" else NEGATIVE_LANE_SCALE
    signal = Decimal("0")
    for rank, row in enumerate(ordered_objects, start=1):
        weight = _rank_weight(rank, OBJECT_DECAY)
        weighted = Decimal(str(row["object_value"])) * weight * lane_scale
        row.update(
            {
                "rank": rank,
                "weight": _number(weight),
                "lane_scale": _number(lane_scale),
                "weighted_value": _number(weighted),
            }
        )
        signal += weighted
    return {"side": side, "signal": _number(signal), "objects": ordered_objects}


def aggregate_rulers(
    contributions: Sequence[Mapping[str, Any]], rulers: Sequence[str]
) -> list[dict[str, Any]]:
    aggregates = []
    for ruler in sorted(rulers):
        materials = [
            {**material, "person": contribution["person"]}
            for contribution in contributions
            if contribution["ruler"] == ruler
            for material in contribution["factor_materials"]
        ]
        positive = _aggregate_side(materials, "positive")
        negative = _aggregate_side(materials, "negative")
        raw_net = Decimal(str(positive["signal"])) - Decimal(str(negative["signal"]))
        aggregates.append(
            {
                "ruler": ruler,
                "positive_signal": positive["signal"],
                "negative_signal": negative["signal"],
                "rule_raw_net": _number(raw_net),
                "rank_decay_detail": {"positive": positive, "negative": negative},
                "not_a_formal_45_point_score": True,
            }
        )
    return aggregates
