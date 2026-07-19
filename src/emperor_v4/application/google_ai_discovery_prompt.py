from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.application.discovery_source_backfill import (
    DEFAULT_I5B_SOURCE_SCOPE_PATH,
    load_i5b_source_search_scope,
    load_i5b_person_retrieval_limit,
)


PROMPT_POLICY_SCHEMA_VERSION = "google-ai-discovery-prompt-policy-v1"
REQUIRED_PLACEHOLDERS = frozenset(
    {
        "{{subject_name}}",
        "{{focus}}",
        "{{search_categories}}",
        "{{relevance_criteria}}",
        "{{requested_outputs}}",
        "{{aliases}}",
        "{{lead_type_scope}}",
        "{{max_leads}}",
        "{{source_scope}}",
    }
)
FORBIDDEN_PROMPT_PHRASES = frozenset(
    {
        "无一字无来历",
        "一字不差地召回",
        "穷尽以下维度",
        "必须完整覆盖",
        "quote_status",
        "quote_candidate",
        "原文候选",
    }
)
I5B_PERSON_IMPACT = {"low": 1, "medium": 2, "high": 3, "critical": 4}
I5B_PERSON_SELECTION_LANES = (
    "political_risk",
    "appointment_delegation",
    "talent_discovery",
    "tolerate_talent",
    "team_building",
    "anti_nepotism",
)


@dataclass(frozen=True, slots=True)
class DiscoveryPromptPolicy:
    prompt_version: str
    status: str
    default_max_leads: int
    maximum_max_leads: int
    template: str
    authority_template: str | None = None
    risk_template: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedDiscoveryPrompt:
    prompt_version: str
    text: str
    fingerprint: str


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Google AI discovery prompt 缺少 {field}")
    return text


