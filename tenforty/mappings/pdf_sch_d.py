"""PDF field mapping for IRS Schedule D (Capital Gains and Losses).

Covers the full Part I / Part II line grid plus page-2 lines 18/19:

  Part I (short-term):
    Line 1a  — covered-basis summary (proceeds / basis / gain); no 8949
    Line 1b  — covered-basis, basis NOT reported; referenced via 8949 Box B
    Line 2   — uncovered / non-1099-B short-term; referenced via 8949 Box C
    Line 3   — other short-term adjustments; referenced via 8949 Box D
    Line 4   — gain from installment sales (Form 6252) — single gain cell
    Line 5   — net short-term gain/loss from K-1s (partnerships / S-corps /
               estates / trusts) — single scalar cell
    Line 6   — short-term capital loss carryover — single scalar cell
    Line 7   — net short-term gain / (loss)

  Part II (long-term):
    Line 8a  — covered-basis summary (proceeds / basis / gain); no 8949
    Line 8b  — covered-basis, basis NOT reported; referenced via 8949 Box E
    Line 9   — uncovered / non-1099-B long-term; referenced via 8949 Box F
    Line 10  — other long-term adjustments; referenced via 8949 Box H
    Line 11  — gain from Form 4797 / 2439 / etc — single gain cell
    Line 12  — net long-term gain/loss from K-1s — single scalar cell
    Line 13  — capital gain distributions — single scalar cell
    Line 14  — long-term capital loss carryover — single scalar cell
    Line 15  — net long-term gain / (loss)

  Page 2:
    Line 16  — combined net gain / (loss)
    Line 18  — unrecaptured Section 1250 gain (from worksheet)
    Line 19  — 28%-rate gain (from worksheet)

Field names were enumerated from ``pdfs/federal/2025/f1040sd.pdf`` and
confirmed by the probe methodology used for Pdf4868/PdfSchB. Per-row
table cells are row-namespaced (``Table_PartI/Row1a/f1_3``). Single-cell
lines outside the table sit directly on Page1 (f1_*) or Page2 (f2_*).

The mapping shape is ``{"scalars": {...}, "repeaters": {}}`` to match the
repeater-aware filler call; the repeaters block is empty because Sch D
writes scalar cells only.
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

                # Part I — Line 1b (covered, basis NOT reported to IRS;
                # totals from 8949 Box B)
                "sch_d_line_1b_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row1b[0].f1_7[0]",
                "sch_d_line_1b_basis":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row1b[0].f1_8[0]",
                "sch_d_line_1b_gain":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row1b[0].f1_10[0]",

                # Part I — Line 2 (uncovered / non-1099-B short-term;
                # totals from 8949 Box C)
                "sch_d_line_2_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row2[0].f1_11[0]",
                "sch_d_line_2_basis":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row2[0].f1_12[0]",
                "sch_d_line_2_gain":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row2[0].f1_14[0]",

                # Part I — Line 3 (other short-term adjustments;
                # totals from 8949 Box D)
                "sch_d_line_3_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row3[0].f1_15[0]",
                "sch_d_line_3_basis":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row3[0].f1_16[0]",
                "sch_d_line_3_gain":
                    "topmostSubform[0].Page1[0].Table_PartI[0].Row3[0].f1_18[0]",

                # Part I — Line 4 short-term gain from installment sales
                # (Form 6252) — single gain cell; no proceeds/basis columns
                "sch_d_line_4_gain":
                    "topmostSubform[0].Page1[0].f1_19[0]",

                # Part I — Line 5 net short-term gain/loss from K-1s
                # (partnerships, S-corps, estates, trusts) — single scalar
                "sch_d_line_5_net_short_k1":
                    "topmostSubform[0].Page1[0].f1_20[0]",

                # Part I — Line 6 short-term capital loss carryover
                # — single scalar cell
                "sch_d_line_6_loss_carryover":
                    "topmostSubform[0].Page1[0].f1_21[0]",

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

                # Part II — Line 8b (covered, basis NOT reported to IRS;
                # totals from 8949 Box E)
                "sch_d_line_8b_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row8b[0].f1_27[0]",
                "sch_d_line_8b_basis":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row8b[0].f1_28[0]",
                "sch_d_line_8b_gain":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row8b[0].f1_30[0]",

                # Part II — Line 9 (uncovered / non-1099-B long-term;
                # totals from 8949 Box F)
                "sch_d_line_9_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row9[0].f1_31[0]",
                "sch_d_line_9_basis":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row9[0].f1_32[0]",
                "sch_d_line_9_gain":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row9[0].f1_34[0]",

                # Part II — Line 10 (other long-term adjustments;
                # totals from 8949 Box H)
                "sch_d_line_10_proceeds":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row10[0].f1_35[0]",
                "sch_d_line_10_basis":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row10[0].f1_36[0]",
                "sch_d_line_10_gain":
                    "topmostSubform[0].Page1[0].Table_PartII[0].Row10[0].f1_38[0]",

                # Part II — Line 11 gain from Forms 4797 / 2439 / etc.
                # — single gain cell; no proceeds/basis columns
                "sch_d_line_11_gain":
                    "topmostSubform[0].Page1[0].f1_39[0]",

                # Part II — Line 12 net long-term gain/loss from K-1s
                # (partnerships, S-corps, estates, trusts) — single scalar
                "sch_d_line_12_net_long_k1":
                    "topmostSubform[0].Page1[0].f1_40[0]",

                # Part II — Line 13 capital gain distributions
                # — single scalar cell
                "sch_d_line_13_cap_gain_dist":
                    "topmostSubform[0].Page1[0].f1_41[0]",

                # Part II — Line 14 long-term capital loss carryover
                # — single scalar cell
                "sch_d_line_14_loss_carryover":
                    "topmostSubform[0].Page1[0].f1_42[0]",

                # Part II — Line 15 net long-term gain / (loss)
                "sch_d_line_15_net_long":
                    "topmostSubform[0].Page1[0].f1_43[0]",

                # Part III — Line 16 combined net gain / (loss) on page 2
                "sch_d_line_16_total":
                    "topmostSubform[0].Page2[0].f2_1[0]",

                # Page 2 — Line 18 unrecaptured Section 1250 gain
                # (from the Unrecaptured Section 1250 Gain Worksheet)
                "sch_d_line_18_unrecap_1250":
                    "topmostSubform[0].Page2[0].f2_2[0]",

                # Page 2 — Line 19 28%-rate gain (from 28% Rate Gain Worksheet)
                "sch_d_line_19_28_rate_gain":
                    "topmostSubform[0].Page2[0].f2_3[0]",
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Schedule D PDF mapping for year {year}")
        return cls._MAPPINGS[year]
