"""Independent reference (oracle) for IRS Form 8962, Premium Tax Credit (PTC).

This module is an AIR-GAPPED, hand-derived reference implementation used to
cross-check a SEPARATE production implementation that the author never read.
Every rule, table value, rounding step, and line formula below is derived
directly from the official IRS **Instructions for Form 8962** for the relevant
year, and is cited inline with the source URL and a short verbatim quote. It
imports nothing from ``tenforty`` except the schema-only input dataclasses
``Form1095A`` / ``Form1095AMonth`` (the shared 1095-A input, per the
``tests/oracles/README.md`` exception). Divergence from production is the
signal we want, so nothing describing production was consulted.

Covered tax years: 2021, 2022, 2023, 2024, 2025.

Scope (matches the brief -- deliberately narrow):
  * Tax family size 1, single filer, one qualified-health-plan policy.
  * 48 contiguous states + DC federal poverty table only (no AK/HI).
  * The monthly grid (Form 8962 lines 12-23) and totals (lines 24-29).
  * The 2021 ARPA unemployment-compensation rule.

Explicitly OUT of scope (not modeled): line 2b (dependents' MAGI), the annual
line-11 shortcut, Part IV policy allocations, Part V alternative calculation
for year of marriage, married-filing-separately repayment, the sub-100%-FPL
applicable-taxpayer eligibility gating and the alien/estimated-income
exceptions (this oracle assumes the caller is an applicable taxpayer and
proceeds with the form arithmetic), and the AK/HI poverty tables.

Primary sources (all fetched from irs.gov/pub/irs-prior):
  * 2021 Instructions for Form 8962: https://www.irs.gov/pub/irs-prior/i8962--2021.pdf
  * 2022 Instructions for Form 8962: https://www.irs.gov/pub/irs-prior/i8962--2022.pdf
  * 2023 Instructions for Form 8962: https://www.irs.gov/pub/irs-prior/i8962--2023.pdf
  * 2024 Instructions for Form 8962: https://www.irs.gov/pub/irs-prior/i8962--2024.pdf
  * 2025 Instructions for Form 8962: https://www.irs.gov/pub/irs-prior/i8962--2025.pdf

Result-dict key names returned by ``reference_f8962`` (documented so a separate
battery author can reconcile them with the production signature):
  * ``line4_poverty_line``     -- Form 8962 line 4: federal poverty line, family size 1 ($).
  * ``line5_pct``              -- Form 8962 line 5: household income as an integer % of FPL
                                  (401 is the ">=400%" sentinel).
  * ``line7_applicable_figure``-- Form 8962 line 7: applicable figure (4-dp decimal, as float).
  * ``line8a_annual_contribution`` -- Form 8962 line 8a: annual contribution amount ($, whole).
  * ``line8b_monthly_contribution``-- Form 8962 line 8b: monthly contribution amount ($, whole).
  * ``monthly`` -- list of 12 dicts (Jan..Dec), each with the whole-dollar columns:
        ``col_a_premium``       -- (a) monthly enrollment premium.
        ``col_b_slcsp``         -- (b) monthly applicable SLCSP premium.
        ``col_c_contribution``  -- (c) monthly contribution amount (line 8b, or 0 if a&b blank).
        ``col_d_max_assistance``-- (d) monthly maximum premium assistance = max(b - c, 0).
        ``col_e_ptc``           -- (e) monthly premium tax credit allowed = min(a, d).
        ``col_f_aptc``          -- (f) monthly advance PTC (APTC).
  * ``line24_total_ptc``    -- Form 8962 line 24: total PTC = sum of column (e).
  * ``line25_total_aptc``   -- Form 8962 line 25: total APTC = sum of column (f).
  * ``line26_net_ptc``      -- Form 8962 line 26: net PTC (0 when line 24 <= line 25).
  * ``line27_excess_aptc``  -- Form 8962 line 27: excess APTC (0 when line 25 <= line 24).
  * ``line28_repayment_limitation`` -- Form 8962 line 28: repayment limitation from Table 5
                                  (``None`` when line 5 >= 400, i.e. "leave line 28 blank").
  * ``line29_excess_aptc_repayment`` -- Form 8962 line 29: excess APTC repayment
                                  = min(line 27, line 28), or line 27 when line 28 is blank.

All Form 8962 line amounts are whole dollars. See ``_round_dollar`` for the
rounding rule and its citation.
"""

