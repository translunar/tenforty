# Schedule SE (Form 1040) line-8a wage-base cases, TY2021–TY2025: hand derivation

Air-gapped oracle author, 2026-10-17. Sources: official IRS PDFs only, listed below. I read no
tenforty source; `tests/test_f1040_spine_oracle.py` turned out to be a workbook parity harness
with no hand-fixture shape, so the case format is self-defined here (the JSON block at the end).
I ran no tenforty code. The arithmetic below is by hand, re-checked with a stand-alone
`decimal` script.

## Sources (fetched 2026-10-17 with curl, all HTTP 200)

| TY | Form | URL | sha256 |
|---|---|---|---|
| 2021 | Schedule SE | https://www.irs.gov/pub/irs-prior/f1040sse--2021.pdf | 474ef0024350fcc7aa2d2c879b28f362e6fdc11e41ef9ea3fba9e6f51ee01e51 |
| 2021 | Instructions | https://www.irs.gov/pub/irs-prior/i1040sse--2021.pdf | 7dcd878dc46c587792b350e9d6a9a7090f91f54419d0e3807ac1d89153c749fc |
| 2022 | Schedule SE | https://www.irs.gov/pub/irs-prior/f1040sse--2022.pdf | 60900671b35f6076b3dd6b24ede232d7e40da1c4dc4eaac49f84257d3a4dc269 |
| 2022 | Instructions | https://www.irs.gov/pub/irs-prior/i1040sse--2022.pdf | c171269529b93deaf2eb4bd8014d6abf4aab572e88d949101cdd9a986c964ec2 |
| 2023 | Schedule SE | https://www.irs.gov/pub/irs-prior/f1040sse--2023.pdf | ae11beaaedd525f47155e1692c7f7e5386c912c334912978f5f87507dcdc0b30 |
| 2023 | Instructions | https://www.irs.gov/pub/irs-prior/i1040sse--2023.pdf | b5e99819f1226c3e169e073deb331ea73585303598e80d9417b441ae923e92d5 |
| 2024 | Schedule SE | https://www.irs.gov/pub/irs-prior/f1040sse--2024.pdf | ac8ba97e554b67275d0e888d709e0ecadc9b45634c52cd934fa9bdcfd15179b0 |
| 2024 | Instructions | https://www.irs.gov/pub/irs-prior/i1040sse--2024.pdf | 8cc5629c3032491e06b72c968f7dae958e1473d744d7f0a8fd808c71cda7a30b |
| 2025 | Schedule SE | https://www.irs.gov/pub/irs-prior/f1040sse--2025.pdf | 05bc2b3e1dfca65d8c6fc6d652af4fa3736e953c6575d6e9f82590484677d347 |
| 2025 | Instructions | https://www.irs.gov/pub/irs-prior/i1040sse--2025.pdf | ea9e3120706f9d5e21ce1c6cbec256b5e2e2bf02c44759773d9236462cf4d800 |

The 2025 form's footer reads "Schedule SE (Form 1040) 2025 Created 5/7/25".

## Wage base per year, verified against two official texts each

| TY | Form line 7 preprint | Form line 8a text | Instructions, "What's New" |
|---|---|---|---|
| 2021 | 142,800 | "If $142,800 or more, skip lines 8b through 10, and go to line 11" | "For 2021, the maximum amount of self-employment income subject to social security tax is $142,800" |
| 2022 | 147,000 | "If $147,000 or more, skip …" | "… For 2022 … is $147,000" |
| 2023 | 160,200 | "If $160,200 or more, skip …" | "… For 2023 … is $160,200" |
| 2024 | 168,600 | "If $168,600 or more, skip …" | "… For 2024 … is $168,600" |
| 2025 | $176,100 | "If $176,100 or more, skip …" | "… For 2025 … is $176,100" |

All five match the team-lead's list.

Across years, the wording of Part I lines 2–13 is identical apart from layout. I compared the
normalized text of every year against 2021. The only substantive edits are elsewhere:
- 2023 onward, line 12 adds "or Form 1040-SS, Part I, line 3".
- 2023 onward, the K-1 code on line 1b changes from AH to AQ.

Neither edit touches these cases. The instructions have no separate guidance for lines 7–12
(the "Instructions for Part I" cover only church income, line 1b, lines 4a–4c, the line 13
1040-SS note, and Additional Medicare Tax), so the form text governs every line used below.

