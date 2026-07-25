from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4

from opencc import OpenCC


SCHEMA_VERSION = "ruler-neutral-person-recall-plan-v1"
FANOUT_SCHEMA_VERSION = "ruler-neutral-person-fanout-v1"
_S2T = OpenCC("s2t")
_T2S = OpenCC("t2s")


def _variants(values: Sequence[object]) -> tuple[str, ...]:
    result: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if len(value) < 2:
            continue
        result.update((value, _S2T.convert(value), _T2S.convert(value)))
    return tuple(sorted((item for item in result if item), key=lambda item: (-len(item), item)))


def _searchable_text(record: Mapping[str, object]) -> str:
    values = [
        record.get("neutral_summary", ""),
        record.get("date", ""),
        record.get("source_page", ""),
    ]
    for assertion in record.get("assertions") or ():
        if isinstance(assertion, Mapping):
            values.extend(
                assertion.get(key, "")
                for key in ("exact_quote", "fact", "locator_anchor")
            )
    return "\n".join(str(value) for value in values)


def _stable_ref(value: str) -> str:
    return "RULER-PERSON-BATCH-" + sha256(value.encode("utf-8")).hexdigest()[:16].upper()


def build_ruler_neutral_person_recall_plan(
    *,
    ruler: str,
    records: Sequence[Mapping[str, object]],
    people: Sequence[Mapping[str, object]],
    batch_count: int = 4,
) -> dict[str, object]:
    ruler = ruler.strip()
    if not ruler or batch_count < 1:
        raise ValueError("皇帝名称不能为空且 batch_count 必须大于零")
    normalized_people: list[dict[str, object]] = []
    seen_refs: set[str] = set()
    for raw in people:
        person_ref = str(raw.get("person_ref") or "").strip()
        canonical_name = str(raw.get("canonical_name") or "").strip()
        if not person_ref or not canonical_name or person_ref in seen_refs:
            raise ValueError("人物入口缺少或重复 person_ref/canonical_name")
        seen_refs.add(person_ref)
        forms = _variants((canonical_name, *(raw.get("aliases") or ())))
        if not forms:
            raise ValueError(f"{canonical_name} 没有可用的至少二字召回词")
        normalized_people.append(
            {
                "person_ref": person_ref,
                "canonical_name": canonical_name,
                "surface_forms": list(forms),
            }
        )

    candidates: list[dict[str, object]] = []
    seen_records: set[str] = set()
    for raw in records:
        record_id = str(raw.get("neutral_record_id") or "").strip()
        if not record_id or record_id in seen_records:
            raise ValueError("中性材料缺少或重复 neutral_record_id")
        seen_records.add(record_id)
        text = _searchable_text(raw)
        matched_people = []
        for person in normalized_people:
            matched = [form for form in person["surface_forms"] if form in text]
            if matched:
                matched_people.append(
                    {
                        "person_ref": person["person_ref"],
                        "canonical_name": person["canonical_name"],
                        "matched_surface_forms": matched,
                    }
                )
        if matched_people:
            candidates.append(
                {
                    "neutral_record_id": record_id,
                    "source_page": str(raw.get("source_page") or ""),
                    "revision_ref": str(raw.get("revision_ref") or ""),
                    "date": str(raw.get("date") or ""),
                    "neutral_summary": str(raw.get("neutral_summary") or ""),
                    "assertions": list(raw.get("assertions") or ()),
                    "matched_people": sorted(
                        matched_people, key=lambda item: str(item["person_ref"])
                    ),
                }
            )

    bins: list[list[dict[str, object]]] = [[] for _ in range(batch_count)]
    sizes = [0] * batch_count
    for record in sorted(
        candidates,
        key=lambda item: len(json.dumps(item, ensure_ascii=False)),
        reverse=True,
    ):
        index = min(range(batch_count), key=lambda item: sizes[item])
        bins[index].append(record)
        sizes[index] += len(json.dumps(record, ensure_ascii=False))

    fingerprint = sha256(
        json.dumps(
            {
                "ruler": ruler,
                "record_ids": sorted(seen_records),
                "people": normalized_people,
                "batch_count": batch_count,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    batches = []
    for index, rows in enumerate(bins, start=1):
        batches.append(
            {
                "task_code": _stable_ref(f"{fingerprint}|{index}"),
                "record_count": len(rows),
                "person_review_count": sum(len(row["matched_people"]) for row in rows),
                "payload_chars": len(json.dumps(rows, ensure_ascii=False)),
                "records": rows,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "shadow_only",
        "ruler": ruler,
        "input_fingerprint": fingerprint,
        "source_record_count": len(records),
        "candidate_record_count": len(candidates),
        "person_count": len(normalized_people),
        "people": normalized_people,
        "batch_count": batch_count,
        "batches": batches,
        "model_call_budget": batch_count,
        "network_requests": 0,
        "database_writes": 0,
        "formal_writes": 0,
        "model_calls": 0,
    }


def build_ruler_neutral_person_fanout(
    plan: Mapping[str, object], batch_results: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("人物分发只接受 ruler-neutral-person-recall-plan-v1")
    expected_batches = {
        str(batch["task_code"]): batch for batch in plan.get("batches") or ()
    }
    supplied = {str(result.get("task_code") or ""): result for result in batch_results}
    if len(supplied) != len(batch_results) or set(supplied) != set(expected_batches):
        raise ValueError("人物分发 batch 结果覆盖不完整或重复")
    people = {
        str(row["person_ref"]): str(row["canonical_name"])
        for row in plan.get("people") or ()
    }
    fanout: dict[str, list[dict[str, object]]] = {person_ref: [] for person_ref in people}
    disposition_counts: dict[str, int] = {}
    reviewed_records = 0
    person_review_count = 0
    eligible_count = 0
    for task_code, batch in expected_batches.items():
        result = supplied[task_code]
        records = {
            str(row["neutral_record_id"]): row for row in batch.get("records") or ()
        }
        reviews = {
            str(row.get("neutral_record_id") or ""): row
            for row in result.get("record_reviews") or ()
        }
        if (
            result.get("schema_version") != "ruler-neutral-shared-fanout-v1"
            or int(result.get("record_count") or -1) != len(records)
            or len(reviews) != len(result.get("record_reviews") or ())
            or set(reviews) != set(records)
        ):
            raise ValueError(f"{task_code} 中性记录覆盖或合同不一致")
        reviewed_records += len(records)
        for record_id, record in records.items():
            review = reviews[record_id]
            expected_people = {
                str(row["person_ref"]): row for row in record["matched_people"]
            }
            actual_people = {
                str(row.get("person_ref") or ""): row
                for row in review.get("person_reviews") or ()
            }
            if (
                len(actual_people) != len(review.get("person_reviews") or ())
                or set(actual_people) != set(expected_people)
            ):
                raise ValueError(f"{record_id} 人物判读覆盖不一致")
            anchors = {
                str(row.get("locator_anchor") or "")
                for row in record.get("assertions") or ()
            }
            for person_ref, person_review in actual_people.items():
                if person_review.get("canonical_name") != people.get(person_ref):
                    raise ValueError(f"{record_id}/{person_ref} 人物身份不一致")
                support = set(person_review.get("supporting_assertion_anchors") or ())
                if not support <= anchors:
                    raise ValueError(f"{record_id}/{person_ref} 引用了不存在的 assertion anchor")
                disposition = str(person_review.get("disposition") or "")
                eligible = bool(person_review.get("profile_eligibility"))
                if disposition == "achievement" and not support:
                    raise ValueError(f"{record_id}/{person_ref} 实绩缺少 assertion anchor")
                if eligible and (
                    disposition != "achievement"
                    or person_review.get("role")
                    in {"recipient", "affected_person", "evaluated_person", "mentioned_only", "not_established"}
                    or person_review.get("responsibility_strength")
                    in {"context_only", "not_established"}
                ):
                    raise ValueError(f"{record_id}/{person_ref} 画像资格与角色或归责冲突")
                person_review_count += 1
                eligible_count += int(eligible)
                disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
                fanout[person_ref].append(
                    {
                        "neutral_record_id": record_id,
                        "source_page": record["source_page"],
                        "revision_ref": record["revision_ref"],
                        "date": record["date"],
                        "neutral_summary": record["neutral_summary"],
                        "review": person_review,
                    }
                )
    return {
        "schema_version": FANOUT_SCHEMA_VERSION,
        "status": "shadow_only",
        "ruler": plan["ruler"],
        "source_record_count": plan["source_record_count"],
        "candidate_record_count": plan["candidate_record_count"],
        "reviewed_record_count": reviewed_records,
        "person_count": len(people),
        "person_review_count": person_review_count,
        "profile_eligible_count": eligible_count,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "person_fanout": [
            {
                "person_ref": person_ref,
                "canonical_name": people[person_ref],
                "candidate_count": len(fanout[person_ref]),
                "profile_eligible_count": sum(
                    bool(row["review"]["profile_eligibility"])
                    for row in fanout[person_ref]
                ),
                "records": fanout[person_ref],
            }
            for person_ref in sorted(people)
        ],
        "network_requests": 0,
        "database_writes": 0,
        "formal_writes": 0,
        "score_writes": 0,
    }


def _atomic_json(path: Path, payload: Mapping[str, object]) -> bool:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按臣子召回皇帝侧中性材料并生成共享判读计划")
    parser.add_argument("--ruler", required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--people", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-count", type=int, default=4)
    args = parser.parse_args(argv)
    people = json.loads(args.people.read_text(encoding="utf-8"))
    if not isinstance(people, list):
        raise ValueError("people 文件必须是 array")
    result = build_ruler_neutral_person_recall_plan(
        ruler=args.ruler,
        records=_read_jsonl(args.records),
        people=people,
        batch_count=args.batch_count,
    )
    changed = _atomic_json(args.output, result)
    print(json.dumps({
        key: result[key]
        for key in (
            "schema_version", "ruler", "source_record_count", "candidate_record_count",
            "person_count", "batch_count", "model_call_budget", "network_requests",
            "database_writes", "formal_writes", "model_calls",
        )
    } | {"changed": changed}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
