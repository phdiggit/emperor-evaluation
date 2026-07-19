from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import unquote, urlparse

from opencc import OpenCC

from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext,
)
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.application.source_cache_service import (
    PreparedSourceSection,
    SourceMaterialBatch,
)
from emperor_v4.contracts.source import (
    SourceCacheRequest,
    SourceRevisionContent,
)
from emperor_v4.domain.source_segmentation import PassageSeed, WindowPolicy


FetchWikisource = Callable[..., WikisourcePageSnapshot]
_CJK = re.compile(r"[\u3400-\u9fff]{2,}")
_ARABIC_VOLUME = re.compile(r"卷\s*0*(\d{1,4})")
_CHINESE_VOLUME = re.compile(r"卷\s*([〇零一二三四五六七八九十百千兩两]{1,8})")
_STOP_TERMS = {
    "人物",
    "事件",
    "结果",
    "結果",
    "历史",
    "歷史",
    "政治",
    "风险",
    "風險",
    "评价",
    "評價",
    "重建",
    "本人",
    "行动",
    "行動",
    "可归责",
    "可歸責",
    "唐朝",
    "时期",
    "時期",
}
_OMISSION_BOILERPLATE = (
    "重大成就",
    "主要成就",
    "重要事迹",
    "奉命",
    "受命",
    "率军",
    "领兵",
    "出征",
    "击破",
    "击败",
    "攻克",
    "平定",
    "领土",
    "战役",
    "战争",
    "功绩",
    "成果",
    "结果",
)
_OMISSION_EVENT_MARKERS = (
    "寇边",
    "行军",
    "出征",
    "征之",
    "决计",
    "决策",
    "深入",
    "军次",
    "大破",
    "杀获",
    "来降",
    "可汗",
)
_OMISSION_FLIGHT_MARKERS = ("将走投", "走投", "将奔", "逃往", "奔赴")
_T2S = OpenCC("t2s")
_LOCATOR_NORMALIZATIONS = (
    ("十条计策", "十策"),
    ("十条策略", "十策"),
    ("秋汛洪水", "秋潦"),
    ("秋汛", "秋潦"),
    ("弹劾", "谮"),
)


def _normalize_locator_text(value: str) -> str:
    normalized = _T2S.convert(value)
    for source, target in _LOCATOR_NORMALIZATIONS:
        normalized = normalized.replace(source, target)
    return normalized


