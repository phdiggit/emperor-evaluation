from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_finite_values import CANONICAL_PERIODS  # noqa: E402
from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import ImportPlanError, json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import repo_relative, text  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V3_DSN"
TARGET_PERIOD_KIND = "target_emperor_period"
PERSON_ROLE_KIND = "person_role"
PERSON_TALENT_KIND = "person_talent_grade"
PERSON_NEGATIVE_TALENT_KIND = "person_negative_talent"
PERSON_PROFILE_BASIS_KIND = "person_profile_basis"
TASK_KINDS = (TARGET_PERIOD_KIND, PERSON_ROLE_KIND, PERSON_TALENT_KIND, PERSON_NEGATIVE_TALENT_KIND, PERSON_PROFILE_BASIS_KIND)
TALENT_GRADES = {
    "historic_talent",
    "top_talent",
    "important_talent",
    "usable_talent",
    "ordinary_talent",
}
TALENT_GRADE_VERSION = "talent-grade-v2"
NEGATIVE_TALENT_VERSION = "negative-talent-v1"
AUTHORITY_CONSENSUS_VALUES = {"none", "weak", "moderate", "strong", "disputed"}
EVIDENCE_STRENGTH_VALUES = {"none", "weak", "moderate", "strong"}
EVIDENCE_COVERAGE_VALUES = {"insufficient", "partial", "substantial", "comprehensive"}
NEGATIVE_TALENT_CLASSES = {
    "sycophant", "favorite", "power_abuser", "framer", "extractive_official",
    "cruel_official", "incompetent_harmful", "traitorous_actor", "mixed_or_disputed",
}
NEGATIVE_TALENT_SEVERITIES = {"minor", "material", "major", "historic"}
PATCH_JSONL_BEGIN = "PATCH_JSONL_BEGIN"
PATCH_JSONL_END = "PATCH_JSONL_END"
ROLE_KINDS = {
    "emperor",
    "heir",
    "prince",
    "minister",
    "general",
    "official",
    "consort",
    "clan_member",
    "eunuch",
    "scholar",
    "rebel",
    "other",
}


class JudgmentWorklistError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise JudgmentWorklistError(f"{path}:{line_no}: expected JSON object")
        payload["_line_no"] = line_no
        rows.append(payload)
    return rows


def chunks(rows: Sequence[Mapping[str, Any]], size: int) -> Iterable[list[Mapping[str, Any]]]:
    step = max(1, size)
    for index in range(0, len(rows), step):
        yield list(rows[index:index + step])


def workitem_code(kind: str, payload: Any) -> str:
    return "JWI-" + stable_hash([kind, payload], length=16)


def task_code(kind: str, rows: Sequence[Mapping[str, Any]]) -> str:
    return "CJT-" + stable_hash([kind, [row.get("workitem_code") for row in rows]], length=16)


