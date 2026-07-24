from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from uuid import uuid4

from opencc import OpenCC
import yaml

from emperor_v4.adapters.structured_output_contract import (
    validate_codex_output_schema,
    validate_payload_against_schema,
)
from emperor_v4.evaluation.governance_achievement_registry import (
    validate_governance_achievement_registry,
)


OUTPUT_SCHEMA_VERSION = "governance-achievement-candidate-output-v2"
PREPARATION_SCHEMA_VERSION = "governance-achievement-candidate-preparation-v1"
AUDIT_SCHEMA_VERSION = "governance-achievement-candidate-audit-v1"
POLICY_VERSION = "governance-achievement-judgment-v2"
DOMAIN_MAP = {
    "central_institutions": "central_institutions",
    "law_and_adjudication": "law_and_adjudication",
    "official_selection": "official_selection",
    "personnel": "official_selection",
    "fiscal_taxation": "fiscal_taxation",
    "fiscal": "fiscal_taxation",
    "local_government": "local_government",
    "local_governance": "local_government",
    "economy_production": "economy_production",
    "social_economic": "economy_production",
    "infrastructure_public_works": "infrastructure_public_works",
    "education_talent": "education_talent",
    "education": "education_talent",
}
REUSE_BY_DOMAIN = {
    "central_institutions": ["item2_central_governance", "item2_institutional_reform"],
    "law_and_adjudication": ["item2_law_and_adjudication", "item2_institutional_reform"],
    "official_selection": ["item2_central_governance", "i5b_team_building"],
    "fiscal_taxation": ["item3_fiscal_and_livelihood"],
    "local_government": ["item2_central_governance", "item4_governance_resilience"],
    "economy_production": ["item3_fiscal_and_livelihood"],
    "infrastructure_public_works": ["item3_fiscal_and_livelihood"],
    "education_talent": ["item2_central_governance", "item6_cultural_legacy"],
    "other_governance": ["item2_central_governance"],
}
_S2T = OpenCC("s2t")
_T2S = OpenCC("t2s")


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    _atomic_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _source_ref(row: Mapping[str, object]) -> str:
    return f"{row['page_title']}@{row['revision_ref']}#{row['quote_ref']}"


def _is_dynasty_chain(chain: Mapping[str, object], dynasty_token: str) -> bool:
    token = dynasty_token.upper()
    return token in str(chain.get("task_code") or "").upper() or str(
        chain.get("chain_key") or ""
    ).lower().startswith(dynasty_token.lower() + "-")


def _person_alias_index(
    people: Sequence[Mapping[str, object]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, object]]]:
    by_alias: dict[str, dict[str, str]] = {}
    by_ref: dict[str, dict[str, object]] = {}
    for row in people:
        person_ref = str(row.get("person_ref") or "")
        canonical_name = str(row.get("canonical_name") or "")
        declared_aliases = [canonical_name, *(str(value) for value in row.get("aliases") or ())]
        aliases = [
            value
            for alias in declared_aliases
            for value in (alias, _S2T.convert(alias), _T2S.convert(alias))
        ]
        if not person_ref or not canonical_name or any(not value for value in aliases):
            raise ValueError("人物索引缺少 person_ref、canonical_name 或合法 aliases")
        if person_ref in by_ref:
            raise ValueError("人物索引 person_ref 重复")
        normalized = {
            "person_ref": person_ref,
            "canonical_name": canonical_name,
            "aliases": sorted(set(aliases)),
        }
        by_ref[person_ref] = normalized
        for alias in normalized["aliases"]:
            previous = by_alias.get(alias)
            if previous and previous["person_ref"] != person_ref:
                raise ValueError(f"人物别名冲突：{alias}")
            by_alias[alias] = {
                "person_ref": person_ref,
                "canonical_name": canonical_name,
            }
    return by_alias, by_ref


def _looks_like_collective_actor(name: str) -> bool:
    simplified = _T2S.convert(name)
    exact = {
        "朝廷", "有司", "百官", "公卿", "刑部", "户部", "吏部", "兵部",
        "礼部", "工部", "左右丞", "州县", "法司", "台司",
    }
    return (
        simplified in exact
        or "及州县" in simplified
        or "等官" in simplified
        or simplified.endswith("诸司")
    )


