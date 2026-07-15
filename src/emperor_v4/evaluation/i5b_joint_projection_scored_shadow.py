from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.domain.boundary import draft_rule_evidence_unit
from emperor_v4.evaluation.i5b_scoring_policy import calculate_material_projection


SCHEMA_VERSION = "i5b-joint-projection-scored-shadow-report-v1"
POLICY_VERSION = "i5b-joint-projection-score-contribution-v2"
RULES = {"talent_discovery", "tolerate_talent", "anti_nepotism"}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def _rounded(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _dataset_role(unit_ref: str) -> str:
    if "-S" in unit_ref or unit_ref.startswith(("TD-S", "TT-S", "AN-S")):
        return "opened_regression"
    return "open_development"


def _object_side_score(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    ranked = sorted(values, reverse=True)
    strongest = ranked[0]
    return min(
        strongest + Decimal("0.35") * sum(ranked[1:], Decimal("0")),
        strongest * Decimal("1.5"),
        Decimal("4.0"),
    )


def _assertion_episode_trace(
    *,
    rule_code: str,
    materials: list[dict[str, Any]],
    assertion_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if assertion_payload.get("profile_code") != f"{rule_code}_chain_v1":
        raise ValueError("assertion review profile 与 scored shadow rule 不一致")
    summary = assertion_payload.get("summary") or {}
    if int(summary.get("pending_blocking_review_unit_count", -1)) != 0:
        raise ValueError("assertion review 仍有 blocking unit，不得生成 Episode trace")
    ruler_ref = str((assertion_payload.get("scope") or {}).get("ruler_ref") or "")
    if not ruler_ref.startswith("PER-"):
        raise ValueError("assertion review 必须声明 canonical ruler_ref")
    units = {
        str(item.get("unit_ref") or ""): item
        for item in _rows(assertion_payload.get("units"), "assertion review units")
    }
    episodes: list[dict[str, Any]] = []
    evidence_units: list[dict[str, Any]] = []
    assertion_link_count = 0
    for material in materials:
        unit_ref = material["unit_ref"]
        unit = units.get(unit_ref)
        if unit is None:
            continue
        if unit.get("review_disposition") != "reviewed_ready_for_episode_shadow":
            raise ValueError(f"assertion unit 尚未完成 review: {unit_ref}")
        assertions = _rows(unit.get("assertion_drafts"), f"{unit_ref} assertions")
        by_passage: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for assertion in assertions:
            passage_ref = str(assertion.get("source_passage_ref") or "")
            if not passage_ref:
                raise ValueError(f"assertion 缺少 passage lineage: {unit_ref}")
            by_passage[passage_ref].append(assertion)
        episode_members: dict[str, str] = {}
        assertion_refs: list[str] = []
        for passage_ref, passage_assertions in sorted(by_passage.items()):
            assertion_refs.extend(
                str(item.get("assertion_code") or "") for item in passage_assertions
            )
            focal_refs = sorted(
                {
                    str(ref)
                    for item in passage_assertions
                    for ref in (
                        (item.get("qualifiers") or {}).get(
                            "candidate_focal_person_refs"
                        )
                        or ()
                    )
                    if str(ref).startswith("PER-") and str(ref) != ruler_ref
                }
            )
            participants = [
                EpisodeParticipant(ruler_ref, ("ruler",), "resolved")
            ] + [
                EpisodeParticipant(ref, ("focal_person",), "resolved")
                for ref in focal_refs
            ]
            links = tuple(
                AssertionLink(
                    assertion_ref=str(item["assertion_code"]),
                    source_passage_ref=passage_ref,
                    relation="supports_episode_draft",
                    supported_fields=tuple(
                        (item.get("passage_support") or {}).get(
                            "supported_fields"
                        )
                        or ()
                    ),
                    evidence_status="draft",
                    representative=index == 0,
                )
                for index, item in enumerate(passage_assertions)
            )
            assertion_link_count += len(links)
            episode_payload = {
                "rule_code": rule_code,
                "unit_ref": unit_ref,
                "passage_ref": passage_ref,
                "assertion_refs": [item.assertion_ref for item in links],
            }
            episode_fingerprint = _hash(episode_payload)
            episode = HistoricalEpisodePacket(
                episode_id=f"EP-{episode_fingerprint[:20].upper()}",
                episode_type=f"{rule_code}_evidence_episode",
                episode_status="proposed",
                evaluation_context=ruler_ref,
                semantic_version=1,
                evidence_version=1,
                semantic_fingerprint=episode_fingerprint,
                time_start=None,
                time_end=None,
                time_precision="source_expression_only",
                locations=tuple(
                    sorted(
                        {
                            str(item["location_expression"])
                            for item in passage_assertions
                            if item.get("location_expression")
                        }
                    )
                ),
                participants=tuple(participants),
                action="；".join(
                    dict.fromkeys(str(item["predicate"]) for item in passage_assertions)
                ),
                responsibility="shadow routing only; formal attribution not accepted",
                outcome=tuple(
                    dict.fromkeys(str(item["object"]) for item in passage_assertions)
                ),
                consequence=(),
                assertion_links=links,
                conflicts=(),
                uncertainties=("draft assertions; no formal fact acceptance",),
                completeness={
                    "identity": "complete",
                    "time": "partial",
                    "action": "complete",
                    "responsibility": "partial",
                    "outcome": "partial",
                    "consequence": "partial",
                    "source_diversity": "partial",
                    "conflict_resolution": "not_applicable",
                },
                lineage={
                    "assertion_report_sha256": str(
                        assertion_payload.get("report_sha256") or ""
                    ),
                    "unit_ref": unit_ref,
                    "source_passage_ref": passage_ref,
                },
                provenance={"builder": "i5b_joint_projection_episode_trace_v1"},
            )
            episodes.append(asdict(episode))
            episode_members[episode.episode_id] = (
                "negative_credit_chain_component"
                if material["side"] == "negative"
                else "positive_feedback_chain_component"
            )
        reu = draft_rule_evidence_unit(
            rule_code=rule_code,
            rule_version="i5b-factor-semantics-v2",
            aggregation_policy_version="i5b-joint-projection-score-contribution-v2",
            evaluation_context=ruler_ref,
            episode_members=episode_members,
            relation_members={},
            aggregation_reason=material["projection_basis"],
        )
        evidence_units.append(asdict(reu))
        material["assertion_draft_refs"] = sorted(assertion_refs)
        material["rule_evidence_unit_ref"] = reu.unit_code
        material["semantic_fingerprint"] = _hash(
            {
                key: value
                for key, value in material.items()
                if key != "semantic_fingerprint"
            }
        )
    return {
        "status": "reviewed_assertion_to_episode_reu_shadow_complete",
        "source_assertion_report_sha256": assertion_payload.get("report_sha256"),
        "episode_count": len(episodes),
        "rule_evidence_unit_count": len(evidence_units),
        "assertion_link_count": assertion_link_count,
        "episodes": episodes,
        "rule_evidence_units": evidence_units,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
    }


def build_i5b_joint_projection_scored_shadow(
    *,
    rule_code: str,
    projection_payload: Mapping[str, Any],
    scoring_policy: Mapping[str, Any],
    assertion_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if rule_code not in RULES:
        raise ValueError("joint projection scorer supports exactly three rules")
    if projection_payload.get("schema_version") != "i5b-joint-projection-input-v1":
        raise ValueError("joint projection input schema mismatch")
    if projection_payload.get("rule_code") != rule_code:
        raise ValueError("joint projection rule mismatch")
    if projection_payload.get("status") != "human_frozen_regression_input":
        raise ValueError("joint projection input is not human frozen")

    units = _rows(projection_payload.get("units"), "joint projection units")
    if len({str(item.get("unit_ref") or "") for item in units}) != len(units):
        raise ValueError("joint projection unit refs must be unique")
    material_rows: list[dict[str, Any]] = []
    insufficient_rows: list[dict[str, Any]] = []
    ruler_names: set[str] = set()
    for item in units:
        unit_ref = str(item.get("unit_ref") or "").strip()
        ruler = str(item.get("ruler") or "").strip()
        subject = str(item.get("subject") or "").strip()
        status = str(item.get("status") or "")
        ruler_names.add(ruler)
        if not unit_ref or not ruler or not subject:
            raise ValueError("joint projection identity fields are incomplete")
        if status == "insufficient_projection":
            missing = sorted({str(value) for value in item.get("missing_inputs") or ()})
            if not missing or item.get("choices"):
                raise ValueError("insufficient projection must identify missing inputs only")
            insufficient_rows.append(
                {
                    "unit_ref": unit_ref,
                    "ruler": ruler,
                    "subject": subject,
                    "missing_inputs": missing,
                    "projection_basis": str(item.get("projection_basis") or ""),
                }
            )
            continue
        if status != "projected":
            raise ValueError("joint projection status is invalid")
        side = str(item.get("side") or "")
        object_ref = str(item.get("object_ref") or "").strip()
        event_group = str(item.get("canonical_event_group") or "").strip()
        source_refs = list(item.get("source_refs") or ())
        if side not in {"positive", "negative"} or not object_ref or not event_group:
            raise ValueError("projected unit ownership fields are incomplete")
        if not source_refs or not str(item.get("projection_basis") or "").strip():
            raise ValueError("projected unit requires evidence basis and source refs")
        projection = calculate_material_projection(
            scoring_policy,
            rule_code=rule_code,
            choices=item.get("choices") or {},
            side=side if rule_code != "talent_discovery" else None,
        )
        if projection["side"] != side:
            raise ValueError("talent discovery direction and declared side disagree")
        score = Decimal(str(projection["material_score"]))
        material = {
            "unit_ref": unit_ref,
            "ruler": ruler,
            "subject": subject,
            "object_ref": object_ref,
            "canonical_event_group": event_group,
            "dataset_role": _dataset_role(unit_ref),
            "side": side,
            "material_score": _rounded(abs(score)),
            "numeric_projection": projection,
            "projection_basis": str(item["projection_basis"]),
            "source_refs": source_refs,
        }
        material["semantic_fingerprint"] = _hash(material)
        material_rows.append(material)

    grouped: dict[tuple[str, str, str], list[Decimal]] = defaultdict(list)
    for material in material_rows:
        grouped[(material["ruler"], material["side"], material["object_ref"])].append(
            Decimal(material["material_score"])
        )
    object_aggregates: list[dict[str, Any]] = []
    for (ruler, side, object_ref), values in sorted(grouped.items()):
        object_aggregates.append(
            {
                "ruler": ruler,
                "side": side,
                "object_ref": object_ref,
                "material_count": len(values),
                "object_side_score": _rounded(_object_side_score(values)),
            }
        )

    assertion_trace = (
        _assertion_episode_trace(
            rule_code=rule_code,
            materials=material_rows,
            assertion_payload=assertion_payload,
        )
        if assertion_payload is not None
        else None
    )

    score_contributions: list[dict[str, Any]] = []
    for ruler in sorted(ruler_names):
        positive = sum(
            (
                Decimal(item["object_side_score"])
                for item in object_aggregates
                if item["ruler"] == ruler and item["side"] == "positive"
            ),
            Decimal("0"),
        )
        negative = sum(
            (
                Decimal(item["object_side_score"])
                for item in object_aggregates
                if item["ruler"] == ruler and item["side"] == "negative"
            ),
            Decimal("0"),
        )
        raw_net = positive - negative
        contribution = {
            "contribution_ref": "SC-I5B-" + _hash([POLICY_VERSION, rule_code, ruler])[:24].upper(),
            "rule_code": rule_code,
            "ruler": ruler,
            "primary_owner": "ruler",
            "primary_owner_ref": ruler,
            "dedup_key": _hash([rule_code, ruler, sorted(
                material["semantic_fingerprint"]
                for material in material_rows if material["ruler"] == ruler
            )]),
            "positive_signal": _rounded(positive),
            "negative_signal": _rounded(negative),
            "rule_raw_net": _rounded(raw_net),
            "insufficient_projection_count": sum(
                item["ruler"] == ruler for item in insufficient_rows
            ),
            "supporting_only_rules": [],
            "score_rate": None,
            "score": None,
            "tier": None,
        }
        traced_reus = sorted(
            str(material["rule_evidence_unit_ref"])
            for material in material_rows
            if material["ruler"] == ruler
            and material.get("rule_evidence_unit_ref")
        )
        if traced_reus:
            contribution["rule_evidence_unit_refs"] = traced_reus
        contribution["semantic_fingerprint"] = _hash(contribution)
        score_contributions.append(contribution)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "projection_input_version": projection_payload.get("input_version"),
        "status": "opened_regression_scored_shadow_raw_signal_only",
        "rule_code": rule_code,
        "summary": {
            "input_unit_count": len(units),
            "projected_material_count": len(material_rows),
            "insufficient_projection_count": len(insufficient_rows),
            "ruler_count": len(ruler_names),
            "score_contribution_count": len(score_contributions),
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
        "materials": material_rows,
        "insufficient_projections": insufficient_rows,
        "object_side_aggregates": object_aggregates,
        "score_contributions": score_contributions,
        "declarations": {
            "old_gold_modified": False,
            "opened_sealed_used_as_new_qualification": False,
            "all_projected_materials_contributed_before_object_cap": True,
            "top_k_applied": False,
            "formal_scoring_allowed": False,
        },
    }
    if assertion_trace is not None:
        report["assertion_episode_reu_trace"] = assertion_trace
        report["summary"]["traced_episode_count"] = assertion_trace[
            "episode_count"
        ]
        report["summary"]["traced_rule_evidence_unit_count"] = assertion_trace[
            "rule_evidence_unit_count"
        ]
    report["report_sha256"] = _hash(report)
    return report
