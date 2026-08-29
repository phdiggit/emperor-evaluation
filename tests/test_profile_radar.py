from __future__ import annotations

from pathlib import Path

from emperor_v4.evaluation.profile_radar import load_profiles, write_samples


ROOT = Path(__file__).resolve().parents[1]


def test_radar_loader_consumes_all_eight_formal_axes() -> None:
    profiles = load_profiles()
    assert len(profiles) == 184
    assert profiles["RULER-TANG-LISHIMIN"].values[2] == 94
    assert profiles["RULER-TANG-LIZHI"].values[2] == 18


def test_radar_sample_write_refreshes_formal_m3_values(tmp_path: Path) -> None:
    report = write_samples(tmp_path)
    assert report["samples"]
    assert (tmp_path / "00-雷达图小样索引.json").exists()
