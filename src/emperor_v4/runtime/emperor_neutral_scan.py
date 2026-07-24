from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import os
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4

from opencc import OpenCC

from emperor_v4.adapters.historical_entity_identity import HistoricalEntityResolver
from emperor_v4.adapters.shared_neutral_extraction import (
    OUTPUT_SCHEMA_VERSION,
    build_shared_neutral_extraction_prompt,
    build_shared_neutral_fact_fanout,
)
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.runtime.structured_codex_runner import (
    ModelBatchAnomalyError,
    StructuredCodexRunner,
)


SCHEMA_VERSION = "current-neutral-materials-v2"
NEUTRAL_EXTRACTION_POLICY_VERSION = "current-neutral-extraction-policy-v17"
MODEL_GROUP_CHAR_LIMIT = 6_000
MODEL_GROUP_SEGMENT_LIMIT = 8
MODEL_GROUP_WEIGHT_LIMIT = 16
MODEL_GROUP_SUBJECT_LIMIT = 4
MODEL_SINGLE_BATCH_CHAR_LIMIT = 6_000
MODEL_SINGLE_BATCH_SEGMENT_LIMIT = 8
MODEL_GROUP_PROMPT_CHAR_LIMIT = 6_000
MODEL_SINGLE_PROMPT_CHAR_LIMIT = 7_000
PLAN_SCHEMA_VERSION = "subject-shared-review-plan-v1"
MULTI_OUTPUT_SCHEMA_VERSION = "multi-page-neutral-extraction-output-v2"
COMPACT_OUTPUT_SCHEMA_VERSION = "current-compact-neutral-output-v2"
_T2S = OpenCC("t2s")
_EVENT_TARGET_POLICY_VERSION = "event-directed-backsource-v1"
_NON_PROFILE_ROLES = {"authorizer", "recipient", "affected_person", "mentioned_only"}
_GENERIC_EVENT_ANCHORS = {
    "皇帝", "太宗", "于是", "以为", "可以", "不得", "其事", "之事",
    "之后", "其中", "已经", "进行", "形成", "结果", "相关", "当前",
}
_HIGH_VALUE_REJECT_SIGNALS = {
    "ruler_delegation": (
        re.compile(
            r"(?:命|遣).{0,16}(?:使於|使于|出使|請兵|请兵|將兵|将兵|討|讨|守|援)"
        ),
        re.compile(
            r"(?:以|命).{1,16}(?:為|为).{0,12}"
            r"(?:行軍總管|行军总管|太守|留守|將軍|将军|大使)"
        ),
        re.compile(r"(?:聽|听).{0,8}(?:便宜從事|便宜从事)"),
        re.compile(r"(?:復使|复使).{0,12}(?:鎮撫|镇抚|討|讨|守|援)"),
    ),
    "severe_command_failure": (
        re.compile(r"(?:軍遂潰|军遂溃|失亡略盡|失亡略尽)"),
        re.compile(r"(?:棄州|弃州|棄城|弃城|以城納|以城纳|城陷)"),
        re.compile(r"(?:大敗|大败|不能拒|不能禦|不能御)"),
    ),
}
_COMMON_ERA_YEAR = re.compile(
    r"公元([〇零一二三四五六七八九0-9]{3,4})年"
)
_COMMON_ERA_DIGITS = str.maketrans("〇零一二三四五六七八九", "00123456789")
_RULER_DEATH = re.compile(r"(?:上崩|(?<!先)帝崩)")
_APPOINTMENT_ACTION = (
    r"(?:(?:為|为)(?=[^，；。]{0,16}(?:總管|总管|大使|都督|將軍|将军|"
    r"留守|刺史|太守|可汗|使))|檢校|检校)"
)
_COMMAND_ACTION = (
    r"(?:使於|使于|將兵|将兵|屯|討|讨|守|援|專知|专知|鎮守|镇守)"
)
_ACTOR_TITLE_SUFFIX = re.compile(
    r"(?:大將軍|大将军|中郎將|中郎将|郎將|郎将|將軍|将军|"
    r"大都督|都督|司馬|司马|刺史|御史|大夫|少常伯|長史|长史|"
    r"副率|都護|都护|太守|留守|尚書|尚书|侍郎|駙馬都尉|驸马都尉|"
    r"皇太子|可汗|右肅機|右肃机|大司憲|大司宪|右相|侍中|卿|監|监|尉|守|令|率)"
)
_COLLECTIVE_ACTOR_NAMES = {
    "朝廷", "有司", "百官", "公卿", "官軍", "官军", "王師", "王师",
    "吐蕃", "突厥", "新羅", "新罗", "高麗", "高丽", "百濟", "百济",
    "回紇", "回纥", "軍中", "军中", "諸軍", "诸军",
}


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _layout_exact_quote(quote: str, source_text: str) -> str:
    """Recover the unique original span when only layout whitespace differs."""

    if quote in source_text:
        return quote
    target = "".join(character for character in quote if not character.isspace())
    if not target:
        return quote
    compact = []
    offsets = []
    for offset, character in enumerate(source_text):
        if not character.isspace():
            compact.append(character)
            offsets.append(offset)
    haystack = "".join(compact)
    start = haystack.find(target)
    if start < 0 or haystack.find(target, start + 1) >= 0:
        return quote
    return source_text[offsets[start] : offsets[start + len(target) - 1] + 1]


def _normalized_text_offsets(text: str) -> tuple[str, list[int]]:
    compact = []
    offsets = []
    for offset, character in enumerate(text):
        for converted in _T2S.convert(character):
            if not converted.isspace():
                compact.append(converted)
                offsets.append(offset)
    return "".join(compact), offsets


def _whole_normalized_text_offsets(text: str) -> tuple[str, list[int]]:
    converted = _T2S.convert(text)
    if len(converted) != len(text):
        return _normalized_text_offsets(text)
    compact = []
    offsets = []
    for offset, character in enumerate(converted):
        if not character.isspace():
            compact.append(character)
            offsets.append(offset)
    return "".join(compact), offsets


def _positions_from_normalized(
    haystack: str, offsets: Sequence[int], name: str
) -> list[int]:
    target = "".join(_T2S.convert(name).split())
    positions = []
    start = 0
    while target and (position := haystack.find(target, start)) >= 0:
        positions.append(offsets[position])
        start = position + 1
    return positions


def _normalized_positions(text: str, name: str) -> list[int]:
    haystack, offsets = _normalized_text_offsets(text)
    return _positions_from_normalized(haystack, offsets, name)


def _contains_normalized(text: str, name: str) -> bool:
    return bool(_normalized_positions(text, name))


def _sentence_spans(text: str, *, absolute_start: int = 0) -> list[dict[str, Any]]:
    spans = []
    start = 0
    depth = 0
    open_quotes = "「『“‘"
    close_quotes = "」』”’"
    terminal = "。！？；!?"
    for index, character in enumerate(text):
        if character in open_quotes:
            depth += 1
        elif character in close_quotes:
            depth = max(0, depth - 1)
        split = depth == 0 and (
            character in terminal
            or character == "\n"
            or (
                character in close_quotes
                and index > 0
                and text[index - 1] in terminal
            )
        )
        if split:
            end = index + 1
            if text[start:end].strip():
                spans.append((start, end))
            start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return [
        {
            "span_ref": f"SPAN-{absolute_start + start}-{absolute_start + end}",
            "start_offset": absolute_start + start,
            "end_offset": absolute_start + end,
            "text": text[start:end],
        }
        for start, end in spans
    ]


