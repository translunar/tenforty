# tests/test_mapping_line_identity.py
"""Line-identity gate for Form 1040 / Schedule 1 money lines.

The fields-on-template existence gate (test_mapping_fields_on_template.py)
proves every mapped field NAME exists on the year's blank template. It cannot
catch a field that exists but sits on the WRONG line — the exact failure that
shipped when the 2024 Form 1040 block was authored against the 2025 layout:
every referenced field existed, so the existence gate stayed green while the
1z total rendered on line 2a, total tax on line 26, the refund in the
Third-Party-Designee PIN box, and so on.

This module closes that gap WITHOUT /TU tooltips (the repo's IRS templates
carry none). It pins each money line's mapped field to a golden leaf derived
by marker-probe (tests/fixtures/golden_field_lines.py), and — when pdftotext
is present — re-derives the probe to prove each golden leaf really prints on
its stated IRS line, so the golden map is machine-checked rather than merely
author-asserted.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from tenforty.mappings.catalog import CATALOG
from tests.fixtures.golden_field_lines import GOLDEN_FIELD_LINES
from tenforty.verification.anchors import row_line_tokens
from tests.helpers import REPO_ROOT

_PDFS = REPO_ROOT / "pdfs"


def _template_for(jurisdiction: str, form: str, year: int) -> Path:
    entry = CATALOG[(jurisdiction, form)]
    return _PDFS / jurisdiction / str(year) / f"{entry.template_stem}.pdf"


def _leaf(path: str) -> str:
    return path.split(".")[-1].replace("[0]", "")


class GoldenPathPinTests(unittest.TestCase):
    """Pin each money line's mapped field to its probe-verified golden leaf.

    A shift of a money line to a DIFFERENT (but existing) field changes the
    leaf and reddens here — the case the existence gate is blind to. Also
    asserts the golden field exists on the blank template, so the fixture can
    never pin a field that isn't really there."""

    def test_money_lines_match_golden_leaves(self):
        for (jurisdiction, form, year), expected in sorted(
            GOLDEN_FIELD_LINES.items()
        ):
            entry = CATALOG[(jurisdiction, form)]
            mapping = entry.mapping_cls.get_mapping(year)
            # Schedule 1 partitions its payload into scalars/repeaters.
            if isinstance(mapping, dict) and "scalars" in mapping:
                mapping = mapping["scalars"]
            template = _template_for(jurisdiction, form, year)
            on_template = set(
                (PdfReader(template).get_fields() or {}).keys()
            )
            for key, (golden_leaf, _line) in expected.items():
                with self.subTest(form=form, year=year, key=key):
                    self.assertIn(
                        key, mapping,
                        f"{form} {year}: golden key '{key}' absent from mapping",
                    )
                    self.assertEqual(
                        _leaf(mapping[key]), golden_leaf,
                        f"{form} {year}: '{key}' maps to {_leaf(mapping[key])}, "
                        f"golden expects {golden_leaf} (money line shifted?)",
                    )
                    self.assertIn(
                        mapping[key], on_template,
                        f"{form} {year}: '{key}' -> {mapping[key]} not on template",
                    )


class GoldenLineIdentityProbeTests(unittest.TestCase):
    """Re-derive the marker-probe and prove each golden leaf prints on its
    stated IRS line. Skips LOUDLY (per year/form) when pdftotext is absent so
    the coverage hole is never silent."""

    # The marker probe lives in tenforty.verification.anchors (lifted
    # verbatim by the check-suite lane, which evaluates RowLabel anchors
    # with it); this test uses the same function.
    _row_line_tokens = staticmethod(row_line_tokens)

    def test_golden_leaves_print_on_stated_lines(self):
        if shutil.which("pdftotext") is None:
            self.skipTest("pdftotext not available; golden line-identity "
                          "self-check skipped (path-pin test still runs)")
        # Cache one probe render per template.
        cache: dict[Path, dict[str, set[str]]] = {}
        for (jurisdiction, form, year), expected in sorted(
            GOLDEN_FIELD_LINES.items()
        ):
            template = _template_for(jurisdiction, form, year)
            if template not in cache:
                cache[template] = self._row_line_tokens(template)
            row_tokens = cache[template]
            for key, (golden_leaf, line) in expected.items():
                with self.subTest(form=form, year=year, key=key):
                    self.assertIn(
                        golden_leaf, row_tokens,
                        f"{form} {year}: golden leaf {golden_leaf} rendered no "
                        f"row (field missing on template?)",
                    )
                    self.assertIn(
                        line, row_tokens[golden_leaf],
                        f"{form} {year}: golden leaf {golden_leaf} does not "
                        f"print on IRS line {line} (row labels: "
                        f"{sorted(row_tokens[golden_leaf])})",
                    )


if __name__ == "__main__":
    unittest.main()
