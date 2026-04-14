from tenforty.rounding import irs_round


def test_below_half_rounds_down():
    assert irs_round(20.49) == 20
    assert irs_round(20.01) == 20


def test_half_rounds_up():
    assert irs_round(20.50) == 21
    assert irs_round(21.50) == 22
    assert irs_round(0.5) == 1
    assert irs_round(1.5) == 2


def test_above_half_rounds_up():
    assert irs_round(20.99) == 21
    assert irs_round(20.51) == 21


def test_whole_numbers_pass_through():
    assert irs_round(20) == 20
    assert irs_round(0) == 0


def test_negative_half_rounds_away_from_zero():
    # IRS rule for negatives is uncommon (1040 amounts are usually non-negative),
    # but keep "half away from zero" symmetry so callers can rely on it.
    assert irs_round(-20.5) == -21
    assert irs_round(-20.49) == -20


def test_accepts_int_input():
    assert irs_round(15000) == 15000
