# tenforty/mappings/pdf_f8962.py
from tenforty.mappings.registry import PdfFormMapping


class PdfF8962(PdfFormMapping[dict]):
    """SKELETON — the real probe-certified year-keyed mapping lands in Task 7.
    get_mapping RAISES (fail-loud) for every year with a work-owed message; all
    five f8962 years are allowlisted in KNOWN_GAPS so the gap-aware
    completeness/fields-on-template/checkbox sweeps never call it. The
    UnsupportedYearRaisesEverywhereTests sweep is NOT gap-aware and requires
    get_mapping to raise ValueError on any year — honored here (ValueError-typed
    to match the universal PdfFormMapping contract, with a work-owed message)."""
    _FORM_NAME = "Form 8962"
    _MAPPINGS: dict[int, dict] = {}

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        raise ValueError(
            f"Form 8962 PDF mapping for year {year} is not yet built — the "
            "probe-certified year-keyed mapping lands in Task 7 (currently "
            "allowlisted in tenforty.mappings.catalog.KNOWN_GAPS)."
        )
