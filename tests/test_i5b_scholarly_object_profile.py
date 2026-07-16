from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.i5b_scholarly_object_profile import (
    build_scholarly_object_profile_report,
    render_scholarly_object_profile_markdown,
    write_scholarly_object_profile_report,
)


ROOT = Path(__file__).parents[1]
CONTRACT = ROOT / "eval/i5b_source_ingestion/team_building_lishimin_scholarly_object_profiles_v1.yml"


def test_scholarly_profiles_are_context_only_and_cover_governance_objects() -> None:
    report = build_scholarly_object_profile_report(CONTRACT)

    assert report["summary"] == {
        "scholarly_source_count": 5,
        "profile_count": 10,
        "summary_item_count": 10,
        "subject_kind_counts": {"institution": 3, "person": 3, "policy": 4},
    }
    assert report["declarations"]["secondary_scholarship_is_formal_fact"] is False
    assert report["declarations"]["direct_factor_choice_allowed"] is False
    assert report["declarations"]["database_write_count"] == 0
    assert all(
        item["primary_source_locators"]
        for profile in report["profiles"]
        for item in profile["summary_items"]
    )
    person_refs = {
        profile["subject"]["label"]: profile["subject"]["ref"]
        for profile in report["profiles"]
        if profile["subject"]["kind"] == "person"
    }
    assert person_refs == {
        "马周": "PER-V4-1E978B22A450",
        "房玄龄": "PER-V4-C37ED24688F5",
        "李勣": "PER-V4-LIJI-CANDIDATE",
    }


def test_scholarly_profile_rejects_factor_authority(tmp_path: Path) -> None:
    payload = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    payload["profiles"][0]["allowed_uses"].append("factor_choice")
    broken = tmp_path / "broken.yml"
    broken.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="使用边界不完整"):
        build_scholarly_object_profile_report(broken)


def test_scholarly_profile_report_is_byte_idempotent(tmp_path: Path) -> None:
    output_json = tmp_path / "profiles.json"
    output_md = tmp_path / "profiles.md"
    write_scholarly_object_profile_report(
        contract_path=CONTRACT,
        output_json=output_json,
        output_markdown=output_md,
    )
    before = output_json.read_bytes(), output_md.read_bytes()
    write_scholarly_object_profile_report(
        contract_path=CONTRACT,
        output_json=output_json,
        output_markdown=output_md,
    )
    assert before == (output_json.read_bytes(), output_md.read_bytes())
    assert json.loads(output_json.read_text(encoding="utf-8"))["report_sha256"]
    markdown = render_scholarly_object_profile_markdown(
        build_scholarly_object_profile_report(CONTRACT)
    )
    assert "不直接接受为V4事实" in markdown
    assert "贞观谏官随宰相议政机制" in markdown
