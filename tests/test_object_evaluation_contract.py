from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "object_evaluation_b2_examples.jsonl"
EXPERIMENTAL_OBJECTS = ROOT / "data" / "experimental" / "objects.jsonl"
EXPERIMENTAL_OEVALS = ROOT / "data" / "experimental" / "object_evaluations.jsonl"
ANCHORS = ROOT / "data" / "anchors.jsonl"

OBJECT_CLASSES = {
    "person",
    "team",
    "event_case",
    "mechanism",
    "institution",
    "policy",
    "relationship",
    "source_statement",
}
OUTCOMES = {
    "objectized",
    "adjacent_only",
    "no_stable_object",
    "unresolved_lead",
    "excluded_from_subitem",
}
OEVAL_REQUIRED = {
    "oeval_id",
    "oeval_code",
    "obj_id",
    "obj_code",
    "src_ids",
    "sp_ids",
    "clus_ids",
    "class",
    "category",
    "relation",
    "polarity",
    "strength",
    "relevance",
    "directness",
    "scale",
    "structurality",
    "confidence",
    "residual",
    "eligible",
}
OBJECT_ALLOWED = {
    "row_type",
    "outcome",
    "obj_id",
    "obj_code",
    "class",
    "category",
    "label",
    "src_ids",
    "sp_ids",
}
CODE_RE = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
PROCESSING_ALLOWED = {
    "row_type",
    "outcome",
    "src_ids",
    "sp_ids",
    "clus_ids",
    "category",
    "relation",
    "residual",
    "eligible",
    "diagnostic_only",
    "feeds_formal_scoring",
}
DIAGNOSTIC_FIELDS = {"diagnostic_only", "feeds_formal_scoring"}
FORMAL_SCORING_FIELDS = {
    "auto_band_direction",
    "formal_band_draft",
    "formal_rank",
    "formal_score_value_45",
    "rank",
    "score",
    "score_value",
}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_dual_key_discipline(rows: list[dict[str, object]]) -> None:
    for row in rows:
        for key, value in row.items():
            if key.endswith("_id"):
                assert value is None or isinstance(value, int), f"{key} must be null or int"
            if key.endswith("_code"):
                assert isinstance(value, str)
                assert CODE_RE.fullmatch(value), f"{key} must be a compact code"
                assert len(value) <= 32


def assert_primary_codes_unique(rows: list[dict[str, object]]) -> None:
    object_codes = [row["obj_code"] for row in rows if row.get("row_type") == "object"]
    oeval_codes = [row["oeval_code"] for row in rows if row.get("row_type") == "object_evaluation"]
    assert len(object_codes) == len(set(object_codes))
    assert len(oeval_codes) == len(set(oeval_codes))


def assert_object_rows(rows: list[dict[str, object]]) -> set[str]:
    object_codes = {
        str(row["obj_code"])
        for row in rows
        if row.get("row_type") == "object"
    }
    assert object_codes

    for row in rows:
        if row.get("row_type") != "object":
            continue
        assert set(row) <= OBJECT_ALLOWED
        assert row["obj_code"] in object_codes
        assert row["class"] in OBJECT_CLASSES
        assert row["outcome"] == "objectized"
        assert isinstance(row["src_ids"], list)
        assert isinstance(row["sp_ids"], list)
        assert "polarity" not in row
        assert "strength" not in row
        assert "eligible" not in row
    return object_codes


def assert_object_evaluation_rows(rows: list[dict[str, object]], object_codes: set[str]) -> None:
    for row in rows:
        if row.get("row_type") != "object_evaluation":
            continue
        required_keys = OEVAL_REQUIRED | {"row_type", "outcome"}
        assert required_keys <= set(row) <= required_keys | DIAGNOSTIC_FIELDS
        assert row["outcome"] == "objectized"
        assert row["obj_code"] in object_codes
        assert row["class"] in OBJECT_CLASSES
        assert row["polarity"] in {"positive", "negative"}
        assert row["strength"] in {1, 2, 3, 4}
        assert isinstance(row["src_ids"], list) and row["src_ids"]
        assert isinstance(row["sp_ids"], list) and row["sp_ids"]
        assert isinstance(row["clus_ids"], list)
        assert isinstance(row["eligible"], bool)
        if "diagnostic_only" in row:
            assert row["diagnostic_only"] is True
            assert row["feeds_formal_scoring"] is False