def _source_event_units(
    text: str, *, max_chars: int = 900, split_offsets: Sequence[int] = ()
) -> list[dict[str, Any]]:
    """Split raw editions on their own entry/paragraph boundaries, then sentences."""

    boundaries = [0]
    pattern = re.compile(
        r"(?:\r?\n\s*){2,}|<BR>\s*(?:\r?\n)?|^\s*=+[^\n]*=+\s*$",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        boundaries.extend((match.start(), match.end()))
    boundaries.append(len(text))
    raw_ranges = []
    for start, end in zip(boundaries, boundaries[1:]):
        if start < end and text[start:end].strip():
            raw_ranges.append((start, end))

    units = []
    for block_start, block_end in raw_ranges:
        spans = _sentence_spans(text[block_start:block_end], absolute_start=block_start)
        if not spans:
            continue
        group = []
        for span in spans:
            if group and any(
                int(group[-1]["end_offset"]) <= int(offset) <= int(span["start_offset"])
                for offset in split_offsets
            ):
                units.append(
                    {
                        "start": group[0]["start_offset"],
                        "end": group[-1]["end_offset"],
                        "spans": group,
                    }
                )
                group = []
            proposed_start = group[0]["start_offset"] if group else span["start_offset"]
            if group and int(span["end_offset"]) - int(proposed_start) > max_chars:
                units.append(
                    {
                        "start": group[0]["start_offset"],
                        "end": group[-1]["end_offset"],
                        "spans": group,
                    }
                )
                group = []
            group.append(span)
        if group:
            units.append(
                {
                    "start": group[0]["start_offset"],
                    "end": group[-1]["end_offset"],
                    "spans": group,
                }
            )
    return units


def _initial_span_range(
    unit: Mapping[str, Any], anchor_positions: Sequence[int], *, target_chars: int = 280
) -> tuple[int, int]:
    spans = list(unit["spans"])
    indices = [
        index
        for index, span in enumerate(spans)
        if any(
            int(span["start_offset"]) <= position < int(span["end_offset"])
            for position in anchor_positions
        )
    ]
    if not indices:
        indices = [0]
    left, right = min(indices), max(indices)
    while True:
        current = int(spans[right]["end_offset"]) - int(spans[left]["start_offset"])
        if current >= target_chars:
            break
        candidates = []
        if left > 0:
            candidates.append((left - 1, right))
        if right + 1 < len(spans):
            candidates.append((left, right + 1))
        candidates = [
            pair
            for pair in candidates
            if int(spans[pair[1]]["end_offset"])
            - int(spans[pair[0]]["start_offset"])
            <= 420
        ]
        if not candidates:
            break
        left, right = min(
            candidates,
            key=lambda pair: int(spans[pair[1]]["end_offset"])
            - int(spans[pair[0]]["start_offset"]),
        )
    return int(spans[left]["start_offset"]), int(spans[right]["end_offset"])


def _biography_section_ranges(
    text: str,
    subjects: Sequence[str],
    identity_resolver: HistoricalEntityResolver,
) -> dict[str, tuple[int, int]]:
    headings = list(re.finditer(r"(?m)^\s*==+\s*([^\n=]+?)\s*==+\s*$", text))
    ranges: dict[str, tuple[int, int]] = {}
    for index, heading in enumerate(headings):
        title = heading.group(1)
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        for subject in subjects:
            if any(
                _contains_normalized(title, term)
                for term in identity_resolver.recall_terms(subject)
            ):
                ranges[subject] = (heading.start(), end)
    return ranges


_CHRONICLE_HEADING = re.compile(r"(?m)^\s*=+\s*([^\n=]+?)\s*=+\s*$")
_CHRONICLE_YEAR_HEADING = re.compile(
    r"(?:元|[一二三四五六七八九十百]{1,4})年"
)
_CHRONICLE_TERMINAL_HEADING = re.compile(
    r"^(?:贊|赞|校勘記|校勘记|附錄|附录|表|序)$"
)


def _page_order_key(page: Any) -> tuple[str, int, str]:
    match = re.search(r"卷0*([0-9]+)", str(page.page_title))
    return (
        str(page.work_title),
        int(match.group(1)) if match else 10**9,
        str(page.page_title),
    )


def _chronicle_ruler_active_ranges(
    pages: Sequence[Any],
    *,
    ruler_name: str,
    identity_resolver: HistoricalEntityResolver,
    ruler_window: str | None = None,
    ruler_heading_terms: Sequence[str] = (),
) -> dict[str, list[tuple[int, int]]]:
    """Locate reign-heading ranges where chronicle pronouns mean this ruler.

    The configured volume range can include pre-accession campaigns and a
    successor transition. Explicit ruler aliases remain usable everywhere,
    while ``上``/``帝`` attribution is enabled only below a matching emperor
    heading and disabled at the next different emperor heading.
    """

    ruler_terms = tuple(
        _normalized_anchor(term)
        for term in identity_resolver.recall_terms(ruler_name)
        if term
    )
    heading_terms = tuple(
        dict.fromkeys(
            _normalized_anchor(term)
            for term in ruler_heading_terms
            if str(term).strip()
        )
    )
    window_match = re.fullmatch(r"\s*(\d{3,4})\s*-\s*(\d{3,4})\s*", ruler_window or "")
    window_bounds = (
        (int(window_match.group(1)), int(window_match.group(2)))
        if window_match is not None
        else None
    )
    ranges_by_page: dict[str, list[tuple[int, int]]] = {}
    active = False
    current_work = None
    for page in sorted(pages, key=_page_order_key):
        if current_work != str(page.work_title):
            active = False
            current_work = str(page.work_title)
        transitions = [(0, active)]
        for match in _CHRONICLE_HEADING.finditer(str(page.raw_text)):
            heading = _normalized_anchor(match.group(1))
            year_match = _COMMON_ERA_YEAR.search(match.group(1))
            common_era_year = (
                int(year_match.group(1).translate(_COMMON_ERA_DIGITS))
                if year_match is not None
                else None
            )
            within_window = (
                window_bounds is None
                or common_era_year is None
                or window_bounds[0] <= common_era_year <= window_bounds[1]
            )
            target_heading = any(
                term in heading for term in (*ruler_terms, *heading_terms)
            )
            if target_heading:
                next_state = within_window
            elif (
                "皇帝" in heading
                or _CHRONICLE_YEAR_HEADING.search(heading)
                or _CHRONICLE_TERMINAL_HEADING.fullmatch(heading)
            ):
                next_state = False
            else:
                # Editorial or nested topical headings do not silently end a
                # reign. Only another emperor/year or a terminal appendix can.
                next_state = transitions[-1][1]
            transitions.append((int(match.start()), next_state))
        if active or any(state for _, state in transitions):
            for death in _RULER_DEATH.finditer(str(page.raw_text)):
                transitions.append((int(death.start()), False))
        transitions.sort(key=lambda row: row[0])
        page_ranges = []
        for index, (start, state) in enumerate(transitions):
            end = (
                transitions[index + 1][0]
                if index + 1 < len(transitions)
                else len(str(page.raw_text))
            )
            if state and start < end:
                page_ranges.append((start, end))
        active = transitions[-1][1]
        ranges_by_page[str(page.page_title)] = page_ranges
    return ranges_by_page


def _candidate_actor_name(value: str) -> str | None:
    value = value.strip("，。、；：『』「」“” ")
    value = re.sub(r"^(?:以|其弟|其子|其將|其将|則|则|召)", "", value)
    matches = list(_ACTOR_TITLE_SUFFIX.finditer(value))
    if matches:
        value = value[matches[-1].end():]
    value = value.strip("，。、；： ")
    simplified = _T2S.convert(value)
    if (
        not re.fullmatch(r"[\u3400-\u9fff]{2,5}", value)
        or any(
            marker in value
            for marker in (
                "其", "等", "代", "並", "并", "俱", "若", "乃", "為", "为",
                "所", "與", "与", "之", "言", "地", "宮", "宫", "軍", "军",
                "兵", "官", "事", "術", "术", "詔", "诏", "命",
            )
        )
        or simplified in {
            "唯别", "上金", "旧安西夏", "妾请", "虏相", "皇帝", "吾属", "兴昔亡"
        }
        or simplified.endswith(("先", "果", "至京", "擐甲"))
    ):
        return None
    if (
        value in _COLLECTIVE_ACTOR_NAMES
        or simplified in {_T2S.convert(name) for name in _COLLECTIVE_ACTOR_NAMES}
        or simplified.endswith(("国", "军", "兵", "众", "部", "州", "县", "城"))
    ):
        return None
    return value


def _explicit_actor_names(text: str) -> list[str]:
    """Return only names occupying an explicit appointment/command slot."""

    candidates = []
    trigger_prefix = r"(?:^|[，；。]|上)(?:仍|乃|又|因)?"
    for triggers, action in (
        (r"(?:詔起|诏起|詔以|诏以|詔|诏|以)", _APPOINTMENT_ACTION),
        (r"(?:敕|命|遣)", _COMMAND_ACTION),
    ):
        for match in re.finditer(
            rf"{trigger_prefix}{triggers}"
            rf"(?P<prefix>[^，；。：「」\n]{{2,30}}?)(?={action})",
            text,
        ):
            candidate = _candidate_actor_name(match.group("prefix"))
            if candidate:
                candidates.append(candidate)
    for match in re.finditer(
        rf"(?:^|[，；、])(?P<name>[\u3400-\u9fff]{{2,6}})"
        rf"(?=為(?:[\u3400-\u9fff]{{0,12}}(?:總管|总管|大使|都督|將軍|将军|留守)))",
        text,
    ):
        candidate = _candidate_actor_name(match.group("name"))
        if candidate:
            candidates.append(candidate)
    for match in re.finditer(
        r"(?:^|[，；。])(?P<name>[\u3400-\u9fff]{2,6})(?:等)?"
        r"(?=引兵|帥|率兵|棄軍|弃军|拒守)",
        text,
    ):
        candidate = _candidate_actor_name(match.group("name"))
        if candidate:
            candidates.append(candidate)
    return list(dict.fromkeys(candidates))


def _canonicalize_result(
    batch: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    subject_ref_by_name: Mapping[str, str],
    identity_resolver: HistoricalEntityResolver | None = None,
    drop_unverifiable_quotes: bool = False,
) -> dict[str, Any]:
    """Apply deterministic identity binding and layout-only quote recovery."""

    canonical = json.loads(json.dumps(result, ensure_ascii=False))
    canonical["schema_version"] = OUTPUT_SCHEMA_VERSION
    segments = {
        str(segment["segment_ref"]): segment for segment in batch["segments"]
    }
    dropped_quote = False
    deduplicated_fact = False
    for review in canonical.get("segment_reviews") or ():
        segment = segments.get(str(review.get("segment_ref") or ""))
        if segment is None:
            continue
        allowed = {str(value) for value in segment.get("subject_refs") or ()}
        source_text = str(segment["text"])
        retained_facts = []
        retained_fact_digests: set[str] = set()
        for fact in review.get("facts") or ():
            legacy_status = str(fact.get("outcome_candidate_status") or "")
            fact["outcome_candidate_status"] = {
                "clear_candidate": "direct_outcome_candidate",
                "ambiguous": "linkable_chain_fact",
                "clear_non_candidate": "context_only",
            }.get(legacy_status, legacy_status or "linkable_chain_fact")
            if not fact.get("evidence_roles"):
                roles = []
                if fact.get("implementation_status") in {
                    "proposed", "adopted", "implemented",
                    "nationally_promulgated", "completed_work",
                }:
                    roles.append(
                        "measure_or_design"
                        if fact.get("implementation_status") in {"proposed", "adopted"}
                        else "implementation_or_operation"
                    )
                if str(fact.get("result") or "").strip():
                    roles.append("public_result")
                if fact.get("legacy_status") not in {None, "", "not_shown"}:
                    roles.append("continuity_or_reversal")
                if fact.get("actors"):
                    roles.append("responsibility_or_attribution")
                fact["evidence_roles"] = list(dict.fromkeys(roles)) or [
                    "historical_baseline"
                ]
            fact.setdefault("effect_domains", [])
            fact.setdefault("evidence_span_refs", [])
            spans = {
                str(row["span_ref"]): str(row["text"])
                for row in segment.get("spans") or ()
            }
            evidence_spans = [
                spans[ref]
                for ref in fact["evidence_span_refs"]
                if ref in spans
            ]
            fact["exact_quote"] = _layout_exact_quote(
                str(fact.get("exact_quote") or ""), source_text
            )
            if fact["exact_quote"] not in source_text and evidence_spans:
                reconstructed = "".join(evidence_spans)
                if reconstructed in source_text:
                    fact["exact_quote"] = reconstructed
            quote_verified = bool(fact["exact_quote"]) and fact["exact_quote"] in source_text
            for actor in fact.get("actors") or ():
                source_name = str(actor.get("source_name") or "")
                resolution = (
                    identity_resolver.resolve(
                        source_name,
                        allowed_subject_refs=sorted(allowed),
                    )
                    if identity_resolver is not None
                    else None
                )
                if resolution is not None and resolution.status == "resolved":
                    actor["canonical_name"] = resolution.canonical_name
                    actor["subject_ref"] = resolution.person_ref
                elif identity_resolver is not None:
                    mapped = subject_ref_by_name.get(
                        str(actor.get("canonical_name") or "")
                    ) or subject_ref_by_name.get(source_name)
                    actor["subject_ref"] = mapped if mapped in allowed else None
                else:
                    mapped = subject_ref_by_name.get(
                        str(actor.get("canonical_name") or "")
                    )
                    actor["subject_ref"] = mapped if mapped in allowed else None
            owned = any(
                actor.get("subject_ref") in allowed
                and actor.get("role") != "mentioned_only"
                for actor in fact.get("actors") or ()
            )
            actor_optional = not fact.get("actors") and bool(
                set(fact["evidence_roles"])
                & {
                    "historical_baseline",
                    "public_result",
                    "public_cost_or_harm",
                    "continuity_or_reversal",
                }
            )
            fact_digest = _digest(fact)
            if (
                (owned or actor_optional)
                and (quote_verified or not drop_unverifiable_quotes)
                and fact_digest in retained_fact_digests
            ):
                deduplicated_fact = True
            elif (owned or actor_optional) and (
                quote_verified or not drop_unverifiable_quotes
            ):
                retained_facts.append(fact)
                retained_fact_digests.add(fact_digest)
            elif owned and not quote_verified:
                dropped_quote = True
        review["facts"] = retained_facts
        if not retained_facts:
            review["decision"] = "reject"
            review["reason"] = "片段未形成归属于当前召回主体的直接中性事实。"
        review.setdefault("context_status", "sufficient")
    if dropped_quote:
        canonical["limitations"] = sorted(
            {
                *[str(value) for value in canonical.get("limitations") or ()],
                "引文重试后仍无法逐字回指的事实已拒绝接纳。",
            }
        )
    if deduplicated_fact:
        canonical["limitations"] = sorted(
            {
                *[str(value) for value in canonical.get("limitations") or ()],
                "模型返回的完全重复中性事实已确定性去重。",
            }
        )
    return canonical


def build_high_value_reject_review(
    *,
    plan: Mapping[str, Any],
    materials: Mapping[str, Any],
) -> dict[str, Any]:
    """Find model rejects that carry strong appointment or command-result signals."""

    segments = {
        str(segment["segment_ref"]): {
            "page_title": str(batch.get("page_title") or ""),
            "revision_ref": str(
                batch.get("revision_ref") or batch.get("revision_id") or ""
            ),
            **dict(segment),
        }
        for batch in plan.get("page_batches") or ()
        for segment in batch.get("segments") or ()
    }
    reviews = {
        str(review["segment_ref"]): review
        for result in materials.get("batch_results") or ()
        for review in result.get("segment_reviews") or ()
        if review.get("segment_ref")
    }
    candidates = []
    for segment_ref, segment in sorted(segments.items()):
        review = reviews.get(segment_ref)
        if (
            review is None
            or str(review.get("decision") or "") != "reject"
            or review.get("facts")
            or not segment.get("subject_refs")
        ):
            continue
        text = str(segment.get("text") or "")
        signal_codes = [
            signal_code
            for signal_code, patterns in _HIGH_VALUE_REJECT_SIGNALS.items()
            if any(pattern.search(text) for pattern in patterns)
        ]
        if not signal_codes:
            continue
        candidates.append(
            {
                "segment_ref": segment_ref,
                "page_title": str(segment.get("page_title") or ""),
                "revision_ref": str(
                    segment.get("revision_ref")
                    or segment.get("revision_id")
                    or ""
                ),
                "subject_refs": sorted(
                    str(value) for value in segment.get("subject_refs") or ()
                ),
                "subject_names": sorted(
                    str(value) for value in segment.get("subject_names") or ()
                ),
                "chronicle_ruler_ref": (
                    str(segment["chronicle_ruler_ref"])
                    if segment.get("chronicle_ruler_ref")
                    else None
                ),
                "signal_codes": signal_codes,
                "text": text,
                "model_reject_reason": str(review.get("reason") or ""),
            }
        )
    return {
        "schema_version": "high-value-neutral-reject-review-v1",
        "status": "pending_main_session_review" if candidates else "clear",
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_multi_page_output_schema(single_schema_path: Path) -> dict[str, Any]:
    single = json.loads(single_schema_path.read_text(encoding="utf-8"))
    result_schema = {key: value for key, value in single.items() if key != "$schema"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "results"],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": MULTI_OUTPUT_SCHEMA_VERSION,
            },
            "results": {
                "type": "array",
                "items": result_schema,
            },
        },
    }


