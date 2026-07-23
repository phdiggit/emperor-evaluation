from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from opencc import OpenCC

from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.evaluation.current_source_pack_compiler import (
    apply_source_pack_increment,
    compile_outcome_candidate_payloads,
)
from emperor_v4.runtime.structured_codex_runner import (
    ModelBatchAnomalyError,
    StructuredCodexRunner,
)


SCHEMA_VERSION = "current-outcome-projection-v1"
PROJECTION_POLICY_VERSION = "current-outcome-projection-policy-v18"
LEGACY_PROJECTION_POLICY_VERSION = "current-outcome-projection-policy-v6"
_T2S = OpenCC("t2s")


def build_outcome_transport_schema(schema_path: Path) -> dict[str, Any]:
    """Remove API-unsupported conditionals from the model transport schema.

    The repository schema remains the acceptance contract used by
    ``compile_outcome_candidate_payloads``.  Outcome-specific campaign and
    governance invariants are also enforced deterministically there, after the
    model response is received.
    """

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def strip(node: object) -> object:
        if isinstance(node, list):
            return [strip(value) for value in node]
        if not isinstance(node, Mapping):
            return node
        result = {
            str(key): strip(value)
            for key, value in node.items()
            if key not in {"allOf", "if", "then", "else"}
        }
        properties = result.get("properties")
        if isinstance(properties, Mapping):
            original_required = {
                str(value) for value in node.get("required") or ()
            }
            for name, child in properties.items():
                if name in original_required or not isinstance(child, Mapping):
                    continue
                types = child.get("type")
                if isinstance(types, str):
                    child["type"] = [types, "null"]
                elif isinstance(types, list) and "null" not in types:
                    child["type"] = [*types, "null"]
                enum = child.get("enum")
                if isinstance(enum, list) and None not in enum:
                    child["enum"] = [*enum, None]
            result["required"] = list(properties)
        return result

    return dict(strip(schema))


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _prompt(
    *,
    ruler: str,
    ruler_window: str,
    actors: Sequence[str],
    existing_outcomes: Sequence[Mapping[str, Any]],
    facts: Sequence[Mapping[str, Any]],
    task_code: str,
) -> str:
    prompt_facts = []
    for fact in facts:
        prompt_fact = {
            key: fact[key]
            for key in (
                "segment_ref",
                "event_refs",
                "exact_quote",
                "fact_kind",
                "governance_domain",
                "governance_title",
                "period",
                "action_summary",
                "implementation_status",
                "result",
                "uncertainty",
            )
            if key in fact
        }
        prompt_fact["actors"] = [
            {
                "name": str(actor.get("canonical_name") or ""),
                "source_name": str(actor.get("source_name") or ""),
                "role": str(actor.get("role") or ""),
                "strength": str(actor.get("responsibility_strength") or ""),
            }
            for actor in fact.get("actors") or ()
        ]
        prompt_facts.append(prompt_fact)
    return f"""你是皇帝评价 V4 的成果候选整理器。只把输入的中性事实整理为可登记的战役、治理或人物谋略成果；不能补史实、不能联网、不能评分。

硬规则：
1. 只有原文同时足以支持行动、可观察结果和参与者责任时才生成 candidate；任官、褒奖、建议、品评或单纯过程而无结果，一律放入 rejections。
2. exact_quotes 与 authorization_quotes 必须逐字复制输入 exact_quote 的连续子串，不得转写、拼接或补字。
3. members 只能使用允许人物：{json.dumps(list(actors), ensure_ascii=False)}。皇帝 {ruler} 用 actor_kind=ruler；其余用 person。
4. 同一独立结果只生成一个 candidate。candidate_key 用小写 ASCII 与连字符，表达皇帝、时期和独立结果，必须稳定。
5. campaign 必须填写 strategic_result_class、campaign_tier、campaign_tier_basis、land_strategic_value、opponent_strategic_weight、opponent_condition、combat_difficulty、combat_difficulty_basis，并分别填写 operational_costs、objective_shortfalls、attributable_failures；治理字段填 null。campaign_tier 只按 strategic_result_class 固定映射：local_tactical=C、important_objective=B、major_stage_or_crisis=A、independent_direction=S-、single_pole_or_state_terminal=S、composite_poles_terminal/unification_terminal/external_hegemony_terminal=S+。S+ 只能走这三条终局路径。对手权重只能表示当时竞争体系位置：minor、regional_major、first_tier_pole、dominant_pole、external_state、external_hegemony、unclear。campaign_tier_basis 固定写成“土地轴=<规范值>；对手轴=<战略权重>/<交战状态>；结果轴=<战果>/<目标完成度>，<定级解释>”。作战难度 D0–D3 另行判断且不得改变字母级：D0=残余或显著优势，D1=常态可战，D2=强主力/坚城/复杂地形后勤，D3=极端兵力态势、霸权压迫、连续击败本方主力或近崩溃逆转；必须用当时事实说明。正常动员、追击、受伤和敌军来援不得自动算负面。实际兵力或机动力损耗写 operational_costs；目标未完成写 objective_shortfalls；只有原文明示责任时才写 attributable_failures，并逐项给出责任人、责任类型、严重度、依据与逐字引文。不得把作战难度重复登记为成本或失败。
6. 必须先完全忽略皇帝窗口，判断事实能否形成独立战役、治理或谋略成果；窗口不明不得成为拒绝成果的理由。成果成立后才填写兼容性的后置绑定提示 ruler_window_status：在位期填 within_window；{ruler} 登基前已取得独立统军权并对战役负核心责任的成果填 leadership_formation；其他时期填 outside_window；确实无法解析填 unresolved，等待绑定层复核。
7. 战争最多三层：war_terminal_context 只表达整个统一战争的总终局，不进入 C1 或人才结算；ruler_campaign_parent 表达可独立定级的战役群；person_campaign_subresult 仅用于同一战役群内确有独立指挥、独立结果的人物子成果并给 parent_outcome_ref。祖先与后代不得重复结算。当前皇帝窗口治理填 governance_result；臣子全生涯中其他皇帝窗口的独立治理成果填 person_governance_result；粮价、人口、生产或治安等宏观结果填 reign_macro_outcome；非指挥、非公共治理但已被采纳并形成独立战略结果的谋略填 person_statecraft_result。谋略只供人物画像消费，不进入皇帝治理投影。宏观结果若史源上下文明确归于皇帝总体治理，causal_attribution_status=source_attributed 且皇帝可为 lead；若只有统治窗口关系则填 limited/reign_holder。
8. 奏疏、谏言和批评只证明臣下提出主张，不能单独证明被批评现象或公共后果已经发生；没有独立实施或结果史源时拒绝治理成果候选，但保留中性材料供 I5A 欲望与自我约束或其他相应规则消费。
9. 完成并投入国家使用的一代正史、跨代通史或大型文化典籍通常至少填 national_cultural_corpus；例行修成单朝皇帝实录通常只属 important，除非完整国家史体系的规模、使用和长期影响另有直接史源。只有作品开创文明范式、长期成为基础文本且本人实际独著、主编或最终定稿，才填 civilization_foundational_corpus/era_shaping/foundational。官修不自动降档，但授权、总裁、主修、分卷撰修和挂名参与必须分别归责。
10. 规模只按原文可支持的影响范围，不因人物名气上调；不确定就拒绝或 limitations 明示。
11. campaign 的 role_code 只能是 commander_in_chief/principal_commander/participant/not_in_command_chain，并至少有一名处于实际军事指挥链的成员。commander_in_chief=节度战役群全局并承担最高军事责任；principal_commander=独立指挥一支主力或主要方向；participant=有作战贡献但无主力独立指挥权。史书称某人为主帅之副时，仍按实际指挥权在 principal_commander 与 participant 之间判断，不另设副将档。within_window/leadership_formation 的父级战役群必须且只能有一个当前皇帝成员；outside_window 的臣子全生涯战役允许没有当前皇帝，不得因此删除。只要登记皇帝成员就必须填唯一皇权关系。皇帝只有授权、默许或阻挠而未实际进入军事指挥链时用 not_in_command_chain；亲征、长期统筹或临时坐镇不得用 not_in_command_chain。governance/statecraft 只能是 exclusive/lead/governance_participant/authorized：exclusive=独立建立且没有同级共同主导者，lead=主导方案或持续执行，governance_participant=有逐字依据的实质参与，authorized=仅批准或维持授权而未主导实施；参会、在职和一般赞同不能推定责任。
12. campaign 成员必须区分“事件发生时的实际皇帝”与“当前评价对象”：只有 sovereign_at_event=true 的皇帝成员可以填写皇权控制。ruler_campaign_relation 只分 authorization_only、operational_direction、frontline_command；授权明示/默示另填 authorization_mode，战区控制局部/持续另填 control_extent，阻挠另填 obstruction_status。登基前的李世民是臣子，不得填写皇帝关系。详细制定分路、进军路线或作战部署属于 operational_direction；本人进入前线并承担最高现场指挥才是 frontline_command。
13. EXISTING_OUTCOMES 已登记的同一独立结果必须拒绝，不得换名重复生成；同一战略目标建立一个父级战役成果，阶段战斗只写入 observable_result/limitations，不得拆成多项重复成果。全局战果有得有失时父级必须 mixed；例如远征总体未达目标但取得局部胜利，不能只按局部胜利登记。规模必须同时检查土地战略价值、对手实际强度和已实现结果，不因国号、名气或史料篇幅升档。
14. governance 只登记已经实施并形成制度、持续程序、跨个案公共效果、明确先例或可独立验收公共产品的结果。迁都、设官、建机构、任命、结约或颁下一次命令若只证明动作发生，没有制度实际生效、持续运行、直接改变公共权利义务或形成可验收产品，必须拒绝；不得用预期目的代替实际结果。已实际生效并直接改变税负、服役、任期或司法程序的持续约束，其制度约束本身可作为结果。单案改判、一次礼遇、个人赏罚、一般言行和仅对一人的处置放入 rejections。
15. statecraft 只登记本人提出或主导、已被采纳并形成独立可核实战略结果的非指挥成果。未实施建议、一般献策、纯夺权、宫廷清洗和只有手段成功而无独立战略结果者必须拒绝；不得为支撑预期人才等级反向生成谋略成果。
16. 带有同一 event_refs 的跨书事实属于同一中性事件，只能合并判断，不得按史书重复生成成果。
17. 输出严格符合 schema；schema_version=current-outcome-candidate-output-v2，task_code={task_code}。
18. INPUT_FACTS 中每个 segment_ref 必须恰有明确处置：生成 candidate 时 exact_quotes 必须覆盖对应输入引文；否则必须在 rejections 中逐项写出 segment_ref 和理由。不得遗漏输入事实。
19. 同一段引文若同时包含彼此独立的战役结果与治理结果，必须分别生成 candidate，不得把治理结果并入战役 observable_result，也不得用其中一个 candidate 代替另一个。明确记载“遂克长安”时必须形成 campaign 候选；明确记载“与民约法……悉除……苛禁”时必须另形成 governance 候选。

EXISTING_OUTCOMES:
{json.dumps(list(existing_outcomes), ensure_ascii=False, sort_keys=True, separators=(",", ":"))}

INPUT_FACTS:
{json.dumps(prompt_facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))}
"""


