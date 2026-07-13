"""Air-gapped attestation of CA S-corp (Form 100S) params, tax year 2023.

Two independent, mutually-blind transcribers each transcribed these four
fields from the official FTB 2023 Form 100S S Corporation Tax Booklet ONLY
(ftb.ca.gov), verbatim, with no reference to tenforty's params, tests, or
any derived value. They agreed on every field; the quotes below are the
shared verbatim booklet text. leginfo/R&TC was not needed — the booklet
states every value (the underlying statutes are R&TC §23802(b) for the
1.5% rate and §23153 for the minimum tax / first-year rule).
"""

SOURCES: tuple[str, ...] = (
    "FTB 2023 Form 100S S Corporation Tax Booklet "
    "(https://www.ftb.ca.gov/forms/2023/2023-100s-booklet.pdf), "
    "General Information B (Tax Rate and Minimum Franchise Tax).",
    "FTB 2023 Form 100S S Corporation Tax Booklet "
    "(https://www.ftb.ca.gov/forms/2023/2023-100s-booklet.pdf), "
    "General Information K (Estimated Tax).",
)

ATTESTED: dict[str, object] = {
    "year": 2023,
    # Gen. Info. B: "The following tax rates apply to S corporations subject
    # to either the corporation franchise tax or the corporation income tax.
    # • S corporations 1.5%" — the S-corp rate, deliberately NOT the 8.84%
    # general C-corp rate nor the 3.5% financial-S-corp rate.
    "franchise_tax_rate": 0.015,
    # Gen. Info. B: "The minimum franchise tax is $800 and must be paid
    # whether the S corporation is active, inactive, operates at a loss, or
    # files a return for a short-period of less than 12 months."
    "minimum_franchise_tax": 800,
    # Gen. Info. B: "A corporation that incorporated or qualified through the
    # California Secretary of State (SOS) to do business in California is not
    # subject to the minimum franchise tax for its first taxable year and
    # will compute its tax liability by multiplying its state net income by
    # the appropriate tax rate. The corporation will become subject to
    # minimum franchise tax beginning in its second taxable year." — a
    # FLOOR-only exemption: measured 1.5% tax still applies in year one.
    "first_year_minimum_tax_exempt": True,
    # Gen. Info. K: "Use Form 100-ES, Corporation Estimated Tax, to figure
    # and pay estimated tax for an S corporation. Corporations are required
    # to pay the following percentages of the estimated tax liability during
    # the taxable year: • 30% for the first required installment ..."
    "estimated_payment_required": True,
}
