from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "military-action-cost-benefit-registry-v1"
SHARD_SCHEMA_VERSION = "military-action-cost-benefit-registry-shard-v1"
PUBLIC_REGISTRY_PATH = Path("docs/公共成果/军事/03-军事行动成本和收益登记.json")
AXIS_KEYS = ("P", "S", "M", "A", "SB", "SN", "BCP", "BCN", "WR")
AXIS_GRADE_MAXIMUMS = {
    "P": 7,
    "S": 7,
    "M": 6,
    "A": 6,
    "SB": 5,
    "SN": 6,
    "BCP": 5,
    "BCN": 6,
    "WR": 5,
}
SEMANTIC_STATUSES = {"CONSUMED", "EXCLUDED"}


def _content_fingerprint(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _required_text(record: Mapping[str, Any], field: str, *, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}缺少非空字符串字段：{field}")
    return value


def _validate_ruler_window(value: Any, *, label: str) -> None:
    if isinstance(value, str):
        if value.strip():
            return
    elif isinstance(value, Mapping):
        if value:
            return
    raise ValueError(f"{label}.ruler_window必须是非空字符串或对象")


def _validate_axes(axes: Any, *, label: str) -> None:
    if not isinstance(axes, Mapping):
        raise ValueError(f"{label}.axes必须是对象")
    actual_keys = set(axes)
    expected_keys = set(AXIS_KEYS)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(f"{label}.axes九轴键不完整：missing={missing}, extra={extra}")
    for axis in AXIS_KEYS:
        adjudication = axes[axis]
        if not isinstance(adjudication, Mapping):
            raise ValueError(f"{label}.axes.{axis}必须是含grade的对象")
        grade = adjudication.get("grade")
        if isinstance(grade, bool) or not isinstance(grade, int):
            raise ValueError(f"{label}.axes.{axis}.grade必须是int档位")
        upper = AXIS_GRADE_MAXIMUMS[axis]
        if not 0 <= grade <= upper:
            raise ValueError(
                f"{label}.axes.{axis}.grade超出0—{upper}：{grade}"
            )


def validate_third_item_d_cycle_registry(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("军事行动成本和收益登记顶层必须是对象")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "军事行动成本和收益登记schema错误："
            f"expected={SCHEMA_VERSION}, actual={payload.get('schema_version')}"
        )
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("军事行动成本和收益登记records必须是数组")

    subject_roster = payload.get("subject_roster")
    if not isinstance(subject_roster, list):
        raise ValueError("军事行动成本和收益登记subject_roster必须是数组")
    declared_subject_count = payload.get("subject_count")
    if (
        isinstance(declared_subject_count, bool)
        or not isinstance(declared_subject_count, int)
        or declared_subject_count != len(subject_roster)
    ):
        raise ValueError("军事行动成本和收益登记subject_count与subject_roster不一致")
    roster_names: dict[str, str] = {}
    roster_name_set: set[str] = set()
    for index, raw_subject in enumerate(subject_roster):
        label = f"subject_roster[{index}]"
        if not isinstance(raw_subject, Mapping):
            raise ValueError(f"{label}必须是对象")
        subject_id = _required_text(raw_subject, "subject_ruler_id", label=label)
        ruler_name = _required_text(raw_subject, "ruler_name", label=label)
        if subject_id in roster_names:
            raise ValueError(f"军事行动成本和收益登记subject_ruler_id重复：{subject_id}")
        if ruler_name in roster_name_set:
            raise ValueError(f"军事行动成本和收益登记ruler_name重复：{ruler_name}")
        windows = raw_subject.get("ruler_windows")
        if not isinstance(windows, list):
            raise ValueError(f"{label}.ruler_windows必须是数组")
        roster_names[subject_id] = ruler_name
        roster_name_set.add(ruler_name)

    identities: set[str] = set()
    for index, raw_record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"{label}必须是对象")
        identity = _required_text(raw_record, "cycle_identity", label=label)
        if identity in identities:
            raise ValueError(f"第三项D周期identity重复：{identity}")
        identities.add(identity)
        status = raw_record.get("semantic_status")
        if status not in SEMANTIC_STATUSES:
            raise ValueError(f"{label}.semantic_status非法：{status}")
        if status != "CONSUMED":
            continue
        subject_id = _required_text(raw_record, "subject_ruler_id", label=label)
        ruler_name = _required_text(raw_record, "ruler_name", label=label)
        if roster_names.get(subject_id) != ruler_name:
            raise ValueError(
                f"{label}主体不在subject_roster或姓名不一致：{subject_id}/{ruler_name}"
            )
        _validate_ruler_window(raw_record.get("ruler_window"), label=label)
        _required_text(raw_record, "canonical_parent_cycle_ref", label=label)
        _validate_axes(raw_record.get("axes"), label=label)
    return deepcopy(dict(payload))


