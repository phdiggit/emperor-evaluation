from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable, Mapping

from scripts.source_ingest.normalizer import normalize_text


_FOOTNOTE_RE = re.compile(r"(?:\[\s*\d+\s*\]|［\s*\d+\s*］)")
_SIMPLIFIED_TO_TRADITIONAL = str.maketrans(
    {
        "为": "為",
        "丰": "豐",
        "乐": "樂",
        "书": "書",
        "于": "於",
        "亲": "親",
        "从": "從",
        "仓": "倉",
        "仪": "儀",
        "传": "傳",
        "刘": "劉",
        "勋": "勳",
        "号": "號",
        "后": "後",
        "复": "復",
        "实": "實",
        "庙": "廟",
        "异": "異",
        "张": "張",
        "录": "錄",
        "征": "徵",
        "数": "數",
        "旧": "舊",
        "汉": "漢",
        "济": "濟",
        "礼": "禮",
        "纂": "纂",
        "经": "經",
        "蓝": "藍",
        "诏": "詔",
        "说": "說",
        "请": "請",
        "论": "論",
        "谏": "諫",
        "谭": "譚",
        "阳": "陽",
        "韩": "韓",
        "魏": "魏",
        "与": "與",
        "罢": "罷",
        "诛": "誅",
    }
)

DEFAULT_LIMITATIONS = (
    "本 benchmark 只验证离线 fixture 的最低召回口径，不代表生产检索质量。",
    "字符与 ngram token 不能替代正式中文古文分词器。",
    "alias 只用于 query expansion，不改写 raw_text 或 norm_text。",
    "false positive 与 false negative 由每条 case 的 expected_passage_codes 显式暴露。",
)


@dataclass(frozen=True)
class SearchBenchmarkCase:
    query: str
    expected_passage_codes: set[str]


@dataclass(frozen=True)
class SearchBenchmarkResult:
    query: str
    matched_passage_codes: set[str]
    expected_passage_codes: set[str]
    missed: set[str]
    unexpected: set[str]


@dataclass(frozen=True)
class BenchmarkReport:
    results: tuple[SearchBenchmarkResult, ...]
    limitations: tuple[str, ...] = DEFAULT_LIMITATIONS

    @property
    def false_positive_queries(self) -> tuple[str, ...]:
        return tuple(result.query for result in self.results if result.unexpected)

    @property
    def false_negative_queries(self) -> tuple[str, ...]:
        return tuple(result.query for result in self.results if result.missed)

    @property
    def passed(self) -> bool:
        return not self.false_positive_queries and not self.false_negative_queries


def normalize_query(term: str) -> str:
    """Normalize benchmark query text without changing fixture source text."""
    normalized = normalize_text(_FOOTNOTE_RE.sub("", term))
    chars = []
    for char in normalized.translate(_SIMPLIFIED_TO_TRADITIONAL):
        category = unicodedata.category(char)
        if category[0] in {"C", "P", "S", "Z"}:
            continue
        chars.append(char)
    return "".join(chars)


def char_tokens(text: str) -> list[str]:
    return list(normalize_query(text))


def ngram_tokens(text: str, min_n: int = 2, max_n: int = 3) -> list[str]:
    if min_n < 1:
        raise ValueError("min_n must be >= 1")
    if max_n < min_n:
        raise ValueError("max_n must be >= min_n")

    chars = char_tokens(text)
    tokens: list[str] = []
    for size in range(min_n, max_n + 1):
        for start in range(0, len(chars) - size + 1):
            tokens.append("".join(chars[start : start + size]))
    return _unique(tokens)


def build_token_text(text: str, aliases: list[str] | None = None) -> str:
    tokens: list[str] = []
    tokens.extend(char_tokens(text))
    tokens.extend(ngram_tokens(text))
    if aliases:
        for alias in aliases:
            normalized_alias = normalize_query(alias)
            if normalized_alias:
                tokens.append(normalized_alias)
                tokens.extend(ngram_tokens(normalized_alias))
    return " ".join(_unique(tokens))


def evaluate_queries(
    passages: list[Mapping[str, Any]],
    queries: list[SearchBenchmarkCase],
) -> BenchmarkReport:
    indexed_passages = [_index_passage(passage) for passage in passages]
    results: list[SearchBenchmarkResult] = []

    for case in queries:
        query = normalize_query(case.query)
        matched = {
            passage["passage_code"]
            for passage in indexed_passages
            if query and (query in passage["searchable_text"] or query in passage["search_tokens"])
        }
        expected = set(case.expected_passage_codes)
        results.append(
            SearchBenchmarkResult(
                query=case.query,
                matched_passage_codes=matched,
                expected_passage_codes=expected,
                missed=expected - matched,
                unexpected=matched - expected,
            )
        )

    return BenchmarkReport(results=tuple(results))


def _index_passage(passage: Mapping[str, Any]) -> dict[str, Any]:
    raw_text = _required_str(passage, "raw_text")
    aliases = passage.get("aliases") or []
    if not isinstance(aliases, list):
        raise TypeError("aliases must be a list")
    token_text = build_token_text(raw_text, aliases=[str(alias) for alias in aliases])
    return {
        "passage_code": _required_str(passage, "passage_code"),
        "searchable_text": normalize_query(raw_text),
        "search_tokens": set(token_text.split()),
    }


def _required_str(passage: Mapping[str, Any], key: str) -> str:
    value = passage.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"passage must include non-empty {key}")
    return value


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
