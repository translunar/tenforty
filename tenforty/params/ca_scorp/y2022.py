# tenforty/params/ca_scorp/y2022.py
"""FTB-attested 2022 California S-corporation (Form 100S) parameters.

Dual-transcribed from the FTB 2022 Form 100S S Corporation Tax Booklet
only; verbatim quotes and URL live in
tests/params_attestations/ca_scorp_y2022.py. General Information B (Tax
Rate and Minimum Franchise Tax) and General Information K (Estimated Tax).
"""
from tenforty.params.ca_scorp import CAScorpParams

PARAMS = CAScorpParams(
    year=2022,
    franchise_tax_rate=0.015,
    minimum_franchise_tax=800,
    first_year_minimum_tax_exempt=True,
    estimated_payment_required=True,
)