def _extend_with_provisional_actors(
    components: Sequence[Mapping[str, object]],
    alias_index: dict[str, dict[str, str]],
    people_by_ref: dict[str, dict[str, object]],
    *,
    dynasty_token: str,
) -> None:
    names = sorted(
        {
            str(actor.get("name") or "")
            for component in components
            for fact in component["facts"]
            for actor in fact.get("actors") or ()
            if str(actor.get("name") or "")
        }
    )
    for name in names:
        if name in alias_index or _looks_like_collective_actor(name):
            continue
        canonical_name = _T2S.convert(name)
        aliases = sorted({name, canonical_name, _S2T.convert(canonical_name)})
        existing = next((alias_index[value] for value in aliases if value in alias_index), None)
        if existing:
            for alias in aliases:
                alias_index.setdefault(alias, existing)
            continue
        identity = f"{dynasty_token.upper()}::{canonical_name}"
        person_ref = "PER-ACTOR-" + sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        person = {
            "person_ref": person_ref,
            "canonical_name": canonical_name,
            "aliases": aliases,
            "identity_status": "provisional_actor_name",
        }
        people_by_ref[person_ref] = person
        binding = {"person_ref": person_ref, "canonical_name": canonical_name}
        for alias in aliases:
            alias_index[alias] = binding


def _ruler_resolver(
    ruler_aliases: Mapping[str, object] | None,
    *,
    dynasty_token: str,
    dynasty_name: str,
):
    if ruler_aliases is None:
        identity_entities = []
    elif (
        isinstance(ruler_aliases, Mapping)
        and ruler_aliases.get("schema_version")
        == "historical-entity-identities-current-v1"
    ):
        identity_entities = ruler_aliases.get("entities") or []
    else:
        raise ValueError("皇帝归责只接受当前历史实体身份目录")
    by_alias: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in identity_entities:
        if not str(row.get("person_ref") or "").startswith("RULER-"):
            continue
        entity = {
            "ruler_ref": str(row["person_ref"]),
            "ruler_name": str(row["canonical_name"]),
            "dynasty": str(row.get("dynasty") or ""),
        }
        surfaces = [
            entity["ruler_name"],
            *(str(alias["surface"]) for alias in row.get("aliases") or ()),
        ]
        for surface in {
            value
            for alias in surfaces
            for value in (alias, _S2T.convert(alias), _T2S.convert(alias))
        }:
            by_alias[surface].append(entity)

    def resolve(name: str) -> dict[str, str] | None:
        variants = {name, _S2T.convert(name), _T2S.convert(name)}
        candidates = {
            row["ruler_ref"]: row
            for variant in variants
            for row in by_alias.get(variant, ())
        }
        scoped = {
            person_ref: row
            for person_ref, row in candidates.items()
            if not dynasty_name or row["dynasty"] == dynasty_name
        }
        resolved = scoped if scoped else candidates
        return next(iter(resolved.values())) if len(resolved) == 1 else None

    return resolve


def _ruler_authorization_status(
    person_ref: str,
    component_refs: Sequence[str],
    components: Mapping[str, Mapping[str, object]],
) -> str:
    phases = {
        str(phase)
        for component_ref in component_refs
        for fact in components[component_ref]["facts"]
        for actor in fact.get("actors") or ()
        if str(actor.get("person_ref") or "") == person_ref
        for phase in actor.get("contribution_phases") or ()
    }
    if "authorized" in phases:
        return "explicit"
    if phases & {"maintained", "operated"}:
        return "maintained"
    return "implicit"