def assert_processing_rows(rows: list[dict[str, object]]) -> None:
    for row in rows:
        if row.get("row_type") != "processing_outcome":
            continue
        assert set(row) <= PROCESSING_ALLOWED
        assert row["outcome"] == "adjacent_only"
        assert row["eligible"] is False
        assert "obj_id" not in row
        assert "obj_code" not in row
        assert "oeval_id" not in row
        assert "oeval_code" not in row


def test_b2_fixture_keeps_compact_object_evaluation_fields() -> None:
    rows = read_jsonl(FIXTURE)
    object_codes = assert_object_rows(rows)

    assert_dual_key_discipline(rows)
    assert_primary_codes_unique(rows)
    for row in rows:
        assert row["outcome"] in OUTCOMES
        if row["row_type"] in {"object", "object_evaluation", "processing_outcome"}:
            continue

        raise AssertionError(f"unexpected row_type: {row['row_type']}")
    assert_object_evaluation_rows(rows, object_codes)
    assert_processing_rows(rows)


def test_b2_fixture_covers_required_migration_examples() -> None:
    rows = read_jsonl(FIXTURE)
    labels = {
        str(row["label"])
        for row in rows
        if row.get("row_type") == "object"
    }
    relations = {
        str(row["relation"])
        for row in rows
        if row.get("row_type") == "object_evaluation"
    }
    categories = {
        str(row["category"])
        for row in rows
        if row.get("row_type") == "object_evaluation"
    }

    assert {"虞世基", "不可谏/无一言谏诤", "周亚夫", "晁错", "丙吉荐才链"} <= labels
    assert {
        "专典机密授权",
        "反馈壅蔽",
        "将相授权专任",
        "功臣旧臣处置",
        "荐才链识人拔擢",
    } <= relations
    assert {"授权专任", "容谏纳言", "功臣旧臣处置", "识人拔擢"} <= categories
    assert any(row.get("outcome") == "adjacent_only" for row in rows)
    assert any(
        row.get("oeval_code") == "OE-B2-YG-AUTH-YSJ-001"
        and row.get("polarity") == "positive"
        for row in rows
    )


def test_experimental_b2_stores_keep_dual_keys_and_resolve_objects() -> None:
    object_rows = read_jsonl(EXPERIMENTAL_OBJECTS)
    oeval_rows = read_jsonl(EXPERIMENTAL_OEVALS)
    all_rows = object_rows + oeval_rows
    object_codes = assert_object_rows(object_rows)

    assert_dual_key_discipline(all_rows)
    assert_primary_codes_unique(all_rows)
    assert_object_evaluation_rows(oeval_rows, object_codes)
    assert_processing_rows(oeval_rows)
    assert not any(row.get("row_type") == "object" and row.get("outcome") == "adjacent_only" for row in object_rows)
    assert not any(str(row.get("label", "")).startswith("相邻项") for row in object_rows)


def test_experimental_b2_examples_cover_required_polarities() -> None:
    rows = read_jsonl(EXPERIMENTAL_OEVALS)

    assert any(
        row.get("oeval_code") == "OE-B2-YG-AUTH-YSJ-001"
        and row.get("obj_code") == "OBJ-B2-YG-YSJ"
        and row.get("relation") == "专典机密授权"
        and row.get("polarity") == "positive"
        for row in rows
    )
    assert any(
        row.get("oeval_code") == "OE-B2-YG-FDBK-BLOCK-001"
        and row.get("relation") == "反馈壅蔽"
        and row.get("polarity") == "negative"
        for row in rows
    )


