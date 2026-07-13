from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Iterable

from emperor_v4.contracts.source import (
    PASSAGE_KINDS,
    PASSAGE_LINK_RELATIONS,
    SOURCE_CACHE_CONTRACT_V2,
    LinkedPassageRef,
    SourcePassage,
    text_content_hash,
)


_SENTENCE_ENDINGS = frozenset("。！？；\n")


@dataclass(frozen=True, slots=True)
class SourceSection:
    document_cache_id: str
    content_version: str
    section_id: str
    section_heading: str
    raw_text: str
    document_span_start: int = 0

    def __post_init__(self) -> None:
        if not all(
            (
                self.document_cache_id,
                self.content_version,
                self.section_id,
                self.section_heading,
                self.raw_text,
            )
        ):
            raise ValueError("SourceSection 缺少稳定文档、版本、章节或原文")
        if self.document_span_start < 0:
            raise ValueError("SourceSection document_span_start 不得为负")


@dataclass(frozen=True, slots=True)
class PassageLinkSeed:
    target_seed_code: str
    relation: str

    def __post_init__(self) -> None:
        if not self.target_seed_code:
            raise ValueError("PassageLinkSeed 必须声明 target_seed_code")
        if self.relation not in PASSAGE_LINK_RELATIONS:
            raise ValueError(f"未知 passage link relation: {self.relation}")


@dataclass(frozen=True, slots=True)
class PassageSeed:
    seed_code: str
    anchor_start: int
    anchor_end: int
    passage_kind: str
    selection_reason: tuple[str, ...]
    links: tuple[PassageLinkSeed, ...] = ()

    def __post_init__(self) -> None:
        if not self.seed_code or self.anchor_start < 0 or self.anchor_end <= self.anchor_start:
            raise ValueError("PassageSeed 必须有 code 和有效 anchor span")
        if self.passage_kind not in PASSAGE_KINDS:
            raise ValueError(f"未知 passage_kind: {self.passage_kind}")
        if not self.selection_reason:
            raise ValueError("PassageSeed 必须声明 selection_reason")
        if self.passage_kind == "navigation_noise" and self.links:
            raise ValueError("navigation_noise seed 不得建立历史证据链接")


@dataclass(frozen=True, slots=True)
class WindowPolicy:
    version: str
    sentence_radius_before: int = 0
    sentence_radius_after: int = 0
    context_chars_before: int = 160
    context_chars_after: int = 160

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("WindowPolicy 必须声明 version")
        if min(
            self.sentence_radius_before,
            self.sentence_radius_after,
            self.context_chars_before,
            self.context_chars_after,
        ) < 0:
            raise ValueError("WindowPolicy 窗口参数不得为负")


def _sentence_ranges(text: str) -> tuple[tuple[int, int], ...]:
    ranges = []
    start = 0
    for index, char in enumerate(text):
        if char in _SENTENCE_ENDINGS:
            if index + 1 > start:
                ranges.append((start, index + 1))
            start = index + 1
    if start < len(text):
        ranges.append((start, len(text)))
    return tuple(ranges)


def _expanded_span(
    text: str, seed: PassageSeed, policy: WindowPolicy
) -> tuple[int, int]:
    if seed.anchor_end > len(text):
        raise ValueError(f"PassageSeed anchor 超出 section: {seed.seed_code}")
    if seed.passage_kind == "navigation_noise":
        return seed.anchor_start, seed.anchor_end
    ranges = _sentence_ranges(text)
    touching = [
        index
        for index, (start, end) in enumerate(ranges)
        if start < seed.anchor_end and seed.anchor_start < end
    ]
    if not touching:
        return seed.anchor_start, seed.anchor_end
    first = max(0, min(touching) - policy.sentence_radius_before)
    last = min(len(ranges) - 1, max(touching) + policy.sentence_radius_after)
    return ranges[first][0], ranges[last][1]