def _select_i5b_civil_people(
    civil_people: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if limit <= 0:
        raise ValueError("I5B 单皇帝人物检索入口上限必须为正数")
    unique: list[dict[str, Any]] = []
    names_by_ref: dict[str, str] = {}
    for raw in civil_people:
        person_ref = _required_text(raw.get("person_ref"), "civil_people.person_ref")
        person_name = _required_text(raw.get("person_name"), "civil_people.person_name")
        existing_name = names_by_ref.get(person_ref)
        if existing_name is not None:
            if existing_name != person_name:
                raise ValueError("I5B 同一 person_ref 对应了不同人物名")
            continue
        names_by_ref[person_ref] = person_name
        unique.append(dict(raw) | {"person_ref": person_ref, "person_name": person_name})
    structured_selection = any(
        row.get("estimated_i5b_impact") or row.get("i5b_rule_lanes")
        for row in unique
    )
    if structured_selection:
        ranked: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []
        for input_order, row in enumerate(unique):
            impact_code = str(row.get("estimated_i5b_impact") or "medium").strip()
            if impact_code not in I5B_PERSON_IMPACT:
                raise ValueError("I5B 人物候选 estimated_i5b_impact 无效")
            lanes = tuple(
                dict.fromkeys(
                    str(value).strip()
                    for value in row.get("i5b_rule_lanes") or ()
                    if str(value).strip()
                )
            )
            unknown_lanes = sorted(set(lanes) - set(I5B_PERSON_SELECTION_LANES))
            if unknown_lanes:
                raise ValueError(f"I5B 人物候选包含未知规则入口: {unknown_lanes}")
            declared_priority = int(row.get("selection_priority") or 1_000_000)
            rank = (
                -I5B_PERSON_IMPACT[impact_code],
                -len(lanes),
                declared_priority,
                input_order,
            )
            ranked.append((rank, row | {"i5b_rule_lanes": list(lanes)}))
        ranked.sort(key=lambda item: item[0])

        # The wide pass is only a routing estimate, but every represented I5B
        # lane gets its strongest candidate before remaining slots are filled.
        chosen_refs: set[str] = set()
        for lane in I5B_PERSON_SELECTION_LANES:
            candidate = next(
                (row for _rank, row in ranked if lane in row["i5b_rule_lanes"]),
                None,
            )
            if candidate is not None:
                chosen_refs.add(str(candidate["person_ref"]))
        for _rank, row in ranked:
            if len(chosen_refs) >= limit:
                break
            chosen_refs.add(str(row["person_ref"]))
        selected = [
            row for _rank, row in ranked if str(row["person_ref"]) in chosen_refs
        ][:limit]
        selected_refs = {str(row["person_ref"]) for row in selected}
        deferred_source = [
            row for _rank, row in ranked if str(row["person_ref"]) not in selected_refs
        ]
    else:
        selected = unique[:limit]
        deferred_source = unique[limit:]
    deferred = [
        {
            "person_ref": str(row["person_ref"]),
            "person_name": str(row["person_name"]),
            "reason": "deferred_boundary_candidate",
        }
        for row in deferred_source
    ]
    return selected, deferred


def load_discovery_prompt_policy(path: Path) -> DiscoveryPromptPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Google AI discovery prompt policy 必须是 object")
    if payload.get("schema_version") != PROMPT_POLICY_SCHEMA_VERSION:
        raise ValueError("Google AI discovery prompt policy 版本不支持")
    template = _required_text(payload.get("template"), "template")
    authority_template = payload.get("authority_template")
    if authority_template is not None:
        authority_template = _required_text(authority_template, "authority_template")
    risk_template = payload.get("risk_template")
    if risk_template is not None:
        risk_template = _required_text(risk_template, "risk_template")
    for label, candidate in (
        ("template", template),
        ("authority_template", authority_template),
        ("risk_template", risk_template),
    ):
        if candidate is None:
            continue
        missing = sorted(item for item in REQUIRED_PLACEHOLDERS if item not in candidate)
        if missing:
            raise ValueError(f"Google AI discovery prompt {label} 缺少占位符: {missing}")
        forbidden = sorted(item for item in FORBIDDEN_PROMPT_PHRASES if item in candidate)
        if forbidden:
            raise ValueError(f"Google AI discovery prompt {label} 包含诱发伪引文的要求: {forbidden}")
    default_max_leads = int(payload.get("default_max_leads") or 0)
    maximum_max_leads = int(payload.get("maximum_max_leads") or 0)
    if not 0 <= default_max_leads <= maximum_max_leads <= 100:
        raise ValueError("Google AI discovery prompt 线索上限非法")
    return DiscoveryPromptPolicy(
        prompt_version=_required_text(payload.get("prompt_version"), "prompt_version"),
        status=_required_text(payload.get("status"), "status"),
        default_max_leads=default_max_leads,
        maximum_max_leads=maximum_max_leads,
        template=template,
        authority_template=authority_template,
        risk_template=risk_template,
    )


def _join(values: Sequence[str], *, empty: str) -> str:
    normalized = [str(value).strip() for value in values if str(value).strip()]
    return "；".join(normalized) if normalized else empty


def render_discovery_prompt(
    policy: DiscoveryPromptPolicy,
    *,
    subject_name: str,
    focus: str,
    search_categories: Sequence[str] = (),
    relevance_criteria: Sequence[str],
    requested_outputs: Sequence[str],
    aliases: Sequence[str] = (),
    allowed_lead_types: Sequence[str] = (),
    source_scope: str = "按当前焦点选择直接承载该事项的正史、编年史、政书、法典、诏令集或类书，不得机械罗列",
    max_leads: int | None = None,
    template_override: str | None = None,
) -> RenderedDiscoveryPrompt:
    lead_limit = policy.default_max_leads if max_leads is None else int(max_leads)
    if not 0 <= lead_limit <= policy.maximum_max_leads:
        raise ValueError("Google AI discovery prompt max_leads 超出策略上限")
    replacements = {
        "{{subject_name}}": _required_text(subject_name, "subject_name"),
        "{{focus}}": _required_text(focus, "focus"),
        "{{search_categories}}": _join(
            search_categories,
            empty="由检索焦点自然拆分为互不重复的类别",
        ),
        "{{relevance_criteria}}": _join(relevance_criteria, empty="未声明"),
        "{{requested_outputs}}": _join(requested_outputs, empty="未声明"),
        "{{aliases}}": _join(aliases, empty="无"),
        "{{lead_type_scope}}": _join(
            allowed_lead_types,
            empty="根据检索焦点只选一种 lead_type",
        ),
        "{{source_scope}}": _required_text(source_scope, "source_scope"),
        "{{max_leads}}": (
            "不限数量，以项目相关性、独立性和可回源性为准"
            if lead_limit == 0
            else f"最多 {lead_limit} 项"
        ),
    }
    if replacements["{{relevance_criteria}}"] == "未声明":
        raise ValueError("Google AI discovery prompt relevance_criteria 不得为空")
    if replacements["{{requested_outputs}}"] == "未声明":
        raise ValueError("Google AI discovery prompt requested_outputs 不得为空")
    text = template_override or policy.template
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    if "{{" in text or "}}" in text:
        raise ValueError("Google AI discovery prompt 存在未解析占位符")
    fingerprint = sha256(
        f"{policy.prompt_version}\n{text}".encode("utf-8")
    ).hexdigest()
    return RenderedDiscoveryPrompt(
        prompt_version=policy.prompt_version,
        text=text,
        fingerprint=fingerprint,
    )


def build_person_rebuild_manifest(
    policy: DiscoveryPromptPolicy,
    *,
    person_ref: str,
    person_name: str,
    input_version: str,
    aliases: Sequence[str] = (),
) -> dict[str, Any]:
    """构造一次人物重建所需的三项串行 discovery 任务。"""

    shared_outputs = ("source_locator_leads", "projection_direction")
    history = render_discovery_prompt(
        policy,
        subject_name=person_name,
        aliases=aliases,
        focus="人物重建所需的原子生平事件与重大人才成就文献地图",
        search_categories=(
            "影响人才等级的本人重大成就及结果",
            "影响团队成员身份或皇帝归责的实际履职节点",
        ),
        relevance_criteria=("HistoricalEpisode 重建", "人才等级重审"),
        requested_outputs=("原子事件线索", "候选书名、篇章或卷次与定位锚词", "画像投影方向"),
        allowed_lead_types=("event", "achievement"),
    )
    authority = render_discovery_prompt(
        policy,
        subject_name=person_name,
        aliases=aliases,
        focus="人才等级所需的权威评价文献地图",
        search_categories=(
            "同时代正式评价与相关皇帝制诏、裁断",
            "正史本传史臣曰、赞曰及相关本纪定调",
            "后世兵学家、将领或军事史家对统帅用兵与战功的直接专评",
        ),
        relevance_criteria=("人才等级重审",),
        requested_outputs=("独立评价线索", "候选书名、篇章或卷次与定位锚词", "评价维度"),
        allowed_lead_types=("authority_evaluation",),
        template_override=policy.authority_template,
    )
    risk = render_discovery_prompt(
        policy,
        subject_name=person_name,
        aliases=aliases,
        focus="本人可归责的政治风险与重大军事败绩",
        search_categories=(
            "滥用权力与非法压制",
            "贪腐侵夺与派系控制",
            "危害国家安全或军政治理的可归责行为",
            "本人统帅责任下的重大军事败绩及可观察损失",
        ),
        relevance_criteria=("负面政治风险与败绩重审", "风险 HistoricalEpisode 重建"),
        requested_outputs=("风险及败绩事件线索", "反证方向", "候选书名、篇章或卷次与定位锚词"),
        allowed_lead_types=("risk",),
        template_override=policy.risk_template,
    )
    tasks = (
        build_google_ai_discovery_task(
            history,
            task_code=f"PERSON-REBUILD-{person_ref}-HISTORY",
            input_version=input_version,
            purpose_code="person_rebuild_discovery",
            subject_ref=person_ref,
            subject_name=person_name,
            subject_aliases=aliases,
            requested_outputs=shared_outputs,
            downstream_context={
                "consumer": "person_rebuild_shadow",
                "possible_projections": [
                    "historical_episode_candidate",
                    "talent_profile_candidate",
                ],
            },
        ),
        build_google_ai_discovery_task(
            authority,
            task_code=f"PERSON-REBUILD-{person_ref}-AUTHORITY",
            input_version=input_version,
            purpose_code="authority_evaluation_discovery",
            subject_ref=person_ref,
            subject_name=person_name,
            subject_aliases=aliases,
            requested_outputs=shared_outputs,
            downstream_context={
                "consumer": "person_rebuild_shadow",
                "possible_projections": ["talent_profile_candidate"],
            },
        ),
        build_google_ai_discovery_task(
            risk,
            task_code=f"PERSON-REBUILD-{person_ref}-RISK",
            input_version=input_version,
            purpose_code="political_risk_discovery",
            subject_ref=person_ref,
            subject_name=person_name,
            subject_aliases=aliases,
            requested_outputs=shared_outputs,
            downstream_context={
                "consumer": "person_rebuild_shadow",
                "possible_projections": [
                    "historical_episode_candidate",
                    "political_risk_profile_candidate",
                ],
            },
        ),
    )
    return {"schema_version": "google-ai-browser-manifest-v1", "tasks": list(tasks)}


def build_i5b_discovery_manifest(
    policy: DiscoveryPromptPolicy,
    *,
    ruler_ref: str,
    ruler_name: str,
    ruler_dynasty: str,
    input_version: str,
    civil_people: Sequence[Mapping[str, Any]],
    max_person_retrieval_entries: int | None = None,
) -> dict[str, Any]:
    """Build serial I5B discovery tasks within the per-ruler person hard cap."""
    ruler_ref = _required_text(ruler_ref, "ruler_ref")
    ruler_name = _required_text(ruler_name, "ruler_name")
    ruler_dynasty = _required_text(ruler_dynasty, "ruler_dynasty")
    canonical_dynasty, source_scopes = load_i5b_source_search_scope(
        DEFAULT_I5B_SOURCE_SCOPE_PATH,
        dynasty=ruler_dynasty,
    )
    configured_person_limit = load_i5b_person_retrieval_limit()
    person_limit = (
        configured_person_limit
        if max_person_retrieval_entries is None
        else int(max_person_retrieval_entries)
    )
    if person_limit > configured_person_limit:
        raise ValueError("I5B 人物检索入口不得超过配置的单皇帝硬上限")
    selected_people, deferred_people = _select_i5b_civil_people(
        civil_people,
        limit=person_limit,
    )
    context = {
        "consumer": "i5b_shadow_source_backfill",
        "ruler_ref": ruler_ref,
        "ruler_name": ruler_name,
        "ruler_dynasty": canonical_dynasty,
        "formal_write_allowed": False,
    }
    tasks = []
    for priority, person in enumerate(selected_people, start=1):
        person_ref = _required_text(person.get("person_ref"), "civil_people.person_ref")
        person_name = _required_text(person.get("person_name"), "civil_people.person_name")
        aliases = tuple(str(value) for value in person.get("aliases") or ())
        rendered = render_discovery_prompt(
            policy,
            subject_name=person_name,
            aliases=aliases,
            focus="文官治理成果的文献地图",
            search_categories=("本人主导或实际负责的治理举措", "可观察的行政、制度或社会结果"),
            relevance_criteria=("I5B 用人与授权", "文臣治理成果补充"),
            requested_outputs=("独立治理线索", "候选书名、篇章或卷次与定位锚词", "归责与结果"),
            allowed_lead_types=("policy", "achievement"),
            source_scope=(
                "书名和章节仅作审计线索，不控制后续回源；可优先提示以下范围中的定位锚词："
                + "、".join(source_scopes["civil_governance_discovery"])
            ),
        )
        task_code = "I5B-CIVIL-" + sha256(
            f"{ruler_ref}\n{person_ref}".encode("utf-8")
        ).hexdigest()[:16].upper()
        tasks.append(
            build_google_ai_discovery_task(
                rendered,
                task_code=task_code,
                input_version=input_version,
                purpose_code="civil_governance_discovery",
                subject_ref=person_ref,
                subject_name=person_name,
                subject_aliases=aliases,
                requested_outputs=("source_locator_leads", "i5b_civil_candidate"),
                downstream_context=context
                | {
                    "i5b_scope": "civil_governance",
                    "person_retrieval_priority": priority,
                    "person_retrieval_limit": person_limit,
                },
            )
        )
    rendered = render_discovery_prompt(
        policy,
        subject_name=ruler_name,
        focus="皇帝政策与制度的文献地图",
        search_categories=("皇帝直接制定或裁定的用人政策", "影响官僚运行的制度与可观察结果"),
        relevance_criteria=("I5B 用人与授权", "皇帝政策制度"),
        requested_outputs=("独立政策线索", "候选书名、篇章或卷次与定位锚词", "政策机制与结果"),
        allowed_lead_types=("policy",),
        source_scope=(
            "书名和章节仅作审计线索，不控制后续回源；不要为扩充答案机械罗列，"
            "可优先提示以下范围中的定位锚词："
            + "、".join(source_scopes["ruler_policy_discovery"])
        ),
    )
    tasks.append(
        build_google_ai_discovery_task(
            rendered,
            task_code="I5B-POLICY-" + sha256(ruler_ref.encode("utf-8")).hexdigest()[:16].upper(),
            input_version=input_version,
            purpose_code="ruler_policy_discovery",
            subject_ref=ruler_ref,
            subject_name=ruler_name,
            requested_outputs=("source_locator_leads", "i5b_policy_candidate"),
            downstream_context=context | {"i5b_scope": "ruler_policy"},
        )
    )
    return {
        "schema_version": "google-ai-browser-manifest-v1",
        "tasks": tasks,
        "i5b_selection": {
            "max_person_retrieval_entries": person_limit,
            "selected_person_count": len(selected_people),
            "selected_person_refs": [str(row["person_ref"]) for row in selected_people],
            "policy_entry_count": 1,
            "policy_entry_counts_against_person_limit": False,
            "selection_order": "input_priority_after_person_ref_deduplication",
            "deferred_people": deferred_people,
        },
    }


def build_google_ai_discovery_task(
    rendered: RenderedDiscoveryPrompt,
    *,
    task_code: str,
    input_version: str,
    purpose_code: str,
    subject_ref: str,
    subject_name: str,
    subject_aliases: Sequence[str] = (),
    requested_outputs: Sequence[str],
    downstream_context: Mapping[str, Any],
    response_timeout_seconds: int = 30,
) -> dict[str, Any]:
    return {
        "task_code": _required_text(task_code, "task_code"),
        "input_version": (
            f"{_required_text(input_version, 'input_version')}+{rendered.prompt_version}"
        ),
        "purpose_code": _required_text(purpose_code, "purpose_code"),
        "subject_ref": _required_text(subject_ref, "subject_ref"),
        "subject_name": _required_text(subject_name, "subject_name"),
        "subject_aliases": [str(value).strip() for value in subject_aliases if str(value).strip()],
        "query": rendered.text,
        "requested_outputs": [str(value) for value in requested_outputs],
        "downstream_context": dict(downstream_context)
        | {
            "discovery_prompt_version": rendered.prompt_version,
            "discovery_prompt_fingerprint": rendered.fingerprint,
        },
        "quality_requirements": {
            "min_answer_characters": 200,
            "min_source_links": 0,
            "require_subject_mention": True,
            "require_locator_hints": True,
        },
        "response_timeout_seconds": response_timeout_seconds,
        # 30 seconds is the generation SLA; the extension keeps the same page
        # open for one additional 30-second capture tail before it gives up.
        "lease_seconds": max(90, response_timeout_seconds + 60),
        "max_attempts": 2,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成一个人物的 HistoricalEpisode 与画像重建宽搜 manifest"
    )
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--person-ref")
    parser.add_argument("--person-name")
    parser.add_argument("--input-version", required=True)
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument(
        "--purpose-code",
        choices=(
            "person_rebuild_discovery",
            "authority_evaluation_discovery",
            "political_risk_discovery",
        ),
    )
    parser.add_argument("--i5b-ruler-ref")
    parser.add_argument("--i5b-ruler-name")
    parser.add_argument("--i5b-ruler-dynasty")
    parser.add_argument(
        "--civil-people",
        type=Path,
        help="UTF-8 JSON array: [{person_ref, person_name, aliases?}]",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    i5b_mode = bool(
        args.i5b_ruler_ref
        or args.i5b_ruler_name
        or args.i5b_ruler_dynasty
        or args.civil_people
    )
    if i5b_mode:
        if not (
            args.i5b_ruler_ref
            and args.i5b_ruler_name
            and args.i5b_ruler_dynasty
            and args.civil_people
        ):
            raise ValueError("I5B manifest 必须提供皇帝 ref、皇帝名、朝代和 --civil-people")
        if args.purpose_code or args.person_ref or args.person_name or args.alias:
            raise ValueError("I5B manifest 不得混用人物重建参数")
        civil_people = json.loads(args.civil_people.read_text(encoding="utf-8"))
        if not isinstance(civil_people, list):
            raise ValueError("--civil-people 必须是 JSON array")
        payload = build_i5b_discovery_manifest(
            load_discovery_prompt_policy(args.policy),
            ruler_ref=args.i5b_ruler_ref,
            ruler_name=args.i5b_ruler_name,
            ruler_dynasty=args.i5b_ruler_dynasty,
            input_version=args.input_version,
            civil_people=civil_people,
        )
    else:
        if not (args.person_ref and args.person_name):
            raise ValueError("人物重建 manifest 必须提供 --person-ref 和 --person-name")
        payload = build_person_rebuild_manifest(
            load_discovery_prompt_policy(args.policy),
            person_ref=args.person_ref,
            person_name=args.person_name,
            input_version=args.input_version,
            aliases=args.alias,
        )
    if args.purpose_code:
        payload["tasks"] = [
            task
            for task in payload["tasks"]
            if task["purpose_code"] == args.purpose_code
        ]
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    encoded = rendered.encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.is_file() and args.output.read_bytes() == encoded:
        return 0
    temporary = args.output.with_name(f".{args.output.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, args.output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
