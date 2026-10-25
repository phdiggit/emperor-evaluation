from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


SOURCE_PATH = Path("config/third-item/third-item-c-strategy-chain-adjudications.json")
C_PATH = Path(
    "docs/评分结算/净收益/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json"
)

AXIS_FIELDS = {
    "C1": "combat_delivery_grade",

}
GRADE_RANGES = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))


def _reject_grade_aliases(row: Mapping[str, Any]) -> None:
    aliases = {'raw_grade', 'C_overall_grade'} & row.keys()
    if aliases:
        raise ValueError(f'C总档只保存final_grade及其C1主评，不得保存重复别名：{sorted(aliases)}')


def _grade_number(value: object) -> int | None:
    match = re.search(r"(\d+)$", str(value or ""))
    return int(match.group(1)) if match else None


def _normalize_return_class(value: object) -> str:
    text = str(value or "UNKNOWN")
    return "PROPORTIONATE_RETURN" if text == "COMMENSURATE_RETURN" else text


def _major_parent_refs(chains, outcome):
    refs=[]
    for chain in chains:
        if not chain.get('major_system_'+outcome):continue
        for field in ('member_parent_refs','source_parent_refs','source_event_refs'):
            refs.extend(chain.get(field) or [])
        refs.extend(chain[field] for field in ('canonical_strategy_ref','canonical_parent_ref') if chain.get(field))
    return list(dict.fromkeys(refs))


