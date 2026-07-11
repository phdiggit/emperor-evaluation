from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.dev import retrieval_v3_source_candidates as tool
from scripts.dev.retrieval_v3_public_ocr import extract_public_ocr_text


def test_extract_public_ocr_text_reads_shidian_router_paragraphs() -> None:
    paragraph = json.dumps(
        {"lines": [{"content": "秦王多有过失。"}, {"content": "太祖召还京师。"}]},
        ensure_ascii=False,
    )
    router = {"loaderData": {"book": {"paragraphList": [{"content": paragraph}]}}}
    html = f'<html><script>window._ROUTER_DATA = {json.dumps(router, ensure_ascii=False)}</script></html>'

    text, extractor = extract_public_ocr_text("https://www.shidianguji.com/book/x/chapter/y", html)

    assert text == "秦王多有过失。\n太祖召还京师。"
    assert extractor == "shidianguji_router_data"


def test_extract_public_ocr_text_marks_empty_shidian_page_shell() -> None:
    text, extractor = extract_public_ocr_text("https://www.shidianguji.com/book/x/chapter/y", "<html>title only</html>")

    assert text == ""
    assert extractor == "shidianguji_router_data_empty"


def sample_task() -> dict:
    return {
        "job_code": "JOB-I5B-LIYUAN-APPOINTMENT-DELEGATION-FIXTURE",
        "target_code": "TGT-I5B-9909F280EEC3",
        "emperor_name": "李渊",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "appointment_delegation",
        "target_profile": {
            "primary_name": "李渊",
            "aliases": ["李渊", "高祖"],
            "must_check_titles": ["秦王", "齐王"],
        },
        "rule": {
            "rule_code": "appointment_delegation",
            "keywords": ["命", "授", "总管", "元帅", "便宜", "留守"],
        },
        "secondary_rule_candidates": ["team_building"],
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


def test_select_candidate_slices_does_not_turn_site_ocr_into_a_review_gate() -> None:
    task = sample_task()
    docs = [
        {
            "document_code": "DOC-OCR",
            "text": "高祖命秦王为西讨元帅征之。",
            "ocr_requires_image_review": True,
        }
    ]

    rows = tool.select_candidate_slices(task, docs, context_chars=40, max_slices_per_object=3)

    assert rows
    assert all("ocr_requires_image_review" not in row for row in rows)


def test_select_candidate_slices_keeps_object_cache_documents_owner_scoped() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "李文忠"}, {"name": "沐英"}]
    docs = [
        {
            "document_code": "DOC-LWZ",
            "text": "太祖命李文忠督军事，李文忠克敌有功。",
            "object_source_cache": {"person_name": "李文忠"},
        },
        {
            "document_code": "DOC-MY",
            "text": "太祖命沐英征西番，沐英平定诸蛮。旁及李文忠旧事。",
            "object_source_cache": {"person_name": "沐英"},
        },
    ]

    rows = tool.select_candidate_slices(task, docs, context_chars=40, max_slices_per_object=4)

    assert {row["object_name"] for row in rows} == {"李文忠", "沐英"}
    assert all(row["document_code"] == "DOC-LWZ" for row in rows if row["object_name"] == "李文忠")
    assert all(row["document_code"] == "DOC-MY" for row in rows if row["object_name"] == "沐英")


def test_select_candidate_slices_keeps_wikisource_biography_section_boundary() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "沐英"}]
    docs = [
        {
            "document_code": "DOC-MY",
            "text": (
                "曾孙 胤𪟝 [ 编辑 ] 胤𪟝命守孤山，寇至战死。"
                "沐英 [ 编辑 ] 沐英字文英。太祖命沐英征西番，沐英平定诸蛮。"
                "下一人 [ 编辑 ] 下一人命守边。"
            ),
            "object_source_cache": {"person_name": "沐英"},
        }
    ]

    rows = tool.select_candidate_slices(task, docs, context_chars=80, max_slices_per_object=3)

    assert rows
    assert rows[0]["text"].startswith("沐英 [ 编辑 ]")
    assert "胤𪟝命守孤山" not in rows[0]["text"]


