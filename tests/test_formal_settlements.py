from pathlib import Path

from emperor_v4.evaluation.formal_settlements import verify_formal_settlements


def test_all_five_formal_settlements_are_coherent() -> None:
    report = verify_formal_settlements(Path("."))
    assert report["status"] == "PASS"
    assert set(report["items"]) == {
        "first_item",
        "second_item",
        "third_item",
        "fourth_item",
        "fifth_item",
    }
    assert all(item["record_count"] > 0 for item in report["items"].values())
