from __future__ import annotations

from dataclasses import asdict
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.source_ingest.normalizer import normalize_text
from scripts.source_ingest.search_benchmark import (
    BenchmarkReport,
    SearchBenchmarkCase,
    build_token_text,
    char_tokens,
    evaluate_queries,
    ngram_tokens,
    normalize_query,
)


FIXTURE = ROOT / "tests" / "fixtures" / "source_search" / "classical_chinese_passages.json"
FORBIDDEN_OUTPUT_KEYS = {
    "score",
    "rank",
    "evidence_strength",
    "final_grade",
    "final_score",
    "candidate_strength",
    "leaderboard",
    "total_ranking",
}


def test_single_character_queries_recall_expected_passages() -> None:
    report = evaluate_queries(
        _load_passages(),
        [
            SearchBenchmarkCase(query="沛", expected_passage_codes={"bench-shiji-008-p0001", "bench-shiji-008-p0002"}),
            SearchBenchmarkCase(query="祀", expected_passage_codes={"bench-ritual-noise-p0001"}),
        ],
    )

    _assert_report_passed(report)


def test_two_character_queries_recall_expected_passages() -> None:
    report = evaluate_queries(
        _load_passages(),
        [
            SearchBenchmarkCase(query="沛丰", expected_passage_codes={"bench-shiji-008-p0001"}),
            SearchBenchmarkCase(query="复碑", expected_passage_codes={"bench-zizhi-weizheng-p0001"}),
            SearchBenchmarkCase(query="胡蓝", expected_passage_codes={"bench-mingshi-taizu-p0001"}),
        ],
    )

    _assert_report_passed(report)


def test_long_terms_and_person_aliases_recall_expected_passages() -> None:
    report = evaluate_queries(
        _load_passages(),
        [
            SearchBenchmarkCase(query="中阳里", expected_passage_codes={"bench-shiji-008-p0001"}),
            SearchBenchmarkCase(query="太公兵法", expected_passage_codes={"bench-shiji-008-p0002"}),
            SearchBenchmarkCase(query="刘邦", expected_passage_codes={"bench-shiji-008-p0001"}),
            SearchBenchmarkCase(query="唐太宗", expected_passage_codes={"bench-zizhi-weizheng-p0001"}),
            SearchBenchmarkCase(query="明实录", expected_passage_codes={"bench-mingshilu-hongwu-p0001"}),
        ],
    )

    _assert_report_passed(report)


def test_query_alias_expands_search_without_rewriting_source_text() -> None:
    passage = _passage("bench-shiji-008-p0001")
    norm_text = normalize_text(passage["raw_text"])

    assert "刘邦" not in passage["raw_text"]
    assert "刘邦" not in norm_text
    assert "劉邦" in build_token_text(passage["raw_text"], aliases=passage["aliases"]).split()

    report = evaluate_queries(
        [passage],
        [SearchBenchmarkCase(query="刘邦", expected_passage_codes={"bench-shiji-008-p0001"})],
    )

    _assert_report_passed(report)


def test_fixture_preserves_traditional_source_text() -> None:
    passages = _load_passages()

    assert _passage("bench-houhan-liuxiu-p0001")["raw_text"].startswith("劉秀")
    assert "刘秀" not in _passage("bench-houhan-liuxiu-p0001")["raw_text"]
    assert "沛豐邑" in _passage("bench-shiji-008-p0001")["raw_text"]
    assert all("expected_hits" in passage for passage in passages)


def test_spacing_fullwidth_space_punctuation_and_footnotes_do_not_block_query_normalization() -> None:
    assert normalize_query(" 沛　豐［1］ ") == "沛豐"
    assert normalize_query("禮官奏曰：郊祀［23］") == "禮官奏曰郊祀"

    report = evaluate_queries(
        _load_passages(),
        [
            SearchBenchmarkCase(query=" 沛　豐［1］ ", expected_passage_codes={"bench-shiji-008-p0001"}),
            SearchBenchmarkCase(query="礼官［23］", expected_passage_codes={"bench-ritual-noise-p0001"}),
        ],
    )

    _assert_report_passed(report)


def test_token_helpers_are_character_and_ngram_based_not_final_segmentation() -> None:
    assert char_tokens("魏征") == ["魏", "徵"]
    assert ngram_tokens("中陽里") == ["中陽", "陽里", "中陽里"]
    assert "太公兵法" not in ngram_tokens("太公兵法")
    assert "太公兵法" in normalize_query("太公兵法")


def test_unrelated_query_is_missed_without_false_positive() -> None:
    report = evaluate_queries(
        _load_passages(),
        [
            SearchBenchmarkCase(query="韓信", expected_passage_codes=set()),
            SearchBenchmarkCase(query="朱棣", expected_passage_codes=set()),
        ],
    )

    _assert_report_passed(report)


def test_benchmark_does_not_access_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in source search benchmark tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    report = evaluate_queries(
        _load_passages(),
        [SearchBenchmarkCase(query="光武", expected_passage_codes={"bench-houhan-liuxiu-p0001"})],
    )

    _assert_report_passed(report)


def test_benchmark_does_not_modify_forbidden_repo_paths() -> None:
    forbidden_paths = [
        ROOT / "data",
        ROOT / "archive" / "data",
        ROOT / "db",
        ROOT / "exports" / "markdown_views",
    ]
    before = {path: _mtime(path) for path in forbidden_paths}

    report = evaluate_queries(
        _load_passages(),
        [SearchBenchmarkCase(query="洪武", expected_passage_codes={"bench-mingshilu-hongwu-p0001"})],
    )

    after = {path: _mtime(path) for path in forbidden_paths}
    _assert_report_passed(report)
    assert after == before


def test_report_output_contains_no_scoring_or_evidence_card_fields() -> None:
    report = evaluate_queries(
        _load_passages(),
        [SearchBenchmarkCase(query="桓谭", expected_passage_codes={"bench-houhan-hanxin-p0001"})],
    )
    payload = asdict(report)

    assert not _contains_forbidden_key(payload)


def test_report_exposes_false_positive_and_false_negative_sets() -> None:
    report = evaluate_queries(
        _load_passages(),
        [
            SearchBenchmarkCase(query="祖", expected_passage_codes=set()),
            SearchBenchmarkCase(query="不存在", expected_passage_codes={"bench-shiji-008-p0001"}),
        ],
    )
    first, second = report.results

    assert isinstance(report, BenchmarkReport)
    assert first.unexpected
    assert second.missed == {"bench-shiji-008-p0001"}
    assert report.false_positive_queries == ("祖",)
    assert report.false_negative_queries == ("不存在",)
    assert not report.passed
    assert any("false positive" in limitation for limitation in report.limitations)
    assert any("false negative" in limitation for limitation in report.limitations)


def _load_passages() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _passage(passage_code: str) -> dict[str, object]:
    for passage in _load_passages():
        if passage["passage_code"] == passage_code:
            return passage
    raise AssertionError(f"missing fixture passage: {passage_code}")


def _assert_report_passed(report: BenchmarkReport) -> None:
    assert report.passed
    assert report.false_positive_queries == ()
    assert report.false_negative_queries == ()
    assert all(not result.missed and not result.unexpected for result in report.results)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_OUTPUT_KEYS or _contains_forbidden_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    if isinstance(value, tuple):
        return any(_contains_forbidden_key(child) for child in value)
    if isinstance(value, set):
        return any(_contains_forbidden_key(child) for child in value)
    return False