def _known_quotes(source_pack: Mapping[str, Any]) -> set[str]:
    return {
        str(assertion["exact_quote"])
        for fact in source_pack.get("facts") or ()
        for assertion in fact.get("assertions") or ()
        if assertion.get("exact_quote")
    }


def _accepted_source_quotes(
    source_pack: Mapping[str, Any]
) -> dict[tuple[str, str], set[str]]:
    accepted: dict[tuple[str, str], set[str]] = {}
    for fact in source_pack.get("facts") or ():
        if not str(fact.get("record_ref") or "").startswith("PFACT-AUTO-"):
            continue
        key = (str(fact["source_page"]), str(fact["revision_ref"]))
        accepted.setdefault(key, set()).update(
            str(row["exact_quote"])
            for row in fact.get("assertions") or ()
            if row.get("exact_quote")
        )
    return accepted


def _expand_fact_quote_to_same_revision_paragraph(
    fact: Mapping[str, Any],
    *,
    pages_by_title: Mapping[str, Any],
    max_chars: int = 1200,
) -> dict[str, Any]:
    expanded = dict(fact)
    page = pages_by_title.get(str(fact.get("page_title") or ""))
    quote = str(fact.get("exact_quote") or "")
    if (
        page is None
        or page.revision_ref != str(fact.get("revision_ref") or "")
        or not quote
        or page.raw_text.count(quote) != 1
    ):
        return expanded
    position = page.raw_text.index(quote)
    boundaries = [
        match.span()
        for match in re.finditer(r"<BR>\s*(?:\r?\n)?|(?:\r?\n\s*){2,}", page.raw_text)
    ]
    start = max(
        (end for boundary_start, end in boundaries if boundary_start < position),
        default=0,
    )
    end = min(
        (
            boundary_start
            for boundary_start, _boundary_end in boundaries
            if boundary_start >= position + len(quote)
        ),
        default=len(page.raw_text),
    )
    paragraph = page.raw_text[start:end].strip()
    if quote in paragraph and len(paragraph) <= max_chars:
        expanded["exact_quote"] = paragraph
    return expanded


