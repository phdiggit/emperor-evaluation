from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
REAL_OUTPUT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "自动结算草案"
    / "第五项B三人试点正负证矩阵.md"
)
SEARCH_LOGS_PATH = ROOT / "data" / "search_logs.jsonl"


def copy_script(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def build_temp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    copy_script(SCRIPTS_DIR / "run_matrix.py", repo / "scripts" / "run_matrix.py")
    copy_script(SCRIPTS_DIR / "matrix" / "__init__.py", repo / "scripts" / "matrix" / "__init__.py")
    copy_script(SCRIPTS_DIR / "matrix" / "run_matrix.py", repo / "scripts" / "matrix" / "run_matrix.py")
    copy_script(SCRIPTS_DIR / "shared" / "__init__.py", repo / "scripts" / "shared" / "__init__.py")
    copy_script(SCRIPTS_DIR / "shared" / "config_loaders.py", repo / "scripts" / "shared" / "config_loaders.py")
    copy_script(
        SCRIPTS_DIR / "shared" / "i5b_markdown_display.py",
        repo / "scripts" / "shared" / "i5b_markdown_display.py",
    )

    write_jsonl(
        repo / "data" / "trigger_terms.jsonl",
        [
            {
                "term_id": "TERM-001",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "识人拔擢",
                "tier": "core",
                "term": "纳谏",
            },
            {
                "term_id": "TERM-002",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "negative",
                "trigger_family": "廷杖刑辱",
                "tier": "core",
                "term": "廷杖",
            },
        ],
    )
    write_json(
        repo / "data" / "configs" / "视图配置" / "第五项B_视图分组.json",
        [
            {
                "group_id": "第五项B_三人试点",
                "group_name": "三人试点",
                "group_type": "试点人物组",
                "subitem": "第五项B",
                "persons": ["李世民", "刘秀", "刘庄"],
                "note": "测试",
            }
        ],
    )
    write_json(
        repo / "data" / "configs" / "导出展示配置" / "第五项B_markdown_view.json",
        {
            "keep_machine_field_name": True,
            "value_labels": {
                "positive": "正向",
                "negative": "负向",
            },
        },
    )
    return repo


def run_matrix_cli(repo: Path, script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_new_and_legacy_cli_generate_matrix_only_in_temp_repo(tmp_path: Path) -> None:
    before_search_logs = SEARCH_LOGS_PATH.read_text(encoding="utf-8")
    before_exists = REAL_OUTPUT_PATH.exists()
    before_mtime = REAL_OUTPUT_PATH.stat().st_mtime_ns if before_exists else None
    repo = build_temp_repo(tmp_path)

    new_result = run_matrix_cli(repo, repo / "scripts" / "matrix" / "run_matrix.py")
    output_path = (
        repo
        / "exports"
        / "markdown_views"
        / "第五项B"
        / "人工审核"
        / "自动裁判链"
        / "自动结算草案"
        / "第五项B三人试点正负证矩阵.md"
    )
    first_content = output_path.read_text(encoding="utf-8")
    output_path.unlink()
    legacy_result = run_matrix_cli(repo, repo / "scripts" / "run_matrix.py")
    second_content = output_path.read_text(encoding="utf-8")

    assert new_result.returncode == 0, new_result.stdout + new_result.stderr
    assert legacy_result.returncode == 0, legacy_result.stdout + legacy_result.stderr
    assert new_result.stdout.strip() == f"exported {output_path}"
    assert legacy_result.stdout.strip() == f"exported {output_path}"
    assert first_content == second_content
    assert "李世民" in second_content
    assert "刘秀" in second_content
    assert "刘庄" in second_content
    assert "正向" in second_content
    assert "负向" in second_content
    assert "识人拔擢" in second_content
    assert "廷杖刑辱" in second_content
    assert "分数" not in second_content
    assert "总榜" not in second_content
    assert "排名" not in second_content

    assert SEARCH_LOGS_PATH.read_text(encoding="utf-8") == before_search_logs
    assert REAL_OUTPUT_PATH.exists() is before_exists
    if before_exists:
        assert REAL_OUTPUT_PATH.stat().st_mtime_ns == before_mtime
    assert not (repo / "data" / "search_logs.jsonl").exists()
    assert not (repo / "data" / "evidence_cards.jsonl").exists()
    assert not (repo / "evidence_cache.sqlite").exists()
