from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.profile_radar import AXIS_ORDER, load_profiles
from emperor_v4.evaluation.profile_video_copy import SAMPLE_RULER_IDS, write_samples


def test_video_copy_cards_are_verbatim_formal_excerpts_with_matching_radar_values(tmp_path: Path) -> None:
    payload = write_samples(tmp_path)
    profiles = load_profiles()
    assert payload["axis_order"] == list(AXIS_ORDER)
    assert payload["editorial_policy"] == "DRAFT_SUMMARIES_BOUND_TO_FORMAL_TASK_CODES_REQUIRES_HUMAN_APPROVAL"
    assert all(payload[key] is False for key in ("profile_total_enabled", "profile_ranking_enabled", "composite_ranking_write"))
    assert [person["ruler_id"] for person in payload["people"]] == list(SAMPLE_RULER_IDS)
    for person in payload["people"]:
        cards = person["axis_cards"]
        assert tuple(cards) == AXIS_ORDER
        assert [card["radar_value"] for card in cards.values()] == list(profiles[person["ruler_id"]].values)
        assert all(card["editorial_status"] == "DRAFT_REQUIRES_HUMAN_APPROVAL" for card in cards.values())
        assert all(card["main_basis"] and card["counterevidence"] for card in cards.values())
        assert all(isinstance(card["counterevidence"], str) for card in cards.values())
        assert all(25 <= len(card["display_summary"]) <= 80 for card in cards.values())
        assert all("；" in card["display_summary"] for card in cards.values())
        forbidden = ("不以", "不因", "不按", "不构成", "限制上限", "与将领分归")
        assert all(not any(term in card["display_summary"] for term in forbidden) for card in cards.values())
        assert all(card["score_alignment"]["range"][0] <= card["radar_value"] <= card["score_alignment"]["range"][1] for card in cards.values())
        assert all(card["score_alignment"]["requirement"] for card in cards.values())
    saved = json.loads((tmp_path / "00-视频人物画像文字小样.json").read_text(encoding="utf-8"))
    assert saved == payload
    markdown = (tmp_path / "00-视频人物画像文字小样.md").read_text(encoding="utf-8")
    assert "## 能力与治理画像" in markdown and "## 决策与用人画像" in markdown
    assert "画像总分" in markdown and "轴内排名" in markdown
