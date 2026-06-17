import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"


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