def _stable_passage_id(
    section: SourceSection,
    *,
    span_start: int,
    span_end: int,
    passage_kind: str,
    window_policy_version: str,
) -> str:
    identity = "\x1f".join(
        (
            section.document_cache_id,
            section.content_version,
            section.section_id,
            str(span_start),
            str(span_end),
            passage_kind,
            window_policy_version,
        )
    )
    return "SP-" + sha256(identity.encode("utf-8")).hexdigest()[:20].upper()


def _overlap_components(
    spans: list[tuple[int, int]],
) -> dict[int, str | None]:
    parents = list(range(len(spans)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left, left_span in enumerate(spans):
        for right in range(left + 1, len(spans)):
            right_span = spans[right]
            if left_span[0] < right_span[1] and right_span[0] < left_span[1]:
                union(left, right)
    members: dict[int, list[int]] = {}
    for index in range(len(spans)):
        members.setdefault(find(index), []).append(index)
    result: dict[int, str | None] = {index: None for index in range(len(spans))}
    for indexes in members.values():
        if len(indexes) < 2:
            continue
        payload = ";".join(f"{spans[index][0]}:{spans[index][1]}" for index in indexes)
        group = "OV-" + sha256(payload.encode("utf-8")).hexdigest()[:16].upper()
        for index in indexes:
            result[index] = group
    return result


def slice_source_section(
    section: SourceSection,
    seeds: Iterable[PassageSeed],
    policy: WindowPolicy,
) -> tuple[SourcePassage, ...]:
    seed_items = tuple(seeds)
    seed_codes = [item.seed_code for item in seed_items]
    if not seed_items or len(seed_codes) != len(set(seed_codes)):
        raise ValueError("section slicer seeds 必须非空且 code 唯一")
    if unknown_targets := sorted(
        {
            link.target_seed_code
            for seed in seed_items
            for link in seed.links
            if link.target_seed_code not in set(seed_codes)
        }
    ):
        raise ValueError(f"linked passage seed 不存在: {unknown_targets}")

    local_spans = [_expanded_span(section.raw_text, seed, policy) for seed in seed_items]
    absolute_spans = [
        (
            section.document_span_start + start,
            section.document_span_start + end,
        )
        for start, end in local_spans
    ]
    overlap_groups = _overlap_components(absolute_spans)
    ids = {
        seed.seed_code: _stable_passage_id(
            section,
            span_start=absolute_spans[index][0],
            span_end=absolute_spans[index][1],
            passage_kind=seed.passage_kind,
            window_policy_version=policy.version,
        )
        for index, seed in enumerate(seed_items)
    }
    passages = []
    for index, seed in enumerate(seed_items):
        local_start, local_end = local_spans[index]
        absolute_start, absolute_end = absolute_spans[index]
        raw_text = section.raw_text[local_start:local_end]
        passages.append(
            SourcePassage(
                passage_cache_id=ids[seed.seed_code],
                document_cache_id=section.document_cache_id,
                locator=f"{section.section_id}:{absolute_start}-{absolute_end}",
                raw_text=raw_text,
                context_before=section.raw_text[
                    max(0, local_start - policy.context_chars_before):local_start
                ],
                context_after=section.raw_text[
                    local_end:min(
                        len(section.raw_text), local_end + policy.context_chars_after
                    )
                ],
                content_hash=text_content_hash(raw_text),
                selection_reason=seed.selection_reason,
                contract_version=SOURCE_CACHE_CONTRACT_V2,
                content_version=section.content_version,
                section_id=section.section_id,
                section_heading=section.section_heading,
                span_start=absolute_start,
                span_end=absolute_end,
                passage_kind=seed.passage_kind,
                linked_passages=tuple(
                    LinkedPassageRef(ids[link.target_seed_code], link.relation)
                    for link in seed.links
                ),
                overlap_group=overlap_groups[index],
                window_policy_version=policy.version,
            )
        )
    return tuple(sorted(passages, key=lambda item: item.passage_cache_id))


def relink_passage(
    passage: SourcePassage, links: Iterable[LinkedPassageRef]
) -> SourcePassage:
    """为确定性开发 fixture 提供显式重连，不改变 passage 身份或原文。"""

    return replace(passage, linked_passages=tuple(links))