Form text used (Schedule SE, Part I, page 1, same every year):
- L2: "Net profit or (loss) from Schedule C, line 31; and Schedule K-1 (Form 1065), box 14, code A (other than farming)"
- L3: "Combine lines 1a, 1b, and 2"
- L4a: "If line 3 is more than zero, multiply line 3 by 92.35% (0.9235). Otherwise, enter amount from line 3"
- L4b: "If you elect one or both of the optional methods, enter the total of lines 15 and 17 here"
- L4c: "Combine lines 4a and 4b. If less than $400, stop; you don't owe self-employment tax. …"
- L5a/5b: church employee income; L5b "Multiply line 5a by 92.35% (0.9235). If less than $100, enter -0-"
- L6: "Add lines 4c and 5b"
- L7: "Maximum amount of combined wages and self-employment earnings subject to social security tax … for <YEAR>" (preprinted base)
- L8a: "Total social security wages and tips (total of boxes 3 and 7 on Form(s) W-2) and railroad retirement (tier 1) compensation. If $<BASE> or more, skip lines 8b through 10, and go to line 11"
- L8b: Form 4137 unreported tips. L8c: Form 8919 wages. L8d: "Add lines 8a, 8b, and 8c"
- L9: "Subtract line 8d from line 7. If zero or less, enter -0- here and on line 10 and go to line 11"
- L10: "Multiply the smaller of line 6 or line 9 by 12.4% (0.124)"
- L11: "Multiply line 6 by 2.9% (0.029)"
- L12: "Self-employment tax. Add lines 10 and 11. Enter here and on Schedule 2 (Form 1040), line 4"
- L13: "Deduction for one-half of self-employment tax. Multiply line 12 by 50% (0.50). Enter here and on Schedule 1 (Form 1040), line 15"

## Case design (synthetic)

- One sole proprietor with Schedule C line 31 net profit of **$40,000** in every case: no farm
  income, no CRP, no church employee income, no optional method, no Form 4137 tips, no Form 8919
  wages, and W-2 box 7 (SS tips) = 0.
- I used $40,000 rather than the suggested $5,500 so that every line comes out to exact cents
  (40,000 × 0.9235 = 36,940.00). It also makes line 6 (36,940) larger than case 3's $20,000 of
  room, so the "smaller of line 6 or line 9" choice on line 10 is actually exercised.
- **Case 1, at the base:** one W-2, box 3 = the year's base.
- **Case 2, $10,000 above the base:** TWO W-2s, because one employer's box 3 cannot exceed the
  base. Employer A box 3 = $100,000; employer B box 3 = base + 10,000 − 100,000. Both are at or
  below the base.
- **Case 3, $20,000 below the base (control):** one W-2, box 3 = base − 20,000.

## Line-by-line arithmetic (identical in all five years except lines 7, 8a, 8d)

| Line | Case 1 (at base) | Case 2 (+10,000) | Case 3 (−20,000) | Working |
|---|---|---|---|---|
| 1a, 1b | blank | blank | blank | no farm income / CRP |
| 2 | 40,000.00 | 40,000.00 | 40,000.00 | Schedule C line 31 |
| 3 | 40,000.00 | 40,000.00 | 40,000.00 | 0 + 0 + 40,000 |
| 4a | 36,940.00 | 36,940.00 | 36,940.00 | 40,000 × 0.9235 |
| 4b | blank | blank | blank | no optional method |
| 4c | 36,940.00 | 36,940.00 | 36,940.00 | 36,940 + 0; ≥ 400, so continue |
| 5a, 5b | blank | blank | blank | no church income (see flag 4) |
| 6 | 36,940.00 | 36,940.00 | 36,940.00 | 36,940 + 0 |
| 7 | BASE | BASE | BASE | preprinted |
| 8a | BASE | BASE + 10,000 | BASE − 20,000 | W-2 box 3 + box 7 total |
| 8b | **SKIPPED** | **SKIPPED** | blank (no Form 4137) | L8a: "If $BASE or more, skip lines 8b through 10" |
| 8c | **SKIPPED** | **SKIPPED** | blank (no Form 8919) | same |
| 8d | **SKIPPED** | **SKIPPED** | BASE − 20,000 | 8a + 0 + 0 |
| 9 | **SKIPPED** | **SKIPPED** | 20,000.00 | BASE − (BASE − 20,000) |
| 10 | **SKIPPED** | **SKIPPED** | 2,480.00 | smaller of 36,940 and 20,000 = 20,000; × 0.124 |
| 11 | 1,071.26 | 1,071.26 | 1,071.26 | 36,940 × 0.029 = 1,071.26 exactly |
| 12 | **1,071.26** | **1,071.26** | **3,551.26** | L10 + L11. In cases 1 and 2, L10 is blank and counts as 0 |
| 13 | **535.63** | **535.63** | **1,775.63** | L12 × 0.50 |

