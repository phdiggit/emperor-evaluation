import re
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_markdown import _m1_public_registered_display, render_profile_markdown


ROOT = Path(__file__).resolve().parents[1]
SETTLEMENT = ROOT / "docs/评分结算/人物画像/M1/01-M1军事判断与统帅能力正式结算.json"
UNTRANSLATED = re.compile(
    r"武将(?:锚|等级|档|人才)|military_grade|M1\.\d_[A-Z_]+|"
    r"\b(?:usable|ordinary|important|capable|elite|historic|top|"
    r"DIRECT_COMMAND|OPERATIONAL_COORDINATION|STRATEGIC_DIRECTION)\b"
)


def test_registered_battle_responsibility_is_readable():
    source = "前线− `A/D3`｜合围／结果责任=actual_command_scope／致败责任=UNKNOWN"
    public = _m1_public_registered_display(source)
    assert "本人结果责任：本人实际指挥范围" in public
    assert "致败归责：具体致败责任未定" in public
    assert "actual_command_scope" not in public


def test_unknown_registered_responsibility_fails_closed():
    with pytest.raises(ValueError, match="未翻译枚举"):
        _m1_public_registered_display("致败责任=NEW_UNDECLARED_CODE")


def test_unresolved_command_scope_remains_explicit_in_public_text():
    public = _m1_public_registered_display("结果责任=unresolved_command_scope")
    assert public == "本人结果责任：本人指挥范围尚未闭合"


def test_formal_m1_public_reasons_exclude_talent_grades_and_machine_labels():
    settlement = load_json(SETTLEMENT)
    for row in settlement["records"]:
        fields = [row.get(key) for key in (
            "typical_pattern", "grade_basis", "position_basis", "phase_profile",
            "failure_and_recovery", "counterpattern", "role_attribution",
        )]
        fields.extend(row.get("limitations") or [])
        assert not any(UNTRANSLATED.search(value) for value in fields if isinstance(value, str)), row["ruler_id"]
        public_refs = list(row["evidence_scope"]["source_refs"])
        review = row.get("m1_stability_review") or {}
        public_refs.extend(review.get("source_refs") or [])
        public_refs.extend(ref for case in review.get("cases", []) for ref in case["source_refs"])
        assert not any("02-武将人才等级.json" in ref for ref in public_refs), row["ruler_id"]
    markdown = render_profile_markdown(settlement)
    assert "本人战役事实摘录" in markdown
    assert not re.search(r"(?:结果责任|致败责任)=[A-Za-z_]+", markdown)
    assert not re.search(r"武将锚|武将等级|武将档|M1\.\d_[A-Z_]+", markdown)
