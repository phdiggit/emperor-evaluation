from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.dev import retrieval_v2_source_candidates as tool


def sample_task() -> dict:
    return {
        "job_code": "JOB-I5B-LIYUAN-DELEGATION-FIXTURE",
        "target_code": "TGT-I5B-9909F280EEC3",
        "emperor_name": "李渊",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "delegation",
        "target_profile": {
            "primary_name": "李渊",
            "aliases": ["李渊", "高祖"],
            "must_check_titles": ["秦王", "齐王"],
        },
        "rule": {
            "rule_code": "delegation",
            "keywords": ["命", "授", "总管", "元帅", "便宜", "留守"],
        },
        "secondary_rule_candidates": ["appointment_trust", "team_building"],
        "object_seeds": [
            {"name": "李世民", "aliases": [{"alias": "秦王", "strength": "medium"}, {"alias": "太宗", "strength": "weak"}]},
            {"name": "李元吉", "aliases": [{"alias": "齐王", "strength": "medium"}, "元吉"]},
        ],
        "source_documents": [
            {
                "document_code": "DOC-JTS-001",
                "title": "旧唐书/卷1",
                "source_kind": "primary_source",
                "text": "高祖命秦王为西讨元帅征之。秋七月，以元吉为镇北将军、太原留守。",
            }
        ],
    }


def test_select_candidate_slices_matches_aliases_and_rule_terms() -> None:
    task = sample_task()
    docs = [
        {
            "document_code": "DOC-JTS-001",
            "text": task["source_documents"][0]["text"],
        }
    ]

    rows = tool.select_candidate_slices(task, docs, context_chars=40, max_slices_per_object=3)

    assert {row["object_name"] for row in rows} == {"李世民", "李元吉"}
    lsm = next(row for row in rows if row["object_name"] == "李世民")
    lyj = next(row for row in rows if row["object_name"] == "李元吉")
    assert "秦王" in lsm["matched_aliases"]
    assert lsm["matched_alias_strengths"]["秦王"] == "medium"
    assert {"命", "元帅"} <= set(lsm["matched_rule_terms"])
    assert "military_delegate" in lsm["matched_role_families"]
    assert "元吉" in lyj["matched_aliases"]
    assert {"留守"} <= set(lyj["matched_rule_terms"])


def test_build_candidates_reports_slice_coverage() -> None:
    result = tool.build_candidates(sample_task(), cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["stats"]["documents"] == 1
    assert result["stats"]["candidate_slices"] == 2
    assert result["coverage"]["objects_without_slices"] == []
    assert result["coverage"]["object_slice_counts"] == {"李世民": 1, "李元吉": 1}
    assert result["coverage_matrix"]["rule_code"] == "delegation"
    gap_types = {gap["gap_type"] for gap in result["coverage_gaps"]}
    assert "civil_undercoverage" in gap_types
    assert "negative_undercoverage" in gap_types


def test_build_candidates_compacts_overlapping_slices() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "李世民", "aliases": [{"alias": "秦王", "strength": "medium"}, "李世民"]}]
    task["source_documents"][0]["text"] = "高祖命秦王为西讨元帅征之。数日后，高祖又命李世民总管诸军。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1, context_chars=20)

    assert result["stats"]["raw_candidate_slices"] >= 2
    assert result["stats"]["candidate_slices"] == 1
    assert result["stats"]["candidate_compaction_removed_slices"] >= 1
    row = result["candidate_slices"][0]
    assert "秦王" in row["matched_aliases"]
    assert "李世民" in row["matched_aliases"]
    assert len(row["merged_from_slice_codes"]) >= 2


def test_weak_alias_only_slice_reports_noise_gap() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "某臣", "aliases": [{"alias": "威侯", "strength": "weak"}]}]
    task["source_documents"][0]["text"] = "高祖命威侯为行军总管。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["candidate_slices"][0]["weak_alias_only"] is True
    assert result["candidate_slices"][0]["matched_alias_strengths"] == {"威侯": "weak"}
    assert any(gap["gap_type"] == "weak_alias_noise" for gap in result["coverage_gaps"])


def test_object_seed_name_can_be_inferred_from_alias_text() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"aliases": [{"text": "赵普", "strength": "strong"}, {"text": "宰相", "strength": "medium"}]}]
    task["source_documents"][0]["text"] = "太祖命赵普为相，专委政事。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["candidate_slices"][0]["object_name"] == "赵普"
    assert result["coverage"]["object_slice_counts"] == {"赵普": 1}


def test_candidate_slices_match_simplified_text_from_traditional_seed() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "房玄齡", "aliases": [{"alias": "左僕射", "strength": "medium"}]}]
    task["source_documents"][0]["text"] = "太宗命房玄龄参预机务，授左仆射。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["coverage"]["objects_without_slices"] == []
    row = result["candidate_slices"][0]
    assert row["object_name"] == "房玄齡"
    assert "房玄龄" in row["matched_aliases"]
    assert "左仆射" in row["matched_aliases"]


