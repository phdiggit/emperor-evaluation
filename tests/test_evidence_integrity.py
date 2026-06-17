import subprocess
import sys
from pathlib import Path
from typing import Any
import importlib.util

import pytest


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"

VALIDATE_EVIDENCE_SPEC = importlib.util.spec_from_file_location(
    "validate_evidence",
    ROOT / "scripts" / "validate_evidence.py",
)
assert VALIDATE_EVIDENCE_SPEC is not None
validate_evidence = importlib.util.module_from_spec(VALIDATE_EVIDENCE_SPEC)
assert VALIDATE_EVIDENCE_SPEC.loader is not None
VALIDATE_EVIDENCE_SPEC.loader.exec_module(validate_evidence)


def test_validate_evidence_allows_empty_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_evidence.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validation passed." in result.stdout


def test_build_db_allows_empty_data() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_db.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert DB_PATH.exists()


def test_export_md_generates_evidence_index() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_md.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert EXPORT_PATH.exists()
    content = EXPORT_PATH.read_text(encoding="utf-8")
    assert "| evidence_id | person | subitem | human_level | source_id | quote_short | verification_status |" in content


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    import json

    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.fixture()
def validation_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ["evidence_cards", "sources", "events", "trigger_terms", "search_logs"]:
        (data_dir / f"{name}.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(validate_evidence, "DATA_DIR", data_dir)
    monkeypatch.setattr(
        validate_evidence,
        "JSONL_FILES",
        [
            data_dir / "evidence_cards.jsonl",
            data_dir / "sources.jsonl",
            data_dir / "events.jsonl",
            data_dir / "trigger_terms.jsonl",
            data_dir / "search_logs.jsonl",
        ],
    )
    return data_dir


def test_validate_empty_data_with_temp_dir(validation_data_dir: Path) -> None:
    assert validate_evidence.validate() == []


def test_trigger_terms_invalid_tier_fails(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "trigger_terms.jsonl",
        [
            {
                "term_id": "TRG-I5B-POS-TEST-001",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "测试",
                "term": "测试词",
                "tier": "middle",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("tier must be core or extended" in error for error in errors)


def test_trigger_terms_duplicate_term_id_fails(validation_data_dir: Path) -> None:
    row = {
        "term_id": "TRG-I5B-POS-TEST-001",
        "item": "第五项",
        "subitem": "第五项B",
        "polarity": "positive",
        "trigger_family": "测试",
        "term": "测试词",
        "tier": "core",
        "note": "",
    }
    write_jsonl(validation_data_dir / "trigger_terms.jsonl", [row, {**row, "term": "测试词二"}])

    errors = validate_evidence.validate()

    assert any("duplicate term_id: TRG-I5B-POS-TEST-001" in error for error in errors)


def test_strength_four_positive_requires_extreme_positive(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VOL-001",
                "title": "测试来源",
                "author": "",
                "dynasty": "",
                "volume": "",
                "location": "",
                "url": "",
                "note": "",
            }
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-I5B-TEST-POS-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "strength": 4,
                "human_level": "强正",
                "source_id": "SRC-TEST-VOL-001",
                "quote_short": "测试短引",
                "interpretation": "测试解释",
                "trigger_family": "测试",
                "trigger_terms": ["测试词"],
                "cross_item_split": "",
                "scoring_effect": "",
                "verification_status": "verified",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("requires human_level=极正" in error for error in errors)


def test_strength_four_negative_requires_extreme_negative(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VOL-001",
                "title": "测试来源",
                "author": "",
                "dynasty": "",
                "volume": "",
                "location": "",
                "url": "",
                "note": "",
            }
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-I5B-TEST-NEG-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "negative",
                "strength": 4,
                "human_level": "强负",
                "source_id": "SRC-TEST-VOL-001",
                "quote_short": "测试短引",
                "interpretation": "测试解释",
                "trigger_family": "测试",
                "trigger_terms": ["测试词"],
                "cross_item_split": "测试切分",
                "scoring_effect": "",
                "verification_status": "verified",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("requires human_level=极负" in error for error in errors)