def test_experimental_b3_tang_seed_rows_are_diagnostic_only() -> None:
    object_rows = read_jsonl(EXPERIMENTAL_OBJECTS)
    oeval_rows = read_jsonl(EXPERIMENTAL_OEVALS)
    b3_people = {"李隆基", "武则天", "李治", "李渊", "李纯"}
    b3_object_codes = {
        str(row["obj_code"])
        for row in object_rows
        if str(row.get("obj_code", "")).startswith("OBJ-B3-")
    }
    b3_object_labels = {
        str(row["label"])
        for row in object_rows
        if str(row.get("obj_code", "")).startswith("OBJ-B3-")
    }
    b3_oevals = [
        row
        for row in oeval_rows
        if str(row.get("oeval_code", "")).startswith("OE-B3-")
    ]
    b3_processing = [
        row
        for row in oeval_rows
        if row.get("row_type") == "processing_outcome"
        and str(row.get("residual", "")).endswith("adjacent-only lane；不创建 object row")
        and str(row.get("residual", "")).split(" adjacent-only", maxsplit=1)[0] in b3_people
    ]

    assert len(b3_object_codes) == 9
    assert b3_object_labels == {
        "姚崇",
        "李林甫",
        "李昭德",
        "酷吏罗织机制",
        "来济",
        "李义府",
        "刘文静",
        "裴度",
        "韩愈",
    }
    assert len(b3_oevals) == 10
    assert len(b3_processing) == 5
    assert {row["obj_code"] for row in b3_oevals} <= b3_object_codes
    assert {row["polarity"] for row in b3_oevals} == {"positive", "negative"}
    assert all(row["diagnostic_only"] is True for row in b3_oevals + b3_processing)
    assert all(row["feeds_formal_scoring"] is False for row in b3_oevals + b3_processing)
    assert not any("ADJACENT" in code for code in b3_object_codes)
    assert not any("相邻项剥离" in label for label in b3_object_labels)


def test_experimental_b4_song_seed_rows_align_with_legacy_anchors() -> None:
    object_rows = read_jsonl(EXPERIMENTAL_OBJECTS)
    oeval_rows = read_jsonl(EXPERIMENTAL_OEVALS)
    anchor_rows = read_jsonl(ANCHORS)
    b4_people = {"赵匡胤", "赵光义", "赵恒", "赵祯", "赵构"}
    expected_objects = {
        "OBJ-B4-ZKY-BJSBQ": ("杯酒释兵权", "event_case"),
        "OBJ-B4-ZKY-ZP": ("赵普", "person"),
        "OBJ-B4-ZGY-LD": ("吕端", "person"),
        "OBJ-B4-ZGY-LDX": ("卢多逊", "person"),
        "OBJ-B4-ZH-WD": ("王旦", "person"),
        "OBJ-B4-ZH-WQR": ("王钦若", "person"),
        "OBJ-B4-ZZ-BZ": ("包拯", "person"),
        "OBJ-B4-ZZ-FZY": ("范仲淹", "person"),
        "OBJ-B4-ZG-LG": ("李纲", "person"),
        "OBJ-B4-ZG-YF": ("岳飞", "person"),
    }
    b4_objects = {
        str(row["obj_code"]): row
        for row in object_rows
        if str(row.get("obj_code", "")).startswith("OBJ-B4-")
    }
    b4_oevals = [
        row
        for row in oeval_rows
        if str(row.get("oeval_code", "")).startswith("OE-B4-")
    ]
    b4_processing = [
        row
        for row in oeval_rows
        if row.get("row_type") == "processing_outcome"
        and str(row.get("residual", "")).endswith("adjacent-only lane；不创建 object row")
        and str(row.get("residual", "")).split(" adjacent-only", maxsplit=1)[0] in b4_people
    ]
    b4_anchor_objects = {
        str(row["object_name"]): str(row["object_class"])
        for row in anchor_rows
        if str(row.get("anchor_id", "")).startswith("ANCH-I5B-B4-")
    }

    assert set(b4_objects) == set(expected_objects)
    assert {
        str(row["label"]): str(row["class"])
        for row in b4_objects.values()
    } == {label: object_class for label, object_class in expected_objects.values()}
    assert b4_anchor_objects == {
        label: object_class for label, object_class in expected_objects.values()
    }
    assert len(b4_oevals) == 10
    assert len(b4_processing) == 5
    assert {row["obj_code"] for row in b4_oevals} == set(b4_objects)
    assert {row["polarity"] for row in b4_oevals} == {"positive", "negative"}
    assert all(row["diagnostic_only"] is True for row in b4_oevals + b4_processing)
    assert all(row["feeds_formal_scoring"] is False for row in b4_oevals + b4_processing)
    assert all(FORMAL_SCORING_FIELDS.isdisjoint(row) for row in b4_oevals + b4_processing)
    assert not any(str(row["label"]) == "相邻项剥离" for row in b4_objects.values())


