from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import shlex
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from opencc import OpenCC


PLAN_SCHEMA_VERSION = "hanchi-locator-search-plan-v1"
BATCH_PLAN_SCHEMA_VERSION = "hanchi-locator-batch-plan-v1"
BATCH_RESULT_SCHEMA_VERSION = "hanchi-locator-batch-result-v1"
_T2S = OpenCC("t2s")
_SPACE = re.compile(r"\s+")
_MODES = ("simple", "advanced", "professional")
_HANCHI_HOST = "hanchi.ihp.sinica.edu.tw"
_DYNASTY_FIELDS = {
    "先秦": "DY.0.2.0.3.S",
    "秦汉": "DY.0.2.3.3.S",
    "魏晋南北朝": "DY.0.2.6.3.S",
    "隋唐五代": "DY.0.2.9.3.S",
    "宋辽金": "DY.0.2.12.3.S",
    "元": "DY.0.2.15.3.S",
    "明": "DY.0.2.18.3.S",
    "清": "DY.0.2.21.3.S",
    "民国": "DY.0.2.24.3.S",
}
_ANCHOR = re.compile(
    r"<a\b[^>]*?href=[\"']?([^\"'\s>]+)[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_INPUT = re.compile(r"<input\b([^>]*)>", re.IGNORECASE)
_FORM_ACTION = re.compile(
    r"<form\b[^>]*?action\s*=\s*(?:[\"']([^\"']+)[\"']|([^\s>]+))",
    re.IGNORECASE,
)
_ATTRIBUTE = re.compile(
    r"([:@.\w-]+)(?:\s*=\s*(?:[\"']([^\"']*)[\"']|([^\s>]+)))?",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


def _normalized(value: str) -> str:
    return _SPACE.sub("", _T2S.convert(str(value).strip()))


@dataclass(frozen=True, slots=True)
class HanchiQuery:
    mode: str
    subject_term: str
    dynasty_scope: str
    result_role: str
    topic_term: str | None = None
    distance_lower: int | None = None
    distance_upper: int | None = None
    variant_search: bool = True


@dataclass(frozen=True, slots=True)
class HanchiPostTemplate:
    url: str
    headers: tuple[tuple[str, str], ...]
    form_fields: tuple[tuple[str, str], ...]


def load_hanchi_curl_template(path: Path) -> HanchiPostTemplate:
    """Read a browser Copy-as-cURL capture without exposing its session state."""
    tokens = shlex.split(path.read_text(encoding="utf-8-sig"), posix=True)
    url = next((token for token in tokens[1:] if token.startswith("http")), "")
    split = urlsplit(url)
    if split.scheme != "https" or split.hostname != _HANCHI_HOST or "/ihpc/hanjiquery" not in split.path:
        raise ValueError("汉籍库 POST 模板 URL 非法")
    headers: list[tuple[str, str]] = []
    payloads: list[str] = []
    for index, token in enumerate(tokens):
        if token in {"-H", "--header"} and index + 1 < len(tokens):
            name, separator, value = tokens[index + 1].partition(":")
            if separator and name.strip().lower() in {
                "accept",
                "accept-language",
                "cache-control",
                "origin",
                "referer",
                "user-agent",
            }:
                headers.append((name.strip(), value.strip()))
        elif token in {"--data", "--data-raw", "--data-binary", "-d"} and index + 1 < len(tokens):
            payloads.append(tokens[index + 1])
    if not payloads:
        raise ValueError("汉籍库 POST 模板缺少表单数据")
    fields = tuple(pair for payload in payloads for pair in parse_qsl(payload, keep_blank_values=True))
    if not any(name == "_TTS_CONTROL" and value for name, value in fields):
        raise ValueError("汉籍库 POST 模板缺少当次表单控制值")
    return HanchiPostTemplate(url=url, headers=tuple(headers), form_fields=fields)


def _replace_fields(
    fields: Sequence[tuple[str, str]],
    *,
    remove_prefixes: Sequence[str] = (),
    remove_names: Sequence[str] = (),
    additions: Sequence[tuple[str, str]] = (),
) -> tuple[tuple[str, str], ...]:
    removed = set(remove_names)
    kept = [
        (name, value)
        for name, value in fields
        if name not in removed and not any(name.startswith(prefix) for prefix in remove_prefixes)
    ]
    addition_names = {name for name, _value in additions}
    kept = [(name, value) for name, value in kept if name not in addition_names]
    return tuple([*kept, *additions])


def build_hanchi_post_fields(
    template: HanchiPostTemplate, query: Mapping[str, Any]
) -> tuple[tuple[str, str], ...]:
    """Project the verified Hanchi form contract for simple/professional POSTs."""
    mode = str(query.get("mode") or "")
    subject = str(query.get("subject_term") or "").strip()
    dynasty = str(query.get("dynasty_scope") or "").strip()
    dynasty_field = _DYNASTY_FIELDS.get(dynasty)
    if not subject or dynasty_field is None:
        raise ValueError("汉籍库 POST query 缺少检索词或朝代字段不受支持")
    common_remove = tuple(["_IMG_搜尋.x", "_IMG_搜尋.y", *_DYNASTY_FIELDS.values()])
    common_additions = (
        (dynasty_field, "on"),
        ("SY.0.1.15.3.S", "on") if bool(query.get("variant_search", True)) else ("@SY.0.1.15.3.S", ""),
        ("_IMG_搜尋.x", "12"),
        ("_IMG_搜尋.y", "7"),
    )
    if mode == "simple":
        return _replace_fields(
            template.form_fields,
            remove_prefixes=("XX.1.", "@XX.1.", "_IMG_"),
            remove_names=common_remove,
            additions=(
                ("@XX.0.0.0.0.T", ""),
                ("XX.0.0.0.0.T", subject),
                ("@BN.0.1.0.3.S", ""),
                ("@TX.0.1.3.3.S", ""),
                ("TX.0.1.3.3.S", "on"),
                ("@RM.0.1.6.3.S", ""),
                ("RM.0.1.6.3.S", "on"),
                ("@IX.0.1.9.3.S", ""),
                *common_additions,
            ),
        )
    if mode == "professional":
        topic = str(query.get("topic_term") or "").strip()
        if not topic:
            raise ValueError("汉籍库专业检索必须同时提供两个词")
        return _replace_fields(
            template.form_fields,
            remove_prefixes=("XX.0.", "@XX.0.", "_TTS.SB", "_TTS_SB", "_IMG_"),
            remove_names=common_remove,
            additions=(
                ("XX.1.0.0.0.T", subject),
                ("XX.1.1.0.0.T", topic),
                ("XX.1.4.0.4.T", str(int(query.get("distance_lower") or 1))),
                ("XX.1.5.0.4.T", str(int(query.get("distance_upper") or 20))),
                *common_additions,
            ),
        )
    if mode == "advanced":
        topic = str(query.get("topic_term") or "").strip()
        if not topic:
            raise ValueError("汉籍库进阶检索必须提供主题词")
        return _replace_fields(
            template.form_fields,
            remove_prefixes=("XX.1.", "@XX.1.", "_TTS.SB", "_TTS_SB"),
            remove_names=common_remove,
            additions=(
                ("_TTS_SBT0", subject),
                ("_TTS.SBY0", "F"),
                ("_TTS.SBC1", "AND"),
                ("_TTS.SBT1", topic),
                ("_TTS.SBF1", "TX"),
                ("_TTS.SBY1", "F"),
                ("_TTS.SBC2", "AND"),
                ("_TTS.SBT2", ""),
                ("_TTS.SBF2", "XX"),
                ("_TTS.SBY2", "F"),
                ("_TTS.SBC3", "AND"),
                ("_TTS.SBT3", ""),
                ("_TTS.SBF3", "XX"),
                ("_TTS.SBY3", "F"),
                *common_additions,
            ),
        )
    raise ValueError("汉籍库 POST query 模式不受支持")


def _hidden_hanchi_form_fields(html: str) -> tuple[tuple[str, str], ...]:
    fields = []
    for attributes in _INPUT.findall(html):
        parsed = {
            name.lower(): unescape(quoted if quoted != "" else unquoted or "")
            for name, quoted, unquoted in _ATTRIBUTE.findall(attributes)
        }
        if parsed.get("type", "").lower() != "hidden" or not parsed.get("name"):
            continue
        fields.append((parsed["name"], parsed.get("value", "")))
    return tuple(fields)


def _hanchi_form_fields(html: str) -> dict[str, str]:
    """Return browser-successful form controls from a Hanchi response.

    A browser does not submit unchecked checkbox/radio controls or submit/image
    buttons.  Replaying every ``input`` found in the response changes Hanchi's
    server-side form state (notably the dynasty scope), so the returned state
    must follow the HTML successful-controls rules before the next POST.
    """
    fields: dict[str, str] = {}
    for attributes in _INPUT.findall(html):
        parsed = {
            name.lower(): unescape(quoted if quoted != "" else unquoted or "")
            for name, quoted, unquoted in _ATTRIBUTE.findall(attributes)
        }
        name = parsed.get("name", "")
        input_type = parsed.get("type", "text").lower()
        if not name or input_type in {"button", "file", "image", "reset", "submit"}:
            continue
        if input_type in {"checkbox", "radio"} and "checked" not in parsed:
            continue
        fields[name] = parsed.get(
            "value", "on" if input_type in {"checkbox", "radio"} else ""
        )
    return fields


def _hanchi_form_action(html: str, *, base_url: str) -> str:
    for quoted, unquoted in _FORM_ACTION.findall(html):
        action = unescape(quoted or unquoted)
        absolute = urljoin(base_url, action)
        split = urlsplit(absolute)
        if (
            split.scheme == "https"
            and split.hostname == _HANCHI_HOST
            and "/ihpc/hanjiquery" in split.path
        ):
            return absolute
    raise ValueError("汉籍库响应缺少可验证的下一步表单 action")


def _template_mode(template: HanchiPostTemplate) -> str:
    names = {name for name, _value in template.form_fields}
    if any(name.startswith("XX.1.") for name in names):
        return "professional"
    if "_TTS_SBT0" in names or "_TTS.SBT0" in names:
        return "advanced"
    if "XX.0.0.0.0.T" in names:
        return "simple"
    raise ValueError("无法识别汉籍库 cURL 模板的检索模式")


def _validate_query_echo(html: str, query: Mapping[str, Any]) -> dict[str, str]:
    fields = _hanchi_form_fields(html)
    mode = str(query.get("mode") or "")
    expected_subject = str(query.get("subject_term") or "")
    expected_topic = str(query.get("topic_term") or "")
    if mode == "simple":
        actual = {"subject_term": fields.get("XX.0.0.0.0.T", "")}
    elif mode == "advanced":
        actual = {
            "subject_term": fields.get("_TTS_SBT0", fields.get("_TTS.SBT0", "")),
            "topic_term": fields.get("_TTS_SBT1", fields.get("_TTS.SBT1", "")),
        }
    elif mode == "professional":
        actual = {
            "subject_term": fields.get("XX.1.0.0.0.T", ""),
            "topic_term": fields.get("XX.1.1.0.0.T", ""),
        }
    else:
        raise ValueError("汉籍库检索模式不受支持")
    if actual.get("subject_term") != expected_subject or (
        mode in {"advanced", "professional"}
        and actual.get("topic_term") != expected_topic
    ):
        raise ValueError(
            "汉籍库响应未回显本次检索词，拒绝陈旧或错误查询结果: "
            f"mode={mode}, expected_subject={expected_subject}, "
            f"expected_topic={expected_topic}, actual={actual}"
        )
    return actual


def _post_hanchi_fields(
    template: HanchiPostTemplate,
    fields: Sequence[tuple[str, str]],
    *,
    timeout_seconds: int,
) -> str:
    headers = {name: value for name, value in template.headers}
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(
        template.url,
        data=urlencode(fields).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
        if response.status != 200:
            raise ValueError(f"汉籍库 POST 返回 HTTP {response.status}")
    return html


def parse_hanchi_result_html(
    html: str, *, allowed_books: Sequence[str] = ()
) -> dict[str, Any]:
    plain = re.sub(r"\s+", " ", unescape(_TAG.sub(" ", html)))
    summary = re.search(r"共計\s*(\d+)本書\s*[,，]\s*(\d+)個章節", plain)
    # A Hanchi form page contains unrelated ``N筆 (...)`` strings.  Counts are
    # only trustworthy when the response also carries the result-summary
    # marker; otherwise accepting the first page-wide number can silently turn
    # a failed search into fabricated recall.
    hit = re.search(r"(\d+)筆\s*\([^)]*\)", plain) if summary else None
    explicit_zero = bool(
        re.search(r"(?:查無|沒有|無)\s*(?:符合|相符)?\s*(?:資料|結果|紀錄|記錄)", plain)
    )
    normalized_allowed = tuple(_normalized(value) for value in allowed_books if str(value).strip())
    allowed_book_pairs = tuple(
        (str(value).strip(), _normalized(value))
        for value in allowed_books
        if str(value).strip()
    )
    locators = []
    seen = set()
    for href, raw_text in _ANCHOR.findall(html):
        text = re.sub(r"\s+", " ", unescape(_TAG.sub(" ", raw_text))).strip()
        normalized_text = _normalized(text)
        if not text or (normalized_allowed and not any(book in normalized_text for book in normalized_allowed)):
            continue
        absolute = urljoin("https://hanchi.ihp.sinica.edu.tw/ihpc/", unescape(href))
        if urlsplit(absolute).hostname != _HANCHI_HOST:
            continue
        matched_book = next(
            (
                (raw_book, normalized_book)
                for raw_book, normalized_book in allowed_book_pairs
                if normalized_book in normalized_text
            ),
            None,
        )
        # Result links carry the live ``@@...`` session token and are neither
        # durable locators nor safe runtime output.  The title is the only
        # cross-session locator at this stage; source backfill resolves it
        # independently against the configured corpus.
        stable_title = matched_book[0] if matched_book else text
        stable_key_text = matched_book[1] if matched_book else normalized_text
        locator_key = f"hanchi-title:{sha256(stable_key_text.encode('utf-8')).hexdigest()[:20]}"
        if locator_key in seen:
            continue
        seen.add(locator_key)
        locators.append(
            {
                "locator_key": locator_key,
                "locator": {
                    "title": stable_title,
                    "resolution": "independent_source_backfill",
                    **({"source_work": matched_book[0]} if matched_book else {}),
                },
            }
        )
    return {
        "book_count": int(summary.group(1)) if summary else (0 if explicit_zero else None),
        "chapter_count": int(summary.group(2)) if summary else (0 if explicit_zero else None),
        "hit_count": int(hit.group(1)) if hit else (0 if explicit_zero else None),
        "locator_hits": locators,
    }


def submit_hanchi_post_query(
    template: HanchiPostTemplate,
    query: Mapping[str, Any],
    *,
    allowed_books: Sequence[str] = (),
    timeout_seconds: int = 30,
    form_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    active_template = template
    network_request_count = 1
    mode = str(query.get("mode") or "")
    _template_mode(template)
    current_mode = ""
    if form_state:
        state_fields = form_state.get("fields") or {}
        state_url = str(form_state.get("url") or template.url)
        state_split = urlsplit(state_url)
        if not isinstance(state_fields, Mapping):
            raise ValueError("汉籍库返回表单状态非法")
        if (
            state_split.scheme != "https"
            or state_split.hostname != _HANCHI_HOST
            or "/ihpc/hanjiquery" not in state_split.path
        ):
            raise ValueError("汉籍库返回表单 action 非法")
        refreshed = tuple(
            (str(name), str(value))
            for name, value in state_fields.items()
        )
        if not {"_TTS_ACTION", "_TTS_CONTROL"} <= {
            name for name, _value in refreshed
        }:
            raise ValueError("汉籍库返回表单状态缺少控制值")
        active_template = HanchiPostTemplate(
            url=state_url,
            headers=template.headers,
            form_fields=refreshed,
        )
        current_mode = str(form_state.get("mode") or "")
    switch_button = {
        "simple": "_IMG_簡易查詢",
        "advanced": "_IMG_進階查詢",
        "professional": "_IMG_專業查詢",
    }.get(mode) if current_mode != mode else None
    if switch_button:
        switch_fields = _replace_fields(
            active_template.form_fields,
            remove_prefixes=("_IMG_",),
            remove_names=("_IMG_搜尋.x", "_IMG_搜尋.y"),
            additions=((f"{switch_button}.x", "12"), (f"{switch_button}.y", "7")),
        )
        switch_html = _post_hanchi_fields(
            active_template, switch_fields, timeout_seconds=timeout_seconds
        )
        hidden = _hidden_hanchi_form_fields(switch_html)
        hidden_names = {name for name, _value in hidden}
        if not {"_TTS_ACTION", "_TTS_CONTROL"} <= hidden_names:
            raise ValueError("汉籍库切换检索表单后缺少刷新控制值")
        active_template = HanchiPostTemplate(
            url=_hanchi_form_action(switch_html, base_url=active_template.url),
            headers=active_template.headers,
            form_fields=tuple(_hanchi_form_fields(switch_html).items()),
        )
        network_request_count = 2
    fields = build_hanchi_post_fields(active_template, query)
    html = _post_hanchi_fields(
        active_template, fields, timeout_seconds=timeout_seconds
    )
    parsed = parse_hanchi_result_html(html, allowed_books=allowed_books)
    parsed["query_echo"] = _validate_query_echo(html, query)
    returned_fields = _hanchi_form_fields(html)
    returned_names = set(returned_fields)
    returned_mode = _template_mode(
        HanchiPostTemplate(
            url=active_template.url,
            headers=(),
            form_fields=tuple(returned_fields.items()),
        )
    )
    if returned_mode != mode or not {"_TTS_ACTION", "_TTS_CONTROL"} <= returned_names:
        raise ValueError("汉籍库响应表单模式或动态控制字段与本次查询不一致")
    next_url = _hanchi_form_action(html, base_url=active_template.url)
    if (
        parsed["book_count"] is None
        and parsed["chapter_count"] is None
        and parsed["hit_count"] is None
        and not parsed["locator_hits"]
    ):
        # Hanchi returns the validated query form without a result summary for
        # a genuine zero-match search.  Only accept that state after the echo,
        # mode, rotating action and control-field checks above all succeed.
        parsed.update(
            {
                "book_count": 0,
                "chapter_count": 0,
                "hit_count": 0,
                "result_status": "completed_no_match",
                "zero_result_basis": "validated_echo_mode_action_and_controls",
            }
        )
    else:
        parsed["result_status"] = (
            "completed_with_matches"
            if int(parsed.get("hit_count") or 0) > 0 or parsed["locator_hits"]
            else "completed_no_match"
        )
    parsed["network_request_count"] = network_request_count
    parsed["form_state"] = {
        "mode": mode,
        "url": next_url,
        "fields": returned_fields,
    }
    return parsed


def select_simple_recall_terms(
    observed_hit_counts: Mapping[str, int],
) -> tuple[str, ...]:
    """Keep the shortest empirically useful surface forms without redundant calls."""
    observed_by_normalized: dict[str, tuple[str, str, int]] = {}
    for raw_term, raw_count in observed_hit_counts.items():
        term = str(raw_term).strip()
        normalized = _normalized(term)
        count = int(raw_count)
        if count < 0:
            raise ValueError("汉籍库简易检索命中数不能为负数")
        if count > 0 and len(normalized) >= 2:
            existing = observed_by_normalized.get(normalized)
            if existing is None:
                observed_by_normalized[normalized] = (term, normalized, count)
            elif count > existing[2]:
                observed_by_normalized[normalized] = (
                    existing[0],
                    normalized,
                    count,
                )
    observed = list(observed_by_normalized.values())
    if not observed:
        raise ValueError("汉籍库简易检索至少需要一个非单字的有效命中词")

    retained = []
    for term, normalized, count in observed:
        dominated = any(
            other_normalized in normalized
            and other_normalized != normalized
            and other_count >= count
            for _other, other_normalized, other_count in observed
        )
        if not dominated:
            retained.append((term, normalized, count))
    return tuple(
        term
        for term, _normalized_term, _count in sorted(
            retained,
            key=lambda item: (len(item[1]), -item[2], item[0]),
        )
    )


def build_hanchi_search_plan(
    *,
    subject_name: str,
    observed_simple_hits: Mapping[str, int],
    dynasty_scope: str,
    broad_topics: Sequence[str] = (),
    professional_anchors: Sequence[str] = (),
    professional_distance_upper: int = 20,
) -> dict[str, Any]:
    subject = str(subject_name).strip()
    dynasty = str(dynasty_scope).strip()
    if not subject or not dynasty:
        raise ValueError("汉籍库检索规划缺少 subject_name 或 dynasty_scope")
    if professional_distance_upper <= 0:
        raise ValueError("汉籍库专业检索距离上限必须为正数")
    recall_terms = select_simple_recall_terms(observed_simple_hits)
    topics = tuple(dict.fromkeys(str(item).strip() for item in broad_topics if str(item).strip()))
    anchors = tuple(
        dict.fromkeys(str(item).strip() for item in professional_anchors if str(item).strip())
    )

    queries = [
        HanchiQuery("simple", term, dynasty, "mandatory_recall")
        for term in recall_terms
    ]
    queries.extend(
        HanchiQuery(
            "advanced",
            term,
            dynasty,
            "priority_only",
            topic_term=topic,
        )
        for term in recall_terms
        for topic in topics
    )
    # Professional predicates are never inferred from broad topics.  They must be
    # supplied as source-attested anchors and may only raise priority.
    queries.extend(
        HanchiQuery(
            "professional",
            term,
            dynasty,
            "priority_only",
            topic_term=anchor,
            distance_lower=1,
            distance_upper=professional_distance_upper,
        )
        for term in recall_terms
        for anchor in anchors
    )
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "subject_name": subject,
        "simple_recall_terms": list(recall_terms),
        "queries": [asdict(query) for query in queries],
        "merge_policy": {
            "simple_hits": "mandatory_and_never_filtered",
            "advanced_hits": "priority_only",
            "professional_hits": "priority_only",
            "full_text_fetch": "after_local_locator_deduplication",
        },
        "execution_policy": {
            "order": ["simple", "advanced", "professional"],
            "batch_by_mode": True,
            "concurrency": 1,
            "reuse_returned_form_state": True,
        },
    }


def build_hanchi_batch_search_plan(
    *,
    ruler: str,
    dynasty_scope: str,
    people: Sequence[Mapping[str, Any]],
    policy_entries: Sequence[Mapping[str, Any]] = (),
    max_person_entries: int = 12,
) -> dict[str, Any]:
    """Build one serial Hanchi plan without allowing per-focus person expansion."""
    ruler_name = str(ruler).strip()
    dynasty = str(dynasty_scope).strip()
    if not ruler_name or not dynasty:
        raise ValueError("汉籍库批量检索缺少皇帝或朝代范围")
    if max_person_entries <= 0 or max_person_entries > 12:
        raise ValueError("汉籍库人物入口上限必须在1至12之间")
    unique_people: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for raw in people:
        person_ref = str(raw.get("person_ref") or "").strip()
        subject_name = str(raw.get("subject_name") or raw.get("person_name") or "").strip()
        if not person_ref or not subject_name:
            raise ValueError("汉籍库人物入口缺少 person_ref 或 subject_name")
        if person_ref in seen_refs:
            continue
        seen_refs.add(person_ref)
        unique_people.append(dict(raw) | {"person_ref": person_ref, "subject_name": subject_name})
    selected = unique_people[:max_person_entries]
    deferred = [
        {
            "person_ref": row["person_ref"],
            "subject_name": row["subject_name"],
            "reason": "deferred_boundary_candidate",
        }
        for row in unique_people[max_person_entries:]
    ]

    entries: list[dict[str, Any]] = []
    for priority, row in enumerate(selected, start=1):
        observed_hits = row.get("observed_simple_hits") or {}
        simple_term_status = "observed"
        if not observed_hits:
            recall_terms = [
                str(value).strip()
                for value in (row.get("recall_terms") or (row["subject_name"],))
                if str(value).strip()
            ]
            observed_hits = {term: 1 for term in recall_terms}
            simple_term_status = "planned_unobserved"
        plan = build_hanchi_search_plan(
            subject_name=row["subject_name"],
            observed_simple_hits=observed_hits,
            dynasty_scope=dynasty,
            broad_topics=row.get("broad_topics") or (),
            professional_anchors=row.get("professional_anchors") or (),
            professional_distance_upper=int(row.get("professional_distance_upper") or 20),
        )
        entries.append(
            {
                "entry_kind": "person",
                "entry_ref": row["person_ref"],
                "priority": priority,
                "simple_term_status": simple_term_status,
                "search_plan": plan,
            }
        )
    policy_refs: set[str] = set()
    for index, raw in enumerate(policy_entries, start=1):
        entry_ref = str(raw.get("entry_ref") or f"POLICY-{index}").strip()
        candidate_ref = str(raw.get("candidate_ref") or entry_ref).strip()
        candidate_summary = str(
            raw.get("candidate_summary") or raw.get("candidate") or ""
        ).strip()
        if not entry_ref or not candidate_ref or entry_ref in policy_refs:
            raise ValueError("汉籍库政策入口缺少稳定候选身份或发生重复")
        policy_refs.add(entry_ref)
        subject_name = str(raw.get("subject_name") or ruler_name).strip()
        observed_hits = raw.get("observed_simple_hits") or {}
        simple_term_status = "observed"
        if not observed_hits:
            recall_terms = [
                str(value).strip()
                for value in (raw.get("recall_terms") or (subject_name,))
                if str(value).strip()
            ]
            observed_hits = {term: 1 for term in recall_terms}
            simple_term_status = "planned_unobserved"
        plan = build_hanchi_search_plan(
            subject_name=subject_name,
            observed_simple_hits=observed_hits,
            dynasty_scope=dynasty,
            broad_topics=raw.get("broad_topics") or (),
            professional_anchors=raw.get("professional_anchors") or (),
            professional_distance_upper=int(raw.get("professional_distance_upper") or 20),
        )
        entries.append(
            {
                "entry_kind": "policy",
                "entry_ref": entry_ref,
                "candidate_ref": candidate_ref,
                "candidate_summary": candidate_summary,
                "source_recall_terms": list(
                    dict.fromkeys(
                        str(value).strip()
                        for value in raw.get("source_recall_terms") or ()
                        if str(value).strip()
                    )
                ),
                "target_rule_hints": list(
                    dict.fromkeys(
                        str(value).strip()
                        for value in raw.get("target_rule_hints") or ()
                        if str(value).strip()
                    )
                ),
                "allowed_books": list(
                    dict.fromkeys(
                        str(value).strip()
                        for value in raw.get("allowed_books") or ()
                        if str(value).strip()
                    )
                ),
                "priority": index,
                "simple_term_status": simple_term_status,
                "search_plan": plan,
            }
        )
    flattened_queries = []
    for mode in _MODES:
        for entry in entries:
            for query in entry["search_plan"]["queries"]:
                if query["mode"] == mode:
                    flattened_queries.append(
                        {
                            **query,
                            "entry_kind": entry["entry_kind"],
                            "entry_ref": entry["entry_ref"],
                            "entry_priority": entry["priority"],
                            **(
                                {
                                    "candidate_ref": entry["candidate_ref"],
                                    "candidate_summary": entry["candidate_summary"],
                                    "target_rule_hints": entry["target_rule_hints"],
                                    "allowed_books": entry["allowed_books"],
                                }
                                if entry["entry_kind"] == "policy"
                                else {}
                            ),
                        }
                    )
    return {
        "schema_version": BATCH_PLAN_SCHEMA_VERSION,
        "ruler": ruler_name,
        "dynasty_scope": dynasty,
        "max_person_entries": max_person_entries,
        "selected_person_count": len(selected),
        "policy_entries_count_against_person_limit": False,
        "entries": entries,
        "queries": flattened_queries,
        "deferred_people": deferred,
        "execution_policy": {
            "order": list(_MODES),
            "concurrency": 1,
            "reuse_returned_form_state": True,
            "credentials_source": "runtime_request_template_only",
            "persist_cookies": False,
        },
    }


def merge_hanchi_locator_hits(
    hits: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Union locator rows while using advanced/professional matches only as tags."""
    merged: dict[str, dict[str, Any]] = {}
    for position, raw in enumerate(hits):
        locator_key = str(raw.get("locator_key") or "").strip()
        mode = str(raw.get("mode") or "").strip()
        if not locator_key or mode not in _MODES:
            raise ValueError("汉籍库定位结果缺少 locator_key 或检索模式无效")
        row = merged.setdefault(
            locator_key,
            {
                "locator_key": locator_key,
                "locator": dict(raw.get("locator") or {}),
                "matched_modes": [],
                "matched_queries": [],
                "first_seen": position,
            },
        )
        if mode not in row["matched_modes"]:
            row["matched_modes"].append(mode)
        query = str(raw.get("query") or "").strip()
        if query and query not in row["matched_queries"]:
            row["matched_queries"].append(query)

    mode_priority = {"professional": 0, "advanced": 1, "simple": 2}
    for row in merged.values():
        row["matched_modes"].sort(key=mode_priority.__getitem__)
        row["recall_origin"] = (
            "simple" if "simple" in row["matched_modes"] else "supplemental"
        )
        row["priority_tier"] = row["matched_modes"][0]
    return tuple(
        sorted(
            merged.values(),
            key=lambda row: (
                mode_priority[row["priority_tier"]],
                row["first_seen"],
                row["locator_key"],
            ),
        )
    )


def execute_hanchi_batch_plan(
    plan: Mapping[str, Any],
    *,
    submit_query: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    """Execute a planned serial POST flow through an injected Hanchi transport.

    The transport owns the live URL, cookies and HTML/form parsing.  It receives
    the next query plus the non-secret form state returned by the previous call.
    Credentials and cookies are deliberately never copied into the result.
    """
    if plan.get("schema_version") != BATCH_PLAN_SCHEMA_VERSION:
        raise ValueError("汉籍库批量执行只接受 batch plan v1")
    policy = plan.get("execution_policy") or {}
    if policy.get("concurrency") != 1 or policy.get("persist_cookies") is not False:
        raise ValueError("汉籍库批量执行必须串行且不得持久化 cookie")

    form_state: Mapping[str, Any] = {}
    raw_hits: list[dict[str, Any]] = []
    request_count = 0
    query_fanout_reuse_count = 0
    response_cache: dict[str, Mapping[str, Any]] = {}
    for raw_query in plan.get("queries") or ():
        if not isinstance(raw_query, Mapping):
            raise ValueError("汉籍库批量 query 必须是 object")
        cache_key = json.dumps(
            {
                key: raw_query.get(key)
                for key in (
                    "mode",
                    "subject_term",
                    "dynasty_scope",
                    "result_role",
                    "topic_term",
                    "distance_lower",
                    "distance_upper",
                    "variant_search",
                    "allowed_books",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        response = response_cache.get(cache_key)
        if response is None:
            response = submit_query(dict(raw_query), dict(form_state))
            if not isinstance(response, Mapping):
                raise ValueError("汉籍库 transport 返回值必须是 object")
            response_cache[cache_key] = dict(response)
            request_count += 1
            next_state = response.get("form_state") or {}
            if not isinstance(next_state, Mapping):
                raise ValueError("汉籍库 transport form_state 必须是 object")
            form_state = dict(next_state)
        else:
            query_fanout_reuse_count += 1
        for hit in response.get("hits") or ():
            if not isinstance(hit, Mapping):
                raise ValueError("汉籍库 transport hit 必须是 object")
            raw_hits.append(
                {
                    **dict(hit),
                    "mode": str(raw_query["mode"]),
                    "query": str(raw_query["subject_term"]),
                    "entry_kind": str(raw_query["entry_kind"]),
                    "entry_ref": str(raw_query["entry_ref"]),
                }
            )

    entry_results = []
    for entry in plan.get("entries") or ():
        entry_ref = str(entry["entry_ref"])
        hits = [row for row in raw_hits if row["entry_ref"] == entry_ref]
        entry_results.append(
            {
                "entry_kind": str(entry["entry_kind"]),
                "entry_ref": entry_ref,
                **(
                    {
                        "candidate_ref": str(entry["candidate_ref"]),
                        "candidate_summary": str(entry.get("candidate_summary") or ""),
                        "source_recall_terms": list(
                            entry.get("source_recall_terms") or ()
                        ),
                        "target_rule_hints": list(entry.get("target_rule_hints") or ()),
                        "allowed_books": list(entry.get("allowed_books") or ()),
                    }
                    if entry["entry_kind"] == "policy"
                    else {}
                ),
                "raw_hit_count": len(hits),
                "locator_hits": list(merge_hanchi_locator_hits(hits)),
                "query_lineage": [
                    {
                        "mode": str(query["mode"]),
                        "subject_term": str(query["subject_term"]),
                        "topic_term": query.get("topic_term"),
                        "result_role": str(query["result_role"]),
                    }
                    for query in plan.get("queries") or ()
                    if str(query["entry_ref"]) == entry_ref
                ],
                "retrieval_status": "completed_with_filtered_locators" if hits else "completed_no_filtered_locator",
            }
        )
    return {
        "schema_version": BATCH_RESULT_SCHEMA_VERSION,
        "ruler": str(plan["ruler"]),
        "dynasty_scope": str(plan["dynasty_scope"]),
        "request_count": request_count,
        "query_fanout_reuse_count": query_fanout_reuse_count,
        "selected_person_count": int(plan["selected_person_count"]),
        "deferred_people": list(plan.get("deferred_people") or ()),
        "entry_results": entry_results,
        "transport_declarations": {
            "serial": True,
            "returned_form_state_reused": True,
            "credentials_persisted": False,
            "cookies_persisted": False,
            "official_retrieval_route": "hanchi_post",
            "google_used_for_retrieval": False,
        },
    }


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> bool:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成汉籍库影子定位检索方案")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--curl-template", type=Path)
    parser.add_argument("--allowed-book", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("汉籍库检索规划输入必须是 object")
    if isinstance(payload.get("people"), list):
        result = build_hanchi_batch_search_plan(
            ruler=str(payload.get("ruler") or ""),
            dynasty_scope=str(payload.get("dynasty_scope") or ""),
            people=payload["people"],
            policy_entries=payload.get("policy_entries") or (),
            max_person_entries=int(payload.get("max_person_entries") or 12),
        )
        if args.curl_template:
            template = load_hanchi_curl_template(args.curl_template)
            query_summaries: list[dict[str, Any]] = []

            def submit(
                query: Mapping[str, Any], state: Mapping[str, Any]
            ) -> Mapping[str, Any]:
                parsed = submit_hanchi_post_query(
                    template,
                    query,
                    allowed_books=(
                        query.get("allowed_books")
                        or args.allowed_book
                        or payload.get("allowed_books")
                        or ()
                    ),
                    form_state=state,
                )
                query_summaries.append(
                    {
                        "entry_ref": str(query["entry_ref"]),
                        "mode": str(query["mode"]),
                        "subject_term": str(query["subject_term"]),
                        "book_count": parsed["book_count"],
                        "chapter_count": parsed["chapter_count"],
                        "hit_count": parsed["hit_count"],
                        "result_status": parsed["result_status"],
                        "network_request_count": parsed["network_request_count"],
                    }
                )
                return {
                    "hits": parsed["locator_hits"],
                    "form_state": parsed["form_state"],
                }

            result = execute_hanchi_batch_plan(result, submit_query=submit)
            result["query_summaries"] = query_summaries
    else:
        if args.curl_template:
            raise ValueError("汉籍库 POST 执行要求批量输入，以落实12人总上限")
        result = build_hanchi_search_plan(
            subject_name=str(payload.get("subject_name") or ""),
            observed_simple_hits=payload.get("observed_simple_hits") or {},
            dynasty_scope=str(payload.get("dynasty_scope") or ""),
            broad_topics=payload.get("broad_topics") or (),
            professional_anchors=payload.get("professional_anchors") or (),
            professional_distance_upper=int(payload.get("professional_distance_upper") or 20),
        )
    _atomic_json(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
