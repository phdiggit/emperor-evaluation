from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_cache as claim_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev.retrieval_v2_taskgen_preseed import text_from  # noqa: E402


BIOGRAPHY_SHAPES = {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"}
DISPOSITION_ONLY_TERMS = ("伏诛", "被诛", "诛", "谋反", "废", "罢", "下狱", "坐罪", "族诛")
APPOINTMENT_AUTHORIZATION_TERMS = (
    "诏",
    "命",
    "任",
    "拜",
    "授",
    "用",
    "擢",
    "迁",
    "委",
    "使",
    "令",
    "领",
    "同知",
    "定策",
    "为",
    "充",
    "副",
    "摄",
    "封",
    "镇",
    "守",
    "督",
    "备边",
    "总制",
    "提督",
    "参军国事",
)
GOVERNANCE_DAMAGE_TERMS = ("专擅", "擅权", "纳贿", "壅蔽", "害政", "乱政", "败", "失", "误", "杀", "构党", "结党")


class ClaimAuditError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return claim_cache.read_jsonl(path)


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def compact_preview(value: Any, *, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def object_aliases(row: Mapping[str, Any]) -> list[str]:
    aliases = [text_from(row, "object_name"), text_from(row, "person_name")]
    aliases.extend(str(alias) for alias in row.get("matched_aliases") or [] if str(alias or "").strip())
    return sorted({alias for alias in aliases if alias}, key=len, reverse=True)


def alias_positions(text: str, aliases: Sequence[str]) -> list[int]:
    positions: set[int] = set()
    for alias in aliases:
        start = 0
        while alias:
            index = text.find(alias, start)
            if index < 0:
                break
            positions.add(index)
            start = index + len(alias)
    return sorted(positions)


def load_object_slice_index(object_cache_root: Path) -> dict[str, dict[str, Any]]:
    docs = {
        text_from(row, "document_cache_code", "document_code"): row
        for row in read_jsonl(object_cache_root / "source_documents.jsonl")
        if text_from(row, "document_cache_code", "document_code")
    }
    index: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(object_cache_root / "mention_slices.jsonl"):
        ref = text_from(row, "slice_cache_code", "source_slice_ref")
        if not ref:
            continue
        document_code = text_from(row, "document_cache_code", "document_code")
        doc = docs.get(document_code, {})
        payload = dict(row)
        payload["document_code"] = document_code
        payload["source_shape"] = text_from(doc, "source_shape")
        payload["source_role"] = text_from(row, "source_role") or text_from(doc, "source_role")
        payload["source_title"] = text_from(row, "source_title") or text_from(doc, "source_title", "title")
        index[ref] = payload
    return index


def duplicate_group_key(claim: Mapping[str, Any]) -> tuple[str, ...]:
    return claim_quality.near_duplicate_group_key(claim)


def grain_group_key(claim: Mapping[str, Any]) -> tuple[str, ...]:
    payload = claim_quality.near_duplicate_group_payload(claim)
    return (
        payload["emperor_name"],
        payload["object_name"],
        payload["direction"],
        payload["action_type"],
        payload["event_scope"],
        payload["office_or_domain"],
        payload["time_context"],
    )


def claim_semantic_findings(claim: Mapping[str, Any]) -> list[dict[str, Any]]:
    action_type = text_from(claim, "action_type")
    direction = text_from(claim, "direction")
    summary = text_from(claim, "claim_summary")
    fact = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    combined = summary + text_from(claim, "outcome") + text_from(fact, "outcome") + text_from(fact, "cost_or_damage")
    findings: list[dict[str, Any]] = []
    if direction == "negative" and action_type in {"任命", "授权"}:
        has_disposition = any(term in combined for term in DISPOSITION_ONLY_TERMS)
        has_damage = any(term in combined for term in GOVERNANCE_DAMAGE_TERMS)
        if has_disposition and not has_damage:
            findings.append(
                {
                    "issue_code": "negative_authorization_disposition_only_review",
                    "severity": "medium",
                    "claim_key": claim.get("claim_key"),
                    "object_name": claim.get("object_name"),
                    "direction": direction,
                    "action_type": action_type,
                    "time_context": claim.get("time_context"),
                    "claim_summary": compact_preview(summary, limit=180),
                    "detail": "negative appointment/authorization claim appears to rely on disposition ending without same-chain governance damage",
                }
            )
    if action_type in {"任命", "授权"} and not any(term in combined for term in APPOINTMENT_AUTHORIZATION_TERMS):
        findings.append(
            {
                "issue_code": "action_type_authorization_anchor_missing",
                "severity": "low",
                "claim_key": claim.get("claim_key"),
                "object_name": claim.get("object_name"),
                "direction": direction,
                "action_type": action_type,
                "time_context": claim.get("time_context"),
                "claim_summary": compact_preview(summary, limit=180),
                "detail": "claim action_type is appointment/authorization but summary/outcome lacks local appointment or authorization anchor",
            }
        )
    return findings


def build_claim_audit(
    *,
    claim_cache_root: Path,
    object_cache_root: Path,
    candidates_path: Path | None = None,
    max_findings: int = 200,
) -> dict[str, Any]:
    claim_paths = claim_cache.cache_paths(claim_cache_root)
    claims = read_jsonl(claim_paths["claims"])
    evidences = read_jsonl(claim_paths["evidence"])
    source_slices = read_jsonl(claim_paths["slices"])
    claims_by_key = {text_from(row, "claim_key"): row for row in claims if text_from(row, "claim_key")}
    active_claims = [row for row in claims if text_from(row, "status") in {"", "active"}]
    active_claim_keys = {text_from(row, "claim_key") for row in active_claims if text_from(row, "claim_key")}
    active_evidences = [row for row in evidences if text_from(row, "claim_key") in active_claim_keys]
    source_by_hash = {text_from(row, "slice_hash"): row for row in source_slices if text_from(row, "slice_hash")}
    object_slices = load_object_slice_index(object_cache_root)
    candidates = claim_cache.read_json(candidates_path) if candidates_path else {}
    candidate_slices = (
        [row for row in candidates.get("candidate_slices") or [] if isinstance(row, Mapping)]
        if isinstance(candidates, Mapping)
        else []
    )
    findings: list[dict[str, Any]] = []

    for claim in active_claims:
        findings.extend(claim_semantic_findings(claim))

    for evidence in active_evidences:
        claim_key = text_from(evidence, "claim_key")
        claim = claims_by_key.get(claim_key, {})
        if not claim:
            continue
        source_ref = text_from(evidence, "source_slice_ref")
        source_hash = text_from(evidence, "slice_hash")
        source_slice = source_by_hash.get(source_hash, {})
        object_slice = object_slices.get(source_ref, {})
        claim_object = text_from(claim, "object_name")
        evidence_object = text_from(evidence, "object_name")
        source_object = text_from(source_slice, "object_name")

        if evidence_object and claim_object and evidence_object != claim_object:
            findings.append(
                finding_row(
                    "claim_evidence_object_mismatch",
                    "medium",
                    claim,
                    evidence,
                    object_slice,
                    detail=f"claim object={claim_object}; evidence object={evidence_object}",
                )
            )
        if source_object and claim_object and source_object != claim_object and source_object != evidence_object:
            findings.append(
                finding_row(
                    "claim_source_object_mismatch",
                    "medium",
                    claim,
                    evidence,
                    object_slice,
                    detail=f"claim object={claim_object}; source slice object={source_object}",
                )
            )

        section_heading = text_from(object_slice, "section_heading")
        source_shape = text_from(object_slice, "source_shape")
        if section_heading and source_shape in BIOGRAPHY_SHAPES:
            aliases = object_aliases({"object_name": claim_object, **object_slice})
            if aliases and not any(alias in section_heading for alias in aliases):
                findings.append(
                    finding_row(
                        "wrong_person_section",
                        "medium",
                        claim,
                        evidence,
                        object_slice,
                        detail=f"section_heading={section_heading}; claim object={claim_object}",
                    )
                )

        text = text_from(object_slice, "raw_text") or text_from(source_slice, "slice_text_preview") or text_from(evidence, "slice_text_preview")
        positions = alias_positions(text, object_aliases({"object_name": claim_object, **object_slice}))
        if len(positions) <= 1 and len(text) >= 260 and source_shape in BIOGRAPHY_SHAPES:
            findings.append(
                finding_row(
                    "weak_single_mention",
                    "low",
                    claim,
                    evidence,
                    object_slice,
                    detail=f"object mention count={len(positions)}; source_shape={source_shape}",
                )
            )
        eligibility = claim_quality.slice_claim_eligibility(
            {
                **object_slice,
                "object_name": claim_object,
                "matched_aliases": object_slice.get("matched_aliases") or [],
                "text": text,
            }
        )
        if not eligibility["claim_eligible"]:
            findings.append(
                finding_row(
                    "ineligible_slice_claim_evidence",
                    "medium",
                    claim,
                    evidence,
                    object_slice,
                    detail=f"mention_role={eligibility['mention_role']}; reasons={','.join(eligibility['reasons'])}",
                )
            )

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for claim in active_claims:
        groups[duplicate_group_key(claim)].append(claim)
    for key, rows in groups.items():
        if len(rows) < 2 or not any(key):
            continue
        findings.append(
            {
                "issue_code": "near_duplicate_claim_group",
                "severity": "low",
                "claim_key": rows[0].get("claim_key"),
                "object_name": rows[0].get("object_name"),
                "direction": rows[0].get("direction"),
                "action_type": rows[0].get("action_type"),
                "canonical_group_payload": claim_quality.near_duplicate_group_payload(rows[0]),
                "claim_count": len(rows),
                "claim_keys": [row.get("claim_key") for row in rows[:12]],
                "claim_summaries": [compact_preview(row.get("claim_summary"), limit=120) for row in rows[:5]],
                "detail": "same object/direction/action/time/outcome cluster has multiple active claims",
            }
        )
    grain_groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for claim in active_claims:
        grain_groups[grain_group_key(claim)].append(claim)
    for rows in grain_groups.values():
        grains = sorted({text_from(row, "claim_grain") or claim_quality.claim_grain(row) for row in rows})
        if len(rows) < 2 or len(grains) < 2:
            continue
        findings.append(
            {
                "issue_code": "mixed_claim_grain_group",
                "severity": "low",
                "claim_key": rows[0].get("claim_key"),
                "object_name": rows[0].get("object_name"),
                "direction": rows[0].get("direction"),
                "action_type": rows[0].get("action_type"),
                "claim_count": len(rows),
                "claim_grains": grains,
                "claim_keys": [row.get("claim_key") for row in rows[:12]],
                "claim_summaries": [compact_preview(row.get("claim_summary"), limit=120) for row in rows[:5]],
                "detail": "same object/action/time group mixes event_chain and sub_event grains",
            }
        )

    if not candidate_slices:
        seen_refs = {text_from(evidence, "source_slice_ref") for evidence in active_evidences if text_from(evidence, "source_slice_ref")}
        for source_ref in sorted(seen_refs):
            object_slice = object_slices.get(source_ref, {})
            source_row = next((row for row in source_slices if text_from(row, "source_slice_ref") == source_ref), {})
            candidate_slices.append(
                {
                    "slice_code": source_ref,
                    "object_name": text_from(source_row, "object_name") or text_from(object_slice, "person_name"),
                    "matched_aliases": object_slice.get("matched_aliases") or [],
                    "source_shape": text_from(object_slice, "source_shape"),
                    "section_heading": text_from(object_slice, "section_heading"),
                    "text": text_from(object_slice, "raw_text") or text_from(source_row, "slice_text_preview"),
                }
            )
    opportunity_estimate = claim_quality.estimate_claim_opportunities(candidate_slices, active_claims)
    for object_name, row in opportunity_estimate.get("objects", {}).items():
        if row.get("undercoverage_risk"):
            findings.append(
                {
                    "issue_code": "claim_opportunity_undercoverage",
                    "severity": "low",
                    "object_name": object_name,
                    "claim_count": row.get("actual_claim_count"),
                    "suggested_claim_budget": row.get("suggested_claim_budget"),
                    "opportunity_count": row.get("opportunity_count"),
                    "opportunity_weight": row.get("opportunity_weight"),
                    "detail": row.get("undercoverage_risk"),
                }
            )

    findings = dedupe_findings(findings)
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda row: (order.get(str(row.get("severity")), 9), str(row.get("issue_code")), str(row.get("object_name")), str(row.get("claim_key"))))
    limited = findings[: max(0, max_findings)]
    return {
        "generated_by": "scripts/dev/retrieval_v2_claim_audit.py",
        "claim_cache_root": str(claim_cache_root),
        "object_cache_root": str(object_cache_root),
        "candidates_path": str(candidates_path) if candidates_path else "",
        "totals": {
            "claims": len(claims),
            "active_claims": len(active_claims),
            "evidence": len(evidences),
            "active_evidence": len(active_evidences),
            "source_slices": len(source_slices),
            "object_cache_slices": len(object_slices),
            "findings": len(findings),
            "reported_findings": len(limited),
            "claim_status_counts": dict(Counter(text_from(row, "status") or "active" for row in claims)),
        },
        "issue_counts": dict(Counter(str(row.get("issue_code")) for row in findings)),
        "severity_counts": dict(Counter(str(row.get("severity")) for row in findings)),
        "object_issue_counts": dict(Counter(str(row.get("object_name")) for row in findings if row.get("object_name"))),
        "claim_opportunity_estimate": opportunity_estimate,
        "findings": limited,
    }


def dedupe_findings(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in findings:
        key = (
            str(row.get("issue_code") or ""),
            str(row.get("claim_key") or ""),
            str(row.get("object_name") or ""),
            str(row.get("source_slice_ref") or ""),
            str(row.get("detail") or ""),
        )
        if key not in deduped:
            deduped[key] = dict(row)
    return list(deduped.values())


def finding_row(
    issue_code: str,
    severity: str,
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
    object_slice: Mapping[str, Any],
    *,
    detail: str,
) -> dict[str, Any]:
    return {
        "issue_code": issue_code,
        "severity": severity,
        "claim_key": claim.get("claim_key"),
        "evidence_key": evidence.get("evidence_key"),
        "object_name": claim.get("object_name"),
        "direction": claim.get("direction"),
        "action_type": claim.get("action_type"),
        "time_context": claim.get("time_context"),
        "claim_summary": compact_preview(claim.get("claim_summary"), limit=180),
        "source_slice_ref": evidence.get("source_slice_ref"),
        "document_code": evidence.get("document_code"),
        "source_title": object_slice.get("source_title"),
        "source_shape": object_slice.get("source_shape"),
        "section_heading": object_slice.get("section_heading"),
        "slice_preview": compact_preview(object_slice.get("raw_text") or evidence.get("slice_text_preview"), limit=220),
        "detail": detail,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    lines = [
        "# retrieval_v2 claim cache audit",
        "",
        f"- claim_cache_root: `{report.get('claim_cache_root')}`",
        f"- object_cache_root: `{report.get('object_cache_root')}`",
        f"- claims: `{totals.get('claims', 0)}`",
        f"- evidence: `{totals.get('evidence', 0)}`",
        f"- findings: `{totals.get('findings', 0)}`",
        "",
        "## Issue Counts",
        "",
    ]
    opportunity = report.get("claim_opportunity_estimate") if isinstance(report.get("claim_opportunity_estimate"), Mapping) else {}
    opportunity_totals = opportunity.get("totals") if isinstance(opportunity.get("totals"), Mapping) else {}
    if opportunity_totals:
        lines[8:8] = [
            f"- opportunity_suggested_claim_budget: `{opportunity_totals.get('suggested_claim_budget', 0)}`",
            f"- opportunity_actual_claim_count: `{opportunity_totals.get('actual_claim_count', 0)}`",
            f"- opportunity_undercoverage_objects: `{opportunity_totals.get('undercoverage_objects', 0)}`",
            "",
        ]
    for key, count in sorted((report.get("issue_counts") or {}).items()):
        lines.append(f"- {key}: `{count}`")
    lines.extend(["", "## Findings", "", "| severity | issue | object | claim | section | summary |", "| --- | --- | --- | --- | --- | --- |"])
    for row in report.get("findings") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("severity") or ""),
                    str(row.get("issue_code") or ""),
                    str(row.get("object_name") or ""),
                    str(row.get("claim_key") or ""),
                    str(row.get("section_heading") or ""),
                    str(row.get("claim_summary") or "").replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit retrieval_v2 claim cache against annotated object source cache slices.")
    parser.add_argument("--claim-cache-root", type=Path, required=True)
    parser.add_argument("--object-cache-root", type=Path, required=True)
    parser.add_argument("--candidates-path", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--max-findings", type=int, default=200)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_claim_audit(
        claim_cache_root=args.claim_cache_root,
        object_cache_root=args.object_cache_root,
        candidates_path=args.candidates_path,
        max_findings=args.max_findings,
    )
    if args.output_json is not None:
        write_json(args.output_json, report)
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": True, "totals": report["totals"], "issue_counts": report["issue_counts"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClaimAuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
