from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_passage_fulltext_backfill as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_source_cache(cache_root: Path, source_key: str, text: str) -> None:
    text_path, meta_path = tool.source_cache_paths(cache_root, source_key)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    write_json(meta_path, {"source_key": source_key})


def test_build_backfill_plan_keeps_full_slice_text(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.final.json"
    full_text = "朱元璋命常遇春北征。" + ("授权背景。" * 60) + "后克州郡、破敌军。"
    write_json(
        candidates_path,
        {
            "candidate_slices": [
                {
                    "slice_code": "SLI-CYC",
                    "document_code": "DOC-1",
                    "locator": "chars:1-300",
                    "text": full_text,
                }
            ]
        },
    )

    plan = tool.build_backfill_plan(
        [
            {
                "passage_id": 1,
                "emperor_name": "朱元璋",
                "source_pack_code": "SPK-1",
                "passage_code": "SPK-1::PAS-1",
                "raw_passage_code": "PAS-1",
                "document_code": "SPK-1::DOC-1",
                "locator": "chars:1-120",
                "raw_text": full_text[:120],
                "passage_payload": {"slice_code": "SLI-CYC", "quote": full_text[:120]},
                "candidates_path": str(candidates_path),
            }
        ]
    )

    assert plan["skipped_counts"] == {}
    assert plan["planned"][0]["new_chars"] == len(full_text)
    assert plan["planned"][0]["raw_text"] == full_text
    assert plan["planned"][0]["passage_payload"]["quote"] == full_text
    assert plan["planned"][0]["passage_payload"]["raw_text"] == full_text


def test_build_backfill_plan_skips_non_prefix_text(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.final.json"
    write_json(
        candidates_path,
        {"candidate_slices": [{"slice_code": "SLI-1", "text": "完整原文后续很长。"}]},
    )

    plan = tool.build_backfill_plan(
        [
            {
                "passage_id": 1,
                "raw_text": "另一段文字",
                "passage_payload": {"slice_code": "SLI-1"},
                "candidates_path": str(candidates_path),
            }
        ]
    )

    assert plan["planned"] == []
    assert plan["skipped_counts"] == {"not_prefix_or_not_longer": 1}


def test_build_backfill_plan_uses_target_fallback_candidates(tmp_path: Path, monkeypatch) -> None:
    missing_primary = tmp_path / "missing" / "candidates.final.json"
    fallback = tmp_path / "fallback" / "candidates.final.json"
    full_text = "刘邦命韩信北击魏。" + ("中间战事。" * 40) + "遂定魏地。"
    write_json(fallback, {"candidate_slices": [{"slice_code": "SLI-HX", "text": full_text}]})
    monkeypatch.setattr(tool, "fallback_candidate_paths", lambda target_code: [fallback])

    plan = tool.build_backfill_plan(
        [
            {
                "passage_id": 1,
                "target_code": "TGT-LB",
                "raw_text": full_text[:120],
                "passage_payload": {"slice_code": "SLI-HX"},
                "candidates_path": str(missing_primary),
            }
        ]
    )

    assert plan["planned"][0]["candidates_path"] == str(fallback)
    assert plan["planned"][0]["raw_text"] == full_text


def test_build_backfill_plan_uses_document_cache_locator_when_candidate_slice_missing(tmp_path: Path) -> None:
    cache_root = tmp_path / "source_cache"
    page_text = "史記卷首。" + ("南越王尉佗者，真定人也。" * 30) + "佗即击并桂林、象郡。"
    source_key = "wikisource:史記/卷113"
    write_source_cache(cache_root, source_key, page_text)
    full_text = page_text[5:261]

    plan = tool.build_backfill_plan(
        [
            {
                "passage_id": 1,
                "raw_text": full_text[:120],
                "locator": "chars:5-260",
                "passage_payload": {"slice_code": "SLI-MISSING"},
                "candidates_path": str(tmp_path / "candidates.final.json"),
                "document_title": "史記/卷113",
            }
        ],
        source_cache_root=cache_root,
    )

    assert plan["skipped_counts"] == {}
    assert plan["planned"][0]["candidates_path"] == f"source_cache:{source_key}"
    assert plan["planned"][0]["raw_text"] == full_text


def test_build_backfill_plan_derives_wikisource_title_from_url_for_cache(tmp_path: Path) -> None:
    cache_root = tmp_path / "source_cache"
    page_text = "卷首。" + ("太祖使夏侯渊督军。" * 40) + "陇右平。"
    source_key = "wikisource:三國志/卷09"
    write_source_cache(cache_root, source_key, page_text)
    full_text = page_text[3:361]

    plan = tool.build_backfill_plan(
        [
            {
                "passage_id": 1,
                "raw_text": full_text[:120],
                "locator": "chars:3-360",
                "passage_payload": {"slice_code": "SLI-SGZ"},
                "candidates_path": str(tmp_path / "missing.json"),
                "document_title": "三國志 卷九 魏書·諸夏侯曹傳",
                "canon_url": "https://zh.wikisource.org/wiki/%E4%B8%89%E5%9C%8B%E5%BF%97/%E5%8D%B709",
            }
        ],
        source_cache_root=cache_root,
    )

    assert plan["skipped_counts"] == {}
    assert plan["planned"][0]["candidates_path"] == f"source_cache:{source_key}"
    assert plan["planned"][0]["raw_text"] == full_text


def test_document_cache_locator_fallback_prefers_longest_safe_window(tmp_path: Path) -> None:
    cache_root = tmp_path / "source_cache"
    page_text = "卷首。" + ("太祖使李靖出征。" * 30) + "捷"
    source_key = "wikisource:舊唐書/卷067"
    write_source_cache(cache_root, source_key, page_text)
    shorter = page_text[3:180].strip()
    longer = page_text[3:181].strip()

    full_text, used_key = tool.full_text_from_document_cache(
        {
            "raw_text": shorter[:120],
            "locator": "chars:3-180",
            "document_title": "舊唐書/卷067",
        },
        source_cache_root=cache_root,
    )

    assert used_key == source_key
    assert full_text == longer
    assert len(full_text) == len(shorter) + 1