def load_third_item_d_cycle_registry(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"军事行动成本和收益登记不存在：{path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"军事行动成本和收益登记JSON损坏：{path}: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise ValueError("军事行动成本和收益登记manifest顶层必须是对象")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "军事行动成本和收益登记manifest schema错误："
            f"expected={SCHEMA_VERSION}, actual={manifest.get('schema_version')}"
        )
    if "records" in manifest:
        raise ValueError("军事行动成本和收益登记只接受manifest，不接受单体records")

    record_count = manifest.get("record_count")
    record_order = manifest.get("record_order")
    shard_entries = manifest.get("shards")
    declared_total_fingerprint = manifest.get("content_fingerprint")
    if isinstance(record_count, bool) or not isinstance(record_count, int) or record_count < 0:
        raise ValueError("军事行动成本和收益登记manifest record_count非法")
    if not isinstance(record_order, list) or not all(
        isinstance(identity, str) and identity.strip() for identity in record_order
    ):
        raise ValueError("军事行动成本和收益登记manifest record_order非法")
    if len(record_order) != len(set(record_order)):
        raise ValueError("军事行动成本和收益登记manifest record_order存在重复identity")
    if not isinstance(shard_entries, list):
        raise ValueError("军事行动成本和收益登记manifest shards必须是数组")
    if not isinstance(declared_total_fingerprint, str) or not declared_total_fingerprint:
        raise ValueError("军事行动成本和收益登记manifest缺少content_fingerprint")

    expected_root = path.with_suffix("").resolve()
    records_by_identity: dict[str, dict[str, Any]] = {}
    source_pools: set[str] = set()
    shard_paths: set[str] = set()
    for index, raw_entry in enumerate(shard_entries):
        label = f"manifest.shards[{index}]"
        if not isinstance(raw_entry, Mapping):
            raise ValueError(f"{label}必须是对象")
        relative_text = raw_entry.get("path")
        if not isinstance(relative_text, str) or not relative_text.strip():
            raise ValueError(f"{label}.path必须是非空字符串")
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"{label}.path越界：{relative_text}")
        shard_path = (path.parent / relative).resolve()
        if not shard_path.is_relative_to(expected_root) or shard_path.parent != expected_root:
            raise ValueError(f"{label}.path不在同名分片目录：{relative_text}")
        normalized_path = shard_path.as_posix()
        if normalized_path in shard_paths:
            raise ValueError(f"军事行动成本和收益登记manifest重复shard路径：{relative_text}")
        shard_paths.add(normalized_path)

        entry_count = raw_entry.get("count")
        if isinstance(entry_count, bool) or not isinstance(entry_count, int) or entry_count < 0:
            raise ValueError(f"{label}.count非法")
        declared_sha256 = raw_entry.get("sha256")
        declared_content_fingerprint = raw_entry.get("content_fingerprint")
        if not isinstance(declared_sha256, str) or not declared_sha256:
            raise ValueError(f"{label}.sha256缺失")
        if not isinstance(declared_content_fingerprint, str) or not declared_content_fingerprint:
            raise ValueError(f"{label}.content_fingerprint缺失")

        try:
            raw = shard_path.read_bytes()
        except FileNotFoundError:
            raise FileNotFoundError(f"军事行动成本和收益登记shard不存在：{relative_text}") from None
        if sha256(raw).hexdigest() != declared_sha256:
            raise ValueError(f"军事行动成本和收益登记shard字节sha256漂移：{relative_text}")
        try:
            shard = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"军事行动成本和收益登记shard JSON损坏：{relative_text}: {exc}") from exc
        if not isinstance(shard, Mapping):
            raise ValueError(f"军事行动成本和收益登记shard顶层必须是对象：{relative_text}")
        if shard.get("schema_version") != SHARD_SCHEMA_VERSION:
            raise ValueError(f"军事行动成本和收益登记shard schema错误：{relative_text}")
        source_pool = shard.get("source_pool")
        if not isinstance(source_pool, str) or not source_pool.strip():
            raise ValueError(f"军事行动成本和收益登记shard source_pool缺失：{relative_text}")
        if source_pool in source_pools:
            raise ValueError(f"军事行动成本和收益登记source_pool重复：{source_pool}")
        source_pools.add(source_pool)
        rows = shard.get("records")
        shard_record_count = shard.get("record_count")
        if not isinstance(rows, list):
            raise ValueError(f"军事行动成本和收益登记shard records必须是数组：{relative_text}")
        if (
            isinstance(shard_record_count, bool)
            or not isinstance(shard_record_count, int)
            or shard_record_count != len(rows)
            or entry_count != len(rows)
        ):
            raise ValueError(f"军事行动成本和收益登记shard数量漂移：{relative_text}")
        actual_shard_fingerprint = _content_fingerprint(rows)
        if (
            shard.get("content_fingerprint") != actual_shard_fingerprint
            or declared_content_fingerprint != actual_shard_fingerprint
        ):
            raise ValueError(f"军事行动成本和收益登记shard内容指纹漂移：{relative_text}")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError(f"军事行动成本和收益登记shard记录必须是对象：{relative_text}")
            identity = row.get("cycle_identity")
            if not isinstance(identity, str) or not identity.strip():
                raise ValueError(f"军事行动成本和收益登记shard记录缺cycle_identity：{relative_text}")
            if identity in records_by_identity:
                raise ValueError(f"军事行动成本和收益登记shard周期identity重复：{identity}")
            records_by_identity[identity] = dict(row)

    if len(records_by_identity) != record_count:
        raise ValueError("军事行动成本和收益登记manifest总记录数漂移")
    if len(record_order) != record_count or set(record_order) != set(records_by_identity):
        raise ValueError("军事行动成本和收益登记record_order与shards不一致")
    ordered_records = [records_by_identity[identity] for identity in record_order]
    if _content_fingerprint(ordered_records) != declared_total_fingerprint:
        raise ValueError("军事行动成本和收益登记重建总内容指纹漂移")
    validated_records = validate_third_item_d_cycle_registry({
        "schema_version": SCHEMA_VERSION,
        "subject_count": manifest.get("subject_count"),
        "subject_roster": manifest.get("subject_roster"),
        "records": ordered_records,
    })
    result = deepcopy(dict(manifest))
    result["records"] = validated_records["records"]
    return result


def consumed_cycle_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    validated = validate_third_item_d_cycle_registry(payload)
    return [
        deepcopy(dict(record))
        for record in validated["records"]
        if record["semantic_status"] == "CONSUMED"
    ]
