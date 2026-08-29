from __future__ import annotations

from emperor_v4.evaluation.profile_m3_livelihood_settlement import *  # noqa: F403
from emperor_v4.evaluation.profile_m3_livelihood_settlement import M3_SETTLEMENT, _load, run


def build(*, write: bool = False):
    if write:
        run()
    return {"settlement": _load(M3_SETTLEMENT)}


if __name__ == "__main__":
    run()
