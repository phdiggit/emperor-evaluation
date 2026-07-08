from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_audit as tool
from scripts.dev import retrieval_v2_claim_cache as claim_cache


def test_claim_semantic_findings_accepts_classical_authorization_anchors() -> None:
    claims = [
        {
            "claim_key": "CLM-001",
            "object_name": "戴胄",
            "claim_summary": "太宗时，戴胄与房玄龄、李靖、温彦博、魏徵、王珪同知国政。",
            "action_type": "授权",
            "direction": "positive",
        },
        {
            "claim_key": "CLM-002",
            "object_name": "褚遂良",
            "claim_summary": "贞观十年，褚遂良自秘书郎迁起居郎。",
            "action_type": "任命",
            "direction": "positive",
        },
        {
            "claim_key": "CLM-003",
            "object_name": "长孙无忌",
            "claim_summary": "太宗曾留长孙无忌、房玄龄、李𪟝及褚遂良定策立高宗。",
            "action_type": "授权",
            "direction": "positive",
        },
    ]

    for claim in claims:
        assert tool.claim_semantic_findings(claim) == []


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_claim_audit_flags_wrong_person_section_and_duplicates(tmp_path: Path) -> None:
    claim_root = tmp_path / "claim_cache"
    object_root = tmp_path / "object_cache"
    paths = claim_cache.cache_paths(claim_root)
    claim_a = {
        "claim_key": "CLM-1",
        "emperor_name": "朱元璋",
        "object_name": "李文忠",
        "direction": "positive",
        "action_type": "战役",
        "event_scope": "军事",
        "office_or_domain": "建德",
        "time_context": "至正年间",
        "outcome": "破敌",
        "claim_summary": "李文忠从太祖攻建德、严州，屡破敌军。",
        "fact_payload": {},
        "status": "active",
    }
    claim_b = {**claim_a, "claim_key": "CLM-2", "claim_summary": "李文忠攻建德严州并破敌。"}
    write_jsonl(paths["claims"], [claim_a, claim_b])
    write_jsonl(
        paths["evidence"],
        [
            {
                "evidence_key": "EVD-1",
                "claim_key": "CLM-1",
                "slice_hash": "SLH-1",
                "source_slice_ref": "OSS-1",
                "document_code": "OSD-1",
                "object_name": "李文忠",
                "slice_text_preview": "愈为人简重慎密，诸将早贵未有如愈与李文忠者。",
            },
            {
                "evidence_key": "EVD-2",
                "claim_key": "CLM-2",
                "slice_hash": "SLH-2",
                "source_slice_ref": "OSS-2",
                "document_code": "OSD-2",
                "object_name": "邓愈",
                "slice_text_preview": "李文忠从太祖攻建德。",
            },
        ],
    )
    write_jsonl(
        paths["slices"],
        [
            {"slice_hash": "SLH-1", "source_slice_ref": "OSS-1", "document_code": "OSD-1", "object_name": "李文忠", "slice_text_preview": "x"},
            {"slice_hash": "SLH-2", "source_slice_ref": "OSS-2", "document_code": "OSD-2", "object_name": "李文忠", "slice_text_preview": "x"},
        ],
    )
    write_jsonl(paths["runs"], [])
    write_jsonl(
        object_root / "source_documents.jsonl",
        [
            {
                "document_cache_code": "OSD-1",
                "source_title": "明史/卷126",
                "source_shape": "object_biography_candidate",
                "source_role": "object_biography_or_mentions",
            },
            {
                "document_cache_code": "OSD-2",
                "source_title": "明史/卷126",
                "source_shape": "object_biography_candidate",
                "source_role": "object_biography_or_mentions",
            },
        ],
    )
    write_jsonl(
        object_root / "mention_slices.jsonl",
        [
            {
                "slice_cache_code": "OSS-1",
                "document_cache_code": "OSD-1",
                "person_name": "李文忠",
                "section_heading": "邓愈",
                "matched_aliases": ["李文忠"],
                "raw_text": "愈为人简重慎密，诸将早贵未有如愈与李文忠者。",
            },
            {
                "slice_cache_code": "OSS-2",
                "document_cache_code": "OSD-2",
                "person_name": "李文忠",
                "section_heading": "李文忠",
                "matched_aliases": ["李文忠"],
                "raw_text": "李文忠从太祖攻建德。",
            },
        ],
    )

    report = tool.build_claim_audit(claim_cache_root=claim_root, object_cache_root=object_root)
    issue_codes = [row["issue_code"] for row in report["findings"]]

    assert "wrong_person_section" in issue_codes
    assert "ineligible_slice_claim_evidence" in issue_codes
    assert "claim_evidence_object_mismatch" in issue_codes
    assert "near_duplicate_claim_group" in issue_codes
    assert report["issue_counts"]["wrong_person_section"] == 1
    assert report["issue_counts"]["ineligible_slice_claim_evidence"] == 1
    assert report["totals"]["claims"] == 2


