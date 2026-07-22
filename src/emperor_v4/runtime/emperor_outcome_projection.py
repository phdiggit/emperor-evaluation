from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
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
PROJECTION_POLICY_VERSION = "current-outcome-projection-policy-v6"
LEGACY_PROJECTION_POLICY_VERSION = "current-outcome-projection-policy-v5"
DIRECT_MODEL_FACT_LIMIT = 16
_T2S = OpenCC("t2s")


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
    return f"""你是皇帝评价 V4 的成果候选整理器。只把输入的中性事实整理为可登记的治理成果或战役；不能补史实、不能联网、不能评分。

硬规则：
1. 只有原文同时足以支持行动、可观察结果和参与者责任时才生成 candidate；任官、褒奖、建议、品评或单纯过程而无结果，一律放入 rejections。
2. exact_quotes 与 authorization_quotes 必须逐字复制输入 exact_quote 的连续子串，不得转写、拼接或补字。
3. members 只能使用允许人物：{json.dumps(list(actors), ensure_ascii=False)}。皇帝 {ruler} 用 actor_kind=ruler；其余用 person。
4. 同一独立结果只生成一个 candidate。candidate_key 用小写 ASCII 与连字符，表达皇帝、时期和独立结果，必须稳定。
5. campaign 必须填写 campaign_tier、campaign_tier_basis、land_strategic_value、process_adversity、process_adversity_basis、固定 process_adversity_index 和逐事件 process_adversity_attributions；治理字段填 null。正常动员、追击、敌军来援和战役困难不是过程负面；非 none 必须逐字说明责任或明确 external_unattributed，绝不能默认归责主帅。
6. ruler_window_status 每项必填：在位期填 within_window；{ruler} 登基前已取得独立统军权并对战役负核心责任的成果填 leadership_formation；前任朝廷独立决策或人物一生其他时期成果填 outside_window。仅凭参战、宗室身份或事后即位不得填 leadership_formation。campaign 不得填 unresolved；窗口无法确定就拒绝候选。
7. settlement_scope 必填：皇帝父级战役填 ruler_campaign_parent；人物在父级内独立统帅战区并形成独立终局时填 person_campaign_subresult 并给 parent_outcome_ref；当前皇帝窗口治理填 governance_result；臣子全生涯中其他皇帝窗口的独立治理成果填 person_governance_result，必须保持 outside_window 且不得归给当前皇帝；粮价、人口、生产或治安等宏观结果填 reign_macro_outcome。宏观结果若史源上下文明确归于皇帝总体治理，causal_attribution_status=source_attributed 且皇帝可为 lead；若只有统治窗口关系则填 limited/reign_holder。每个战役成员填写 talent_credit，父级中已由子成果承载的人物填 covered_by_child。
8. 奏疏、谏言和批评只证明臣下提出主张，不能单独证明被批评现象或公共后果已经发生；没有独立实施或结果史源时拒绝治理成果候选，但保留中性材料供 I5A 欲望与自我约束或其他相应规则消费。
9. 完成并投入国家使用的一代正史、跨代通史或大型文化典籍通常至少填 national_cultural_corpus；例行修成单朝皇帝实录通常只属 important，除非完整国家史体系的规模、使用和长期影响另有直接史源。只有作品开创文明范式、长期成为基础文本且本人实际独著、主编或最终定稿，才填 civilization_foundational_corpus/era_shaping/foundational。官修不自动降档，但授权、总裁、主修、分卷撰修和挂名参与必须分别归责。
10. 规模只按原文可支持的影响范围，不因人物名气上调；不确定就拒绝或 limitations 明示。
11. campaign 的 role_code 只能是 commander_in_chief/principal_commander/deputy_commander/participant/not_in_command_chain，并至少有一名处于实际军事指挥链的成员。within_window/leadership_formation 的父级战役群必须且只能有一个当前皇帝成员；outside_window 的臣子全生涯战役允许没有当前皇帝，不得因此删除。只要登记皇帝成员就必须填唯一皇权关系。皇帝只有授权、默许或阻挠而未实际进入军事指挥链时用 not_in_command_chain；亲征、长期统筹或临时坐镇不得用 not_in_command_chain。governance 只能是 exclusive/lead/governance_participant/authorized：exclusive=独立建立且没有同级共同主导者，lead=主导方案或持续执行，governance_participant=有逐字依据的实质参与，authorized=仅批准或维持授权而未主导实施；参会、在职和一般赞同不能推定责任。
12. campaign 中皇帝成员另填唯一 ruler_campaign_relation：obstructed/acquiesced/authorized/temporary_theater_control/sustained_theater_control/personal_command；非皇帝或治理成果填 null。同一父级战役群按 personal_command > sustained_theater_control > temporary_theater_control > authorized > acquiesced > obstructed 取最高实际参与，低档阶段只留在事实中，不并列登记。
13. EXISTING_OUTCOMES 已登记的同一独立结果必须拒绝，不得换名重复生成；同一战略目标建立一个父级战役成果，阶段战斗只写入 observable_result/limitations，不得拆成多项重复成果。全局战果有得有失时父级必须 mixed；例如远征总体未达目标但取得局部胜利，不能只按局部胜利登记。规模必须同时检查土地战略价值、对手实际强度和已实现结果，不因国号、名气或史料篇幅升档。
14. governance 只登记制度、持续程序、跨个案公共效果或明确先例。单案改判、一次礼遇、个人赏罚、一般言行和仅对一人的处置放入 rejections；不得因其有可观察结果就包装成治理成果。
15. 带有同一 event_refs 的跨书事实属于同一中性事件，只能合并判断，不得按史书重复生成成果。
16. 输出严格符合 schema；schema_version=current-outcome-candidate-output-v1，task_code={task_code}。

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
        normalized = _T2S.convert(quote)
        matches = set()
        for fact_quote in fact_quotes:
            start = _T2S.convert(fact_quote).find(normalized)
            if start >= 0:
                candidate = fact_quote[start : start + len(quote)]
                if _T2S.convert(candidate) == normalized:
                    matches.add(candidate)
        return next(iter(matches)) if len(matches) == 1 else quote

    retained_candidates = []
    for candidate in payload.get("candidates") or ():
        quotes = [canonical_quote(value) for value in candidate.get("exact_quotes") or ()]
        candidate["exact_quotes"] = quotes
        for member in candidate.get("members") or ():
            member["authorization_quotes"] = [
                canonical_quote(value)
                for value in member.get("authorization_quotes") or ()
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
        if (
            candidate.get("outcome_kind") == "governance"
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
    return payload


def project_current_outcomes(
    *,
    source_pack_path: Path,
    neutral_materials: Mapping[str, Any],
    source_index: LocalSourceTextIndex,
    schema_path: Path,
    runner: StructuredCodexRunner,
    checkpoint_dir: Path,
    workspace_root: Path,
    max_workers: int,
    facts_per_call: int = 16,
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
    full_refresh = not current_projection_compatible
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
    all_eligible = [
        dict(fact)
        for fact in (neutral_materials.get("fanout") or {}).get("facts") or ()
        if any(
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
    def make_item(group: Sequence[Mapping[str, Any]]):
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
                return _normalize_candidate_sources(saved["payload"], group)
        return None

    payloads: list[Mapping[str, Any]] = []
    pending = []
    for group in groups:
        item = make_item(group)
        saved = load_checkpoint(item)
        if saved is not None:
            payloads.append(saved)
        else:
            pending.append(item)

    def invoke(item: tuple[str, Sequence[Mapping[str, Any]], str, Path]):
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

    def persist_payload(item, payload: Mapping[str, Any]) -> None:
        _, _, input_fingerprint, checkpoint = item
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

    def invoke_resilient(item, *, allow_single_retry: bool = True):
        task_code, group, _, _ = item
        saved = load_checkpoint(item)
        if saved is not None:
            return saved, 0
        if len(group) > 1:
            middle = len(group) // 2
            child_items = (make_item(group[:middle]), make_item(group[middle:]))
            child_saved = [load_checkpoint(child) for child in child_items]
            if all(value is not None for value in child_saved):
                child_payloads = child_saved
                calls = 0
            elif any(value is not None for value in child_saved):
                child_payloads = []
                calls = 0
                for child, saved in zip(child_items, child_saved):
                    if saved is not None:
                        child_payloads.append(saved)
                        continue
                    payload, child_calls = invoke_resilient(child)
                    child_payloads.append(payload)
                    calls += child_calls
            else:
                child_payloads = []
                calls = 0
                if len(group) <= DIRECT_MODEL_FACT_LIMIT:
                    try:
                        return invoke(item), 1
                    except ModelBatchAnomalyError:
                        raise
                    except Exception:
                        calls = 1
                for child in child_items:
                    payload, child_calls = invoke_resilient(child)
                    child_payloads.append(payload)
                    calls += child_calls
            merged = {
                "schema_version": "current-outcome-candidate-output-v1",
                "task_code": task_code,
                "candidates": [
                    row
                    for payload in child_payloads
                    for row in payload.get("candidates") or ()
                ],
                "rejections": [
                    row
                    for payload in child_payloads
                    for row in payload.get("rejections") or ()
                ],
            }
            persist_payload(item, merged)
            return merged, calls
        try:
            return invoke(item), 1
        except ModelBatchAnomalyError:
            raise
        except Exception:
            if not allow_single_retry:
                raise
            payload, calls = invoke_resilient(item, allow_single_retry=False)
            return payload, calls + 1

    actual_model_calls = 0
    errors: list[Exception] = []
    parallel_pending = pending
    if pending:
        canary_payload, canary_calls = invoke_resilient(pending[0])
        payloads.append(canary_payload)
        actual_model_calls += canary_calls
        parallel_pending = pending[1:]
    with ThreadPoolExecutor(
        max_workers=min(max_workers, len(parallel_pending) or 1)
    ) as pool:
        futures = [pool.submit(invoke_resilient, item) for item in parallel_pending]
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
                "；".join(dict.fromkeys(reasons))
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
