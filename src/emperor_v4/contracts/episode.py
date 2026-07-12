from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


COMPLETENESS_STATES = frozenset(
    {"complete", "partial", "missing", "not_applicable", "conflicted"}
)
EPISODE_STATUSES = frozenset(
    {
        "proposed",
        "needs_identity_review",
        "needs_evidence_review",
        "accepted",
        "accepted_with_uncertainty",
        "rejected",
        "superseded",
        "split",
        "merged",
    }
)


@dataclass(frozen=True, slots=True)
class EpisodeParticipant:
    person_ref: str
    role_codes: tuple[str, ...]
    role_status: str = "unresolved"


@dataclass(frozen=True, slots=True)
class AssertionLink:
    assertion_ref: str
    source_passage_ref: str
    relation: str
    supported_fields: tuple[str, ...]
    evidence_status: str = "draft"
    representative: bool = False


@dataclass(frozen=True, slots=True)
class HistoricalEpisodePacket:
    episode_id: str
    episode_type: str
    episode_status: str
    evaluation_context: str
    semantic_version: int
    evidence_version: int
    semantic_fingerprint: str
    time_start: str | None
    time_end: str | None
    time_precision: str
    locations: tuple[str, ...]
    participants: tuple[EpisodeParticipant, ...]
    action: str
    responsibility: str | None
    outcome: tuple[str, ...]
    consequence: tuple[str, ...]
    assertion_links: tuple[AssertionLink, ...]
    conflicts: tuple[str, ...]
    uncertainties: tuple[str, ...]
    completeness: Mapping[str, str]
    lineage: Mapping[str, str]
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.episode_status not in EPISODE_STATUSES:
            raise ValueError(f"未知 episode_status: {self.episode_status}")
        if not self.participants:
            raise ValueError("HistoricalEpisodePacket 至少需要一个 participant")
        invalid = {
            slot: state
            for slot, state in self.completeness.items()
            if state not in COMPLETENESS_STATES
        }
        if invalid:
            raise ValueError(f"未知 completeness 状态: {invalid}")
        if self.episode_status in {"accepted", "accepted_with_uncertainty"}:
            if not self.assertion_links or any(
                not link.source_passage_ref for link in self.assertion_links
            ):
                raise ValueError("accepted episode 必须有 passage lineage")
