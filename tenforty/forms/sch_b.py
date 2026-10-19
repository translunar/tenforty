"""Schedule B — Interest and Ordinary Dividends.

Native-Python compute: sums 1099-INT and 1099-DIV entries from the
scenario and returns PDF-ready result keys.

v1 scope: Parts I and II only. Part III (Foreign Accounts and Trusts)
is gated at scenario load via ``TaxReturnConfig.has_foreign_accounts``
— scenarios with ``True`` fail load with
``NotImplementedError``, so any scenario reaching this compute has
attested ``False``. Part III / FinCEN 114 (FBAR) support is tracked as
a follow-up.

Overflow of the paper's row caps (14 interest rows; 16 dividend rows in
2021, 15 from 2022) raises immediately
(the PDF cannot physically represent more rows on one page, and
multi-page Sch B emission is deferred). The row caps are sourced from
the mapping module so they stay in sync with the PDF geometry.
"""

from tenforty.mappings.pdf_sch_b import dividend_max_rows, interest_max_rows
from tenforty.models import K1FanoutData, Scenario
from tenforty.rounding import irs_round


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    interest_payers = [
        {"payer": e.payer, "amount": irs_round(e.interest)}
        for e in scenario.form1099_int
    ]
    dividend_payers = [
        {"payer": e.payer, "amount": irs_round(e.ordinary_dividends)}
        for e in scenario.form1099_div
    ]

    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()
    for pa in fanout.sch_b_interest_additions:
        interest_payers.append({"payer": pa.payer, "amount": irs_round(pa.amount)})
    for pa in fanout.sch_b_dividend_additions:
        dividend_payers.append({"payer": pa.payer, "amount": irs_round(pa.amount)})

    year = scenario.config.year
    interest_rows = interest_max_rows(year)
    dividend_rows = dividend_max_rows(year)
    if len(interest_payers) > interest_rows:
        raise NotImplementedError(
            f"Schedule B has {len(interest_payers)} 1099-INT payers; the "
            f"{year} PDF holds {interest_rows} rows per page and multi-page "
            "Sch B emission is not supported in tenforty v1."
        )
    if len(dividend_payers) > dividend_rows:
        raise NotImplementedError(
            f"Schedule B has {len(dividend_payers)} 1099-DIV payers; the "
            f"{year} PDF holds {dividend_rows} rows per page and multi-page "
            "Sch B emission is not supported in tenforty v1."
        )

    total_interest = sum(p["amount"] for p in interest_payers)
    total_dividends = sum(p["amount"] for p in dividend_payers)

    return {
        **scenario.config.pdf_header(),
        "interest_payers": interest_payers,
        "total_interest": total_interest,
        "excludable_savings_bond": 0,
        "taxable_interest": total_interest,
        "dividend_payers": dividend_payers,
        "total_ordinary_dividends": total_dividends,
    }


