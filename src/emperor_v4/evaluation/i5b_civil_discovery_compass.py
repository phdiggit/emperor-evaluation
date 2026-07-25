from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


DISCOVERY_COMPASS_SCHEMA_VERSION = "i5b-civil-discovery-compass-v1"


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ValueError(f"检索罗盘记录缺少 {field}")
    return value


def validate_discovery_record(record: Mapping[str, Any]) -> dict[str, Any]:
    task_code = _required_text(record, "task_code")
    if not task_code.startswith("I5B-CIVIL-"):
        raise ValueError("检索罗盘 task_code 必须以 I5B-CIVIL- 开头")
    leads = record.get("leads") or ()
    if not isinstance(leads, (list, tuple)):
        raise ValueError("检索罗盘 leads 必须是 array")
    normalized_leads = []
    for lead in leads:
        if not isinstance(lead, Mapping):
            raise ValueError("检索罗盘 lead 必须是 object")
        normalized_leads.append(
            {
                "measure": _required_text(lead, "measure"),
                "source_hint": _required_text(lead, "source_hint"),
            }
        )
    return {
        "task_code": task_code,
        "person": _required_text(record, "person"),
        "person_ref": _required_text(record, "person_ref"),
        "query": _required_text(record, "query"),
        "leads": normalized_leads,
    }


def _load_compass(path: Path, ruler: str) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": DISCOVERY_COMPASS_SCHEMA_VERSION,
            "ruler": ruler,
            "records": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("检索罗盘必须是 JSON object")
    if payload.get("schema_version") != DISCOVERY_COMPASS_SCHEMA_VERSION:
        raise ValueError("检索罗盘版本不支持")
    if payload.get("ruler") != ruler:
        raise ValueError("检索罗盘皇帝不匹配")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("检索罗盘 records 必须是 array")
    normalized = [validate_discovery_record(row) for row in records]
    task_codes = [row["task_code"] for row in normalized]
    if len(task_codes) != len(set(task_codes)):
        raise ValueError("检索罗盘 task_code 不得重复")
    return dict(payload) | {"records": normalized}


def record_discovery_compass(
    path: Path,
    *,
    ruler: str,
    record: Mapping[str, Any],
) -> bool:
    normalized = validate_discovery_record(record)
    compass = _load_compass(path, ruler)
    existing = {
        row["task_code"]: row
        for row in compass["records"]
    }.get(normalized["task_code"])
    if existing is not None:
        if existing != normalized:
            raise ValueError("检索罗盘 task_code 已存在且内容冲突")
        return False

    compass["records"].append(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(compass, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True
