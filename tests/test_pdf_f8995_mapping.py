"""PDF field mapping for Form 8995 — scalar fields only in v1."""

import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.models import ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_k1_scenario, needs_libreoffice, needs_pdf

# The placement test binds each mapped field to its printed line with the SAME
# caption-anchored method Task 1's probe uses (nearest left-margin numeric label
# above the field's /Rect bottom, within 20pt). Re-derive it from the template
# via the probe module rather than parsing the generated correspondence doc.
_SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import probe_f8995_boxes as _probe  # noqa: E402


class PdfF8995MappingTests(unittest.TestCase):
    def test_has_2025_mapping(self):
        mapping = PdfF8995.get_mapping(2025)
        self.assertIn("scalars", mapping)
        for key in (
            "f8995_line_1_qbi",
            "f8995_line_3_component",
            "f8995_line_15_qbi_deduction",
            "taxpayer_name",
            "taxpayer_ssn",
        ):
            self.assertIn(key, mapping["scalars"])

    def test_raises_for_unknown_year(self):
        with self.assertRaises(ValueError):
            PdfF8995.get_mapping(1999)

    def test_2021_inherits_2022_payload(self):
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022 (which itself
        # carries the line-6 Line6_ReadOrder-unwrapped path); 2021 inherits it.
        self.assertIs(PdfF8995.get_mapping(2021), PdfF8995.get_mapping(2022))


@unittest.skipUnless(
    (REPO_ROOT / "pdfs/federal/2021/f8995.pdf").exists(),
    "2021 Form 8995 template not present",
)
class PdfF89952021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Form 8995 template with distinctive values and read
    the cells back directly with pypdf — no soffice."""

    def test_distinctive_values_round_trip(self):
        scalars = PdfF8995.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct 8995 Filer",
            "taxpayer_ssn": "444-00-2021",
            "f8995_line_1_qbi": 51_000,
            "f8995_line_6_total_before_limit": 52_000,
            "f8995_line_15_qbi_deduction": 13_000,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f8995_2021.pdf"
            PdfFiller().fill(
                template_path=REPO_ROOT / "pdfs/federal/2021/f8995.pdf",
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))


@needs_libreoffice
class PdfF8995RoundTripTests(unittest.TestCase):
    @unittest.skipUnless(
        (REPO_ROOT / "pdfs/federal/2025/f8995.pdf").exists(),
        "f8995 template not present",
    )
    def test_emit_produces_nonempty_pdf(self):
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=50_000.0, qbi_amount=50_000.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results = orch.compute_federal(s)
            emitted = orch.emit_pdfs(s, results, Path(tmp))
            self.assertIn("f8995", emitted)
            self.assertGreater(emitted["f8995"].stat().st_size, 0)


_F8995_YEARS = (2021, 2022, 2023, 2024, 2025)

# compute key -> (IRS printed line, caption fragment that identifies that line).
#
# The expected line is derived from the FORM'S ARITHMETIC, never from the key's
# name. Four keys are named one conceptual tier too high in compute
# (tenforty/forms/f8995.py); their NAMES therefore lie about their printed line,
# which is exactly the defect this test pins. So `f8995_line_3_component` really
# prints on line 5 ("Qualified business income component. Multiply line 4 by
# 20%"), `f8995_line_4_reit_ptp` on line 6, `f8995_line_5_reit_ptp_component` on
# line 9, `f8995_line_6_total_before_limit` on line 10. The fragment — not the
# key string — is what identifies each target line, so this table survives the
# eventual key rename (ticket (cc)).
_F8995_EXPECTED = {
    "f8995_line_2_total_qbi": (2, "Total qualified business income or (loss)"),
    "f8995_line_3_component": (5, "Qualified business income component"),
    "f8995_line_4_reit_ptp": (6, "Qualified REIT dividends and publicly traded"),
    "f8995_line_5_reit_ptp_component": (9, "REIT and PTP component"),
    "f8995_line_6_total_before_limit": (10, "before the income limitation"),
    "f8995_line_11_taxable_income": (11, "Taxable income before qualified"),
    "f8995_line_12_net_capital_gain": (12, "net capital gain"),
    "f8995_line_13_subtract": (13, "Subtract line 12 from line 11"),
    "f8995_line_14_income_limit": (14, "Income limitation. Multiply line 13"),
    "f8995_line_15_qbi_deduction": (15, "Enter the smaller of"),
    "f8995_line_16_qbi_loss_carryforward": (
        16,
        "Total qualified business (loss) carryforward",
    ),
    # Combine lines. These keys are named by their TRUE FORM line.
    "f8995_line_3_prior_qbi_loss_carryforward": (
        3,
        "Qualified business net (loss) carryforward from the prior year",
    ),
    "f8995_line_4_total_qbi": (
        4,
        "Total qualified business income. Combine lines 2 and 3",
    ),
    "f8995_line_7_prior_reit_ptp_loss_carryforward": (
        7,
        "qualified PTP (loss) carryforward",
    ),
    "f8995_line_8_total_reit_ptp": (
        8,
        "Total qualified REIT dividends and PTP income",
    ),
}

# Scalar keys that are deliberately NOT line-placement-tested, each for a stated
# reason. The completeness guard requires every mapped scalar key to be either
# in _F8995_EXPECTED or here — so a key added later cannot silently escape.
_F8995_EXEMPT_KEYS = frozenset(
    {
        "taxpayer_name",     # header field ("Name(s) shown on return"), not a numbered line
        "taxpayer_ssn",      # header field (taxpayer id number), not a numbered line
        "f8995_line_1_qbi",  # line-1 TABLE cell (row i, col c); binds to "1i", not a plain numeric line
        "f8995_line_1i_name",  # line-1 TABLE cell (row i, col a); pinned by F8995Line1RowColumnTests
        "f8995_line_1i_tin",   # line-1 TABLE cell (row i, col b); pinned by F8995Line1RowColumnTests
    }
)


@unittest.skipUnless(
    all(
        (REPO_ROOT / f"pdfs/federal/{year}/f8995.pdf").exists()
        for year in _F8995_YEARS
    ),
    "Form 8995 templates for 2021–2025 not all present",
)
class F8995PlacementByCaptionTests(unittest.TestCase):
    """Pin each compute key to the PRINTED line it lands on, identified by that
    line's caption — not by the key's (in four cases, wrong) name.

    Expected-RED pending Task 3: the four misnamed keys print one tier too high
    and `f8995_line_16_qbi_loss_carryforward` is mapped nowhere, so
    `test_placement_by_line` fails for those five keys in every year until the
    mapping is corrected. The uniqueness and completeness guards are expected
    green — they protect the placement test, not the mapping.
    """

    @classmethod
    def setUpClass(cls):
        # Re-derive the field -> printed-line binding straight from each template
        # with the probe's caption-anchored method.
        cls.rows = {year: _probe.probe_year(year) for year in _F8995_YEARS}
        cls.by_path = {
            year: {r["full_path"]: r for r in rows}
            for year, rows in cls.rows.items()
        }
        # Distinct printed-line label -> the set of captions bound to it. Table
        # rows ("1i".."1v") are distinct labels here, so a fragment that leaked
        # into a column header would be caught as ambiguous.
        cls.line_captions = {}
        for year, rows in cls.rows.items():
            mapping: dict[str, set[str]] = {}
            for r in rows:
                if r["line"] is not None:
                    mapping.setdefault(r["line"], set()).add(r["caption"])
            cls.line_captions[year] = mapping

    def test_placement_by_line(self):
        """Each mapped field must sit on its expected printed line. EXPECTED-RED
        for the four misnamed keys (one tier high) and the unmapped line-16 key.
        """
        for year in _F8995_YEARS:
            scalars = PdfF8995.get_mapping(year)["scalars"]
            for key, (expected_line, frag) in _F8995_EXPECTED.items():
                with self.subTest(year=year, key=key):
                    # Explicit presence check so line-16's failure reads
                    # "unmapped", not KeyError.
                    self.assertIn(
                        key,
                        scalars,
                        f"{year}: {key} is unmapped — computed but placed in no "
                        f"PDF box (belongs on line {expected_line}: {frag!r})",
                    )
                    path = scalars[key]
                    row = self.by_path[year].get(path)
                    self.assertIsNotNone(
                        row,
                        f"{year}: {key} -> {path} matches no widget on the template",
                    )
                    self.assertEqual(
                        row["line"],
                        str(expected_line),
                        f"{year}: {key} prints on line {row['line']} but belongs "
                        f"on line {expected_line} ({frag!r})",
                    )

    # Why two tests, not one: placement is asserted by printed-line NUMBER
    # (test_placement_by_line); the caption fragment is enforced separately by
    # test_caption_fragments_are_unambiguous. On Form 8995 every numeric printed
    # line has exactly one captioned row (singleton caption sets, verified all
    # five years), so the two together pin compute-key -> line <-> caption. Do
    # NOT delete the uniqueness test as "redundant": it is what makes the caption
    # pin real and what survives ticket (cc)'s key rename.
    def test_caption_fragments_are_unambiguous(self):
        """Each caption fragment must identify EXACTLY the one printed line it is
        paired with. If a fragment matched two lines (or the wrong line), the
        placement test could bind the wrong line and pass falsely.
        """
        for year in _F8995_YEARS:
            for key, (expected_line, frag) in _F8995_EXPECTED.items():
                with self.subTest(year=year, key=key):
                    needle = frag.lower()
                    matched = sorted(
                        line
                        for line, caps in self.line_captions[year].items()
                        if any(needle in cap.lower() for cap in caps)
                    )
                    self.assertEqual(
                        matched,
                        [str(expected_line)],
                        f"{year}: fragment {frag!r} must identify exactly line "
                        f"{expected_line}; it matched printed lines {matched}",
                    )

    def test_every_scalar_key_is_placement_tested_or_exempt(self):
        """No mapped scalar key may silently escape placement testing: each must
        be in _F8995_EXPECTED or explicitly exempt.
        """
        for year in _F8995_YEARS:
            scalars = PdfF8995.get_mapping(year)["scalars"]
            for key in scalars:
                with self.subTest(year=year, key=key):
                    self.assertTrue(
                        key in _F8995_EXPECTED or key in _F8995_EXEMPT_KEYS,
                        f"{year}: mapped scalar key {key!r} is neither "
                        f"placement-tested (_F8995_EXPECTED) nor exempt "
                        f"(_F8995_EXEMPT_KEYS)",
                    )


# Fields deliberately left BLANK on the template, keyed by the printed-line
# label the probe binds them to. Each entry needs a reason; the enumeration test
# fails if a template field is neither mapped nor on a listed line, AND if a
# listed line has no unmapped field (so this list cannot go stale).
_F8995_BLANK_BY_DESIGN_LINES = {
    "1ii": "line-1 table rows ii-v: v1 is single-row (one aggregated source)",
    "1iii": "line-1 table rows ii-v: v1 is single-row (one aggregated source)",
    "1iv": "line-1 table rows ii-v: v1 is single-row (one aggregated source)",
    "1v": "line-1 table rows ii-v: v1 is single-row (one aggregated source)",
    "17": "total REIT/PTP loss carryforward: v1 models no REIT/PTP income "
          "(form line 6 is a constant 0), so there is nothing to carry forward",
}


@unittest.skipUnless(
    all(
        (REPO_ROOT / f"pdfs/federal/{year}/f8995.pdf").exists()
        for year in _F8995_YEARS
    ),
    "Form 8995 templates for 2021–2025 not all present",
)
class F8995FullTemplateEnumerationTests(unittest.TestCase):
    """Every fillable field on each year's template is either mapped or on an
    explicit blank-by-design line — an unmapped line can no longer be added
    (or left) silently."""

    def test_every_fillable_field_is_mapped_or_blank_by_design(self):
        for year in _F8995_YEARS:
            reader = PdfReader(str(REPO_ROOT / f"pdfs/federal/{year}/f8995.pdf"))
            fillable = {
                name for name, fld in (reader.get_fields() or {}).items()
                if fld.get("/FT") == "/Tx"
            }
            line_of = {r["full_path"]: r["line"] for r in _probe.probe_year(year)}
            mapped = set(PdfF8995.get_mapping(year)["scalars"].values())
            # Every mapped path must exist on the template.
            self.assertEqual(mapped - fillable, set(), f"{year}: stale mapping paths")
            unmapped = fillable - mapped
            lines_hit = set()
            for path in sorted(unmapped):
                with self.subTest(year=year, field=path):
                    line = line_of.get(path)
                    self.assertIn(
                        line, _F8995_BLANK_BY_DESIGN_LINES,
                        f"{year}: {path} (printed line {line!r}) is neither "
                        f"mapped nor blank-by-design",
                    )
                    lines_hit.add(line)
            with self.subTest(year=year, check="blank list not stale"):
                self.assertEqual(
                    lines_hit, set(_F8995_BLANK_BY_DESIGN_LINES),
                    f"{year}: blank-by-design lines with no unmapped field",
                )


@unittest.skipUnless(
    all(
        (REPO_ROOT / f"pdfs/federal/{year}/f8995.pdf").exists()
        for year in _F8995_YEARS
    ),
    "Form 8995 templates for 2021–2025 not all present",
)
class F8995Line1RowColumnTests(unittest.TestCase):
    """Row 1i col (a) = name and col (b) = TIN land on the right column."""

    def test_row_1i_name_and_tin_columns(self):
        for year in _F8995_YEARS:
            scalars = PdfF8995.get_mapping(year)["scalars"]
            by_path = {r["full_path"]: r for r in _probe.probe_year(year)}
            for key, fragment in (
                ("f8995_line_1i_name", "trade, business, or aggregation name"),
                ("f8995_line_1i_tin", "taxpayer identification number"),
            ):
                with self.subTest(year=year, key=key):
                    self.assertIn(key, scalars)
                    row = by_path[scalars[key]]
                    self.assertEqual(row["line"], "1i")
                    self.assertIn(fragment, row["caption"].lower())


class F8995CombineLinesRoundTripTests(unittest.TestCase):
    """Real compute output -> fill -> read back, per year: the printed form
    foots (line 4 visible, line 5 = 20% of it) and row 1i carries name/TIN."""

    def test_printed_lines_foot_and_row_1i_filled(self):
        from tests.test_f8995_compute import _scenario_with_qbi
        from tenforty.forms import f8995 as form_f8995

        for year in _F8995_YEARS:
            with self.subTest(year=year):
                s, upstream = _scenario_with_qbi(qbi=20_000.0)
                s.config.year = year
                out = form_f8995.compute(s, upstream=upstream)
                scalars = PdfF8995.get_mapping(year)["scalars"]
                with tempfile.TemporaryDirectory() as tmp:
                    dest = Path(tmp) / "f8995.pdf"
                    PdfFiller().fill(
                        template_path=REPO_ROOT / f"pdfs/federal/{year}/f8995.pdf",
                        output_path=dest, field_mapping=scalars, values=out,
                    )
                    read = {
                        n: (f.get("/V") or "")
                        for n, f in (PdfReader(str(dest)).get_fields() or {}).items()
                    }
                def v(key):
                    return read[scalars[key]]
                self.assertEqual(v("f8995_line_3_prior_qbi_loss_carryforward"), "0")
                self.assertEqual(v("f8995_line_4_total_qbi"), "20000")
                self.assertEqual(v("f8995_line_3_component"), "4000")  # form line 5
                self.assertEqual(v("f8995_line_7_prior_reit_ptp_loss_carryforward"), "0")
                self.assertEqual(v("f8995_line_8_total_reit_ptp"), "0")
                self.assertEqual(v("f8995_line_1i_name"), "Fake S-Corp Inc")
                self.assertEqual(v("f8995_line_1i_tin"), "00-0000000")


if __name__ == "__main__":
    unittest.main()
