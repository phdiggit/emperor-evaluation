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

PASSAGE_SUPPORT_MODES = frozenset(
    {"single_passage", "equivalent_evidence", "atomic_component", "context_only"}
)
PASSAGE_SUPPORT_FIELDS = frozenset(
    {
        "identity",
        "action",
        "responsibility",
        "time",
        "location",
        "outcome",
        "consequence",
        "attribution",
        "context",
    }
)


@dataclass(frozen=True, slots=True)
class PassageSupport:
    support_mode: str
    assertion_semantic_key: str
    supported_fields: tuple[str, ...]
    binding_provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.support_mode not in PASSAGE_SUPPORT_MODES:
            raise ValueError(f"未知 passage support mode: {self.support_mode}")
        if not self.assertion_semantic_key.strip():
            raise ValueError("PassageSupport 必须声明 assertion_semantic_key")
        fields = tuple(self.supported_fields)
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("PassageSupport supported_fields 必须非空且唯一")
        unknown = sorted(set(fields) - PASSAGE_SUPPORT_FIELDS)
        if unknown:
            raise ValueError(f"PassageSupport 包含未知 supported_fields: {unknown}")
        if self.support_mode != "context_only" and not {
            "identity",
            "action",
        } <= set(fields):
            raise ValueError("核心 PassageSupport 必须至少支持 identity 和 action")


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
    passage_support: PassageSupport | None = None

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