def fetch_target_period_gaps(cur: Any, *, item_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            rt.id as target_id,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            o.id as object_id,
            o.object_code,
            o.object_identity_key,
            pr.role_title,
            pp.talent_grade_basis
          from retrieval_v3.retrieval_targets rt
          join retrieval_v3.target_objects tob
            on tob.target_id = rt.id
           and tob.object_role = 'target_emperor'
          join retrieval_v3.objects o on o.id = tob.object_id
          left join retrieval_v3.person_roles pr
            on pr.object_id = o.id
           and pr.role_kind = 'emperor'
           and pr.review_status in ('pending', 'accepted')
          left join retrieval_v3.person_profiles pp on pp.object_id = o.id
         where rt.target_status = 'active'
           and (%s = '' or rt.item_code = %s)
           and not exists (
               select 1
                 from retrieval_v3.person_affiliations pa
                where pa.object_id = o.id
                  and pa.affiliation_kind = 'dynasty'
                  and pa.review_status in ('pending', 'accepted')
           )
         order by rt.item_code, rt.emperor_name
        """,
        (item_code, item_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_missing_roles(cur: Any, *, item_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            o.id as object_id,
            o.object_code,
            o.canonical_name,
            o.normalized_name,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            array_remove(array_agg(distinct mol.role order by mol.role), null) as material_roles,
            array_remove(array_agg(distinct pa.dynasty_label order by pa.dynasty_label), null) as known_dynasties
          from retrieval_v3.objects o
          join retrieval_v3.target_objects tob on tob.object_id = o.id
          join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id
          left join retrieval_v3.material_object_links mol on mol.target_object_id = tob.id
          left join retrieval_v3.person_affiliations pa
            on pa.object_id = o.id
           and pa.review_status in ('pending', 'accepted')
         where o.object_type = 'person'
           and tob.object_role <> 'target_emperor'
           and (%s = '' or rt.item_code = %s)
           and not exists (
               select 1
                 from retrieval_v3.person_roles pr
                where pr.object_id = o.id
                  and pr.review_status in ('pending', 'accepted')
           )
         group by o.id, o.object_code, o.canonical_name, o.normalized_name, rt.target_code, rt.emperor_name, rt.item_code
         order by o.canonical_name, rt.emperor_name
        """,
        (item_code, item_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_missing_talent(cur: Any, *, item_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            o.id as object_id,
            o.object_code,
            o.canonical_name,
            o.normalized_name,
            pp.id as person_profile_id,
            pp.talent_grade_basis,
            pp.review_status::text as profile_status,
            array_remove(array_agg(distinct rt.emperor_name order by rt.emperor_name), null) as target_emperors,
            array_remove(array_agg(distinct pa.dynasty_label order by pa.dynasty_label), null) as known_dynasties,
            array_remove(array_agg(distinct pr.role_kind::text order by pr.role_kind::text), null) as role_kinds,
            coalesce(ev.evidence_claims, '[]'::jsonb) as evidence_claims,
            coalesce(av.authority_evaluations, '[]'::jsonb) as authority_evaluations
          from retrieval_v3.objects o
          join retrieval_v3.person_profiles pp on pp.object_id = o.id
          join retrieval_v3.target_objects tob on tob.object_id = o.id
          join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id
          left join retrieval_v3.person_affiliations pa
            on pa.object_id = o.id
           and pa.review_status in ('pending', 'accepted')
          left join retrieval_v3.person_roles pr
            on pr.object_id = o.id
           and pr.review_status in ('pending', 'accepted')
          left join lateral (
              select jsonb_agg(jsonb_build_object(
                         'claim_code', q.claim_code,
                         'direction', q.direction,
                         'claim_summary', q.claim_summary,
                         'source_document_codes', q.source_document_codes
                     ) order by q.claim_code) as evidence_claims
                from (
                    select mc.claim_code, mc.direction::text as direction, mc.claim_summary,
                           coalesce(array_agg(distinct sd.document_code) filter (where sd.id is not null), array[]::text[]) as source_document_codes
                      from retrieval_v3.material_object_links mol
                      join retrieval_v3.material_claims mc on mc.id = mol.claim_id
                      left join retrieval_v3.claim_source_passages csp on csp.claim_id = mc.id
                      left join retrieval_v3.source_passages spg on spg.id = csp.source_passage_id
                      left join retrieval_v3.source_documents sd on sd.id = spg.source_document_id
                     where mol.object_id = o.id
                       and mol.review_status = 'accepted'
                     group by mc.id, mc.claim_code, mc.direction, mc.claim_summary
                     order by mc.id
                     limit 40
                ) q
          ) ev on true
          left join lateral (
              select jsonb_agg(jsonb_build_object(
                         'claim_key', q.claim_key,
                         'proposal_status', q.proposal_status,
                         'basis', q.basis,
                         'claim_summary', q.claim_summary,
                         'source_titles', q.source_titles
                     ) order by q.claim_key) as authority_evaluations
                from (
                    select ppl.claim_key, ppl.proposal_status::text as proposal_status,
                           ppl.basis, cc.claim_summary,
                           coalesce(array_agg(distinct css.source_title) filter (where btrim(css.source_title) <> ''), array[]::text[]) as source_titles
                      from retrieval_v3.person_profile_claim_links ppl
                      join retrieval_v3.claim_cache cc on cc.claim_key = ppl.claim_key
                      left join retrieval_v3.claim_evidence ce on ce.claim_key = cc.claim_key
                      left join retrieval_v3.claim_source_slices css on css.slice_hash = ce.slice_hash
                     where coalesce(ppl.object_id, cc.object_id) = o.id
                       and ppl.profile_field = 'authority_evaluation'
                       and ppl.proposal_status in ('accepted', 'candidate', 'needs_review')
                     group by ppl.claim_key, ppl.proposal_status, ppl.basis, cc.claim_summary
                ) q
          ) av on true
         where o.object_type = 'person'
           and tob.object_role <> 'target_emperor'
           and (%s = '' or rt.item_code = %s)
           and (pp.talent_grade is null or pp.talent_grade_version <> %s)
         group by o.id, o.object_code, o.canonical_name, o.normalized_name, pp.id, pp.talent_grade_basis, pp.review_status,
                  ev.evidence_claims, av.authority_evaluations
         order by o.canonical_name
        """,
        (item_code, item_code, TALENT_GRADE_VERSION),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_incomplete_profile_basis(cur: Any, *, item_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            o.id as object_id,
            o.object_code,
            o.canonical_name,
            o.normalized_name,
            pp.id as person_profile_id,
            pp.talent_grade::text as talent_grade,
            pp.talent_grade_basis,
            pp.review_status::text as profile_status,
            coalesce(pp.profile_payload->>'source', '') as profile_source,
            bool_or(tob.object_role = 'target_emperor') as is_target_emperor,
            array_remove(array_agg(distinct rt.emperor_name order by rt.emperor_name), null) as target_emperors,
            array_remove(array_agg(distinct pa.dynasty_label order by pa.dynasty_label), null) as known_dynasties,
            array_remove(array_agg(distinct pr.role_kind::text order by pr.role_kind::text), null) as role_kinds,
            array_remove(array_agg(distinct onm.name_kind::text || ':' || onm.name_text order by onm.name_kind::text || ':' || onm.name_text), null) as known_names
          from retrieval_v3.objects o
          join retrieval_v3.person_profiles pp on pp.object_id = o.id
          join retrieval_v3.target_objects tob on tob.object_id = o.id
          join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id
          left join retrieval_v3.person_affiliations pa
            on pa.object_id = o.id
           and pa.review_status in ('pending', 'accepted')
          left join retrieval_v3.person_roles pr
            on pr.object_id = o.id
           and pr.review_status in ('pending', 'accepted')
          left join retrieval_v3.object_names onm
            on onm.object_id = o.id
           and onm.review_status in ('pending', 'accepted')
         where o.object_type = 'person'
           and (%s = '' or rt.item_code = %s)
           and (
               btrim(pp.talent_grade_basis) = ''
               or pp.talent_grade_basis not like o.canonical_name || '，%%'
               or char_length(pp.talent_grade_basis) < 16
               or pp.talent_grade_basis = o.canonical_name || '，当前评价项目标皇帝。'
           )
         group by o.id, o.object_code, o.canonical_name, o.normalized_name,
                  pp.id, pp.talent_grade, pp.talent_grade_basis, pp.review_status, pp.profile_payload
         order by bool_or(tob.object_role = 'target_emperor') desc, o.canonical_name
        """,
        (item_code, item_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_pending_negative_talent(cur: Any, *, item_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select distinct on (o.id)
            o.id as object_id,
            o.object_code,
            o.canonical_name,
            o.normalized_name,
            pp.negative_talent_class::text as current_negative_talent_class,
            pp.negative_talent_severity::text as current_negative_talent_severity,
            pp.negative_talent_basis,
            coalesce(av.authority_evaluations, '[]'::jsonb) as authority_evaluations,
            coalesce(ev.evidence_claims, '[]'::jsonb) as evidence_claims
          from retrieval_v3.objects o
          join retrieval_v3.person_profiles pp on pp.object_id = o.id
          join retrieval_v3.target_objects tob on tob.object_id = o.id and tob.object_role <> 'target_emperor'
          join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id
          left join lateral (
              select jsonb_agg(jsonb_build_object(
                         'claim_key', ppl.claim_key,
                         'proposal_status', ppl.proposal_status::text,
                         'basis', ppl.basis,
                         'claim_summary', cc.claim_summary
                     ) order by ppl.claim_key) as authority_evaluations
                from retrieval_v3.person_profile_claim_links ppl
                join retrieval_v3.claim_cache cc on cc.claim_key = ppl.claim_key
               where coalesce(ppl.object_id, cc.object_id) = o.id
                 and ppl.profile_field = 'authority_evaluation'
                 and ppl.proposal_status in ('accepted', 'candidate', 'needs_review')
          ) av on true
          left join lateral (
              select jsonb_agg(jsonb_build_object(
                         'claim_key', q.claim_key,
                         'claim_summary', q.claim_summary,
                         'outcome', q.outcome
                     ) order by q.claim_key) as evidence_claims
                from (
                    select cc.claim_key, cc.claim_summary, cc.outcome
                      from retrieval_v3.claim_cache cc
                     where cc.object_id = o.id and cc.status = 'active'
                     order by cc.updated_at desc, cc.claim_key
                     limit 40
                ) q
          ) ev on true
         where o.object_type = 'person'
           and (%s = '' or rt.item_code = %s)
           and pp.talent_grade is not null
           and pp.negative_talent_version <> %s
         order by o.id, rt.id
        """,
        (item_code, item_code, NEGATIVE_TALENT_VERSION),
    )
    return [dict(row) for row in cur.fetchall()]


def target_period_item(row: Mapping[str, Any]) -> dict[str, Any]:
    code = workitem_code(TARGET_PERIOD_KIND, [row.get("target_code"), row.get("emperor_name")])
    return {
        "workitem_code": code,
        "task_kind": TARGET_PERIOD_KIND,
        "priority": 20,
        "subject": {
            "target_id": row.get("target_id"),
            "target_code": text(row.get("target_code")),
            "item_code": text(row.get("item_code")),
            "emperor_name": text(row.get("emperor_name")),
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
        },
        "context": {
            "current_role_title": text(row.get("role_title")),
            "current_profile_basis": text(row.get("talent_grade_basis")),
            "allowed_dynasty_labels": list(CANONICAL_PERIODS),
        },
        "required_patch": {
            "task_kind": TARGET_PERIOD_KIND,
            "workitem_code": code,
            "emperor_name": text(row.get("emperor_name")),
            "item_code": text(row.get("item_code")),
            "dynasty_label": "",
            "role_title": "",
            "basis": "",
        },
    }


def role_item(row: Mapping[str, Any]) -> dict[str, Any]:
    code = workitem_code(PERSON_ROLE_KIND, [row.get("object_id"), row.get("target_code")])
    return {
        "workitem_code": code,
        "task_kind": PERSON_ROLE_KIND,
        "priority": 40,
        "subject": {
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
            "canonical_name": text(row.get("canonical_name")),
            "normalized_name": text(row.get("normalized_name")),
            "target_code": text(row.get("target_code")),
            "target_emperor": text(row.get("emperor_name")),
            "item_code": text(row.get("item_code")),
        },
        "context": {
            "material_roles": [text(value) for value in row.get("material_roles") or [] if text(value)],
            "known_dynasties": [text(value) for value in row.get("known_dynasties") or [] if text(value)],
            "allowed_role_kinds": sorted(ROLE_KINDS),
        },
        "required_patch": {
            "task_kind": PERSON_ROLE_KIND,
            "workitem_code": code,
            "object_id": row.get("object_id"),
            "target_code": text(row.get("target_code")),
            "role_kind": "",
            "dynasty_label": "",
            "role_title": "",
            "basis": "",
        },
    }


def talent_item(row: Mapping[str, Any]) -> dict[str, Any]:
    code = workitem_code(PERSON_TALENT_KIND, row.get("object_id"))
    return {
        "workitem_code": code,
        "task_kind": PERSON_TALENT_KIND,
        "priority": 60,
        "subject": {
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
            "canonical_name": text(row.get("canonical_name")),
            "normalized_name": text(row.get("normalized_name")),
        },
        "context": {
            "target_emperors": [text(value) for value in row.get("target_emperors") or [] if text(value)],
            "known_dynasties": [text(value) for value in row.get("known_dynasties") or [] if text(value)],
            "role_kinds": [text(value) for value in row.get("role_kinds") or [] if text(value)],
            "current_profile_basis": text(row.get("talent_grade_basis")),
            "allowed_talent_grades": sorted(TALENT_GRADES),
            "rubric_version": TALENT_GRADE_VERSION,
            "rubric": {
                "ordinary_talent": "史料确认能够胜任职责，但没有形成明显的突出能力共识。",
                "usable_talent": "有明确专长和可靠表现，受到一定肯定，但影响主要限于局部或具体阶段。",
                "important_talent": "在政权运作、重大事务或专业领域发挥重要作用，史论评价较稳定。",
                "top_talent": "同时代同领域第一梯队，对重大历史进程、制度或文化建设具有关键作用。",
                "historic_talent": "跨时代公认的标杆人物，其方法、制度、思想或成就具有持续历史影响。",
            },
            "evidence_claims": row.get("evidence_claims") if isinstance(row.get("evidence_claims"), list) else [],
            "authority_evaluations": row.get("authority_evaluations") if isinstance(row.get("authority_evaluations"), list) else [],
            "allowed_authority_consensus": sorted(AUTHORITY_CONSENSUS_VALUES),
            "allowed_performance_support": sorted(EVIDENCE_STRENGTH_VALUES),
            "allowed_evidence_coverage": sorted(EVIDENCE_COVERAGE_VALUES),
        },
        "required_patch": {
            "task_kind": PERSON_TALENT_KIND,
            "workitem_code": code,
            "object_id": row.get("object_id"),
            "talent_grade": "",
            "talent_grade_confidence": None,
            "talent_authority_consensus": "",
            "talent_performance_support": "",
            "talent_evidence_coverage": "",
            "authority_sources": [],
            "talent_grade_basis": f"{text(row.get('canonical_name'))}，",
        },
    }


def negative_talent_item(row: Mapping[str, Any]) -> dict[str, Any]:
    code = workitem_code(PERSON_NEGATIVE_TALENT_KIND, row.get("object_id"))
    return {
        "workitem_code": code,
        "task_kind": PERSON_NEGATIVE_TALENT_KIND,
        "priority": 65,
        "subject": {
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
            "canonical_name": text(row.get("canonical_name")),
            "normalized_name": text(row.get("normalized_name")),
        },
        "context": {
            "rubric_version": NEGATIVE_TALENT_VERSION,
            "current_negative_talent_class": text(row.get("current_negative_talent_class")),
            "current_negative_talent_severity": text(row.get("current_negative_talent_severity")),
            "current_negative_talent_basis": text(row.get("negative_talent_basis")),
            "allowed_negative_talent_classes": sorted(NEGATIVE_TALENT_CLASSES),
            "allowed_negative_talent_severities": sorted(NEGATIVE_TALENT_SEVERITIES),
            "allowed_authority_consensus": sorted(AUTHORITY_CONSENSUS_VALUES),
            "allowed_fact_support": sorted(EVIDENCE_STRENGTH_VALUES),
            "allowed_evidence_coverage": sorted(EVIDENCE_COVERAGE_VALUES),
            "authority_evaluations": row.get("authority_evaluations") if isinstance(row.get("authority_evaluations"), list) else [],
            "evidence_claims": row.get("evidence_claims") if isinstance(row.get("evidence_claims"), list) else [],
            "class_rubric": {
                "sycophant": "以迎合、谄媚或取悦君主获得或维持权力。",
                "favorite": "主要依赖私人宠信、宫廷或亲缘关系取得政治影响。",
                "power_abuser": "滥权、专权、结党或破坏正常政治秩序。",
                "framer": "通过构陷、诬告或制造冤狱伤害他人。",
                "extractive_official": "通过聚敛、盘剥或财政行政手段造成显著社会损害。",
                "cruel_official": "酷烈执法、滥刑或以恐怖手段治理。",
                "incompetent_harmful": "能力不足却占据关键位置并造成明确重大损害。",
                "traitorous_actor": "有明确背叛其政治共同体的行为；不得仅据败亡、投降或敌对史书定性。",
                "mixed_or_disputed": "权威来源之间存在无法消解的类型或性质冲突。",
            },
        },
        "required_patch": {
            "task_kind": PERSON_NEGATIVE_TALENT_KIND,
            "workitem_code": code,
            "object_id": row.get("object_id"),
            "has_negative_talent_class": None,
            "negative_talent_class": "",
            "negative_talent_severity": "",
            "negative_talent_confidence": None,
            "negative_authority_consensus": "",
            "negative_fact_support": "",
            "negative_evidence_coverage": "",
            "authority_sources": [],
            "negative_talent_basis": f"{text(row.get('canonical_name'))}，",
        },
    }


def profile_basis_item(row: Mapping[str, Any]) -> dict[str, Any]:
    code = workitem_code(PERSON_PROFILE_BASIS_KIND, row.get("object_id"))
    return {
        "workitem_code": code,
        "task_kind": PERSON_PROFILE_BASIS_KIND,
        "priority": 70,
        "subject": {
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
            "canonical_name": text(row.get("canonical_name")),
            "normalized_name": text(row.get("normalized_name")),
            "is_target_emperor": bool(row.get("is_target_emperor")),
        },
        "context": {
            "current_talent_grade": text(row.get("talent_grade")),
            "current_profile_basis": text(row.get("talent_grade_basis")),
            "profile_status": text(row.get("profile_status")),
            "profile_source": text(row.get("profile_source")),
            "target_emperors": [text(value) for value in row.get("target_emperors") or [] if text(value)],
            "known_dynasties": [text(value) for value in row.get("known_dynasties") or [] if text(value)],
            "role_kinds": [text(value) for value in row.get("role_kinds") or [] if text(value)],
            "known_names": [text(value) for value in row.get("known_names") or [] if text(value)],
        },
        "required_patch": {
            "task_kind": PERSON_PROFILE_BASIS_KIND,
            "workitem_code": code,
            "object_id": row.get("object_id"),
            "talent_grade_basis": f"{text(row.get('canonical_name'))}，",
        },
    }


def build_workitems(*, dsn: str, item_code: str, kinds: Sequence[str], object_ids: Sequence[int] = ()) -> list[dict[str, Any]]:
    selected = set(kinds or TASK_KINDS)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            rows: list[dict[str, Any]] = []
            if TARGET_PERIOD_KIND in selected:
                rows.extend(target_period_item(row) for row in fetch_target_period_gaps(cur, item_code=item_code))
            if PERSON_ROLE_KIND in selected:
                rows.extend(role_item(row) for row in fetch_missing_roles(cur, item_code=item_code))
            if PERSON_TALENT_KIND in selected:
                rows.extend(talent_item(row) for row in fetch_missing_talent(cur, item_code=item_code))
            if PERSON_NEGATIVE_TALENT_KIND in selected:
                rows.extend(negative_talent_item(row) for row in fetch_pending_negative_talent(cur, item_code=item_code))
            if PERSON_PROFILE_BASIS_KIND in selected:
                rows.extend(profile_basis_item(row) for row in fetch_incomplete_profile_basis(cur, item_code=item_code))
    selected_object_ids = {int(value) for value in object_ids}
    if selected_object_ids:
        rows = [row for row in rows if int((row.get("subject") or {}).get("object_id") or 0) in selected_object_ids]
    return sorted(rows, key=lambda row: (int(row.get("priority") or 0), text(row.get("task_kind")), text(row.get("workitem_code"))))


def prompt_for_task(*, task: Mapping[str, Any], workitems: Sequence[Mapping[str, Any]], patch_path: Path) -> str:
    kind = text(task.get("task_kind"))
    schema_notes = {
        TARGET_PERIOD_KIND: "为每个目标皇帝填写 dynasty_label；必须是 allowed_dynasty_labels 之一。basis 只写具体判断，例如“司马炎为西晋开国皇帝”。",
        PERSON_ROLE_KIND: "为每个人物填写 role_kind；只能用 allowed_role_kinds。只有无法判定时才用 other，并在 basis 写明原因。",
        PERSON_TALENT_KIND: "按 rubric_version 先用 authority_evaluations 确定史论共识基础档，再用 evidence_claims 校准；只能用 allowed_talent_grades。若输入没有权威评价，必须只读检索正史论赞、后世史论或现代专业研究，并把来源标题、定位和评价摘要写入 authority_sources；找不到有效权威来源则不要输出该人物。材料不足降低 evidence_coverage 和 confidence，不得直接降为普通。不得用官职、名气、忠诚、政治结局或品格替代能力判断。talent_grade_basis 必须以“姓名，”开头，分别说明史论共识、事实校准、主要限制或争议。",
        PERSON_NEGATIVE_TALENT_KIND: "先用 authority_evaluations 判断负面政治风险共识，再用 evidence_claims 校准。若没有稳定负面分类，has_negative_talent_class=false，其余类型和严重度留空，但仍填写共识、事实支持、覆盖度、置信度和依据。不得仅凭被诛、被贬、败亡、投降、党争结局或单一敌对来源定性；能力、品格和政治风险必须分开。",
        PERSON_PROFILE_BASIS_KIND: "只补人物评价简介 talent_grade_basis，不修改 talent_grade。talent_grade_basis 必须以“姓名，”开头，写高信息量中文评价，不写模板句。",
    }
    return (
        "# retrieval_v3 judgment task\n\n"
        "你是消费侧判断子进程。不要修改代码、数据库或 schema；唯一允许写入的是指定 JSONL patch 文件。\n"
        "可以只读检索本地材料；不得执行破坏性命令。无法判断的项不要写入 patch。\n\n"
        f"- task_kind: `{kind}`\n"
        f"- patch_path: `{repo_relative(patch_path)}`\n"
        f"- 要求: {schema_notes.get(kind, '')}\n\n"
        "输出要求：每行一个 JSON object，字段必须符合每个 workitem 的 `required_patch`。无法判断的项不要写入 patch。\n"
        f"若不能写入 patch 文件，在最终消息中用独占行 {PATCH_JSONL_BEGIN} 和 {PATCH_JSONL_END} 包住同样的 JSONL。\n\n"
        "## Workitems\n\n"
        "```json\n"
        + json.dumps(list(workitems), ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def build_codex_tasks(workitems: Sequence[Mapping[str, Any]], *, output_root: Path, batch_size: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    by_kind: dict[str, list[Mapping[str, Any]]] = {}
    for item in workitems:
        by_kind.setdefault(text(item.get("task_kind")), []).append(item)
    for kind, rows in sorted(by_kind.items()):
        for batch_index, batch in enumerate(chunks(rows, batch_size), start=1):
            code = task_code(kind, batch)
            prompt_path = output_root / "prompts" / f"{code}.md"
            patch_path = output_root / "patches" / f"{code}.jsonl"
            last_message_path = output_root / "logs" / f"{code}.last.md"
            log_path = output_root / "logs" / f"{code}.jsonl"
            task = {
                "task_code": code,
                "task_kind": kind,
                "batch_index": batch_index,
                "workitem_codes": [text(row.get("workitem_code")) for row in batch],
                "prompt_path": repo_relative(prompt_path),
                "patch_path": repo_relative(patch_path),
                "expected_outputs": [
                    {
                        "kind": "jsonl_patch",
                        "path": repo_relative(patch_path),
                        "fallback": "last_message_marked_block",
                        "begin": PATCH_JSONL_BEGIN,
                        "end": PATCH_JSONL_END,
                    }
                ],
                "last_message_path": repo_relative(last_message_path),
                "log_path": repo_relative(log_path),
                "argv": agent_runtime_config.codex_task_argv(
                    "identity_judgment",
                    exec_args=[
                        "-C", str(ROOT), "--dangerously-bypass-approvals-and-sandbox",
                        "--output-last-message", str(last_message_path), "--json", "-",
                    ],
                ),
            }
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt_for_task(task=task, workitems=batch, patch_path=patch_path), encoding="utf-8")
            tasks.append(task)
    return tasks


def render_markdown(*, workitems: Sequence[Mapping[str, Any]], tasks: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 judgment worklist",
        "",
        f"- total_workitems: `{summary['totals']['workitems']}`",
        f"- codex_tasks: `{summary['totals']['codex_tasks']}`",
        "",
        "## Counts",
        "",
        "| kind | count |",
        "| --- | ---: |",
    ]
    for kind, count in summary["counts_by_kind"].items():
        lines.append(f"| `{kind}` | {count} |")
    lines.extend(["", "## Codex Tasks", "", "| task | kind | workitems | patch |", "| --- | --- | ---: | --- |"])
    for task in tasks:
        lines.append(f"| `{task['task_code']}` | `{task['task_kind']}` | {len(task['workitem_codes'])} | `{task['patch_path']}` |")
    if workitems:
        lines.extend(["", "## Workitems", ""])
        for item in workitems[:120]:
            subject = item.get("subject") if isinstance(item.get("subject"), Mapping) else {}
            name = subject.get("emperor_name") or subject.get("canonical_name") or subject.get("object_code") or ""
            lines.append(f"- `{item.get('workitem_code')}` `{item.get('task_kind')}` {name}")
        if len(workitems) > 120:
            lines.append(f"- ... {len(workitems) - 120} more")
    return "\n".join(lines).rstrip() + "\n"


def write_worklist_outputs(*, output_root: Path, workitems: Sequence[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    tasks = build_codex_tasks(workitems, output_root=output_root, batch_size=batch_size)
    workitems_path = output_root / "judgment_workitems.jsonl"
    tasks_path = output_root / "codex_tasks.jsonl"
    summary_path = output_root / "judgment_summary.json"
    md_path = output_root / "judgment_worklist.md"
    write_jsonl(workitems_path, workitems)
    write_jsonl(tasks_path, tasks)
    counts = Counter(text(row.get("task_kind")) for row in workitems)
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_judgment_worklists.py",
        "totals": {
            "workitems": len(workitems),
            "codex_tasks": len(tasks),
        },
        "counts_by_kind": dict(sorted(counts.items())),
        "files": {
            "workitems": repo_relative(workitems_path),
            "codex_tasks": repo_relative(tasks_path),
            "markdown": repo_relative(md_path),
        },
    }
    write_json(summary_path, summary)
    md_path.write_text(render_markdown(workitems=workitems, tasks=tasks, summary=summary), encoding="utf-8")
    return summary


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def run_codex_tasks(
    *,
    tasks_path: Path,
    execute: bool,
    background: bool,
    limit: int,
    output: Path | None,
    agent_output_root: Path | None = None,
    codex_win_bin: str = "codex-win",
    max_workers: int = 4,
    timeout_seconds: int = 1800,
    sandbox_profile: str = "local-write",
    respect_task_argv: bool = False,
    search: bool = False,
) -> dict[str, Any]:
    agent_root = agent_output_root or (tasks_path.parent / "agent_run")
    agent_root.mkdir(parents=True, exist_ok=True)
    tasks_for_agent = tasks_path
    if limit > 0:
        tasks = load_tasks(tasks_path)[:limit]
        tasks_for_agent = agent_root / "limited_tasks.jsonl"
        write_jsonl(tasks_for_agent, tasks)

    argv = [
        codex_win_bin,
        "agent",
        "run-plan",
        "--tasks-jsonl",
        str(tasks_for_agent),
        "--output-root",
        str(agent_root),
        "--cwd",
        str(ROOT),
        "--max-workers",
        str(max(1, max_workers)),
        "--timeout-seconds",
        str(max(1, timeout_seconds)),
        "--sandbox-profile",
        sandbox_profile,
    ]
    if background:
        argv.append("--background")
    if not execute:
        argv.append("--dry-run")
    if respect_task_argv:
        argv.append("--respect-task-argv")
    if search:
        argv.append("--search")

    completed = subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        agent_payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise JudgmentWorklistError(
            f"codex-win agent run-plan returned non-JSON stdout rc={completed.returncode}: {completed.stdout[:400]}"
        ) from exc

    payload = {
        "generated_by": "scripts/dev/retrieval_v3_judgment_worklists.py",
        "runner": "codex-win agent run-plan",
        "execute": execute,
        "background": background,
        "returncode": completed.returncode,
        "agent_output_root": repo_relative(agent_root),
        "tasks_jsonl": repo_relative(tasks_for_agent),
        "command": argv,
        "results": agent_payload.get("tasks", []),
        "totals": agent_payload.get("totals", {}),
        "agent": agent_payload,
    }
    if completed.stderr:
        payload["stderr"] = completed.stderr
    if output:
        write_json(output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end="")
    return payload


def require_period(value: Any) -> str:
    period = text(value)
    if period not in CANONICAL_PERIODS:
        raise JudgmentWorklistError(f"unsupported dynasty_label: {period}")
    return period


def require_role(value: Any) -> str:
    role = text(value)
    if role not in ROLE_KINDS:
        raise JudgmentWorklistError(f"unsupported role_kind: {role}")
    return role


def require_grade(value: Any) -> str:
    grade = text(value)
    if grade not in TALENT_GRADES:
        raise JudgmentWorklistError(f"unsupported talent_grade: {grade}")
    return grade


def require_choice(value: Any, allowed: set[str], field: str) -> str:
    selected = text(value)
    if selected not in allowed:
        raise JudgmentWorklistError(f"unsupported {field}: {selected}")
    return selected


def require_confidence(value: Any, field: str) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise JudgmentWorklistError(f"unsupported {field}: {value}") from exc
    if confidence < 0 or confidence > 1:
        raise JudgmentWorklistError(f"unsupported {field}: {value}")
    return confidence


def fetch_one(cur: Any) -> dict[str, Any]:
    row = cur.fetchone()
    if not row:
        raise JudgmentWorklistError("expected row")
    return dict(row)


def upsert_target_period(cur: Any, row: Mapping[str, Any]) -> None:
    emperor = text(row.get("emperor_name"))
    item_code = text(row.get("item_code") or "I5B")
    period = require_period(row.get("dynasty_label"))
    role_title = text(row.get("role_title"))
    basis = text(row.get("basis"))
    if not basis:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: basis is required")
    cur.execute(
        """
        select o.id as object_id, o.object_identity_key
          from retrieval_v3.retrieval_targets rt
          join retrieval_v3.target_objects tob on tob.target_id = rt.id and tob.object_role = 'target_emperor'
          join retrieval_v3.objects o on o.id = tob.object_id
         where rt.emperor_name = %s
           and rt.item_code = %s
         order by rt.id
         limit 1
        """,
        (emperor, item_code),
    )
    target = fetch_one(cur)
    identity_key = text(target["object_identity_key"])
    aff_key = "|".join([identity_key, "affiliation", "dynasty", period])
    payload = {"source": "retrieval_v3_judgment_patch", "patch": {k: v for k, v in row.items() if not str(k).startswith("_")}}
    cur.execute(
        """
        insert into retrieval_v3.person_affiliations (
            person_affiliation_code, person_affiliation_key, object_id, affiliation_kind,
            dynasty_label, affiliation_basis, review_status, affiliation_payload
        )
        values (%s, %s, %s, 'dynasty', %s, %s, 'accepted', %s::jsonb)
        on conflict on constraint rv3_person_affiliations_key_uk do update set
            dynasty_label = excluded.dynasty_label,
            affiliation_basis = excluded.affiliation_basis,
            review_status = 'accepted',
            affiliation_payload = excluded.affiliation_payload,
            updated_at = now()
        """,
        ("PAF-" + stable_hash(aff_key, length=16), aff_key, int(target["object_id"]), period, basis, json_param(payload)),
    )
    role_key = "|".join([identity_key, "role", "emperor"])
    cur.execute(
        """
        update retrieval_v3.person_roles
           set dynasty_label = %s,
               role_title = case when %s <> '' then %s else role_title end,
               role_basis = %s,
               role_payload = role_payload || %s::jsonb,
               review_status = 'accepted',
               updated_at = now()
         where person_role_key = %s
        """,
        (period, role_title, role_title, basis, json_param(payload), role_key),
    )
    profile_basis = f"{emperor}，当前评价项目标皇帝；朝代为{period}" + (f"；称号为{role_title}" if role_title else "") + "。"
    cur.execute(
        """
        update retrieval_v3.person_profiles
           set talent_grade_basis = %s,
               profile_payload = profile_payload || %s::jsonb,
               review_status = 'accepted',
               updated_at = now()
         where object_id = %s
           and coalesce(profile_payload->>'source', '') = 'retrieval_v3_target_person_consumer'
        """,
        (profile_basis, json_param(payload), int(target["object_id"])),
    )


def upsert_person_role(cur: Any, row: Mapping[str, Any]) -> None:
    object_id = int(row.get("object_id") or 0)
    target_code = text(row.get("target_code"))
    role_kind = require_role(row.get("role_kind"))
    period = text(row.get("dynasty_label"))
    if period:
        require_period(period)
    basis = text(row.get("basis"))
    if not object_id or not target_code or not basis:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: object_id, target_code and basis are required")
    cur.execute(
        """
        select o.object_code
          from retrieval_v3.objects o
         where o.id = %s
        """,
        (object_id,),
    )
    obj = fetch_one(cur)
    cur.execute(
        """
        select pa.id
          from retrieval_v3.person_affiliations pa
         where pa.object_id = %s
           and pa.review_status in ('pending', 'accepted')
           and (pa.affiliation_payload->>'target_code' = %s or pa.dynasty_label = %s)
         order by (pa.affiliation_payload->>'target_code' = %s) desc, pa.id
         limit 1
        """,
        (object_id, target_code, period, target_code),
    )
    affiliation = cur.fetchone()
    role_key = "|".join(["object", text(obj["object_code"]), "role", role_kind, "target", target_code])
    payload = {"source": "retrieval_v3_judgment_patch", "patch": {k: v for k, v in row.items() if not str(k).startswith("_")}}
    cur.execute(
        """
        insert into retrieval_v3.person_roles (
            person_role_code, person_role_key, object_id, person_affiliation_id,
            role_kind, dynasty_label, role_title, role_basis, review_status, role_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v3.rv3_person_role_kind, %s, %s, %s, 'accepted', %s::jsonb)
        on conflict on constraint rv3_person_roles_key_uk do update set
            person_affiliation_id = coalesce(excluded.person_affiliation_id, retrieval_v3.person_roles.person_affiliation_id),
            dynasty_label = excluded.dynasty_label,
            role_title = excluded.role_title,
            role_basis = excluded.role_basis,
            review_status = 'accepted',
            role_payload = excluded.role_payload,
            updated_at = now()
        """,
        (
            "PRO-" + stable_hash(role_key, length=16),
            role_key,
            object_id,
            int(affiliation["id"]) if affiliation else None,
            role_kind,
            period,
            text(row.get("role_title")),
            basis,
            json_param(payload),
        ),
    )


def update_talent_grade(cur: Any, row: Mapping[str, Any]) -> None:
    object_id = int(row.get("object_id") or 0)
    grade = require_grade(row.get("talent_grade"))
    confidence = require_confidence(row.get("talent_grade_confidence"), "talent_grade_confidence")
    authority_consensus = require_choice(row.get("talent_authority_consensus"), AUTHORITY_CONSENSUS_VALUES, "talent_authority_consensus")
    authority_sources = row.get("authority_sources")
    if authority_consensus == "none" or not isinstance(authority_sources, list) or not authority_sources:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: talent-grade-v2 requires authority consensus and authority_sources")
    performance_support = require_choice(row.get("talent_performance_support"), EVIDENCE_STRENGTH_VALUES, "talent_performance_support")
    evidence_coverage = require_choice(row.get("talent_evidence_coverage"), EVIDENCE_COVERAGE_VALUES, "talent_evidence_coverage")
    basis = text(row.get("talent_grade_basis"))
    if not object_id or not basis or "，" not in basis:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: object_id and Chinese talent_grade_basis are required")
    payload = {"source": "retrieval_v3_judgment_patch", "patch": {k: v for k, v in row.items() if not str(k).startswith("_")}}
    cur.execute(
        """
        update retrieval_v3.person_profiles
           set talent_grade = %s::retrieval_v3.rv3_person_talent_grade,
               talent_grade_basis = %s,
               talent_grade_version = %s,
               talent_grade_confidence = %s,
               talent_authority_consensus = %s::retrieval_v3.rv3_authority_consensus,
               talent_performance_support = %s::retrieval_v3.rv3_evidence_strength,
               talent_evidence_coverage = %s::retrieval_v3.rv3_evidence_coverage,
               review_status = 'accepted',
               profile_payload = profile_payload || %s::jsonb,
               updated_at = now()
         where object_id = %s
        """,
        (
            grade, basis, TALENT_GRADE_VERSION, confidence, authority_consensus,
            performance_support, evidence_coverage,
            json_param(payload | {"talent_grade_version": TALENT_GRADE_VERSION}), object_id,
        ),
    )
    if cur.rowcount != 1:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: person profile not found for object_id {object_id}")


def update_negative_talent(cur: Any, row: Mapping[str, Any]) -> None:
    object_id = int(row.get("object_id") or 0)
    has_negative = row.get("has_negative_talent_class")
    if not isinstance(has_negative, bool):
        raise JudgmentWorklistError(f"{row.get('_line_no')}: has_negative_talent_class must be boolean")
    negative_class = text(row.get("negative_talent_class"))
    severity = text(row.get("negative_talent_severity"))
    if has_negative:
        negative_class = require_choice(negative_class, NEGATIVE_TALENT_CLASSES, "negative_talent_class")
        severity = require_choice(severity, NEGATIVE_TALENT_SEVERITIES, "negative_talent_severity")
    elif negative_class or severity:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: negative class and severity must be blank when has_negative_talent_class is false")
    confidence = require_confidence(row.get("negative_talent_confidence"), "negative_talent_confidence")
    authority_consensus = require_choice(row.get("negative_authority_consensus"), AUTHORITY_CONSENSUS_VALUES, "negative_authority_consensus")
    authority_sources = row.get("authority_sources")
    if has_negative and (authority_consensus == "none" or not isinstance(authority_sources, list) or not authority_sources):
        raise JudgmentWorklistError(f"{row.get('_line_no')}: negative classification requires authority consensus and authority_sources")
    fact_support = require_choice(row.get("negative_fact_support"), EVIDENCE_STRENGTH_VALUES, "negative_fact_support")
    evidence_coverage = require_choice(row.get("negative_evidence_coverage"), EVIDENCE_COVERAGE_VALUES, "negative_evidence_coverage")
    basis = text(row.get("negative_talent_basis"))
    if not object_id or not basis or "，" not in basis:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: object_id and Chinese negative_talent_basis are required")
    payload = {"source": "retrieval_v3_judgment_patch", "patch": {k: v for k, v in row.items() if not str(k).startswith("_")}}
    cur.execute(
        """
        update retrieval_v3.person_profiles
           set negative_talent_class = %s::retrieval_v3.rv3_negative_talent_class,
               negative_talent_severity = %s::retrieval_v3.rv3_negative_talent_severity,
               negative_talent_confidence = %s,
               negative_authority_consensus = %s::retrieval_v3.rv3_authority_consensus,
               negative_fact_support = %s::retrieval_v3.rv3_evidence_strength,
               negative_evidence_coverage = %s::retrieval_v3.rv3_evidence_coverage,
               negative_talent_basis = %s,
               negative_talent_version = %s,
               profile_payload = profile_payload || %s::jsonb,
               updated_at = now()
         where object_id = %s
        """,
        (
            negative_class or None, severity or None, confidence, authority_consensus,
            fact_support, evidence_coverage, basis, NEGATIVE_TALENT_VERSION,
            json_param(payload | {"negative_talent_version": NEGATIVE_TALENT_VERSION}), object_id,
        ),
    )
    if cur.rowcount != 1:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: person profile not found for object_id {object_id}")


def update_profile_basis(cur: Any, row: Mapping[str, Any]) -> None:
    object_id = int(row.get("object_id") or 0)
    basis = text(row.get("talent_grade_basis"))
    if not object_id or not basis or "，" not in basis or len(basis) < 16:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: object_id and high-information Chinese talent_grade_basis are required")
    cur.execute(
        """
        select canonical_name
          from retrieval_v3.objects
         where id = %s
           and object_type = 'person'
        """,
        (object_id,),
    )
    obj = fetch_one(cur)
    prefix = f"{text(obj.get('canonical_name'))}，"
    if not basis.startswith(prefix):
        raise JudgmentWorklistError(f"{row.get('_line_no')}: talent_grade_basis must start with {prefix}")
    payload = {"source": "retrieval_v3_profile_basis_patch", "patch": {k: v for k, v in row.items() if not str(k).startswith("_")}}
    cur.execute(
        """
        update retrieval_v3.person_profiles
           set talent_grade_basis = %s,
               review_status = 'accepted',
               profile_payload = profile_payload || %s::jsonb,
               updated_at = now()
         where object_id = %s
        """,
        (basis, json_param(payload), object_id),
    )
    if cur.rowcount != 1:
        raise JudgmentWorklistError(f"{row.get('_line_no')}: person profile not found for object_id {object_id}")


def apply_patch_rows(*, dsn: str, rows: Sequence[Mapping[str, Any]], execute: bool) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    counts: Counter[str] = Counter()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for row in rows:
                kind = text(row.get("task_kind"))
                if kind == TARGET_PERIOD_KIND:
                    upsert_target_period(cur, row)
                elif kind == PERSON_ROLE_KIND:
                    upsert_person_role(cur, row)
                elif kind == PERSON_TALENT_KIND:
                    update_talent_grade(cur, row)
                elif kind == PERSON_NEGATIVE_TALENT_KIND:
                    update_negative_talent(cur, row)
                elif kind == PERSON_PROFILE_BASIS_KIND:
                    update_profile_basis(cur, row)
                else:
                    raise JudgmentWorklistError(f"{row.get('_line_no')}: unsupported task_kind {kind}")
                counts[kind] += 1
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "generated_by": "scripts/dev/retrieval_v3_judgment_worklists.py",
        "write_db": execute,
        "ok": True,
        "applied_counts": dict(sorted(counts.items())),
        "rows": len(rows),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and apply retrieval_v3 consumer judgment worklists.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worklist = subparsers.add_parser("worklist", help="Build DB-backed judgment workitems and Codex CLI task prompts.")
    worklist.add_argument("--env-file", type=Path)
    worklist.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    worklist.add_argument("--item-code", default="I5B")
    worklist.add_argument("--kind", choices=TASK_KINDS, action="append", default=[])
    worklist.add_argument("--object-id", type=int, action="append", default=[], help="Limit person workitems to explicit retrieval_v3 object IDs; repeatable.")
    worklist.add_argument("--batch-size", type=int)
    worklist.add_argument("--output-root", type=Path, required=True)

    run_plan = subparsers.add_parser("run-plan", help="Run or start Codex CLI tasks from codex_tasks.jsonl.")
    run_plan.add_argument("--tasks-jsonl", type=Path, required=True)
    run_plan.add_argument("--execute", action="store_true")
    run_plan.add_argument("--background", action="store_true")
    run_plan.add_argument("--limit", type=int, default=0)
    run_plan.add_argument("--output", type=Path)
    run_plan.add_argument("--agent-output-root", type=Path)
    run_plan.add_argument("--codex-win-bin", default="codex-win")
    run_plan.add_argument("--max-workers", type=int)
    run_plan.add_argument("--timeout-seconds", type=int)
    run_plan.add_argument("--sandbox-profile", choices=("read-only", "local-write", "bypass"), default="local-write")
    run_plan.add_argument("--respect-task-argv", action="store_true")
    run_plan.add_argument("--search", action="store_true")

    apply = subparsers.add_parser("apply-patch", help="Validate and apply judgment patch JSONL; dry-run unless --execute.")
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    apply.add_argument("--patch-jsonl", type=Path, action="append", required=True)
    apply.add_argument("--execute", action="store_true")
    apply.add_argument("--output-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "worklist":
        load_env_file(args.env_file)
        dsn = resolve_dsn(args.dsn_env)
        workitems = build_workitems(
            dsn=dsn,
            item_code=args.item_code,
            kinds=args.kind or TASK_KINDS,
            object_ids=args.object_id,
        )
        runtime = agent_runtime_config.resolve_agent_stage("identity_judgment")
        summary = write_worklist_outputs(
            output_root=args.output_root,
            workitems=workitems,
            batch_size=int(args.batch_size or runtime["batch_size"]),
        )
        print(json.dumps({"output_root": str(args.output_root), "totals": summary["totals"], "counts_by_kind": summary["counts_by_kind"]}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "run-plan":
        runtime = agent_runtime_config.resolve_agent_stage("identity_judgment")
        payload = run_codex_tasks(
            tasks_path=args.tasks_jsonl,
            execute=args.execute,
            background=args.background,
            limit=max(0, args.limit),
            output=args.output,
            agent_output_root=args.agent_output_root,
            codex_win_bin=args.codex_win_bin,
            max_workers=int(args.max_workers or runtime["max_workers"]),
            timeout_seconds=int(args.timeout_seconds or runtime["timeout_seconds"]),
            sandbox_profile=args.sandbox_profile,
            respect_task_argv=args.respect_task_argv,
            search=args.search,
        )
        return 0 if payload["returncode"] == 0 and payload["totals"].get("failed", 0) == 0 else 1
    if args.command == "apply-patch":
        load_env_file(args.env_file)
        dsn = resolve_dsn(args.dsn_env)
        rows = [row for path in args.patch_jsonl for row in read_jsonl(path)]
        payload = apply_patch_rows(dsn=dsn, rows=rows, execute=args.execute)
        write_json(args.output_json, payload)
        print(json.dumps({"ok": payload["ok"], "rows": payload["rows"], "write_db": payload["write_db"]}, ensure_ascii=False, sort_keys=True))
        return 0
    raise JudgmentWorklistError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
