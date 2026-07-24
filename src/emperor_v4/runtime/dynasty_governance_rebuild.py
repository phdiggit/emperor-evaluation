from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
from threading import Lock
from typing import Any, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.adapters.dynasty_neutral_governance import (
    AUDIT_SCHEMA_VERSION,
    audit_scan,
    prepare_scan,
)
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.evaluation.model_policy import resolve_agent_route
from emperor_v4.runtime.structured_codex_runner import StructuredCodexRunner


SCHEMA_VERSION = "dynasty-governance-current-v1"
EXTRACTION_POLICY_VERSION = "dynasty-governance-neutral-extraction-v2"
_EDITORIAL_NOTE_ANCHOR = re.compile(r"\[\d+\]")
_LAYOUT_WHITESPACE = re.compile(r"\s+")


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _quote_match_text(value: str) -> str:
    return _LAYOUT_WHITESPACE.sub("", _EDITORIAL_NOTE_ANCHOR.sub("", value))


def _sanitize_task_payload(
    payload: Mapping[str, Any], task: Mapping[str, Any]
) -> dict[str, Any]:
    page_map = {
        (str(page["page_title"]), str(page["revision_ref"])): Path(
            str(page["text_path"])
        ).read_text(encoding="utf-8").strip()
        for page in task["pages"]
    }
    accepted = []
    seen_chain_keys: set[str] = set()
    seen_evidence_identities: set[tuple[tuple[str, str, str], ...]] = set()
    dropped = 0
    for raw_chain in payload.get("chains") or ():
        chain = dict(raw_chain)
        chain_key = str(chain.get("chain_key") or "")
        evidence_refs = {
            str(evidence.get("quote_ref") or "")
            for evidence in chain.get("evidence") or ()
        }
        evidence_identity = tuple(
            sorted(
                (
                    str(evidence.get("page_title") or ""),
                    str(evidence.get("revision_ref") or ""),
                    str(evidence.get("exact_quote") or ""),
                )
                for evidence in chain.get("evidence") or ()
            )
        )
        quotes_valid = bool(evidence_identity) and all(
            (page_title, revision_ref) in page_map
            and _quote_match_text(exact_quote)
            in _quote_match_text(page_map[(page_title, revision_ref)])
            for page_title, revision_ref, exact_quote in evidence_identity
        )
        actors_valid = all(
            set(str(ref) for ref in actor.get("quote_refs") or ()) <= evidence_refs
            and len(actor.get("contribution_phases") or ())
            == len(set(actor.get("contribution_phases") or ()))
            for actor in chain.get("actors") or ()
        )
        if (
            not chain_key
            or chain_key in seen_chain_keys
            or evidence_identity in seen_evidence_identities
            or not quotes_valid
            or not actors_valid
        ):
            dropped += 1
            continue
        seen_chain_keys.add(chain_key)
        seen_evidence_identities.add(evidence_identity)
        accepted.append(chain)
    limitations = [str(item) for item in payload.get("limitations") or ()]
    if dropped:
        limitations.append(
            f"确定性拒绝 {dropped} 条无法逐字回指、重复或 actor 引用越界的候选链。"
        )
    return {**payload, "chains": accepted, "limitations": list(dict.fromkeys(limitations))}


def _restore_accepted_results(
    *,
    preparation: Mapping[str, Any],
    resume_root: Path,
    results_dir: Path,
    output_schema_path: Path,
) -> list[str]:
    restored: list[str] = []
    for task in preparation["tasks"]:
        task_code = str(task["task_code"])
        source = resume_root / f"{task_code}.json"
        if not source.is_file():
            continue
        target = results_dir / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        task_audit = audit_scan(
            preparation,
            results_dir=results_dir,
            output_schema_path=output_schema_path,
            task_codes=(task_code,),
        )
        if task_audit["status"] == "accepted_shadow":
            restored.append(task_code)
        else:
            target.unlink(missing_ok=True)
    return restored


@dataclass(frozen=True, slots=True)
class DynastyGovernanceLimits:
    model_workers: int = 4
    model_timeout_seconds: int = 120
    target_chars: int = 2_400

    def __post_init__(self) -> None:
        if not 1 <= self.model_workers <= 8:
            raise ValueError("政书模型并发必须在 1..8")
        if not 15 <= self.model_timeout_seconds <= 180:
            raise ValueError("政书单批模型超时必须在 15..180 秒")
        if not 1_500 <= self.target_chars <= 12_000:
            raise ValueError("政书单批目标字符数必须在 1500..12000")


