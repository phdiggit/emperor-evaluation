from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "i5b-scholarly-object-profile-contract-v1"
REPORT_SCHEMA_VERSION = "i5b-scholarly-object-profile-report-v1"
SUBJECT_KINDS = {"person", "institution", "policy"}
AUTHORITY_CLASSES = {
    "peer_reviewed_journal",
    "academic_monograph",
    "university_academic_publication",
}
ALLOWED_USES = {
    "retrieval_query_expansion",
    "primary_source_location",
    "judge_context",
}
PROHIBITED_USES = {
    "formal_fact_acceptance",
    "factor_choice",
    "score_contribution",
}


def _load(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("学术对象画像合同顶层必须为对象")
    return payload


def _strings(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} 必须为字符串列表")
    values = tuple(str(item).strip() for item in value)
    if not values or "" in values or len(values) != len(set(values)):
        raise ValueError(f"{label} 必须非空且唯一")
    return values


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def build_scholarly_object_profile_report(contract_path: Path) -> dict[str, Any]:
    contract_path = contract_path if contract_path.is_absolute() else ROOT / contract_path
    contract = _load(contract_path)
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("学术对象画像合同 schema_version 不匹配")
    if contract.get("status") != "research_context_only":
        raise ValueError("学术对象画像只能保持 research_context_only")

    sources: dict[str, Mapping[str, Any]] = {}
    for source in contract.get("scholarly_sources") or ():
        source_ref = str(source.get("source_ref") or "").strip()
        if not source_ref or source_ref in sources:
            raise ValueError("学术来源 source_ref 缺失或重复")
        if source.get("authority_class") not in AUTHORITY_CLASSES:
            raise ValueError(f"{source_ref} authority_class 非法")
        for field in (
            "author",
            "title",
            "publication",
            "canonical_url",
            "source_version",
            "retrieved_on",
        ):
            if not str(source.get(field) or "").strip():
                raise ValueError(f"{source_ref}.{field} 缺失")
        sources[source_ref] = source

    profiles: list[dict[str, Any]] = []
    seen_profiles: set[str] = set()
    seen_subjects: set[str] = set()
    for profile in contract.get("profiles") or ():
        profile_ref = str(profile.get("profile_ref") or "").strip()
        subject = profile.get("subject") or {}
        subject_ref = str(subject.get("ref") or "").strip()
        if not profile_ref or profile_ref in seen_profiles:
            raise ValueError("profile_ref 缺失或重复")
        if not subject_ref or subject_ref in seen_subjects:
            raise ValueError("同一合同中 subject.ref 必须非空且唯一")
        if subject.get("kind") not in SUBJECT_KINDS:
            raise ValueError(f"{profile_ref} subject.kind 非法")
        if not str(subject.get("label") or "").strip():
            raise ValueError(f"{profile_ref} subject.label 缺失")
        allowed = set(_strings(profile.get("allowed_uses"), label="allowed_uses"))
        prohibited = set(
            _strings(profile.get("prohibited_uses"), label="prohibited_uses")
        )
        if allowed != ALLOWED_USES or prohibited != PROHIBITED_USES:
            raise ValueError(f"{profile_ref} 使用边界不完整")

        summaries: list[dict[str, Any]] = []
        for item in profile.get("summary_items") or ():
            summary_ref = str(item.get("summary_ref") or "").strip()
            normalized_summary = str(item.get("normalized_summary") or "").strip()
            source_refs = _strings(
                item.get("scholarly_source_refs"), label=f"{summary_ref}.source_refs"
            )
            unknown = sorted(set(source_refs) - set(sources))
            if not summary_ref or not normalized_summary or unknown:
                raise ValueError(
                    f"{profile_ref} 总结项缺失或引用未知来源: {unknown}"
                )
            locators = list(item.get("primary_source_locators") or ())
            if not locators:
                raise ValueError(f"{summary_ref} 必须包含原始史料定位")
            for locator in locators:
                if locator.get("status") not in {
                    "located",
                    "located_pending_formal_acceptance",
                }:
                    raise ValueError(f"{summary_ref} 原始史料尚未定位")
                for field in ("work", "section", "canonical_url"):
                    if not str(locator.get(field) or "").strip():
                        raise ValueError(f"{summary_ref}.locator.{field} 缺失")
            summaries.append(
                {
                    "summary_ref": summary_ref,
                    "normalized_summary": normalized_summary,
                    "scholarly_source_refs": list(source_refs),
                    "primary_source_locators": locators,
                    "formal_assertion_refs": list(
                        _strings(
                            item.get("formal_assertion_refs"),
                            label=f"{summary_ref}.formal_assertion_refs",
                        )
                    )
                    if item.get("formal_assertion_refs")
                    else [],
                    "disputed_points": list(item.get("disputed_points") or ()),
                    "retrieval_terms": list(
                        _strings(
                            item.get("retrieval_terms"),
                            label=f"{summary_ref}.retrieval_terms",
                        )
                    ),
                }
            )
        if not summaries:
            raise ValueError(f"{profile_ref} 缺少 summary_items")
        profiles.append(
            {
                "profile_ref": profile_ref,
                "profile_version": str(profile.get("profile_version") or ""),
                "subject": dict(subject),
                "summary_items": summaries,
                "allowed_uses": sorted(allowed),
                "prohibited_uses": sorted(prohibited),
            }
        )
        seen_profiles.add(profile_ref)
        seen_subjects.add(subject_ref)

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "scholarly_object_profiles_ready",
        "task_code": str(contract["task_code"]),
        "contract_ref": str(contract_path.relative_to(ROOT)).replace("\\", "/"),
        "contract_sha256": sha256(contract_path.read_bytes()).hexdigest(),
        "scholarly_sources": [dict(value) for value in sources.values()],
        "profiles": profiles,
        "summary": {
            "scholarly_source_count": len(sources),
            "profile_count": len(profiles),
            "summary_item_count": sum(len(row["summary_items"]) for row in profiles),
            "subject_kind_counts": {
                kind: sum(row["subject"]["kind"] == kind for row in profiles)
                for kind in sorted(SUBJECT_KINDS)
            },
        },
        "declarations": {
            "secondary_scholarship_is_formal_fact": False,
            "primary_source_location_required": True,
            "direct_factor_choice_allowed": False,
            "direct_score_contribution_allowed": False,
            "model_call_count": 0,
            "database_write_count": 0,
            "migration_executed": False,
        },
    }
    report["report_sha256"] = _stable_hash(report)
    return report


def render_scholarly_object_profile_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# 学术成果辅助对象画像",
        "",
        "学术总结只用于扩展检索、定位原始史料和提供Judge背景，不直接接受为V4事实或计分因子。",
        "",
        "| 对象 | 类型 | 学术总结 | 原始史料定位 |",
        "|---|---|---|---|",
    ]
    for profile in report["profiles"]:
        for item in profile["summary_items"]:
            locators = "；".join(
                f"{row['work']}·{row['section']}" for row in item["primary_source_locators"]
            )
            lines.append(
                f"| {profile['subject']['label']} | {profile['subject']['kind']} | "
                f"{item['normalized_summary']} | {locators} |"
            )
    lines.extend(["", "本报告不生成正式事实、材料分、45分、tier或排名。", ""])
    return "\n".join(lines)


def write_scholarly_object_profile_report(
    *, contract_path: Path, output_json: Path, output_markdown: Path
) -> dict[str, Any]:
    report = build_scholarly_object_profile_report(contract_path)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_markdown.write_text(
        render_scholarly_object_profile_markdown(report), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="生成第五项B学术成果辅助对象画像")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    write_scholarly_object_profile_report(
        contract_path=args.contract,
        output_json=args.output_json,
        output_markdown=args.output_md,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
