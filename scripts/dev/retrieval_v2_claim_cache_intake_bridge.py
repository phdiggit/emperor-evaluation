from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_cache as fs_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_chain_candidates as chain_candidates  # noqa: E402
from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev import retrieval_v2_import_plan as import_plan  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_claim_event_groups import owner_scope_values  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v2_runtime_paths import load_runtime_paths  # noqa: E402
from scripts.dev.retrieval_v3_contract_reanchor_plan import NATIVE_CONTRACT_CODE  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_STATUSES = ("active",)
TARGET_MODES = ("canonical", "v3_native")
ITEM_CODE = "I5B"
RULE_CODE = "appointment_delegation"
ROUTABLE_CHAIN_TYPES = {"delegated_power_abuse_chain", "appointment_to_outcome_chain"}
NORMALIZED_FILES = (
    "source_packs",
    "source_pack_artifacts",
    "source_documents",
    "source_passages",
    "material_claims",
    "primary_claim_rule_bindings",
    "secondary_binding_candidates",
    "claim_rule_binding_candidates",
    "coverage_gap_events",
)


class ClaimCacheIntakeBridgeError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_code(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{claim_quality.sha256_text('|'.join(text(part) for part in parts), length=20).upper()}"


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def ready_chains(claims: Sequence[Mapping[str, Any]], *, min_members: int) -> list[dict[str, Any]]:
    return [
        dict(chain)
        for chain in chain_candidates.build_chain_candidates(claims, min_members=min_members)
        if text(chain.get("chain_type")) in ROUTABLE_CHAIN_TYPES
        and text(chain.get("route_readiness")) == "ready_for_chain_route_review"
    ]


def fetch_targets(
    cur: Any,
    *,
    emperor_names: Sequence[str],
    target_mode: str = "canonical",
) -> list[dict[str, Any]]:
    if target_mode not in TARGET_MODES:
        raise ClaimCacheIntakeBridgeError(f"unsupported target_mode: {target_mode!r}")
    names = [text(name) for name in emperor_names if text(name)]
    if not names:
        return []
    cur.execute(
        """
        select rt.target_code, rt.emperor_name, rt.item_code, rc.contract_code
          from retrieval_v2.retrieval_targets rt
          join retrieval_v2.rule_contracts rc on rc.id = rt.contract_id
         where rt.emperor_name = any(%s)
           and rt.item_code = %s
         order by emperor_name, target_code
        """,
        [names, ITEM_CODE],
    )
    rows = [dict(row) for row in cur.fetchall()]
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        emperor = text(row.get("emperor_name"))
        row_is_v3_native = text(row.get("contract_code")) == NATIVE_CONTRACT_CODE
        if not text(row.get("contract_code")):
            row_is_v3_native = "-V3N-" in text(row.get("target_code")) or "-R3R-" in text(row.get("target_code"))
        if row_is_v3_native != (target_mode == "v3_native"):
            continue
        if emperor not in selected:
            selected[emperor] = row
    return [selected[name] for name in sorted(selected)]


def fetch_cache_evidence_rows(cur: Any, *, claim_keys: Sequence[str]) -> list[dict[str, Any]]:
    keys = [text(key) for key in claim_keys if text(key)]
    if not keys:
        return []
    cur.execute(
        """
        select
            c.claim_key, c.emperor_name, c.object_name, c.object_type::text as object_type,
            c.claim_type::text as claim_type, c.claim_summary, c.confidence, c.fact_payload,
            c.canonical_event_key, c.event_group_key, c.status::text as status,
            e.evidence_key, e.support_level::text as support_level, e.span_payload,
            e.raw_output_path,
            s.slice_hash, s.document_code, s.raw_document_code, s.source_title, s.source_url,
            s.source_slice_ref, s.text_hash
          from retrieval_v2.claim_cache c
          join retrieval_v2.claim_evidence e on e.claim_key = c.claim_key
          join retrieval_v2.claim_source_slices s on s.slice_hash = e.slice_hash
         where c.claim_key = any(%s)
           and c.status = 'active'
         order by c.emperor_name, c.claim_key, e.evidence_key
        """,
        [keys],
    )
    return [dict(row) for row in cur.fetchall()]


def full_text_by_slice(cache_root: Path) -> dict[str, str]:
    cache = fs_cache.load_existing_cache(cache_root)
    result: dict[str, str] = {}
    for slice_hash, row in cache["slices"].items():
        raw_text = text(row.get("slice_text") or row.get("text") or row.get("raw_text"))
        if raw_text:
            result[text(slice_hash)] = raw_text
    return result


def hydrate_full_texts_from_raw_runs(
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    full_texts: Mapping[str, str],
    runtime_paths: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    result = dict(full_texts)
    missing_by_output: dict[Path, set[str]] = defaultdict(set)
    resolved_runtime_paths = dict(runtime_paths or load_runtime_paths())
    linux_roots = (
        (text(resolved_runtime_paths.get("active_root_linux")), text(resolved_runtime_paths.get("active_root"))),
        (text(resolved_runtime_paths.get("archive_root_linux")), text(resolved_runtime_paths.get("archive_root"))),
    )
    for row in evidence_rows:
        slice_hash = text(row.get("slice_hash"))
        if slice_hash and not text(result.get(slice_hash)) and text(row.get("raw_output_path")):
            raw_path = text(row.get("raw_output_path"))
            resolved_path = Path(raw_path)
            if not resolved_path.is_file():
                normalized = raw_path.replace("\\", "/")
                for linux_root, smb_root in linux_roots:
                    normalized_root = linux_root.rstrip("/")
                    if normalized_root and smb_root and (
                        normalized == normalized_root or normalized.startswith(normalized_root + "/")
                    ):
                        relative = normalized[len(normalized_root) :].lstrip("/")
                        resolved_path = Path(smb_root).joinpath(*relative.split("/"))
                        break
            missing_by_output[resolved_path].add(slice_hash)
    for judge_path, needed_hashes in missing_by_output.items():
        candidates_path = judge_path.parent / "candidates.final.json"
        if not candidates_path.is_file():
            continue
        try:
            payload = json.loads(candidates_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for candidate in payload.get("candidate_slices") or []:
            if not isinstance(candidate, Mapping):
                continue
            slice_hash = fs_cache.slice_hash_from_row(candidate)
            raw_text = text(candidate.get("text") or candidate.get("raw_text") or candidate.get("slice_text"))
            if slice_hash in needed_hashes and raw_text:
                result[slice_hash] = raw_text
    return result


def claim_keys_from_chains(chains: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            text(member.get("claim_key"))
            for chain in chains
            for member in (chain.get("members") or [])
            if isinstance(member, Mapping) and text(member.get("claim_key"))
        }
    )


def claim_keys_from_claims(claims: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({text(claim.get("claim_key")) for claim in claims if text(claim.get("claim_key"))})


def build_rows_for_claims(
    *,
    claims: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    full_texts: Mapping[str, str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Build rule-neutral material rows after evidence/text gates.

    Rule-chain readiness is intentionally not consulted here.  Claims with no
    evidence or no rehydrated full slice remain outside the material intake
    until the source layer can satisfy the evidence contract; they are not
    silently promoted or scored.
    """
    claim_keys = claim_keys_from_claims(claims)
    evidence_by_claim: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        evidence_by_claim[text(row.get("claim_key"))].append(row)
    eligible_claims: list[Mapping[str, Any]] = []
    eligible_keys: set[str] = set()
    missing_evidence = 0
    missing_full_slice = 0
    partial_full_slice = 0
    for claim in claims:
        claim_key = text(claim.get("claim_key"))
        evidence = evidence_by_claim.get(claim_key, [])
        if not evidence:
            missing_evidence += 1
            continue
        complete_evidence = [row for row in evidence if text(full_texts.get(text(row.get("slice_hash"))))]
        if not complete_evidence:
            missing_full_slice += 1
            continue
        if len(complete_evidence) != len(evidence):
            partial_full_slice += 1
        eligible_claims.append(claim)
        eligible_keys.add(claim_key)
    grouped_claims: dict[str, list[str]] = defaultdict(list)
    for claim in eligible_claims:
        grouped_claims[text(claim.get("emperor_name"))].append(text(claim.get("claim_key")))
    intake_chains = [
        {"emperor_name": emperor, "members": [{"claim_key": key} for key in sorted(keys)]}
        for emperor, keys in sorted(grouped_claims.items())
    ]
    eligible_evidence = [
        row
        for row in evidence_rows
        if text(row.get("claim_key")) in eligible_keys
        and text(full_texts.get(text(row.get("slice_hash"))))
    ]
    rows = build_rows(
        chains=intake_chains,
        targets=targets,
        evidence_rows=eligible_evidence,
        full_texts=full_texts,
    )
    passages = {text(row.get("passage_code")): row for row in rows["source_passages"]}
    alignment_blockers: list[dict[str, str]] = []
    aligned_materials: list[dict[str, Any]] = []
    for material in rows["material_claims"]:
        issue = import_plan.claim_passage_alignment_issue(material, passages)
        if issue and text(issue.get("severity")) == "blocker":
            alignment_blockers.append(
                {
                    "claim_code": text(material.get("claim_code")),
                    "claim_key": text(material.get("raw_claim_code")),
                    "code": text(issue.get("code")),
                    "message": text(issue.get("message")),
                }
            )
            continue
        aligned_materials.append(material)
    rows["material_claims"] = aligned_materials
    return rows, {
        "input_claims": len(claim_keys),
        "eligible_material_claims": len(rows["material_claims"]),
        "excluded_missing_evidence": missing_evidence,
        "excluded_missing_full_slice": missing_full_slice,
        "excluded_claim_passage_alignment": len(alignment_blockers),
        "claim_passage_alignment_blockers": alignment_blockers,
        "partial_missing_full_slice": partial_full_slice,
        "rule_filter_applied": 0,
    }


def build_rows(
    *,
    chains: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    full_texts: Mapping[str, str],
) -> dict[str, list[dict[str, Any]]]:
    target_by_emperor: dict[str, Mapping[str, Any]] = {}
    for target in targets:
        emperor = text(target.get("emperor_name"))
        if emperor in target_by_emperor:
            raise ClaimCacheIntakeBridgeError(f"multiple {ITEM_CODE} retrieval targets for {emperor}")
        target_by_emperor[emperor] = target
    claim_keys = claim_keys_from_chains(chains)
    rows_by_claim: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        rows_by_claim[text(row.get("claim_key"))].append(row)
    missing_evidence = sorted(set(claim_keys) - set(rows_by_claim))
    if missing_evidence:
        raise ClaimCacheIntakeBridgeError("claim cache rows missing evidence: " + ",".join(missing_evidence))
    missing_targets = sorted({text(chain.get("emperor_name")) for chain in chains} - set(target_by_emperor))
    if missing_targets:
        raise ClaimCacheIntakeBridgeError(f"missing {ITEM_CODE} retrieval target: " + ",".join(missing_targets))

    rows = {name: [] for name in NORMALIZED_FILES}
    pack_by_emperor: dict[str, str] = {}
    document_codes: dict[tuple[str, str], str] = {}
    passage_codes: dict[tuple[str, str], str] = {}
    for chain in chains:
        emperor = text(chain.get("emperor_name"))
        if emperor in pack_by_emperor:
            continue
        target = target_by_emperor[emperor]
        pack_code = stable_code("SPK-CACHE", target.get("target_code"), RULE_CODE, emperor)
        pack_by_emperor[emperor] = pack_code
        rows["source_packs"].append(
            {
                "source_pack_code": pack_code,
                "target_code": text(target.get("target_code")),
                "emperor_name": emperor,
                "item_code": ITEM_CODE,
                "rule_code": RULE_CODE,
                "run_root": "claim_cache",
                "run_dir": "claim_cache",
                "manifest_payload": {
                    "source": "claim_cache_intake_bridge",
                    "capture_mode": "claim_cache",
                    "acceptance_status": "draft",
                    "formal_binding_allowed": False,
                    "object_identity_gate": "deferred_until_formal_binding",
                    "material_scope": "rule_neutral",
                    "rule_filter_applied": False,
                },
            }
        )

    for claim_key in claim_keys:
        evidence = rows_by_claim[claim_key]
        claim = evidence[0]
        emperor = text(claim.get("emperor_name"))
        pack_code = pack_by_emperor[emperor]
        source_passage_refs: list[str] = []
        for source in evidence:
            slice_hash = text(source.get("slice_hash"))
            raw_text = text(full_texts.get(slice_hash))
            if not raw_text:
                raise ClaimCacheIntakeBridgeError(f"missing full slice text for {slice_hash} / {claim_key}")
            raw_document_code = text(source.get("raw_document_code") or source.get("document_code") or slice_hash)
            document_key = (pack_code, raw_document_code)
            document_code = document_codes.setdefault(document_key, stable_code("DOC", pack_code, raw_document_code))
            if not any(row["document_code"] == document_code for row in rows["source_documents"]):
                rows["source_documents"].append(
                    {
                        "source_pack_code": pack_code,
                        "document_code": document_code,
                        "raw_document_code": raw_document_code,
                        "source_title": text(source.get("source_title")) or raw_document_code,
                        "title": text(source.get("source_title")) or raw_document_code,
                        "locator": text(source.get("source_url")),
                        "canon_url": text(source.get("source_url")),
                        "source_kind": "claim_cache_source_slice",
                        "document_payload": {"document_code": text(source.get("document_code")), "source": "claim_cache"},
                    }
                )
            passage_key = (pack_code, slice_hash)
            passage_code = passage_codes.setdefault(passage_key, stable_code("PAS", pack_code, slice_hash))
            if not any(row["passage_code"] == passage_code for row in rows["source_passages"]):
                rows["source_passages"].append(
                    {
                        "source_pack_code": pack_code,
                        "passage_code": passage_code,
                        "raw_passage_code": slice_hash,
                        "document_code": document_code,
                        "raw_document_code": raw_document_code,
                        "locator": text(source.get("source_slice_ref")),
                        "raw_text": raw_text,
                        "quote_hash": text(source.get("text_hash")) or claim_quality.sha256_text(raw_text),
                        "passage_payload": {
                            "slice_hash": slice_hash,
                            "source_slice_ref": text(source.get("source_slice_ref")),
                            "evidence_key": text(source.get("evidence_key")),
                            "source": "claim_cache",
                        },
                    }
                )
            source_passage_refs.append(passage_code)
        fact_payload = dict(claim.get("fact_payload") or {})
        rows["material_claims"].append(
            {
                "source_pack_code": pack_code,
                "claim_code": stable_code("CLM", pack_code, claim_key),
                "raw_claim_code": claim_key,
                "emperor_name": emperor,
                "object_name": text(claim.get("object_name")),
                "object_type": text(claim.get("object_type")) or "person",
                "claim_kind": text(claim.get("claim_type")) or "material_claim",
                "claim_summary": text(claim.get("claim_summary")),
                "direction": "neutral",
                "confidence": claim.get("confidence"),
                "review_status": "pending",
                "source_passage_refs": list(dict.fromkeys(source_passage_refs)),
                "raw_source_passage_refs": [text(row.get("source_slice_ref")) for row in evidence],
                "source_slice_refs": [text(row.get("source_slice_ref")) for row in evidence],
                "claim_payload": {
                    "cached_claim_key": claim_key,
                    "claim_key": claim_key,
                    "fact_payload": fact_payload,
                    "canonical_event_key": text(claim.get("canonical_event_key")),
                    "event_group_key": text(claim.get("event_group_key")),
                    "cache_intake": {
                        "formal_binding_allowed": False,
                        "object_identity_gate": "deferred_until_formal_binding",
                        "material_scope": "rule_neutral",
                        "rule_filter_applied": False,
                    },
                },
            }
        )
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")


def write_rows(output_root: Path, rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    for name in NORMALIZED_FILES:
        write_jsonl(output_root / f"{name}.jsonl", rows.get(name) or [])


def report_from_pg(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
    min_members: int,
    cache_root: Path,
    target_mode: str = "canonical",
    selected_claim_keys: Sequence[str] = (),
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            claims = chain_candidates.fetch_claim_rows(cur, emperor_names=emperor_names, statuses=statuses, owner_scopes=owner_scopes)
            requested_keys = {text(key) for key in selected_claim_keys if text(key)}
            if requested_keys:
                available_keys = {text(claim.get("claim_key")) for claim in claims}
                missing_keys = sorted(requested_keys - available_keys)
                if missing_keys:
                    raise ClaimCacheIntakeBridgeError("requested claim keys not found: " + ",".join(missing_keys))
                claims = [claim for claim in claims if text(claim.get("claim_key")) in requested_keys]
            chains = ready_chains(claims, min_members=min_members)
            targets = fetch_targets(
                cur,
                emperor_names=sorted({text(claim.get("emperor_name")) for claim in claims}),
                target_mode=target_mode,
            )
            evidence_rows = fetch_cache_evidence_rows(cur, claim_keys=claim_keys_from_claims(claims))
        conn.rollback()
    cached_texts = full_text_by_slice(cache_root)
    full_texts = hydrate_full_texts_from_raw_runs(evidence_rows, full_texts=cached_texts)
    rows, material_gate = build_rows_for_claims(
        claims=claims,
        targets=targets,
        evidence_rows=evidence_rows,
        full_texts=full_texts,
    )
    report = {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_cache_intake_bridge.py",
        "mode": "dry_run_claim_cache_intake_bridge",
        "write_db": False,
        "formal_binding_allowed": False,
        "target_mode": target_mode,
        "requested_claim_key_count": len({text(key) for key in selected_claim_keys if text(key)}),
        "object_identity_gate": "deferred_until_formal_binding",
        "input_claim_count": len(claims),
        "ready_chain_count": len(chains),
        "material_gate": material_gate,
        "full_slice_text_sources": {
            "filesystem_cache_count": len(cached_texts),
            "available_after_raw_run_rehydrate": len(full_texts),
        },
        "normalized_row_counts": {name: len(rows[name]) for name in NORMALIZED_FILES},
    }
    return report, rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build normalized draft intake rows from strong claim-cache chains.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--owner-scope", action="append", default=[])
    parser.add_argument("--min-members", type=int, default=chain_candidates.CHAIN_MIN_MEMBERS)
    parser.add_argument("--target-mode", choices=TARGET_MODES, default="canonical")
    parser.add_argument("--claim-key", action="append", default=[])
    parser.add_argument("--claim-cache-root", type=Path, required=True, help="Filesystem cache root containing source_slices.jsonl full slice_text.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report, rows = report_from_pg(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        emperor_names=args.emperor_name,
        statuses=args.status or DEFAULT_STATUSES,
        owner_scopes=args.owner_scope,
        min_members=args.min_members,
        cache_root=args.claim_cache_root,
        target_mode=args.target_mode,
        selected_claim_keys=args.claim_key,
    )
    write_rows(args.output_root, rows)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(pretty_json(report), encoding="utf-8", newline="\n")
    print(pretty_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
