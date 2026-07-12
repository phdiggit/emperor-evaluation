from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


ASSERTION_TYPES = frozenset(
    {
        "event_fact",
        "identity_fact",
        "role_fact",
        "outcome_fact",
        "causal_claim",
        "historiographical_evaluation",
        "numeric_fact",
        "context_fact",
    }
)


@dataclass(frozen=True, slots=True)
class AssertionDraft:
    assertion_code: str
    source_passage_ref: str
    assertion_type: str
    subject: str
    predicate: str
    object: str
    time_expression: str | None
    location_expression: str | None
    qualifiers: Mapping[str, Any]
    polarity: str
    source_attribution: Mapping[str, Any]
    candidate_episode_key: str | None
    confidence: float
    ambiguity_flags: tuple[str, ...] = ()
    extraction_provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "assertion_code": self.assertion_code,
            "source_passage_ref": self.source_passage_ref,
            "assertion_type": self.assertion_type,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "polarity": self.polarity,
        }
        missing = [name for name, value in required.items() if value in (None, "")]
        if missing:
            raise ValueError(f"AssertionDraft 缺少必填字段: {', '.join(missing)}")
        if self.assertion_type not in ASSERTION_TYPES:
            raise ValueError(f"未知 assertion_type: {self.assertion_type}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("AssertionDraft confidence 必须在 0 到 1 之间")