def test_build_candidates_reports_slice_coverage() -> None:
    result = tool.build_candidates(sample_task(), cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["stats"]["documents"] == 1
    assert result["stats"]["candidate_slices"] == 2
    assert result["coverage"]["objects_without_slices"] == []
    assert result["coverage"]["object_slice_counts"] == {"李世民": 1, "李元吉": 1}
    assert result["coverage_matrix"]["rule_code"] == "appointment_delegation"
    gap_types = {gap["gap_type"] for gap in result["coverage_gaps"]}
    assert "civil_undercoverage" in gap_types
    assert "negative_undercoverage" in gap_types


def test_delegation_chain_signal_outranks_disposition_noise() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "冯胜", "aliases": [{"alias": "宋国公", "strength": "medium"}]}]
    task["source_documents"][0]["text"] = (
        "宋国公冯胜有罪，坐党，后赐死。"
        "太祖命宋国公冯胜为征西将军，取甘肃，征扩廓帖木儿；冯胜克甘肃，追败元兵。"
    )

    rows = tool.select_candidate_slices(task, task["source_documents"], context_chars=24, max_slices_per_object=1)

    assert len(rows) == 1
    assert "征西将军" in rows[0]["text"]
    assert "克甘肃" in rows[0]["text"]
    assert rows[0]["slice_profile"]["has_full_delegation_chain"] is True


def test_slice_profile_marks_disposition_noise() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "李善长", "aliases": [{"alias": "韩国公", "strength": "medium"}]}]
    task["source_documents"][0]["text"] = (
        "太祖命有司治韩国公李善长罪，坐胡党，后伏诛。"
        "太祖命有司治韩国公罪，家属连坐。"
        "太祖命有司治韩国公有罪，下狱。"
        "太祖命有司治韩国公谋反，诛。"
    )

    rows = tool.select_candidate_slices(task, task["source_documents"], context_chars=12, max_slices_per_object=8)

    assert len(rows) >= 4
    assert all(row["slice_profile"]["disposition_noise_only"] for row in rows)


def test_dynamic_slice_budget_keeps_diverse_delegation_signals() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "冯胜", "aliases": [{"alias": "宋国公", "strength": "medium"}]}]
    task["source_documents"] = [
        {
            "document_code": "DOC-FULL",
            "title": "明史/卷1",
            "source_kind": "primary_source",
            "text": "太祖命宋国公冯胜为征西将军，取甘肃；冯胜克甘肃，追败元兵。",
        },
        {
            "document_code": "DOC-PARTIAL",
            "title": "明史/卷2",
            "source_kind": "primary_source",
            "text": "太祖又命宋国公镇边，统诸军。",
        },
        {
            "document_code": "DOC-NOISE",
            "title": "明史/卷3",
            "source_kind": "primary_source",
            "text": "宋国公冯胜坐事赐死。",
        },
    ]

    rows = tool.select_candidate_slices(task, task["source_documents"], context_chars=26, max_slices_per_object=8)

    assert len(rows) >= 2
    assert any(row["slice_profile"]["has_full_delegation_chain"] for row in rows)
    assert any(row["slice_profile"]["has_authority_task_chain"] and not row["slice_profile"]["has_full_delegation_chain"] for row in rows)
    assert any("克甘肃" in row["text"] for row in rows)


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


def test_candidate_slices_match_traditional_text_from_simplified_seed() -> None:
    task = copy.deepcopy(sample_task())
    task["object_seeds"] = [{"name": "陆贾", "aliases": []}]
    task["source_documents"][0]["text"] = "高祖命陸賈使南越，授尉佗印，因說以中國新定。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    assert result["coverage"]["objects_without_slices"] == []
    row = result["candidate_slices"][0]
    assert row["object_name"] == "陆贾"
    assert "陸賈" in row["matched_aliases"]


