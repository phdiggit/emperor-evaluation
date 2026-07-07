from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_recall_term_sampler as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def candidate_payload(emperor: str, object_name: str, text: str, terms: list[str]) -> dict:
    return {
        "task_identity": {"emperor_name": emperor, "capture_profile": "personnel_political_wide"},
        "candidate_slices": [
            {
                "slice_code": f"SLI-{emperor}-{object_name}",
                "document_code": f"DOC-{emperor}",
                "object_name": object_name,
                "matched_rule_terms": terms,
                "matched_role_families": ["appointment_delegation_material"],
                "text": text,
            }
        ],
    }


def candidate_payload_rows(emperor: str, rows: list[dict]) -> dict:
    return {
        "task_identity": {"emperor_name": emperor, "capture_profile": "personnel_political_wide"},
        "candidate_slices": rows,
    }


def test_recall_term_sampler_promotes_generic_terms_and_rejects_case_terms(tmp_path: Path) -> None:
    paths = []
    rows = [
        candidate_payload("朱元璋", "胡惟庸", "帝宠任胡惟庸，惟庸专擅威福，封事匿闻。刘基尝言不可。", ["宠任", "专擅", "威福", "刘基"]),
        candidate_payload("唐玄宗", "李林甫", "帝宠任李林甫，林甫专擅威福，壅蔽言路。", ["宠任", "专擅", "威福"]),
        candidate_payload("宋太祖", "赵普", "上宠任赵普，普久居相位，或专擅威福。", ["宠任", "专擅", "威福"]),
        candidate_payload("明太祖", "某臣", "某臣总中书政，语涉个案，不应入长期词表。", ["总中书政"]),
    ]
    for index, payload in enumerate(rows):
        path = tmp_path / f"run-{index}" / "candidates.final.json"
        write_json(path, payload)
        paths.append(path)

    report = tool.build_report(
        candidates_paths=paths,
        min_chars=2,
        max_chars=4,
        include_text_ngrams=False,
        include_candidate_ab=False,
        min_support=1,
        include_case_terms=True,
        top=0,
    )

    by_term = {row["term"]: row for row in report["terms"]}
    assert by_term["专擅"]["tier"] == "core_term"
    assert by_term["威福"]["target_diversity"] == 3
    assert by_term["宠任"]["object_diversity"] == 3
    assert by_term["刘基"]["tier"] == "reject_term"
    assert "case_term_blocklist" in by_term["刘基"]["rejection_reasons"]
    assert by_term["总中书政"]["tier"] == "reject_term"
    assert tool.term_rejection_reasons("信曰", []) == ["grammar_fragment_not_profile_term"]
    assert "office_title_not_long_term_profile_term" in tool.term_rejection_reasons("征西将军", [])


