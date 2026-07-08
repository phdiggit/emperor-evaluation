from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_calibration_package as tool


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sample_task() -> dict:
    return {
        "job_code": "JOB-I5B-ZYZ-CALIBRATION",
        "target_code": "TGT-I5B-ZYZ",
        "emperor_name": "朱元璋",
        "item_code": "I5B",
        "rule_code": "i5b_item_wide",
        "capture_profile": "personnel_political_wide",
        "target_profile": {"primary_name": "朱元璋", "aliases": ["太祖", "高皇帝"]},
        "rule": {
            "rule_code": "i5b_item_wide",
            "keywords": ["命", "拜", "任", "相", "专", "擅", "谋反", "功", "封", "谏"],
        },
        "object_seeds": [
            {"name": "胡惟庸"},
            {"name": "汤和"},
            {"name": "朱升"},
        ],
        "source_documents": [
            {
                "document_code": "DOC-ZS",
                "title": "明史/卷136",
                "source_kind": "primary_source",
                "text": "朱升谏曰：高筑墙，广积粮，缓称王。太祖善之。",
            }
        ],
    }


def write_cache(cache_root: Path) -> None:
    write_jsonl(
        cache_root / "source_documents.jsonl",
        [
            {
                "document_cache_code": "OSD-HWY",
                "person_cache_code": "PSC-HWY",
                "person_name": "胡惟庸",
                "source_title": "明史/卷308",
                "wikisource_title": "明史/卷308",
                "source_kind": "wikisource_page",
                "source_role": "object_biography_or_mentions",
                "source_shape": "object_biography_candidate",
                "mention_slice_count": 2,
                "text_chars": 600,
            },
            {
                "document_cache_code": "OSD-TH",
                "person_cache_code": "PSC-TH",
                "person_name": "汤和",
                "source_title": "明史/卷126",
                "wikisource_title": "明史/卷126",
                "source_kind": "wikisource_page",
                "source_role": "object_biography_or_mentions",
                "source_shape": "object_biography_candidate",
                "mention_slice_count": 2,
                "text_chars": 600,
            },
        ],
    )
    write_jsonl(
        cache_root / "person_coverage.jsonl",
        [
            {
                "person_name": "胡惟庸",
                "has_source_document": True,
                "has_biography_source": True,
                "source_document_count": 1,
                "mention_slice_count": 2,
                "needs_agent_review": False,
                "source_shapes": ["object_biography_candidate"],
            },
            {
                "person_name": "汤和",
                "has_source_document": True,
                "has_biography_source": True,
                "source_document_count": 1,
                "mention_slice_count": 2,
                "needs_agent_review": False,
                "source_shapes": ["object_biography_candidate"],
            },
        ],
    )


def test_build_calibration_package_classifies_budget_and_writes_signals(tmp_path: Path, monkeypatch) -> None:
    cache_root = tmp_path / "cache"
    source_cache = tmp_path / "source-cache"
    output_root = tmp_path / "out"
    profile_priors = tmp_path / "profile_priors.jsonl"
    write_cache(cache_root)
    write_jsonl(
        profile_priors,
        [
            {"canonical_name": "胡惟庸", "talent_grade": "major_sycophant", "review_status": "accepted"},
            {"canonical_name": "汤和", "talent_grade": "important_talent", "review_status": "accepted"},
        ],
    )
    text_by_title = {
        "明史/卷308": "太祖拜胡惟庸为丞相。胡惟庸专擅威福，结党谋反，事觉伏诛，遂废丞相罢中书。",
        "明史/卷126": "太祖命汤和为征南将军，率师讨方国珍，平之，以功封信国公。",
    }

    def fake_fetch(document: dict, *, cache_dir: Path, timeout: int) -> tuple[str, dict]:
        del cache_dir, timeout
        if document.get("text"):
            return str(document["text"]), {"cache_status": "embedded"}
        return text_by_title[str(document["title"])], {"cache_status": "fixture"}

    monkeypatch.setattr(tool.source_candidates, "fetch_document_text", fake_fetch)

    result = tool.build_calibration_package(
        task=sample_task(),
        output_root=output_root,
        object_source_cache_root=cache_root,
        source_cache_root=source_cache,
        profile_priors_path=profile_priors,
        context_chars=80,
        max_slices_per_object=6,
    )

    rows = {row["object_name"]: row for row in result["object_rows"]}
    assert result["summary"]["mode"] == "candidate_only_calibration"
    assert result["summary"]["full_judge_invoked"] is False
    assert result["summary"]["write_db"] is False
    assert result["summary"]["overlay_stats"]["added_source_document_count"] == 2
    assert rows["胡惟庸"]["object_budget_class"] == "high_risk_object"
    assert rows["胡惟庸"]["claim_budget"] == {"min": 4, "max": 7}
    assert {"risk_or_conflict", "outcome_or_feedback"} <= set(rows["胡惟庸"]["slot_hits"])
    assert rows["汤和"]["object_budget_class"] == "important_object"
    assert rows["朱升"]["object_budget_class"] == "ordinary_object"
    assert (output_root / "calibration_summary.md").exists()
    signal_rows = [
        json.loads(line)
        for line in (output_root / "profile_signal_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["object_name"] for row in signal_rows} == {"胡惟庸", "汤和", "朱升"}
    assert all(row["write_db"] is False and row["review_status"] == "candidate" for row in signal_rows)


def test_document_owner_index_treats_shared_volume_as_multi_owner(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    write_jsonl(
        cache_root / "source_documents.jsonl",
        [
            {"person_name": "李文忠", "source_title": "明史/卷126", "wikisource_title": "明史/卷126"},
            {"person_name": "邓愈", "source_title": "明史/卷126", "wikisource_title": "明史/卷126"},
        ],
    )
    task = {
        "source_documents": [
            {
                "document_code": "DOC-SHARED",
                "title": "明史/卷126",
                "wikisource_title": "明史/卷126",
                "object_source_cache": {"person_name": "李文忠"},
            }
        ]
    }

    owners = tool.document_owner_index(task, cache_root=cache_root)

    assert owners == {"DOC-SHARED": {"李文忠", "邓愈"}}
