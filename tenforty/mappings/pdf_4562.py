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


class Pdf4562:
    _MAPPINGS: dict[int, dict] = {
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

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Form 4562 PDF mapping for year {year}")
        return cls._MAPPINGS[year]