def _chain_profile(chains: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    refs: dict[str, list[str]] = {}
    for chain in chains:
        chain_id = str(chain.get("chain_id") or "")
        outcome = _normalize_return_class(chain.get("terminal_result_class"))
        counts[outcome] += 1
        refs.setdefault(outcome, []).append(chain_id)
    known = sum(
        counts.get(outcome, 0)
        for outcome in (
            "HIGH_RETURN",
            "PROPORTIONATE_RETURN",
            "LOW_RETURN",
            "NEGATIVE_RETURN",
        )
    )
    return {
        "source": "CURRENT_STRATEGIC_CHAIN_RESULTS",
        "selected_chain_count": len(chains),
        "known_outcome_count": known,
        "return_class_counts": dict(sorted(counts.items())),
        "return_class_chain_refs": {
            key: refs[key] for key in sorted(refs)
        },
        "major_system_success_count": sum(
            bool(chain.get("major_system_success")) for chain in chains
        ),
        "major_system_failure_count": sum(
            bool(chain.get("major_system_failure")) for chain in chains
        ),
        "status": "QUANTIFIED" if known else "UNQUANTIFIED",
    }


def _records_by_id(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    for row in payload.get('records') or ():
        _reject_grade_aliases(row)
    return {
        str(row["ruler_id"]): row
        for row in payload.get("records") or ()
        if row.get("ruler_id")
    }


def _source_records_by_id(source: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = list(source.get("records") or ())
    indexed = {
        str(row["ruler_id"]): row
        for row in records
        if row.get("ruler_id")
    }
    if len(indexed) != len(records):
        raise ValueError("第三项C战略链正式源人物ID缺失或重复")
    for row in records:
        _reject_grade_aliases(row.get('formal_writeback', {}).get('fields', {}))
        if "public_reading" in row.get("formal_writeback", {}).get("fields", {}):
            raise ValueError("第三项C公开正文只维护在正式记录，不得存入战略链写回源")
    return indexed


def _formal_public_readings(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records = list(payload.get("records") or ())
    indexed = _records_by_id(payload)
    if len(indexed) != len(records):
        raise ValueError("第三项C正文来源人物ID缺失或重复")
    readings = {}
    for ruler_id, row in indexed.items():
        reading = row.get("public_reading")
        if not isinstance(reading, dict) or not reading:
            raise ValueError(f"{ruler_id}缺少正式C公开正文，不得从旧写回源或生成记录补造")
        readings[ruler_id] = reading
    return readings


def load_strategy_chain_source(workspace_root: Path) -> dict[str, Any]:
    source = json.loads(
        (workspace_root / SOURCE_PATH).read_text(encoding="utf-8")
    )
    if source.get("schema_version") != "third-item-c-strategy-chain-adjudications-v3":
        raise ValueError("第三项C战略链正式源schema不合法")
    if source.get("public_reading_source") != C_PATH.as_posix():
        raise ValueError("第三项C公开正文来源必须是正式C记录")
    if source.get("canonical_status") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("第三项C战略链正式源未声明为正式写回源")
    if source.get("status") != "CURRENT":
        raise ValueError("第三项C战略链正式源不是CURRENT")
    if source.get("primary_scoring_unit") != "STRATEGIC_CHAIN":
        raise ValueError("第三项C战略链正式源主评分颗粒错误")
    if source.get("parent_cycle_role") != "EVIDENCE_ONLY_AND_DISPUTE_DRILLDOWN":
        raise ValueError("第三项C战略链正式源父周期角色错误")
    records = list(source.get("records") or ())
    formal_ids = set(_formal_public_readings(load_json(workspace_root / C_PATH)))
    source_ids = set(_source_records_by_id(source))
    if source_ids != formal_ids:
        raise ValueError(
            f"第三项C战略链源与正式人物集合不一致：缺失{sorted(formal_ids - source_ids)}，"
            f"多余{sorted(source_ids - formal_ids)}"
        )
    for row in records:
        if not row.get("formal_writeback", {}).get("fields"):
            raise ValueError(f"{row.get('ruler_name')}缺少正式写回字段")
    return source


def apply_strategy_chain_writeback_to_payload(
    payload: Mapping[str, Any], source: Mapping[str, Any],
    *, formal_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply scoring fields, retaining authored reading from the formal records."""
    source_by_id = _source_records_by_id(source)
    readings = _formal_public_readings(formal_payload)
    payload_ids = set(_records_by_id(payload))
    if (len(payload_ids) != len(payload.get("records") or ())
            or payload_ids != set(readings) or payload_ids != set(source_by_id)):
        raise ValueError("第三项C重建、战略链源与正文来源人物集合不一致")
    output = deepcopy(dict(payload))
    output_records: list[dict[str, Any]] = []
    for row in payload.get("records") or ():
        updated = deepcopy(dict(row))
        source_row = source_by_id.get(str(row.get("ruler_id") or ""))
        if source_row is not None:
            fields = source_row["formal_writeback"]["fields"]
            for key, value in fields.items():
                updated[key] = deepcopy(value)
        updated["public_reading"] = deepcopy(readings[str(row["ruler_id"])])
        output_records.append(updated)
    output["records"] = output_records
    metadata = source.get("formal_payload_metadata") or {}
    for key, value in metadata.items():
        if key != "records":
            output[key] = deepcopy(value)
    return output


def write_third_item_c_strategy_chain_settlement(
    workspace_root: Path,
) -> dict[str, Any]:
    source = load_strategy_chain_source(workspace_root)
    current = load_json(workspace_root / C_PATH)
    updated = apply_strategy_chain_writeback_to_payload(current, source, formal_payload=current)
    write_json(
        workspace_root / C_PATH,
        updated,
        ruler_polities=load_ruler_polities(workspace_root),
    )
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    from emperor_v4.evaluation.third_item_c_contract_reading import load_context
    from .reading_layout import write_reading
    write_reading(workspace_root, C_PATH.with_suffix('.md'),
        _render_formal_markdown("C", updated["records"], c_review_context=load_context(workspace_root)),
    )
    result = source.get("summary", {}).get("formal_writeback") or {}
    return {
        "status": "WRITTEN",
        "source": str(SOURCE_PATH).replace("\\", "/"),
        "record_count": len(updated.get("records") or ()),
        "score_ready_count": sum(bool(row.get('score_ready')) for row in updated['records']),
        "remaining_unknown_names": result.get("remaining_unknown_names"),
    }


def _verify_inherited_system(row):
    from .third_item_c_joint import verify_joint
    verify_joint(row)

def _verify_grade_projection(row):
    from .third_item_c_joint import verify_joint
    _reject_grade_aliases(row)
    verify_joint(row)

def _verify_score_fields(row, source_row=None):
    from .third_item_c_joint import verify_joint
    verify_joint(row)


def verify_third_item_c_strategy_chain_settlement(
    workspace_root: Path,
) -> dict[str, Any]:
    source = load_strategy_chain_source(workspace_root)
    payload = load_json(workspace_root / C_PATH)
    formal_by_id = _records_by_id(payload)
    source_by_id = _source_records_by_id(source)
    if len(formal_by_id) != len(payload.get("records") or ()):
        raise ValueError("第三项C正式结果人物ID缺失或重复")
    missing = sorted(set(source_by_id) - set(formal_by_id))
    if missing:
        raise ValueError(f"第三项C战略链正式源人物不在正式结果：{missing}")

    all_chain_ids: set[str] = set()
    current_count = 0
    capability_count = 0
    from emperor_v4.evaluation.third_item_c_contract_reading import load_context
    from emperor_v4.evaluation.third_item_c_five_gate import verify_five_gate
    c_review_context = load_context(workspace_root)
    five_systems = c_review_context["systems"]
    five_profiles = {}
    for source_id, source_row in source_by_id.items():
        row = formal_by_id[source_id]
        if row.get("ruler_name") != source_row.get("ruler_name"):
            raise ValueError(f"第三项C人物身份漂移：{source_id}")
        if not str(row.get("polity") or "").strip():
            raise ValueError(f"{row.get('ruler_name')}第三项C缺少政权名称")
        fields = source_row["formal_writeback"]["fields"]
        for key, expected in fields.items():
            if row.get(key) != expected:
                raise ValueError(f"{row.get('ruler_name')}正式C字段未按源同步：{key}")
        current_chains = list(row.get("strategy_chains") or ())
        capability_chains = list(row.get("capability_only_strategy_chains") or ())
        if row.get("strategy_chain_count") != len(current_chains):
            raise ValueError(f"{row.get('ruler_name')}当前战略链计数不一致")
        if row.get("capability_only_strategy_chain_count") != len(capability_chains):
            raise ValueError(f"{row.get('ruler_name')}能力专用战略链计数不一致")
        current_ids = [str(chain.get("chain_id") or "") for chain in current_chains]
        capability_ids = [str(chain.get("chain_id") or "") for chain in capability_chains]
        if current_ids != list(row.get("strategy_chain_refs") or ()):
            raise ValueError(f"{row.get('ruler_name')}当前战略链索引不一致")
        if capability_ids != list(row.get("capability_only_strategy_chain_refs") or ()):
            raise ValueError(f"{row.get('ruler_name')}能力专用战略链索引不一致")
        if set(current_ids) & set(capability_ids):
            raise ValueError(f"{row.get('ruler_name')}当前与能力专用战略链重叠")
        for chain_id in [*current_ids, *capability_ids]:
            if not chain_id or chain_id in all_chain_ids:
                raise ValueError(f"第三项C战略链ID缺失或重复：{chain_id}")
            all_chain_ids.add(chain_id)
        if row.get("strategy_chain_outcome_profile") != _chain_profile(current_chains):
            raise ValueError(f"{row.get('ruler_name')}战略链回报剖面不一致")
        for outcome in ('success','failure'):
            if row.get('major_system_'+outcome+'_refs') != _major_parent_refs(current_chains+capability_chains,outcome):
                raise ValueError(f"{row.get('ruler_name')}重大胜负父阶段引用未同步")
        current_count += len(current_chains)
        capability_count += len(capability_chains)
        _verify_inherited_system(row)
        _verify_grade_projection(row)
        _verify_score_fields(row, source_row)
        verify_five_gate(row, five_systems, five_profiles)

    expected_summary = source.get("summary", {}).get("formal_writeback") or {}
    if expected_summary.get("current_strategy_chain_count") != current_count:
        raise ValueError("第三项C战略链总数与正式记录不一致")
    if expected_summary.get("capability_only_strategy_chain_count") != capability_count:
        raise ValueError("第三项C能力专用战略链总数与正式记录不一致")
    distribution = dict(sorted(Counter(
        str(row.get("final_grade")) for row in payload["records"]
    ).items()))
    if payload.get("grade_distribution") != distribution:
        raise ValueError("第三项C档位分布摘要不一致")

    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    from .reading_layout import check_reading
    check_reading(workspace_root, C_PATH.with_suffix('.md'), _render_formal_markdown("C", payload["records"], c_review_context=c_review_context))
    return {
        "status": "PASS",
        "formal_record_count": len(formal_by_id),
        "source_record_count": len(source_by_id),
        "strategy_chain_count": current_count,
        "capability_only_strategy_chain_count": capability_count,
        "score_ready_count": sum(bool(row.get('score_ready')) for row in payload['records']),
        "remaining_unknown_names": expected_summary.get("remaining_unknown_names"),
    }