def build_diagnostic_cluster_summaries(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for row in rows:
        if row.get("row_type") != "object_evaluation" or row.get("eligible") is not True:
            continue
        for cluster_id in row.get("clus_ids", []):
            summary = summaries.setdefault(
                str(cluster_id),
                {
                    "linked_oeval_ids": [],
                    "linked_oeval_codes": [],
                    "polarity": None,
                    "max_strength": 0,
                    "category_counts": {},
                    "category_core_count": 0,
                    "positive_total": 0,
                    "negative_total": 0,
                    "extreme_candidate": False,
                    "formula_trace": [],
                    "diagnostic_only": True,
                    "feeds_formal_scoring": False,
                },
            )
            oeval_id = row.get("oeval_id")
            if oeval_id is not None:
                summary["linked_oeval_ids"].append(oeval_id)
            summary["linked_oeval_codes"].append(row["oeval_code"])
            summary["max_strength"] = max(int(summary["max_strength"]), int(row["strength"]))
            category_counts = summary["category_counts"]
            assert isinstance(category_counts, dict)
            category_counts[row["category"]] = int(category_counts.get(row["category"], 0)) + 1
            if row["relevance"] == "core":
                summary["category_core_count"] = int(summary["category_core_count"]) + 1
            polarity = row["polarity"]
            if polarity == "positive":
                summary["positive_total"] = int(summary["positive_total"]) + 1
            else:
                summary["negative_total"] = int(summary["negative_total"]) + 1
            if summary["polarity"] is None:
                summary["polarity"] = polarity
            elif summary["polarity"] != polarity:
                summary["polarity"] = "mixed"
            summary["formula_trace"].append(
                f"{row['oeval_code']}:{row['polarity']}:{row['strength']}:{row['category']}"
            )

    for summary in summaries.values():
        same_direction_total = max(int(summary["positive_total"]), int(summary["negative_total"]))
        summary["extreme_candidate"] = int(summary["max_strength"]) >= 4 or same_direction_total >= 3
    return summaries


def test_experimental_b2_diagnostic_cluster_summary_is_report_only() -> None:
    summaries = build_diagnostic_cluster_summaries(read_jsonl(EXPERIMENTAL_OEVALS))

    required_keys = {
        "linked_oeval_ids",
        "polarity",
        "max_strength",
        "category_core_count",
        "positive_total",
        "negative_total",
        "extreme_candidate",
        "formula_trace",
    }
    assert required_keys <= summaries["ADJ-I5B-YANGGUANG-POS-ADMIN-AUTH-001"].keys()
    assert summaries["ADJ-I5B-YANGGUANG-POS-ADMIN-AUTH-001"]["polarity"] == "positive"
    assert summaries["ADJ-I5B-YANGGUANG-POS-ADMIN-AUTH-001"]["positive_total"] == 1
    assert summaries["ADJ-I5B-YANGGUANG-NEG-TALENT-FEEDBACK-SAFETY-001"]["polarity"] == "negative"
    assert summaries["ADJ-I5B-LIUQI-NEG-TALENT-SAFETY-001"]["negative_total"] == 2
    assert all(summary["diagnostic_only"] is True for summary in summaries.values())
    assert all(summary["feeds_formal_scoring"] is False for summary in summaries.values())


def test_experimental_b2_rows_do_not_introduce_formal_scoring_surface() -> None:
    rows = read_jsonl(EXPERIMENTAL_OBJECTS) + read_jsonl(EXPERIMENTAL_OEVALS)

    for row in rows:
        assert FORMAL_SCORING_FIELDS.isdisjoint(row)

    for path in [
        ROOT / "scripts" / "export" / "export_md.py",
        ROOT / "scripts" / "export" / "dimension_adapters" / "i5b_people_delegation" / "adapter.py",
    ]:
        content = path.read_text(encoding="utf-8")
        assert "data/experimental" not in content
        assert "object_evaluations.jsonl" not in content
