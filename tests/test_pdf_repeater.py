"""Tests for PdfFiller repeater expansion."""

import shutil
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller

REPO_ROOT = Path(__file__).resolve().parents[1]
SCH_B_TEMPLATE = REPO_ROOT / "pdfs/federal/2025/f1040sb.pdf"


class ExpandRepeatersTests(unittest.TestCase):
    def test_flattens_scalars_and_numbered_rows(self):
        mapping = {
            "scalars": {"header": "topmostSubform[0].Page1[0].header[0]"},
            "repeaters": {
                "rows": {
                    "template": {
                        "label": "topmostSubform[0].Page1[0].Row{i}[0].label[0]",
                        "value": "topmostSubform[0].Page1[0].Row{i}[0].value[0]",
                    },
                    "max_slots": 3,
                    "overflow": "raise",
                },
            },
        }
        values = {
            "header": "My Form",
            "rows": [
                {"label": "A", "value": 1},
                {"label": "B", "value": 2},
            ],
        }

        expanded = PdfFiller._expand_repeaters(mapping, values)

        self.assertEqual(expanded["topmostSubform[0].Page1[0].header[0]"], "My Form")
        self.assertEqual(expanded["topmostSubform[0].Page1[0].Row1[0].label[0]"], "A")
        self.assertEqual(expanded["topmostSubform[0].Page1[0].Row1[0].value[0]"], "1")
        self.assertEqual(expanded["topmostSubform[0].Page1[0].Row2[0].label[0]"], "B")
        self.assertEqual(expanded["topmostSubform[0].Page1[0].Row2[0].value[0]"], "2")
        self.assertNotIn("topmostSubform[0].Page1[0].Row3[0].label[0]", expanded)

    def test_overflow_raises(self):
        mapping = {
            "scalars": {},
            "repeaters": {
                "rows": {
                    "template": {"label": "Row{i}[0].x[0]"},
                    "max_slots": 2,
                    "overflow": "raise",
                },
            },
        }
        values = {"rows": [{"label": "a"}, {"label": "b"}, {"label": "c"}]}

        with self.assertRaisesRegex(OverflowError, r"rows.*3.*2"):
            PdfFiller._expand_repeaters(mapping, values)

    def test_unknown_overflow_policy_raises_not_implemented(self):
        mapping = {
            "scalars": {},
            "repeaters": {
                "rows": {
                    "template": {"label": "Row{i}[0].x[0]"},
                    "max_slots": 1,
                    "overflow": "truncate",
                },
            },
        }
        values = {"rows": [{"label": "a"}, {"label": "b"}]}
        with self.assertRaisesRegex(NotImplementedError, r"truncate"):
            PdfFiller._expand_repeaters(mapping, values)

    def test_skips_none_fields(self):
        mapping = {
            "scalars": {"a": "a_pdf", "b": "b_pdf"},
            "repeaters": {},
        }
        values = {"a": "present", "b": None}
        expanded = PdfFiller._expand_repeaters(mapping, values)
        self.assertEqual(expanded, {"a_pdf": "present"})


class FillWithRepeatersTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_end_to_end_writes_pdf(self):
        if not SCH_B_TEMPLATE.exists():
            self.skipTest(f"Template not found: {SCH_B_TEMPLATE}")
        template = self.tmp_path / "tmpl.pdf"
        shutil.copy(SCH_B_TEMPLATE, template)
        mapping = {"scalars": {}, "repeaters": {}}
        out = self.tmp_path / "out.pdf"
        filler = PdfFiller()
        result = filler.fill_with_repeaters(
            template_path=template,
            output_path=out,
            mapping=mapping,
            values={},
        )
        self.assertEqual(result, out)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 0)

    def test_end_to_end_writes_scalar_and_repeater_fields(self):
        if not SCH_B_TEMPLATE.exists():
            self.skipTest(f"Template not found: {SCH_B_TEMPLATE}")
        template = self.tmp_path / "tmpl.pdf"
        shutil.copy(SCH_B_TEMPLATE, template)
        out = self.tmp_path / "out.pdf"

        # Real fields on f1040sb.pdf. We use f1_04 as a scalar sink and
        # f1_0{i}[0] (i in 1..2) as the repeater row template; these are
        # distinct fields on the Sch B template.
        scalar_field = "topmostSubform[0].Page1[0].f1_04[0]"
        row_template = "topmostSubform[0].Page1[0].f1_0{i}[0]"
        row1_field = "topmostSubform[0].Page1[0].f1_01[0]"
        row2_field = "topmostSubform[0].Page1[0].f1_02[0]"

        mapping = {
            "scalars": {"filer_name": scalar_field},
            "repeaters": {
                "payers": {
                    "template": {"amt": row_template},
                    "max_slots": 14,
                    "overflow": "raise",
                },
            },
        }
        values = {
            "filer_name": "Taxpayer Name",
            "payers": [{"amt": 100}, {"amt": 250}],
        }

        filler = PdfFiller()
        filler.fill_with_repeaters(
            template_path=template,
            output_path=out,
            mapping=mapping,
            values=values,
        )

        fields = PdfReader(str(out)).get_fields() or {}
        self.assertIn(scalar_field, fields)
        self.assertEqual(fields[scalar_field].get("/V"), "Taxpayer Name")
        self.assertIn(row1_field, fields)
        self.assertEqual(fields[row1_field].get("/V"), "100")
        self.assertIn(row2_field, fields)
        self.assertEqual(fields[row2_field].get("/V"), "250")
