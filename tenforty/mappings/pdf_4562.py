"""Form 4562 PDF field mapping (tax year 2025).

v1 scope: header (name/SSN), Part III Section B line 19 rows, and the
Part IV line 22 total. Parts I/II/V/VI and Section C ADS are not
wired — add them when a scenario needs them.

Form 4562 Part III Section B is row-per-recovery-class. Each row has
six visible columns: (b) month/year placed, (c) basis, (d) recovery
period, (e) convention, (f) method, (g) deduction.

Row label → PDF subform:

  19a 3-year   → SectionBTable[0].Line19a
  19b 5-year   → Line19b
  19c 7-year   → Line19c
  19d 10-year  → Line19d
  19e 15-year  → Line19e
  19f 20-year  → Line19f
  19g 25-year  → Line19g
  19h 50-year  → Line19h         (new 2025 class, v1 has no MACRS table)
  19i 27.5-yr  → Line19i_1       (v1 uses sub-row 1; Line19i_2 reserved)
  19j 39-yr    → Line19j_1       (v1 uses sub-row 1; Line19j_2 reserved)

Within each subform the six per-column fields are `f1_{base+0..5}[0]`
where `base` is the first f1_N for that row — this module encodes the
base explicitly rather than relying on arithmetic.
"""

from tenforty.mappings.registry import PdfFormMapping

_P1 = "topmostSubform[0].Page1[0]"
_P2 = "topmostSubform[0].Page2[0]"
_SB = f"{_P1}.SectionBTable[0]"

# Row label → (subform name, first f1_N base index).
_ROW_BASES: dict[str, tuple[str, int]] = {
    "a": ("Line19a", 26),
    "b": ("Line19b", 32),
    "c": ("Line19c", 38),
    "d": ("Line19d", 44),
    "e": ("Line19e", 50),
    "f": ("Line19f", 56),
    "g": ("Line19g", 62),
    "h": ("Line19h", 68),
    "i": ("Line19i_1", 74),
    "j": ("Line19j_1", 86),
}

_COL_OFFSETS = {
    "date_placed_in_service": 0,   # col (b) month and year
    "basis": 1,                    # col (c) basis for depreciation
    "recovery_period": 2,          # col (d) recovery period
    "convention": 3,               # col (e) convention
    "method": 4,                   # col (f) method
    "deduction": 5,                # col (g) depreciation deduction
}


def _row_fields(label: str) -> dict[str, str]:
    subform, base = _ROW_BASES[label]
    out: dict[str, str] = {}
    for col, offset in _COL_OFFSETS.items():
        out[f"f4562_line_19{label}_{col}"] = (
            f"{_SB}.{subform}[0].f1_{base + offset}[0]"
        )
    return out


def _all_row_fields() -> dict[str, str]:
    out: dict[str, str] = {}
    for label in _ROW_BASES:
        out.update(_row_fields(label))
    return out


# 2024 Form 4562 Section B row structure differs from 2025:
#   - Rows a–f: 5 text fields each (stride 5), bases 26/31/36/41/46/51.
#     Columns: date(0), basis(1), recovery_period(2), convention(3), deduction(4).
#     The "method" column has no separate text field in 2024 (built-in default).
#   - Row g (25-year): f1_56/f1_58/f1_60 (non-consecutive; sub-containers for
#     convention and method mean only 3 writeable text cells per IRS XFA layout).
#     Map: date=f1_56, basis=f1_58, deduction=f1_60.
#   - Rows h_1 / h_2 (27.5-year sub-rows): f1_61/f1_62/f1_66 and f1_67/f1_68/f1_72.
#     Map: date=f1_{x}, basis=f1_{x+1}, deduction=f1_{x+n}.
#   - Rows i_1 / i_2 (39-year sub-rows): f1_73/f1_74/f1_78 and f1_79/f1_80/f1_84.
#     Map: date=f1_{x}, basis=f1_{x+1}, deduction=f1_{x+n}.
#   - There is no Line19j (50-year) in 2024; v1 has no 50-year scenario so
#     row "h" (50-year) from 2025 is omitted here.
#   - Page2: line 22 total = f2_1[0] (2024) vs f2_2[0] (2025).