def test_build_candidates_skips_root_pages_used_only_for_discovery() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "荀彧"}]
    task["source_documents"] = [
        {
            "document_code": "DOC-ROOT",
            "title": "三國志",
            "source_kind": "wikisource_root_page",
            "text": "曹操命荀彧为司马。",
        },
        {
            "document_code": "DOC-SGZ-010",
            "title": "三國志/卷10",
            "source_kind": "wikisource_page",
            "text": "太祖命荀彧为司马，委以军国之事。",
        },
    ]

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["stats"]["skipped_source_documents"] == 1
    assert result["skipped_source_documents"][0]["document_code"] == "DOC-ROOT"
    assert result["stats"]["candidate_slices"] == 1
    assert result["candidate_slices"][0]["document_code"] == "DOC-SGZ-010"


def test_build_candidates_skips_source_root_mismatch_even_without_presearch() -> None:
    task = copy.deepcopy(sample_task())
    task["source_strategy"] = {"source_hints": ["舊唐書"], "source_root_filter_required": True}
    task["object_seeds"] = [{"name": "房玄齡"}]
    task["source_documents"] = [
        {
            "document_code": "DOC-WRONG",
            "title": "舊五代史/卷145",
            "source_kind": "wikisource_page",
            "text": "太宗命房玄齡为相。",
        },
        {
            "document_code": "DOC-RIGHT",
            "title": "舊唐書/卷66",
            "source_kind": "wikisource_page",
            "text": "太宗命房玄齡参预机务，授左僕射。",
        },
    ]

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["stats"]["skipped_source_documents"] == 1
    assert result["skipped_source_documents"][0]["reason"] == "source_root_mismatch"
    assert result["skipped_source_documents"][0]["allowed_source_roots"] == ["舊唐書"]
    assert result["stats"]["candidate_slices"] == 1
    assert result["candidate_slices"][0]["document_code"] == "DOC-RIGHT"


def test_build_candidates_allows_canonical_siku_volume_variant() -> None:
    task = copy.deepcopy(sample_task())
    task["source_strategy"] = {"source_hints": ["宋史"], "source_root_filter_required": True}
    task["object_seeds"] = [{"name": "夏竦"}]
    task["source_documents"] = [
        {
            "document_code": "DOC-SIKU",
            "title": "宋史(四庫全書本)/卷283",
            "source_kind": "wikisource_page",
            "text": "仁宗命夏竦经略陕西，委以边事。",
        }
    ]

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["stats"]["skipped_source_documents"] == 0
    assert result["stats"]["candidate_slices"] == 1
    assert result["candidate_slices"][0]["document_code"] == "DOC-SIKU"


def test_fetch_document_text_falls_back_to_url_when_wikisource_title_is_empty(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch_title(title: str, *, timeout: int) -> str:
        raise tool.RetrievalV2CandidateError(f"empty Wikisource page: {title}")

    def fake_request_text(url: str, *, timeout: int) -> str:
        assert url == "https://example.test/siku"
        return "<p>仁宗命夏竦经略陕西，委以边事。</p>"

    monkeypatch.setattr(tool, "fetch_wikisource_title", fake_fetch_title)
    monkeypatch.setattr(tool, "request_text", fake_request_text)

    text, meta = tool.fetch_document_text(
        {
            "title": "宋史(四庫全書本)/卷283",
            "wikisource_title": "宋史(四庫全書本)/卷283",
            "url": "https://example.test/siku",
        },
        cache_dir=tmp_path,
        timeout=1,
    )

    assert "仁宗命夏竦" in text
    assert meta["source_kind"] == "url_fallback"
    assert meta["fallback_url"] == "https://example.test/siku"


def test_cli_writes_candidates_and_prompt(tmp_path: Path) -> None:
    task_path = tmp_path / "task.json"
    output_path = tmp_path / "candidates.json"
    prompt_path = tmp_path / "prompt.md"
    task_path.write_text(json.dumps(sample_task(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(["--input", str(task_path), "--output", str(output_path), "--prompt-output", str(prompt_path)]) == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    prompt = prompt_path.read_text(encoding="utf-8")
    assert payload["candidate_slices"]
    assert "candidate_slices" in prompt
    assert "coverage_matrix" in prompt
    assert "primary_bindings" in prompt
    assert "secondary_binding_candidates" in prompt
    assert "不要联网" in prompt
    assert "mixed claim" in prompt
    assert "判读预算" in prompt
    assert "每个对象默认最多 2 个" in prompt
    assert "civil_undercoverage" in prompt
