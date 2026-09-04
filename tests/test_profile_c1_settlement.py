from __future__ import annotations

from pathlib import Path

from emperor_v4.evaluation.profile_c1_verifier import _cached_text, verify


ROOT = Path(__file__).resolve().parents[1]


def test_c1_formal_settlement_passes_semantic_and_structural_gates() -> None:
    result = verify(ROOT)
    assert result["status"] == "PASS"
    assert result["unresolved_count"] == 0
    assert result["scoring_parent_count"] > 0


def test_c1_source_text_cache_reads_each_file_once(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    source.write_text("first", encoding="utf-8")
    original_read_text = Path.read_text
    read_count = 0

    def counting_read_text(path: Path, *args, **kwargs) -> str:
        nonlocal read_count
        if path == source:
            read_count += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    cache: dict[Path, str] = {}

    assert _cached_text(source, cache) == "first"
    source.write_text("second", encoding="utf-8")
    assert _cached_text(source, cache) == "first"
    assert read_count == 1
