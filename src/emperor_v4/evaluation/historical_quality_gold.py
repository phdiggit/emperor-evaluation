from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from emperor_v4.adapters.structured_output_contract import (
    validate_payload_against_schema,
)
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCHEMA_PATH = ROOT / "config/historical-quality-gold-manifest.schema.json"
REPORT_SCHEMA_VERSION = "historical-quality-gold-comparison-v1"


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须是 object: {path}")
    return payload


def _normalize_text(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", str(value or "")).casefold()


def _path_value(value: object, path: str) -> object:
    current = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _validate_manifest_semantics(manifest: Mapping[str, object]) -> None:
    cases = list(manifest.get("cases") or ())
    refs = [str(case.get("gold_ref") or "") for case in cases]
    if len(refs) != len(set(refs)):
        raise ValueError("Gold manifest 的 gold_ref 必须唯一")
    known = set(refs)
    dispositions = list(manifest.get("actual_dispositions") or ())
    disposition_keys = [
        (str(row.get("collection") or ""), str(row.get("actual_ref") or ""))
        for row in dispositions
    ]
    if len(disposition_keys) != len(set(disposition_keys)):
        raise ValueError("Gold actual disposition 的 collection + actual_ref 必须唯一")
    if manifest.get("scope_completeness") == "full_ruler" and not dispositions:
        raise ValueError("full_ruler Gold 必须完整声明 actual_dispositions")
    for row in dispositions:
        unknown = set(str(value) for value in row.get("gold_refs") or ()) - known
        if unknown:
            raise ValueError(f"Gold actual disposition 引用未知 gold_ref: {sorted(unknown)}")
        if row.get("disposition") == "accepted" and not row.get("gold_refs"):
            raise ValueError("accepted actual disposition 必须绑定至少一个 gold_ref")
    for case in cases:
        source_refs = list(case.get("source_refs") or ())
        if len(source_refs) != len(set(source_refs)):
            raise ValueError(f"Gold source_refs 重复: {case['gold_ref']}")
        if any("@" not in str(value) or "#" not in str(value) for value in source_refs):
            raise ValueError(f"Gold source_ref 必须包含 revision 与逐字 locator: {case['gold_ref']}")
        parent = case.get("parent_gold_ref")
        if parent and parent not in known:
            raise ValueError(f"Gold parent_gold_ref 不存在: {case['gold_ref']}")
        if parent == case.get("gold_ref"):
            raise ValueError(f"Gold case 不能以自身为父级: {case['gold_ref']}")
        selector = case.get("selector") or {}
        if any("outcome_ref" in str(key).lower() for key in selector):
            raise ValueError("Gold selector 不得绑定自动生成的 outcome_ref")
        if selector.get("collection") == "historical_outcome_clusters":
            if not any(
                selector.get(key)
                for key in (
                    "label_terms_all",
                    "label_terms_any",
                    "source_refs_any",
                    "content_terms_all",
                    "content_terms_any",
                )
            ):
                raise ValueError(f"成果 Gold selector 缺少语义定位条件: {case['gold_ref']}")
        elif not selector.get("person"):
            raise ValueError(f"人物 Gold selector 缺少 person: {case['gold_ref']}")
        expectations = case.get("expectations") or {}
        if case.get("expected_match_count") == 0 and any(
            expectations.get(key) for key in ("fields", "members", "require_parent_link")
        ):
            raise ValueError(f"排除型 Gold case 不得声明正向期望: {case['gold_ref']}")
        if expectations.get("require_parent_link") and not parent:
            raise ValueError(f"父级链接期望缺少 parent_gold_ref: {case['gold_ref']}")


def load_historical_quality_gold(
    path: Path, *, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> dict[str, Any]:
    manifest = _read_object(path)
    schema = _read_object(schema_path)
    validate_payload_against_schema(manifest, schema)
    _validate_manifest_semantics(manifest)
    return manifest


def _matches(row: Mapping[str, object], selector: Mapping[str, object]) -> bool:
    if selector.get("outcome_kind") and row.get("outcome_kind") != selector["outcome_kind"]:
        return False
    if selector.get("person") and row.get("person") != selector["person"]:
        return False
    label = _normalize_text(row.get("canonical_label") or row.get("person"))
    all_terms = [_normalize_text(value) for value in selector.get("label_terms_all") or ()]
    if any(term not in label for term in all_terms):
        return False
    any_terms = [_normalize_text(value) for value in selector.get("label_terms_any") or ()]
    if any_terms and not any(term in label for term in any_terms):
        return False
    source_refs = set(str(value) for value in row.get("source_refs") or ())
    expected_sources = set(str(value) for value in selector.get("source_refs_any") or ())
    if expected_sources and source_refs.isdisjoint(expected_sources):
        return False
    content = _normalize_text(json.dumps(row, ensure_ascii=False, sort_keys=True))
    content_all = [
        _normalize_text(value) for value in selector.get("content_terms_all") or ()
    ]
    if any(term not in content for term in content_all):
        return False
    content_any = [
        _normalize_text(value) for value in selector.get("content_terms_any") or ()
    ]
    if content_any and not any(term in content for term in content_any):
        return False
    return True


def _member_matches(
    actual: Sequence[Mapping[str, object]], expected: Mapping[str, object]
) -> bool:
    return any(
        all(member.get(key) == value for key, value in expected.items())
        for member in actual
    )


def compare_historical_quality_gold(
    manifest: Mapping[str, object], result: Mapping[str, object]
) -> dict[str, Any]:
    if result.get("ruler") != manifest.get("ruler") or result.get("ruler_ref") != manifest.get("ruler_ref"):
        raise ValueError("Gold manifest 与 result 皇帝身份不一致")
    expected_identity = manifest["input_identity"]
    identity_errors = []
    if result.get("source_pack_sha256") != expected_identity["source_pack_sha256"]:
        identity_errors.append("source_pack_sha256_mismatch")
    if result.get("schema_version") != expected_identity["result_schema_version"]:
        identity_errors.append("result_schema_version_mismatch")

    cases = list(manifest.get("cases") or ())
    matched_by_gold: dict[str, Mapping[str, object]] = {}
    case_reports = []
    blocking = list(identity_errors)
    recall_totals: Counter[str] = Counter()
    recall_matches: Counter[str] = Counter()
    field_total = 0
    field_matches = 0
    for case in cases:
        selector = case["selector"]
        rows = list(result.get(selector["collection"]) or ())
        matches = [row for row in rows if _matches(row, selector)]
        expected_count = int(case["expected_match_count"])
        count_ok = len(matches) == expected_count
        differences: list[dict[str, object]] = []
        if not count_ok:
            differences.append(
                {
                    "kind": "match_count",
                    "expected": expected_count,
                    "actual": len(matches),
                }
            )
        if expected_count == 1:
            importance = str(case["importance"])
            recall_totals[importance] += 1
            if len(matches) == 1:
                recall_matches[importance] += 1
                matched_by_gold[str(case["gold_ref"])] = matches[0]
                for expectation in case["expectations"].get("fields") or ():
                    field_total += 1
                    actual = _path_value(matches[0], str(expectation["path"]))
                    if actual == expectation["expected"]:
                        field_matches += 1
                    else:
                        differences.append(
                            {
                                "kind": "field",
                                "path": expectation["path"],
                                "expected": expectation["expected"],
                                "actual": actual,
                            }
                        )
                actual_members = list(matches[0].get("members") or ())
                for expectation in case["expectations"].get("members") or ():
                    field_total += 1
                    if _member_matches(actual_members, expectation):
                        field_matches += 1
                    else:
                        differences.append(
                            {
                                "kind": "member",
                                "expected": expectation,
                            }
                        )
        case_reports.append(
            {
                "gold_ref": case["gold_ref"],
                "canonical_label": case["canonical_label"],
                "importance": case["importance"],
                "matched_refs": [
                    row.get("outcome_ref") or row.get("person_ref") for row in matches
                ],
                "status": "matched" if not differences else "mismatch",
                "differences": differences,
            }
        )

    report_by_ref = {row["gold_ref"]: row for row in case_reports}
    for case in cases:
        if not (case["expectations"].get("require_parent_link") and case.get("parent_gold_ref")):
            continue
        child = matched_by_gold.get(str(case["gold_ref"]))
        parent = matched_by_gold.get(str(case["parent_gold_ref"]))
        linked = bool(
            child
            and parent
            and (
                child.get("parent_outcome_ref")
                or (child.get("payload") or {}).get("parent_outcome_ref")
            )
            == parent.get("outcome_ref")
        )
        field_total += 1
        if linked:
            field_matches += 1
        else:
            report_by_ref[str(case["gold_ref"])]["differences"].append(
                {
                    "kind": "parent_link",
                    "parent_gold_ref": case["parent_gold_ref"],
                    "expected": "linked",
                    "actual": "missing_or_unlinked",
                }
            )
            report_by_ref[str(case["gold_ref"])]["status"] = "mismatch"

    for row in case_reports:
        if row["status"] == "mismatch":
            blocking.append(str(row["gold_ref"]))
    recall = {
        importance: {
            "matched": recall_matches[importance],
            "total": recall_totals[importance],
            "rate": (
                recall_matches[importance] / recall_totals[importance]
                if recall_totals[importance]
                else None
            ),
        }
        for importance in ("major", "secondary", "boundary")
    }
    precision = None
    precision_status = "not_claimed_for_calibration_slice"
    disposition_report: dict[str, object] = {
        "required": manifest["scope_completeness"] == "full_ruler",
        "covered": 0,
        "actual": 0,
        "missing_refs": [],
        "unexpected_refs": [],
        "kind_counts": {},
    }
    if manifest["scope_completeness"] == "full_ruler":
        actual_keys: set[tuple[str, str]] = set()
        for collection, reference_field in (
            ("historical_outcome_clusters", "outcome_ref"),
            ("profile_projection_review", "person_ref"),
        ):
            for row in result.get(collection) or ():
                actual_keys.add((collection, str(row[reference_field])))
        dispositions = list(manifest.get("actual_dispositions") or ())
        disposition_by_key = {
            (str(row["collection"]), str(row["actual_ref"])): row
            for row in dispositions
        }
        disposition_keys = set(disposition_by_key)
        missing = sorted(f"{collection}:{reference}" for collection, reference in actual_keys - disposition_keys)
        unexpected = sorted(f"{collection}:{reference}" for collection, reference in disposition_keys - actual_keys)
        kind_counts = Counter(str(row["disposition"]) for row in dispositions)
        denominator = (
            kind_counts["accepted"]
            + kind_counts["duplicate"]
            + kind_counts["false_positive"]
        )
        if not missing and not unexpected and denominator:
            precision = kind_counts["accepted"] / denominator
            precision_status = "measured_full_ruler"
        else:
            precision_status = "blocked_incomplete_actual_dispositions"
            if missing:
                blocking.append("missing_actual_dispositions")
            if unexpected:
                blocking.append("unexpected_actual_dispositions")
        disposition_report = {
            "required": True,
            "covered": len(actual_keys & disposition_keys),
            "actual": len(actual_keys),
            "missing_refs": missing,
            "unexpected_refs": unexpected,
            "kind_counts": dict(sorted(kind_counts.items())),
        }

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed" if not blocking else "failed",
        "comparison_mode": "post_run_gold_only",
        "gold_accessed": True,
        "ruler": manifest["ruler"],
        "ruler_ref": manifest["ruler_ref"],
        "scope_code": manifest["scope_code"],
        "scope_completeness": manifest["scope_completeness"],
        "input_identity_errors": identity_errors,
        "recall": recall,
        "field_accuracy": {
            "matched": field_matches,
            "total": field_total,
            "rate": field_matches / field_total if field_total else None,
        },
        "accepted_episode_precision": precision,
        "precision_status": precision_status,
        "actual_disposition_coverage": disposition_report,
        "blocking_refs": blocking,
        "cases": case_reports,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }


def compare_historical_quality_gold_files(
    *, manifest_path: Path, result_path: Path, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> dict[str, Any]:
    return compare_historical_quality_gold(
        load_historical_quality_gold(manifest_path, schema_path=schema_path),
        _read_object(result_path),
    )


def verify_historical_quality_gold_sources(
    manifest: Mapping[str, object], *, source_index: LocalSourceTextIndex
) -> dict[str, Any]:
    references = sorted(
        {
            str(reference)
            for case in manifest.get("cases") or ()
            for reference in case.get("source_refs") or ()
        }
    )
    parsed = []
    for reference in references:
        page_revision, separator, quote = reference.partition("#")
        page_title, revision_separator, revision_ref = page_revision.rpartition("@")
        if not separator or not revision_separator or not page_title or not revision_ref or not quote:
            raise ValueError(f"Gold source_ref 格式无效: {reference}")
        parsed.append((reference, page_title, revision_ref, quote))
    page_titles = sorted({page_title for _, page_title, _, _ in parsed})
    works = sorted({page_title.split("/", 1)[0] for page_title in page_titles})
    pages = {
        page.page_title: page
        for page in source_index.iter_pages(works=works, page_titles=page_titles)
    }
    rows = []
    for reference, page_title, revision_ref, quote in parsed:
        page = pages.get(page_title)
        errors = []
        if page is None:
            errors.append("page_missing")
        else:
            accepted_revision = revision_ref.removeprefix("wikisource-revid:")
            if page.revision_ref != accepted_revision:
                errors.append("revision_mismatch")
            if quote not in page.raw_text:
                errors.append("exact_quote_missing")
        rows.append(
            {
                "source_ref": reference,
                "status": "verified" if not errors else "failed",
                "errors": errors,
            }
        )
    failures = [row["source_ref"] for row in rows if row["status"] != "verified"]
    return {
        "schema_version": "historical-quality-gold-source-verification-v1",
        "status": "passed" if not failures else "failed",
        "ruler": manifest["ruler"],
        "scope_code": manifest["scope_code"],
        "source_index_identity": source_index.identity,
        "source_ref_count": len(rows),
        "verified_count": len(rows) - len(failures),
        "failed_refs": failures,
        "sources": rows,
        "network_requests": 0,
        "model_calls": 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }


def verify_historical_quality_gold_source_files(
    *,
    manifest_path: Path,
    source_index_path: Path,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    return verify_historical_quality_gold_sources(
        load_historical_quality_gold(manifest_path, schema_path=schema_path),
        source_index=LocalSourceTextIndex(source_index_path),
    )