def _material_variants(
    baseline_audit: Mapping[str, object],
    settlement: Mapping[str, object],
    atomization: Mapping[str, object],
    *,
    dynasty_token: str,
) -> list[dict[str, object]]:
    if baseline_audit.get("status") != "accepted_shadow":
        raise ValueError("baseline audit 未达到 accepted_shadow")
    if settlement.get("status") != "accepted_shadow":
        raise ValueError("settlement 未达到 accepted_shadow")
    if atomization.get("status") != "accepted_shadow":
        raise ValueError("atomization 未达到 accepted_shadow")
    baseline = {
        str(row["chain_key"]): dict(row)
        for row in baseline_audit.get("chains") or ()
        if _is_dynasty_chain(row, dynasty_token)
    }
    review_candidates = {
        str(row["candidate_chain_key"])
        for row in settlement.get("review_queue") or ()
        if row.get("review_reason") == "mixed_chain_partial_overlap_requires_atomization"
    }
    components: list[dict[str, object]] = []
    covered_baseline: set[str] = set()
    for material in settlement.get("materials") or ():
        candidate_keys = {str(value) for value in material.get("candidate_chain_keys") or ()}
        if candidate_keys & review_candidates:
            continue
        variants = [
            dict(row)
            for row in material.get("fact_variants") or ()
            if _is_dynasty_chain(row.get("chain") or {}, dynasty_token)
        ]
        if not variants:
            continue
        baseline_keys = {
            str(row["chain_key"])
            for row in variants
            if row.get("source_kind") == "baseline" and str(row["chain_key"]) in baseline
        }
        covered_baseline.update(baseline_keys)
        components.append(
            {
                "component_ref": str(material["material_ref"]),
                "variant_refs": [str(row["chain_key"]) for row in variants],
                "facts": [dict(row["chain"]) for row in variants],
            }
        )

    atom_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for atom in atomization.get("atoms") or ():
        baseline_keys = [
            str(value) for value in atom.get("baseline_chain_keys") or () if str(value) in baseline
        ]
        if baseline_keys:
            group_key = "baseline::" + "::".join(sorted(baseline_keys))
            covered_baseline.update(baseline_keys)
        else:
            group_key = "atom::" + str(atom["atom_ref"])
        atom_groups[group_key].append(dict(atom))
    for group_key, atoms in sorted(atom_groups.items()):
        baseline_keys = sorted(
            {
                str(value)
                for atom in atoms
                for value in atom.get("baseline_chain_keys") or ()
                if str(value) in baseline
            }
        )
        facts = [baseline[key] for key in baseline_keys]
        facts.extend(atoms)
        identity = json.dumps(
            [group_key, [str(row.get("atom_ref") or "") for row in atoms]],
            ensure_ascii=False,
            sort_keys=True,
        )
        components.append(
            {
                "component_ref": "DNGCOMP-" + sha256(identity.encode("utf-8")).hexdigest()[:20].upper(),
                "variant_refs": [*baseline_keys, *(str(row["atom_ref"]) for row in atoms)],
                "facts": facts,
            }
        )

    for key, chain in sorted(baseline.items()):
        if key in covered_baseline:
            continue
        components.append(
            {
                "component_ref": "DNGCOMP-" + sha256(key.encode("utf-8")).hexdigest()[:20].upper(),
                "variant_refs": [key],
                "facts": [chain],
            }
        )
    refs = [str(row["component_ref"]) for row in components]
    if len(refs) != len(set(refs)):
        raise ValueError("治理材料组件 ID 重复")
    return sorted(components, key=lambda row: str(row["component_ref"]))


def _component_for_model(
    component: Mapping[str, object],
    alias_index: Mapping[str, Mapping[str, str]],
) -> dict[str, object]:
    source_rows: dict[str, dict[str, object]] = {}
    participant_sources: dict[str, set[str]] = defaultdict(set)
    participant_actor_names: dict[str, set[str]] = defaultdict(set)
    unresolved: set[str] = set()
    domains: list[str] = []
    periods: list[str] = []
    compact_facts = []
    for fact in component["facts"]:
        domain = DOMAIN_MAP.get(str(fact.get("domain") or ""), "other_governance")
        domains.append(domain)
        period = str(fact.get("period") or "")
        if period:
            periods.append(period)
        evidence = [dict(row) for row in fact.get("evidence") or ()]
        by_quote = {str(row["quote_ref"]): _source_ref(row) for row in evidence}
        for row in evidence:
            source_rows[_source_ref(row)] = row
        compact_actors = []
        for actor in fact.get("actors") or ():
            name = str(actor.get("name") or "")
            resolved = alias_index.get(name)
            actor_source_refs = sorted(
                {by_quote[ref] for ref in actor.get("quote_refs") or () if ref in by_quote}
                | {by_quote[ref] for ref in actor.get("evidence_refs") or () if ref in by_quote}
            )
            if resolved:
                person_ref = str(resolved["person_ref"])
                participant_sources[person_ref].update(actor_source_refs)
                participant_actor_names[person_ref].add(name)
                compact_actors.append(
                    {
                        "name": name,
                        "person_ref": person_ref,
                        "canonical_name": resolved["canonical_name"],
                        "responsibility_role": actor.get("responsibility_role", ""),
                        "contribution_phases": actor.get("contribution_phases", []),
                        "role_basis": actor.get("role_basis", ""),
                        "source_refs": actor_source_refs,
                    }
                )
            elif name:
                unresolved.add(name)
        compact_facts.append(
            {
                "fact_ref": str(fact.get("chain_key") or fact.get("atom_ref") or ""),
                "title": fact.get("title", ""),
                "domain": domain,
                "period": period,
                "action": fact.get("action", ""),
                "implementation": fact.get("implementation", ""),
                "operation_status": fact.get("operation_status", ""),
                "observable_result": fact.get("observable_result", ""),
                "cost_or_burden": fact.get("cost_or_burden", ""),
                "actors": compact_actors,
                "source_refs": sorted(_source_ref(row) for row in evidence),
                "uncertainty": fact.get("uncertainty", ""),
            }
        )
    participants = [
        {
            "person_ref": person_ref,
            "canonical_name": alias_index[next(iter(participant_actor_names[person_ref]))]["canonical_name"],
            "actor_names": sorted(participant_actor_names[person_ref]),
            "source_refs": sorted(participant_sources[person_ref]),
        }
        for person_ref in sorted(participant_sources)
    ]
    return {
        "component_ref": component["component_ref"],
        "variant_refs": component["variant_refs"],
        "primary_domain": Counter(domains).most_common(1)[0][0],
        "periods": sorted(set(periods)),
        "facts": compact_facts,
        "allowed_participants": participants,
        "allowed_source_refs": sorted(source_rows),
        "unresolved_actor_names": sorted(unresolved),
    }


