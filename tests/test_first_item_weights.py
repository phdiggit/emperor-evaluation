import pytest

from emperor_v4.evaluation.first_item_weights import (
    A_MAX, B1_MAX, B2_MAX, C_MAX, C_POINTS,
    personal_unification_points, unification_pool,
)


def test_contract_weights_and_grade_bounds():
    assert A_MAX + B1_MAX + B2_MAX + C_MAX == 240
    assert min(C_POINTS.values()) == 0
    assert max(C_POINTS.values()) == C_MAX
    assert list(C_POINTS.values()) == sorted(C_POINTS.values())


def test_shared_project_is_split_after_single_nonlinear_pool():
    pool = unification_pool(200)
    assert personal_unification_points(200, .5) * 2 == pytest.approx(pool, abs=.1)
    assert personal_unification_points(200, .5) < unification_pool(100)
    assert unification_pool(2000) == A_MAX
    assert personal_unification_points(0) == 0
    with pytest.raises(ValueError):
        personal_unification_points(200, 1.1)
