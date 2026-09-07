"""First-item contract weights and grade projections; no historical adjudication."""
from decimal import Decimal, ROUND_HALF_UP

A_MAX = 120
B1_MAX = 50
B2_MAX = 30
C_MAX = 40
C_POINTS = {
    "C-0": 0.0,
    "C-1-LOW": 4.0, "C-1-MID": 7.0, "C-1-HIGH": 10.0,
    "C-2-LOW": 12.0, "C-2-MID": 15.0, "C-2-HIGH": 18.0,
    "C-3-LOW": 20.0, "C-3-MID": 23.0, "C-3-HIGH": 26.0,
    "C-4-LOW": 28.0, "C-4-MID": 31.0, "C-4-HIGH": 34.0,
    "C-5-LOW": 36.0, "C-5-MID": 38.0, "C-5-HIGH": 40.0,
}


def round_points(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def unification_pool(control_credit: float) -> float:
    if control_credit < 0:
        raise ValueError("Control credit must be nonnegative")
    return round_points(A_MAX * (min(1000, control_credit) / 1000) ** 0.65)


def personal_unification_points(control_credit: float, share: float = 1.0) -> float:
    if not 0 <= share <= 1:
        raise ValueError("Personal share must be between zero and one")
    return round_points(unification_pool(control_credit) * share)