**Lines the official form leaves blank in cases 1 and 2:** 8b, 8c, 8d, 9 and 10, all five. The
skip instruction on line 8a covers "lines 8b through 10" and sends the filer to line 11. Line 8a
itself IS entered (with the wage total). Line 9's "enter -0- … on line 10" alternative applies
only to a filer who reaches line 9, so it does not apply here: in cases 1 and 2, lines 9 and 10
are blank, not zero.

Per-year values for lines 7 / 8a / 8d:

| TY | BASE (L7) | C1 L8a | C2 W-2s → L8a | C3 L8a = L8d |
|---|---|---|---|---|
| 2021 | 142,800 | 142,800 | 100,000 + 52,800 = 152,800 | 122,800 |
| 2022 | 147,000 | 147,000 | 100,000 + 57,000 = 157,000 | 127,000 |
| 2023 | 160,200 | 160,200 | 100,000 + 70,200 = 170,200 | 140,200 |
| 2024 | 168,600 | 168,600 | 100,000 + 78,600 = 178,600 | 148,600 |
| 2025 | 176,100 | 176,100 | 100,000 + 86,100 = 186,100 | 156,100 |

Totals are the same in every year: cases 1 and 2 have L12 = 1,071.26 and L13 = 535.63; case 3
has L12 = 3,551.26 and L13 = 1,775.63. This is by design. The year's base enters only through
the branch decision and the room on line 9, and both are pinned exactly. A wrong base still
shows up. For example, a too-high base in case 1 would create room and a nonzero line 10, and
any base error in case 3 changes line 9.

## Flags

1. **Rounding.** The form's multiplications give exact cents here, and every value above is
   exact; no rounding was applied. The Schedule SE instructions say nothing about rounding to
   whole dollars. The Form 1040 instructions' general round-off option is something I did not
   re-fetch or verify for this task. If the harness compares whole dollars:
   - L11 and L12 in cases 1 and 2 = 1,071, and L13 = 536 (from 535.63).
   - Case 3: L12 = 3,551, and L13 = 1,776 (from 1,775.63).
   Rounding L12 first and then halving it (1,071 / 2 = 535.50) is a different, path-dependent
   result. Decide which convention the fixture pins.
2. **Case 2 needs two W-2s.** A single employer's box 3 stops at the base, so "above the base"
   is only possible with multiple employers. Consequence outside Schedule SE: excess
   social-security withholding becomes a credit (Schedule 3 / Form 1040), if the spine
   computes it.
3. **Additional Medicare Tax (Form 8959) is out of Schedule SE scope but may trigger
   elsewhere.** The SE instructions put the single/HoH threshold at $200,000, reduced by wages.
   For a SINGLE filer, wages + line 6 exceed $200,000 in:
   - 2023 case 2: 170,200 + 36,940 = 207,140
   - 2024 cases 1 and 2: 205,540 and 215,540
   - 2025 cases 1 and 2: 213,040 and 223,040
   The MFJ threshold is $250,000, which no case reaches, so an MFJ filer (spouse with no income)
   keeps Form 8959 out of all 15 cases. Pick the filing status deliberately.
4. **Lines 5a/5b.** 5b says "If less than $100, enter -0-". With no church income I leave 5a
   and 5b blank (no entry) and treat 5b as 0 in line 6. No value changes either way.
5. **The skip branch is inclusive.** It triggers at "$BASE or more", so case 1 (exactly at the
   base) takes the skip branch. On the non-skip path, line 9 would be 0 and line 10 would be
   −0−, so line 12 is the same; only the blank-vs-zero pattern on lines 8b–10 differs.