def _chunks(values: Sequence[dict[str, object]], size: int) -> Iterable[list[dict[str, object]]]:
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def prepare_governance_achievement_candidates(
    baseline_audit: Mapping[str, object],
    settlement: Mapping[str, object],
    atomization: Mapping[str, object],
    people: Sequence[Mapping[str, object]],
    *,
    dynasty_token: str,
    output_root: Path,
    output_schema_path: Path,
    max_components_per_task: int = 24,
) -> dict[str, object]:
    if max_components_per_task < 1:
        raise ValueError("max_components_per_task 必须大于0")
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    alias_index, people_by_ref = _person_alias_index(people)
    universe = _material_variants(
        baseline_audit, settlement, atomization, dynasty_token=dynasty_token
    )
    _extend_with_provisional_actors(
        universe, alias_index, people_by_ref, dynasty_token=dynasty_token
    )
    all_components = [_component_for_model(row, alias_index) for row in universe]
    eligible = [row for row in all_components if row["allowed_participants"]]
    by_domain: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in eligible:
        by_domain[str(row["primary_domain"])].append(row)
    tasks = []
    bindings = []
    for domain, rows in sorted(by_domain.items()):
        rows.sort(key=lambda row: (str(row["periods"]), str(row["component_ref"])))
        for part, batch in enumerate(_chunks(rows, max_components_per_task), start=1):
            fingerprint = sha256(
                json.dumps(
                    [POLICY_VERSION, batch], ensure_ascii=False, sort_keys=True
                ).encode("utf-8")
            ).hexdigest()[:16].upper()
            task_code = f"GOVACH-{dynasty_token.upper()}-{domain.upper()}-{part:02d}-{fingerprint}"
            prompt_path = output_root / "prompts" / f"{task_code}.md"
            result_path = output_root / "results" / f"{task_code}.json"
            event_path = output_root / "events" / f"{task_code}.events.jsonl"
            prompt = f"""EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS
TOOLS: FORBIDDEN
REPOSITORY_READ: FORBIDDEN
OUTPUT: JSON_ONLY

你是中性史料到治理成果候选的裁决器。每个 INPUT component 已完成史源、重复结算、原子化和人物别名解析。只依据 INPUT 判断，不联网、不补史实、不评价皇帝总分或人才总档位。

规则：
1. 每个 component_ref 必须且只能在 component_decisions 出现一次。已实施、运行、完成或形成可观察公共结果，且能具体归责给 allowed_participants 时才 register；纯任职、列名、未落实建议、无可观察结果的表态、一般文化编纂或纯军事行动 omit；材料不足 uncertain。
2. 同一治理对象的设计、实施、运行和结果优先合为一项 achievement；不同政策、税种、案件或不同统治期重新制定的系统不得强并。每个输入组件只由本任务读取一次。
3. achievements 只能引用 disposition=register 的 component_refs；register 组件至少被一项 achievement 使用，omit/uncertain 组件不得使用。
4. participants 只能使用相关组件 allowed_participants 中的 person_ref。同处中枢、共同署名或同时任职不等于同功；exclusive=材料明确独占，lead=主导，participant=明确参与。每人必须以 contribution_types 区分政策设计、治理主导、持续运行、关键执行、纠偏、授权、学术撰写或一般参与，并用 contribution_basis_fact_refs 回指 component_refs。不要写“非独占”等辩护句，只写实际负责内容。
5. implementation_status 只回答是否已实施、运行、完成、失败或不明，禁止使用 mixed；mixed 只用于价值方向。
6. value_judgment 判断生产民生、文明制度、国家与民众安全、文化教育与思想活力四轴。不要复原抽象的“时代平均水平”，只比较这项举措前后的具体状态。basis 必须写成“基线：……；变化：……；结果：……”，三段均须具体；禁止只写“以举措前状态为基线”。史料直接记载前后变化用 explicit_before_after，与旧制明确比较用 prior_institution_comparison，由已引事实归纳旧状态用 inferred_prior_state；无法说清则用 not_established 且 overall_direction=unclear。scale 只表示范围，不能代替 overall_magnitude。每个已建立方向的 basis_fact_refs 必须来自 component_refs，未建立轴不得伪造依据。
7. 只登记已经观察到的实现结果。制度目的、官职重要性和后世常识不能代替 observable_result。mixed/negative 必须有材料中的实际不利公共结果；存在限制但没有不利结果时仍可 positive，并把限制写入 limitations。负向轴的 basis 使用“恶化、加重、压缩、损害”等方向词，不得写成“改善”。
6. scale 衡量已实现结果的实质幅度，不衡量法令的名义管辖范围。全国颁令、中央发文或适用于天下，本身最多证明覆盖范围，不能单独证明 national。
6A. national_core_subsystem 只用于建立、重构或长期稳定运行财政、刑律、选官、行政等全国核心系统，并且材料给出系统级实现结果。单个案件、单条刑罚标准、一个考试科目、年龄资格线、一次禁令、一次撤销或窄程序调整，即使全国适用，也只能按实际结果判 local 或 important。
6B. national_public_result 必须有跨区域或全国人口、财政、生产、秩序等直接可观察结果；“颁行天下”及政策目的不算结果。regional 必须有主要区域的实际结果。era_shaping 必须有直接材料证明治理秩序重构，不能由“重要”推定。
6C. stable_delivery 只在多年或跨阶段实际运行并交付结果时为 true；important_method_or_legacy 只在反复应用、后续制度化或材料明确显示方法传承时为 true；新设法令或一次成功不能自动为 true。
7. independent_governance_key 使用稳定英文小写连字符，不含人物名。一个成果跨多个组件时只输出一次。local_key 按 achievement-1 起顺序唯一。
8. component_refs、person_ref 不得越界。不要输出 source refs、复用项目、规则方向、分数、Episode 或 REU；审计器会从组件确定性派生。

固定身份：
- schema_version: {OUTPUT_SCHEMA_VERSION}
- task_code: {task_code}

只输出严格符合传入 JSON Schema 的一个 JSON object。

INPUT
{json.dumps(batch, ensure_ascii=False, sort_keys=True)}
"""
            _atomic_text(prompt_path, prompt)
            task = {
                "task_code": task_code,
                "prompt_path": str(prompt_path.resolve()),
                "last_message_path": str(result_path.resolve()),
                "log_path": str(event_path.resolve()),
                "permission_profile": "review-only",
                "argv": [
                    "codex",
                    "exec",
                    "--output-schema",
                    str(output_schema_path.resolve()),
                    "-",
                ],
            }
            tasks.append(task)
            bindings.append(
                {
                    "task_code": task_code,
                    "domain": domain,
                    "component_refs": [str(row["component_ref"]) for row in batch],
                }
            )
    _atomic_text(
        output_root / "tasks.jsonl",
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in tasks),
    )
    preparation = {
        "schema_version": PREPARATION_SCHEMA_VERSION,
        "dynasty_token": dynasty_token.upper(),
        "component_universe_count": len(all_components),
        "eligible_component_count": len(eligible),
        "ineligible_component_count": len(all_components) - len(eligible),
        "task_count": len(tasks),
        "bindings": bindings,
        "components": {str(row["component_ref"]): row for row in eligible},
        "people": people_by_ref,
        "unresolved_actor_names": sorted(
            {name for row in all_components for name in row["unresolved_actor_names"]}
        ),
        "output_schema_path": str(output_schema_path.resolve()),
    }
    _atomic_json(output_root / "preparation.json", preparation)
    return preparation


