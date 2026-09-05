from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.presentation

from PIL import Image

from emperor_v4.evaluation.profile_radar import AXIS_ORDER, load_profiles
from emperor_v4.evaluation.profile_video_card import SAMPLE_RULER_IDS, write_samples


def test_video_card_samples_are_16_by_9_and_preserve_formal_values(tmp_path: Path) -> None:
    index = write_samples(tmp_path)
    profiles = load_profiles()
    assert index["canvas"] == {"width": 1920, "height": 1080, "aspect_ratio": "16:9"}
    assert index["portrait_status"] == "LOCAL_PUBLIC_DOMAIN_ASSETS"
    assert index["editorial_status"] == "DRAFT_REQUIRES_HUMAN_APPROVAL"
    assert index["axis_order"] == list(AXIS_ORDER)
    assert index["profile_total_enabled"] is False
    assert index["profile_ranking_enabled"] is False
    assert index["composite_ranking_write"] is False
    assert [row["ruler_id"] for row in index["cards"]] == list(SAMPLE_RULER_IDS)
    assert all(row["values"] == list(profiles[row["ruler_id"]].values) for row in index["cards"])
    for ruler_id in SAMPLE_RULER_IDS:
        image = Image.open(tmp_path / f"{ruler_id}-人物卡.png")
        assert image.size == (1920, 1080)
        svg = (tmp_path / f"{ruler_id}-人物卡.svg").read_text(encoding="utf-8")
        card = next(card for card in index["cards"] if card["ruler_id"] == ruler_id)
        assert card["editorial"]["citation"] in svg
        assert card["portrait"]["license"] == "PUBLIC_DOMAIN_PD_ART"
        assert 10 <= len(card["editorial"]["summary"]) <= 60
        assert card["editorial"]["context_sources"]
    saved = json.loads((tmp_path / "00-视频人物卡小样索引.json").read_text(encoding="utf-8"))
    assert saved == index