## Machine-readable cases

`"SKIPPED"` = the form says to skip the line (blank). `null` = no entry (nothing to report).
Amounts are decimal strings.

```json
[
 {
  "tax_year": 2021,
  "case": "1_at_base",
  "w2_box3_social_security_wages": [
   142800
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "142800",
   "8a": "142800",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "474ef0024350fcc7aa2d2c879b28f362e6fdc11e41ef9ea3fba9e6f51ee01e51",
  "i1040sse_sha256": "7dcd878dc46c587792b350e9d6a9a7090f91f54419d0e3807ac1d89153c749fc"
 },
 {
  "tax_year": 2021,
  "case": "2_above_base",
  "w2_box3_social_security_wages": [
   100000,
   52800
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "142800",
   "8a": "152800",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "474ef0024350fcc7aa2d2c879b28f362e6fdc11e41ef9ea3fba9e6f51ee01e51",
  "i1040sse_sha256": "7dcd878dc46c587792b350e9d6a9a7090f91f54419d0e3807ac1d89153c749fc"
 },
 {
  "tax_year": 2021,
  "case": "3_below_base",
  "w2_box3_social_security_wages": [
   122800
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "142800",
   "8a": "122800",
   "8b": null,
   "8c": null,
   "8d": "122800",
   "9": "20000",
   "10": "2480.00",
   "11": "1071.26",
   "12": "3551.26",
   "13": "1775.63"
  },
  "f1040sse_sha256": "474ef0024350fcc7aa2d2c879b28f362e6fdc11e41ef9ea3fba9e6f51ee01e51",
  "i1040sse_sha256": "7dcd878dc46c587792b350e9d6a9a7090f91f54419d0e3807ac1d89153c749fc"
 },
 {
  "tax_year": 2022,
  "case": "1_at_base",
  "w2_box3_social_security_wages": [
   147000
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "147000",
   "8a": "147000",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "60900671b35f6076b3dd6b24ede232d7e40da1c4dc4eaac49f84257d3a4dc269",
  "i1040sse_sha256": "c171269529b93deaf2eb4bd8014d6abf4aab572e88d949101cdd9a986c964ec2"
 },
 {
  "tax_year": 2022,
  "case": "2_above_base",
  "w2_box3_social_security_wages": [
   100000,
   57000
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "147000",
   "8a": "157000",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "60900671b35f6076b3dd6b24ede232d7e40da1c4dc4eaac49f84257d3a4dc269",
  "i1040sse_sha256": "c171269529b93deaf2eb4bd8014d6abf4aab572e88d949101cdd9a986c964ec2"
 },
 {
  "tax_year": 2022,
  "case": "3_below_base",
  "w2_box3_social_security_wages": [
   127000
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "147000",
   "8a": "127000",
   "8b": null,
   "8c": null,
   "8d": "127000",
   "9": "20000",
   "10": "2480.00",
   "11": "1071.26",
   "12": "3551.26",
   "13": "1775.63"
  },
  "f1040sse_sha256": "60900671b35f6076b3dd6b24ede232d7e40da1c4dc4eaac49f84257d3a4dc269",
  "i1040sse_sha256": "c171269529b93deaf2eb4bd8014d6abf4aab572e88d949101cdd9a986c964ec2"
 },
 {
  "tax_year": 2023,
  "case": "1_at_base",
  "w2_box3_social_security_wages": [
   160200
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "160200",
   "8a": "160200",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "ae11beaaedd525f47155e1692c7f7e5386c912c334912978f5f87507dcdc0b30",
  "i1040sse_sha256": "b5e99819f1226c3e169e073deb331ea73585303598e80d9417b441ae923e92d5"
 },
 {
  "tax_year": 2023,
  "case": "2_above_base",
  "w2_box3_social_security_wages": [
   100000,
   70200
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "160200",
   "8a": "170200",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "ae11beaaedd525f47155e1692c7f7e5386c912c334912978f5f87507dcdc0b30",
  "i1040sse_sha256": "b5e99819f1226c3e169e073deb331ea73585303598e80d9417b441ae923e92d5"
 },
 {
  "tax_year": 2023,
  "case": "3_below_base",
  "w2_box3_social_security_wages": [
   140200
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "160200",
   "8a": "140200",
   "8b": null,
   "8c": null,
   "8d": "140200",
   "9": "20000",
   "10": "2480.00",
   "11": "1071.26",
   "12": "3551.26",
   "13": "1775.63"
  },
  "f1040sse_sha256": "ae11beaaedd525f47155e1692c7f7e5386c912c334912978f5f87507dcdc0b30",
  "i1040sse_sha256": "b5e99819f1226c3e169e073deb331ea73585303598e80d9417b441ae923e92d5"
 },
 {
  "tax_year": 2024,
  "case": "1_at_base",
  "w2_box3_social_security_wages": [
   168600
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "168600",
   "8a": "168600",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "ac8ba97e554b67275d0e888d709e0ecadc9b45634c52cd934fa9bdcfd15179b0",
  "i1040sse_sha256": "8cc5629c3032491e06b72c968f7dae958e1473d744d7f0a8fd808c71cda7a30b"
 },
 {
  "tax_year": 2024,
  "case": "2_above_base",
  "w2_box3_social_security_wages": [
   100000,
   78600
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "168600",
   "8a": "178600",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "ac8ba97e554b67275d0e888d709e0ecadc9b45634c52cd934fa9bdcfd15179b0",
  "i1040sse_sha256": "8cc5629c3032491e06b72c968f7dae958e1473d744d7f0a8fd808c71cda7a30b"
 },
 {
  "tax_year": 2024,
  "case": "3_below_base",
  "w2_box3_social_security_wages": [
   148600
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "168600",
   "8a": "148600",
   "8b": null,
   "8c": null,
   "8d": "148600",
   "9": "20000",
   "10": "2480.00",
   "11": "1071.26",
   "12": "3551.26",
   "13": "1775.63"
  },
  "f1040sse_sha256": "ac8ba97e554b67275d0e888d709e0ecadc9b45634c52cd934fa9bdcfd15179b0",
  "i1040sse_sha256": "8cc5629c3032491e06b72c968f7dae958e1473d744d7f0a8fd808c71cda7a30b"
 },
 {
  "tax_year": 2025,
  "case": "1_at_base",
  "w2_box3_social_security_wages": [
   176100
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "176100",
   "8a": "176100",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "05bc2b3e1dfca65d8c6fc6d652af4fa3736e953c6575d6e9f82590484677d347",
  "i1040sse_sha256": "ea9e3120706f9d5e21ce1c6cbec256b5e2e2bf02c44759773d9236462cf4d800"
 },
 {
  "tax_year": 2025,
  "case": "2_above_base",
  "w2_box3_social_security_wages": [
   100000,
   86100
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "176100",
   "8a": "186100",
   "8b": "SKIPPED",
   "8c": "SKIPPED",
   "8d": "SKIPPED",
   "9": "SKIPPED",
   "10": "SKIPPED",
   "11": "1071.26",
   "12": "1071.26",
   "13": "535.63"
  },
  "f1040sse_sha256": "05bc2b3e1dfca65d8c6fc6d652af4fa3736e953c6575d6e9f82590484677d347",
  "i1040sse_sha256": "ea9e3120706f9d5e21ce1c6cbec256b5e2e2bf02c44759773d9236462cf4d800"
 },
 {
  "tax_year": 2025,
  "case": "3_below_base",
  "w2_box3_social_security_wages": [
   156100
  ],
  "w2_box7_ss_tips": 0,
  "schedule_c_line_31_net_profit": 40000,
  "lines": {
   "1a": null,
   "1b": null,
   "2": "40000",
   "3": "40000",
   "4a": "36940.00",
   "4b": null,
   "4c": "36940.00",
   "5a": null,
   "5b": null,
   "6": "36940.00",
   "7": "176100",
   "8a": "156100",
   "8b": null,
   "8c": null,
   "8d": "156100",
   "9": "20000",
   "10": "2480.00",
   "11": "1071.26",
   "12": "3551.26",
   "13": "1775.63"
  },
  "f1040sse_sha256": "05bc2b3e1dfca65d8c6fc6d652af4fa3736e953c6575d6e9f82590484677d347",
  "i1040sse_sha256": "ea9e3120706f9d5e21ce1c6cbec256b5e2e2bf02c44759773d9236462cf4d800"
 }
]
```