def _normalize_candidate_sources(
    payload: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any]:
    payload = dict(payload)
    # Older split-parent checkpoints accidentally carried a top-level helper
    # field that is not part of the candidate output contract.  Checkpoints are
    # disposable recovery state; normalize them before schema validation rather
    # than repeating already completed model calls.
    payload.pop("limitations", None)
    fact_quotes = [str(fact.get("exact_quote") or "") for fact in facts]

    def canonical_quote(value: object) -> str:
        quote = str(value)
        candidates = [quote]
        if quote.endswith(("。", "；", "，", "！", "？")):
            candidates.append(quote[:-1])
        for candidate_quote in candidates:
            normalized = _T2S.convert(candidate_quote)
            matches = set()
            for fact_quote in fact_quotes:
                start = _T2S.convert(fact_quote).find(normalized)
                if start >= 0:
                    candidate = fact_quote[start : start + len(candidate_quote)]
                    if _T2S.convert(candidate) == normalized:
                        matches.add(candidate)
            if len(matches) == 1:
                return next(iter(matches))
        return quote

    retained_candidates = []
    rejections = list(payload.get("rejections") or ())

    def reject_candidate(
        candidate: Mapping[str, Any],
        quote_matches: Sequence[Sequence[Mapping[str, Any]]],
        reason: str,
    ) -> None:
        for fact in {
            str(fact["segment_ref"]): fact
            for rows in quote_matches
            for fact in rows
        }.values():
            rejections.append(
                {
                    "segment_ref": str(fact["segment_ref"]),
                    "reason": f"{candidate['candidate_key']} {reason}",
                }
            )

    def content_bigrams(value: object) -> set[str]:
        normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", _T2S.convert(str(value)).lower())
        return {normalized[index : index + 2] for index in range(len(normalized) - 1)}

    for candidate in payload.get("candidates") or ():
        quotes = [canonical_quote(value) for value in candidate.get("exact_quotes") or ()]
        candidate["exact_quotes"] = quotes
        for member in candidate.get("members") or ():
            if member.get("actor_kind") == "ruler":
                member["talent_credit"] = "not_applicable"
            elif member.get("talent_credit") is None:
                member.pop("talent_credit", None)
            member["authorization_quotes"] = [
                canonical_quote(value)
                for value in member.get("authorization_quotes") or ()
            ]
        for field in (
            "operational_costs",
            "objective_shortfalls",
            "attributable_failures",
        ):
            for item in (candidate.get("payload") or {}).get(field) or ():
                item["exact_quotes"] = [
                    canonical_quote(value)
                    for value in item.get("exact_quotes") or ()
                ]
        quote_matches = [
            [
                fact
                for fact in facts
                if quote and quote in str(fact.get("exact_quote") or "")
            ]
            for quote in quotes
        ]
        matches = {
            (str(fact["page_title"]), str(fact["revision_ref"]))
            for rows in quote_matches
            for fact in rows
        }
        if not quotes or any(not rows for rows in quote_matches) or len(matches) != 1:
            continue
        limitation_text = "\n".join(
            str(value) for value in candidate.get("limitations") or ()
        ).lower()
        normalized_limitation = limitation_text.replace("`", "").replace(" ", "")
        disclaims_quote_support = (
            "exact_quote" in normalized_limitation
            and (
                any(
                    marker in normalized_limitation
                    for marker in (
                        "未在exact_quote中",
                        "exact_quote中未",
                        "exact_quote未",
                        "未由exact_quote",
                        "不受exact_quote",
                    )
                )
                or (
                    "依据来自" in normalized_limitation
                    and any(
                        marker in normalized_limitation
                        for marker in ("action_summary", "result字段")
                    )
                )
            )
        )
        if disclaims_quote_support:
            reject_candidate(
                candidate,
                quote_matches,
                "自认关键结果未由 exact_quote 直接支持，确定性拒绝并保留中性材料。",
            )
            continue
        matched_facts = [fact for rows in quote_matches for fact in rows]
        source_context = "".join(
            str(fact.get("exact_quote") or "") for fact in matched_facts
        )
        simplified_source_context = _T2S.convert(source_context)
        candidate_summary = "".join(
            str(candidate.get(key) or "")
            for key in ("canonical_label", "neutral_summary", "observable_result")
        )
        simplified_candidate_summary = _T2S.convert(candidate_summary)
        palace_seizure_context = (
            "玄武门" in simplified_candidate_summary
            or "玄武门" in simplified_source_context
            or (
                "太子、齐王作乱" in simplified_source_context
                and "举兵诛之" in simplified_source_context
            )
            or "秦王已讨而诛之" in simplified_source_context
        )
        if (
            candidate.get("outcome_kind") in {"governance", "statecraft"}
            and palace_seizure_context
        ):
            reject_candidate(
                candidate,
                quote_matches,
                "属于夺权或宫廷清洗的直接收束，不得登记为治理或谋略成果。",
            )
            continue
        li_yuan_pre_accession_context = (
            any(
                member.get("actor_kind") == "ruler"
                and member.get("actor_name") == "李渊"
                for member in candidate.get("members") or ()
            )
            and "唐公" in simplified_source_context
            and "代王" in simplified_source_context
        )
        if li_yuan_pre_accession_context:
            candidate["ruler_window_status"] = (
                "leadership_formation"
                if candidate.get("outcome_kind") == "campaign"
                else "outside_window"
            )
            candidate["period_start"] = "创业期"
            candidate["period_end"] = "创业期"
        if (
            candidate.get("ruler_window_status") == "leadership_formation"
            and not any(str(fact.get("period") or "").strip() for fact in matched_facts)
        ):
            candidate["period_start"] = "创业期"
            candidate["period_end"] = "创业期"
        quote_text = "".join(quotes)
        candidate_payload = candidate.get("payload") or {}
        if (
            candidate.get("outcome_kind") == "campaign"
            and candidate_payload.get("battle_result") == "victory"
            and candidate_payload.get("objective_completion") == "complete"
            and not re.search(r"[克破败降平定捷斩擒獲获拔]|下之", quote_text)
        ):
            reject_candidate(
                candidate,
                quote_matches,
                "声称战役胜利并完成目标，但 exact_quote 缺少结果信号，"
                "确定性拒绝并保留中性材料。",
            )
            continue
        result_bigrams = content_bigrams(candidate.get("observable_result") or "")
        quote_bigrams = {
            pair for quote in quotes for pair in content_bigrams(quote)
        }
        limitation_admits_missing_input = any(
            marker in normalized_limitation
            for marker in ("输入未", "原文未", "引文未", "史料未")
        )
        if (
            candidate.get("outcome_kind") in {"governance", "statecraft"}
            and limitation_admits_missing_input
            and result_bigrams
            and not result_bigrams.intersection(quote_bigrams)
        ):
            reject_candidate(
                candidate,
                quote_matches,
                "limitations 承认输入缺项，且 observable_result 与 exact_quote "
                "无实质词组重合，确定性拒绝并保留中性材料。",
            )
            continue
        if (
            candidate.get("outcome_kind") == "governance"
            and candidate.get("settlement_scope") != "reign_macro_outcome"
        ):
            window_status = candidate.get("ruler_window_status")
            if window_status == "outside_window":
                candidate["settlement_scope"] = "person_governance_result"
            elif window_status in {"within_window", "leadership_formation"}:
                candidate["settlement_scope"] = "governance_result"
        if (
            candidate.get("outcome_kind") == "governance"
            and candidate_payload.get("durable_cross_stage") is True
            and "未说明" in limitation_text
            and any(
                marker in limitation_text
                for marker in ("持续执行", "制度寿命", "后续")
            )
        ):
            candidate_payload["durable_cross_stage"] = False
        if candidate.get("outcome_kind") == "campaign":
            basis = str(candidate_payload.get("campaign_tier_basis") or "")
            explanation = basis.split("，", 1)[1] if "，" in basis else basis
            candidate_payload["campaign_tier_basis"] = (
                f"土地轴={candidate_payload['land_strategic_value']}；"
                f"对手轴={candidate_payload['opponent_strategic_weight']}/"
                f"{candidate_payload['opponent_condition']}；"
                f"结果轴={candidate_payload['battle_result']}/"
                f"{candidate_payload['objective_completion']}，{explanation}"
            )
        if (
            candidate.get("outcome_kind") in {"governance", "statecraft"}
            and candidate.get("scale_basis") == "local_public_result"
            and candidate.get("stable_delivery") is not True
            and candidate.get("important_method_or_legacy") is not True
        ):
            # Keep the neutral fact and its Episode lineage, but do not turn a
            # one-off local disposition into an independent governance result.
            continue
        page_title, revision_ref = next(iter(matches))
        candidate["source_page"] = page_title
        candidate["revision_ref"] = revision_ref
        retained_candidates.append(candidate)
    payload["candidates"] = retained_candidates
    payload["rejections"] = rejections
    return payload


