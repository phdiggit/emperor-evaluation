from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.source_ingest import parse_wikisource_fixture

FIXTURE = ROOT / "tests" / "fixtures" / "wikisource" / "shiji_juan008_minimal.html"
SOURCE_URL = "https://zh.wikisource.org/wiki/史記/卷008"
CAPTURED_AT = "2026-06-24T00:00:00Z"
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


def parse_fixture():
    return parse_wikisource_fixture(FIXTURE, source_url=SOURCE_URL, captured_at=CAPTURED_AT)


def test_parser_extracts_ordered_passages_from_fixture() -> None:
    result = parse_fixture()

    assert result.snapshot.source_host == "zh.wikisource.org"
    assert result.snapshot.source_title == "史記/卷008"
    assert result.snapshot.source_url == SOURCE_URL
    assert [passage.seq for passage in result.passages] == [1, 2]
    assert [passage.location for passage in result.passages] == ["p[1]", "p[2]"]


def test_passage_text_fields_and_hashes_are_present_and_stable() -> None:
    first = parse_fixture()
    second = parse_fixture()

    assert first.snapshot.raw_hash == second.snapshot.raw_hash
    assert first.normalized_hash == second.normalized_hash
    assert len(first.snapshot.raw_hash) == 64
    assert len(first.normalized_hash) == 64
    for passage in first.passages:
        assert passage.raw_text
        assert passage.norm_text
        assert passage.token_text
        assert passage.source_title == "史記/卷008"
        assert passage.source_url == SOURCE_URL


def test_normalizer_removes_fixture_noise_without_simplifying_traditional_text() -> None:
    result = parse_fixture()
    combined_raw = "\n".join(passage.raw_text for passage in result.passages)
    combined_norm = "\n".join(passage.norm_text for passage in result.passages)

    assert "navigation noise" not in combined_raw
    assert "目录噪音" not in combined_raw
    assert "编辑" not in combined_raw
    assert "Retrieved from" not in combined_raw
    assert "［1］" not in combined_norm
    assert "沛豐邑" in combined_norm
    assert result.passages[1].norm_text == "良數以太公兵法說沛公，沛公善之。"


def test_parser_does_not_access_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in fixture parser tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    result = parse_fixture()

    assert len(result.passages) == 2


def test_parser_does_not_modify_forbidden_repo_paths() -> None:
    forbidden_paths = [
        ROOT / "data",
        ROOT / "archive" / "data",
        ROOT / "db" / "schema.sql",
        ROOT / "db" / "postgres",
        ROOT / "exports" / "markdown_views",
    ]
    before = {path: _mtime(path) for path in forbidden_paths}

    parse_fixture()

    after = {path: _mtime(path) for path in forbidden_paths}
    assert after == before


def test_output_contains_no_scoring_or_evidence_card_fields() -> None:
    result = parse_fixture()
    payload = asdict(result)

    assert not _contains_forbidden_key(payload)


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_OUTPUT_KEYS or _contains_forbidden_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False