def test_item_wide_tolerate_terms_capture_attacked_talent_protection() -> None:
    task = copy.deepcopy(sample_task())
    task["rule_code"] = "i5b_item_wide"
    task["rule"] = {"rule_code": "i5b_item_wide", "keywords": []}
    task["coverage_matrix"] = {"rule_code": "i5b_item_wide", "role_families": []}
    task["object_seeds"] = [
        {
            "name": "陈平",
            "aliases": [{"alias": "陈平", "strength": "strong"}],
            "role_families": ["tolerate_talent_material"],
        }
    ]
    task["source_documents"][0]["text"] = "或言陈平盗嫂受金，高祖不疑，卒复用陈平。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    row = result["candidate_slices"][0]
    assert row["object_name"] == "陈平"
    assert "tolerate_talent_material" in row["matched_role_families"]
    assert {"盗嫂", "受金"} <= set(row["matched_rule_terms"])


def test_item_wide_material_terms_capture_cross_item_future_hint_signals() -> None:
    task = copy.deepcopy(sample_task())
    task["rule_code"] = "i5b_item_wide"
    task["rule"] = {"rule_code": "i5b_item_wide", "keywords": []}
    task["object_seeds"] = [{"name": "某臣", "aliases": [{"alias": "某臣", "strength": "strong"}]}]
    task["source_documents"][0]["text"] = "帝因边疆失地与徭役横征，问策某臣，遂罢兵议和班师。"

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    row = result["candidate_slices"][0]
    assert row["object_name"] == "某臣"
    assert {"边疆", "失地", "徭役", "横征", "问策", "罢兵", "议和", "班师"} & set(row["matched_rule_terms"])
    assert "future_power_character_hint" in row["matched_role_families"]
    assert row["slice_profile"]["has_item_wide_signal"] is True


def test_item_wide_material_terms_capture_negative_ad_power_abuse_without_case_terms() -> None:
    task = copy.deepcopy(sample_task())
    task["rule_code"] = "i5b_item_wide"
    task["rule"] = {"rule_code": "i5b_item_wide", "keywords": []}
    task["object_seeds"] = [{"name": "胡惟庸", "aliases": [{"alias": "胡惟庸", "strength": "strong"}]}]
    task["source_documents"][0]["text"] = (
        "帝宠任胡惟庸。胡惟庸专擅威福，内外封事有害己者辄匿闻，"
        "生杀黜陟或不奏径行，奔竞之徒多趋附。"
    )

    result = tool.build_candidates(task, cache_dir=Path("tmp/test-unused"), timeout=1)

    row = result["candidate_slices"][0]
    assert row["object_name"] == "胡惟庸"
    assert "appointment_delegation_material" in row["matched_role_families"]
    assert {"宠任", "专擅", "威福", "封事", "不奏", "径行"} <= set(row["matched_rule_terms"])
    assert row["slice_profile"]["has_negative_ad_power_abuse_signal"] is True
    assert {"宠任", "专擅", "威福"} <= set(row["slice_profile"]["negative_ad_power_abuse_terms"])
    assert "刘基" not in tool.NEGATIVE_AD_POWER_ABUSE_TERMS
    assert "总中书政" not in tool.NEGATIVE_AD_POWER_ABUSE_TERMS