def _achievement_signature(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        row["canonical_label"], row["domain"], row["period_start"], row["period_end"],
        row["implementation_status"], row["observable_result"], row["result_direction"],
        row["positive_result_preserved"], row["scale_level"], row["scale_basis"],
        row["scale_reason"], row["foundational"], row["durable_cross_stage"],
        row["stable_delivery"], row["important_method_or_legacy"],
    )


def _validate_value_judgment(
    row: Mapping[str, object], *, component_refs: set[str]
) -> None:
    judgment = row["value_judgment"]
    comparison_basis = str(judgment["comparison_basis"])
    overall_direction = str(judgment["overall_direction"])
    if overall_direction != str(row["result_direction"]):
        raise ValueError("治理成果方向与四轴总体方向不一致")
    if overall_direction != "unclear" and comparison_basis == "not_established":
        raise ValueError("未建立历史比较时价值方向只能不明")
    if comparison_basis != "not_established":
        basis = str(judgment["basis"])
        if not all(marker in basis for marker in ("基线：", "变化：", "结果：")):
            raise ValueError("历史比较必须按“基线；变化；结果”写明具体内容")
    baseline_refs = {str(value) for value in judgment["baseline_fact_refs"]}
    if not baseline_refs <= component_refs:
        raise ValueError("历史基线依据越出本成果 component_refs")
    if comparison_basis in {"explicit_before_after", "prior_institution_comparison"}:
        if not baseline_refs:
            raise ValueError("史料直接比较或旧制比较必须引用基线事实")
    for axis_name, axis in judgment["axes"].items():
        basis_refs = {str(value) for value in axis["basis_fact_refs"]}
        if not basis_refs <= component_refs:
            raise ValueError(f"{axis_name} 四轴依据越出本成果 component_refs")
        established = axis["direction"] != "not_established"
        if established != bool(basis_refs):
            raise ValueError(f"{axis_name} 已建立方向必须有依据，未建立不得伪造依据")
        if axis["direction"] == "negative" and "改善" in str(axis["basis"]):
            raise ValueError(f"{axis_name} 负向影响不得使用“改善”表述")


