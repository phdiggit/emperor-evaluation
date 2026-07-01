from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_factor_recalculator.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_factor_recalculator_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_factor_doc(path: Path, disposition_value: str) -> None:
    path.write_text(
        f"""# factors

`disposition_severity`：

| 值 | 口径 |
| --- | --- |
| `{disposition_value}` | 大规模牵连、系统清洗或长期人才生态破坏。 |

`spillover_factor`：

| 值 | 口径 |
| --- | --- |
| `1.5` | 形成寒蝉、授权信用破裂或人才安全预期下降。 |
""",
        encoding="utf-8",
    )


def test_load_profile_substitutes_markdown_factor_values(tmp_path: Path) -> None:
    tool = load_tool()
    doc = tmp_path / "factors.md"
    profile = tmp_path / "profile.json"
    write_factor_doc(doc, "2.5")
    profile.write_text(
        json.dumps(
            {
                "item_code": "I5B",
                "formula_code": "evidence_cluster_signal_test",
                "clusters": [
                    {
                        "emperor": "测试帝",
                        "rule_code": "tolerate_talent",
                        "note": "测试簇",
                        "materials": [
                            {
                                "obj_src_id": 1,
                                "obj_id": 10,
                                "obj_name": "甲",
                                "direction": "negative",
                                "factors": {
                                    "disposition_severity": {
                                        "label": "大规模牵连、系统清洗或长期人才生态破坏。"
                                    },
                                    "object_weight": "1.0",
                                    "spillover_factor": {
                                        "label": "形成寒蝉、授权信用破裂或人才安全预期下降。"
                                    },
                                    "certainty_factor": "1.0",
                                    "attribution_factor": "1.0",
                                    "source_factor": "1.0",
                                    "context_factor": "1.0",
                                },
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _, _, clusters = tool.load_profile(profile, factor_docs=(doc,))

    assert clusters[0].negative_signal == tool.Decimal("3.750")
    detail = clusters[0].calc_detail
    assert detail["materials"][0]["factor_values"]["disposition_severity"] == "2.5"
    assert detail["materials"][0]["abs_score"] == "3.750"
    assert detail["covered_material_ids"] == [1]
    assert detail["scored_material_ids"] == [1]
    assert detail["supporting_material_ids"] == []


def test_markdown_factor_change_immediately_changes_signal(tmp_path: Path) -> None:
    tool = load_tool()
    doc = tmp_path / "factors.md"
    profile = tmp_path / "profile.json"
    write_factor_doc(doc, "2.0")
    profile.write_text(
        json.dumps(
            {
                "clusters": [
                    {
                        "emperor": "测试帝",
                        "rule_code": "tolerate_talent",
                        "note": "测试簇",
                        "materials": [
                            {
                                "obj_src_id": 1,
                                "obj_id": 10,
                                "obj_name": "甲",
                                "direction": "negative",
                                "factors": {
                                    "disposition_severity": {
                                        "label": "大规模牵连、系统清洗或长期人才生态破坏。"
                                    },
                                    "spillover_factor": "1.0",
                                },
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _, _, before = tool.load_profile(profile, factor_docs=(doc,))
    write_factor_doc(doc, "3.0")
    _, _, after = tool.load_profile(profile, factor_docs=(doc,))

    assert before[0].negative_signal == tool.Decimal("2.000")
    assert after[0].negative_signal == tool.Decimal("3.000")


def test_single_material_score_is_capped_at_four(tmp_path: Path) -> None:
    tool = load_tool()
    doc = tmp_path / "factors.md"
    profile = tmp_path / "profile.json"
    write_factor_doc(doc, "3.0")
    profile.write_text(
        json.dumps(
            {
                "clusters": [
                    {
                        "emperor": "测试帝",
                        "rule_code": "tolerate_talent",
                        "note": "测试簇",
                        "materials": [
                            {
                                "obj_src_id": 1,
                                "obj_id": 10,
                                "obj_name": "甲",
                                "direction": "negative",
                                "factors": {
                                    "disposition_severity": {
                                        "label": "大规模牵连、系统清洗或长期人才生态破坏。"
                                    },
                                    "spillover_factor": "2.0",
                                },
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _, _, clusters = tool.load_profile(profile, factor_docs=(doc,))

    assert clusters[0].negative_signal == tool.Decimal("4.000")
    assert clusters[0].calc_detail["materials"][0]["raw_score"] == "6.000"
    assert clusters[0].calc_detail["materials"][0]["abs_score"] == "4.000"


def test_factor_catalog_accepts_label_then_factor_table(tmp_path: Path) -> None:
    tool = load_tool()
    doc = tmp_path / "factors.md"
    doc.write_text(
        """# factors

`obj_attrs.value_text -> talent_quality_factor`:
| value_text | factor | note |
| --- | --- | --- |
| `historical talent` | `2.5` | fixture |
""",
        encoding="utf-8",
    )

    catalog = tool.parse_factor_catalog((doc,))

    assert tool.lookup_factor(
        catalog,
        "obj_attrs.value_text -> talent_quality_factor",
        "historical talent",
    ) == tool.Decimal("2.5")


def test_load_profile_from_log_replays_factor_refs_not_stale_values(tmp_path: Path) -> None:
    tool = load_tool()
    doc = tmp_path / "factors.md"
    log = tmp_path / "cluster.jsonl"
    doc.write_text(
        """# factors

`severity_factor`:
| value | label |
| --- | --- |
| `2.0` | heavy |
""",
        encoding="utf-8",
    )
    log.write_text(
        json.dumps(
            {
                "emperor": "Replay Emperor",
                "rule_code": "tolerate_talent",
                "formula_code": "evidence_cluster_signal_test",
                "positive_signal": "0.000",
                "negative_signal": "2.000",
                "material_ids": [1, 2],
                "calc_detail": {
                    "item_code": "I5B",
                    "formula_code": "evidence_cluster_signal_test",
                    "coverage": {"positive": "1.0", "negative": "1.0"},
                    "materials": [
                        {
                            "obj_src_id": 1,
                            "obj_key": "case",
                            "obj_name": "case",
                            "side": "negative",
                            "factor_values": {"severity_factor": "2.0"},
                            "factor_refs": {"severity_factor": {"label": "heavy"}},
                        }
                    ],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    _, _, before = tool.load_profile_from_log(
        log,
        factor_docs=(doc,),
        formula_code="evidence_cluster_signal_test",
    )
    doc.write_text(
        """# factors

`severity_factor`:
| value | label |
| --- | --- |
| `3.0` | heavy |
""",
        encoding="utf-8",
    )
    _, _, after = tool.load_profile_from_log(
        log,
        factor_docs=(doc,),
        formula_code="evidence_cluster_signal_test",
    )

    assert before[0].negative_signal == tool.Decimal("2.000")
    assert after[0].negative_signal == tool.Decimal("3.000")
    assert after[0].material_ids == (1, 2)
    assert after[0].calc_detail["covered_material_ids"] == [1, 2]
    assert after[0].calc_detail["scored_material_ids"] == [1]
    assert after[0].calc_detail["supporting_material_ids"] == [2]


def test_material_requires_stable_object_key_for_same_object_aggregation(tmp_path: Path) -> None:
    tool = load_tool()
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "clusters": [
                    {
                        "emperor": "测试帝",
                        "rule_code": "talent_discovery",
                        "note": "测试簇",
                        "materials": [
                            {
                                "obj_src_id": 1,
                                "obj_name": "甲",
                                "direction": "positive",
                                "factors": {"object_weight": "1.0"},
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        tool.load_profile(profile, factor_docs=())
    except tool.I5BFactorRecalculatorError as exc:
        assert "expected obj_id or obj_key" in str(exc)
    else:
        raise AssertionError("expected missing object key to fail")


def test_team_building_uses_team_quality_aggregate(tmp_path: Path) -> None:
    tool = load_tool()
    doc = tmp_path / "factors.md"
    profile = tmp_path / "profile.json"
    doc.write_text(
        """# factors

`talent_quality_factor`：

| 值 | 口径 |
| --- | --- |
| `1.70` | 历史级人才。 |
| `1.35` | 顶级人才。 |
| `1.00` | 重要人才。 |

`role_complementarity_factor`：

| 值 | 口径 |
| --- | --- |
| `1.15` | 文武、谋政、执行、反馈等互补清楚。 |

`long_term_stability_factor`：

| 值 | 口径 |
| --- | --- |
| `1.15` | 长期稳定核心班底。 |
""",
        encoding="utf-8",
    )
    profile.write_text(
        json.dumps(
            {
                "clusters": [
                    {
                        "emperor": "测试帝",
                        "rule_code": "team_building",
                        "note": "测试团队",
                        "team_factors": {
                            "role_complementarity_factor": {
                                "label": "文武、谋政、执行、反馈等互补清楚。"
                            },
                            "long_term_stability_factor": {"label": "长期稳定核心班底。"},
                        },
                        "materials": [
                            {
                                "obj_src_id": 1,
                                "obj_id": 10,
                                "obj_name": "甲",
                                "direction": "positive",
                                "factors": {"talent_quality_factor": {"label": "历史级人才。"}},
                            },
                            {
                                "obj_src_id": 2,
                                "obj_id": 20,
                                "obj_name": "乙",
                                "direction": "positive",
                                "factors": {"talent_quality_factor": {"label": "顶级人才。"}},
                            },
                            {
                                "obj_src_id": 3,
                                "obj_id": 30,
                                "obj_name": "丙",
                                "direction": "positive",
                                "factors": {"talent_quality_factor": {"label": "重要人才。"}},
                            },
                            {
                                "obj_src_id": 4,
                                "obj_id": 40,
                                "obj_name": "群体对象",
                                "direction": "positive",
                                "factors": {"team_quality_excluded": "group_object"},
                            },
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _, _, clusters = tool.load_profile(profile, factor_docs=(doc,))

    detail = clusters[0].calc_detail
    assert clusters[0].positive_signal == tool.Decimal("2.958")
    assert detail["team_quality_signal"] == "2.237"
    assert [item["rank_decay"] for item in detail["team_quality_components"]] == ["1.00", "0.90", "0.80"]
    assert detail["scored_material_ids"] == [4, 1, 2, 3]
    excluded = [item for item in detail["materials"] if item["obj_name"] == "群体对象"][0]
    assert excluded["team_quality_included"] is False


def test_write_clusters_requires_full_material_coverage_by_default(monkeypatch, tmp_path: Path) -> None:
    tool = load_tool()
    cluster = tool.ClusterInput(
        emperor="测试帝",
        rule_code="talent_discovery",
        positive_signal=tool.Decimal("1.0"),
        negative_signal=tool.Decimal("0"),
        formula_code="fixture",
        note="fixture",
        material_ids=(10,),
        calc_detail={"materials": [{"obj_src_id": 10}]},
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(tool, "load_profile", lambda path, factor_docs: ("I5B", "fixture", (cluster,)))
    monkeypatch.setattr(tool, "resolve_dsn", lambda env_name: "postgresql://fixture")

    def fake_upsert_clusters(**kwargs):
        calls.append(kwargs)
        return {"dry_run": kwargs["dry_run"]}

    monkeypatch.setattr(tool, "upsert_clusters", fake_upsert_clusters)

    assert tool.main(["--input", str(tmp_path / "profile.json"), "--write-clusters", "--dry-run"]) == 0
    assert calls[0]["require_full_material_coverage"] is True

    calls.clear()
    assert (
        tool.main(
            [
                "--input",
                str(tmp_path / "profile.json"),
                "--write-clusters",
                "--dry-run",
                "--allow-partial-material-coverage",
            ]
        )
        == 0
    )
    assert calls[0]["require_full_material_coverage"] is False