from decimal import Decimal, ROUND_HALF_UP

from tenforty.models import Form1095A, Form1095AMonth  # schema-only input (README exception)

_SUPPORTED_YEARS = (2021, 2022, 2023, 2024, 2025)


# --- Rounding ---------------------------------------------------------------
# Every dollar amount entered on Form 8962 is a whole dollar. The general
# instruction is to round each Form 1095-A amount to the nearest whole dollar
# before entering it, and to round each computed dollar line likewise.
#
# SOURCE (identical sentence in all five years' instructions; e.g. 2024,
# https://www.irs.gov/pub/irs-prior/i8962--2024.pdf, Part IV note):
#   "You should round the amounts on Form 1095-A to the nearest whole dollar
#    and enter dollars only on Form 8962."
# SOURCE -- line 8a (2024 same URL, "Line 8a"):
#   "Multiply line 3 by line 7 and enter the result on line 8a, rounded to the
#    nearest whole dollar amount."
# SOURCE -- line 8b (2024 same URL, "Line 8b"):
#   "Divide line 8a by 12.0 and enter the result on line 8b, rounded to the
#    nearest whole dollar amount."
# "Nearest whole dollar" is the ordinary IRS rule -- ties round up (away from
# zero) -- which is Decimal ROUND_HALF_UP.
def _round_dollar(value) -> int:
    """Round to the nearest whole dollar, ties away from zero."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# --- Table 1 (line 4): federal poverty line, family size 1, 48 states + DC --
# Form 8962 for tax year N uses the poverty guidelines published for the PRIOR
# calendar year (N-1).
#
# SOURCE (2024, https://www.irs.gov/pub/irs-prior/i8962--2024.pdf, Line 4 /
# Table 1-1):
#   "(For 2024, the 2023 federal poverty lines are used for this purpose ...)"
#   Table 1-1 "Federal Poverty Line for the 48 Contiguous States and the
#   District of Columbia", family size 1 -> "$14,580".
# The same "(For <year>, the <year-1> federal poverty lines are used ...)"
# note and Table 1-1 family-size-1 row appear in each year's instructions at
# the URLs listed in the module docstring:
#   2021 -> "$12,760"  (2020 guideline)
#   2022 -> "$12,880"  (2021 guideline)
#   2023 -> "$13,590"  (2022 guideline)
#   2024 -> "$14,580"  (2023 guideline)
#   2025 -> "$15,060"  (2024 guideline)
_POVERTY_LINE_FAMILY_SIZE_1 = {
    2021: 12760,
    2022: 12880,
    2023: 13590,
    2024: 14580,
    2025: 15060,
}


# --- Table 2 (line 7): applicable figure -----------------------------------
# The applicable-figure table is BYTE-IDENTICAL across all five years (2021-2025):
# under the American Rescue Plan Act (2021-2022) and its Inflation Reduction Act
# extension (2023-2025), the schedule runs 0.0000 at <=150% of FPL up to 0.0850
# at >=400% of FPL. The table is an integer lookup keyed on the Form 8962 line 5
# percentage.
#
# SOURCE (2024, https://www.irs.gov/pub/irs-prior/i8962--2024.pdf, Table 2 TIP;
# identical text in 2021/2022/2023/2025 at their URLs):
#   "If the amount on line 5 is 150 or less, your applicable figure is 0.0000.
#    If the amount on line 5 is 400 or more, your applicable figure is 0.0850."
# SOURCE -- Line 7 (same):
#   "Enter on line 7 the decimal number from Table 2 that applies to the amount
#    you entered on line 5."
#
# The dict below transcribes the printed Table 2 rows for line-5 values 150
# through 399 verbatim (e.g. 2024 URL, Table 2: 150->0.0000, 200->0.0200,
# 250->0.0400, 300->0.0600, 350->0.0725, 399->0.0848). Values <150 map to
# 0.0000 and values >=400 map to 0.0850 per the TIP quoted above.
_APPLICABLE_FIGURE = {
    150: "0.0000", 151: "0.0004", 152: "0.0008", 153: "0.0012", 154: "0.0016",
    155: "0.0020", 156: "0.0024", 157: "0.0028", 158: "0.0032", 159: "0.0036",
    160: "0.0040", 161: "0.0044", 162: "0.0048", 163: "0.0052", 164: "0.0056",
    165: "0.0060", 166: "0.0064", 167: "0.0068", 168: "0.0072", 169: "0.0076",
    170: "0.0080", 171: "0.0084", 172: "0.0088", 173: "0.0092", 174: "0.0096",
    175: "0.0100", 176: "0.0104", 177: "0.0108", 178: "0.0112", 179: "0.0116",
    180: "0.0120", 181: "0.0124", 182: "0.0128", 183: "0.0132", 184: "0.0136",
    185: "0.0140", 186: "0.0144", 187: "0.0148", 188: "0.0152", 189: "0.0156",
    190: "0.0160", 191: "0.0164", 192: "0.0168", 193: "0.0172", 194: "0.0176",
    195: "0.0180", 196: "0.0184", 197: "0.0188", 198: "0.0192", 199: "0.0196",
    200: "0.0200", 201: "0.0204", 202: "0.0208", 203: "0.0212", 204: "0.0216",
    205: "0.0220", 206: "0.0224", 207: "0.0228", 208: "0.0232", 209: "0.0236",
    210: "0.0240", 211: "0.0244", 212: "0.0248", 213: "0.0252", 214: "0.0256",
    215: "0.0260", 216: "0.0264", 217: "0.0268", 218: "0.0272", 219: "0.0276",
    220: "0.0280", 221: "0.0284", 222: "0.0288", 223: "0.0292", 224: "0.0296",
    225: "0.0300", 226: "0.0304", 227: "0.0308", 228: "0.0312", 229: "0.0316",
    230: "0.0320", 231: "0.0324", 232: "0.0328", 233: "0.0332", 234: "0.0336",
    235: "0.0340", 236: "0.0344", 237: "0.0348", 238: "0.0352", 239: "0.0356",
    240: "0.0360", 241: "0.0364", 242: "0.0368", 243: "0.0372", 244: "0.0376",
    245: "0.0380", 246: "0.0384", 247: "0.0388", 248: "0.0392", 249: "0.0396",
    250: "0.0400", 251: "0.0404", 252: "0.0408", 253: "0.0412", 254: "0.0416",
    255: "0.0420", 256: "0.0424", 257: "0.0428", 258: "0.0432", 259: "0.0436",
    260: "0.0440", 261: "0.0444", 262: "0.0448", 263: "0.0452", 264: "0.0456",
    265: "0.0460", 266: "0.0464", 267: "0.0468", 268: "0.0472", 269: "0.0476",
    270: "0.0480", 271: "0.0484", 272: "0.0488", 273: "0.0492", 274: "0.0496",
    275: "0.0500", 276: "0.0504", 277: "0.0508", 278: "0.0512", 279: "0.0516",
    280: "0.0520", 281: "0.0524", 282: "0.0528", 283: "0.0532", 284: "0.0536",
    285: "0.0540", 286: "0.0544", 287: "0.0548", 288: "0.0552", 289: "0.0556",
    290: "0.0560", 291: "0.0564", 292: "0.0568", 293: "0.0572", 294: "0.0576",
    295: "0.0580", 296: "0.0584", 297: "0.0588", 298: "0.0592", 299: "0.0596",
    300: "0.0600", 301: "0.0603", 302: "0.0605", 303: "0.0608", 304: "0.0610",
    305: "0.0613", 306: "0.0615", 307: "0.0618", 308: "0.0620", 309: "0.0623",
    310: "0.0625", 311: "0.0628", 312: "0.0630", 313: "0.0633", 314: "0.0635",
    315: "0.0638", 316: "0.0640", 317: "0.0643", 318: "0.0645", 319: "0.0648",
    320: "0.0650", 321: "0.0653", 322: "0.0655", 323: "0.0658", 324: "0.0660",
    325: "0.0663", 326: "0.0665", 327: "0.0668", 328: "0.0670", 329: "0.0673",
    330: "0.0675", 331: "0.0678", 332: "0.0680", 333: "0.0683", 334: "0.0685",
    335: "0.0688", 336: "0.0690", 337: "0.0693", 338: "0.0695", 339: "0.0698",
    340: "0.0700", 341: "0.0703", 342: "0.0705", 343: "0.0708", 344: "0.0710",
    345: "0.0713", 346: "0.0715", 347: "0.0718", 348: "0.0720", 349: "0.0723",
    350: "0.0725", 351: "0.0728", 352: "0.0730", 353: "0.0733", 354: "0.0735",
    355: "0.0738", 356: "0.0740", 357: "0.0743", 358: "0.0745", 359: "0.0748",
    360: "0.0750", 361: "0.0753", 362: "0.0755", 363: "0.0758", 364: "0.0760",
    365: "0.0763", 366: "0.0765", 367: "0.0768", 368: "0.0770", 369: "0.0773",
    370: "0.0775", 371: "0.0778", 372: "0.0780", 373: "0.0783", 374: "0.0785",
    375: "0.0788", 376: "0.0790", 377: "0.0793", 378: "0.0795", 379: "0.0798",
    380: "0.0800", 381: "0.0803", 382: "0.0805", 383: "0.0808", 384: "0.0810",
    385: "0.0813", 386: "0.0815", 387: "0.0818", 388: "0.0820", 389: "0.0823",
    390: "0.0825", 391: "0.0828", 392: "0.0830", 393: "0.0833", 394: "0.0835",
    395: "0.0838", 396: "0.0840", 397: "0.0843", 398: "0.0845", 399: "0.0848",
}


# --- Table 5 (line 28): repayment limitation, Single filing status ----------
# Per-year Single-column brackets keyed on the Form 8962 line 5 percentage.
# ">=400%" -> "leave line 28 blank" -> no limitation (represented as None).
#
# SOURCE (each year's "Table 5. Repayment Limitation", Single column, at the
# URLs in the module docstring; e.g. 2024:
# https://www.irs.gov/pub/irs-prior/i8962--2024.pdf):
#   2024 -> "Less than 200 ... $375 ; At least 200 but less than 300 ... $950 ;
#            At least 300 but less than 400 ... $1,575 ; 400 or more ... leave
#            line 28 blank"
# Verbatim Single-column figures transcribed per year:
#   2021 -> 325 / 800  / 1350 / blank
#   2022 -> 325 / 825  / 1400 / blank
#   2023 -> 350 / 900  / 1500 / blank
#   2024 -> 375 / 950  / 1575 / blank
#   2025 -> 375 / 975  / 1625 / blank
# Bracket structure (all years): "Less than 200", "At least 200 but less than
# 300", "At least 300 but less than 400", "400 or more".
_REPAYMENT_LIMITATION_SINGLE = {
    2021: (325, 800, 1350),
    2022: (325, 825, 1400),
    2023: (350, 900, 1500),
    2024: (375, 950, 1575),
    2025: (375, 975, 1625),
}


def _line5_percentage(magi_whole: int, poverty_line: int, year: int) -> int:
    """Form 8962 line 5: household income as an integer percentage of the FPL.

    The 401 (">400% of FPL") sentinel boundary is NOT uniform across years:
    2021 uses a different (older) Worksheet 2 than 2022-2025, and the two
    formats disagree at EXACTLY 400% of the poverty line (magi == 4 * FPL).
    Each year is implemented exactly per its OWN worksheet.

    line 3 == household income (line 2a; no line-2b dependents in scope);
    line 4 == the poverty line.

    --- 2021: single-step "400 or more" test on the FLOORED percentage ---
    SOURCE (2021, https://www.irs.gov/pub/irs-prior/i8962--2021.pdf,
    Worksheet 2, step 3):
      "Divide the amount on line 1 above by the amount on line 2 above. Do not
       round; instead, multiply this number by 100 (to express it as a
       percentage) and then drop any numbers after the decimal point. For
       example, for 0.9984, enter the result as 99; ... and for 3.997, enter
       the result as 399.* Is the result 400 or more? [Yes] Enter 401 here and
       on line 5 of Form 8962. [No] Enter the result here ..."
    The test is on the floored integer percentage, so at exactly 400%
    (floor = 400) the "400 or more" branch fires -> line 5 = 401.

    --- 2022-2025: "multiply line 2 by 4.0 ... more than 400%" (STRICT) ---
    SOURCE (2024, https://www.irs.gov/pub/irs-prior/i8962--2024.pdf,
    Worksheet 2, steps 3-4; identical steps in 2022/2023/2025 at their URLs):
      "3. Multiply the amount on line 2 by 4.0 ...
       4. Is the amount on line 1 more than the amount on line 3? [Yes] The
          amount on line 1 above is more than 400% of the federal poverty line.
          Enter 401 here and on line 5 of Form 8962. [No] Divide the amount on
          line 1 above by the amount on line 2 above. Do not round; instead,
          multiply this number by 100 ... drop any numbers after the decimal
          point ... Enter the result ..."
    Line 3 == 4 * FPL; the test is a STRICT "more than", so at exactly 400%
    (line 1 == line 3, not "more than") the "No" branch fires and line 5 is the
    floored percentage 400 (not 401).
    """
    if year == 2021:
        # 2021: floor first, then "400 or more" -> 401 (exact 400% -> 401).
        ratio = Decimal(magi_whole) / Decimal(poverty_line) * Decimal(100)
        pct = int(ratio.to_integral_value(rounding="ROUND_FLOOR"))
        if pct >= 400:
            return 401
        return pct

    # 2022-2025: strict "line 1 more than 4 * line 2" -> 401 (exact 400% -> 400).
    if magi_whole > 4 * poverty_line:
        return 401
    ratio = Decimal(magi_whole) / Decimal(poverty_line) * Decimal(100)
    return int(ratio.to_integral_value(rounding="ROUND_FLOOR"))


def _applicable_figure(line5_pct: int) -> Decimal:
    """Form 8962 line 7 applicable figure from Table 2 (integer line-5 lookup)."""
    if line5_pct < 150:
        return Decimal("0.0000")
    if line5_pct >= 400:
        return Decimal("0.0850")
    return Decimal(_APPLICABLE_FIGURE[line5_pct])


def _repayment_limitation(year: int, line5_pct: int):
    """Form 8962 line 28 from Table 5 (Single). None => "leave line 28 blank"."""
    low, mid, high = _REPAYMENT_LIMITATION_SINGLE[year]
    if line5_pct < 200:
        return low
    if line5_pct < 300:
        return mid
    if line5_pct < 400:
        return high
    return None  # "400 or more" -> leave line 28 blank (no limitation)


def reference_f8962(block: Form1095A, magi: float, year: int) -> dict:
    """Independent Form 8962 result for one tax year, from the IRS instructions.

    ``block`` carries the 1095-A monthly rows (premium, SLCSP, APTC per month,
    Jan..Dec) plus ``block.received_unemployment_2021`` and
    ``block.tax_exempt_interest``. ``magi`` is the taxpayer's modified AGI
    (Form 8962 line 2a household income input) -- taken as given, NOT recomputed
    (tax-exempt interest is already inside ``magi`` per Worksheet 1-1, so
    ``block.tax_exempt_interest`` is not re-added here). Assumes tax family
    size 1, single filer, one policy, 48 contiguous states + DC.

    Returns a dict; see the module docstring for the key names and meanings.
    """
    if year not in _SUPPORTED_YEARS:
        raise ValueError(
            f"year {year} is outside the supported range {_SUPPORTED_YEARS}"
        )

    poverty_line = _POVERTY_LINE_FAMILY_SIZE_1[year]

    # Line 2a / line 3: household income entered as a whole dollar (no line 2b
    # dependents in scope).
    line3 = _round_dollar(magi)

    # Line 5: household income as a percentage of the federal poverty line.
    #
    # 2021 ARPA unemployment rule -- SOURCE (2021
    # https://www.irs.gov/pub/irs-prior/i8962--2021.pdf, Line 5):
    #   "If you, or your spouse (if filing a joint return), received, or were
    #    approved to receive, unemployment compensation for any week beginning
    #    in 2021, enter 133 on line 5."
    # The instruction is to ENTER 133 directly (not a min() against the actual
    # percentage); implemented exactly as written. Only 2021's instructions
    # contain this rule.
    if year == 2021 and block.received_unemployment_2021:
        line5_pct = 133
    else:
        line5_pct = _line5_percentage(line3, poverty_line, year)

    # Line 7: applicable figure.
    applicable_figure = _applicable_figure(line5_pct)

    # Line 8a: annual contribution amount = round(line 3 * line 7).
    line8a = _round_dollar(Decimal(line3) * applicable_figure)
    # Line 8b: monthly contribution amount = round(line 8a / 12).
    line8b = _round_dollar(Decimal(line8a) / Decimal(12))

    # Lines 12-23: monthly grid.
    # SOURCE (2024 https://www.irs.gov/pub/irs-prior/i8962--2024.pdf,
    # "Lines 12 Through 23"):
    #   Column (a): 1095-A monthly enrollment premium (col A).
    #   Column (b): applicable SLCSP premium (col B).
    #   Column (c): "enter ... your monthly contribution amount from line 8b.
    #                If columns (a) and (b) ... are blank, leave column (c) ...
    #                blank."
    #   Column (d): "Subtract the amount in column (c) from the amount in
    #                column (b). If the result is zero or less, enter -0-."
    #   Column (e): "the lesser of the amount in column (a) or the amount in
    #                column (d)."
    #   Column (f): 1095-A monthly APTC (col C).
    monthly = []
    total_ptc = 0
    total_aptc = 0
    for m in block.months:  # exactly 12, Jan..Dec
        col_a = _round_dollar(m.premium)
        col_b = _round_dollar(m.slcsp)
        col_f = _round_dollar(m.aptc)
        if col_a == 0 and col_b == 0:
            # Columns (a) and (b) blank -> leave (c), (d), (e) blank (0).
            col_c = 0
            col_d = 0
            col_e = 0
        else:
            col_c = line8b
            col_d = max(col_b - col_c, 0)
            col_e = min(col_a, col_d)
        total_ptc += col_e
        total_aptc += col_f
        monthly.append(
            {
                "col_a_premium": col_a,
                "col_b_slcsp": col_b,
                "col_c_contribution": col_c,
                "col_d_max_assistance": col_d,
                "col_e_ptc": col_e,
                "col_f_aptc": col_f,
            }
        )

    # Line 24: total PTC = sum of column (e).
    # Line 25: total APTC = sum of column (f).
    line24 = total_ptc
    line25 = total_aptc

    # Line 26 (net PTC) and Line 27 (excess APTC).
    # SOURCE (2024 same URL, Line 26 / Line 27):
    #   Line 26: "If line 24 is greater than line 25, subtract line 25 from
    #             line 24 ..." (else net PTC is 0/blank).
    #   Line 27: "If line 25 is greater than line 24, subtract line 24 from
    #             line 25 ..." (excess APTC).
    if line24 > line25:
        line26 = line24 - line25
        line27 = 0
    else:
        line26 = 0
        line27 = line25 - line24

    # Line 28: repayment limitation (Table 5, Single). None => blank.
    line28 = _repayment_limitation(year, line5_pct)

    # Line 29: excess APTC repayment.
    # SOURCE (2024 same URL, Line 29):
    #   "Enter the smaller of line 27 or line 28. If line 28 is blank, enter the
    #    amount from line 27 on line 29."
    if line28 is None:
        line29 = line27
    else:
        line29 = min(line27, line28)

    return {
        "line4_poverty_line": poverty_line,
        "line5_pct": line5_pct,
        "line7_applicable_figure": float(applicable_figure),
        "line8a_annual_contribution": line8a,
        "line8b_monthly_contribution": line8b,
        "monthly": monthly,
        "line24_total_ptc": line24,
        "line25_total_aptc": line25,
        "line26_net_ptc": line26,
        "line27_excess_aptc": line27,
        "line28_repayment_limitation": line28,
        "line29_excess_aptc_repayment": line29,
    }