def _all_row_fields_2024() -> dict[str, str]:
    sb = _SB
    out: dict[str, str] = {}

    # Rows a–f (3-year through 20-year): 5 text fields each, stride 5.
    # Columns: date_placed_in_service(0), basis(1), recovery_period(2),
    #          convention(3), deduction(4).
    # The "method" column has no separate writeable text field in 2024 —
    # it is omitted from this mapping.
    _simple_rows = {
        "a": ("Line19a", 26),
        "b": ("Line19b", 31),
        "c": ("Line19c", 36),
        "d": ("Line19d", 41),
        "e": ("Line19e", 46),
        "f": ("Line19f", 51),
    }
    _simple_cols = {
        "date_placed_in_service": 0,
        "basis": 1,
        "recovery_period": 2,
        "convention": 3,
        # method: no text field in 2024 — key omitted (filler skips missing keys)
        "deduction": 4,
    }
    for label, (subform, base) in _simple_rows.items():
        for col, offset in _simple_cols.items():
            out[f"f4562_line_19{label}_{col}"] = (
                f"{sb}.{subform}[0].f1_{base + offset}[0]"
            )

    # Row g (25-year): 3 writeable cells — date, basis, deduction.
    # recovery_period, convention, method are inside sub-containers without
    # separate text fields.
    out.update({
        "f4562_line_19g_date_placed_in_service": f"{sb}.Line19g[0].f1_56[0]",
        "f4562_line_19g_basis":                  f"{sb}.Line19g[0].f1_58[0]",
        "f4562_line_19g_deduction":              f"{sb}.Line19g[0].f1_60[0]",
    })

    # Row i (27.5-year in 2025 = Line19h_1 in 2024): 3 writeable cells.
    out.update({
        "f4562_line_19i_date_placed_in_service": f"{sb}.Line19h_1[0].f1_61[0]",
        "f4562_line_19i_basis":                  f"{sb}.Line19h_1[0].f1_62[0]",
        "f4562_line_19i_deduction":              f"{sb}.Line19h_1[0].f1_66[0]",
    })

    # Row j (39-year in 2025 = Line19i_1 in 2024): 3 writeable cells.
    out.update({
        "f4562_line_19j_date_placed_in_service": f"{sb}.Line19i_1[0].f1_73[0]",
        "f4562_line_19j_basis":                  f"{sb}.Line19i_1[0].f1_74[0]",
        "f4562_line_19j_deduction":              f"{sb}.Line19i_1[0].f1_78[0]",
    })

    return out


class Pdf4562(PdfFormMapping[dict]):
    _FORM_NAME = "Form 4562"

    _MAPPINGS: dict[int, dict] = {
        2024: {
            "scalars": {
                "taxpayer_name": f"{_P1}.f1_1[0]",
                "taxpayer_ssn": f"{_P1}.f1_2[0]",
                # Line 22 total depreciation: f2_1[0] in 2024 (f2_2[0] in 2025).
                "f4562_line_22_total_depreciation": f"{_P2}.f2_1[0]",
                **_all_row_fields_2024(),
            },
            "repeaters": {},
        },
        2025: {
            "scalars": {
                "taxpayer_name": f"{_P1}.f1_1[0]",
                "taxpayer_ssn": f"{_P1}.f1_2[0]",
                "f4562_line_22_total_depreciation": f"{_P2}.f2_2[0]",
                **_all_row_fields(),
            },
            "repeaters": {},
        },
    }


# 2023's Form 4562 field tree is byte-identical to 2024's (verified: identical
# AcroForm field-path sets), so 2023 reuses the 2024 payload unchanged. The
# fields-on-template gate re-verifies existence; the 2023 emit + parity gates
# verify positions.
Pdf4562._MAPPINGS[2023] = Pdf4562._MAPPINGS[2024]

# 2022's Form 4562 keeps 2023's identical field-NAME inventory and mapped paths;
# the sole widget nudge is on an unmapped field. So 2022 reuses the 2023 payload.
Pdf4562._MAPPINGS[2022] = Pdf4562._MAPPINGS[2023]
