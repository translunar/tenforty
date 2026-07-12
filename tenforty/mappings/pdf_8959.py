"""PDF field mapping for IRS Form 8959 (Additional Medicare Tax).

All fields are flat scalars (no repeaters). Field names enumerated from
``pdfs/federal/2025/f8959.pdf``: 26 `/Tx` fields on Page 1 — f1_1 is
the header name, f1_2 is the SSN, f1_3..f1_26 map to lines 1..24 in
order. The 2024 template's field tree is identical (verified by
scripts/diff_pdf_fields.py; re-verified every run by the fields-on-template
gate), so one payload serves both years.
"""

from tenforty.mappings.registry import PdfFormMapping

# One payload for 2024 and 2025 — identical field trees.
_FIELDS: dict = {
    "scalars": {
        "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
        "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",
        **{
            f"f8959_line_{n}":
                f"topmostSubform[0].Page1[0].f1_{n + 2}[0]"
            for n in range(1, 25)
        },
    },
    "repeaters": {},
}


class Pdf8959(PdfFormMapping[dict]):
    _FORM_NAME = "Form 8959"

    # 2023's field tree is byte-identical to 2024's (verified: identical
    # AcroForm field-path sets), so one payload serves all three years.
    _MAPPINGS: dict[int, dict] = {2023: _FIELDS, 2024: _FIELDS, 2025: _FIELDS}
