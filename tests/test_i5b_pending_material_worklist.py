from __future__ import annotations

from scripts.dev import i5b_pending_material_worklist as tool


def pending_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "emperor": "刘彻",
        "rule_code": "appointment_delegation",
        "obj_src_id": 2304,
        "direction": "positive",
        "emp_obj_id": 340,
        "obj_id": 343,
        "obj_type": "person",
        "obj_period": "西汉",
        "obj_name": "儿宽",
        "src_key": "SRC-WS-237F6D77AD",
        "title": "漢書",
        "author": "班固",
        "dynasty": "东汉",
        "volume": "卷058",
        "locator": "漢書/卷058",
        "source_url": "",
        "obj_src_note": "漢書卷058摘录命中儿宽，可复核其任官、议政或军务材料。",
        "source_note": "source note",
    }
    row.update(overrides)
    return row


def test_build_report_groups_pending_materials_and_suggests_batches() -> None:
    report = tool.build_report_from_rows(
        [
            pending_row(obj_src_id=2304),
            pending_row(obj_src_id=2319, obj_name="董仲舒"),
            pending_row(emperor="刘邦", rule_code="appointment_delegation", obj_src_id=2280, obj_name="韩信"),
        ],
        batch_size=2,
    )

    assert report["pending_cluster_count"] == 2
    assert report["pending_material_count"] == 3
    groups = {(group["emperor"], group["rule_code"]): group for group in report["groups"]}
    assert groups[("刘邦", "appointment_delegation")]["pending_material_ids"] == [2280]
    assert groups[("刘彻", "appointment_delegation")]["pending_material_ids"] == [2304, 2319]
    assert sorted(batch["material_count"] for batch in report["suggested_batches"]) == [1, 2]


def test_build_report_adds_factor_patch_templates() -> None:
    report = tool.build_report_from_rows(
        [pending_row()],
        factor_options=[
            {
                "rule_code": "appointment_delegation",
                "factor_name": "appointment_importance",
                "label": "有实际职责的任用、信任或单一领域真实授权。",
                "value_num": "1",
                "factor_option_id": 43,
                "source_doc": "docs/分项规则/第五项统治者政治素质/B用人与授权.md",
                "source_line": 251,
            },
            {
                "rule_code": "",
                "factor_name": "source_factor",
                "label": "基础史源",
                "value_num": "1",
                "factor_option_id": 9,
                "source_doc": "docs/证据规则/证据簇计算公式.md",
                "source_line": 120,
            },
        ],
    )

    template = report["groups"][0]["materials"][0]["factor_patch_template"]

    assert template["target_action"] == "review"
    assert template["side"] == "positive"
    assert template["factor_keys"] == [
        "appointment_importance",
        "appointment_effect",
        "continuity_factor",
        "attribution_factor",
        "source_factor",
        "context_factor",
    ]
    assert template["factor_refs"]["appointment_importance"] == {"label": ""}
    assert template["factor_option_candidates"]["appointment_importance"][0]["label"] == "有实际职责的任用、信任或单一领域真实授权。"
    assert template["factor_option_candidates"]["source_factor"][0]["label"] == "基础史源"


def test_render_markdown_includes_material_details() -> None:
    report = tool.build_report_from_rows([pending_row()], batch_size=40)

    rendered = tool.render_markdown(report)

    assert "刘彻/appointment_delegation" in rendered
    assert "儿宽(343)" in rendered
    assert "漢書 卷058 漢書/卷058" in rendered