def _validate_candidate_payload_coverage(
    payload: Mapping[str, Any],
    facts: Sequence[Mapping[str, Any]],
) -> None:
    covered_segment_refs = {
        str(row["segment_ref"]) for row in payload.get("rejections") or ()
    }
    for candidate in payload.get("candidates") or ():
        quotes = [str(value) for value in candidate.get("exact_quotes") or ()]
        for fact in facts:
            fact_quote = str(fact.get("exact_quote") or "")
            if any(
                quote in fact_quote or fact_quote in quote
                for quote in quotes
                if quote and fact_quote
            ):
                covered_segment_refs.add(str(fact["segment_ref"]))
    expected_segment_refs = {str(fact["segment_ref"]) for fact in facts}
    missing = sorted(expected_segment_refs - covered_segment_refs)
    if missing:
        raise ValueError("成果模型遗漏输入 segment_ref: " + ", ".join(missing))
    for fact in facts:
        fact_quote = _T2S.convert(str(fact.get("exact_quote") or ""))
        if "遂克长安" in fact_quote:
            has_campaign_candidate = any(
                candidate.get("outcome_kind") == "campaign"
                and any(
                    str(quote) in str(fact.get("exact_quote") or "")
                    or str(fact.get("exact_quote") or "") in str(quote)
                    for quote in candidate.get("exact_quotes") or ()
                )
                for candidate in payload.get("candidates") or ()
            )
            if not has_campaign_candidate:
                raise ValueError(
                    f"{fact['segment_ref']} 明确战役结果未形成独立 campaign 候选"
                )
        if not (
            "与民约法" in fact_quote
            and "悉除" in fact_quote
            and "苛禁" in fact_quote
        ):
            continue
        has_governance_candidate = any(
            candidate.get("outcome_kind") == "governance"
            and any(
                str(quote) in str(fact.get("exact_quote") or "")
                or str(fact.get("exact_quote") or "") in str(quote)
                for quote in candidate.get("exact_quotes") or ()
            )
            for candidate in payload.get("candidates") or ()
        )
        if not has_governance_candidate:
            raise ValueError(
                f"{fact['segment_ref']} 明确法律结果未形成独立 governance 候选"
            )


