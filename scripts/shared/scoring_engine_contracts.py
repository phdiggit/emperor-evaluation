from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class ContractValidationError(ValueError):
    """Raised when a scoring-engine contract object crosses a locked boundary."""


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")


def _decimal(value: str | int | float | Decimal, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractValidationError(f"{field} must be numeric") from exc


def _format_decimal(value: str | int | float | Decimal) -> str:
    decimal_value = _decimal(value, "decimal")
    return format(decimal_value.normalize(), "f")


@dataclass(frozen=True)
class ScoreRange:
    lower: str | int | float | Decimal
    upper: str | int | float | Decimal
    inclusive_lower: bool = True
    inclusive_upper: bool = True

    def validate(self, *, score_cap: str | int | float | Decimal) -> None:
        lower = _decimal(self.lower, "score_range.lower")
        upper = _decimal(self.upper, "score_range.upper")
        cap = _decimal(score_cap, "score_cap")
        if lower < 0:
            raise ContractValidationError("score_range.lower must be non-negative")
        if upper > cap:
            raise ContractValidationError("score_range.upper must not exceed score_cap")
        if lower > upper:
            raise ContractValidationError("score_range.lower must not exceed score_range.upper")

    def contains(self, value: str | int | float | Decimal) -> bool:
        candidate = _decimal(value, "candidate_value")
        lower = _decimal(self.lower, "score_range.lower")
        upper = _decimal(self.upper, "score_range.upper")
        lower_ok = candidate >= lower if self.inclusive_lower else candidate > lower
        upper_ok = candidate <= upper if self.inclusive_upper else candidate < upper
        return lower_ok and upper_ok

    def to_dict(self) -> dict[str, object]:
        return {
            "lower": _format_decimal(self.lower),
            "upper": _format_decimal(self.upper),
            "inclusive_lower": self.inclusive_lower,
            "inclusive_upper": self.inclusive_upper,
        }


@dataclass(frozen=True)
class SubitemProfile:
    subitem_id: str
    subitem_name: str
    score_cap: str | int | float | Decimal
    grade_scale_version: str
    algorithm_version: str
    g8_gate_status: str
    g9_publication_status: str
    stage_or_final_total_release_allowed: bool = False
    cross_subitem_leaderboard_release_allowed: bool = False

    def validate(self) -> None:
        for field in ("subitem_id", "subitem_name", "grade_scale_version", "algorithm_version"):
            _require_text(getattr(self, field), field)
        if _decimal(self.score_cap, "score_cap") <= 0:
            raise ContractValidationError("score_cap must be positive")
        if self.stage_or_final_total_release_allowed:
            raise ContractValidationError("subitem profile must not release stage or final totals")
        if self.cross_subitem_leaderboard_release_allowed:
            raise ContractValidationError("subitem profile must not release cross-subitem leaderboards")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "subitem_id": self.subitem_id,
            "subitem_name": self.subitem_name,
            "score_cap": _format_decimal(self.score_cap),
            "grade_scale_version": self.grade_scale_version,
            "algorithm_version": self.algorithm_version,
            "g8_gate_status": self.g8_gate_status,
            "g9_publication_status": self.g9_publication_status,
            "stage_or_final_total_release_allowed": self.stage_or_final_total_release_allowed,
            "cross_subitem_leaderboard_release_allowed": self.cross_subitem_leaderboard_release_allowed,
        }


@dataclass(frozen=True)
class EvidenceProfile:
    person_id: str
    subitem_id: str
    positive_signal_profile: Mapping[str, Any]
    negative_signal_profile: Mapping[str, Any]
    confidence: str
    cross_item_split_signals: tuple[str, ...]
    source_traceability_status: str

    def validate(self) -> None:
        for field in ("person_id", "subitem_id", "confidence", "source_traceability_status"):
            _require_text(getattr(self, field), field)
        if not isinstance(self.positive_signal_profile, Mapping):
            raise ContractValidationError("positive_signal_profile must be a mapping")
        if not isinstance(self.negative_signal_profile, Mapping):
            raise ContractValidationError("negative_signal_profile must be a mapping")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "person_id": self.person_id,
            "subitem_id": self.subitem_id,
            "positive_signal_profile": dict(self.positive_signal_profile),
            "negative_signal_profile": dict(self.negative_signal_profile),
            "confidence": self.confidence,
            "cross_item_split_signals": list(self.cross_item_split_signals),
            "source_traceability_status": self.source_traceability_status,
        }


@dataclass(frozen=True)
class NoOverridePolicy:
    person_specific_override_allowed: bool = False
    manual_final_grade_allowed: bool = False
    manual_final_score_allowed: bool = False

    def validate(self) -> None:
        if self.person_specific_override_allowed:
            raise ContractValidationError("person-specific override is not allowed")
        if self.manual_final_grade_allowed:
            raise ContractValidationError("manual final grade is not allowed")
        if self.manual_final_score_allowed:
            raise ContractValidationError("manual final score is not allowed")

    def to_dict(self) -> dict[str, bool]:
        self.validate()
        return {
            "person_specific_override_allowed": False,
            "manual_final_grade_allowed": False,
            "manual_final_score_allowed": False,
        }


