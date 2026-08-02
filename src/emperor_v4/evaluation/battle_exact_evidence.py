from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "battle-exact-evidence-current-v1"
INPUT_SCHEMA_VERSION = "battle-exact-evidence-backfill-v1"
FORMAL_STATUS = "ADJUDICATED_SOURCE_BACKFILL_REQUIRED"
REQUIRED_RESULT_FIELD = "observable_result"


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def build_current_battle_exact_evidence(
    input_payloads: Sequence[Mapping[str, Any]],
    *,
    ordinary_adjudications: Mapping[str, Any],
    source_pages: Mapping[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    formal = {
        str(row["war_event_id"]): row
        for row in ordinary_adjudications.get("adjudications") or ()
        if row.get("status") == FORMAL_STATUS
    }
    items: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    quote_owners: dict[tuple[str, str, str], str] = {}
    dynasty_counts: dict[str, int] = {}
    evidence_unit_count = 0
    for payload in input_payloads:
        if payload.get("schema_version") != INPUT_SCHEMA_VERSION:
            raise ValueError("逐字回填输入 schema_version 不受支持")
        for raw_item in payload.get("items") or ():
            item = json.loads(json.dumps(raw_item, ensure_ascii=False))
            event_id = str(item.get("war_event_id") or "")
            adjudication = formal.get(event_id)
            if not event_id or event_id in seen_events or adjudication is None:
                raise ValueError(f"逐字回填事件缺失、重复或不属于正式集合: {event_id}")
            seen_events.add(event_id)
            if item.get("unresolved_requirements"):
                raise ValueError(f"{event_id} 仍有未闭合逐字证据")
            adjudicated_source_refs = tuple(
                str(value) for value in adjudication.get("source_refs") or ()
            )
            if not adjudicated_source_refs:
                raise ValueError(f"{event_id} 正式裁决缺少史源范围")
            item["source_refs"] = list(adjudicated_source_refs)
            units = item.get("evidence_units") or []
            if not units:
                raise ValueError(f"{event_id} 缺少逐字证据")
            supported_fields: set[str] = set()
            for unit in units:
                page = str(unit.get("source_page") or "")
                revision = str(unit.get("revision_ref") or "")
                quote = str(unit.get("exact_quote") or "")
                fields = tuple(str(value) for value in unit.get("supported_fields") or ())
                if (
                    not page
                    or not revision
                    or not quote
                    or len(quote) > 120
                    or not unit.get("fact")
                    or not fields
                ):
                    raise ValueError(f"{event_id} 存在不完整逐字证据单元")
                if f"{page}@{revision}" not in set(item["source_refs"]):
                    raise ValueError(f"{event_id} 逐字证据越出裁决史源范围")
                quote_key = (page, revision, quote)
                previous_owner = quote_owners.get(quote_key)
                if previous_owner not in {None, event_id}:
                    raise ValueError(
                        f"{event_id} 与 {previous_owner} 重复消费同一逐字引文"
                    )
                quote_owners[quote_key] = event_id
                if source_pages is not None:
                    raw_text = source_pages.get((page, revision))
                    if raw_text is None or _compact(quote) not in _compact(raw_text):
                        raise ValueError(
                            f"{event_id} 引文未命中固定来源: {page}@{revision}"
                        )
                supported_fields.update(fields)
                evidence_unit_count += 1
            if REQUIRED_RESULT_FIELD not in supported_fields:
                raise ValueError(f"{event_id} 缺少逐字核心结果证据")
            consumes_person_credit = any(
                (member.get("person_command_index") or {}).get("consumption_mode")
                not in {None, "none"}
                for member in adjudication.get("members") or ()
            )
            if consumes_person_credit and (
                "command_and_role_attribution" not in supported_fields
            ):
                raise ValueError(f"{event_id} 缺少逐字人物指挥证据")
            if (adjudication.get("payload") or {}).get("operational_costs") and (
                "participating_scale_or_cost_facts" not in supported_fields
            ):
                raise ValueError(f"{event_id} 缺少逐字规模或成本证据")
            if (
                (adjudication.get("payload") or {}).get("combat_difficulty")
                in {"D3", "D4"}
                and "battle_process" not in supported_fields
            ):
                raise ValueError(f"{event_id} 缺少逐字实际攻守过程")
            if (
                (adjudication.get("payload") or {}).get("attributable_failures")
                and "attributable_failure" not in supported_fields
            ):
                raise ValueError(f"{event_id} 缺少逐字可归责失败证据")
            item.pop("minimum_quote_count", None)
            item["evidence_ref"] = (
                "BATTLE-EVIDENCE-" + _digest({"war_event_id": event_id})[:20].upper()
            )
            items.append(item)
            dynasty = str(item.get("dynasty") or adjudication.get("dynasty") or "")
            dynasty_counts[dynasty] = dynasty_counts.get(dynasty, 0) + 1
    missing = sorted(set(formal) - seen_events)
    extra = sorted(seen_events - set(formal))
    if missing or extra:
        raise ValueError(f"逐字证据未完整覆盖正式集合: missing={missing}, extra={extra}")
    current = {
        "schema_version": SCHEMA_VERSION,
        "status": "REGISTERED_NOT_GOLD",
        "source_backfill_status": "exact_quote_verified",
        "ordinary_adjudications_sha256": _digest(ordinary_adjudications),
        "item_count": len(items),
        "evidence_unit_count": evidence_unit_count,
        "dynasty_counts": dict(sorted(dynasty_counts.items())),
        "items": sorted(items, key=lambda row: str(row["war_event_id"])),
    }
    current["semantic_fingerprint"] = _digest(current)
    return current


def build_current_battle_exact_evidence_from_paths(
    *,
    input_paths: Sequence[Path],
    adjudication_path: Path,
    source_cache_path: Path | None = None,
) -> dict[str, Any]:
    payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in input_paths
    ]
    adjudications = json.loads(adjudication_path.read_text(encoding="utf-8"))
    source_pages: dict[tuple[str, str], str] | None = None
    if source_cache_path is not None:
        with sqlite3.connect(
            f"file:{source_cache_path.resolve()}?mode=ro", uri=True
        ) as connection:
            source_pages = {
                (str(page), str(revision)): str(raw_text)
                for page, revision, raw_text in connection.execute(
                    "SELECT page_title, revision_ref, raw_text FROM pages"
                )
            }
    return build_current_battle_exact_evidence(
        payloads,
        ordinary_adjudications=adjudications,
        source_pages=source_pages,
    )


def write_current_battle_exact_evidence(
    workspace_root: Path,
    *,
    output_path: Path | None = None,
) -> Path:
    input_root = workspace_root / "tmp/战役登记/逐字回填"
    current = build_current_battle_exact_evidence_from_paths(
        input_paths=[
            input_root / "tang.json",
            input_root / "jin_ns.json",
            input_root / "qin_han_sui.json",
            input_root / "sg.json",
        ],
        adjudication_path=(
            workspace_root / "config/ordinary-campaign-adjudications.json"
        ),
        source_cache_path=(
            workspace_root / "tmp/chronicle-tongdian-source-cache.sqlite3"
        ),
    )
    target = output_path or (
        workspace_root / "eval/battle_exact_evidence/current.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target