def test_source_ab_report_summarizes_overlay_term_changes(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    overlay_path = tmp_path / "overlay.json"
    write_json(
        base_path,
        candidate_payload_rows(
            "朱元璋",
            [
                {
                    "slice_code": "SLI-1",
                    "document_code": "DOC-1",
                    "object_name": "胡惟庸",
                    "matched_rule_terms": ["宠任"],
                    "matched_role_families": ["appointment_delegation_material"],
                    "text": "帝宠任胡惟庸，惟庸专擅中书。",
                }
            ],
        ),
    )
    write_json(
        overlay_path,
        candidate_payload_rows(
            "朱元璋",
            [
                {
                    "slice_code": "SLI-1",
                    "document_code": "DOC-1",
                    "object_name": "胡惟庸",
                    "matched_rule_terms": ["宠任", "谋反"],
                    "matched_role_families": ["appointment_delegation_material"],
                    "text": "帝宠任胡惟庸，惟庸专擅中书。",
                },
                {
                    "slice_code": "SLI-2",
                    "document_code": "DOC-2",
                    "object_name": "蓝玉",
                    "matched_rule_terms": ["伏诛"],
                    "matched_role_families": ["appointment_delegation_material"],
                    "text": "蓝玉谋反，伏诛。",
                },
            ],
        ),
    )

    report = tool.build_source_ab_report(
        base_candidates_path=base_path,
        overlay_candidates_path=overlay_path,
        accepted_terms=["谋反", "伏诛"],
    )

    assert report["safety"]["writes_db"] is False
    assert report["summary"]["slice_count_delta"] == 1
    assert report["summary"]["added_slice_count"] == 1
    assert report["summary"]["changed_term_slice_count"] == 1
    assert report["summary"]["new_accepted_term_hits"] == {"伏诛": 1, "谋反": 1}
    policy_by_term = {row["term"]: row for row in report["term_policy_recommendations"]}
    assert policy_by_term["谋反"]["profile_action"] == "conditional_term"
    assert policy_by_term["谋反"]["policy_group"] == "disposition_risk"
    assert report["changed_term_slices"][0]["accepted_added_terms"] == ["谋反"]
    assert report["added_slices"][0]["accepted_term_hits"] == ["伏诛"]
    rendered = tool.render_source_ab_markdown(report)
    assert "source A/B" in rendered
    assert "term policy recommendations" in rendered


def test_recall_term_policy_uses_static_taxonomy_before_sampling() -> None:
    assert tool.recall_term_policy("委任")["policy_group"] == "appointment_delegation"
    assert tool.recall_term_policy("信任")["policy_group"] == "appointment_delegation"
    assert tool.recall_term_policy("专擅")["policy_group"] == "power_abuse_mechanism"
    assert tool.recall_term_policy("纳谏")["profile_action"] == "append_rule_term"
    assert tool.recall_term_policy("荐举")["policy_group"] == "talent_discovery"
    assert tool.recall_term_policy("谮害")["policy_group"] == "anti_nepotism"
    assert tool.recall_term_policy("削藩")["policy_group"] == "power_control"
    assert tool.recall_term_policy("将兵")["policy_group"] == "military_authority"
    assert tool.recall_term_policy("谋反")["policy_group"] == "disposition_risk"
    assert tool.recall_term_policy("欲反")["policy_group"] == "disposition_risk"
    assert tool.recall_term_policy("欲发兵")["policy_group"] == "military_authority"
    assert tool.recall_term_policy("赐死")["policy_group"] == "disposition_risk"
    assert tool.recall_term_policy("宗室")["policy_group"] == "power_base_context"
    assert tool.recall_term_policy("刘基")["profile_action"] == "reject_term"
    assert tool.recall_term_policy("自杀")["profile_action"] == "context_only"
    assert tool.recall_term_policy("大赦")["policy_group"] == "context_or_noise"
    assert tool.recall_term_policy("军国")["profile_action"] == "context_only"
    assert tool.recall_term_policy("王信")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("信国公")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("暂未分类词")["profile_action"] == "needs_taxonomy_review"


def test_recall_term_policy_rejects_sentence_fragment_ngrams_without_hiding_known_terms() -> None:
    assert tool.recall_term_policy("信任")["policy_group"] == "appointment_delegation"
    assert tool.recall_term_policy("将兵")["policy_group"] == "military_authority"
    assert tool.recall_term_policy("下狱")["policy_group"] == "disposition_risk"
    assert tool.recall_term_policy("谋反")["policy_group"] == "disposition_risk"
    assert tool.recall_term_policy("可与言乎")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("子有言")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("下精兵")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("精兵处也")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("果反")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("上赦")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("公引兵")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("沛公引兵")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("杀彭")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("陛下乃疑")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("亦何言")["policy_group"] == "fragment_noise"
    assert tool.recall_term_policy("分兵")["profile_action"] == "context_only"
    assert tool.recall_term_policy("屯田")["profile_action"] == "context_only"
    assert tool.recall_term_policy("军中")["profile_action"] == "context_only"


def test_recall_term_sampler_filters_case_terms_by_default(tmp_path: Path) -> None:
    path = tmp_path / "candidates.final.json"
    write_json(path, candidate_payload("朱元璋", "胡惟庸", "刘基总中书政专擅威福。", ["刘基", "专擅"]))

    report = tool.build_report(
        candidates_paths=[path],
        min_chars=2,
        max_chars=4,
        include_text_ngrams=False,
        include_candidate_ab=False,
        min_support=2,
        include_case_terms=False,
        top=100,
    )

    by_term = {row["term"]: row for row in report["terms"]}
    assert by_term["刘基"]["tier"] == "reject_term"
    assert "专擅" not in by_term
    assert report["summary"]["tier_counts"]["reject_term"] >= 1


def test_candidate_ab_counts_new_text_hits(tmp_path: Path) -> None:
    path = tmp_path / "candidates.final.json"
    write_json(
        path,
        {
            "task_identity": {"emperor_name": "朱元璋"},
            "candidate_slices": [
                {
                    "slice_code": "SLI-1",
                    "document_code": "DOC-1",
                    "object_name": "胡惟庸",
                    "matched_rule_terms": ["宠任"],
                    "matched_role_families": ["appointment_delegation_material"],
                    "text": "帝宠任胡惟庸，惟庸专擅威福。",
                },
                {
                    "slice_code": "SLI-2",
                    "document_code": "DOC-2",
                    "object_name": "李林甫",
                    "matched_rule_terms": ["宠任"],
                    "matched_role_families": ["appointment_delegation_material"],
                    "text": "帝宠任李林甫，林甫专擅威福。",
                },
            ],
        },
    )

    report = tool.build_report(
        candidates_paths=[path],
        min_chars=2,
        max_chars=4,
        include_text_ngrams=True,
        include_candidate_ab=True,
        min_support=2,
        include_case_terms=True,
        top=0,
    )

    by_term = {row["term"]: row for row in report["candidate_ab"]["terms"]}
    assert by_term["专擅"]["new_text_hit_count"] == 2
    assert by_term["专擅"]["already_matched_count"] == 0
    assert by_term["宠任"]["new_text_hit_count"] == 0
    assert by_term["宠任"]["already_matched_count"] == 2
    assert report["taxonomy_validation"]["policy_action_counts"]["append_rule_term"] >= 1
    assert "needs_taxonomy_review_count" in report["taxonomy_validation"]
    assert "policy_action_counts" in tool.render_markdown(report)


def test_profile_patch_template_requires_reviewable_ab_terms(tmp_path: Path) -> None:
    path = tmp_path / "candidates.final.json"
    write_json(
        path,
        {
            "task_identity": {"emperor_name": "朱元璋"},
            "candidate_slices": [
                {
                    "slice_code": f"SLI-{index}",
                    "document_code": f"DOC-{index}",
                    "object_name": object_name,
                    "matched_rule_terms": ["宠任"],
                    "matched_role_families": ["appointment_delegation_material"],
                    "text": f"帝宠任{object_name}，{object_name}专擅威福，刘基不应入长期词表。",
                }
                for index, object_name in enumerate(["甲臣", "乙臣", "丙臣"], start=1)
            ],
        },
    )
    report = tool.build_report(
        candidates_paths=[path],
        min_chars=2,
        max_chars=4,
        include_text_ngrams=True,
        include_candidate_ab=True,
        min_support=1,
        include_case_terms=True,
        top=0,
    )

    patch = tool.profile_patch_template(report, min_new_hits=3, min_object_diversity=3, max_terms=10, accepted_terms=["专擅"])

    by_term = {row["term"]: row for row in patch["terms"]}
    assert by_term["专擅"]["accepted_for_profile"] is True
    assert by_term["专擅"]["review_status"] == "accepted"
    assert "accepted_by_explicit_term_list" in by_term["专擅"]["review_flags"]
    assert by_term["专擅"]["proposed_location"] == "source_discovery_profile"
    assert by_term["专擅"]["review_suggestion"] == "needs_human_review"
    assert "刘基" not in by_term
    assert patch["safety"]["writes_profile"] is False
    assert patch["summary"]["accepted_term_count"] == 1
    delta = tool.profile_delta_from_patch(patch)
    assert delta["report_type"] == "recall_term_profile_delta"
    assert delta["safety"]["writes_profile"] is False
    assert delta["summary"]["accepted_term_count"] == 1
    assert delta["proposed_updates"][0]["target_field"] == "rule_terms"
    assert delta["proposed_updates"][0]["add_terms"] == ["专擅"]

    guarded_patch = {
        "version": "test",
        "terms": [
            {"term": "谋反", "accepted_for_profile": True},
            {"term": "伏诛", "accepted_for_profile": True},
            {"term": "将兵", "accepted_for_profile": True},
            {"term": "刘基", "accepted_for_profile": True},
        ],
    }
    guarded_delta = tool.profile_delta_from_patch(guarded_patch)
    assert guarded_delta["summary"]["append_rule_term_count"] == 0
    assert guarded_delta["summary"]["conditional_term_count"] == 3
    assert guarded_delta["summary"]["rejected_term_count"] == 1
    assert guarded_delta["proposed_updates"][0]["target_field"] == "conditional_rule_terms"
    guarded_terms = {row["term"]: row for row in guarded_delta["proposed_updates"][0]["conditional_terms"]}
    assert guarded_terms["谋反"]["policy_group"] == "disposition_risk"
    assert guarded_terms["将兵"]["policy_group"] == "military_authority"

    review_patch = {
        "version": "test",
        "terms": [{"term": "未分类高频词", "accepted_for_profile": True}],
    }
    review_delta = tool.profile_delta_from_patch(review_patch)
    assert review_delta["summary"]["taxonomy_review_term_count"] == 1
    assert review_delta["proposed_updates"] == []

    context_patch = {
        "version": "test",
        "terms": [{"term": "自杀", "accepted_for_profile": True}],
    }
    context_delta = tool.profile_delta_from_patch(context_patch)
    assert context_delta["summary"]["context_only_term_count"] == 1
    assert context_delta["proposed_updates"] == []

    noisy_report = {
        "version": "test",
        "candidate_ab": {
            "terms": [
                {
                    "term": "信欲反",
                    "tier": "conditional_term",
                    "new_text_hit_count": 9,
                    "text_hit_count": 9,
                    "already_matched_count": 0,
                    "hit_object_diversity": 6,
                    "hit_target_diversity": 1,
                    "hit_role_family_counts": {},
                    "rejection_reasons": [],
                }
            ]
        },
    }
    assert tool.profile_patch_template(noisy_report, min_new_hits=3, min_object_diversity=3, max_terms=10)["terms"] == []

    suggested_report = {
        "version": "test",
        "candidate_ab": {
            "terms": [
                {
                    "term": "谋反",
                    "tier": "conditional_term",
                    "new_text_hit_count": 12,
                    "text_hit_count": 12,
                    "already_matched_count": 0,
                    "hit_object_diversity": 4,
                    "hit_target_diversity": 1,
                    "hit_role_family_counts": {},
                    "rejection_reasons": [],
                },
                {
                    "term": "大赦",
                    "tier": "conditional_term",
                    "new_text_hit_count": 12,
                    "text_hit_count": 12,
                    "already_matched_count": 0,
                    "hit_object_diversity": 4,
                    "hit_target_diversity": 1,
                    "hit_role_family_counts": {},
                    "rejection_reasons": [],
                },
            ]
        },
    }
    suggested_patch = tool.profile_patch_template(suggested_report, min_new_hits=3, min_object_diversity=3, max_terms=10)
    suggestions = {row["term"]: row["review_suggestion"] for row in suggested_patch["terms"]}
    assert suggestions["谋反"] == "profile_candidate_review"
    assert suggestions["大赦"] == "context_or_noise_review"


def test_cli_writes_json_markdown_and_jsonl(tmp_path: Path, capsys) -> None:
    path = tmp_path / "run" / "target" / "candidates.final.json"
    write_json(path, candidate_payload("唐太宗", "魏徵", "太宗纳谏，魏徵直言，数从其言。", ["纳谏", "直言"]))
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    output_jsonl = tmp_path / "terms.jsonl"
    output_profile_patch = tmp_path / "profile_patch.json"
    output_profile_delta = tmp_path / "profile_delta.json"

    assert (
        tool.main(
            [
                "--run-root",
                str(tmp_path / "run"),
                "--min-support",
                "1",
                "--include-case-terms",
                "--include-candidate-ab",
                "--output-profile-patch",
                str(output_profile_patch),
                "--output-profile-delta",
                str(output_profile_delta),
                "--accept-term",
                "纳谏",
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
                "--output-jsonl",
                str(output_jsonl),
            ]
        )
        == 0
    )

    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["profile_delta_terms"] == 1
    assert output_json.exists()
    assert "# retrieval_v2 recall term sampling report" in output_md.read_text(encoding="utf-8")
    assert "candidate-only A/B" in output_md.read_text(encoding="utf-8")
    assert output_jsonl.read_text(encoding="utf-8").strip()
    profile_patch = json.loads(output_profile_patch.read_text(encoding="utf-8"))
    assert profile_patch["report_type"] == "recall_term_profile_patch_template"
    assert profile_patch["safety"]["requires_human_review"] is True
    accepted_terms = [row["term"] for row in profile_patch["terms"] if row["accepted_for_profile"] is True]
    assert accepted_terms == ["纳谏"]
    profile_delta = json.loads(output_profile_delta.read_text(encoding="utf-8"))
    assert profile_delta["proposed_updates"][0]["add_terms"] == ["纳谏"]