def _chinese_integer(value: str) -> int:
    digits = {"〇": 0, "零": 0, "一": 1, "二": 2, "兩": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    if all(char in digits for char in value):
        return int("".join(str(digits[char]) for char in value))
    total = 0
    current = 0
    for char in value:
        if char in digits:
            current = digits[char]
        elif char in units:
            total += (current or 1) * units[char]
            current = 0
        else:
            raise ValueError(f"卷次包含无法识别的数字: {value}")
    return total + current


def _volume_number(text: str) -> int | None:
    if match := _ARABIC_VOLUME.search(text):
        return int(match.group(1))
    if match := _CHINESE_VOLUME.search(text):
        return _chinese_integer(match.group(1))
    return None


def _page_title_in_worklist_range(
    *, page_title: str, work_title: str, worklist: Mapping[str, Any]
) -> bool:
    raw_ranges = (worklist.get("i5b_selection") or {}).get("source_page_ranges") or {}
    normalized_work = _T2S.convert(work_title).replace(" ", "")
    bounds = next(
        (
            value
            for work, value in raw_ranges.items()
            if _T2S.convert(str(work)).replace(" ", "") == normalized_work
        ),
        None,
    )
    if bounds is None:
        return True
    volume = _volume_number(page_title)
    return volume is not None and int(bounds[0]) <= volume <= int(bounds[1])


def wikisource_title_candidates(batch: Mapping[str, Any]) -> tuple[str, ...]:
    parsed = urlparse(str(batch.get("source_url") or ""))
    candidates = []
    if parsed.netloc.lower().endswith("wikisource.org"):
        path = unquote(parsed.path).strip("/")
        if path.startswith("wiki/"):
            candidates.append(path.removeprefix("wiki/").replace("_", " "))
        elif path.startswith(("zh-hans/", "zh-hant/", "zh/")):
            candidates.append(path.split("/", 1)[1].replace("_", " "))

    works = tuple(str(item).replace(" ", "") for item in batch.get("source_works") or ())
    sections = " ".join(str(item) for item in batch.get("requested_sections") or ())
    volume = _volume_number(sections)
    if volume is not None:
        mappings = (
            (("旧唐书", "舊唐書"), "舊唐書", f"卷{volume}"),
            (("新唐书", "新唐書"), "新唐書", f"卷{volume:03d}"),
            (("资治通鉴", "資治通鑑"), "資治通鑑", f"卷{volume}"),
        )
        for aliases, work_title, volume_title in mappings:
            if any(work in aliases for work in works):
                candidates.append(f"{work_title}/{volume_title}")
    return tuple(dict.fromkeys(item for item in candidates if item))


def _candidate_terms(
    lead: Mapping[str, Any],
    subject_name: str,
    *,
    include_subject_term: bool = True,
) -> tuple[str, ...]:
    text = _normalize_locator_text(" ".join(
        str(lead.get(field) or "")
        for field in (
            "lead",
            "subject_action",
            "observable_result",
        )
    ))
    for noise in ("作为行军总管", "任行军总管", "行军总管"):
        text = text.replace(noise, " ")
    terms = [_T2S.convert(subject_name)] if include_subject_term else []
    normalized_subject = _T2S.convert(subject_name)
    for sequence in _CJK.findall(text):
        for width in range(min(6, len(sequence)), 1, -1):
            for start in range(0, len(sequence) - width + 1):
                term = sequence[start : start + width]
                if term in _STOP_TERMS:
                    continue
                if not include_subject_term and normalized_subject in term:
                    continue
                terms.append(term)
    return tuple(dict.fromkeys(terms))


def omission_has_distinctive_match(
    matched_terms: Sequence[str],
    *,
    omitted_lead: str,
    subject_name: str,
) -> bool:
    """Reject omission matches supported only by names, dates, or generic actions."""
    normalized_omission = _normalize_locator_text(omitted_lead)
    normalized_subject = _T2S.convert(subject_name)
    for raw_term in matched_terms:
        term = _normalize_locator_text(str(raw_term))
        if len(term) < 3 or term not in normalized_omission:
            continue
        if normalized_subject and normalized_subject in term:
            continue
        if "年" in term or re.search(r"[〇零一二三四五六七八九十百千两兩\d]", term):
            continue
        if any(term in boilerplate for boilerplate in _OMISSION_BOILERPLATE):
            continue
        return True
    return False


def has_subject_section(source_text: str, subject_name: str) -> bool:
    normalized_source = _T2S.convert(source_text)
    normalized_subject = _T2S.convert(subject_name)
    return re.search(
        rf"(?m)^==+\s*{re.escape(normalized_subject)}\s*==+\s*$",
        normalized_source,
    ) is not None


def locate_omission_span(
    source_text: str,
    *,
    subject_name: str,
    distinctive_terms: Sequence[str],
) -> tuple[int, int, tuple[str, ...]] | None:
    """Locate an omission anchor in the focal biography, favouring event context."""
    normalized_source = _T2S.convert(source_text)
    normalized_subject = _T2S.convert(subject_name)
    heading = re.search(
        rf"(?m)^==+\s*{re.escape(normalized_subject)}\s*==+\s*$",
        normalized_source,
    )
    if heading is None:
        return None
    next_heading = re.search(
        r"(?m)^==+\s*.+?\s*==+\s*$", normalized_source[heading.end() :]
    )
    search_start = heading.end()
    search_end = (
        heading.end() + next_heading.start()
        if next_heading
        else len(normalized_source)
    )
    occurrences: list[tuple[int, str, float]] = []
    for term in distinctive_terms:
        position = normalized_source.find(term, search_start, search_end)
        while position >= 0:
            before = normalized_source[max(search_start, position - 180) : position]
            context = normalized_source[
                max(search_start, position - 180) : min(search_end, position + len(term) + 300)
            ]
            score = float(len(term) ** 2)
            score += 8.0 * sum(marker in context for marker in _OMISSION_EVENT_MARKERS)
            if any(marker in before[-12:] for marker in _OMISSION_FLIGHT_MARKERS):
                score -= 1_000.0
            occurrences.append((position, term, score))
            position = normalized_source.find(term, position + 1, search_end)
    if not occurrences:
        return None
    best_position, best_term, _score = max(
        occurrences,
        key=lambda item: (item[2], len(item[1]), -item[0]),
    )
    nearby_terms = tuple(
        dict.fromkeys(
            term
            for position, term, _score in sorted(occurrences)
            if abs(position - best_position) <= 360
        )
    )
    return best_position, best_position + len(best_term), nearby_terms


def locate_lead_span(
    source_text: str,
    lead: Mapping[str, Any],
    *,
    subject_name: str,
    include_subject_term: bool = True,
    terms_override: Sequence[str] | None = None,
) -> tuple[int, int, tuple[str, ...]] | None:
    normalized_source = _T2S.convert(source_text)
    search_start = 0
    search_end = len(normalized_source)
    lead_text = _normalize_locator_text(
        " ".join(
            str(lead.get(field) or "")
            for field in ("lead", "subject_action", "observable_result")
        )
    )
    heading_scoped = False
    if not any(marker in lead_text for marker in ("史臣", "赞曰", "传论", "史评")):
        heading = re.search(
            rf"(?m)^==+\s*{re.escape(subject_name)}\s*==+\s*$",
            normalized_source,
        )
        if heading:
            heading_scoped = True
            next_heading = re.search(r"(?m)^==+\s*.+?\s*==+\s*$", normalized_source[heading.end() :])
            search_start = heading.end()
            search_end = (
                heading.end() + next_heading.start()
                if next_heading
                else len(normalized_source)
            )
    occurrences: list[tuple[int, str, float]] = []
    terms = tuple(terms_override) if terms_override is not None else _candidate_terms(
        lead,
        subject_name,
        include_subject_term=include_subject_term,
    )
    for term in terms:
        count = normalized_source.count(term, search_start, search_end)
        if not 1 <= count <= 20:
            continue
        weight = (len(term) ** 2) / count
        position = normalized_source.find(term, search_start, search_end)
        while position >= 0:
            occurrences.append((position, term, weight))
            position = normalized_source.find(term, position + 1, search_end)
    if not occurrences:
        return None

    def independent_terms(anchor_position: int) -> tuple[str, ...]:
        nearby = {
            term
            for position, term, _weight in occurrences
            if abs(position - anchor_position) <= 360
        }
        independent = []
        for term in sorted(nearby, key=lambda item: (-len(item), item)):
            if any(term in selected for selected in independent):
                continue
            independent.append(term)
        return tuple(independent)

    def anchor_score(anchor_position: int) -> float:
        score = 0.0
        for term in independent_terms(anchor_position):
            score += max(
                weight / (1.0 + abs(position - anchor_position) / 80.0)
                for position, candidate, weight in occurrences
                if candidate == term and abs(position - anchor_position) <= 360
            )
        return score

    normalized_subject = _T2S.convert(subject_name)
    context_text = _T2S.convert(
        " ".join(
            str(lead.get(field) or "")
            for field in ("lead", "subject_action", "period_or_ruler_context")
        )
    )
    actor_aliases = [normalized_subject]
    if len(normalized_subject) >= 3 and normalized_subject in normalized_source[search_start:search_end]:
        actor_aliases.append(normalized_subject[-2:])
    if str(lead.get("lead_type") or "") == "policy":
        for title in ("高祖", "太宗", "高宗", "中宗", "睿宗", "玄宗", "肃宗", "代宗", "德宗"):
            if title in context_text:
                actor_aliases.append(title)
    actor_aliases = list(dict.fromkeys(alias for alias in actor_aliases if len(alias) >= 2))
    focus_text = _normalize_locator_text(str(lead.get("lead") or ""))
    focus_terms = set()
    for sequence in _CJK.findall(focus_text):
        for width in range(min(6, len(sequence)), 1, -1):
            for start in range(0, len(sequence) - width + 1):
                focus_terms.add(sequence[start : start + width])
    focus_terms.update(
        _normalize_locator_text(str(term))
        for term in lead.get("source_recall_terms") or ()
        if str(term).strip()
    )
    ranked = sorted(
        occurrences,
        key=lambda anchor: (-anchor_score(anchor[0]), anchor[0], -len(anchor[1])),
    )
    checked_positions = set()
    for best in ranked:
        if best[0] in checked_positions:
            continue
        checked_positions.add(best[0])
        nearby = independent_terms(best[0])
        paragraph_start = normalized_source.rfind("\n", search_start, best[0]) + 1
        paragraph_end = normalized_source.find("\n", best[0] + len(best[1]), search_end)
        if paragraph_end < 0:
            paragraph_end = search_end
        paragraph = normalized_source[paragraph_start:paragraph_end]
        if not heading_scoped and not any(alias in paragraph for alias in actor_aliases):
            continue
        if not any(
            (focus in term or term in focus)
            and (term in paragraph or focus in paragraph)
            for term in nearby
            for focus in focus_terms
        ):
            continue
        distinctive = tuple(
            term
            for term in nearby
            if len(term) >= 3
            and not any(alias in term for alias in actor_aliases)
            and term not in _STOP_TERMS
            and not term.endswith("等")
            and not re.search(r"^[〇零一二三四五六七八九十百千两兩\d]+年?$", term)
        )
        if distinctive:
            return best[0], best[0] + len(best[1]), tuple(nearby[:8])
    return None


class DiscoverySourceMaterialProvider:
    def __init__(
        self,
        *,
        worklist: Mapping[str, Any],
        fetch: FetchWikisource = fetch_wikisource_plaintext,
        local_index: LocalSourceTextIndex | None = None,
        local_candidate_limit: int = 5,
    ) -> None:
        self.worklist = worklist
        self.fetch = fetch
        self.local_index = local_index
        self.local_candidate_limit = local_candidate_limit

    def load(self, request: SourceCacheRequest) -> SourceMaterialBatch:
        subject_ref = request.subject.person_or_ruler_ref
        if any(
            str(batch.get("subject_ref") or "") != subject_ref
            for batch in self.worklist.get("source_batches") or ()
        ):
            raise ValueError("source batch subject 与 Source Cache request 不一致")
        snapshots: dict[str, WikisourcePageSnapshot] = {}
        revisions: dict[str, SourceRevisionContent] = {}
        sections = []
        errors = []
        network_request_count = 0
        for batch in self.worklist.get("source_batches") or ():
            direct_titles = wikisource_title_candidates(batch)
            lead_candidates: dict[str, tuple[str, ...]] = {}
            for lead in batch.get("leads") or ():
                lead_ref = str(lead["lead_ref"])
                if direct_titles:
                    lead_candidates[lead_ref] = direct_titles
                elif self.local_index is not None:
                    source_recall_terms = tuple(
                        str(term).strip()
                        for term in lead.get("source_recall_terms") or ()
                        if str(term).strip()
                    )
                    requested_works = tuple(
                        str(item) for item in batch.get("source_works") or ()
                    )
                    hits_by_title = {}
                    for requested_work in requested_works:
                        for hit in self.local_index.search(
                            works=(requested_work,),
                            terms=tuple(
                                dict.fromkeys(
                                    [
                                        *source_recall_terms,
                                        *_candidate_terms(
                                            lead,
                                            request.subject.canonical_name,
                                        ),
                                    ]
                                )
                            ),
                            limit=max(self.local_candidate_limit, 30),
                        ):
                            if _page_title_in_worklist_range(
                                page_title=hit.page_title,
                                work_title=hit.work_title,
                                worklist=self.worklist,
                            ):
                                hits_by_title.setdefault(hit.page_title, hit)
                    hits = tuple(hits_by_title.values())
                    work_priority = {
                        _T2S.convert(work).replace(" ", ""): index
                        for index, work in enumerate(requested_works)
                    }
                    hits = tuple(
                        sorted(
                            hits,
                            key=lambda hit: (
                                work_priority.get(
                                    _T2S.convert(hit.work_title).replace(" ", ""),
                                    len(work_priority),
                                ),
                                -hit.score,
                                hit.page_title,
                            ),
                        )
                    )
                    lead_candidates[lead_ref] = tuple(
                        hit.page_title
                        for hit in hits
                        if (
                            (local_text := self.local_index.read_page_text(hit.page_title))
                            and locate_lead_span(
                                local_text,
                                lead,
                                subject_name=request.subject.canonical_name,
                                terms_override=(
                                    source_recall_terms
                                    if source_recall_terms
                                    else None
                                ),
                            )
                            is not None
                        )
                    )[: self.local_candidate_limit]
                else:
                    lead_candidates[lead_ref] = ()
            if not any(lead_candidates.values()):
                errors.append(
                    {
                        "source_batch_code": batch.get("source_batch_code"),
                        "reason": (
                            "local_source_index_required"
                            if self.local_index is None and not direct_titles
                            else "local_source_index_no_match"
                        ),
                        "attempted_titles": [],
                    }
                )
                continue
            for lead in batch.get("leads") or ():
                lead_ref = str(lead["lead_ref"])
                located = None
                located_title = ""
                located_snapshot = None
                attempted_titles = []
                for title in lead_candidates[lead_ref]:
                    attempted_titles.append(title)
                    snapshot = snapshots.get(title)
                    if snapshot is None:
                        network_request_count += 1
                        try:
                            snapshot = self.fetch(
                                page_code="DISC-"
                                + sha256(title.encode("utf-8")).hexdigest()[:12].upper(),
                                page_title=title,
                            )
                        except (OSError, ValueError):
                            continue
                        snapshots[title] = snapshot
                        revisions[title] = SourceRevisionContent(
                            source_host="wikisource",
                            source_document_ref=snapshot.page_code,
                            title=snapshot.canonical_title,
                            url=snapshot.canonical_url,
                            revision_ref=str(snapshot.revision_id),
                            revision_timestamp=snapshot.revision_timestamp,
                            retrieved_at=snapshot.retrieved_at,
                            raw_text=snapshot.raw_text,
                            content_hash=snapshot.content_hash,
                        )
                    located = locate_lead_span(
                        snapshot.raw_text,
                        lead,
                        subject_name=request.subject.canonical_name,
                    )
                    if located is not None:
                        located_title = title
                        located_snapshot = snapshot
                        break
                if located is None:
                    errors.append(
                        {
                            "source_batch_code": batch.get("source_batch_code"),
                            "lead_ref": lead_ref,
                            "reason": "lead_anchor_not_found",
                            "attempted_titles": attempted_titles,
                        }
                    )
                    continue
                assert located_snapshot is not None
                start, end, matched_terms = located
                section_hash = sha256(
                    f"{batch['source_batch_code']}\n{lead_ref}".encode("utf-8")
                ).hexdigest()[:16].upper()
                sections.append(
                    PreparedSourceSection(
                        revision=revisions[located_title],
                        work_identity="/".join(
                            batch.get("source_works")
                            or (located_snapshot.canonical_title,)
                        ),
                        edition_identity=(
                            f"wikisource-revision-{located_snapshot.revision_id}"
                        ),
                        source_role="official_history",
                        license_or_access_note="Wikisource public text",
                        section_id=f"DISCSEC-{section_hash}",
                        section_heading=str(lead["lead"]),
                        document_span_start=0,
                        seeds=(
                            PassageSeed(
                                seed_code=f"DISCSEED-{section_hash}",
                                anchor_start=start,
                                anchor_end=end,
                                passage_kind="atomic",
                                selection_reason=(
                                    "discovery_source_backfill",
                                    lead_ref,
                                    f"lead_type:{lead['lead_type']}",
                                    *(
                                        f"projection:{target}"
                                        for target in lead.get("projection_targets") or ()
                                    ),
                                    *(f"matched:{term}" for term in matched_terms),
                                ),
                            ),
                        ),
                        window_policy=WindowPolicy(
                            version="discovery-source-window-v1",
                            sentence_radius_before=2,
                            sentence_radius_after=2,
                            context_chars_before=120,
                            context_chars_after=120,
                        ),
                    )
                )
        for omission in self.worklist.get("discovery_omissions") or ():
            if omission.get("blocks_profile_review") is not True:
                continue
            lead_ref = f"{omission['discovery_task_code']}:OMISSION"
            omission_lead = {
                "lead_ref": lead_ref,
                "lead_type": "omission_followup",
                "lead": str(omission["omitted_leads"]),
                "subject_action": "",
                "observable_result": "",
                "projection_targets": [
                    "historical_episode_candidate",
                    "talent_profile_candidate",
                ],
            }
            located_omission = False
            omission_terms = tuple(
                term
                for term in _candidate_terms(
                    omission_lead,
                    request.subject.canonical_name,
                    include_subject_term=False,
                )
                if omission_has_distinctive_match(
                    (term,),
                    omitted_lead=str(omission["omitted_leads"]),
                    subject_name=request.subject.canonical_name,
                )
            )
            if not omission_terms:
                errors.append(
                    {
                        "lead_ref": lead_ref,
                        "reason": "discovery_omission_has_no_distinctive_anchor",
                    }
                )
                continue
            for title, snapshot in snapshots.items():
                if not has_subject_section(
                    snapshot.raw_text,
                    request.subject.canonical_name,
                ):
                    continue
                located = locate_omission_span(
                    snapshot.raw_text,
                    subject_name=request.subject.canonical_name,
                    distinctive_terms=omission_terms,
                )
                if located is None:
                    continue
                start, end, matched_terms = located
                if not omission_has_distinctive_match(
                    matched_terms,
                    omitted_lead=str(omission["omitted_leads"]),
                    subject_name=request.subject.canonical_name,
                ):
                    continue
                section_hash = sha256(
                    f"omission\n{lead_ref}\n{title}".encode("utf-8")
                ).hexdigest()[:16].upper()
                sections.append(
                    PreparedSourceSection(
                        revision=revisions[title],
                        work_identity=snapshot.canonical_title,
                        edition_identity=f"wikisource-revision-{snapshot.revision_id}",
                        source_role="official_history",
                        license_or_access_note="Wikisource public text",
                        section_id=f"DISCSEC-{section_hash}",
                        section_heading=str(omission["omitted_leads"]),
                        document_span_start=0,
                        seeds=(
                            PassageSeed(
                                seed_code=f"DISCSEED-{section_hash}",
                                anchor_start=start,
                                anchor_end=end,
                                passage_kind="atomic",
                                selection_reason=(
                                    "discovery_omission_sweep",
                                    f"discovery_omission:{omission['discovery_task_code']}",
                                    lead_ref,
                                    "lead_type:omission_followup",
                                    "projection:historical_episode_candidate",
                                    "projection:talent_profile_candidate",
                                    *(f"matched:{term}" for term in matched_terms),
                                ),
                            ),
                        ),
                        window_policy=WindowPolicy(
                            version="discovery-source-window-v1",
                            sentence_radius_before=2,
                            sentence_radius_after=2,
                            context_chars_before=120,
                            context_chars_after=120,
                        ),
                    )
                )
                located_omission = True
                break
            if not located_omission:
                errors.append(
                    {
                        "lead_ref": lead_ref,
                        "reason": "discovery_omission_anchor_not_found",
                    }
                )
        return SourceMaterialBatch(
            sections=tuple(sections),
            provider_code=(
                "local_text_index_then_wikisource_revision:v23"
                if self.local_index is not None
                else "discovery_wikisource_locator:v23"
            ),
            network_request_count=network_request_count,
            errors=tuple(errors),
        )