def project_current_outcomes(
    *,
    source_pack_path: Path,
    neutral_materials: Mapping[str, Any],
    source_index: LocalSourceTextIndex,
    schema_path: Path,
    runner: StructuredCodexRunner | None,
    checkpoint_dir: Path,
    workspace_root: Path,
    max_workers: int,
    facts_per_call: int = 16,
    reviewed_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project new neutral facts and atomically apply the validated increment.

    A fact whose exact quote is already in the current source pack is settled and
    never sent to the model again. Checkpoints are disposable failure recovery;
    the source pack itself is the only successful-run state.
    """

    source_pack = json.loads(source_pack_path.read_text(encoding="utf-8"))
    known_quotes = _known_quotes(source_pack)
    # Accepted business output is invalidated only by projection semantics.  A
    # model, schema transport, batch size, or worker-count change is scheduling
    # metadata and must not force every accepted outcome through the model again.
    policy_fingerprint = str(
        _digest({"projection_policy": PROJECTION_POLICY_VERSION})
    )
    legacy_policy_fingerprint = str(
        _digest(
            {
                "runner": getattr(runner, "policy_fingerprint", "settled-without-model"),
                "projection_policy": LEGACY_PROJECTION_POLICY_VERSION,
            }
        )
    )
    current_projection = neutral_materials.get("outcome_projection") or {}
    compatible_policy_fingerprints = {
        policy_fingerprint,
        legacy_policy_fingerprint,
    }
    current_projection_compatible = (
        current_projection.get("policy_fingerprint")
        in compatible_policy_fingerprints
    )
    # A main-session review payload is an audited increment over the current
    # source pack.  It is not guaranteed to repeat accepted outcomes whose
    # evidence came from an earlier shared source layer and is absent from the
    # current neutral worklist.  Only autonomous/model regeneration may replace
    # the complete AUTO projection.
    full_refresh = (
        not current_projection_compatible and reviewed_payload is None
    )
    dispositions = {
        str(row["fact_ref"]): dict(row)
        for row in current_projection.get("dispositions") or ()
        if current_projection_compatible
    }
    accepted_quotes = {} if full_refresh else _accepted_source_quotes(source_pack)
    allowed_subject_refs = {
        str(source_pack["ruler_ref"]),
        *(str(row["person_ref"]) for row in source_pack.get("members") or ()),
    }
    ruler_projection = neutral_materials.get("ruler_neutral_projection") or {}
    projected_backbone_fact_refs = {
        str(value) for value in ruler_projection.get("backbone_fact_refs") or ()
    }

    def in_current_ruler_projection(fact: Mapping[str, Any]) -> bool:
        source_role = str(fact.get("source_role") or "")
        if source_role == "dynasty_governance":
            return fact.get("ruler_window_match") is True
        if not source_role and ruler_projection:
            return str(fact.get("fact_ref") or "") in projected_backbone_fact_refs
        return True

    all_eligible = [
        dict(fact)
        for fact in (neutral_materials.get("fanout") or {}).get("facts") or ()
        if in_current_ruler_projection(fact)
        and any(
            str(actor.get("subject_ref") or "") in allowed_subject_refs
            for actor in fact.get("actors") or ()
        )
        and fact.get("projection_eligibility") == "direct_neutral_fact"
        and fact.get("implementation_status")
        in {"adopted", "implemented", "nationally_promulgated", "completed_work"}
        and bool(str(fact.get("result") or "").strip())
        and fact.get("fact_kind") not in {"appointment", "admonition"}
    ]
    for fact in all_eligible:
        fact.setdefault("fact_ref", "NEUTRALFACT-" + _digest(fact)[:20].upper())
        fact.setdefault("segment_ref", str(fact["fact_ref"]))
        if fact.get("outcome_candidate_status") == "clear_non_candidate":
            dispositions[str(fact["fact_ref"])] = {
                "fact_ref": str(fact["fact_ref"]),
                "decision": "rejected",
                "reason": str(
                    fact.get("outcome_candidate_reason")
                    or "中性抽取已判定不构成治理成果或战役候选。"
                ),
            }
    current_fact_refs = {str(fact["fact_ref"]) for fact in all_eligible}
    dispositions = {
        fact_ref: row
        for fact_ref, row in dispositions.items()
        if fact_ref in current_fact_refs
    }
    for fact in all_eligible:
        fact_ref = str(fact["fact_ref"])
        if fact_ref in dispositions:
            continue
        source_quotes = accepted_quotes.get(
            (str(fact.get("page_title") or ""), str(fact.get("revision_ref") or "")),
            set(),
        )
        exact_quote = str(fact.get("exact_quote") or "")
        if exact_quote in known_quotes or any(
            quote in exact_quote or exact_quote in quote for quote in source_quotes
        ):
            dispositions[fact_ref] = {
                "fact_ref": fact_ref,
                "decision": "accepted",
                "reason": "当前 source-pack 已含同源逐字成果引文。",
            }
    eligible = [
        fact
        for fact in all_eligible
        if str(fact["fact_ref"]) not in dispositions
        and fact.get("outcome_candidate_status") != "clear_non_candidate"
    ]
    if not eligible:
        return {
            "schema_version": SCHEMA_VERSION,
            "candidate_count": 0,
            "rejection_count": 0,
            "model_call_count": 0,
            "source_pack_changed": False,
            "policy_fingerprint": policy_fingerprint,
            "dispositions": [dispositions[key] for key in sorted(dispositions)],
        }
    if source_index is None:
        raise ValueError("待投射成果事实必须提供固定 revision 史源索引")
    eligible_pages = {
        page.page_title: page
        for page in source_index.iter_pages(
            works=sorted(
                {
                    str(fact["page_title"]).split("/", 1)[0]
                    for fact in eligible
                    if fact.get("page_title")
                }
            ),
            page_titles=sorted(
                {
                    str(fact["page_title"])
                    for fact in eligible
                    if fact.get("page_title")
                }
            ),
        )
    }
    eligible = [
        _expand_fact_quote_to_same_revision_paragraph(
            fact,
            pages_by_title=eligible_pages,
        )
        for fact in eligible
    ]
    ordered_eligible = sorted(
        eligible,
        key=lambda row: (
            str(row["page_title"]),
            str(row["segment_ref"]),
            str(row["fact_ref"]),
        ),
    )
    atomic_groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
    for fact in ordered_eligible:
        event_refs = tuple(sorted(str(value) for value in fact.get("event_refs") or ()))
        key = event_refs or (str(fact["fact_ref"]),)
        atomic_groups.setdefault(key, []).append(fact)
    groups: list[list[Mapping[str, Any]]] = []
    group: list[Mapping[str, Any]] = []
    for key in sorted(atomic_groups):
        event_facts = atomic_groups[key]
        if group and len(group) + len(event_facts) > facts_per_call:
            groups.append(group)
            group = []
        group.extend(event_facts)
        if len(group) >= facts_per_call:
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    actor_names = [
        str(source_pack["ruler"]),
        *[str(row["person"]) for row in source_pack.get("members") or ()],
    ]
    existing_outcomes = [
        {
            "independent_key": row["independent_key"],
            "canonical_label": row["canonical_label"],
            "outcome_kind": row["outcome_kind"],
            "period": row["period"],
            "members": [member["actor_name"] for member in row["members"]],
        }
        for row in (source_pack.get("outcome_registry") or {}).get("clusters") or ()
        if not str(row.get("outcome_ref") or "").startswith("OUTCOME-AUTO-")
    ]
    review_task_code = "OUTCOME-REVIEW-" + _digest(
        {
            "ruler": source_pack["ruler"],
            "facts": ordered_eligible,
            "projection_policy": PROJECTION_POLICY_VERSION,
        }
    )[:20].upper()
    if reviewed_payload is None and runner is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "awaiting_main_session_review",
            "candidate_count": 0,
            "rejection_count": 0,
            "model_call_count": 0,
            "source_pack_changed": False,
            "policy_fingerprint": policy_fingerprint,
            "dispositions": [dispositions[key] for key in sorted(dispositions)],
            "review_worklist": {
                "schema_version": "current-outcome-main-review-worklist-v1",
                "task_code": review_task_code,
                "ruler": str(source_pack["ruler"]),
                "ruler_window": str(source_pack["window"]),
                "allowed_actors": actor_names,
                "existing_outcomes": existing_outcomes,
                "facts": ordered_eligible,
                "required_output_schema": str(schema_path),
                "output_template": {
                    "schema_version": "current-outcome-candidate-output-v2",
                    "task_code": review_task_code,
                    "candidates": [],
                    "rejections": [],
                },
                "instructions": [
                    "主会话逐项登记战役、治理、谋略成果或明确拒绝。",
                    "每个 segment_ref 必须由 candidate exact_quotes 覆盖或进入 rejections。",
                    "完成跨书归并、成果拆分、责任、窗口、等级、持续性和重复结算审计后再提交。",
                ],
            },
        }

    reviewed_mode = reviewed_payload is not None
    payloads: list[Mapping[str, Any]] = []
    if reviewed_mode:
        payload = {
            **dict(reviewed_payload or {}),
            "schema_version": "current-outcome-candidate-output-v2",
            "task_code": review_task_code,
        }
        payload = _normalize_candidate_sources(payload, ordered_eligible)
        _validate_candidate_payload_coverage(payload, ordered_eligible)
        payloads.append(payload)
        actual_model_calls = 0
    else:
        if runner is None:
            raise ValueError("成果模型草案模式缺少 runner")

    def make_item(group: Sequence[Mapping[str, Any]]):
        assert runner is not None
        input_fingerprint = _digest(
            {
                "ruler": source_pack["ruler"],
                "facts": group,
                "runner_policy": runner.policy_fingerprint,
            }
        )
        task_code = "OUTCOME-AUTO-" + input_fingerprint[:20].upper()
        checkpoint = checkpoint_dir / f"{task_code}.json"
        return task_code, group, input_fingerprint, checkpoint

    def load_checkpoint(item):
        _, group, input_fingerprint, checkpoint = item
        if checkpoint.is_file():
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            if saved.get("input_fingerprint") == input_fingerprint:
                payload = _normalize_candidate_sources(saved["payload"], group)
                try:
                    _validate_candidate_payload_coverage(payload, group)
                except ValueError:
                    return None
                return payload
        return None

    pending = []
    if not reviewed_mode:
        for group in groups:
            item = make_item(group)
            saved = load_checkpoint(item)
            if saved is not None:
                payloads.append(saved)
            else:
                pending.append(item)

    def invoke(item: tuple[str, Sequence[Mapping[str, Any]], str, Path]):
        assert runner is not None
        task_code, group, input_fingerprint, checkpoint = item
        payload, _ = runner.run(
            _prompt(
                ruler=str(source_pack["ruler"]),
                ruler_window=str(source_pack["window"]),
                actors=actor_names,
                existing_outcomes=existing_outcomes,
                facts=group,
                task_code=task_code,
            )
        )
        payload = _normalize_candidate_sources(payload, group)
        _validate_candidate_payload_coverage(payload, group)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"input_fingerprint": input_fingerprint, "payload": payload},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(checkpoint)
        return payload

    def invoke_once(item):
        saved = load_checkpoint(item)
        if saved is not None:
            return saved, 0
        return invoke(item), 1

    actual_model_calls = 0
    errors: list[Exception] = []
    parallel_pending = pending
    if pending:
        canary_payload, canary_calls = invoke_once(pending[0])
        payloads.append(canary_payload)
        actual_model_calls += canary_calls
        parallel_pending = pending[1:]
    with ThreadPoolExecutor(
        max_workers=min(max_workers, len(parallel_pending) or 1)
    ) as pool:
        futures = [pool.submit(invoke_once, item) for item in parallel_pending]
        for future in as_completed(futures):
            try:
                payload, calls = future.result()
            except ModelBatchAnomalyError:
                for pending_future in futures:
                    pending_future.cancel()
                raise
            except Exception as exc:
                errors.append(exc)
                continue
            payloads.append(payload)
            actual_model_calls += calls
    if errors:
        raise RuntimeError(
            f"成果投影仍有 {len(errors)} 个不可恢复批次；首个错误: {errors[0]}"
        ) from errors[0]
    payloads.sort(key=lambda row: str(row["task_code"]))
    increment = compile_outcome_candidate_payloads(
        source_pack,
        payloads,
        source_index=source_index,
        schema_path=schema_path,
    )
    changed = apply_source_pack_increment(
        source_pack_path,
        increment,
        workspace_root=workspace_root,
        replace_auto=full_refresh,
        require_current_projection_ready=False,
    )
    candidate_keys_by_fact: dict[str, set[str]] = {}
    rejection_reasons_by_segment: dict[str, list[str]] = {}
    for payload in payloads:
        for candidate in payload.get("candidates") or ():
            candidate_key = str(candidate["candidate_key"])
            quotes = [str(value) for value in candidate.get("exact_quotes") or ()]
            for fact in eligible:
                exact_quote = str(fact.get("exact_quote") or "")
                if any(quote in exact_quote or exact_quote in quote for quote in quotes):
                    candidate_keys_by_fact.setdefault(str(fact["fact_ref"]), set()).add(
                        candidate_key
                    )
        for rejection in payload.get("rejections") or ():
            rejection_reasons_by_segment.setdefault(
                str(rejection["segment_ref"]), []
            ).append(str(rejection["reason"]))
    for fact in eligible:
        fact_ref = str(fact["fact_ref"])
        candidate_keys = sorted(candidate_keys_by_fact.get(fact_ref) or ())
        reasons = rejection_reasons_by_segment.get(str(fact["segment_ref"])) or []
        dispositions[fact_ref] = {
            "fact_ref": fact_ref,
            "decision": "accepted" if candidate_keys else "rejected",
            "reason": (
                "生成成果候选：" + "、".join(candidate_keys)
                if candidate_keys
                else "；".join(dict.fromkeys(reasons))
                if reasons
                else "当前成果投影未生成可登记候选。"
            ),
            **({"candidate_keys": candidate_keys} if candidate_keys else {}),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_count": len(increment["outcomes"]),
        "rejection_count": sum(len(row.get("rejections") or ()) for row in payloads),
        "model_call_count": actual_model_calls,
        "source_pack_changed": changed,
        "policy_fingerprint": policy_fingerprint,
        "dispositions": [dispositions[key] for key in sorted(dispositions)],
    }
