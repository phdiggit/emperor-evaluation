from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.presentation

from emperor_v4.evaluation.profile_radar import AXIS_ORDER, load_profiles, write_samples


ROOT = Path(__file__).resolve().parents[1]


def test_radar_loader_consumes_all_eight_formal_axes() -> None:
    profiles = load_profiles()
    assert profiles
    assert all(len(profile.values) == len(AXIS_ORDER) for profile in profiles.values())


def test_radar_sample_write_refreshes_formal_m3_values(tmp_path: Path) -> None:
    report = write_samples(tmp_path)
    assert report["samples"]
    assert (tmp_path / "00-雷达图小样索引.json").exists()
