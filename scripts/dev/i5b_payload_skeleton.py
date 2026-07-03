from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import object_pool_importer as importer  # noqa: E402
from scripts.dev import source_excerpt_pool as excerpts  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.common import DEFAULT_PROFILE, DEFAULT_WORKFLOW_CODE, load_source_excerpt_pool_paths, normalize_workflow_code  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.profile import load_profile  # noqa: E402


def source_key_from_page_title(page_title: str) -> str:
    digest = hashlib.sha1(page_title.encode("utf-8")).hexdigest()[:10].upper()
    return f"SRC-WS-{digest}"


def split_page_title(page_title: str) -> tuple[str, str]:
    parts = re.split(r"[/／]", page_title, maxsplit=1)
    title = parts[0].strip()
    volume = parts[1].strip() if len(parts) > 1 else ""
    return title, volume


def _direction_for_layer(layer: str) -> str:
    if "negative" in layer or "reversal" in layer:
        return "negative"
    if "positive" in layer or "supplemental" in layer or "core" in layer:
        return "positive"
    return "mixed"


def _guess_object_type(name: str) -> str:
    if re.search(r"(案|事件|牵连|疑云|破坏|机制|政治|安全)$", name):
        return "event"
    if re.search(r"(制度|兵制|体系)$", name):
        return "mechanism"
    if re.search(r"(外戚|功臣|群体|集团|团队|官员)$", name):
        return "group"
    return "person"


def _load_excerpt_report(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise importer.ImportErrorWithContext(f"{path}: expected object")
    return raw


def _source_rows_from_excerpts(report: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, str]]:
    source_by_title: dict[str, dict[str, str]] = {}
    title_to_key: dict[str, str] = {}
    for item in report.get("excerpts", []) if isinstance(report.get("excerpts", []), list) else []:
        if not isinstance(item, dict):
            continue
        page_title = str(item.get("page_title") or "").strip()
        page_url = str(item.get("page_url") or "").strip()
        if not page_title:
            continue
        src_key = source_key_from_page_title(page_title)
        title, volume = split_page_title(page_title)
        author, dynasty = importer.source_biblio_for_title(title)
        title_to_key[page_title] = src_key
        source_by_title.setdefault(
            page_title,
            {
                "src_key": src_key,
                "title": title or "TODO",
                "author": author,
                "dynasty": dynasty,
                "volume": volume,
                "locator": page_title,
                "url": page_url,
                "note": "TODO: 回源后填写史源说明。",
            },
        )
    return list(source_by_title.values()), title_to_key


def _excerpt_index(report: dict[str, Any], title_to_key: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in report.get("excerpts", []) if isinstance(report.get("excerpts", []), list) else []:
        if not isinstance(item, dict):
            continue
        object_name = str(item.get("object_name") or "").strip()
        page_title = str(item.get("page_title") or "").strip()
        if not object_name:
            continue
        by_object[object_name].append(
            {
                "query": item.get("query"),
                "page_title": page_title,
                "page_url": item.get("page_url"),
                "src_key": title_to_key.get(page_title, ""),
                "passages": item.get("passages", []),
            }
        )
    return by_object


def _placeholder_source(index: int, object_name: str) -> dict[str, str]:
    return {
        "src_key": f"TODO-SRC-{index:03d}",
        "title": "TODO",
        "author": "",
        "dynasty": "",
        "volume": "",
        "locator": "TODO",
        "url": "",
        "note": f"TODO: {object_name} 的回源史料。",
    }


def build_payload_skeleton(
    profile: dict[str, Any],
    *,
    excerpt_report: dict[str, Any] | None = None,
    include_adjacent: bool = False,
    item_code: str = "I5B",
    subitem: str = "第五项B",
) -> dict[str, Any]:
    person = str(profile.get("person") or "").strip()
    if not person:
        raise importer.ImportErrorWithContext("profile.person: expected non-empty string")
    excerpt_report = excerpt_report or {}
    source_rows, title_to_key = _source_rows_from_excerpts(excerpt_report)
    excerpts_by_object = _excerpt_index(excerpt_report, title_to_key)

    source_keys = {row["src_key"] for row in source_rows}
    objects: list[dict[str, Any]] = []
    placeholder_sources: list[dict[str, str]] = []
    for index, candidate in enumerate(excerpts.iter_candidate_objects(profile, include_adjacent=include_adjacent), start=1):
        candidate_excerpts = excerpts_by_object.get(candidate.raw_name, [])
        src_key = next((item.get("src_key") for item in candidate_excerpts if item.get("src_key")), "")
        if not src_key:
            placeholder = _placeholder_source(index, candidate.raw_name)
            src_key = placeholder["src_key"]
            if src_key not in source_keys:
                placeholder_sources.append(placeholder)
                source_keys.add(src_key)
        obj_type = _guess_object_type(candidate.raw_name)
        obj: dict[str, Any] = {
            "obj_type": obj_type,
            "period": "TODO",
            "name": candidate.raw_name,
            "retrieval_layer": candidate.layer,
            "note": f"TODO: {candidate.raw_name} 的身份或事件事实。",
            "links": [
                {
                    "src_key": src_key,
                    "rule_code": "TODO_RULE_CODE",
                    "direction": _direction_for_layer(candidate.layer),
                    "note": "TODO: 写清史料事实与此对象的关系。",
                }
            ],
            "attrs": [],
        }
        if obj_type == "person":
            obj["attrs"].append(
                {
                    "attr_code": "talent_quality",
                    "src_key": src_key,
                    "value_text": "TODO_TALENT_QUALITY",
                    "confidence": 0.85,
                    "note": "TODO: 人才等级属性的史源依据。",
                }
            )
        objects.append(obj)

    payload = {
        "item_code": item_code,
        "subitem": subitem,
        "profile_person": person,
        "query_profile_id": profile.get("query_profile_id"),
        "source_targets": profile.get("source_targets", []),
        "query_bundles": profile.get("query_bundles", []),
        "emperor": {
            "period": "TODO",
            "name": person,
            "title": "TODO",
            "sort_no": None,
            "is_founder": None,
            "succession_mode": "TODO",
            "power_origin": "TODO",
            "note": f"TODO: {person} 的皇帝表说明。",
        },
        "sources": [*source_rows, *placeholder_sources],
        "objects": objects,
        "review": {
            "excerpt_report_person": excerpt_report.get("person"),
            "excerpt_status": excerpt_report.get("status"),
            "candidate_excerpts": excerpts_by_object,
            "warnings": [
                "本文件是待人工回源和填因子的骨架，不得直接导入。",
                "TODO_RULE_CODE、TODO_TALENT_QUALITY、TODO-SRC 必须处理后才能交给 object_pool_importer。",
            ],
        },
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a richer I5B object payload skeleton from a query profile and excerpt report.")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE)
    parser.add_argument("--person", required=True)
    parser.add_argument("--excerpt-report", type=Path)
    parser.add_argument("--include-adjacent", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    profile = load_profile(profile_path, args.person, workflow_code=workflow_code)
    excerpt_report = _load_excerpt_report(args.excerpt_report)
    payload = build_payload_skeleton(profile, excerpt_report=excerpt_report, include_adjacent=args.include_adjacent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "objects": len(payload["objects"]), "sources": len(payload["sources"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