def _catalog_dynasty_config(
    project: Mapping[str, Any], dynasty: str
) -> tuple[str, Mapping[str, Any]]:
    catalog = project.get("dynasty_governance_catalog") or {}
    rows = catalog.get("dynasties") or {}
    if not isinstance(rows, Mapping):
        raise ValueError("朝代政书目录 dynasties 必须是 object")
    normalized = str(dynasty).strip()
    for name, row in rows.items():
        if not isinstance(row, Mapping):
            continue
        aliases = {str(value).strip() for value in row.get("aliases") or ()}
        if normalized == str(name) or normalized in aliases:
            return str(name), row
    raise ValueError(f"朝代尚未配置政书目录: {dynasty}")


def load_dynasty_governance_catalog_entry(
    workspace_root: Path, dynasty: str
) -> tuple[str, Mapping[str, Any]]:
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    return _catalog_dynasty_config(project, dynasty)


def _load_dynasty_config(
    workspace_root: Path, dynasty: str, *, use_catalog: bool = False
) -> tuple[Mapping[str, Any], Mapping[str, Any], str]:
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    scan_config = project.get("dynasty_governance_scans") or {}
    if use_catalog:
        canonical_dynasty, configured = _catalog_dynasty_config(project, dynasty)
        return scan_config, configured, canonical_dynasty
    configured = (scan_config.get("dynasties") or {}).get(dynasty)
    if not isinstance(configured, Mapping):
        raise ValueError(f"朝代尚未配置政书扫描: {dynasty}")
    return scan_config, configured, dynasty


