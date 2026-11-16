"""Find C3 process text that adds to the authored evidence cards."""
from __future__ import annotations

from typing import Any


def additional_process_start(parent: dict[str, Any]) -> int:
    """Skip only complete leading evidence entries repeated in the same order."""
    narrative = parent.get("lifecycle_narrative") or ""
    start = len(narrative) - len(narrative.lstrip())
    for entry in parent.get("evidence_detail") or []:
        text = entry.strip().rstrip("。；")
        if not text or not narrative.startswith(text, start):
            break
        end = start + len(text)
        if end < len(narrative) and narrative[end] not in "。；\n":
            break
        start = end
        while start < len(narrative) and (narrative[start] in "。；" or narrative[start].isspace()):
            start += 1
    return start


def counter_repeated_in_grade(counter: str, grade_basis: str) -> bool:
    """Recognize an exact final counterexample, including one introduced by 但."""
    counter, grade_basis = counter.strip(), grade_basis.strip()
    if not counter or not grade_basis.endswith(counter):
        return False
    prefix = grade_basis.removesuffix(counter).rstrip()
    return not prefix or prefix.removesuffix("但").rstrip().endswith(("。", "！", "？", "；"))