def audit_governance_achievement_candidates(
    preparation: Mapping[str, object],
    payloads: Sequence[Mapping[str, object]],
    *,
    output_schema_path: Path,
    registry_schema_path: Path,
    ruler_aliases: Mapping[str, object] | None = None,
    dynasty_name: str = "",
) -> dict[str, object]:
    if preparation.get("schema_version") != PREPARATION_SCHEMA_VERSION:
        raise ValueError("governance achievement preparation 版本不支持")
    schema = json.loads(output_schema_path.read_text(encoding="utf-8"))
    validate_codex_output_schema(schema, require_all_properties=True)
    expected_tasks = {str(row["task_code"]): row for row in preparation["bindings"]}
    actual_codes = [str(row.get("task_code") or "") for row in payloads]
    if len(actual_codes) != len(set(actual_codes)) or set(actual_codes) != set(expected_tasks):
        raise ValueError("governance achievement task 覆盖不唯一")
    candidates_by_key: dict[str, list[dict[str, object]]] = defaultdict(list)
    resolve_ruler = _ruler_resolver(
        ruler_aliases,
        dynasty_token=str(preparation["dynasty_token"]),
        dynasty_name=dynasty_name,
    )
    decisions = []
    limitations = []
    disposition_counts: Counter[str] = Counter()
    for payload in payloads:
        validate_payload_against_schema(payload, schema)
        task_code = str(payload["task_code"])
        if payload["schema_version"] != OUTPUT_SCHEMA_VERSION:
            raise ValueError("governance achievement output 版本不支持")
        binding = expected_tasks[task_code]
        expected_components = set(binding["component_refs"])
        decision_rows = payload["component_decisions"]
        actual_components = [str(row["component_ref"]) for row in decision_rows]
        if len(actual_components) != len(set(actual_components)) or set(actual_components) != expected_components:
            raise ValueError(f"{task_code} component 覆盖不唯一")
        disposition_by_component = {
            str(row["component_ref"]): str(row["disposition"]) for row in decision_rows
        }
        used_components: set[str] = set()
        local_keys = [str(row["local_key"]) for row in payload["achievements"]]
        if len(local_keys) != len(set(local_keys)):
            raise ValueError(f"{task_code} local_key 重复")
        for row in payload["achievements"]:
            component_refs = [str(value) for value in row["component_refs"]]
            if len(component_refs) != len(set(component_refs)) or not set(component_refs) <= expected_components:
                raise ValueError("achievement component_refs 越界或重复")
            if any(disposition_by_component[ref] != "register" for ref in component_refs):
                raise ValueError("achievement 引用了非 register 组件")
            _validate_value_judgment(row, component_refs=set(component_refs))
            used_components.update(component_refs)
            allowed_people = {
                str(person["person_ref"])
                for ref in component_refs
                for person in preparation["components"][ref]["allowed_participants"]
            }
            participant_refs = [str(person["person_ref"]) for person in row["participants"]]
            if len(participant_refs) != len(set(participant_refs)) or not set(participant_refs) <= allowed_people:
                raise ValueError("achievement participant 越界或重复")
            candidates_by_key[str(row["independent_governance_key"])].append(
                {**dict(row), "task_code": task_code}
            )
        registered = {ref for ref, disposition in disposition_by_component.items() if disposition == "register"}
        if used_components != registered:
            raise ValueError(f"{task_code} register 组件与成果引用不闭合")
        for row in decision_rows:
            disposition_counts[str(row["disposition"])] += 1
            decisions.append({"task_code": task_code, **dict(row)})
        limitations.extend(str(value) for value in payload["limitations"])

    achievements = []
    conflicts = []
    lineage_refinement_queue = []
    for independent_key, rows in sorted(candidates_by_key.items()):
        signatures = {_achievement_signature(row) for row in rows}
        if len(signatures) != 1:
            conflicts.append(
                {
                    "independent_governance_key": independent_key,
                    "task_codes": sorted({str(row["task_code"]) for row in rows}),
                    "reason": "same_key_semantic_conflict_requires_review",
                }
            )
            continue
        first = rows[0]
        component_refs = sorted({str(ref) for row in rows for ref in row["component_refs"]})
        source_refs = sorted(
            {
                str(ref)
                for component_ref in component_refs
                for ref in preparation["components"][component_ref]["allowed_source_refs"]
            }
        )
        participants_by_ref: dict[str, dict[str, object]] = {}
        rulers_by_ref: dict[str, dict[str, str]] = {}
        role_rank = {"participant": 0, "lead": 1, "exclusive": 2}
        for row in rows:
            for participant in row["participants"]:
                person_ref = str(participant["person_ref"])
                person = preparation["people"][person_ref]
                ruler = resolve_ruler(str(person["canonical_name"]))
                if ruler is not None:
                    ruler_ref = str(ruler["ruler_ref"])
                    rulers_by_ref[ruler_ref] = {
                        **ruler,
                        "authorization_status": _ruler_authorization_status(
                            person_ref,
                            row["component_refs"],
                            preparation["components"],
                        ),
                    }
                    continue
                previous = participants_by_ref.get(person_ref)
                if previous is None or role_rank[str(participant["responsibility_role"])] > role_rank[str(previous["responsibility_role"] )]:
                    participants_by_ref[person_ref] = dict(participant)
        participants = [
            {
                "person_ref": person_ref,
                "canonical_name": preparation["people"][person_ref]["canonical_name"],
                "responsibility_role": participant["responsibility_role"],
                "contribution_scope": participant["contribution_scope"],
                "contribution_types": list(participant["contribution_types"]),
                "contribution_basis_fact_refs": list(
                    participant["contribution_basis_fact_refs"]
                ),
            }
            for person_ref, participant in sorted(participants_by_ref.items())
        ]
        ruler_links = [
            {
                "ruler_ref": ruler_ref,
                "ruler_name": ruler["ruler_name"],
                "authorization_status": ruler["authorization_status"],
                "reign_window": "；".join(
                    sorted(
                        {
                            str(period)
                            for component_ref in component_refs
                            for period in preparation["components"][component_ref]["periods"]
                            if str(period)
                        }
                    )
                )
                or "统治窗口待后置校准",
            }
            for ruler_ref, ruler in sorted(rulers_by_ref.items())
        ]
        domain = str(first["domain"])
        broad_components = [
            component_ref
            for component_ref in component_refs
            if len(preparation["components"][component_ref]["facts"]) > 1
        ]
        if broad_components:
            lineage_refinement_queue.append(
                {
                    "independent_governance_key": independent_key,
                    "component_refs": broad_components,
                    "reason": "multi_fact_component_requires_exact_source_subset_or_upstream_atomization",
                }
            )
        identity = json.dumps(
            [preparation["dynasty_token"], independent_key], ensure_ascii=False
        )
        achievements.append(
            {
                "achievement_ref": "GOVACH-" + sha256(identity.encode("utf-8")).hexdigest()[:20].upper(),
                "independent_governance_key": independent_key,
                "canonical_label": first["canonical_label"],
                "domain": domain,
                "period": {"start": first["period_start"], "end": first["period_end"]},
                "implementation_status": first["implementation_status"],
                "observable_result": first["observable_result"],
                "result_direction": first["result_direction"],
                "positive_result_preserved": first["positive_result_preserved"],
                "value_judgment": dict(first["value_judgment"]),
                "scale": {
                    "level": first["scale_level"],
                    "consequence_basis": first["scale_basis"],
                    "reason": first["scale_reason"],
                },
                "foundational": first["foundational"],
                "durable_cross_stage": first["durable_cross_stage"],
                "stable_delivery": first["stable_delivery"],
                "important_method_or_legacy": first["important_method_or_legacy"],
                "participants": participants,
                "ruler_links": ruler_links,
                "neutral_fact_refs": component_refs,
                "source_refs": source_refs,
                "reuse_targets": sorted({"talent_grade_civil_governance", *REUSE_BY_DOMAIN[domain]}),
                "limitations": sorted(
                    {
                        *(str(value) for row in rows for value in row["limitations"]),
                        "皇帝授权与统治窗口由后置规则投影，不在本轮中性成果裁决中推定。",
                        *(
                            ["存在多事实上游组件；当前保留组件级完整史源，正式接受前需细化本成果的逐事实引用子集。"]
                            if broad_components
                            else []
                        ),
                    }
                ),
            }
        )
    registry = {
        "schema_version": "governance-achievement-registry-v2",
        "status": "shadow",
        "achievements": achievements,
    }
    registry_validation = validate_governance_achievement_registry(
        registry, schema_path=registry_schema_path
    )
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "accepted_shadow" if not conflicts else "needs_review",
        "task_count": len(payloads),
        "component_count": len(decisions),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "achievement_count": len(achievements),
        "minister_participant_count": sum(
            len(row["participants"]) for row in achievements
        ),
        "ruler_link_count": sum(len(row["ruler_links"]) for row in achievements),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "lineage_refinement_count": len(lineage_refinement_queue),
        "lineage_refinement_queue": lineage_refinement_queue,
        "decisions": sorted(decisions, key=lambda row: (str(row["task_code"]), str(row["component_ref"]))),
        "registry": registry,
        "registry_validation": registry_validation,
        "limitations": sorted(set(limitations)),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="中性材料到治理成果候选的批量消费")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--baseline", type=Path, required=True)
    prepare.add_argument("--settlement", type=Path, required=True)
    prepare.add_argument("--atomization", type=Path, required=True)
    prepare.add_argument("--people", type=Path, required=True)
    prepare.add_argument("--dynasty-token", required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--output-schema", type=Path, required=True)
    prepare.add_argument("--max-components-per-task", type=int, default=24)
    audit = sub.add_parser("audit")
    audit.add_argument("--preparation", type=Path, required=True)
    audit.add_argument("--results-dir", type=Path, required=True)
    audit.add_argument("--output-schema", type=Path, required=True)
    audit.add_argument("--registry-schema", type=Path, required=True)
    audit.add_argument("--ruler-aliases", type=Path)
    audit.add_argument("--dynasty-name", default="")
    audit.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        people_payload = json.loads(args.people.read_text(encoding="utf-8"))
        if isinstance(people_payload, Mapping):
            people = people_payload.get("people") or people_payload.get("profiles")
            if people is None:
                raise ValueError("人物输入必须包含 people 或 profiles")
        else:
            people = people_payload
        report = prepare_governance_achievement_candidates(
            json.loads(args.baseline.read_text(encoding="utf-8")),
            json.loads(args.settlement.read_text(encoding="utf-8")),
            json.loads(args.atomization.read_text(encoding="utf-8")),
            people,
            dynasty_token=args.dynasty_token,
            output_root=args.output_root,
            output_schema_path=args.output_schema,
            max_components_per_task=args.max_components_per_task,
        )
    else:
        preparation = json.loads(args.preparation.read_text(encoding="utf-8"))
        payloads = [
            json.loads((args.results_dir / f"{row['task_code']}.json").read_text(encoding="utf-8"))
            for row in preparation["bindings"]
        ]
        report = audit_governance_achievement_candidates(
            preparation,
            payloads,
            output_schema_path=args.output_schema,
            registry_schema_path=args.registry_schema,
            ruler_aliases=(
                yaml.safe_load(args.ruler_aliases.read_text(encoding="utf-8"))
                if args.ruler_aliases
                else None
            ),
            dynasty_name=args.dynasty_name,
        )
        _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
