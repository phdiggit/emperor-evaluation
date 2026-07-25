import json
from pathlib import Path

import pytest
import emperor_v4.application.google_ai_discovery_prompt as discovery_prompt

from emperor_v4.application.google_ai_discovery_prompt import (
    build_person_rebuild_manifest,
    build_google_ai_discovery_task,
    load_discovery_prompt_policy,
    render_discovery_prompt,
)
from emperor_v4.infrastructure.google_ai_bridge import normalize_task


ROOT = Path(__file__).parents[1]
POLICY_PATH = ROOT / "config/google-ai-discovery-prompt.yml"


def test_project_prompt_is_source_compass_and_forbids_quotes() -> None:
    policy = load_discovery_prompt_policy(POLICY_PATH)
    rendered = render_discovery_prompt(
        policy,
        subject_name="李靖",
        focus="独立重大功业",
        search_categories=("军事功业", "制度建设", "人才培养"),
        relevance_criteria=("人才等级", "皇帝用人归责"),
        requested_outputs=("事件线索", "史源提示"),
        aliases=("李药师", "卫国公"),
    )

    assert "完整传记" in rendered.text
    assert "现代白话短语" in rendered.text
    assert "不得出现“”、英文引号、原话" in rendered.text
    assert "quote_status" not in rendered.text
    assert "quote_candidate" not in rendered.text
    assert "原文候选" not in rendered.text
    assert "彼此独立、可回源" in rendered.text
    assert "本人被指控、受害、遭猜忌或遇险不算本人行动" in rendered.text
    assert "不查也不输出外链" in rendered.text
    assert "检索优先级而不是答案" in rendered.text
    assert "某书不实际承载该事项就不得列入" in rendered.text
    assert "制度目的、后世概括或因果推断一律写待核" in rendered.text
    assert "locator_anchor:" in rendered.text
    assert "source_url: 未核" in rendered.text
    assert "焦点：独立重大功业；类别：军事功业；制度建设；人才培养" in rendered.text
    assert "searched_categories:" in rendered.text
    assert "subject: 李靖" in rendered.text
    assert "uncovered_categories:" in rendered.text
    assert "stop_reason:" in rendered.text
    assert "不预判分数" not in rendered.text
    assert "人才等级；皇帝用人归责" in rendered.text
    assert "无一字无来历" not in rendered.text
    assert "穷尽以下维度" not in rendered.text
    assert len(rendered.fingerprint) == 64


def test_person_rebuild_manifest_uses_three_serial_focuses_and_one_policy() -> None:
    policy = load_discovery_prompt_policy(POLICY_PATH)
    manifest = build_person_rebuild_manifest(
        policy,
        person_ref="PER-V4-LIJING",
        person_name="李靖",
        input_version="person-rebuild-v1",
        aliases=("李药师", "卫国公"),
    )

    assert manifest["schema_version"] == "google-ai-browser-manifest-v1"
    assert len(manifest["tasks"]) == 3
    history, authority, risk = manifest["tasks"]
    assert history["purpose_code"] == "person_rebuild_discovery"
    assert authority["purpose_code"] == "authority_evaluation_discovery"
    assert risk["purpose_code"] == "political_risk_discovery"
    assert history["response_timeout_seconds"] == 30
    assert risk["response_timeout_seconds"] == 30
    assert "event；achievement" in history["query"]
    assert "subject: 李靖" in history["query"]
    assert "authority_evaluation" in authority["query"]
    assert "最多 3 项" not in authority["query"]
    assert len(authority["query"]) < 1_300
    assert "lead 仅为“评价者或作品｜正/负｜评价维度”" in authority["query"]
    assert "不得出现“”、英文引号、原话、比喻、心理或荣典" in authority["query"]
    assert "project_relevance 只填 talent_profile_candidate" in authority["query"]
    assert "宋至清兵学家、将领、军事史家" in authority["query"]
    assert "武庙、托名兵书、泛及不算" in authority["query"]
    assert "后世兵学家、将领或军事史家对统帅用兵与战功的直接专评" in authority["query"]
    assert authority["downstream_context"]["possible_projections"] == [
        "talent_profile_candidate",
    ]
    assert "本人被诬告或受害不算" in risk["query"]
    assert "本人可归责的政治风险与重大军事败绩" in risk["query"]
    assert "本人统帅责任下的重大军事败绩及可观察损失" in risk["query"]
    assert "败绩不等于风险成立" in risk["query"]
    assert "部将单独失利、本人被诬告或受害不算" in risk["query"]
    assert len(risk["query"]) < len(history["query"])
    assert "不得出现“”、英文引号、原话、心理、比喻或官职罗列" in risk["query"]
    assert "project_relevance 只填 historical_episode_candidate 或 political_risk_profile_candidate" in risk["query"]
    assert "不能确认篇章时写未核，不得猜卷次" in risk["query"]
    assert history["downstream_context"]["possible_projections"] == [
        "historical_episode_candidate",
        "talent_profile_candidate",
    ]


