from __future__ import annotations

import json

from emperor_v4.adapters import shidian


def _payload(*, chapters=None, text: str | None = None):
    book = {}
    if chapters is not None:
        book["bookInfo"] = {"catalog": {"chapters": chapters}}
    if text is not None:
        book["paragraphList"] = [
            {
                "content": json.dumps(
                    {"lines": [{"content": text}]},
                    ensure_ascii=False,
                )
            }
        ]
    return {"loaderData": {"__session/(lang$)/book/$": book}}


def test_shidian_catalog_and_split_volume_are_fixed_as_one_page(monkeypatch) -> None:
    chapters = [
        {
            "chapterId": "one",
            "chapterName": [{"content": "大明太祖高皇帝實錄卷之一"}],
            "volumeVersion": 3,
        },
        {
            "chapterId": "two-a",
            "chapterName": [{"content": "大明太祖高皇帝實錄卷之二上"}],
            "volumeVersion": 4,
        },
        {
            "chapterId": "two-b",
            "chapterName": [{"content": "大明太祖高皇帝實錄卷之二下"}],
            "volumeVersion": 5,
        },
    ]
    payloads = {
        "catalog": _payload(chapters=chapters),
        "chapter/one": _payload(text="甲" * 60),
        "chapter/two-a": _payload(text="乙" * 60),
        "chapter/two-b": _payload(text="丙" * 60),
    }
    monkeypatch.setattr(
        shidian,
        "_fetch_router_data",
        lambda url, **_: payloads[url],
    )
    inventory = shidian.discover_shidian_chapters(
        catalog_url="catalog",
        work_title="大明太祖高皇帝實錄",
        chapter_name_contains="高皇帝實錄卷",
        first_volume=1,
        last_volume=2,
    )
    assert list(inventory) == [
        "大明太祖高皇帝實錄/卷001",
        "大明太祖高皇帝實錄/卷002",
    ]
    assert len(inventory["大明太祖高皇帝實錄/卷002"]["chapters"]) == 2

    snapshots = shidian.fetch_shidian_plaintext_batch(
        page_titles=list(inventory),
        page_metadata=inventory,
        book_id="LS0026",
        chapter_url_format="chapter/{chapter_id}",
    )
    assert snapshots["大明太祖高皇帝實錄/卷002"]["raw_text"] == (
        "乙" * 60 + "\n" + "丙" * 60
    )
    assert "two-a:v4+two-b:v5" in snapshots[
        "大明太祖高皇帝實錄/卷002"
    ]["revision_ref"]
