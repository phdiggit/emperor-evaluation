import re
from pathlib import Path

import pytest

from emperor_v4.evaluation.profile_markdown import _m1_public_registered_display


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