def test_person_rebuild_manifest_cli_is_zero_write_on_unchanged_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "manifest.json"
    argv = [
        "--policy",
        str(POLICY_PATH),
        "--person-ref",
        "PER-V4-LIJING",
        "--person-name",
        "李靖",
        "--input-version",
        "person-rebuild-v1",
        "--output",
        str(output),
    ]
    assert discovery_prompt.main(argv) == 0
    first = output.read_bytes()

    def unexpected_replace(*args: object, **kwargs: object) -> None:
        raise AssertionError("unchanged manifest must not be replaced")

    monkeypatch.setattr(discovery_prompt.os, "replace", unexpected_replace)
    assert discovery_prompt.main(argv) == 0
    assert output.read_bytes() == first


def test_person_rebuild_manifest_cli_can_emit_one_focus_for_targeted_retest(
    tmp_path: Path,
) -> None:
    output = tmp_path / "history-only.json"
    assert discovery_prompt.main(
        [
            "--policy",
            str(POLICY_PATH),
            "--person-ref",
            "PER-V4-LIJING",
            "--person-name",
            "李靖",
            "--input-version",
            "person-rebuild-v1",
            "--purpose-code",
            "person_rebuild_discovery",
            "--output",
            str(output),
        ]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [row["purpose_code"] for row in payload["tasks"]] == [
        "person_rebuild_discovery"
    ]


def test_i5b_manifest_cli_emits_civil_and_uncapped_policy_discovery(
    tmp_path: Path,
) -> None:
    civil_people = tmp_path / "civil-people.json"
    civil_people.write_text(
        json.dumps(
            [{"person_ref": "PER-FANG", "person_name": "房玄龄"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "manifest.json"
    assert discovery_prompt.main(
        [
            "--policy",
            str(POLICY_PATH),
            "--i5b-ruler-ref",
            "PER-TAIZONG",
            "--i5b-ruler-name",
            "唐太宗",
            "--i5b-ruler-dynasty",
            "唐",
            "--input-version",
            "i5b-v1",
            "--civil-people",
            str(civil_people),
            "--output",
            str(output),
        ]
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [row["purpose_code"] for row in payload["tasks"]] == [
        "civil_governance_discovery",
        "ruler_policy_discovery",
    ]
    assert all("不限数量" in row["query"] for row in payload["tasks"])


def test_same_prompt_supports_all_workflows_by_changing_only_focus() -> None:
    policy = load_discovery_prompt_policy(POLICY_PATH)
    common = {
        "policy": policy,
        "subject_name": "房玄龄",
        "relevance_criteria": ("第五项B候选发现",),
        "requested_outputs": ("事件线索", "史源提示"),
    }
    governance = render_discovery_prompt(
        **common, focus="文官本人实施的治理举措及结果"
    )
    risk = render_discovery_prompt(
        **common, focus="达到实质损害门槛的政治风险"
    )

    assert governance.prompt_version == risk.prompt_version
    assert governance.fingerprint != risk.fingerprint
    assert "文官本人实施的治理举措及结果" in governance.text
    assert "达到实质损害门槛的政治风险" in risk.text


def test_rendered_prompt_builds_generic_idempotent_bridge_task() -> None:
    policy = load_discovery_prompt_policy(POLICY_PATH)
    rendered = render_discovery_prompt(
        policy,
        subject_name="杜如晦",
        focus="重大治理成就",
        relevance_criteria=("人才等级复核",),
        requested_outputs=("时间线", "成就事件", "评价来源"),
    )
    task = build_google_ai_discovery_task(
        rendered,
        task_code="PROFILE-DURU-001",
        input_version="person-profile-v1",
        purpose_code="person_profile_discovery",
        subject_ref="PER-DURU",
        subject_name="杜如晦",
        subject_aliases=("杜克明",),
        requested_outputs=("timeline", "achievement_leads", "authority_evaluations"),
        downstream_context={"consumer": "person_profile_review"},
    )

    first = normalize_task(task)
    second = normalize_task(task)
    assert first == second
    assert first["quality_requirements"]["min_source_links"] == 0
    assert first["quality_requirements"]["require_locator_hints"] is True
    assert first["quality_requirements"]["acceptable_subject_mentions"] == [
        "杜如晦",
        "杜克明",
    ]
    assert first["response_timeout_seconds"] == 30
    assert first["lease_seconds"] == 90
    assert first["downstream_context"]["discovery_prompt_version"] == (
        policy.prompt_version
    )


def test_prompt_rejects_empty_relevance_and_excessive_lead_count() -> None:
    policy = load_discovery_prompt_policy(POLICY_PATH)
    with pytest.raises(ValueError, match="relevance_criteria"):
        render_discovery_prompt(
            policy,
            subject_name="李靖",
            focus="功业",
            relevance_criteria=(),
            requested_outputs=("事件线索",),
        )
    with pytest.raises(ValueError, match="max_leads"):
        render_discovery_prompt(
            policy,
            subject_name="李靖",
            focus="功业",
            relevance_criteria=("人才等级",),
            requested_outputs=("事件线索",),
            max_leads=51,
        )
