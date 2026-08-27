from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.profile_radar import AXIS_ORDER, COMPARISONS, SAMPLE_RULER_IDS, load_profiles, write_samples


ROOT = Path(__file__).resolve().parents[1]


def test_radar_loader_joins_all_eight_formal_axes_on_stable_ruler_id() -> None:
    profiles = load_profiles()
    assert len(profiles) == 184
    assert tuple(AXIS_ORDER) == ("M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5")
    assert all(len(profile.values) == 8 for profile in profiles.values())
    assert all(all(0 <= value <= 100 for value in profile.values) for profile in profiles.values())
    assert all(ruler_id in profiles for ruler_id in SAMPLE_RULER_IDS)
    assert all(left in profiles and right in profiles for left, right in COMPARISONS)


def test_radar_sample_write_preserves_source_values_and_editable_svg(tmp_path: Path) -> None:
    index = write_samples(tmp_path)
    profiles = load_profiles()
    assert index["population_count"] == 184
    assert index["scale"] == [0, 100]
    assert index["profile_total_enabled"] is False
    assert index["profile_ranking_enabled"] is False
    assert index["composite_ranking_write"] is False
    assert len(index["samples"]) == 8
    assert len(index["comparisons"]) == 3
    assert all(row["values"] == list(profiles[row["ruler_id"]].values) for row in index["samples"])
    written = {path.name for path in tmp_path.iterdir()}
    assert set(index["files"]) <= written
    svg = next(tmp_path.glob("single-*.svg")).read_text(encoding="utf-8")
    assert "<text" in svg
    assert "独立人物画像" in svg
    assert "不构成画像总分或排名" in svg
    assert all(path.stat().st_size > 10_000 for path in tmp_path.glob("*.png"))
    saved = json.loads((tmp_path / "00-雷达图小样索引.json").read_text(encoding="utf-8"))
    assert saved == index
