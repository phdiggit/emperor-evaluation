from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from opencc import OpenCC

from emperor_v4.adapters.historical_entity_identity import HistoricalEntityResolver


SCHEMA_VERSION = "deterministic-backbone-campaign-discovery-v1"
POLICY_VERSION = "deterministic-backbone-campaign-policy-v2"
_T2S = OpenCC("t2s")

_MILITARY_ACTION = re.compile(
    r"(?:將兵|将兵|引兵|勒兵|率兵|帥兵|帅兵|督諸軍|督诸军|統兵|统兵|"
    r"親征|亲征|出征|追擊|追击|遣.{0,8}(?:攻|擊|击|討|讨|伐|征|圍|围)|"
    r"命.{0,12}(?:將兵|将兵|軍|军|兵|攻|擊|击|討|讨|伐|征|圍|围|戰|战)|"
    r"攻|討(?!論)|讨(?!论)|擊|击|伐|征|圍|围|戰|战|敗|败|"
    r"衝|冲|救|守|拒|陷陳|陷陈|殺|杀)"
)
_RULER_PRONOUN_TERMS = ("上", "帝", "車駕", "车驾")
_POSITIVE_RESULT = re.compile(
    r"(?:大破|擊破|击破|攻克|克之|克[\u3400-\u9fff]{1,6}|拔之|平定|平之|擒(?:之|獲|获)?|"
    r"俘(?:之|獲|获|斬|斩|其眾|其众)|降(?:之|其眾|其众)?|敗走|败走|潰|溃|斬首|斩首|"
    r"獲其|获其|悉平|皆平)"
)
_NEGATIVE_RESULT = re.compile(
    r"(?:不克|未克|不能克|敗績|败绩|為.{0,8}所敗|为.{0,8}所败|"
    r"退保|引兵還|引兵还|引還|引还|旋師|旋师|班師|班师|還軍|还军|撤軍|撤军|"
    r"死者甚眾|死者甚众|皆敗|皆败|軍敗|军败|兵敗|兵败|大敗|大败)"
)
_HYPOTHETICAL_PREFIX = re.compile(r"(?:可|當|当|將|将|欲|若|俟|宜|必|願|愿|恐).{0,7}$")
_SPEECH_AFTER_SUBJECT = re.compile(r"^(?:[^，。；：]{0,12})(?:曰|云|謂|谓|言|問|问)")
_OBJECT_OR_PROTECTED_PREFIX = re.compile(
    r"(?:攻|討|讨|擊|击|伐|征|圍|围|追|拒|殺|杀|翼蔽|庇護|庇护|護|护|救)"
    r"[^，。；：]{0,8}$"
)
_REPORTED_SPEECH_PREFIX = re.compile(r"(?:曰|云|謂|谓|言|問|问)[^，。；：]{0,20}$")
_CLEAR_POSITIVE_RESULT = re.compile(
    r"(?:大破之|擊破之|击破之|破之|攻克|克之|克[㐀-鿿]{1,6}(?=[，。；、：])|"
    r"拔之|平定|平之|擒之|俘(?:斬|斩|其眾|其众)|斬首|斩首|悉平|皆平)"
)
_CLEAR_NEGATIVE_RESULT = re.compile(
    r"(?:不克|未克|不能克|不得進|不得进|敗績|败绩|為.{0,8}所敗|为.{0,8}所败)"
)
_CHRONOLOGY = re.compile(
    r"(?:[一二三四五六七八九十百〇零元]+年|(?:春|夏|秋|冬)，?"
    r"(?:正|一|二|三|四|五|六|七|八|九|十|十一|十二)月|"
    r"(?:甲|乙|丙|丁|戊|己|庚|辛|壬|癸)(?:子|丑|寅|卯|辰|巳|午|未|申|酉|戌|亥))"
)
_LOCATION = re.compile(
    r"[\u3400-\u9fff]{1,5}(?:州|郡|縣|县|城|關|关|河|江|山|谷|原|陂|門|门|鎮|镇)"
)
_TARGET = re.compile(
    r"(?:攻|討|讨|擊|击|伐|征|圍|围|追|拒|破)"
    r"(?:於|于)?([\u3400-\u9fff]{2,8}?)(?=[，。；、：])"
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _normalized(value: object) -> str:
    return "".join(_T2S.convert(str(value)).split())


def _contains_term(value: str, terms: Sequence[str]) -> bool:
    normalized = _normalized(value)
    return any(_normalized(term) in normalized for term in terms if term)


def _direct_action_span(value: str, terms: Sequence[str]) -> bool:
    normalized = _normalized(value)
    for term in terms:
        anchor = _normalized(term)
        start = normalized.find(anchor)
        while start >= 0:
            if (
                normalized.rfind("「", 0, start) > normalized.rfind("」", 0, start)
                or normalized.rfind("『", 0, start) > normalized.rfind("』", 0, start)
                or normalized.rfind("“", 0, start) > normalized.rfind("”", 0, start)
            ):
                start = normalized.find(anchor, start + 1)
                continue
            clause_prefix = re.split(r"[，。；：]", normalized[max(0, start - 24) : start])[-1]
            # A ruler can be the target of an attack or the person being
            # protected.  A later verb in the same source span must not turn
            # that object mention into an executor attribution.  Likewise,
            # names inside another speaker's report are not direct actions.
            if _OBJECT_OR_PROTECTED_PREFIX.search(clause_prefix) or _REPORTED_SPEECH_PREFIX.search(
                clause_prefix
            ):
                start = normalized.find(anchor, start + 1)
                continue
            if re.search(r"(?:從|从|隨|随|會|会)$", normalized[max(0, start - 2) : start]):
                start = normalized.find(anchor, start + 1)
                continue
            after_anchor = normalized[start + len(anchor) :]
            if _SPEECH_AFTER_SUBJECT.match(after_anchor):
                start = normalized.find(anchor, start + 1)
                continue
            # Keep the immediately following result clause: classical event
            # prose commonly writes the action before a comma and its result
            # just after it (for example “引兵追……，大破之”).  Object and
            # protected-person inversions have already been rejected from the
            # left context above, so retaining this short right window does
            # not reintroduce that attribution error.
            local = anchor + after_anchor[:32]
            # A ruler named as the speaker is not thereby the executor of a
            # proposed or predicted action later in the same sentence.
            if re.search(re.escape(anchor) + r"[^，。；：]{0,6}(?:曰|云|謂|谓|言)", local):
                start = normalized.find(anchor, start + 1)
                continue
            if _MILITARY_ACTION.search(local):
                return True
            start = normalized.find(anchor, start + 1)
    return False


def _result_status(value: str, terms: Sequence[str]) -> tuple[str, str, bool]:
    def realized(pattern: re.Pattern[str], suffix: str) -> bool:
        return any(
            not _HYPOTHETICAL_PREFIX.search(suffix[max(0, match.start() - 16) : match.start()])
            for match in pattern.finditer(suffix)
        )

    # A result may safely bypass judgment only when it follows the ruler's
    # own action mention. Generic `X大敗` and withdrawal words are deliberately
    # excluded: without resolving X or the campaign objective their direction
    # is not deterministic.
    term_pattern = re.compile(
        "(?:" + "|".join(re.escape(str(term)) for term in terms if term) + ")"
    )
    suffixes = [
        value[match.end() : match.end() + 56] for match in term_pattern.finditer(value)
    ]
    positive = any(realized(_CLEAR_POSITIVE_RESULT, suffix) for suffix in suffixes)
    negative = any(realized(_CLEAR_NEGATIVE_RESULT, suffix) for suffix in suffixes)
    if positive and negative:
        return "mixed", "mixed", True
    if negative:
        return "failed", "negative", False
    if positive:
        return "completed", "positive", False
    return "unclear", "unclear", True


def _deduplicate_overlapping_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep one stable event for nested quotes cut from the same source unit."""

    selected: list[dict[str, Any]] = []
    for row in sorted(
        events,
        key=lambda item: (
            str(item["page_title"]),
            str(item["segment_ref"]),
            int(item["start_offset"]),
            -int(item["end_offset"]),
        ),
    ):
        if selected:
            prior = selected[-1]
            if (
                prior["page_title"] == row["page_title"]
                and prior["segment_ref"] == row["segment_ref"]
                and int(row["start_offset"]) < int(prior["end_offset"])
            ):
                # The widest quote preserves the chronology and actor context;
                # narrower overlapping cuts add no independent source fact.
                if int(row["end_offset"]) <= int(prior["end_offset"]):
                    continue
        selected.append(dict(row))
    return selected


def _semantic_quote_anchors(value: str, *, limit: int = 24) -> list[str]:
    normalized = _normalized(value)
    anchors: list[str] = []
    for size in (4, 3, 2):
        for start in range(0, max(0, len(normalized) - size + 1)):
            anchor = normalized[start : start + size]
            if not all("\u3400" <= char <= "\u9fff" for char in anchor):
                continue
            if anchor not in anchors:
                anchors.append(anchor)
            if len(anchors) >= limit:
                return anchors
    return anchors


def build_deterministic_campaign_signatures(
    *,
    discovery: Mapping[str, Any],
    identity_resolver: HistoricalEntityResolver,
) -> list[dict[str, Any]]:
    """Convert zero-model discoveries into the existing directed-recall contract."""

    ruler_name = str(discovery["ruler"])
    ruler_ref = str(discovery["ruler_ref"])
    signatures = []
    for event in discovery.get("events") or ():
        quote = str(event["exact_quote"])
        signatures.append(
            {
                "event_ref": str(event["event_ref"]),
                "subject_bindings": [
                    {
                        "subject_ref": ruler_ref,
                        "canonical_name": ruler_name,
                        "recall_terms": list(identity_resolver.recall_terms(ruler_name)),
                    }
                ],
                "chronology_anchors": list(event.get("chronology_anchors") or ()),
                "location_anchors": list(event.get("location_anchors") or ()),
                "action_anchors": list(event.get("action_anchors") or ()),
                "result_anchors": list(event.get("result_anchors") or ()),
                "quote_anchors": _semantic_quote_anchors(quote),
                "backbone_quotes": [
                    {
                        "event_ref": str(event["event_ref"]),
                        "exact_quote": quote,
                        "page_title": str(event["page_title"]),
                        "revision_ref": str(event["revision_ref"]),
                        "segment_ref": str(event["segment_ref"]),
                    }
                ],
                "resolution_status": str(event["resolution_status"]),
            }
        )
    return signatures


def _quote_range(
    spans: Sequence[Mapping[str, Any]], anchor_index: int
) -> tuple[int, int, list[Mapping[str, Any]]]:
    left = anchor_index
    if left > 0 and _CHRONOLOGY.search(str(spans[left - 1]["text"])):
        left -= 1
    right = anchor_index
    while right + 1 < len(spans) and right - anchor_index < 2:
        next_text = str(spans[right + 1]["text"])
        if not (_MILITARY_ACTION.search(next_text) or _POSITIVE_RESULT.search(next_text) or _NEGATIVE_RESULT.search(next_text)):
            break
        right += 1
    selected = list(spans[left : right + 1])
    return (
        int(selected[0]["start_offset"]),
        int(selected[-1]["end_offset"]),
        selected,
    )


def discover_deterministic_backbone_campaigns(
    *,
    backbone_plan: Mapping[str, Any],
    ruler_name: str,
    ruler_ref: str,
    identity_resolver: HistoricalEntityResolver,
) -> dict[str, Any]:
    """Discover direct ruler campaign events without a model or external I/O.

    This layer deliberately stops before scale, final ruler-window attribution,
    or cross-book identity judgment.  Clear local action/result chains can skip
    generic fact extraction; mixed or incomplete chains enter a small judgment
    queue instead of triggering per-segment recursive fallback.
    """

    recall_terms = identity_resolver.recall_terms(ruler_name)
    events: list[dict[str, Any]] = []
    seen_quotes: set[tuple[str, str, int, int]] = set()
    ruler_segment_count = 0
    for batch in backbone_plan.get("page_batches") or ():
        for segment in batch.get("segments") or ():
            if ruler_ref not in {str(value) for value in segment.get("subject_refs") or ()}:
                continue
            ruler_segment_count += 1
            segment_terms = (
                (*recall_terms, *_RULER_PRONOUN_TERMS)
                if segment.get("chronicle_ruler_active")
                else recall_terms
            )
            segment_start = int(segment["start_offset"])
            segment_text = str(segment["text"])
            spans = list(segment.get("spans") or ())
            for index, span in enumerate(spans):
                span_text = str(span["text"])
                if not _contains_term(span_text, segment_terms):
                    continue
                if not _direct_action_span(span_text, segment_terms):
                    continue
                start, end, selected_spans = _quote_range(spans, index)
                quote = segment_text[start - segment_start : end - segment_start]
                quote_key = (str(batch["page_title"]), str(batch["revision_ref"]), start, end)
                if quote_key in seen_quotes:
                    continue
                seen_quotes.add(quote_key)
                result_status, result_direction, needs_judgment = _result_status(
                    quote, segment_terms
                )
                chronology = list(dict.fromkeys(_normalized(value) for value in _CHRONOLOGY.findall(quote)))
                locations = list(dict.fromkeys(_normalized(value) for value in _LOCATION.findall(quote)))
                targets = list(dict.fromkeys(_normalized(value) for value in _TARGET.findall(quote)))
                event_identity = {
                    "policy": POLICY_VERSION,
                    "page_title": batch["page_title"],
                    "revision_ref": batch["revision_ref"],
                    "start": start,
                    "end": end,
                    "ruler_ref": ruler_ref,
                }
                event_ref = "DET-CAMPAIGN-" + _digest(event_identity)[:20].upper()
                fact_id = "DET-FACT-" + _digest([event_ref, quote])[:20].upper()
                events.append(
                    {
                        "event_ref": event_ref,
                        "segment_ref": str(segment["segment_ref"]),
                        "page_title": str(batch["page_title"]),
                        "work_title": str(batch["work_title"]),
                        "source_url": str(batch["source_url"]),
                        "revision_ref": str(batch["revision_ref"]),
                        "start_offset": start,
                        "end_offset": end,
                        "exact_quote": quote,
                        "chronology_anchors": chronology,
                        "location_anchors": locations,
                        "target_anchors": targets,
                        "action_anchors": list(
                            dict.fromkeys(
                                _normalized(match.group(0))
                                for match in _MILITARY_ACTION.finditer(quote)
                            )
                        ),
                        "result_anchors": list(
                            dict.fromkeys(
                                _normalized(match.group(0))
                                for pattern in (_POSITIVE_RESULT, _NEGATIVE_RESULT)
                                for match in pattern.finditer(quote)
                            )
                        ),
                        "result_status": result_status,
                        "result_direction": result_direction,
                        "resolution_status": (
                            "needs_judgment" if needs_judgment else "deterministic_clear"
                        ),
                        "neutral_fact": {
                            "fact_id": fact_id,
                            "exact_quote": quote,
                            "fact_kind": "political_action",
                            "action_summary": "统治者直接实施史料所载军事行动。",
                            "actors": [
                                {
                                    "source_name": next(
                                        (
                                            term
                                            for term in segment_terms
                                            if _contains_term(quote, [term])
                                        ),
                                        ruler_name,
                                    ),
                                    "canonical_name": ruler_name,
                                    "subject_ref": ruler_ref,
                                    "role": "executor",
                                    "responsibility_strength": "primary",
                                    "attribution_basis": "原文在军事行动语法范围内直接记载统治者。",
                                }
                            ],
                            "implementation_status": "completed_work",
                            "result": (
                                "原文明确记载军事行动结果。"
                                if result_status != "unclear"
                                else "原文记载军事行动，结果仍需合并相邻事件判断。"
                            ),
                            "outcome_candidate_status": (
                                "clear_candidate"
                                if not needs_judgment
                                else "ambiguous"
                            ),
                            "outcome_candidate_reason": (
                                "行动、统军责任和结果均可由原文确定。"
                                if not needs_judgment
                                else "行动可确定，整体胜败、目标完成度或事件边界仍需裁决。"
                            ),
                            "uncertainty": "" if not needs_judgment else "不得直接登记最终战役成果。",
                            "evidence_span_refs": [
                                str(value["span_ref"]) for value in selected_spans
                            ],
                            "legacy_status": "not_shown",
                            "legacy_basis": "原文未显示跨期延续。",
                            "projection_eligibility": "direct_neutral_fact",
                        },
                    }
                )
    events = _deduplicate_overlapping_events(events)
    events.sort(
        key=lambda row: (
            row["page_title"],
            int(row["start_offset"]),
            row["event_ref"],
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "ruler": ruler_name,
        "ruler_ref": ruler_ref,
        "source_index_identity": backbone_plan.get("source_index_identity"),
        "ruler_segment_count": ruler_segment_count,
        "event_count": len(events),
        "deterministic_clear_count": sum(
            row["resolution_status"] == "deterministic_clear" for row in events
        ),
        "needs_judgment_count": sum(
            row["resolution_status"] == "needs_judgment" for row in events
        ),
        "model_call_count": 0,
        "database_write_count": 0,
        "formal_write_count": 0,
        "events": events,
    }