def test_claim_audit_cli_writes_reports(tmp_path: Path, capsys) -> None:
    claim_root = tmp_path / "claim_cache"
    object_root = tmp_path / "object_cache"
    for path in claim_cache.cache_paths(claim_root).values():
        if path.suffix == ".jsonl":
            write_jsonl(path, [])
    write_jsonl(object_root / "source_documents.jsonl", [])
    write_jsonl(object_root / "mention_slices.jsonl", [])

    rc = tool.main(
        [
            "--claim-cache-root",
            str(claim_root),
            "--object-cache-root",
            str(object_root),
            "--output-json",
            str(tmp_path / "audit.json"),
            "--output-md",
            str(tmp_path / "audit.md"),
        ]
    )

    assert rc == 0
    assert json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))["totals"]["claims"] == 0
    assert "# retrieval_v2 claim cache audit" in (tmp_path / "audit.md").read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_claim_audit_flags_negative_authorization_disposition_only(tmp_path: Path) -> None:
    claim_root = tmp_path / "claim_cache"
    object_root = tmp_path / "object_cache"
    paths = claim_cache.cache_paths(claim_root)
    write_jsonl(
        paths["claims"],
        [
            {
                "claim_key": "CLM-HWY",
                "emperor_name": "朱元璋",
                "object_name": "胡惟庸",
                "direction": "negative",
                "action_type": "授权",
                "event_scope": "中枢",
                "office_or_domain": "丞相",
                "time_context": "洪武十三年",
                "outcome": "谋反伏诛，废丞相",
                "claim_summary": "胡惟庸谋反伏诛，朱元璋废丞相。",
                "fact_payload": {},
                "status": "active",
            }
        ],
    )
    write_jsonl(paths["evidence"], [])
    write_jsonl(paths["slices"], [])
    write_jsonl(paths["runs"], [])
    write_jsonl(object_root / "source_documents.jsonl", [])
    write_jsonl(object_root / "mention_slices.jsonl", [])

    report = tool.build_claim_audit(claim_cache_root=claim_root, object_cache_root=object_root)

    assert report["issue_counts"]["negative_authorization_disposition_only_review"] == 1


def test_claim_audit_excludes_rejected_claims_from_active_findings(tmp_path: Path) -> None:
    claim_root = tmp_path / "claim_cache"
    object_root = tmp_path / "object_cache"
    paths = claim_cache.cache_paths(claim_root)
    write_jsonl(
        paths["claims"],
        [
            {
                "claim_key": "CLM-HWY",
                "emperor_name": "朱元璋",
                "object_name": "胡惟庸",
                "direction": "negative",
                "action_type": "授权",
                "claim_summary": "胡惟庸谋反伏诛，朱元璋废丞相。",
                "fact_payload": {},
                "status": "rejected",
            }
        ],
    )
    write_jsonl(paths["evidence"], [{"claim_key": "CLM-HWY", "evidence_key": "EVD-1", "source_slice_ref": "SLI-1"}])
    write_jsonl(paths["slices"], [])
    write_jsonl(paths["runs"], [])
    write_jsonl(object_root / "source_documents.jsonl", [])
    write_jsonl(object_root / "mention_slices.jsonl", [])

    report = tool.build_claim_audit(claim_cache_root=claim_root, object_cache_root=object_root)

    assert report["totals"]["claims"] == 1
    assert report["totals"]["active_claims"] == 0
    assert report["totals"]["claim_status_counts"] == {"rejected": 1}
    assert report["issue_counts"] == {}


def test_claim_audit_uses_candidates_for_opportunity_estimate(tmp_path: Path) -> None:
    claim_root = tmp_path / "claim_cache"
    object_root = tmp_path / "object_cache"
    paths = claim_cache.cache_paths(claim_root)
    write_jsonl(paths["claims"], [])
    write_jsonl(paths["evidence"], [])
    write_jsonl(paths["slices"], [])
    write_jsonl(paths["runs"], [])
    write_jsonl(object_root / "source_documents.jsonl", [])
    write_jsonl(object_root / "mention_slices.jsonl", [])
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            {
                "candidate_slices": [
                    {
                        "slice_code": "SLI-001",
                        "object_name": "李文忠",
                        "matched_aliases": ["李文忠"],
                        "source_shape": "object_biography_candidate",
                        "section_heading": "李文忠",
                        "text": "太祖诏李文忠领常遇春众，命其北征，克应昌。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = tool.build_claim_audit(
        claim_cache_root=claim_root,
        object_cache_root=object_root,
        candidates_path=candidates_path,
    )

    estimate = report["claim_opportunity_estimate"]["objects"]["李文忠"]
    assert estimate["suggested_claim_budget"] == 2
    assert estimate["undercoverage_risk"] == "missing_claims"
    assert report["issue_counts"]["claim_opportunity_undercoverage"] == 1


def test_dedupe_findings_keeps_object_level_undercoverage_separate() -> None:
    findings = [
        {
            "issue_code": "claim_opportunity_undercoverage",
            "severity": "low",
            "object_name": "张亮",
            "detail": "possible_undercoverage",
        },
        {
            "issue_code": "claim_opportunity_undercoverage",
            "severity": "low",
            "object_name": "长孙无忌",
            "detail": "possible_undercoverage",
        },
    ]

    assert len(tool.dedupe_findings(findings)) == 2
