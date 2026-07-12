from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_runtime_paths as tool


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "active_root_smb": str(path.parent / "active"),
                "archive_root_smb": str(path.parent / "archive"),
                "retrieval_v3_clean_runs": str(path.parent / "active" / "clean_runs"),
                "retrieval_v3_consumption": str(path.parent / "active" / "consumption"),
                "source_cache": str(path.parent / "active" / "source_cache"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_load_runtime_paths_from_config(tmp_path: Path) -> None:
    config = tmp_path / "runtime_paths.json"
    write_config(config)

    paths = tool.load_runtime_paths(config_path=config)

    assert paths["uses_runtime_config"] is True
    assert paths["retrieval_v3_clean_runs"] == tmp_path / "active" / "clean_runs"
    assert paths["retrieval_v3_consumption"] == tmp_path / "active" / "consumption"
    assert tool.default_run_root("personnel political/朱元璋", paths).name == "personnel_political"
    assert tool.default_source_cache_root(paths) == tmp_path / "active" / "source_cache"


def test_load_runtime_paths_can_force_local_fallback() -> None:
    paths = tool.load_runtime_paths(use_local=True)

    assert paths["uses_runtime_config"] is False
    assert paths["retrieval_v3_clean_runs"] == tool.ROOT / "tmp" / "retrieval_v3_clean_runs"
    assert paths["source_cache"] == tool.ROOT / "tmp" / "retrieval_v3_source_cache"


def test_explicit_missing_config_is_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    try:
        tool.load_runtime_paths(config_path=missing)
    except tool.RuntimePathError as exc:
        assert "does not exist" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing explicit config should fail")


def test_report_payload_contains_standard_run_paths(tmp_path: Path) -> None:
    config = tmp_path / "runtime_paths.json"
    write_config(config)
    paths = tool.load_runtime_paths(config_path=config)

    payload = tool.report_payload("liubang-shadow", paths)

    assert payload["uses_runtime_config"] is True
    assert Path(str(payload["run_root"])) == tmp_path / "active" / "clean_runs" / "liubang-shadow"
    assert Path(str(payload["output_root"])) == tmp_path / "active" / "consumption" / "liubang-shadow"
    assert Path(str(payload["source_cache_root"])) == tmp_path / "active" / "source_cache"
