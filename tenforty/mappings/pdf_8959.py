"""PDF field mapping for IRS Form 8959 (Additional Medicare Tax).

All fields are flat scalars (no repeaters). Field names enumerated from
``pdfs/federal/2025/f8959.pdf``: 26 `/Tx` fields on Page 1 — f1_1 is
the header name, f1_2 is the SSN, f1_3..f1_26 map to lines 1..24 in
order.
"""


class Pdf8959:
    _MAPPINGS: dict[int, dict] = {
        2025: {
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
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Form 8959 PDF mapping for year {year}")
        return cls._MAPPINGS[year]
