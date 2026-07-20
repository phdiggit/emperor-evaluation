from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4

from opencc import OpenCC


OUTPUT_SCHEMA_VERSION = "neutral-person-lifecycle-source-scan-v1"
FANOUT_SCHEMA_VERSION = "neutral-person-lifecycle-fanout-v1"
_T2S = OpenCC("t2s")


def _stable_ref(prefix: str, *values: object) -> str:
    digest = sha256()
    for value in values:
        digest.update(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\0")
    return prefix + digest.hexdigest()[:20].upper()


def _validate_quote(
    *,
    task_code: str,
    person_ref: str,
    row_kind: str,
    row: Mapping[str, object],
    source_text: str,
) -> None:
    exact_quote = str(row.get("exact_quote") or "")
    locator_anchor = str(row.get("locator_anchor") or "")
    if not exact_quote or exact_quote not in source_text:
        raise ValueError(
            f"{task_code}/{person_ref}/{row_kind}: exact_quote 无法逐字回指 plaintext"
        )
    if not locator_anchor or locator_anchor not in exact_quote:
        raise ValueError(
            f"{task_code}/{person_ref}/{row_kind}: locator_anchor 不属于 exact_quote"
        )


def build_person_lifecycle_fanout(
    manifest: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
    source_texts: Mapping[str, str],
) -> dict[str, object]:
    tasks = {
        str(task.get("task_code") or ""): task
        for task in manifest.get("tasks") or ()
        if isinstance(task, Mapping)
    }
    if not tasks or len(tasks) != len(manifest.get("tasks") or ()) or "" in tasks:
        raise ValueError("人物生涯扫描 manifest 缺少唯一 task_code")
    supplied = {
        str(result.get("task_code") or ""): result
        for result in results
        if isinstance(result, Mapping)
    }
    if len(supplied) != len(results) or set(supplied) != set(tasks):
        raise ValueError("人物生涯扫描结果必须完整且唯一覆盖 manifest")

    person_fanout: dict[str, dict[str, object]] = {}
    seen_record_refs: dict[str, set[str]] = {}
    seen_lead_refs: dict[str, set[str]] = {}
    page_summaries = []
    quote_count = 0
    record_count = 0
    lead_count = 0
    for task_code, task in sorted(tasks.items()):
        page = str(task.get("source_page") or "")
        revision_ref = str(task.get("revision_ref") or "")
        source_text = source_texts.get(page)
        if not page or not revision_ref or not source_text:
            raise ValueError(f"{task_code}: 缺少页面、revision 或 plaintext")
        source_sha256 = sha256(source_text.encode("utf-8")).hexdigest()
        expected_sha256 = str(task.get("source_sha256") or "")
        if expected_sha256 and expected_sha256 != source_sha256:
            raise ValueError(f"{task_code}: plaintext hash 与 manifest 不一致")
        expected_people = {
            str(person.get("person_ref") or ""): person
            for person in task.get("people") or ()
            if isinstance(person, Mapping)
        }
        if (
            not expected_people
            or "" in expected_people
            or len(expected_people) != len(task.get("people") or ())
        ):
            raise ValueError(f"{task_code}: manifest 人物身份缺失或重复")

        result = supplied[task_code]
        actual_people = {
            str(person.get("person_ref") or ""): person
            for person in result.get("people") or ()
            if isinstance(person, Mapping)
        }
        if (
            result.get("schema_version") != OUTPUT_SCHEMA_VERSION
            or result.get("source_page") != page
            or str(result.get("revision_ref") or "") != revision_ref
            or result.get("coverage_scope") != "FULL_LIFECYCLE_SOURCE"
            or len(actual_people) != len(result.get("people") or ())
            or set(actual_people) != set(expected_people)
        ):
            raise ValueError(f"{task_code}: 输出合同、史源身份或人物覆盖不一致")

        page_records = 0
        page_leads = 0
        for person_ref, person in actual_people.items():
            expected = expected_people[person_ref]
            if (
                person.get("person_scan_key") != expected.get("person_scan_key")
                or _T2S.convert(str(person.get("canonical_name") or ""))
                != _T2S.convert(str(expected.get("canonical_name") or ""))
            ):
                raise ValueError(f"{task_code}/{person_ref}: person identity 不一致")
            canonical_name = str(expected["canonical_name"])
            target = person_fanout.setdefault(
                person_ref,
                {
                    "person_ref": person_ref,
                    "canonical_name": canonical_name,
                    "source_scans": [],
                    "records": [],
                    "leads": [],
                },
            )
            if target["canonical_name"] != canonical_name:
                raise ValueError(f"{person_ref}: 跨页面 canonical_name 不一致")
            target["source_scans"].append(
                {
                    "person_scan_key": person["person_scan_key"],
                    "source_page": page,
                    "revision_ref": revision_ref,
                    "source_sha256": source_sha256,
                    "coverage_scope": result["coverage_scope"],
                    "scan_notes": str(person.get("scan_notes") or ""),
                }
            )
            for record in person.get("records") or ():
                assertions = record.get("assertions") or ()
                if not assertions:
                    raise ValueError(f"{task_code}/{person_ref}: record 缺少 assertions")
                for assertion in assertions:
                    _validate_quote(
                        task_code=task_code,
                        person_ref=person_ref,
                        row_kind="assertion",
                        row=assertion,
                        source_text=source_text,
                    )
                    quote_count += 1
                record_ref = _stable_ref(
                    "PFACT-",
                    person["person_scan_key"],
                    record.get("date"),
                    record.get("neutral_summary"),
                    assertions,
                )
                if record_ref in seen_record_refs.setdefault(person_ref, set()):
                    raise ValueError(f"{task_code}/{person_ref}: 重复中性 record")
                seen_record_refs[person_ref].add(record_ref)
                target["records"].append(
                    {
                        **record,
                        "record_ref": record_ref,
                        "source_page": page,
                        "revision_ref": revision_ref,
                        "person_scan_key": person["person_scan_key"],
                        "formal_write": False,
                    }
                )
                record_count += 1
                page_records += 1
            for lead in person.get("leads") or ():
                _validate_quote(
                    task_code=task_code,
                    person_ref=person_ref,
                    row_kind="lead",
                    row=lead,
                    source_text=source_text,
                )
                quote_count += 1
                lead_ref = _stable_ref(
                    "PLEAD-",
                    person["person_scan_key"],
                    lead.get("specific_claim"),
                    lead.get("exact_quote"),
                )
                if lead_ref in seen_lead_refs.setdefault(person_ref, set()):
                    raise ValueError(f"{task_code}/{person_ref}: 重复评价 lead")
                seen_lead_refs[person_ref].add(lead_ref)
                target["leads"].append(
                    {
                        **lead,
                        "lead_ref": lead_ref,
                        "source_page": page,
                        "revision_ref": revision_ref,
                        "person_scan_key": person["person_scan_key"],
                        "formal_write": False,
                    }
                )
                lead_count += 1
                page_leads += 1
        page_summaries.append(
            {
                "task_code": task_code,
                "source_page": page,
                "revision_ref": revision_ref,
                "person_count": len(actual_people),
                "record_count": page_records,
                "lead_count": page_leads,
                "quote_audit": "passed",
            }
        )

    return {
        "schema_version": FANOUT_SCHEMA_VERSION,
        "status": "shadow_only",
        "source_output_schema_version": OUTPUT_SCHEMA_VERSION,
        "task_count": len(tasks),
        "source_page_count": len({str(task["source_page"]) for task in tasks.values()}),
        "person_count": len(person_fanout),
        "record_count": record_count,
        "lead_count": lead_count,
        "audited_quote_count": quote_count,
        "page_summaries": page_summaries,
        "people": [
            {
                **person_fanout[person_ref],
                "source_scans": sorted(
                    person_fanout[person_ref]["source_scans"],
                    key=lambda row: (row["source_page"], row["revision_ref"]),
                ),
                "records": sorted(
                    person_fanout[person_ref]["records"],
                    key=lambda row: row["record_ref"],
                ),
                "leads": sorted(
                    person_fanout[person_ref]["leads"],
                    key=lambda row: row["lead_ref"],
                ),
            }
            for person_ref in sorted(person_fanout)
        ],
        "network_requests": 0,
        "database_writes": 0,
        "formal_writes": 0,
        "score_writes": 0,
    }


def _atomic_json(path: Path, payload: Mapping[str, object]) -> bool:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(encoded, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验人物全生涯 plaintext 扫描并确定性分发")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = [
        json.loads((args.results_dir / f"{task['task_code']}.json").read_text(encoding="utf-8"))
        for task in manifest.get("tasks") or ()
    ]
    source_texts = {
        str(task["source_page"]): (
            args.source_dir / (str(task["source_page"]).replace("/", "-") + ".txt")
        ).read_text(encoding="utf-8")
        for task in manifest.get("tasks") or ()
    }
    output = build_person_lifecycle_fanout(manifest, results, source_texts)
    changed = _atomic_json(args.output, output)
    print(
        json.dumps(
            {
                key: output[key]
                for key in (
                    "schema_version",
                    "status",
                    "task_count",
                    "source_page_count",
                    "person_count",
                    "record_count",
                    "lead_count",
                    "audited_quote_count",
                    "database_writes",
                    "formal_writes",
                    "score_writes",
                )
            }
            | {"changed": changed},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