def build_compact_multi_output_schema(single_schema_path: Path) -> dict[str, Any]:
    single = json.loads(single_schema_path.read_text(encoding="utf-8"))
    fact = single["properties"]["segment_reviews"]["items"]["properties"]["facts"]["items"]
    retained = {
        key: fact["properties"][key]
        for key in (
            "exact_quote", "fact_kind", "action_summary", "actors",
            "implementation_status", "result", "outcome_candidate_status",
            "outcome_candidate_reason", "uncertainty", "evidence_roles",
            "effect_domains",
        )
    }
    retained["segment_ref"] = {"type": "string", "minLength": 1}
    compact_fact = {
        "type": "object", "additionalProperties": False,
        "required": list(retained), "properties": retained,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "required": ["schema_version", "results"],
        "properties": {
            "schema_version": {"type": "string", "const": COMPACT_OUTPUT_SCHEMA_VERSION},
            "results": {
                "type": "array",
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["batch_ref", "facts", "context_requests", "limitations"],
                    "properties": {
                        "batch_ref": {"type": "string", "minLength": 1},
                        "facts": {"type": "array", "items": compact_fact},
                        "context_requests": {
                            "type": "array",
                            "items": {
                                "type": "object", "additionalProperties": False,
                                "required": ["segment_ref", "context_status"],
                                "properties": {
                                    "segment_ref": {"type": "string", "minLength": 1},
                                    "context_status": {
                                        "type": "string",
                                        "enum": ["need_previous_block", "need_next_block", "need_both"],
                                    },
                                },
                            },
                        },
                        "limitations": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }


def build_compact_multi_page_prompt(
    batches: Sequence[Mapping[str, Any]], *, strict_quotes: bool = False
) -> str:
    return (
        "EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS\nTOOLS: FORBIDDEN\nOUTPUT: JSON_ONLY\n\n"
        "你是皇帝评价V4的中性历史事件发现器。只读INPUT_BATCHES，不联网、不评分、不补史实。\n"
        "提取与当前窗口直接相关的历史基线、实际行动、命令、建议、任用授权、制度运行、"
        "战役、可观察公共结果、政治风险、重要代价和跨期延续；普通仪礼宴饮及仅被提名者不收。\n"
        "编年主干若给出chronicle_ruler_ref，只能将‘上’、‘帝’、‘车驾’等皇帝代称绑定到"
        "subject_ref等于该值的人物；未给出时必须依靠本段明确姓名或别名。\n"
        "exact_quote逐字复制segment.text的连续原文；actors只能复制batch.subject_bindings中"
        "subject_ref同时列在该segment.subject_refs内的人物，"
        "人物没有直接行动或责任不得创建actor。宏观基线、公共结果、成本或持续性可以actors=[]。"
        "segment_ref逐字复制输入。\n"
        "evidence_roles按事实选择historical_baseline/measure_or_design/implementation_or_operation/"
        "public_result/public_cost_or_harm/continuity_or_reversal/responsibility_or_attribution；"
        "effect_domains只标公共效果相关领域，不判断正负。"
        "行动、结果、责任单条闭合填direct_outcome_candidate；仅闭合一环但可跨史源连接填"
        "linkable_chain_fact；只作上下文填context_only；无关填irrelevant。不得把无结果的措施、"
        "无人物的宏观结果或单独责任片段直接判无关。\n"
        "只缺紧邻上下文时写入context_requests；无事实且无需扩窗的片段完全省略。"
        "每个INPUT_BATCHES元素即使facts和context_requests都为空，也必须返回一个results元素；"
        "不得省略整个batch。"
        + (
            "这是引文校验重试：exact_quote必须原样连续复制，不得转写、节略或拼接。\n"
            if strict_quotes else ""
        )
        + f"顶层schema_version必须是{COMPACT_OUTPUT_SCHEMA_VERSION}。\n\nINPUT_BATCHES:\n"
        + json.dumps(batches, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def build_multi_page_prompt(
    batches: Sequence[Mapping[str, Any]], *, strict_quotes: bool = False
) -> str:
    policy = build_shared_neutral_extraction_prompt({}).split("INPUT_BATCH:\n", 1)[0]
    return (
        policy
        + "每个输入批次必须各返回一个完整结果，放入 results；不得合并不同页面。\n"
        + "segment_reviews 使用稀疏输出：只返回 facts 非空，或 context_status 不是 sufficient 的片段；"
        + "其余已读但无合格事实的片段不要返回，程序会确定性补为 reject。"
        + "segment_count 仍须填写输入批次的全部片段数。\n"
        + "只抽取直接归属于当前 segment.subject_bindings 的事实；每个 fact 至少一个非 mentioned_only actor，"
        + "其 canonical_name 与 subject_ref 必须逐字复制同一条 subject_bindings。"
        + "片段内仅涉及旁人、后朝或其他事项且召回主体不是行为参与者的事实不得输出。\n"
        + "actor 的 canonical_name 与 subject_ref 只能从 subject_bindings 选择；source_name 逐字抄原文称谓。"
        + "若人物仅靠省称、旧名或避讳名出现，按 subject_bindings.aliases 解析，不得按字形相近猜测。\n"
        + f"顶层 schema_version 必须是 {MULTI_OUTPUT_SCHEMA_VERSION}。\n\n"
        + (
            "这是引文校验重试：exact_quote 必须从 segment.text 原样复制，"
            "包括繁简字、标点和空白，不得转写、节略、拼接或补字。\n\n"
            if strict_quotes
            else ""
        )
        + "INPUT_BATCHES:\n"
        + json.dumps(batches, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _prompt_segment_view(
    segment: Mapping[str, Any], *, context_status: str = "sufficient"
) -> dict[str, Any]:
    full_start = int(segment["start_offset"])
    full_end = int(segment["end_offset"])
    start = int(segment.get("initial_start_offset", full_start))
    end = int(segment.get("initial_end_offset", full_end))
    # Directed source hits are already bounded event units. Sending their small
    # adjacent context delta up front avoids one serial model round trip per
    # context request while retaining every recalled unit.
    if segment.get("source_role") in {"backsource", "supplement"}:
        start = full_start
        end = full_end
    if context_status in {"need_previous_block", "need_both"}:
        start = full_start
    if context_status in {"need_next_block", "need_both"}:
        end = full_end
    full_text = str(segment["text"])
    visible_text = full_text[start - full_start : end - full_start]
    return {
        "segment_ref": str(segment["segment_ref"]),
        "subject_refs": [str(value) for value in segment.get("subject_refs") or ()],
        **(
            {"chronicle_ruler_active": bool(segment["chronicle_ruler_active"])}
            if "chronicle_ruler_active" in segment
            else {}
        ),
        **(
            {"chronicle_ruler_ref": str(segment["chronicle_ruler_ref"])}
            if segment.get("chronicle_ruler_ref")
            else {}
        ),
        **(
            {"source_role": str(segment["source_role"])}
            if segment.get("source_role")
            else {}
        ),
        "text": visible_text,
        # Span lineage is assigned deterministically from the returned exact
        # quote against the complete internal segment.  It is not a model
        # output field, so sending span text/offsets only duplicated metadata.
    }


def _model_group_weight(segments: Sequence[Mapping[str, Any]]) -> int:
    return sum(max(1, int(segment.get("model_weight") or 1)) for segment in segments)


def _model_group_subject_refs(segments: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(subject_ref)
        for segment in segments
        for subject_ref in segment.get("subject_refs") or ()
    }


def build_ruler_neutral_plan(
    *,
    source_pack: Mapping[str, Any],
    source_index: LocalSourceTextIndex,
    inventory: Mapping[str, Any],
    identity_resolver: HistoricalEntityResolver,
    allowed_works: Sequence[str] | None = None,
    allowed_page_ranges: Mapping[str, Sequence[int]] | None = None,
    shared_subjects: Mapping[str, str] | None = None,
    ruler_window: str | None = None,
    discover_explicit_actors: bool = True,
    ruler_heading_terms: Sequence[str] = (),
) -> dict[str, Any]:
    continuous_backbone = bool(allowed_page_ranges)
    bounded_independent_window = bool(
        continuous_backbone
        and not shared_subjects
        and re.fullmatch(r"\s*\d{3,4}\s*-\s*\d{3,4}\s*", ruler_window or "")
    )
    ruler_name = str(source_pack["ruler"])
    subject_refs = {
        str(source_pack["ruler"]): str(source_pack["ruler_ref"]),
        **{
            str(row["person"]): str(row["person_ref"])
            for row in source_pack.get("members") or ()
        },
        **{str(name): str(ref) for name, ref in (shared_subjects or {}).items()},
    }
    page_subjects: dict[str, set[str]] = {}
    allowed_work_set = set(str(value) for value in allowed_works or ())
    for row in inventory.get("subjects") or ():
        name = str(row["subject"])
        for page_title in row.get("pages") or ():
            if allowed_work_set and str(page_title).split("/", 1)[0] not in allowed_work_set:
                continue
            page_subjects.setdefault(str(page_title), set()).add(name)
    # The chronicle range is the ruler's continuous event backbone, not another
    # name-recall pool. Every source event unit is retained. Explicit aliases
    # bind pre-accession actions, while reign headings safely bind ruler
    # pronouns after accession; known members are bindings, never scan gates.
    if continuous_backbone:
        for page in source_index.iter_pages(
            works=sorted(allowed_work_set), page_ranges=allowed_page_ranges
        ):
            page_subjects[page.page_title] = set(subject_refs)
    works = sorted({page.split("/", 1)[0] for page in page_subjects})
    pages = {
        page.page_title: page
        for page in source_index.iter_pages(
            works=works, page_ranges=allowed_page_ranges
        )
    }
    chronicle_ranges_by_ruler = {
        name: _chronicle_ruler_active_ranges(
            list(pages.values()),
            ruler_name=name,
            identity_resolver=identity_resolver,
            ruler_window=ruler_window if name == ruler_name else None,
            ruler_heading_terms=ruler_heading_terms if name == ruler_name else (),
        )
        for name in ([ruler_name, *sorted(shared_subjects or {})] if continuous_backbone else [])
    }
    biography_subjects: dict[str, set[str]] = {}
    for member in source_pack.get("members") or ():
        biography = ((member.get("profile_review") or {}).get("full_lifecycle_biography") or {})
        if biography.get("source_page"):
            biography_subjects.setdefault(str(biography["source_page"]), set()).add(
                str(member["person"])
            )
    batches = []
    provisional_subject_bindings: dict[str, dict[str, Any]] = {}
    dynasty_token = identity_resolver.entity_for_name(ruler_name).dynasty
    for page_title, names in sorted(page_subjects.items()):
        page = pages.get(page_title)
        if page is None:
            continue
        full_biography_names = biography_subjects.get(page_title, set())
        biography_ranges = _biography_section_ranges(
            page.raw_text, sorted(names), identity_resolver
        )
        if len(full_biography_names) == 1:
            subject = next(iter(full_biography_names))
            biography_ranges.setdefault(subject, (0, len(page.raw_text)))
        normalized_page, normalized_offsets = _normalized_text_offsets(page.raw_text)
        positions_by_name = {
            name: sorted(
                {
                    position
                    for term in identity_resolver.recall_terms(name)
                    for position in _positions_from_normalized(
                        normalized_page, normalized_offsets, term
                    )
                }
                | (
                    set()
                    if continuous_backbone
                    else {
                        match.start()
                        for term in identity_resolver.contextual_terms(name)
                        for match in re.finditer(re.escape(term), page.raw_text)
                    }
                )
            )
            for name in names
        }
        units = _source_event_units(
            page.raw_text,
            max_chars=420 if biography_ranges else 900,
            split_offsets=[
                match.start() for match in _RULER_DEATH.finditer(page.raw_text)
            ],
        )
        selected: dict[tuple[int, int], dict[str, Any]] = {}
        for unit in units:
            unit_start, unit_end = int(unit["start"]), int(unit["end"])
            matched_names = {
                name
                for name, (section_start, section_end) in biography_ranges.items()
                if section_start <= unit_start < section_end
            }
            anchor_positions = []
            for name in sorted(names):
                positions = [
                    position
                    for position in positions_by_name[name]
                    if unit_start <= position < unit_end
                ]
                anchor_positions.extend(positions)
                if positions:
                    matched_names.add(name)
            active_ruler_names = [
                name
                for name, ranges_by_page in chronicle_ranges_by_ruler.items()
                if any(
                    start <= unit_start < end
                    for start, end in ranges_by_page.get(page.page_title, ())
                )
            ]
            matched_names.update(active_ruler_names)
            ruler_active = ruler_name in active_ruler_names
            if ruler_active:
                matched_names.add(ruler_name)
            if not continuous_backbone and not matched_names:
                continue
            if continuous_backbone or matched_names & set(biography_ranges):
                initial_start, initial_end = unit_start, unit_end
            else:
                initial_start, initial_end = _initial_span_range(
                    unit, anchor_positions
                )
            selected[(unit_start, unit_end)] = {
                **unit,
                "names": matched_names,
                "initial_start": initial_start,
                "initial_end": initial_end,
                "chronicle_ruler_active": ruler_active,
                "chronicle_ruler_ref": (
                    subject_refs[active_ruler_names[0]]
                    if len(active_ruler_names) == 1
                    else None
                ),
            }
        segments = []
        for row in selected.values():
            text = page.raw_text[int(row["start"]): int(row["end"])]
            names_in_text_set = set(row["names"])
            if bounded_independent_window and not row["chronicle_ruler_active"]:
                names_in_text_set.clear()
            if allowed_page_ranges:
                normalized_segment = _normalized_anchor(text)
                # Directed backsource pages are often selected through a
                # minister biography.  The same event unit can still contain
                # an explicit ruler or another shared subject action.  Bind
                # every configured subject that is actually named in the
                # retained unit so the extractor does not reject the real
                # actor merely because a different biography recalled it.
                configured_names = [
                    ruler_name,
                    *(str(member["person"]) for member in source_pack.get("members") or ()),
                    *(str(name) for name in (shared_subjects or {})),
                ]
                for member_name in (
                    dict.fromkeys(configured_names)
                    if not bounded_independent_window
                    or row["chronicle_ruler_active"]
                    else ()
                ):
                    if any(
                        _normalized_anchor(term) in normalized_segment
                        for term in identity_resolver.recall_terms(member_name)
                        if term
                    ):
                        names_in_text_set.add(member_name)
                for actor_name in (
                    _explicit_actor_names(text)
                    if discover_explicit_actors
                    and (
                        not bounded_independent_window
                        or row["chronicle_ruler_active"]
                    )
                    else ()
                ):
                    try:
                        resolved = identity_resolver.resolve_any(
                            actor_name, dynasty=dynasty_token
                        )
                    except ValueError:
                        resolved = None
                    if resolved is not None and resolved.status == "resolved":
                        names_in_text_set.add(str(resolved.canonical_name))
                        continue
                    canonical_name = _T2S.convert(actor_name)
                    person_ref = (
                        "PER-ACTOR-"
                        + sha256(
                            f"{dynasty_token.upper()}::{canonical_name}".encode("utf-8")
                        ).hexdigest()[:12].upper()
                    )
                    subject_refs.setdefault(canonical_name, person_ref)
                    provisional_subject_bindings[person_ref] = {
                        "subject_ref": person_ref,
                        "canonical_name": canonical_name,
                        "aliases": [
                            {
                                "surface": actor_name,
                                "alias_type": "source_surface",
                                "contextual": False,
                            }
                        ],
                        "identity_status": "provisional_actor_name",
                    }
                    names_in_text_set.add(canonical_name)
            names_in_text = sorted(names_in_text_set)
            refs = sorted(subject_refs[name] for name in names_in_text)
            identity = {
                "page_title": page.page_title,
                "revision_ref": page.revision_ref,
                "start": row["start"],
                "end": row["end"],
                "subject_refs": refs,
            }
            segments.append(
                {
                    "segment_ref": "SEG-AUTO-" + _digest(identity)[:20].upper(),
                    "start_offset": row["start"],
                    "end_offset": row["end"],
                    "text": text,
                    "initial_start_offset": row["initial_start"],
                    "initial_end_offset": row["initial_end"],
                    "initial_text": page.raw_text[
                        int(row["initial_start"]): int(row["initial_end"])
                    ],
                    "spans": row["spans"],
                    "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
                    "subject_refs": refs,
                    "subject_names": names_in_text,
                    **(
                        {
                            "chronicle_ruler_active": bool(
                                row["chronicle_ruler_active"]
                            )
                        }
                        if continuous_backbone
                        else {}
                    ),
                    **(
                        {"chronicle_ruler_ref": str(row["chronicle_ruler_ref"])}
                        if row.get("chronicle_ruler_ref")
                        else {}
                    ),
                }
            )
        if not segments:
            continue
        shards: list[list[dict[str, Any]]] = []
        shard: list[dict[str, Any]] = []
        shard_chars = 0
        shard_subject_refs: set[str] = set()
        for segment in segments:
            segment_chars = len(str(segment["initial_text"]))
            segment_subject_refs = _model_group_subject_refs([segment])
            if shard and (
                shard_chars + segment_chars > 4800
                or len(shard) >= MODEL_GROUP_SEGMENT_LIMIT
                or len(shard_subject_refs | segment_subject_refs)
                > MODEL_GROUP_SUBJECT_LIMIT
            ):
                shards.append(shard)
                shard = []
                shard_chars = 0
                shard_subject_refs = set()
            shard.append(segment)
            shard_chars += segment_chars
            shard_subject_refs.update(segment_subject_refs)
        if shard:
            shards.append(shard)
        for shard_segments in shards:
            batch_ref = "BATCH-AUTO-" + _digest(
                {
                    "page_title": page.page_title,
                    "revision_ref": page.revision_ref,
                    "segments": [row["segment_ref"] for row in shard_segments],
                }
            )[:20].upper()
            batches.append(
                {
                    "batch_ref": batch_ref,
                    "page_title": page.page_title,
                    "work_title": page.work_title,
                    "source_url": page.source_url,
                    "revision_ref": page.revision_ref,
                    "segments": shard_segments,
                }
            )
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "ruler": source_pack["ruler"],
        "source_index_identity": source_index.identity,
        "mention_index_fingerprint": _digest(
            {
                "ruler": source_pack["ruler"],
                "subjects": subject_refs,
                "identity_bindings": [
                    *identity_resolver.bindings(sorted(subject_refs.values())),
                    *[
                        provisional_subject_bindings[key]
                        for key in sorted(provisional_subject_bindings)
                    ],
                ],
                "allowed_works": sorted(allowed_work_set),
                "allowed_page_ranges": dict(allowed_page_ranges or {}),
                "ruler_heading_terms": sorted(
                    str(value) for value in ruler_heading_terms
                ),
                "segmentation": NEUTRAL_EXTRACTION_POLICY_VERSION,
            }
        ),
        "provisional_subject_bindings": [
            provisional_subject_bindings[key]
            for key in sorted(provisional_subject_bindings)
        ],
        "page_batches": batches,
    }


def _normalized_anchor(value: str) -> str:
    return "".join(_T2S.convert(str(value)).split())


def _safe_recall_terms(
    identity_resolver: HistoricalEntityResolver, canonical_name: str
) -> tuple[str, ...]:
    try:
        return identity_resolver.recall_terms(canonical_name)
    except ValueError:
        return (canonical_name,)


def _semantic_event_anchors(
    values: Sequence[str], *, limit: int = 24
) -> list[str]:
    anchors_by_size: dict[int, list[str]] = {4: [], 3: [], 2: []}
    for value in values:
        for raw_run in re.findall(r"[\u3400-\u9fff]+", str(value)):
            run = _normalized_anchor(raw_run)
            for size in (4, 3, 2):
                for offset in range(0, max(0, len(run) - size + 1)):
                    anchor = run[offset : offset + size]
                    if (
                        anchor in _GENERIC_EVENT_ANCHORS
                        or anchor in anchors_by_size[size]
                    ):
                        continue
                    anchors_by_size[size].append(anchor)

    def evenly(values: Sequence[str], count: int) -> list[str]:
        if not values or count <= 0:
            return []
        if len(values) <= count:
            return list(values)
        if count == 1:
            return [values[0]]
        return list(
            dict.fromkeys(
                values[round(index * (len(values) - 1) / (count - 1))]
                for index in range(count)
            )
        )

    quotas = (max(1, limit * 2 // 3), max(1, limit // 4))
    anchors = [
        *evenly(anchors_by_size[4], quotas[0]),
        *evenly(anchors_by_size[3], quotas[1]),
    ]
    anchors.extend(
        evenly(anchors_by_size[2], max(0, limit - len(anchors)))
    )
    return anchors[:limit]


def _chronology_event_anchors(value: str) -> list[str]:
    patterns = (
        r"(?:武德|貞觀|贞观)?(?:元|[一二三四五六七八九十]{1,3})年",
        r"(?:春|夏|秋|冬)?(?:正|[一二三四五六七八九十]{1,3})月(?:[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])?",
    )
    return list(
        dict.fromkeys(
            _normalized_anchor(match.group(0))
            for pattern in patterns
            for match in re.finditer(pattern, value)
        )
    )


def _location_event_anchors(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            _normalized_anchor(match.group(0))
            for match in re.finditer(
                r"[\u3400-\u9fff]{1,5}(?:州|郡|縣|县|城|宮|宫|關|关|道|河|江|山|谷|原|陂|門|门|府|鎮|镇)",
                value,
            )
            if 2 <= len(_normalized_anchor(match.group(0))) <= 6
        )
    )


def build_backbone_event_signatures(
    *,
    backbone_plan: Mapping[str, Any],
    backbone_materials: Mapping[str, Any],
    identity_resolver: HistoricalEntityResolver,
) -> list[dict[str, Any]]:
    """Aggregate extracted backbone facts into stable, neutral source events."""

    segment_catalog = {
        str(segment["segment_ref"]): (batch, segment)
        for batch in backbone_plan.get("page_batches") or ()
        for segment in batch.get("segments") or ()
    }
    facts_by_segment: dict[str, list[Mapping[str, Any]]] = {}
    for fact in (backbone_materials.get("fanout") or {}).get("facts") or ():
        segment_ref = str(fact.get("segment_ref") or "")
        if segment_ref in segment_catalog:
            facts_by_segment.setdefault(segment_ref, []).append(fact)

    signatures = []
    for segment_ref, facts in sorted(facts_by_segment.items()):
        batch, segment = segment_catalog[segment_ref]
        subject_rows: dict[str, dict[str, Any]] = {}
        for fact in facts:
            for actor in fact.get("actors") or ():
                subject_ref = actor.get("subject_ref")
                canonical_name = str(actor.get("canonical_name") or "")
                if subject_ref is None or not canonical_name:
                    continue
                subject_rows[str(subject_ref)] = {
                    "subject_ref": str(subject_ref),
                    "canonical_name": canonical_name,
                    "recall_terms": list(
                        _safe_recall_terms(identity_resolver, canonical_name)
                    ),
                }
        quote_lineage = [
            {
                "fact_ref": str(fact["fact_ref"]),
                "exact_quote": str(fact["exact_quote"]),
                "page_title": str(fact["page_title"]),
                "revision_ref": str(fact["revision_ref"]),
                "segment_ref": segment_ref,
                "segment_text_sha256": str(fact["segment_text_sha256"]),
            }
            for fact in sorted(facts, key=lambda row: str(row["fact_ref"]))
        ]
        source_text = str(segment["text"])
        subject_terms = {
            _normalized_anchor(term)
            for row in subject_rows.values()
            for term in row["recall_terms"]
        }

        def content_anchors(values: Sequence[str]) -> list[str]:
            return [
                anchor
                for anchor in _semantic_event_anchors(values)
                if not any(
                    anchor in subject_term or subject_term in anchor
                    for subject_term in subject_terms
                )
            ]

        event_identity = {
            "page_title": batch["page_title"],
            "revision_ref": batch["revision_ref"],
            "segment_ref": segment_ref,
            "quotes": [row["exact_quote"] for row in quote_lineage],
            "subject_refs": sorted(subject_rows),
        }
        signatures.append(
            {
                "event_ref": "EVENT-AUTO-" + _digest(event_identity)[:20].upper(),
                "subject_bindings": [subject_rows[key] for key in sorted(subject_rows)],
                "chronology_anchors": _chronology_event_anchors(source_text),
                "location_anchors": _location_event_anchors(source_text),
                "action_anchors": content_anchors(
                    [str(fact.get("action_summary") or "") for fact in facts]
                ),
                "result_anchors": content_anchors(
                    [str(fact.get("result") or "") for fact in facts]
                ),
                "quote_anchors": content_anchors(
                    [str(fact.get("exact_quote") or "") for fact in facts]
                ),
                "backbone_quotes": quote_lineage,
            }
        )
    return signatures


def build_deterministic_backbone_event_signatures(
    *,
    backbone_plan: Mapping[str, Any],
    identity_resolver: HistoricalEntityResolver,
) -> list[dict[str, Any]]:
    """Create neutral recall signatures before any model extraction.

    These signatures establish source-unit identity and recall anchors only.
    They do not decide whether the unit contains a scoreable fact, merge it
    into an outcome, or assign direction.  That keeps directed backsource
    planning deterministic and removes the old model-stage dependency.
    """

    signatures: list[dict[str, Any]] = []
    for batch in backbone_plan.get("page_batches") or ():
        for segment in batch.get("segments") or ():
            bindings = []
            allowed_refs = {
                str(value) for value in segment.get("subject_refs") or ()
            }
            for name in segment.get("subject_names") or ():
                try:
                    subject_ref = identity_resolver.entity_for_name(str(name)).person_ref
                except ValueError:
                    subject_ref = next(
                        (
                            str(value)
                            for value in segment.get("subject_refs") or ()
                            if str(value).startswith("PER-ACTOR-")
                            and any(
                                str(binding.get("canonical_name") or "") == str(name)
                                and str(binding.get("subject_ref") or "") == str(value)
                                for binding in backbone_plan.get(
                                    "provisional_subject_bindings"
                                )
                                or ()
                            )
                        ),
                        "",
                    )
                if subject_ref not in allowed_refs:
                    raise ValueError(f"{segment['segment_ref']}: 人物名称与 subject_ref 不一致")
                bindings.append(
                    {
                        "subject_ref": str(subject_ref),
                        "canonical_name": str(name),
                        "recall_terms": list(
                            _safe_recall_terms(identity_resolver, str(name))
                        ),
                    }
                )
            source_text = str(segment["text"])
            subject_terms = {
                _normalized_anchor(term)
                for row in bindings
                for term in row["recall_terms"]
            }
            quote_anchors = [
                anchor
                for anchor in _semantic_event_anchors([source_text])
                if not any(
                    anchor in subject_term or subject_term in anchor
                    for subject_term in subject_terms
                )
            ]
            event_identity = {
                "policy": _EVENT_TARGET_POLICY_VERSION,
                "page_title": batch["page_title"],
                "revision_ref": batch["revision_ref"],
                "segment_ref": segment["segment_ref"],
                "subject_refs": sorted(str(row["subject_ref"]) for row in bindings),
            }
            signatures.append(
                {
                    "event_ref": "EVENT-AUTO-" + _digest(event_identity)[:20].upper(),
                    "subject_bindings": sorted(
                        bindings, key=lambda row: str(row["subject_ref"])
                    ),
                    "chronology_anchors": _chronology_event_anchors(source_text),
                    "location_anchors": _location_event_anchors(source_text),
                    "action_anchors": [],
                    "result_anchors": [],
                    "quote_anchors": quote_anchors,
                    "backbone_quotes": [
                        {
                            "exact_quote": source_text,
                            "page_title": str(batch["page_title"]),
                            "revision_ref": str(batch["revision_ref"]),
                            "segment_ref": str(segment["segment_ref"]),
                            "segment_text_sha256": str(segment["text_sha256"]),
                        }
                    ],
                    "resolution_status": "needs_fact_resolution",
                }
            )
    return signatures


_FACT_RESOLUTION_TRIGGER = re.compile(
    r"(?:詔|诏|敕|制曰|令|命|遣|置|立|改|定|行|禁|罷|罢|免|減|减|省|增|"
    r"修|築|筑|開|开|賑|赈|恤|給|给|賜|赐|收|戶籍|户籍|籍民|稅|税|租|役|徵|征|發|发|"
    r"赦|拜|除|擢|任|黜|貶|贬|誅|诛|殺|杀|刑|法|獄|狱|"
    r"官制|官員|官员|百官|官吏|吏治|百姓|民戶|民户|民田|"
    r"軍|军|兵|攻|討(?!論)|讨(?!论)|擊|击|伐|圍|围|戰|战|守|救|降|破|克|敗|败|"
    r"奏|諫|谏|拒|從之|从之|不從|不从)"
)


def build_deterministic_fact_resolution_plan(
    plan: Mapping[str, Any],
    *,
    dense_segment_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Route only possible factual-action units to the extraction model.

    Every source unit is still scanned locally. Units without any action,
    command, implementation, institutional, personnel, military, or observable
    result trigger are deterministically empty under the neutral contract.
    """

    page_batches = []
    dense_refs = {str(value) for value in dense_segment_refs}
    rejected_segment_refs = []
    unbound_segment_refs = []
    scanned_segment_count = 0
    for batch in plan.get("page_batches") or ():
        retained = []
        for segment in batch.get("segments") or ():
            scanned_segment_count += 1
            if not segment.get("subject_refs"):
                rejected_segment_refs.append(str(segment["segment_ref"]))
                unbound_segment_refs.append(str(segment["segment_ref"]))
            elif _FACT_RESOLUTION_TRIGGER.search(str(segment["text"])):
                segment_ref = str(segment["segment_ref"])
                retained.append(
                    {
                        **dict(segment),
                        "model_weight": int(
                            segment.get("model_weight")
                            or (
                                2
                                if segment_ref in dense_refs
                                or segment.get("source_role")
                                in {"backsource", "supplement"}
                                else 1
                            )
                        ),
                    }
                )
            else:
                rejected_segment_refs.append(str(segment["segment_ref"]))
        if retained:
            page_batches.append({**dict(batch), "segments": retained})
    return {
        **dict(plan),
        "mention_index_fingerprint": _digest(
            {
                "policy": "deterministic-fact-resolution-routing-v2",
                "input": plan.get("mention_index_fingerprint"),
                "retained": [
                    str(segment["segment_ref"])
                    for batch in page_batches
                    for segment in batch["segments"]
                ],
            }
        ),
        "page_batches": page_batches,
        "deterministic_routing": {
            "policy_version": "deterministic-fact-resolution-routing-v2",
            "scanned_segment_count": scanned_segment_count,
            "model_segment_count": sum(
                len(batch["segments"]) for batch in page_batches
            ),
            "deterministic_empty_count": len(rejected_segment_refs),
            "deterministic_empty_segment_refs": sorted(rejected_segment_refs),
            "unbound_segment_count": len(unbound_segment_refs),
            "model_call_count": 0,
        },
    }


def seed_deterministic_campaign_facts(
    *,
    plan: Mapping[str, Any],
    current: Mapping[str, Any] | None,
    discovery: Mapping[str, Any],
) -> dict[str, Any]:
    """Seed only completely covered clear campaign units into current results.

    A whole event unit may skip generic model extraction only when every span
    that could contain a neutral fact is contained in a deterministic campaign
    quote. Outcome ambiguity remains explicit for the later projection layer;
    it does not invalidate the neutral action fact.
    Existing current segment results always take precedence.
    """

    existing = json.loads(json.dumps(current or {}, ensure_ascii=False))
    existing_segment_refs = {
        str(review.get("segment_ref") or "")
        for result in existing.get("batch_results") or ()
        for review in result.get("segment_reviews") or ()
        if review.get("segment_ref")
    }
    events_by_segment: dict[str, list[Mapping[str, Any]]] = {}
    for event in discovery.get("events") or ():
        events_by_segment.setdefault(str(event["segment_ref"]), []).append(event)

    seeded_by_batch: dict[str, dict[str, Any]] = {}
    outcome_judgment_pending_segment_refs: set[str] = set()
    uncovered_segment_refs: set[str] = set()
    seeded_fact_count = 0
    for batch in plan.get("page_batches") or ():
        for segment in batch.get("segments") or ():
            segment_ref = str(segment["segment_ref"])
            if segment_ref in existing_segment_refs:
                continue
            events = events_by_segment.get(segment_ref, [])
            if not events:
                continue
            clear_ranges = [
                (int(event["start_offset"]), int(event["end_offset"]))
                for event in events
            ]
            action_spans = [
                span
                for span in segment.get("spans") or ()
                if _FACT_RESOLUTION_TRIGGER.search(str(span.get("text") or ""))
            ]
            if not action_spans or any(
                not any(
                    int(span["start_offset"]) >= start
                    and int(span["end_offset"]) <= end
                    for start, end in clear_ranges
                )
                for span in action_spans
            ):
                uncovered_segment_refs.add(segment_ref)
                continue
            facts = [dict(event["neutral_fact"]) for event in events]
            row = seeded_by_batch.setdefault(
                str(batch["batch_ref"]),
                {
                    "schema_version": OUTPUT_SCHEMA_VERSION,
                    "batch_ref": str(batch["batch_ref"]),
                    "page_title": str(batch["page_title"]),
                    "revision_ref": str(batch["revision_ref"]),
                    "segment_count": 0,
                    "segment_reviews": [],
                    "limitations": [],
                },
            )
            row["segment_reviews"].append(
                {
                    "segment_ref": segment_ref,
                    "decision": "accept",
                    "context_status": "sufficient",
                    "facts": facts,
                    "reason": "事件单元内全部事实触发句均由确定性清晰战役引文覆盖。",
                }
            )
            row["segment_count"] += 1
            seeded_fact_count += len(facts)
            if any(event.get("resolution_status") == "needs_judgment" for event in events):
                outcome_judgment_pending_segment_refs.add(segment_ref)

    seeded_rows = [seeded_by_batch[key] for key in sorted(seeded_by_batch)]
    existing["batch_results"] = [
        *(existing.get("batch_results") or ()),
        *seeded_rows,
    ]
    return {
        "current": existing,
        "seeded_segment_refs": sorted(
            str(review["segment_ref"])
            for row in seeded_rows
            for review in row["segment_reviews"]
        ),
        "seeded_segment_count": sum(row["segment_count"] for row in seeded_rows),
        "seeded_fact_count": seeded_fact_count,
        "outcome_judgment_pending_segment_count": len(
            outcome_judgment_pending_segment_refs
        ),
        "uncovered_segment_count": len(uncovered_segment_refs),
    }


def build_chronicle_role_projections(
    *,
    plan: Mapping[str, Any],
    neutral_materials: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Project reusable ruler-to-person profile inputs without changing facts."""

    ruler_ref_by_segment = {
        str(segment["segment_ref"]): str(segment["chronicle_ruler_ref"])
        for batch in plan.get("page_batches") or ()
        for segment in batch.get("segments") or ()
        if segment.get("chronicle_ruler_ref")
    }
    fact_refs_by_pair: dict[tuple[str, str], set[str]] = {}
    for fact in (neutral_materials.get("fanout") or {}).get("facts") or ():
        ruler_ref = ruler_ref_by_segment.get(str(fact.get("segment_ref") or ""))
        if not ruler_ref:
            continue
        for actor in fact.get("actors") or ():
            person_ref = str(actor.get("subject_ref") or "")
            if (
                not person_ref
                or person_ref == ruler_ref
                or actor.get("role") in _NON_PROFILE_ROLES
            ):
                continue
            fact_refs_by_pair.setdefault((ruler_ref, person_ref), set()).add(
                str(fact["fact_ref"])
            )
    return [
        {
            "chronicle_ruler_ref": ruler_ref,
            "profile_subject_ref": person_ref,
            "fact_refs": sorted(fact_refs),
        }
        for (ruler_ref, person_ref), fact_refs in sorted(fact_refs_by_pair.items())
    ]


def _event_target_batches(
    *,
    source_index: LocalSourceTextIndex,
    event_signatures: Sequence[Mapping[str, Any]],
    identity_resolver: HistoricalEntityResolver,
    works_by_role: Mapping[str, Sequence[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    signature_subject_bindings: dict[str, dict[str, Any]] = {}
    for signature in event_signatures:
        for raw_binding in signature.get("subject_bindings") or ():
            name = str(raw_binding.get("canonical_name") or "").strip()
            subject_ref = str(raw_binding.get("subject_ref") or "").strip()
            if not name or not subject_ref:
                raise ValueError("事件回源 subject binding 缺少人物名称或稳定身份")
            binding = {
                "canonical_name": name,
                "subject_ref": subject_ref,
                "recall_terms": [
                    str(value)
                    for value in raw_binding.get("recall_terms") or ()
                    if str(value)
                ],
            }
            existing = signature_subject_bindings.get(name)
            if existing is not None and existing["subject_ref"] != subject_ref:
                raise ValueError(f"事件回源人物身份冲突: {name}")
            if existing is None:
                signature_subject_bindings[name] = binding
            else:
                existing["recall_terms"] = list(
                    dict.fromkeys(
                        [
                            *existing["recall_terms"],
                            *binding["recall_terms"],
                        ]
                    )
                )
    signature_subjects = set(signature_subject_bindings)
    if not signature_subjects:
        raise ValueError("事件回源缺少人物绑定")
    recall_terms_by_subject = {
        name: tuple(
            signature_subject_bindings[name]["recall_terms"]
            or _safe_recall_terms(identity_resolver, name)
        )
        for name in signature_subjects
    }
    normalized_recall_terms_by_subject = {
        name: tuple(
            dict.fromkeys(_normalized_anchor(term) for term in terms if term)
        )
        for name, terms in recall_terms_by_subject.items()
    }
    all_recall_terms = tuple(
        dict.fromkeys(
            term
            for name in sorted(recall_terms_by_subject)
            for term in recall_terms_by_subject[name]
        )
    )
    pages = [
        (role, page)
        for role, works in works_by_role.items()
        for page in source_index.iter_pages_matching_terms(
            works=works,
            terms=all_recall_terms,
        )
    ]
    units: list[dict[str, Any]] = []
    subject_units: dict[str, set[int]] = {name: set() for name in signature_subjects}
    for role, page in pages:
        for unit in _source_event_units(page.raw_text, max_chars=420):
            text = page.raw_text[int(unit["start"]): int(unit["end"])]
            normalized_text = _normalized_anchor(text)
            unit_id = len(units)
            units.append(
                {
                    "role": role,
                    "page": page,
                    "unit": unit,
                    "text": text,
                    "normalized_text": normalized_text,
                }
            )
            for name in signature_subjects:
                if any(
                    term in normalized_text
                    for term in normalized_recall_terms_by_subject[name]
                ):
                    subject_units[name].add(unit_id)

    planned_by_source: dict[tuple[str, str, str, int, int], dict[str, Any]] = {}
    bindings: list[dict[str, Any]] = []
    for signature in event_signatures:
        subject_names = [
            str(row["canonical_name"])
            for row in signature.get("subject_bindings") or ()
        ]
        candidate_ids: set[int] = set()
        for name in subject_names:
            candidate_ids.update(subject_units.get(name, set()))
        contextual_terms = list(
            dict.fromkeys(
                [
                    *(str(value) for value in signature.get("chronology_anchors") or ()),
                    *(str(value) for value in signature.get("location_anchors") or ()),
                ]
            )
        )
        semantic_terms = list(
            dict.fromkeys(
                [
                    *(
                        str(value)
                        for value in (signature.get("action_anchors") or ())[:12]
                    ),
                    *(
                        str(value)
                        for value in (signature.get("result_anchors") or ())[:12]
                    ),
                    *(
                        str(value)
                        for value in (signature.get("quote_anchors") or ())[:24]
                    ),
                ]
            )
        )
        ranked = []
        for unit_id in candidate_ids:
            row = units[unit_id]
            normalized_text = str(row["normalized_text"])
            matched_names = [
                name
                for name in subject_names
                if any(
                    term in normalized_text
                    for term in normalized_recall_terms_by_subject[name]
                )
            ]
            matched_terms = [term for term in semantic_terms if term in normalized_text]
            matched_context = [
                term for term in contextual_terms if term in normalized_text
            ]
            if not matched_names or not matched_terms:
                continue
            long_semantic_terms = {
                term for term in matched_terms if len(term) >= 4
            }
            # A lone four-character overlap is common in long biographies and
            # produced near-full-book recall. Keep it only when an independent
            # chronology/location anchor agrees; otherwise require two long
            # semantic anchors from the same backbone event.
            if not matched_context and len(long_semantic_terms) < 2:
                continue
            semantic_score = sum(len(term) ** 2 for term in matched_terms)
            if not long_semantic_terms:
                continue
            score = (
                20 * len(matched_names)
                + semantic_score
                + sum(len(term) ** 2 for term in matched_context)
            )
            ranked.append(
                (score, unit_id, matched_names, [*matched_context, *matched_terms])
            )

        retained_by_work: dict[str, int] = {}
        for _, unit_id, matched_names, matched_terms in sorted(
            ranked, key=lambda value: (-value[0], value[1])
        ):
            row = units[unit_id]
            page = row["page"]
            role = str(row["role"])
            per_work_limit = 1
            if retained_by_work.get(page.work_title, 0) >= per_work_limit:
                continue
            unit = row["unit"]
            matched_entity_names = set(matched_names)
            for name in signature_subjects:
                if any(
                    term in str(row["normalized_text"])
                    for term in normalized_recall_terms_by_subject[name]
                ):
                    matched_entity_names.add(name)
            subject_refs = sorted(
                {
                    str(signature_subject_bindings[name]["subject_ref"])
                    for name in matched_entity_names
                }
            )
            normalized_offsets = row.get("normalized_offsets")
            if normalized_offsets is None:
                normalized_with_offsets, normalized_offsets = (
                    _whole_normalized_text_offsets(str(row["text"]))
                )
                if normalized_with_offsets != str(row["normalized_text"]):
                    raise ValueError("事件回源归一化坐标与匹配文本不一致")
                row["normalized_offsets"] = normalized_offsets
            anchor_positions = [
                int(unit["start"]) + position
                for term in [*matched_terms, *matched_names]
                for position in _positions_from_normalized(
                    str(row["normalized_text"]),
                    normalized_offsets,
                    term,
                )
            ]
            initial_start, initial_end = _initial_span_range(unit, anchor_positions)
            source_key = (
                role,
                page.page_title,
                page.revision_ref,
                int(unit["start"]),
                int(unit["end"]),
            )
            segment_identity = {
                "source_role": role,
                "page_title": page.page_title,
                "revision_ref": page.revision_ref,
                "start": unit["start"],
                "end": unit["end"],
            }
            segment_ref = "SEG-AUTO-" + _digest(segment_identity)[:20].upper()
            if source_key in planned_by_source:
                planned = planned_by_source[source_key]
                planned["initial_start_offset"] = min(
                    int(planned["initial_start_offset"]), initial_start
                )
                planned["initial_end_offset"] = max(
                    int(planned["initial_end_offset"]), initial_end
                )
                planned["initial_text"] = page.raw_text[
                    int(planned["initial_start_offset"]): int(planned["initial_end_offset"])
                ]
                planned["subject_refs"] = sorted(
                    {*planned["subject_refs"], *subject_refs}
                )
                planned["subject_names"] = sorted(
                    {*planned["subject_names"], *matched_entity_names}
                )
            else:
                planned_by_source[source_key] = {
                    "segment_ref": segment_ref,
                    "source_role": role,
                    "page_title": page.page_title,
                    "work_title": page.work_title,
                    "source_url": page.source_url,
                    "revision_ref": page.revision_ref,
                    "start_offset": unit["start"],
                    "end_offset": unit["end"],
                    "text": row["text"],
                    "initial_start_offset": initial_start,
                    "initial_end_offset": initial_end,
                    "initial_text": page.raw_text[initial_start:initial_end],
                    "spans": unit["spans"],
                    "text_sha256": sha256(str(row["text"]).encode("utf-8")).hexdigest(),
                    "subject_refs": subject_refs,
                    "subject_names": sorted(matched_entity_names),
                }
            bindings.append(
                {"segment_ref": segment_ref, "event_ref": signature["event_ref"]}
            )
            retained_by_work[page.work_title] = retained_by_work.get(page.work_title, 0) + 1

    batches = []
    by_page: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for segment in planned_by_source.values():
        key = (
            str(segment.pop("page_title")),
            str(segment.pop("work_title")),
            str(segment.pop("source_url")),
            str(segment.pop("revision_ref")),
        )
        by_page.setdefault(key, []).append(segment)
    for (page_title, work_title, source_url, revision_ref), segments in sorted(by_page.items()):
        shards: list[list[dict[str, Any]]] = []
        shard: list[dict[str, Any]] = []
        shard_chars = 0
        for segment in sorted(segments, key=lambda row: str(row["segment_ref"])):
            segment_chars = len(str(segment["text"]))
            if shard and (
                shard_chars + segment_chars > 4800
                or len(shard) >= MODEL_GROUP_SEGMENT_LIMIT
            ):
                shards.append(shard)
                shard = []
                shard_chars = 0
            shard.append(segment)
            shard_chars += segment_chars
        if shard:
            shards.append(shard)
        for shard_segments in shards:
            batch_ref = "BATCH-AUTO-" + _digest(
                {
                    "page_title": page_title,
                    "revision_ref": revision_ref,
                    "segments": [row["segment_ref"] for row in shard_segments],
                }
            )[:20].upper()
            batches.append(
                {
                    "batch_ref": batch_ref,
                    "page_title": page_title,
                    "work_title": work_title,
                    "source_url": source_url,
                    "revision_ref": revision_ref,
                    "segments": shard_segments,
                }
            )
    return batches, bindings


def build_event_directed_neutral_plan(
    *,
    backbone_plan: Mapping[str, Any],
    backbone_materials: Mapping[str, Any] | None = None,
    event_signatures: Sequence[Mapping[str, Any]] | None = None,
    source_index: LocalSourceTextIndex,
    identity_resolver: HistoricalEntityResolver,
    backsource_works: Sequence[str],
    supplement_works: Sequence[str],
) -> dict[str, Any]:
    if event_signatures is None:
        if backbone_materials is None:
            raise ValueError("事件回源需要确定性事件签名或已抽取主干材料")
        event_signatures = build_backbone_event_signatures(
            backbone_plan=backbone_plan,
            backbone_materials=backbone_materials,
            identity_resolver=identity_resolver,
        )
    event_signatures = [dict(row) for row in event_signatures]
    target_batches, target_bindings = _event_target_batches(
        source_index=source_index,
        event_signatures=event_signatures,
        identity_resolver=identity_resolver,
        works_by_role={
            "backsource": tuple(backsource_works),
            "supplement": tuple(supplement_works),
        },
    )
    fact_bindings = [
        {"fact_ref": quote["fact_ref"], "event_ref": signature["event_ref"]}
        for signature in event_signatures
        for quote in signature["backbone_quotes"]
        if quote.get("fact_ref")
    ]
    backbone_segment_bindings = [
        {
            "segment_ref": str(quote["segment_ref"]),
            "event_ref": str(signature["event_ref"]),
        }
        for signature in event_signatures
        for quote in signature["backbone_quotes"]
        if quote.get("segment_ref")
    ]
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "ruler": backbone_plan["ruler"],
        "source_index_identity": backbone_plan["source_index_identity"],
        "mention_index_fingerprint": _digest(
            {
                "policy": _EVENT_TARGET_POLICY_VERSION,
                "backbone": backbone_plan["mention_index_fingerprint"],
                "event_signatures": event_signatures,
                "backsource_works": sorted(str(value) for value in backsource_works),
                "supplement_works": sorted(str(value) for value in supplement_works),
            }
        ),
        "event_target_policy": _EVENT_TARGET_POLICY_VERSION,
        "event_signatures": event_signatures,
        "event_fact_bindings": fact_bindings,
        "target_segment_event_bindings": [
            *backbone_segment_bindings,
            *target_bindings,
        ],
        "page_batches": [*(backbone_plan.get("page_batches") or ()), *target_batches],
    }


def merge_dynasty_governance_current(
    *,
    neutral_materials: Mapping[str, Any],
    current: Mapping[str, Any],
    expected_dynasty_token: str,
    expected_source_index_identity: str,
    period_terms: Sequence[str],
    identity_resolver: HistoricalEntityResolver,
    subject_ref_by_name: Mapping[str, str],
    ruler_ref: str,
    event_signatures: Sequence[Mapping[str, Any]] = (),
    include_all_dynasty_chains: bool = False,
) -> dict[str, Any]:
    """Project accepted dynasty material into the ruler fanout without a model."""

    if current.get("schema_version") != "dynasty-governance-current-v2":
        raise ValueError("朝代政书 current schema 不支持")
    if current.get("status") != "quality_accepted_shadow":
        raise ValueError("朝代政书 current 尚未通过质量门")
    if str(current.get("dynasty_token") or "") != expected_dynasty_token:
        raise ValueError("朝代政书 current token 与皇帝配置不匹配")
    if str(current.get("source_index_identity") or "") != expected_source_index_identity:
        raise ValueError("朝代政书 current 与其固定政书索引版本不一致")
    if not period_terms and not include_all_dynasty_chains:
        raise ValueError("皇帝配置缺少朝代政书纪年筛选词")

    normalized_period_terms = tuple(
        dict.fromkeys(_normalized_anchor(value) for value in period_terms if value)
    )
    allowed_subject_refs = tuple(sorted(set(subject_ref_by_name.values())))
    dynasty = str(current.get("dynasty") or "")
    normalized_identity_terms = {
        _normalized_anchor(term)
        for name in subject_ref_by_name
        for term in identity_resolver.recall_terms(name)
    }
    signature_match_catalog = []
    for signature in event_signatures:
        quote_anchors = []
        for quote in signature.get("backbone_quotes") or ():
            for raw_run in re.findall(
                r"[\u3400-\u9fff]+", str(quote.get("exact_quote") or "")
            ):
                run = _normalized_anchor(raw_run)
                for offset in range(0, max(0, len(run) - 8 + 1)):
                    anchor = run[offset : offset + 8]
                    if any(
                        identity in anchor or anchor in identity
                        for identity in normalized_identity_terms
                    ):
                        continue
                    quote_anchors.append(anchor)
        signature_match_catalog.append(
            {
                "event_ref": str(signature["event_ref"]),
                "subject_refs": {
                    str(row.get("subject_ref") or "")
                    for row in signature.get("subject_bindings") or ()
                },
                "quote_anchors": tuple(dict.fromkeys(quote_anchors)),
            }
        )
    implementation_by_status = {
        "proposed": "proposed",
        "ordered": "adopted",
        "enacted": "adopted",
        "implemented": "implemented",
        "operated": "implemented",
        "modified": "implemented",
        "repealed": "repealed",
        "completed": "completed_work",
        "observed_outcome": "implemented",
        "mixed_chain": "implemented",
        "unclear": "not_shown",
    }
    role_by_phase = {
        "initiated": "initiator",
        "designed": "designer",
        "authorized": "authorizer",
        "implemented": "executor",
        "operated": "executor",
        "corrected": "supervisor",
        "repealed": "authorizer",
        "reported_or_evaluated": "advisor",
    }
    strength_by_responsibility = {
        "exclusive": "primary",
        "lead": "primary",
        "participant": "important_support",
    }
    projected_facts: list[dict[str, Any]] = []
    selected_chain_refs: set[str] = set()
    selected_chain_keys: set[str] = set()
    aligned_chain_keys: set[str] = set()
    four_axis_candidate_chain_keys: set[str] = set()
    context_only_chain_keys: set[str] = set()
    event_fact_refs: dict[str, list[str]] = {}
    for chain in current.get("chains") or ():
        period = str(chain.get("period") or "")
        normalized_period = _normalized_anchor(period)
        in_ruler_window = any(
            term in normalized_period for term in normalized_period_terms
        )
        resolved_actors = []
        for actor in chain.get("actors") or ():
            resolution = identity_resolver.resolve(
                str(actor.get("name") or ""),
                allowed_subject_refs=allowed_subject_refs,
                dynasty=dynasty or None,
            )
            if resolution.status != "resolved":
                continue
            phases = [str(value) for value in actor.get("contribution_phases") or ()]
            role = next(
                (role_by_phase[phase] for phase in phases if phase in role_by_phase),
                "executor",
            )
            resolved_actors.append(
                {
                    "source": actor,
                    "source_name": str(actor.get("name") or ""),
                    "canonical_name": str(resolution.canonical_name),
                    "subject_ref": str(resolution.person_ref),
                    "role": role,
                    "responsibility_strength": strength_by_responsibility.get(
                        str(actor.get("responsibility_role") or ""), "limited"
                    ),
                    "attribution_basis": str(actor.get("role_basis") or "政书原文归责"),
                }
            )
        has_lifetime_person_actor = any(
            str(actor["subject_ref"]) != ruler_ref for actor in resolved_actors
        )
        if (
            not include_all_dynasty_chains
            and not in_ruler_window
            and not has_lifetime_person_actor
        ):
            continue
        chain_identity = {
            "dynasty_token": expected_dynasty_token,
            "input_fingerprint": current.get("input_fingerprint"),
            "chain_key": chain.get("chain_key"),
        }
        result = str(chain.get("observable_result") or "")
        meaningful_result = bool(result.strip()) and not any(
            marker in result
            for marker in (
                "原文未载",
                "原文未載",
                "未载进一步",
                "未載進一步",
            )
        )
        explicit_chain_evidence_roles = {
            str(role)
            for evidence in chain.get("evidence") or ()
            for role in evidence.get("evidence_roles") or ()
        }
        # V2 evidence roles are the source-of-truth for whether a chain can
        # support a four-axis outcome review.  Legacy fixtures without roles
        # retain their previous result-based behavior, but a V2 summary may not
        # turn design-only or court-procedure quotes into public-result facts.
        chain_has_public_effect_evidence = bool(
            explicit_chain_evidence_roles
            & {"public_result", "cost_or_burden"}
        ) or (not explicit_chain_evidence_roles and meaningful_result)
        if chain_has_public_effect_evidence:
            four_axis_candidate_chain_keys.add(str(chain.get("chain_key") or ""))
        else:
            context_only_chain_keys.add(str(chain.get("chain_key") or ""))
        chain_text = _normalized_anchor(
            " ".join(
                str(chain.get(key) or "")
                for key in (
                    "title",
                    "period",
                    "action",
                    "implementation",
                    "observable_result",
                    "cost_or_burden",
                )
            )
            + " "
            + " ".join(
                str(evidence.get("exact_quote") or "")
                for evidence in chain.get("evidence") or ()
            )
        )
        chain_subject_refs = {str(actor["subject_ref"]) for actor in resolved_actors}
        signature_matches = []
        for signature in signature_match_catalog:
            if not chain_subject_refs & signature["subject_refs"]:
                continue
            matched_quote_anchors = [
                anchor
                for anchor in signature["quote_anchors"]
                if anchor in chain_text
            ]
            if not matched_quote_anchors:
                continue
            signature_matches.append(
                (
                    len(matched_quote_anchors),
                    str(signature["event_ref"]),
                )
            )
        signature_matches.sort(key=lambda row: (-row[0], row[1]))
        if signature_matches and (
            len(signature_matches) == 1
            or signature_matches[0][0] > signature_matches[1][0]
        ):
            event_ref = signature_matches[0][1]
            aligned_chain_keys.add(str(chain.get("chain_key") or ""))
        else:
            event_ref = "DYNGOV-EVENT-" + _digest(chain_identity)[:20].upper()
        event_fact_refs.setdefault(event_ref, [])
        implementation_status = implementation_by_status.get(
            str(chain.get("operation_status") or ""), "not_shown"
        )
        for evidence in chain.get("evidence") or ():
            quote_ref = str(evidence.get("quote_ref") or "")
            evidence_actors = [
                actor
                for actor in resolved_actors
                if quote_ref in set(str(value) for value in actor["source"].get("quote_refs") or ())
            ]
            evidence_identity = {
                **chain_identity,
                "quote_ref": quote_ref,
                "page_title": evidence.get("page_title"),
                "revision_ref": evidence.get("revision_ref"),
                "exact_quote": evidence.get("exact_quote"),
            }
            suffix = _digest(evidence_identity)[:20].upper()
            fact_ref = "DYNGOV-FACT-" + suffix
            segment_ref = "DYNGOV-SEG-" + suffix
            exact_quote = str(evidence.get("exact_quote") or "")
            source_evidence_roles = list(
                dict.fromkeys(
                    str(value)
                    for value in (
                        evidence.get("evidence_roles")
                        or (
                            [
                                "implementation_or_operation"
                                if implementation_status
                                in {
                                    "adopted",
                                    "implemented",
                                    "nationally_promulgated",
                                    "completed_work",
                                }
                                else "measure_or_design"
                            ]
                            + (["public_result"] if meaningful_result else [])
                            + (
                                ["responsibility_or_attribution"]
                                if evidence_actors
                                else []
                            )
                        )
                    )
                )
            )
            evidence_roles = [
                (
                    "public_cost_or_harm"
                    if value == "cost_or_burden"
                    else value
                )
                for value in source_evidence_roles
            ]
            evidence_result = (
                result if "public_result" in set(evidence_roles) else ""
            )
            projected_facts.append(
                {
                    "fact_id": fact_ref,
                    "fact_ref": fact_ref,
                    "batch_ref": "DYNGOV-BATCH-" + _digest(chain_identity)[:20].upper(),
                    "segment_ref": segment_ref,
                    "page_title": str(evidence.get("page_title") or ""),
                    "work_title": str(evidence.get("page_title") or "").split("/", 1)[0],
                    "source_url": "",
                    "revision_ref": str(evidence.get("revision_ref") or ""),
                    "segment_text_sha256": sha256(exact_quote.encode("utf-8")).hexdigest(),
                    "exact_quote": exact_quote,
                    "evidence_span_refs": [quote_ref],
                    "fact_kind": "institutional_action",
                    "evidence_roles": evidence_roles,
                    "effect_domains": list(
                        dict.fromkeys(
                            str(value) for value in chain.get("effect_domains") or ()
                        )
                    ),
                    "governance_domain": str(chain.get("domain") or ""),
                    "governance_title": str(chain.get("title") or ""),
                    "period": period,
                    "action_summary": str(chain.get("action") or chain.get("title") or ""),
                    "actors": [
                        {key: value for key, value in actor.items() if key != "source"}
                        for actor in evidence_actors
                    ],
                    "implementation_status": implementation_status,
                    "result": evidence_result,
                    "legacy_status": (
                        "cross_reign_continuity"
                        if chain.get("temporal_scope") == "cross_reign_continuity"
                        else "within_reign_continuity"
                    ),
                    "legacy_basis": str(chain.get("temporal_scope") or "single_event"),
                    "projection_eligibility": "direct_neutral_fact",
                    "outcome_candidate_status": (
                        "linkable_chain_fact"
                        if chain_has_public_effect_evidence
                        else "context_only"
                    ),
                    "outcome_candidate_reason": (
                        "政书链含公共结果或实际代价证据，仍需与编年和正史材料归并判断。"
                        if chain_has_public_effect_evidence
                        else "政书仅载制度设计、行政运行或宫廷流程，保留为背景，不独立进入四轴成果审阅。"
                    ),
                    "uncertainty": str(chain.get("uncertainty") or ""),
                    "event_refs": [event_ref],
                    "source_role": "dynasty_governance",
                    "ruler_window_match": in_ruler_window,
                    "formal_write": False,
                }
            )
            event_fact_refs[event_ref].append(fact_ref)
            selected_chain_refs.add(event_ref)
            selected_chain_keys.add(str(chain.get("chain_key") or ""))

    output = json.loads(json.dumps(neutral_materials, ensure_ascii=False))
    fanout = output["fanout"]
    previous_governance_refs = {
        str(row["fact_ref"])
        for row in fanout.get("facts") or ()
        if row.get("source_role") == "dynasty_governance"
    }
    fanout["facts"] = [
        row
        for row in fanout.get("facts") or ()
        if str(row["fact_ref"]) not in previous_governance_refs
    ]
    for person in fanout.get("person_fanout") or ():
        person["facts"] = [
            row
            for row in person.get("facts") or ()
            if str(row["fact_ref"]) not in previous_governance_refs
        ]
    fanout["event_groups"] = [
        {
            **dict(row),
            "fact_refs": [
                ref
                for ref in row.get("fact_refs") or ()
                if str(ref) not in previous_governance_refs
            ],
        }
        for row in fanout.get("event_groups") or ()
        if not str(row.get("event_ref") or "").startswith("DYNGOV-EVENT-")
    ]
    existing_fact_refs = {str(row["fact_ref"]) for row in fanout.get("facts") or ()}
    projected_facts = [
        fact for fact in projected_facts if str(fact["fact_ref"]) not in existing_fact_refs
    ]
    fanout["facts"] = sorted(
        [*(fanout.get("facts") or ()), *projected_facts],
        key=lambda row: str(row["fact_ref"]),
    )
    person_rows = {
        str(row["subject_ref"]): dict(row)
        for row in fanout.get("person_fanout") or ()
    }
    for fact in projected_facts:
        for actor in fact["actors"]:
            subject_ref = str(actor["subject_ref"])
            person = person_rows.setdefault(
                subject_ref,
                {
                    "subject_ref": subject_ref,
                    "fact_count": 0,
                    "profile_eligible_count": 0,
                    "facts": [],
                },
            )
            person["facts"] = [
                *(person.get("facts") or ()),
                {
                    "fact_ref": fact["fact_ref"],
                    "actor": actor,
                    "profile_eligible": actor["role"] not in _NON_PROFILE_ROLES,
                    "page_title": fact["page_title"],
                    "revision_ref": fact["revision_ref"],
                    "segment_ref": fact["segment_ref"],
                },
            ]
    for person in person_rows.values():
        person["facts"] = sorted(
            person.get("facts") or (), key=lambda row: str(row["fact_ref"])
        )
        person["fact_count"] = len(person["facts"])
        person["profile_eligible_count"] = sum(
            bool(row.get("profile_eligible")) for row in person["facts"]
        )
    fanout["person_fanout"] = [person_rows[key] for key in sorted(person_rows)]
    fanout["fact_count"] = len(fanout["facts"])
    fanout["person_count"] = len(person_rows)
    fanout["dynasty_governance_fact_count"] = len(projected_facts)
    event_groups_by_ref = {
        str(row["event_ref"]): dict(row)
        for row in fanout.get("event_groups") or ()
    }
    for event_ref in sorted(selected_chain_refs):
        row = event_groups_by_ref.setdefault(
            event_ref,
            {
                "event_ref": event_ref,
                "fact_refs": [],
            },
        )
        row["fact_refs"] = sorted(
            {*[str(value) for value in row.get("fact_refs") or ()], *event_fact_refs[event_ref]}
        )
    fanout["event_groups"] = [
        event_groups_by_ref[key] for key in sorted(event_groups_by_ref)
    ]
    output["dynasty_governance_current"] = {
        "dynasty_token": expected_dynasty_token,
        "input_fingerprint": str(current.get("input_fingerprint") or ""),
        "source_index_identity": str(current.get("source_index_identity") or ""),
        "selected_chain_count": len(selected_chain_keys),
        "aligned_to_backbone_chain_count": len(aligned_chain_keys),
        "four_axis_candidate_chain_count": len(
            four_axis_candidate_chain_keys
        ),
        "context_only_chain_count": len(context_only_chain_keys),
        "fact_count": len(projected_facts),
        "model_call_count": 0,
    }
    return output


def extract_current_neutral_materials(
    *,
    plan: Mapping[str, Any],
    current: Mapping[str, Any] | None,
    runner: StructuredCodexRunner,
    max_workers: int,
    checkpoint_dir: Path,
    pages_per_call: int = 5,
    subject_ref_by_name: Mapping[str, str] | None = None,
    identity_resolver: HistoricalEntityResolver | None = None,
    supplemental_facts_by_segment: Mapping[
        str, Sequence[Mapping[str, Any]]
    ] | None = None,
) -> dict[str, Any]:
    subject_ref_by_name = dict(subject_ref_by_name or {})
    current_results = {
        str(row["batch_ref"]): row
        for row in (current or {}).get("batch_results") or ()
    }
    current_segments: dict[str, tuple[str, str, Mapping[str, Any], Sequence[str]]] = {}
    conflicting_current_segments: set[str] = set()

    def register_seed_result(current_result: Mapping[str, Any]) -> None:
        page_title = str(current_result.get("page_title") or "")
        revision_ref = str(current_result.get("revision_ref") or "")
        limitations = tuple(
            str(value) for value in current_result.get("limitations") or ()
        )
        for review in current_result.get("segment_reviews") or ():
            segment_ref = str(review.get("segment_ref") or "")
            if not segment_ref:
                continue
            candidate = (page_title, revision_ref, review, limitations)
            previous = current_segments.get(segment_ref)
            if previous is not None and _digest(previous[2]) != _digest(review):
                conflicting_current_segments.add(segment_ref)
            else:
                current_segments[segment_ref] = candidate

    for current_result in current_results.values():
        register_seed_result(current_result)
    # Contract repairs can change subject bindings and therefore batch refs
    # without changing most source segments. Recover old checkpoint reviews as
    # untrusted seeds; seed_current_segments re-canonicalizes each review
    # against the exact new segment and validates quotes/ownership before use.
    if checkpoint_dir.is_dir():
        for checkpoint_path in sorted(checkpoint_dir.glob("*.json")):
            try:
                checkpoint_payload = json.loads(
                    checkpoint_path.read_text(encoding="utf-8")
                )
                checkpoint_result = checkpoint_payload.get("result")
                if isinstance(checkpoint_result, Mapping):
                    register_seed_result(checkpoint_result)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    for segment_ref in conflicting_current_segments:
        current_segments.pop(segment_ref, None)
    current_fingerprints = dict((current or {}).get("batch_fingerprints") or {})
    batch_fingerprints = {
        str(batch["batch_ref"]): _digest(
            {
                "batch": batch,
                "extraction_policy": NEUTRAL_EXTRACTION_POLICY_VERSION,
            }
        )
        for batch in plan.get("page_batches") or ()
    }
    results: dict[str, Mapping[str, Any]] = {}
    pending = []
    retry_seeds: dict[str, Mapping[str, Any]] = {}
    seeded_reviews_by_batch: dict[str, dict[str, Mapping[str, Any]]] = {}
    seeded_limitations_by_batch: dict[str, list[str]] = {}
    segment_checkpoint_dir = checkpoint_dir / "_segments"

    def validate_one(
        batch: Mapping[str, Any], result: Mapping[str, Any]
    ) -> None:
        build_shared_neutral_fact_fanout(
            {
                "schema_version": plan["schema_version"],
                "source_index_identity": plan["source_index_identity"],
                "mention_index_fingerprint": plan["mention_index_fingerprint"],
                "page_batches": [batch],
            },
            [result],
        )

    def seed_current_segments(
        batch: Mapping[str, Any],
    ) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
        seeded: dict[str, Mapping[str, Any]] = {}
        limitations: set[str] = set()
        for segment in batch["segments"]:
            segment_ref = str(segment["segment_ref"])
            candidate = current_segments.get(segment_ref)
            if candidate is None:
                continue
            page_title, revision_ref, review, current_limitations = candidate
            if (
                page_title != str(batch["page_title"])
                or revision_ref != str(batch["revision_ref"])
            ):
                continue
            mini_batch = {**dict(batch), "segments": [segment]}
            mini_result = {
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "batch_ref": batch["batch_ref"],
                "page_title": batch["page_title"],
                "revision_ref": batch["revision_ref"],
                "segment_count": 1,
                "segment_reviews": [review],
                "limitations": list(current_limitations),
            }
            repaired = _canonicalize_result(
                mini_batch,
                mini_result,
                subject_ref_by_name=subject_ref_by_name,
                identity_resolver=identity_resolver,
            )
            try:
                validate_one(mini_batch, repaired)
            except ValueError:
                continue
            seeded[segment_ref] = repaired["segment_reviews"][0]
            limitations.update(str(value) for value in repaired.get("limitations") or ())
            _atomic_json(
                segment_checkpoint_dir
                / f"{batch['batch_ref']}--{segment_ref}.json",
                {
                    "batch_fingerprint": batch_fingerprints[str(batch["batch_ref"])],
                    "review": seeded[segment_ref],
                    "limitations": sorted(limitations),
                },
            )
        return seeded, sorted(limitations)

    for batch in plan.get("page_batches") or ():
        batch_ref = str(batch["batch_ref"])
        checkpoint = checkpoint_dir / f"{batch_ref}.json"
        if (
            current_fingerprints.get(batch_ref) == batch_fingerprints[batch_ref]
            and batch_ref in current_results
        ):
            try:
                repaired = _canonicalize_result(
                    batch,
                    current_results[batch_ref],
                    subject_ref_by_name=subject_ref_by_name,
                    identity_resolver=identity_resolver,
                )
                validate_one(batch, repaired)
                results[batch_ref] = repaired
            except ValueError:
                retry_seeds[batch_ref] = repaired
                pending.append(batch)
        elif checkpoint.is_file():
            checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            if checkpoint_payload.get("batch_fingerprint") == batch_fingerprints[batch_ref]:
                try:
                    repaired = _canonicalize_result(
                        batch,
                        checkpoint_payload["result"],
                        subject_ref_by_name=subject_ref_by_name,
                        identity_resolver=identity_resolver,
                    )
                    validate_one(batch, repaired)
                    results[batch_ref] = repaired
                    if repaired != checkpoint_payload["result"]:
                        _atomic_json(
                            checkpoint,
                            {
                                "batch_fingerprint": batch_fingerprints[batch_ref],
                                "result": repaired,
                            },
                        )
                except ValueError:
                    retry_seeds[batch_ref] = repaired
                    pending.append(batch)
            else:
                seeded, seeded_limitations = seed_current_segments(batch)
                seeded_reviews_by_batch[batch_ref] = seeded
                seeded_limitations_by_batch[batch_ref] = seeded_limitations
                if len(seeded) == len(batch["segments"]):
                    reused = {
                        "schema_version": OUTPUT_SCHEMA_VERSION,
                        "batch_ref": batch_ref,
                        "page_title": batch["page_title"],
                        "revision_ref": batch["revision_ref"],
                        "segment_count": len(batch["segments"]),
                        "segment_reviews": [
                            seeded[str(segment["segment_ref"])]
                            for segment in batch["segments"]
                        ],
                        "limitations": seeded_limitations,
                    }
                    validate_one(batch, reused)
                    results[batch_ref] = reused
                else:
                    pending.append(
                        {
                            **dict(batch),
                            "segments": [
                                segment
                                for segment in batch["segments"]
                                if str(segment["segment_ref"]) not in seeded
                            ],
                        }
                    )
        else:
            seeded, seeded_limitations = seed_current_segments(batch)
            seeded_reviews_by_batch[batch_ref] = seeded
            seeded_limitations_by_batch[batch_ref] = seeded_limitations
            if len(seeded) == len(batch["segments"]):
                reused = {
                    "schema_version": OUTPUT_SCHEMA_VERSION,
                    "batch_ref": batch_ref,
                    "page_title": batch["page_title"],
                    "revision_ref": batch["revision_ref"],
                    "segment_count": len(batch["segments"]),
                    "segment_reviews": [
                        seeded[str(segment["segment_ref"])]
                        for segment in batch["segments"]
                    ],
                    "limitations": seeded_limitations,
                }
                validate_one(batch, reused)
                results[batch_ref] = reused
            else:
                pending.append(
                    {
                        **dict(batch),
                        "segments": [
                            segment
                            for segment in batch["segments"]
                            if str(segment["segment_ref"]) not in seeded
                        ],
                    }
                )

    def has_current_segment_checkpoint(batch: Mapping[str, Any]) -> bool:
        batch_ref = str(batch["batch_ref"])
        for segment in batch["segments"]:
            path = segment_checkpoint_dir / f"{batch_ref}--{segment['segment_ref']}.json"
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("batch_fingerprint") == batch_fingerprints[batch_ref]:
                return True
        return False

    direct_fallback_refs = {
        str(batch["batch_ref"])
        for batch in pending
        if has_current_segment_checkpoint(batch)
    }
    fresh_pending = [
        batch
        for batch in pending
        if str(batch["batch_ref"]) not in retry_seeds
        and str(batch["batch_ref"]) not in direct_fallback_refs
    ]

    def prepare_prompt_batch(batch: Mapping[str, Any]) -> dict[str, Any]:
        prompt_segments = []
        allowed_subject_refs: set[str] = set()
        for segment in batch["segments"]:
            visible = _prompt_segment_view(segment)
            allowed_subject_refs.update(str(value) for value in visible["subject_refs"])
            prompt_segments.append(visible)
        if identity_resolver is not None:
            subject_bindings = identity_resolver.bindings(sorted(allowed_subject_refs))
            visible_text = "\n".join(str(row["text"]) for row in prompt_segments)
            normalized_visible_text = _T2S.convert(visible_text)
            subject_bindings = [
                {
                    **dict(binding),
                    "aliases": [
                        alias
                        for alias in binding.get("aliases") or ()
                        if str(alias.get("surface") or "")
                        and (
                            str(alias.get("surface")) in visible_text
                            or _T2S.convert(str(alias.get("surface")))
                            in normalized_visible_text
                        )
                    ],
                }
                for binding in subject_bindings
            ]
            known_binding_refs = {
                str(binding["subject_ref"]) for binding in subject_bindings
            }
            subject_bindings.extend(
                {
                    "canonical_name": name,
                    "subject_ref": subject_ref_by_name[name],
                    "aliases": [],
                    "identity_status": "provisional_actor_name",
                }
                for name in sorted(subject_ref_by_name)
                if subject_ref_by_name[name] in allowed_subject_refs
                and subject_ref_by_name[name] not in known_binding_refs
            )
        else:
            subject_bindings = [
                {
                    "canonical_name": name,
                    "subject_ref": subject_ref_by_name[name],
                    "aliases": [],
                }
                for name in sorted(subject_ref_by_name)
                if subject_ref_by_name[name] in allowed_subject_refs
            ]
        return {
            **dict(batch),
            "subject_bindings": subject_bindings,
            "segments": prompt_segments,
        }

    def prepare_prompt_group(
        group: Sequence[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        """Coalesce same-page shards before transport, preserving result owners."""

        grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
        for batch in group:
            key = (
                str(batch["page_title"]),
                str(batch["revision_ref"]),
                str(batch.get("source_role") or ""),
            )
            grouped.setdefault(key, []).append(batch)
        prompt_batches = []
        owners: dict[str, list[str]] = {}
        for key in sorted(grouped):
            shards = grouped[key]
            owner_refs = [str(batch["batch_ref"]) for batch in shards]
            if len(shards) == 1:
                combined = dict(shards[0])
            else:
                combined = {
                    **dict(shards[0]),
                    "batch_ref": "PROMPT-GROUP-"
                    + _digest(
                        {
                            "page_title": key[0],
                            "revision_ref": key[1],
                            "batch_refs": owner_refs,
                        }
                    )[:20].upper(),
                    "segments": [
                        segment
                        for batch in shards
                        for segment in batch["segments"]
                    ],
                }
            prepared = prepare_prompt_batch(combined)
            prompt_ref = str(prepared["batch_ref"])
            owners[prompt_ref] = owner_refs
            prompt_batches.append(prepared)
        return prompt_batches, owners

    groups: list[list[Mapping[str, Any]]] = []
    oversized_fresh: list[Mapping[str, Any]] = []
    eligible_fresh: list[Mapping[str, Any]] = []
    prompt_chars_by_ref: dict[str, int] = {}
    for batch in fresh_pending:
        batch_chars = sum(
            len(_prompt_segment_view(segment)["text"])
            for segment in batch["segments"]
        )
        prepared_batch = prepare_prompt_batch(batch)
        single_prompt_chars = len(build_compact_multi_page_prompt([prepared_batch]))
        if (
            batch_chars > MODEL_SINGLE_BATCH_CHAR_LIMIT
            or len(batch["segments"]) > MODEL_SINGLE_BATCH_SEGMENT_LIMIT
            or single_prompt_chars > MODEL_SINGLE_PROMPT_CHAR_LIMIT
        ):
            oversized_fresh.append(batch)
            continue
        eligible_fresh.append(batch)
        prompt_chars_by_ref[str(batch["batch_ref"])] = single_prompt_chars
    if eligible_fresh:
        largest_prompt_chars = max(prompt_chars_by_ref.values())
        canary_target_chars = (largest_prompt_chars + 1) // 2
        canary_batch = min(
            eligible_fresh,
            key=lambda row: (
                prompt_chars_by_ref[str(row["batch_ref"])] < canary_target_chars,
                abs(
                    prompt_chars_by_ref[str(row["batch_ref"])]
                    - canary_target_chars
                ),
                str(row["batch_ref"]),
            ),
        )
        canary_prompt_chars = prompt_chars_by_ref[str(canary_batch["batch_ref"])]
        all_eligible_prompt_chars = len(
            build_compact_multi_page_prompt(
                prepare_prompt_group(eligible_fresh)[0]
            )
        )
        if (
            len(eligible_fresh) <= pages_per_call
            and sum(_model_group_weight(row["segments"]) for row in eligible_fresh)
            <= MODEL_GROUP_WEIGHT_LIMIT
            and len(
                {
                    subject_ref
                    for row in eligible_fresh
                    for subject_ref in _model_group_subject_refs(row["segments"])
                }
            )
            <= MODEL_GROUP_SUBJECT_LIMIT
            and all_eligible_prompt_chars
            <= min(MODEL_GROUP_PROMPT_CHAR_LIMIT, 2 * canary_prompt_chars)
        ):
            groups.append(eligible_fresh)
            eligible_fresh = []
    if eligible_fresh:
        groups.append([canary_batch])
        # Both source payload and the combined prompt remain capped at 6k.
        # Same-page coalescing removes repeated bindings before this check, so
        # the cap controls historical output density rather than JSON overhead.
        comparable_prompt_limit = MODEL_GROUP_PROMPT_CHAR_LIMIT
        group: list[Mapping[str, Any]] = []
        group_chars = 0
        group_weight = 0
        group_subject_refs: set[str] = set()
        for batch in eligible_fresh:
            if batch is canary_batch:
                continue
            batch_chars = sum(
                len(_prompt_segment_view(segment)["text"])
                for segment in batch["segments"]
            )
            candidate_prompt_chars = (
                len(
                    build_compact_multi_page_prompt(
                        prepare_prompt_group([*group, batch])[0]
                    )
                )
                if group
                else prompt_chars_by_ref[str(batch["batch_ref"])]
            )
            batch_subject_refs = _model_group_subject_refs(batch["segments"])
            if group and (
                len(group) >= pages_per_call
                or group_chars + batch_chars > MODEL_GROUP_CHAR_LIMIT
                or group_weight + _model_group_weight(batch["segments"])
                > MODEL_GROUP_WEIGHT_LIMIT
                or len(group_subject_refs | batch_subject_refs)
                > MODEL_GROUP_SUBJECT_LIMIT
                or candidate_prompt_chars > comparable_prompt_limit
            ):
                groups.append(group)
                group = []
                group_chars = 0
                group_weight = 0
                group_subject_refs = set()
            if prompt_chars_by_ref[str(batch["batch_ref"])] > comparable_prompt_limit:
                groups.append([batch])
                continue
            group.append(batch)
            group_chars += batch_chars
            group_weight += _model_group_weight(batch["segments"])
            group_subject_refs.update(batch_subject_refs)
        if group:
            groups.append(group)
    model_call_count = len(groups)

    def run_group(
        group: Sequence[Mapping[str, Any]], *, strict_quotes: bool = False
    ) -> tuple[Sequence[Mapping[str, Any]], int]:
        if len(group) == 1 and sum(
            len(_prompt_segment_view(segment)["text"])
            for segment in group[0]["segments"]
        ) > MODEL_SINGLE_BATCH_CHAR_LIMIT or (
            len(group) == 1
            and len(group[0]["segments"]) > MODEL_SINGLE_BATCH_SEGMENT_LIMIT
        ):
            raise ValueError("超长单页批次必须按 segment 拆分")
        prompt_group, prompt_owners = prepare_prompt_group(group)
        payload, _ = runner.run(
            build_compact_multi_page_prompt(prompt_group, strict_quotes=strict_quotes)
        )
        expected = [str(batch["batch_ref"]) for batch in group]
        segment_owner = {
            str(segment["segment_ref"]): str(batch["batch_ref"])
            for batch in group
            for segment in batch["segments"]
        }
        compact_by_ref = {
            batch_ref: {
                "batch_ref": batch_ref,
                "facts": [],
                "context_requests": [],
                "limitations": [],
            }
            for batch_ref in expected
        }
        seen_batch_refs: set[str] = set()
        raw_rows = list(payload.get("results") or ())
        for raw in raw_rows:
            raw_ref = str(raw.get("batch_ref") or "")
            if len(group) == 1:
                raw_ref = expected[0]
            limitation_owners = prompt_owners.get(raw_ref, [raw_ref])
            for owner in limitation_owners:
                if owner not in compact_by_ref:
                    continue
                seen_batch_refs.add(owner)
                compact_by_ref[owner]["limitations"].extend(
                    str(value) for value in raw.get("limitations") or ()
                )
            for key in ("facts", "context_requests"):
                for item in raw.get(key) or ():
                    owner = segment_owner.get(str(item.get("segment_ref") or ""))
                    if owner is None:
                        continue
                    compact_by_ref[owner][key].append(item)
                    seen_batch_refs.add(owner)
        compact_rows = []
        for batch_ref in expected:
            compact = compact_by_ref[batch_ref]
            compact["limitations"] = sorted(set(compact["limitations"]))
            if batch_ref not in seen_batch_refs:
                compact["limitations"].append(
                    "模型稀疏输出省略整个空批次，已确定性补为空结果。"
                )
            compact_rows.append(compact)
        rows = []
        for batch in group:
            compact = next(
                row for row in compact_rows if row["batch_ref"] == batch["batch_ref"]
            )
            segments = {
                str(segment["segment_ref"]): segment for segment in batch["segments"]
            }
            facts_by_segment: dict[str, list[dict[str, Any]]] = {}
            for compact_fact in compact.get("facts") or ():
                segment_ref = str(compact_fact.get("segment_ref") or "")
                segment = segments.get(segment_ref)
                if segment is None:
                    continue
                fact = dict(compact_fact)
                fact.pop("segment_ref", None)
                quote = _layout_exact_quote(
                    str(fact.get("exact_quote") or ""), str(segment["text"])
                )
                fact["exact_quote"] = quote
                quote_start = str(segment["text"]).find(quote)
                absolute_start = int(segment["start_offset"]) + max(0, quote_start)
                absolute_end = absolute_start + len(quote)
                span_refs = [
                    str(span["span_ref"])
                    for span in segment.get("spans") or ()
                    if int(span["end_offset"]) > absolute_start
                    and int(span["start_offset"]) < absolute_end
                ]
                if not span_refs and segment.get("spans"):
                    span_refs = [str(segment["spans"][0]["span_ref"])]
                fact.update(
                    {
                        "fact_id": "FACT-AUTO-" + _digest(
                            [segment_ref, quote, fact.get("action_summary")]
                        )[:20].upper(),
                        "evidence_span_refs": span_refs,
                        "legacy_status": "not_shown",
                        "legacy_basis": "原文未显示跨期延续。",
                        "projection_eligibility": "direct_neutral_fact",
                    }
                )
                facts_by_segment.setdefault(segment_ref, []).append(fact)
            reviews = {
                segment_ref: {
                    "segment_ref": segment_ref,
                    "decision": "accept",
                    "context_status": "sufficient",
                    "facts": facts,
                    "reason": "轻量事件发现返回直接中性事实。",
                }
                for segment_ref, facts in facts_by_segment.items()
            }
            for request in compact.get("context_requests") or ():
                segment_ref = str(request.get("segment_ref") or "")
                if segment_ref in segments and segment_ref not in reviews:
                    reviews[segment_ref] = {
                        "segment_ref": segment_ref,
                        "decision": "reject",
                        "context_status": str(request["context_status"]),
                        "facts": [],
                        "reason": "需要紧邻上下文。",
                    }
            rows.append(
                {
                    "schema_version": OUTPUT_SCHEMA_VERSION,
                    "batch_ref": batch["batch_ref"],
                    "page_title": batch["page_title"],
                    "revision_ref": batch["revision_ref"],
                    "segment_count": len(batch["segments"]),
                    "segment_reviews": list(reviews.values()),
                    "limitations": list(compact.get("limitations") or ()),
                }
            )
        extra_calls = 0
        for batch in group:
            raw_result = next(
                row for row in rows if row["batch_ref"] == batch["batch_ref"]
            )
            reviews = {
                str(review.get("segment_ref") or ""): review
                for review in raw_result.get("segment_reviews") or ()
            }
            for segment in batch["segments"]:
                segment_ref = str(segment["segment_ref"])
                review = reviews.get(segment_ref) or {}
                context_status = str(review.get("context_status") or "sufficient")
                if context_status == "sufficient":
                    continue
                expanded = _prompt_segment_view(
                    segment, context_status=context_status
                )
                if expanded["text"] == _prompt_segment_view(segment)["text"]:
                    review["context_status"] = "sufficient"
                    continue
                split = {
                    **dict(batch),
                    "batch_ref": f"{batch['batch_ref']}--CONTEXT--{segment_ref}",
                    "segments": [expanded],
                }
                expanded_result, expanded_calls = run_group(
                    [split], strict_quotes=strict_quotes
                )
                if len(expanded_result) != 1:
                    raise ValueError("中性材料按需扩窗未返回唯一结果")
                expanded_review = list(
                    expanded_result[0].get("segment_reviews") or ()
                )
                if len(expanded_review) != 1:
                    raise ValueError("中性材料按需扩窗未返回唯一片段")
                expanded_review[0]["context_status"] = "sufficient"
                reviews[segment_ref] = expanded_review[0]
                extra_calls += 1 + expanded_calls
            for segment in batch["segments"]:
                segment_ref = str(segment["segment_ref"])
                reviews.setdefault(
                    segment_ref,
                    {
                        "segment_ref": segment_ref,
                        "decision": "reject",
                        "context_status": "sufficient",
                        "facts": [],
                        "reason": "模型稀疏输出未返回该片段，按无合格中性事实处理。",
                    },
                )
            raw_result["segment_reviews"] = [
                reviews[str(segment["segment_ref"])]
                for segment in batch["segments"]
            ]
            repaired = _canonicalize_result(
                batch,
                raw_result,
                subject_ref_by_name=subject_ref_by_name,
                identity_resolver=identity_resolver,
                # An unverifiable quote cannot become evidence. Reject it
                # deterministically instead of paying another model round trip
                # to repair model-authored text.
                drop_unverifiable_quotes=True,
            )
            raw_result.clear()
            raw_result.update(repaired)
        return rows, extra_calls

    def valid_seed_reviews(
        batch: Mapping[str, Any], result: Mapping[str, Any]
    ) -> dict[str, Mapping[str, Any]]:
        reviews = {
            str(review.get("segment_ref") or ""): review
            for review in result.get("segment_reviews") or ()
        }
        valid = {}
        for segment in batch["segments"]:
            segment_ref = str(segment["segment_ref"])
            review = reviews.get(segment_ref)
            if review is None:
                continue
            mini_batch = {**dict(batch), "segments": [segment]}
            mini_result = {
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "batch_ref": batch["batch_ref"],
                "page_title": batch["page_title"],
                "revision_ref": batch["revision_ref"],
                "segment_count": 1,
                "segment_reviews": [review],
                "limitations": list(result.get("limitations") or ()),
            }
            try:
                validate_one(mini_batch, mini_result)
            except ValueError:
                continue
            valid[segment_ref] = review
        return valid

    fallback_by_ref = {
        str(batch["batch_ref"]): batch
        for batch in pending
        if str(batch["batch_ref"]) in retry_seeds
    }
    fallback_by_ref.update(
        {str(batch["batch_ref"]): batch for batch in oversized_fresh}
    )
    fallback_by_ref.update(
        {
            str(batch["batch_ref"]): batch
            for batch in pending
            if str(batch["batch_ref"]) in direct_fallback_refs
        }
    )

    def persist_rows(
        rows: Sequence[Mapping[str, Any]],
    ) -> list[Mapping[str, Any]]:
        failed = []
        for result in rows:
            batch_ref = str(result["batch_ref"])
            batch = next(
                row
                for row in plan["page_batches"]
                if row["batch_ref"] == batch_ref
            )
            seeded_reviews = seeded_reviews_by_batch.get(batch_ref) or {}
            if seeded_reviews:
                reviews = {
                    str(review.get("segment_ref") or ""): review
                    for review in result.get("segment_reviews") or ()
                }
                reviews.update(seeded_reviews)
                result = {
                    **dict(result),
                    "segment_count": len(batch["segments"]),
                    "segment_reviews": [
                        reviews[str(segment["segment_ref"])]
                        for segment in batch["segments"]
                    ],
                    "limitations": sorted(
                        {
                            *[str(value) for value in result.get("limitations") or ()],
                            *seeded_limitations_by_batch.get(batch_ref, ()),
                        }
                    ),
                }
            try:
                validate_one(batch, result)
            except ValueError:
                failed.append(batch)
                continue
            results[batch_ref] = result
            _atomic_json(
                checkpoint_dir / f"{batch_ref}.json",
                {
                    "batch_fingerprint": batch_fingerprints[batch_ref],
                    "result": result,
                },
            )
        return failed

    failed_batches: list[Mapping[str, Any]] = []
    if groups:
        canary_group, *parallel_groups = groups
        canary_rows, canary_extra_calls = run_group(canary_group)
        model_call_count += canary_extra_calls
        canary_failures = persist_rows(canary_rows)
        if canary_failures:
            raise RuntimeError("中性抽取 canary 未通过当前事实合同，已停止并发扇出")
        with ThreadPoolExecutor(
            max_workers=min(max_workers, len(parallel_groups) or 1)
        ) as pool:
            futures = {
                pool.submit(run_group, group): group for group in parallel_groups
            }
            for future in as_completed(futures):
                try:
                    rows, extra_calls = future.result()
                    model_call_count += extra_calls
                    failed_batches.extend(persist_rows(rows))
                except ModelBatchAnomalyError:
                    for pending_future in futures:
                        pending_future.cancel()
                    raise
                except Exception:
                    failed_batches.extend(futures[future])
    for batch in failed_batches:
        fallback_by_ref[str(batch["batch_ref"])] = batch

    fallback = list(fallback_by_ref.values())
    if fallback:
        valid_reviews_by_batch = {
            str(batch["batch_ref"]): valid_seed_reviews(
                batch, retry_seeds[str(batch["batch_ref"])]
            )
            if str(batch["batch_ref"]) in retry_seeds
            else {}
            for batch in fallback
        }
        for batch in fallback:
            batch_ref = str(batch["batch_ref"])
            for segment in batch["segments"]:
                segment_ref = str(segment["segment_ref"])
                checkpoint = segment_checkpoint_dir / f"{batch_ref}--{segment_ref}.json"
                if not checkpoint.is_file():
                    continue
                payload = json.loads(checkpoint.read_text(encoding="utf-8"))
                if payload.get("batch_fingerprint") != batch_fingerprints[batch_ref]:
                    continue
                review = payload.get("review")
                if not isinstance(review, Mapping):
                    continue
                mini_batch = {**dict(batch), "segments": [segment]}
                mini_result = {
                    "schema_version": OUTPUT_SCHEMA_VERSION,
                    "batch_ref": batch_ref,
                    "page_title": batch["page_title"],
                    "revision_ref": batch["revision_ref"],
                    "segment_count": 1,
                    "segment_reviews": [review],
                    "limitations": list(payload.get("limitations") or ()),
                }
                try:
                    validate_one(mini_batch, mini_result)
                except ValueError:
                    continue
                valid_reviews_by_batch[batch_ref][segment_ref] = review
        fallback_tasks: list[tuple[Mapping[str, Any], list[Mapping[str, Any]]]] = []
        fallback_chunk_char_limit = max(
            420, 1800 * min(max(1, pages_per_call), 5) // 5
        )
        for batch in fallback:
            batch_ref = str(batch["batch_ref"])
            chunk: list[Mapping[str, Any]] = []
            chunk_chars = 0
            for segment in batch["segments"]:
                if str(segment["segment_ref"]) in valid_reviews_by_batch[batch_ref]:
                    continue
                segment_chars = len(
                    _prompt_segment_view(segment)["text"]
                )
                if chunk and (
                    chunk_chars + segment_chars > fallback_chunk_char_limit
                    or len(chunk) >= MODEL_GROUP_SEGMENT_LIMIT
                ):
                    fallback_tasks.append((batch, chunk))
                    chunk = []
                    chunk_chars = 0
                chunk.append(segment)
                chunk_chars += segment_chars
            if chunk:
                fallback_tasks.append((batch, chunk))
        model_call_count += len(fallback_tasks)

        segment_errors: dict[str, Exception] = {}
        actual_segment_call_count = 0
        limitations_by_batch: dict[str, set[str]] = {
            str(batch["batch_ref"]): {
                str(value)
                for value in (retry_seeds.get(str(batch["batch_ref"])) or {}).get(
                    "limitations"
                )
                or ()
            }
            for batch in fallback
        }
        def run_fallback_chunk(
            batch: Mapping[str, Any],
            segments: Sequence[Mapping[str, Any]],
        ) -> tuple[Mapping[str, Any], int]:
            split = {
                **dict(batch),
                "batch_ref": f"{batch['batch_ref']}--FALLBACK-{segments[0]['segment_ref']}",
                "segments": list(segments),
            }
            result_rows, nested_calls = run_group([split], strict_quotes=True)
            row = result_rows[0]
            reviews = {
                str(review["segment_ref"]): review
                for review in row.get("segment_reviews") or ()
            }
            calls = 1 + nested_calls
            missing = [
                str(segment["segment_ref"])
                for segment in segments
                if str(segment["segment_ref"]) not in reviews
            ]
            if missing:
                raise ValueError(
                    "定向修订仍遗漏中性片段: " + ", ".join(missing)
                )
            row["segment_reviews"] = [
                reviews[str(segment["segment_ref"])] for segment in segments
            ]
            return row, calls

        if fallback_tasks:
            with ThreadPoolExecutor(
                max_workers=min(max_workers, len(fallback_tasks))
            ) as pool:
                futures = {
                    pool.submit(run_fallback_chunk, batch, segments): (batch, segments)
                    for batch, segments in fallback_tasks
                }
                for future in as_completed(futures):
                    batch, segments = futures[future]
                    batch_ref = str(batch["batch_ref"])
                    try:
                        row, call_count = future.result()
                    except ModelBatchAnomalyError:
                        for pending_future in futures:
                            pending_future.cancel()
                        raise
                    except Exception as exc:
                        for segment in segments:
                            segment_errors[
                                f"{batch_ref}/{segment['segment_ref']}"
                            ] = exc
                        continue
                    actual_segment_call_count += call_count
                    limitations_by_batch[batch_ref].update(
                        str(value) for value in row.get("limitations") or ()
                    )
                    for review in row["segment_reviews"]:
                        segment_ref = str(review["segment_ref"])
                        valid_reviews_by_batch[batch_ref][segment_ref] = review
                        _atomic_json(
                            segment_checkpoint_dir / f"{batch_ref}--{segment_ref}.json",
                            {
                                "batch_fingerprint": batch_fingerprints[batch_ref],
                                "review": review,
                                "limitations": list(row.get("limitations") or ()),
                            },
                        )
        for batch in fallback:
            batch_ref = str(batch["batch_ref"])
            if any(key.startswith(batch_ref + "/") for key in segment_errors):
                continue
            reviews = [
                valid_reviews_by_batch[batch_ref][str(segment["segment_ref"])]
                for segment in batch["segments"]
            ]
            combined = {
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "batch_ref": batch_ref,
                "page_title": batch["page_title"],
                "revision_ref": batch["revision_ref"],
                "segment_count": len(batch["segments"]),
                "segment_reviews": reviews,
                "limitations": sorted(limitations_by_batch[batch_ref]),
            }
            if persist_rows([combined]):
                segment_errors[batch_ref] = ValueError(
                    "严格引文重试后仍未通过当前中性事实合同"
                )
        model_call_count += actual_segment_call_count - len(fallback_tasks)
        if segment_errors:
            failed_refs = ", ".join(sorted(segment_errors))
            first = segment_errors[sorted(segment_errors)[0]]
            raise RuntimeError(
                f"中性抽取片段重试失败，已保存其余成功页面: {failed_refs}"
            ) from first
    ordered = [
        json.loads(json.dumps(results[str(batch["batch_ref"])], ensure_ascii=False))
        for batch in plan["page_batches"]
    ]
    supplemental_facts_by_segment = dict(supplemental_facts_by_segment or {})
    if supplemental_facts_by_segment:
        for result in ordered:
            for review in result.get("segment_reviews") or ():
                supplemental = supplemental_facts_by_segment.get(
                    str(review.get("segment_ref") or ""), ()
                )
                existing_quotes = {
                    str(fact.get("exact_quote") or "")
                    for fact in review.get("facts") or ()
                }
                additions = [
                    dict(fact)
                    for fact in supplemental
                    if str(fact.get("exact_quote") or "") not in existing_quotes
                ]
                if not additions:
                    continue
                review["facts"] = [*(review.get("facts") or ()), *additions]
                review["decision"] = "accept"
                review["context_status"] = "sufficient"
                review["reason"] = (
                    "通用抽取结果已合并确定性军事行动事实；成果方向仍由后置投影裁决。"
                )
    fanout = build_shared_neutral_fact_fanout(plan, ordered)
    event_refs_by_fact: dict[str, set[str]] = {}
    for binding in plan.get("event_fact_bindings") or ():
        event_refs_by_fact.setdefault(str(binding["fact_ref"]), set()).add(
            str(binding["event_ref"])
        )
    event_refs_by_segment: dict[str, set[str]] = {}
    for binding in plan.get("target_segment_event_bindings") or ():
        event_refs_by_segment.setdefault(str(binding["segment_ref"]), set()).add(
            str(binding["event_ref"])
        )
    if event_refs_by_fact or event_refs_by_segment:
        grouped_fact_refs: dict[str, list[str]] = {}
        for fact in fanout["facts"]:
            event_refs = sorted(
                event_refs_by_fact.get(str(fact["fact_ref"]), set())
                or event_refs_by_segment.get(str(fact["segment_ref"]), set())
            )
            if not event_refs:
                continue
            fact["event_refs"] = event_refs
            for event_ref in event_refs:
                grouped_fact_refs.setdefault(event_ref, []).append(str(fact["fact_ref"]))
        fanout["event_groups"] = [
            {
                "event_ref": str(signature["event_ref"]),
                "fact_refs": sorted(grouped_fact_refs.get(str(signature["event_ref"]), [])),
            }
            for signature in plan.get("event_signatures") or ()
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "ruler": plan["ruler"],
        "source_index_identity": plan["source_index_identity"],
        "plan_fingerprint": _digest(plan),
        "batch_fingerprints": batch_fingerprints,
        "batch_results": ordered,
        "fanout": fanout,
        **(
            {"event_signatures": list(plan.get("event_signatures") or ())}
            if plan.get("event_signatures") is not None
            else {}
        ),
        "model_call_count": model_call_count,
    }
