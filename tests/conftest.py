import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
PYTEST_TMP_ROOT = ROOT / ".tmp"

PYTEST_TMP_ROOT.mkdir(exist_ok=True)
os.environ.setdefault("TMP", str(PYTEST_TMP_ROOT))
os.environ.setdefault("TEMP", str(PYTEST_TMP_ROOT))
os.environ.setdefault("TMPDIR", str(PYTEST_TMP_ROOT))
tempfile.tempdir = str(PYTEST_TMP_ROOT)


def write_project_config(
    path: Path,
    *,
    active_subitem: str = "第五项B",
    groups: dict[str, dict[str, object]] | None = None,
    default_person_group: str | None = None,
    defaults: dict[str, str] | None = None,
    outputs: dict[str, object] | None = None,
    view_groups: list[dict[str, object]] | None = None,
    candidate_pool: list[dict[str, object]] | None = None,
    review_warning_rules: list[dict[str, object]] | None = None,
) -> Path:
    _ = (candidate_pool, defaults, review_warning_rules)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_groups = groups if groups is not None else _project_groups_from_view_groups(view_groups)
    resolved_default_group = default_person_group or _default_person_group_from_view_groups(view_groups)
    resolved_outputs = outputs or {
        "matrix": True,
        "auto_adjudication": True,
        "review_entry": True,
        "subitem_details": True,
        "net_evidence": True,
        "evidence_indexes": True,
    }
    payload = {
        "version": 2,
        "active_subitem": active_subitem,
        "default_person_group": resolved_default_group,
        "person_groups": resolved_groups,
        "outputs": resolved_outputs,
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) + "\n", encoding="utf-8")
    return path


def _project_groups_from_view_groups(view_groups: list[dict[str, object]] | None) -> dict[str, dict[str, object]]:
    default_groups: dict[str, dict[str, object]] = {
        "three_pilot": {"label": "三人试点", "persons": ["李世民", "刘秀", "刘庄"]},
        "expanded_batch1": {"label": "扩展第一批", "persons": ["刘邦", "雍正", "朱元璋"]},
    }
    if view_groups is None:
        return default_groups

    groups: dict[str, dict[str, object]] = {}
    for row in view_groups:
        group_key = str(row.get("group_id"))
        group: dict[str, object] = {"label": row.get("group_name") or row.get("label") or group_key}
        if "persons" in row:
            group["persons"] = row["persons"]
        elif "persons_ref" in row:
            group["persons_ref"] = row["persons_ref"]
        else:
            group["persons"] = []
        groups[group_key] = group
    return {**default_groups, **groups}


def _default_person_group_from_view_groups(view_groups: list[dict[str, object]] | None) -> str:
    if not view_groups:
        return "expanded_batch1"
    first_group_id = str(view_groups[0].get("group_id"))
    return first_group_id


@pytest.fixture
def project_config_writer():
    return write_project_config


def pytest_sessionfinish(session, exitstatus) -> None:
    for path in [
        ROOT / "evidence_cache.sqlite",
        ROOT / ".pytest_cache",
        ROOT / "scripts" / "__pycache__",
        ROOT / "tests" / "__pycache__",
        PYTEST_TMP_ROOT,
    ]:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
