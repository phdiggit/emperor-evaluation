from pathlib import Path

from scripts.dev import retrieval_v3_judgment_worklists as tool


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/migrations/20260712_retrieval_v3_talent_grade_v4.sql").read_text(encoding="utf-8")


def test_current_rubric_uses_strict_governance_and_military_gatekeepers() -> None:
    assert tool.TALENT_GRADE_VERSION == "talent-grade-v4"
    prompt = tool.prompt_for_task(
        task={"task_code": "T", "task_kind": tool.PERSON_TALENT_KIND},
        workitems=[],
        patch_path=Path("tmp/talent.jsonl"),
    )
    assert "房玄龄" in prompt
    assert "李绩、苏定方" in prompt
    assert "多个决定性核心战役或战略要地" in prompt
    assert "普通多战役" in prompt
    assert "传世兵法" in prompt
    assert "横向一致性" in prompt
    assert "每个人都必须联网" in prompt
    assert "不能把 evidence_claims 的覆盖范围" in prompt


def test_team_building_view_accepts_v4_profiles_and_active_people_only() -> None:
    assert "'talent-grade-v4'" in SQL
    assert "o.identity_status='active'" in SQL