def _build_source_manifest(
    *,
    index: LocalSourceTextIndex,
    dynasty: str,
    configured: Mapping[str, Any],
    work_root: Path,
    max_segment_chars: int,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    source_specs = configured.get("source_works") or ()
    if not source_specs:
        raise ValueError(f"{dynasty}: 未配置政书")
    pages: list[dict[str, object]] = []
    identities: list[dict[str, str]] = []
    for spec in source_specs:
        if not isinstance(spec, Mapping):
            raise ValueError(f"{dynasty}: source_works 条目必须是 object")
        work = str(spec.get("work") or "").strip()
        source_genre = str(spec.get("source_genre") or "").strip()
        target_scope = str(spec.get("target_scope") or "").strip()
        if not work or not source_genre or not target_scope:
            raise ValueError(f"{dynasty}: 政书 work/genre/target_scope 不完整")
        selected_pages = tuple(index.iter_pages(works=(work,)))
        configured_page_titles = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in spec.get("page_titles") or ()
                if str(value).strip()
            )
        )
        if configured_page_titles:
            pages_by_title = {str(page.page_title): page for page in selected_pages}
            missing_page_titles = sorted(set(configured_page_titles) - set(pages_by_title))
            if missing_page_titles:
                raise ValueError(
                    f"{dynasty}: 本地索引缺少已配置政书页面 "
                    + ", ".join(missing_page_titles)
                )
            selected_pages = tuple(
                pages_by_title[page_title] for page_title in configured_page_titles
            )
        section_groups = spec.get("section_groups") or {}
        if section_groups and not configured_page_titles and not spec.get(
            "scan_all_pages"
        ):
            if not isinstance(section_groups, Mapping):
                raise ValueError(f"{dynasty}: {work} section_groups 必须是 object")
            selected_by_ref = {}
            missing_groups = []
            for group, terms in section_groups.items():
                normalized_terms = tuple(
                    str(term).replace(" ", "").strip()
                    for term in terms or ()
                    if str(term).strip()
                )
                if not normalized_terms:
                    raise ValueError(
                        f"{dynasty}: {work} section group {group} 没有检索词"
                    )
                matched = []
                for page in selected_pages:
                    heading_text = (
                        str(page.page_title) + "\n" + page.raw_text[:2_000]
                    ).replace(" ", "")
                    if any(term in heading_text for term in normalized_terms):
                        matched.append(page)
                        selected_by_ref[
                            (str(page.page_title), str(page.revision_ref))
                        ] = page
                if not matched:
                    missing_groups.append(str(group))
            if missing_groups:
                raise ValueError(
                    f"{dynasty}: 本地索引缺少 {work} 政书篇章组 "
                    + ", ".join(missing_groups)
                )
            selected_pages = tuple(selected_by_ref.values())
        if not selected_pages:
            raise ValueError(f"{dynasty}: 本地索引不含已配置政书 {work}")
        for position, page in enumerate(selected_pages, 1):
            text_sha256 = sha256(page.raw_text.encode("utf-8")).hexdigest()
            remaining = page.raw_text
            page_segments: list[str] = []
            while len(remaining) > max_segment_chars:
                split_at = remaining.rfind("\n", max_segment_chars // 2, max_segment_chars + 1)
                if split_at < 0:
                    split_at = max_segment_chars
                else:
                    split_at += 1
                page_segments.append(remaining[:split_at])
                remaining = remaining[split_at:]
            if remaining:
                page_segments.append(remaining)
            if "".join(page_segments) != page.raw_text:
                raise AssertionError(f"{page.page_title}: 政书分段丢字")
            for segment_position, text in enumerate(page_segments, 1):
                text_path = work_root / "source" / f"{len(pages) + 1:04d}.txt"
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(text, encoding="utf-8", newline="\n")
                pages.append(
                    {
                        "dynasty": dynasty,
                        "source_genre": source_genre,
                        "source_work": page.work_title,
                        "target_scope": target_scope,
                        "page_title": page.page_title,
                        "revision_ref": page.revision_ref,
                        "text_path": str(text_path),
                        "segment_position": segment_position,
                        "segment_count": len(page_segments),
                    }
                )
            identities.append(
                {
                    "work": page.work_title,
                    "page_title": page.page_title,
                    "revision_ref": page.revision_ref,
                    "text_sha256": text_sha256,
                    "source_url": page.source_url,
                    "page_order": str(position),
                }
            )
    return {"pages": pages}, identities


def _quality_report(
    *, audit: Mapping[str, Any], configured: Mapping[str, Any]
) -> dict[str, object]:
    observed_domains = sorted(
        {str(chain["domain"]) for chain in audit.get("chains") or ()}
    )
    observed = set(observed_domains)
    domain_groups = configured.get("required_domain_groups") or {}
    coverage: dict[str, dict[str, object]] = {}
    missing_groups = []
    for group, domains in domain_groups.items():
        candidates = [str(domain) for domain in domains]
        matched = sorted(observed.intersection(candidates))
        covered = bool(matched)
        coverage[str(group)] = {
            "covered": covered,
            "accepted_domains": matched,
            "candidate_domains": candidates,
        }
        if not covered:
            missing_groups.append(str(group))
    passed = (
        audit.get("schema_version") == AUDIT_SCHEMA_VERSION
        and audit.get("status") == "accepted_shadow"
        and int(audit.get("chain_count") or 0) > 0
        and int(audit.get("quote_count") or 0) >= int(audit.get("chain_count") or 0)
        and not missing_groups
    )
    return {
        "status": "passed" if passed else "failed_closed",
        "audit_status": str(audit.get("status") or ""),
        "task_count": int(audit.get("task_count") or 0),
        "accepted_task_count": int(audit.get("accepted_task_count") or 0),
        "chain_count": int(audit.get("chain_count") or 0),
        "quote_count": int(audit.get("quote_count") or 0),
        "failures": list(audit.get("failures") or ()),
        "observed_domains": observed_domains,
        "required_domain_group_coverage": coverage,
        "missing_domain_groups": missing_groups,
    }


def rebuild_dynasty_governance(
    *,
    dynasty: str,
    source_index_path: Path,
    runtime_root: Path,
    workspace_root: Path,
    limits: DynastyGovernanceLimits = DynastyGovernanceLimits(),
    codex_bin: str = "codex",
    use_catalog: bool = False,
) -> dict[str, object]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root.resolve()
    scan_config, configured, canonical_dynasty = _load_dynasty_config(
        workspace_root, dynasty, use_catalog=use_catalog
    )
    dynasty = canonical_dynasty
    index = LocalSourceTextIndex(source_index_path)
    dynasty_token = str(configured["dynasty_token"])
    current_path = runtime_root / dynasty_token / "current.json"
    resume_root = runtime_root / ".resume" / dynasty_token
    work_root = runtime_root / ".work" / uuid4().hex
    succeeded = False
    try:
        manifest, source_identities = _build_source_manifest(
            index=index,
            dynasty=dynasty,
            configured=configured,
            work_root=work_root,
            max_segment_chars=limits.target_chars,
        )
        schema_path = workspace_root / str(scan_config["output_schema"])
        extraction_identity = {
            "contract": SCHEMA_VERSION,
            "extraction_policy": EXTRACTION_POLICY_VERSION,
            "source_index_identity": index.identity,
            "sources": source_identities,
            "configured_sources": configured.get("source_works") or (),
            "required_domain_groups": configured.get("required_domain_groups") or {},
            "output_schema_sha256": sha256(schema_path.read_bytes()).hexdigest(),
        }
        input_fingerprint = _digest(extraction_identity)
        if current_path.is_file():
            current = json.loads(current_path.read_text(encoding="utf-8"))
            exact_current = (
                current.get("schema_version") == SCHEMA_VERSION
                and current.get("status") == "quality_accepted_shadow"
                and current.get("input_fingerprint") == input_fingerprint
            )
            previous_index_identity = str(
                current.get("source_index_identity") or ""
            )
            previous_extraction_identity = {
                **extraction_identity,
                "source_index_identity": previous_index_identity,
            }
            index_superset_compatible = (
                current.get("schema_version") == SCHEMA_VERSION
                and current.get("status") == "quality_accepted_shadow"
                and bool(previous_index_identity)
                and previous_index_identity != index.identity
                and current.get("sources") == source_identities
                and current.get("input_fingerprint")
                == _digest(previous_extraction_identity)
                and (current.get("quality") or {}).get("status") == "passed"
            )
            compatible_current = (
                current.get("schema_version") == SCHEMA_VERSION
                and current.get("status") == "quality_accepted_shadow"
                and current.get("source_index_identity") == index.identity
                and current.get("sources") == source_identities
                and (current.get("quality") or {}).get("status") == "passed"
                and not current.get("extraction_policy")
            )
            if exact_current or compatible_current or index_superset_compatible:
                shutil.rmtree(resume_root, ignore_errors=True)
                current = {
                    **current,
                    "input_fingerprint": input_fingerprint,
                    "extraction_policy": EXTRACTION_POLICY_VERSION,
                    "source_index_identity": index.identity,
                    "sources": source_identities,
                    "output_schema_sha256": extraction_identity[
                        "output_schema_sha256"
                    ],
                }
                if compatible_current or index_superset_compatible:
                    _atomic_json(current_path, current)
                return {
                    **current,
                    "reused": True,
                    "model_call_count": 0,
                    "business_write_count": 0,
                }

        model_policy_path = workspace_root / "config/model-policy.yml"
        model_policy = yaml.safe_load(model_policy_path.read_text(encoding="utf-8"))
        route = resolve_agent_route(
            model_policy, stage_code="dynasty_governance_neutral_extraction"
        )
        preparation = prepare_scan(
            manifest,
            output_root=work_root,
            output_schema_path=schema_path,
            target_chars=limits.target_chars,
        )
        restored = _restore_accepted_results(
            preparation=preparation,
            resume_root=resume_root,
            results_dir=work_root / "results",
            output_schema_path=schema_path,
        )
        runner = StructuredCodexRunner(
            codex_bin=codex_bin,
            model=str(route["model"]),
            reasoning_effort=str(route["reasoning_effort"]),
            output_schema_path=schema_path,
            timeout_seconds=limits.model_timeout_seconds,
            cwd=workspace_root,
        )

        model_calls: list[str] = []
        model_calls_lock = Lock()

        task_by_code = {
            str(task["task_code"]): task for task in preparation["tasks"]
        }

        def invoke(task_code: str, prompt: str) -> Mapping[str, Any]:
            with model_calls_lock:
                model_calls.append(task_code)
            payload, _metrics = runner.run(prompt)
            payload = _sanitize_task_payload(payload, task_by_code[task_code])
            _atomic_json(work_root / "results" / f"{task_code}.json", payload)
            return payload

        def extract(task: Mapping[str, Any]) -> str:
            task_code = str(task["task_code"])
            prompt = (work_root / "prompts" / f"{task_code}.md").read_text(
                encoding="utf-8"
            )
            invoke(task_code, prompt)
            task_audit = audit_scan(
                preparation,
                results_dir=work_root / "results",
                output_schema_path=schema_path,
                task_codes=(task_code,),
            )
            if task_audit["status"] != "accepted_shadow":
                correction = json.dumps(
                    task_audit["failures"], ensure_ascii=False, sort_keys=True
                )
                corrected_prompt = prompt.replace(
                    "SOURCE_TEXT\n",
                    "PREVIOUS_OUTPUT_REJECTED_BY_DETERMINISTIC_AUDIT:\n"
                    + correction
                    + "\n请只修正上述合同或逐字引文错误，并重新输出完整 JSON。\n\n"
                    + "SOURCE_TEXT\n",
                    1,
                )
                invoke(
                    task_code,
                    corrected_prompt,
                )
                task_audit = audit_scan(
                    preparation,
                    results_dir=work_root / "results",
                    output_schema_path=schema_path,
                    task_codes=(task_code,),
                )
                if task_audit["status"] != "accepted_shadow":
                    raise ValueError(
                        f"{task_code}: 政书批次纠正后仍未通过审计: "
                        + json.dumps(
                            task_audit["failures"],
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                    )
            return task_code

        tasks = list(preparation["tasks"])
        canary_code = str(preparation["canary_task_code"])
        canary = next(task for task in tasks if str(task["task_code"]) == canary_code)
        completed: list[str] = list(restored)
        if canary_code not in completed:
            completed.append(extract(canary))
        completed_set = set(completed)
        remaining_tasks = [
            task for task in tasks if str(task["task_code"]) not in completed_set
        ]
        with ThreadPoolExecutor(max_workers=limits.model_workers) as executor:
            futures = {
                executor.submit(extract, task): str(task["task_code"])
                for task in remaining_tasks
            }
            for future in as_completed(futures):
                try:
                    completed.append(future.result())
                except Exception:
                    for pending in futures:
                        pending.cancel()
                    raise
        audit = audit_scan(
            preparation,
            results_dir=work_root / "results",
            output_schema_path=schema_path,
        )
        quality = _quality_report(audit=audit, configured=configured)
        if quality["status"] != "passed":
            raise ValueError(
                "政书中性材料未通过质量门: "
                + json.dumps(quality, ensure_ascii=False, sort_keys=True)
            )
        current = {
            "schema_version": SCHEMA_VERSION,
            "status": "quality_accepted_shadow",
            "dynasty": dynasty,
            "dynasty_token": str(configured["dynasty_token"]),
            "input_fingerprint": input_fingerprint,
            "extraction_policy": EXTRACTION_POLICY_VERSION,
            "output_schema_sha256": extraction_identity["output_schema_sha256"],
            "source_index_identity": index.identity,
            "sources": source_identities,
            "quality": quality,
            "chains": audit["chains"],
            "limitations": sorted(
                {
                    str(item)
                    for task_code in completed
                    for item in (
                        json.loads(
                            (work_root / "results" / f"{task_code}.json").read_text(
                                encoding="utf-8"
                            )
                        ).get("limitations")
                        or ()
                    )
                }
            ),
            "formal_writes": 0,
            "score_writes": 0,
        }
        _atomic_json(current_path, current)
        succeeded = True
        shutil.rmtree(resume_root, ignore_errors=True)
        return {
            **current,
            "reused": False,
            "model_call_count": len(model_calls),
            "business_write_count": 0,
            "output": str(current_path),
        }
    except Exception:
        results_dir = work_root / "results"
        if results_dir.is_dir():
            resume_root.mkdir(parents=True, exist_ok=True)
            for result_path in results_dir.glob("*.json"):
                shutil.copy2(result_path, resume_root / result_path.name)
        raise
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
        if succeeded:
            shutil.rmtree(resume_root, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="朝代级政书中性材料一次性扫描")
    parser.add_argument("--dynasty", required=True)
    parser.add_argument("--source-index", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model-workers", type=int, default=4)
    parser.add_argument("--model-timeout-seconds", type=int, default=120)
    parser.add_argument("--target-chars", type=int, default=2_400)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = rebuild_dynasty_governance(
        dynasty=args.dynasty,
        source_index_path=args.source_index,
        runtime_root=args.runtime_root,
        workspace_root=args.workspace_root,
        codex_bin=args.codex_bin,
        limits=DynastyGovernanceLimits(
            model_workers=args.model_workers,
            model_timeout_seconds=args.model_timeout_seconds,
            target_chars=args.target_chars,
        ),
    )
    summary = {
        key: report.get(key)
        for key in (
            "schema_version",
            "status",
            "dynasty",
            "reused",
            "model_call_count",
            "business_write_count",
            "quality",
            "output",
        )
        if key in report
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
