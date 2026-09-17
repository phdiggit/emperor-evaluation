from __future__ import annotations

from copy import deepcopy
import json

from emperor_v4.evaluation.second_item_a_public import (
    PUBLIC_FORBIDDEN_RE,
    _clean_public_text,
    _ensure_profile_ids,
    _public_nodes,
    _refresh_payload,
)


def _material(material_id: str, *, measure: str, operation: str, result: str, scope: str = "R0") -> dict:
    return {
        "material_id": material_id,
        "measure": measure,
        "operation": operation,
        "result": result,
        "cost_or_capture": "只计算一次，其他项目事实只作交叉核对。",
        "reception_scope": scope,
    }


def _row() -> dict:
    return {
        "ruler_id": "SYNTHETIC-RULER",
        "ruler_name": "合成甲",
        "grade": "G2",
        "position": "lower",
        "direction_index": 41.5,
        "rank": 1,
        "important_institutions": [
            {
                "institution_node_id": "SYNTHETIC-NODE-1",
                "label_zh": "中央文书接口",
                "institution_domain": "中央组织",
                "major_node_role": "MAJOR_RESTRUCTURE",
                "decision": "MAJOR_NODE",
                "normative_direction": "positive",
                "reason": "本人设置中央文书接口并投入实际运行。",
                "material_ids": ["SYNTHETIC-MATERIAL-1"],
                "construction_operation_material_ids": ["SYNTHETIC-MATERIAL-1"],
                "durability_gate": "NON_S_MAJOR_CONTRIBUTION",
                "counts_toward_S": False,
            }
        ],
        "M_positive_profile": [
            {
                "institution_node_id": "SYNTHETIC-NODE-1",
                "M": "M2",
                "direction": "positive",
                "direction_factor": 1.0,
                "signed_weight": 1.0,
                "result_closure": "observed",
                "material_ids": ["SYNTHETIC-MATERIAL-1"],
            },
            {
                "M": "M2",
                "direction": "positive",
                "direction_factor": 1.0,
                "signed_weight": 1.0,
                "result_closure": "observed",
                "mechanism": "地方账簿核验接口",
                "material_ids": ["SYNTHETIC-MATERIAL-2"],
            },
        ],
        "M_mixed_profile": [],
        "M_negative_profile": [],
    }


def test_public_nodes_merge_by_id_and_assign_a_stable_id_to_unidentified_profile():
    row = _row()
    _ensure_profile_ids(row)
    materials = {
        "SYNTHETIC-MATERIAL-1": _material(
            "SYNTHETIC-MATERIAL-1",
            measure="设置中央文书接口",
            operation="中央文书接口投入运行",
            result="形成稳定文书传递",
        ),
        "SYNTHETIC-MATERIAL-2": _material(
            "SYNTHETIC-MATERIAL-2",
            measure="建立地方账簿核验",
            operation="地方账簿核验实际运行",
            result="形成地方核验结果",
        ),
    }

    nodes, counts = _public_nodes(row, materials)

    assert len(nodes) == 2
    assert nodes[0]["institution_node_id"] == "SYNTHETIC-NODE-1"
    assert nodes[0]["signed_weight"] == 1
    assert nodes[1]["institution_node_id"].startswith("A-PUBLIC-NODE-")
    assert counts["actual"] == 1
    assert counts["not_counted"] == 1
    for node in nodes:
        assert set(node) == {
            "institution_node_id",
            "public_label",
            "public_direction",
            "public_tags",
            "signed_weight",
            "public_adjudication_basis",
            "public_scope",
            "public_boundary",
            "public_reception",
        }
        text = " ".join(
            str(node[field])
            for field in (
                "public_label",
                "public_adjudication_basis",
                "public_scope",
                "public_boundary",
                "public_reception",
            )
        )
        assert not PUBLIC_FORBIDDEN_RE.search(text)


def test_public_text_translates_internal_shorthand_before_persisting():
    text = _clean_public_text(
        "按正式显式复核完成canonical生命周期复核；R4与S++门禁不重复消费；"
        "按A审查清单进入A计权，M2与position只作内部记录。"
    )

    assert "现有材料" in text
    assert "跨朝代长期沿用" in text
    assert "只计算一次" in text
    assert not PUBLIC_FORBIDDEN_RE.search(text)


def test_public_projection_fills_missing_totals_without_changing_scoring_fields(tmp_path):
    payload = {
        "records": [_row()],
        "schema_id": "synthetic-a",
    }
    before = deepcopy(payload["records"][0])
    root = tmp_path
    material_root = root / "docs/公共成果/制度行政/01-制度行政计分材料登记"
    material_root.mkdir(parents=True)
    for material in (
        _material(
            "SYNTHETIC-MATERIAL-1",
            measure="设置中央文书接口",
            operation="中央文书接口投入运行",
            result="形成稳定文书传递",
        ),
        _material(
            "SYNTHETIC-MATERIAL-2",
            measure="建立地方账簿核验",
            operation="地方账簿核验实际运行",
            result="形成地方核验结果",
        ),
        ):
        (material_root / f"{material['material_id']}.json").write_text(
            '{"records": [' + json.dumps(material, ensure_ascii=False) + ']}',
            encoding="utf-8",
        )

    projected = _refresh_payload(payload, root)
    row = projected["records"][0]

    assert row["P_gross"] == 2
    assert row["N_gross"] == 0
    assert row["A_net_units"] == 2
    assert row["grade"] == before["grade"]
    assert row["position"] == before["position"]
    assert row["direction_index"] == before["direction_index"]
    assert row["rank"] == before["rank"]
    assert row["public_adjudication_summary"].endswith("C级（下位）。")
