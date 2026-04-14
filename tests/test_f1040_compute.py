from tenforty.forms.f1040 import compute


def test_f1040_compute_renames_engine_keys_to_pdf_keys():
    raw = {
        "interest_income": 100,
        "dividend_income": 200,
        "schd_line16": 300,
        "sche_line26": 400,
        "federal_withheld": 1000,
        "additional_medicare_withheld": 50,
        "agi": 75000,
    }
    result = compute(raw_1040=raw, upstream={})
    assert result["taxable_interest"] == 100
    assert result["ordinary_dividends"] == 200
    assert result["capital_gain_loss"] == 300
    assert result["other_income"] == 400
    assert result["federal_withheld_w2"] == 1000
    assert result["federal_withheld_other"] == 50
    assert result["agi"] == 75000
    assert result["agi_page2"] == 75000


def test_f1040_compute_sums_line_25d():
    raw = {
        "federal_withheld": 1000,
        "additional_medicare_withheld": 50,
        "federal_withheld_1099": 25,
    }
    result = compute(raw_1040=raw, upstream={})
    assert result["federal_withheld"] == 1000 + 25 + 50


def test_f1040_compute_missing_agi_omits_page2():
    result = compute(raw_1040={"federal_withheld": 0}, upstream={})
    assert "agi_page2" not in result