@dataclass(frozen=True)
class FormalGradeResult:
    person_id: str
    subitem_id: str
    formal_grade: str
    score_range: ScoreRange
    candidate_value: str | int | float | Decimal
    algorithm_version: str
    deterministic_rerun_key: str
    no_override_policy: NoOverridePolicy = NoOverridePolicy()

    def validate(self, *, subitem: SubitemProfile) -> None:
        for field in ("person_id", "subitem_id", "formal_grade", "algorithm_version", "deterministic_rerun_key"):
            _require_text(getattr(self, field), field)
        if self.subitem_id != subitem.subitem_id:
            raise ContractValidationError("formal grade subitem_id must match subitem profile")
        if self.algorithm_version != subitem.algorithm_version:
            raise ContractValidationError("formal grade algorithm_version must match subitem profile")
        self.score_range.validate(score_cap=subitem.score_cap)
        if not self.score_range.contains(self.candidate_value):
            raise ContractValidationError("candidate_value must stay inside score_range")
        self.no_override_policy.validate()

    def to_dict(self, *, subitem: SubitemProfile) -> dict[str, object]:
        self.validate(subitem=subitem)
        return {
            "person_id": self.person_id,
            "subitem_id": self.subitem_id,
            "formal_grade": self.formal_grade,
            "score_range": self.score_range.to_dict(),
            "candidate_value": _format_decimal(self.candidate_value),
            "algorithm_version": self.algorithm_version,
            "deterministic_rerun_key": self.deterministic_rerun_key,
            "no_override_policy": self.no_override_policy.to_dict(),
        }


@dataclass(frozen=True)
class ScorePublicationResult:
    person_id: str
    subitem_id: str
    formal_score_value: str | int | float | Decimal
    subitem_rank: int
    publication_gate: str
    publication_scope: str
    stage_or_final_total_table_released: bool = False
    cross_subitem_leaderboard_released: bool = False

    def validate(self, *, formal_grade: FormalGradeResult, subitem: SubitemProfile) -> None:
        for field in ("person_id", "subitem_id", "publication_gate", "publication_scope"):
            _require_text(getattr(self, field), field)
        if self.person_id != formal_grade.person_id:
            raise ContractValidationError("publication person_id must match formal grade")
        if self.subitem_id != formal_grade.subitem_id or self.subitem_id != subitem.subitem_id:
            raise ContractValidationError("publication subitem_id must match formal grade and subitem profile")
        if self.publication_gate != "G9":
            raise ContractValidationError("formal score publication requires G9")
        if self.subitem_rank < 1:
            raise ContractValidationError("subitem_rank must be positive")
        if _decimal(self.formal_score_value, "formal_score_value") != _decimal(
            formal_grade.candidate_value, "candidate_value"
        ):
            raise ContractValidationError("formal_score_value must equal the deterministic candidate value")
        if self.stage_or_final_total_table_released:
            raise ContractValidationError("stage/final total table publication is outside subitem G9")
        if self.cross_subitem_leaderboard_released:
            raise ContractValidationError("cross-subitem leaderboard publication is outside subitem G9")

    def to_dict(self, *, formal_grade: FormalGradeResult, subitem: SubitemProfile) -> dict[str, object]:
        self.validate(formal_grade=formal_grade, subitem=subitem)
        return {
            "person_id": self.person_id,
            "subitem_id": self.subitem_id,
            "formal_score_value": _format_decimal(self.formal_score_value),
            "subitem_rank": self.subitem_rank,
            "publication_gate": self.publication_gate,
            "publication_scope": self.publication_scope,
            "stage_or_final_total_table_released": self.stage_or_final_total_table_released,
            "cross_subitem_leaderboard_released": self.cross_subitem_leaderboard_released,
        }


def validate_interface_bundle(
    *,
    subitem: SubitemProfile,
    evidence: EvidenceProfile,
    formal_grade: FormalGradeResult,
    publication: ScorePublicationResult | None = None,
) -> dict[str, object]:
    subitem.validate()
    evidence.validate()
    if evidence.subitem_id != subitem.subitem_id:
        raise ContractValidationError("evidence subitem_id must match subitem profile")
    if formal_grade.person_id != evidence.person_id:
        raise ContractValidationError("formal grade person_id must match evidence profile")
    formal_grade.validate(subitem=subitem)
    result: dict[str, object] = {
        "subitem_profile": subitem.to_dict(),
        "evidence_profile": evidence.to_dict(),
        "formal_grade_result": formal_grade.to_dict(subitem=subitem),
        "publication_result": None,
        "stage_or_final_total_table_released": False,
        "cross_subitem_leaderboard_released": False,
    }
    if publication is not None:
        result["publication_result"] = publication.to_dict(formal_grade=formal_grade, subitem=subitem)
    return result