def test_guarded_conditional_recall_overlay_requires_guard_terms() -> None:
    task = copy.deepcopy(sample_task())
    task["rule"] = {"rule_code": "appointment_delegation", "keywords": ["宠任"]}
    task["object_seeds"] = [{"name": "胡惟庸", "aliases": [{"alias": "胡惟庸", "strength": "strong"}]}]
    task["recall_term_overlays"] = [
        {
            "conditional_terms_not_injected": [
                {
                    "term": "谋反",
                    "policy_group": "disposition_risk",
                    "guard": {"requires_near_any": ["宠任", "专擅", "中书"]},
                },
                {
                    "term": "伏诛",
                    "policy_group": "disposition_risk",
                    "guard": {"requires_near_any": ["宠任", "专擅", "中书"]},
                },
            ]
        }
    ]
    task["source_documents"][0]["text"] = "帝宠任胡惟庸，惟庸专擅中书，后谋反伏诛。"

    rows = tool.select_candidate_slices(task, task["source_documents"], context_chars=32, max_slices_per_object=3)

    assert len(rows) == 1
    assert {"谋反", "伏诛"} <= set(rows[0]["matched_rule_terms"])
    assert rows[0]["matched_conditional_recall_terms"] == ["谋反", "伏诛"]


def test_guarded_conditional_recall_overlay_does_not_match_without_guard_terms() -> None:
    task = copy.deepcopy(sample_task())
    task["rule"] = {"rule_code": "appointment_delegation", "keywords": ["宠任"]}
    task["object_seeds"] = [{"name": "胡惟庸", "aliases": [{"alias": "胡惟庸", "strength": "strong"}]}]
    task["recall_term_overlays"] = [
        {
            "conditional_terms_not_injected": [
                {
                    "term": "谋反",
                    "policy_group": "disposition_risk",
                    "guard": {"requires_near_any": ["宠任", "专擅", "中书"]},
                }
            ]
        }
    ]
    task["source_documents"][0]["text"] = "胡惟庸谋反伏诛。"

    rows = tool.select_candidate_slices(task, task["source_documents"], context_chars=32, max_slices_per_object=3)

    assert rows == []


def test_guarded_conditional_recall_overlay_requires_nearby_nonself_guard() -> None:
    task = copy.deepcopy(sample_task())
    task["rule"] = {"rule_code": "appointment_delegation", "keywords": ["宠任"]}
    task["object_seeds"] = [{"name": "胡惟庸", "aliases": [{"alias": "胡惟庸", "strength": "strong"}]}]
    task["recall_term_overlays"] = [
        {
            "conditional_terms_not_injected": [
                {
                    "term": "其党",
                    "policy_group": "disposition_risk",
                    "guard": {"requires_near_any": ["其党", "党"]},
                },
                {
                    "term": "谋反",
                    "policy_group": "disposition_risk",
                    "guard": {"requires_near_any": ["丞相"]},
                },
            ]
        }
    ]
    task["source_documents"][0]["text"] = (
        "丞相论事甚详，群臣退。"
        "其后诏书往复，百官议礼，州县奏报，仓储户籍，河渠学校，文字相续。"
        "又命有司详定礼制，修城浚渠，赈恤流民，清理逋赋，诸司各具奏牍。"
        "胡惟庸某日谋反。又言其党。"
    )

    rows = tool.select_candidate_slices(task, task["source_documents"], context_chars=80, max_slices_per_object=3)

    assert rows == []


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
        raise tool.RetrievalV3CandidateError(f"empty Wikisource page: {title}")

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


def test_fetch_document_text_uses_explicit_public_ocr_url_without_wikisource_probe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tool, "fetch_wikisource_title", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no Wikisource probe")))
    monkeypatch.setattr(tool, "request_text", lambda url, *, timeout: "<p>鲁王一打死火者二名。</p>")

    text, meta = tool.fetch_document_text(
        {
            "title": "御制纪非录",
            "url": "https://example.test/jifeilu",
            "source_kind": "public_ocr_page",
            "fetch_mode": "url",
        },
        cache_dir=tmp_path,
        timeout=1,
    )

    assert "鲁王" in text
    assert meta["source_kind"] == "url"


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
    assert "拆成多条原子 claim" in prompt
    assert "判读预算" in prompt
    assert "每个对象默认最多 2 个" in prompt
    assert "civil_undercoverage" in prompt
