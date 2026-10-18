"""First-item A public prose is formal, complete, and projected at build time."""

import json
from pathlib import Path
import pytest

from emperor_v4.evaluation.first_item_public_outcomes import (
    PUBLIC_FIELDS,
    PUBLIC_READING_FIELDS,
    PUBLIC_RECORD_FIELDS,
    PUBLIC_OUTCOME_SCHEMA,
    PUBLIC_OUTCOME_PATH,
    SOURCE_MARKDOWN_PATH,
    _parse_source_sections,
    load_first_item_public_outcomes,
    public_outcome_for_name,
)
from reader.validate_first_item_docs import parse_people


ROOT = Path(__file__).resolve().parents[1]
A_SOURCE = ROOT / "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项A统一主链客观贡献正式结算.md"


def test_formal_a_public_outcomes_cover_the_current_a_source():
    source_names = set(parse_people(A_SOURCE))
    outcomes = load_first_item_public_outcomes(ROOT)

    assert set(outcomes) == source_names
    assert all(set(PUBLIC_FIELDS) <= set(record) for record in outcomes.values())
    assert all(
        isinstance(record["public_share_percent"], (int, float))
        and 0 <= record["public_share_percent"] <= 100
        for record in outcomes.values()
    )
    assert all(
        all(isinstance(record[field], str) and record[field].strip() for field in PUBLIC_FIELDS if field != "public_boundary")
        for record in outcomes.values()
    )
    assert all(
        record["public_boundary"] is None
        or isinstance(record["public_boundary"], str) and record["public_boundary"].strip()
        for record in outcomes.values()
    )


def test_reader_first_item_sources_no_longer_contain_known_person_specific_outcome_rewrites():
    source = (ROOT / "reader/first-item-reading.js").read_text(encoding="utf-8")
    for phrase in (
        "从女真整合到1683核心统一一次结算",
        "郭威取得中原核心、柴荣续接淮南及北方阶段成果",
        "李克用前置基盘、李存勖灭梁主体、李嗣源独立方面贡献",
        "总池封顶100；仅计元统一主链直接继承成果",
    ):
        assert phrase not in source
    assert "firstAReadingMarkup(item, record)" in source


def test_generated_person_detail_contains_formal_public_outcome():
    outcomes = load_first_item_public_outcomes(ROOT)
    candidates = []
    for person_path in (ROOT / "reader/data/people").glob("*.json"):
        record = json.loads(person_path.read_text(encoding="utf-8"))["record"]
        for item in (record.get("net") or {}).get("component_details", {}).get("first", []):
            if item.get("label") == "A统一贡献" and "reader_public_outcome" in item:
                candidates.append((record["ruler_name"], item))

    assert candidates
    for name, item in candidates:
        assert item["reader_public_outcome"] == public_outcome_for_name(outcomes, name)


def test_public_calculation_and_scale_are_projected_from_current_authorities():
    payload = json.loads((ROOT / PUBLIC_OUTCOME_PATH).read_text(encoding="utf-8"))
    sections = _parse_source_sections(ROOT / SOURCE_MARKDOWN_PATH)
    outcomes = load_first_item_public_outcomes(ROOT)
    for name, outcome in outcomes.items():
        for field, text in payload["reading_guide"].items():
            assert outcome[field] == text
        assert outcome["public_calculation"] == sections[name]["计算"]
    for person_path in (ROOT / "reader/data/people").glob("*.json"):
        record = json.loads(person_path.read_text(encoding="utf-8"))["record"]
        for item in (record.get("net") or {}).get("component_details", {}).get("first", []):
            if item.get("label") == "A统一贡献" and item.get("value") is not None:
                outcome = public_outcome_for_name(outcomes, record["ruler_name"])
                assert item["reader_how"] == (
                    outcome["public_calculation_basis"]
                    + "\n本人的正式计算：" + outcome["public_calculation"]
                )


def test_every_formal_person_has_an_individual_upstream_reading_entry():
    outcomes = load_first_item_public_outcomes(ROOT)
    payload = json.loads((ROOT / PUBLIC_OUTCOME_PATH).read_text(encoding="utf-8"))
    records = {record["ruler_name"]: record for record in payload["records"]}
    for field in PUBLIC_READING_FIELDS:
        assert len({outcome[field] for outcome in outcomes.values()}) == len(outcomes)
        for name, outcome in outcomes.items():
            assert outcome[field] == records[name][field]


def test_all_formal_a_people_are_published_without_requiring_a_total_score():
    from html.parser import HTMLParser

    class Entries(HTMLParser):
        def __init__(self):
            super().__init__()
            self.people = {}
            self.current = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "article" and "first-a-reading" in attrs.get("class", ""):
                self.current = attrs["id"]
                self.people[self.current] = []

        def handle_endtag(self, tag):
            if tag == "article":
                self.current = None

        def handle_data(self, text):
            if self.current:
                self.people[self.current].append(text)

    parser = Entries()
    parser.feed((ROOT / "reader/first-item-a.html").read_text(encoding="utf-8"))
    outcomes = load_first_item_public_outcomes(ROOT)
    assert set(parser.people) == set(outcomes)
    for name, chunks in parser.people.items():
        text = "".join(chunks)
        for field in PUBLIC_READING_FIELDS:
            assert outcomes[name][field] in text


@pytest.mark.parametrize("missing_field", PUBLIC_READING_FIELDS)
def test_missing_upstream_reading_entry_is_rejected(tmp_path, missing_field):
    source = tmp_path / SOURCE_MARKDOWN_PATH
    source.parent.mkdir(parents=True)
    source.write_text(
        "### 1. 合成对象\n- **取得/恢复成果**：有效控制信用为100。\n- **计算**：合成公式用于测试投影。\n",
        encoding="utf-8",
    )
    record = {field: "合成公开说明保留完整含义。" for field in (*PUBLIC_FIELDS, *PUBLIC_READING_FIELDS)}
    record.update(ruler_name="合成对象", public_project=None)
    del record[missing_field]
    payload = {
        "schema_version": PUBLIC_OUTCOME_SCHEMA,
        "source_markdown": SOURCE_MARKDOWN_PATH.as_posix(),
        "record_count": 1,
        "fields": list(PUBLIC_RECORD_FIELDS),
        "reading_guide": {"public_scale_basis": "合成尺度", "public_calculation_basis": "合成计算"},
        "records": [record],
    }
    (tmp_path / PUBLIC_OUTCOME_PATH).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match=missing_field):
        load_first_item_public_outcomes(tmp_path)
