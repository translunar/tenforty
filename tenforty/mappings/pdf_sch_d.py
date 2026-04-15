"""PDF field mapping for IRS Schedule D (Capital Gains and Losses).

v1 scope: SUMMARY PATH ONLY. The covered-basis, no-adjustment summary
lines 1a and 8a carry aggregate proceeds / basis / gain for transactions
reported on 1099-B with basis reported to the IRS and no wash-sale or
other adjustments. Any lot that would require Form 8949 (non-covered
basis, basis adjustments, wash sales) is gated at scenario load via
``TaxReturnConfig.acknowledges_form_8949_unsupported`` and enforced in
``forms.sch_d.compute`` (see #11 Tasks 6 and 11). 8949 support is tracked
as a follow-up.

Field names were enumerated from ``pdfs/federal/2025/f1040sd.pdf`` and
confirmed by the probe methodology used for Pdf4868/PdfSchB. Unlike
Sch B, Sch D's per-row fields are row-namespaced
(``Table_PartI/Row1a/f1_3``), so the mapping is shape
``{"scalars": {...}, "repeaters": {}}`` matching the repeater-aware
Plan-B-Task-1 filler call — but with an empty repeaters block, since the
summary path writes scalar cells only.
"""


class PdfSchD:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": {
                # Header
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",

                # Part I — Short-term, Line 1a (covered, basis reported,
                # no adjustments — no 8949 required)
                "sch_d_line_1a_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row1a[0].f1_3[0]",
                "sch_d_line_1a_basis":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row1a[0].f1_4[0]",
                "sch_d_line_1a_gain":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row1a[0].f1_6[0]",

                # Part I — Line 7 net short-term gain / (loss)
                "sch_d_line_7_net_short":
                    "topmostSubform[0].Page1[0].f1_22[0]",

                # Part II — Long-term, Line 8a (covered summary)
                "sch_d_line_8a_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row8a[0].f1_23[0]",
                "sch_d_line_8a_basis":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row8a[0].f1_24[0]",
                "sch_d_line_8a_gain":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row8a[0].f1_26[0]",

                # Part II — Line 15 net long-term gain / (loss)
                "sch_d_line_15_net_long":
                    "topmostSubform[0].Page1[0].f1_43[0]",

                # Part III — Line 16 combined net gain / (loss) on page 2
                "sch_d_line_16_total":
                    "topmostSubform[0].Page2[0].f2_1[0]",
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Schedule D PDF mapping for year {year}")
        return cls._MAPPINGS[year]
