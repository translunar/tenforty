# tests/test_stylesheet_extraction.py
"""IRS MeF stylesheet extraction (emit-verification harness spec §5).

The IRS publishes the XSL that renders an e-filed return as the printed
form. ``tenforty.declarations.stylesheet.extract`` reads, per line block,
the printed label, the line text and the e-file element(s) that fill it;
the committed ``tenforty/declarations/stylesheets/<form>_<year>.json`` files
are that extraction over the hash-pinned packages in ``manifest.PACKAGES``.
"""
import unittest

from tenforty.declarations import stylesheet
from tenforty.declarations.stylesheet import (
    StylesheetLine,
    extract,
    load,
    load_census,
)
from tenforty.declarations.stylesheets import manifest

YEARS = (2021, 2022, 2023, 2024, 2025)
_XSL_NS = 'xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'


def _doc(body: str, data_param: str = "") -> str:
    """Wrap an excerpt in a stylesheet root (the namespace is preserved)."""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<xsl:stylesheet {_XSL_NS} version="1.0">{data_param}'
            f'<xsl:template match="/"><div>{body}</div></xsl:template>'
            f'</xsl:stylesheet>')


# Verbatim from TY2025 IRS8995.xsl (package py2026r1.zip,
# PY2026R10/mef/Stylesheets/2025/IRS8995.xsl), lines 401-429: the balanced
# line-10 and line-11 blocks (the plan's 402-425 ends inside a
# call-template, so it is not well-formed on its own).
IRS8995_LINES_10_11 = """
					<div class="styStdDiv">
						<div class="styLNLeftNumBox">10</div>
						<div class="styLNDesc">
							Qualified business income deduction before the income limitation. Add lines 5 and 9
							<span class="sty8995DotLn">.......</span>
						</div>
						<div class="styLNRightNumBox">10</div>
						<div class="styLNAmountBox">
							<xsl:call-template name="PopulateAmount">
								<xsl:with-param name="TargetNode" select="$FormData/QBIDedBfrIncomeLimitationAmt"/>
							</xsl:call-template>
						</div>
					</div>
					<!-- Line 11 -->
					<div class="styStdDiv">
						<div class="styLNLeftNumBox">11</div>
						<div class="styLNDesc" style="width:98mm;">
							Taxable income before qualified business income deduction
							<span class="sty8995DotLn">.....</span>
						</div>
						<div class="styLNRightNumBox">11</div>
						<div class="styLNAmountBox">
							<xsl:call-template name="PopulateAmount">
								<xsl:with-param name="TargetNode" select="$FormData/TaxableIncomeBeforeQBIDedAmt"/>
							</xsl:call-template>
						</div>
						<div class="styLNRightNumBoxNBB" style="background-color:lightgrey;"></div>
						<div class="styLNAmountBoxNBB"></div>
					</div>
"""


def _block(label_class: str, label: str, desc: str, *elements: str,
           desc_class: str = "styLNDesc", var: str = "$FormData") -> str:
    targets = "".join(
        f'<div class="styLNAmountBox"><xsl:call-template name="PopulateAmount">'
        f'<xsl:with-param name="TargetNode" select="{var}/{e}"/>'
        f'</xsl:call-template></div>' for e in elements)
    return (f'<div class="styStdDiv"><div class="{label_class}">{label}</div>'
            f'<div class="{desc_class}">{desc}</div>{targets}</div>')


class ExtractLineBlockTests(unittest.TestCase):

    def test_irs8995_lines_10_and_11(self):
        lines = extract(_doc(IRS8995_LINES_10_11))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], StylesheetLine(
            "10",
            "Qualified business income deduction before the income "
            "limitation. Add lines 5 and 9",
            ("QBIDedBfrIncomeLimitationAmt",), ""))
        self.assertEqual(lines[1], StylesheetLine(
            "11", "Taxable income before qualified business income deduction",
            ("TaxableIncomeBeforeQBIDedAmt",), ""))

    def test_right_num_box_does_not_open_a_record(self):
        # The right-hand number box repeats the label beside the amount.
        labels = [ln.label for ln in extract(_doc(IRS8995_LINES_10_11))]
        self.assertEqual(labels, ["10", "11"])

    def test_targets_before_the_first_label_are_not_attributed(self):
        header = ('<div class="styNameBox"><xsl:call-template name="PopulateText">'
                  '<xsl:with-param name="TargetNode" select="$RtnHdrData/Name"/>'
                  '</xsl:call-template></div>')
        lines = extract(_doc(header + _block("styLNLeftNumBox", "1", "One", "AAmt")))
        self.assertEqual([ln.elements for ln in lines], [("AAmt",)])

    def test_dot_leaders_and_whitespace_normalize(self):
        lines = extract(_doc(_block(
            "styLNLeftNumBox", " 4 ",
            "Net  income.\n  Add lines 1 and 2 . . . . . . <span class=\"styDotLn\">...</span>",
            "NetAmt")))
        self.assertEqual(lines[0].label, "4")
        self.assertEqual(lines[0].text, "Net income. Add lines 1 and 2")

    def test_part_heading_becomes_the_page_section(self):
        body = ('<div class="styPartName">Part I</div>'
                '<div class="styPartDesc">Short-Term</div>'
                + _block("styLNLeftNumBox", "1", "One", "AAmt")
                + '<div class="styPartName">Part II</div>'
                + _block("styLNLeftNumBox", "1", "One again", "BAmt"))
        lines = extract(_doc(body))
        self.assertEqual([(ln.page_section, ln.label) for ln in lines],
                         [("Part I", "1"), ("Part II", "1")])


class MultiElementLineTests(unittest.TestCase):
    """Review Focus 2: two TargetNodes under one label keep both, in order."""

    def test_two_target_nodes_keep_both_in_document_order(self):
        lines = extract(_doc(_block(
            "styLNLeftNumBox", "3", "Amount and checkbox", "LineThreeAmt",
            "LineThreeInd")))
        self.assertEqual(lines[0].elements, ("LineThreeAmt", "LineThreeInd"))

    def test_three_target_nodes(self):
        lines = extract(_doc(_block(
            "styLNLeftNumBox", "7", "Two columns plus total", "ColAAmt",
            "ColBAmt", "TotalAmt")))
        self.assertEqual(lines[0].elements, ("ColAAmt", "ColBAmt", "TotalAmt"))


# Every label-box class the five pinned packages use in the forms tenforty
# emits (survey 2026-10-17, re-checked by test_pins_equal_the_committed_census
# against the class census recorded in each committed extraction).
SURVEYED_LABEL_CLASSES = frozenset({
    "styLNLeftNumBox", "styLNLeftNumBoxSD", "styLNLeftNumBoxBB",
    "styLNLeftLtrBox", "styLNLeftLtrBoxDD",
    "styIRS4562LNLeftNumBox", "styIRS8582LNLeftNumBox",
    "styIRS1120SLNLeftLtrBoxTD",
    "styIRS3115LNLeftNumBox", "styIRS3115LNLeftLtrBox",
    "IRS1120SScheduleK1_itemLabel",  # form-specific (K-1 box grid)
})
# Every description-box class the same forms use.
SURVEYED_DESC_CLASSES = frozenset({
    "styLNDesc", "styLnDesc", "sty1040Desc", "sty1040XDesc",
    "sty1040XLongDesc", "styIRS4562LNDesc", "styIRS8582LNDesc",
    "styIRS8949LNDesc",
})


def _census_union():
    labels, descs = set(), set()
    for year in YEARS:
        for form in manifest.XSL_NAME:
            lab, desc = load_census(form, year)
            labels |= set(lab)
            descs |= set(desc)
    return labels, descs
# styLN*Box classes that are NOT labels: amount boxes, the right-hand
# repeat of the label, the centered value box.
SURVEYED_NON_LABEL_CLASSES = frozenset({
    "styLNRightNumBox", "styLNRightNumBoxNBB", "styLNAmountBox",
    "styLNAmountBoxNBB", "styLNCtrNumBox",
})


class LeftNumBoxVariantTests(unittest.TestCase):

    def test_every_surveyed_label_class_opens_a_record(self):
        for cls in sorted(SURVEYED_LABEL_CLASSES):
            form = cls.split("_")[0] if "_" in cls else None
            with self.subTest(cls=cls):
                lines = extract(_doc(_block(cls, "2a", "Text", "XAmt")),
                                form_xsl=form)
                self.assertEqual([(ln.label, ln.elements) for ln in lines],
                                 [("2a", ("XAmt",))])
                self.assertTrue(stylesheet.is_label_class(cls, form))

    def test_label_pin_equals_the_committed_census(self):
        self.assertEqual(_census_union()[0], set(SURVEYED_LABEL_CLASSES))

    def test_form_specific_label_class_is_scoped_to_its_form(self):
        self.assertFalse(stylesheet.is_label_class(
            "IRS1120SScheduleK1_itemLabel"))
        self.assertFalse(stylesheet.is_label_class(
            "IRS1120SScheduleK1_itemLabel", "IRS1120S"))

    def test_class_with_extra_tokens_still_opens_a_record(self):
        lines = extract(_doc(_block(
            "styLNLeftNumBoxSD styGenericDiv", "5", "Text", "XAmt")))
        self.assertEqual(lines[0].label, "5")

    def test_non_label_boxes_never_open_a_record(self):
        for cls in sorted(SURVEYED_NON_LABEL_CLASSES):
            with self.subTest(cls=cls):
                self.assertFalse(stylesheet.is_label_class(cls))
                lines = extract(_doc(_block(cls, "9", "Text", "XAmt")))
                self.assertEqual(lines, ())


class DescClassTests(unittest.TestCase):
    """The line text comes from the Desc-family box, whatever the form calls
    it (styLNDesc, sty1040Desc, sty1040XLongDesc, styIRS4562LNDesc, ...)."""

    def test_desc_pin_equals_the_committed_census(self):
        self.assertEqual(_census_union()[1], set(SURVEYED_DESC_CLASSES))

    def test_desc_family_classes(self):
        for cls in sorted(SURVEYED_DESC_CLASSES):
            with self.subTest(cls=cls):
                lines = extract(_doc(_block(
                    "styLNLeftNumBox", "6", "Line six text", "SixAmt",
                    desc_class=cls)))
                self.assertEqual(lines[0].text, "Line six text")


class LineTextFallbackTests(unittest.TestCase):
    """Forms whose line text is not in a Desc-family box: the text comes
    from the label's first following sibling that prints words (Schedule C's
    styGenericDiv cell), or from the next cell when the label sits alone in
    a table cell (Form 4562 lines 31-36). Nested number and amount boxes
    contribute no words."""

    def test_generic_div_sibling_text(self):
        body = ('<div><div class="styLNLeftNumBox">8</div>'
                '<div class="styGenericDiv">Advertising'
                '<div class="styLNRightNumBox">8</div></div>'
                '<div class="styLNAmountBox"><xsl:call-template name="PopulateAmount">'
                '<xsl:with-param name="TargetNode" select="$FormData/AdvertisingAmt"/>'
                '</xsl:call-template></div></div>')
        lines = extract(_doc(body))
        self.assertEqual((lines[0].label, lines[0].text, lines[0].elements),
                         ("8", "Advertising", ("AdvertisingAmt",)))

    def test_label_alone_in_a_table_cell_reads_the_next_cell(self):
        body = ('<table><tr><td><div class="styLNLeftNumBox">32</div>'
                '<span class="styDotLn">...</span></td>'
                '<td>Property used more than 50% in a qualified business use</td>'
                '<td><xsl:call-template name="PopulateAmount">'
                '<xsl:with-param name="TargetNode" select="$FormData/QBUAmt"/>'
                '</xsl:call-template></td></tr></table>')
        lines = extract(_doc(body))
        self.assertEqual(lines[0].text,
                         "Property used more than 50% in a qualified business use")

    def test_desc_family_box_wins_over_the_sibling(self):
        lines = extract(_doc(
            '<div class="styLNLeftNumBox">2</div><div>Sibling words</div>'
            '<div class="styLNDesc">Described line</div>'))
        self.assertEqual(lines[0].text, "Described line")


class LabelShapeTests(unittest.TestCase):
    """A label-class box whose content is not label-shaped is a description
    styled with a label class (2025 Schedule B line 4), not a new line."""

    def test_description_in_a_label_class_box(self):
        body = ('<div class="styLNLeftNumBoxBB">4</div>'
                '<div class="styLNLeftNumBoxBB">Subtract line 3 from line 2</div>'
                '<div class="styLNAmountBox"><xsl:call-template name="PopulateAmount">'
                '<xsl:with-param name="TargetNode" select="$FormData/FourAmt"/>'
                '</xsl:call-template></div>')
        lines = extract(_doc(body))
        self.assertEqual([(ln.label, ln.text, ln.elements) for ln in lines],
                         [("4", "Subtract line 3 from line 2", ("FourAmt",))])

    def test_label_shapes(self):
        for good in ("1", "10a", "b", "A.", "(a)", "6c(1)", "43"):
            with self.subTest(label=good):
                self.assertRegex(good, stylesheet.LABEL_SHAPE)
        for bad in ("Subtract line 3", "Note:", "Part I"):
            with self.subTest(label=bad):
                self.assertNotRegex(bad, stylesheet.LABEL_SHAPE)

    def test_repeated_element_is_kept_once_in_first_order(self):
        lines = extract(_doc(_block(
            "styLNLeftNumBox", "D", "Employer ID", "EIN", "EIN", "OtherInd")))
        self.assertEqual(lines[0].elements, ("EIN", "OtherInd"))


class DataRootTests(unittest.TestCase):
    """The form's own data variable is stripped; every other source of a
    value (the return header, a repeating row's node) stays visible."""

    def test_form_data_named_formdata_is_stripped(self):
        param = '<xsl:param name="FormData" select="$RtnDoc/IRS8995"/>'
        body = (_block("styLNLeftNumBox", "10", "Ten", "QBIAmt")
                + _block("styLNLeftNumBox", "11", "Eleven", "Name",
                         var="$RtnHdrData"))
        lines = extract(_doc(body, data_param=param), form_xsl="IRS8995")
        self.assertEqual([ln.elements for ln in lines],
                         [("QBIAmt",), ("$RtnHdrData/Name",)])

    def test_real_extractions_strip_both_prefix_styles(self):
        f8995 = {ln.label: ln for ln in load("f8995", 2025)}
        self.assertEqual(f8995["10"].elements, ("QBIDedBfrIncomeLimitationAmt",))
        f4562 = {(ln.page_section, ln.label): ln for ln in load("4562", 2025)}
        self.assertEqual(f4562[("Part I", "1")].elements,
                         ("MaximumDollarLimitationAmt",))

    def test_form_data_param_is_stripped_and_others_kept(self):
        param = '<xsl:param name="IRS4562Data" select="$RtnDoc/IRS4562"/>'
        body = (_block("styLNLeftNumBox", "1", "One", "MaxAmt",
                       var="$IRS4562Data")
                + _block("styLNLeftNumBox", "2", "Two", "Name",
                         var="$RtnHdrData"))
        lines = extract(_doc(body, data_param=param), form_xsl="IRS4562")
        self.assertEqual([ln.elements for ln in lines],
                         [("MaxAmt",), ("$RtnHdrData/Name",)])


# Verbatim from TY2025 IRS1120SScheduleK1.xsl (py2026r1.zip,
# PY2026R10/mef/Stylesheets/2025/IRS1120SScheduleK1.xsl), lines 597-615.
K1_LINE_1 = """
							<div style="width: 46.5mm;">
								<div class="IRS1120SScheduleK1_itemLabel" style="width:5.3mm;text-align: center;">1</div>
								<div style="width:40.3mm;">Ordinary business income (loss)
								</div>
								<div class="IRS1120SScheduleK1_codeBox" style="width:5.3mm;height: 5mm;"/>
								<div class="IRS1120SScheduleK1_amountBox" style="width:40.3mm;height: 5mm;padding-top:2mm;">
									<span style="float:left;padding-left:2px;">
										<!-- Schedule K-1 Part III Line 1 Push Pin -->
										<xsl:call-template name="SetFormLinkInline">
											<xsl:with-param name="TargetNode" select="$FormData/OrdinaryIncomeLossAmt"/>
										</xsl:call-template>
									</span>
									<span style="float:right;">
										<xsl:call-template name="PopulateAmount">
											<xsl:with-param name="TargetNode" select="$FormData/OrdinaryIncomeLossAmt"/>
										</xsl:call-template>
									</span>
								</div>
							</div>
"""


class ScheduleK1ShapeTests(unittest.TestCase):
    """The K-1 box grid: item label -> unclassed text div -> amount box."""

    def test_verbatim_k1_line_1(self):
        lines = extract(_doc(K1_LINE_1), form_xsl="IRS1120SScheduleK1")
        self.assertEqual(lines, (StylesheetLine(
            "1", "Ordinary business income (loss)",
            ("OrdinaryIncomeLossAmt",), ""),))

    def test_without_the_form_name_the_grid_is_not_read(self):
        self.assertEqual(extract(_doc(K1_LINE_1)), ())

    def test_committed_k1_extraction_line_1_every_year(self):
        for year in YEARS:
            with self.subTest(year=year):
                first = load("f1120s_k1", year)[0]
                self.assertEqual(
                    (first.label, first.text, first.elements,
                     first.page_section),
                    ("1", "Ordinary business income (loss)",
                     ("OrdinaryIncomeLossAmt",), "Part III"))


class CoverageOfOurFormsTests(unittest.TestCase):
    """Every form tenforty emits has a committed extraction for every year;
    a form-year with nothing extracted is an explicit recorded gap, never a
    skip, and the gap list is exactly what manifest.GAPS records."""

    def test_every_form_year_is_extracted_or_a_recorded_gap(self):
        empty = set()
        for year in YEARS:
            for form in sorted(manifest.XSL_NAME):
                with self.subTest(form=form, year=year):
                    lines = load(form, year)
                    if (form, year) in manifest.GAPS:
                        self.assertEqual(lines, ())
                        empty.add((form, year))
                        continue
                    self.assertGreater(
                        len(lines), 0,
                        f"{manifest.XSL_NAME[form]}.xsl TY{year} (package "
                        f"{manifest.PACKAGES[year].url}) extracted nothing "
                        "and is not a recorded gap")
                    if not lines:
                        empty.add((form, year))
        self.assertEqual(empty, set(manifest.GAPS))

    def test_the_recorded_gaps_are_the_8949_transaction_table(self):
        self.assertEqual(sorted(manifest.GAPS),
                         [("f8949", year) for year in YEARS])

    def test_every_recorded_gap_has_a_reason(self):
        for key, reason in manifest.GAPS.items():
            with self.subTest(gap=key):
                self.assertIn(key[0], manifest.XSL_NAME)
                self.assertIn(key[1], YEARS)
                self.assertGreater(len(reason.strip()), 20)

    def test_load_round_trips_the_dataclass(self):
        lines = load("f8995", 2025)
        self.assertTrue(all(isinstance(ln, StylesheetLine) for ln in lines))
        labels = {ln.label: ln for ln in lines}
        self.assertEqual(labels["10"].elements,
                         ("QBIDedBfrIncomeLimitationAmt",))


class PinnedHashTests(unittest.TestCase):

    def test_ty2025_package_is_the_pinned_one(self):
        self.assertEqual(
            manifest.PACKAGES[2025].sha256,
            "903d2d186da0615f626d0737b45933d8007628084be820a3d669d9ff7779b61a")
        self.assertTrue(manifest.PACKAGES[2025].url.endswith("/py2026r1.zip"))

    def test_every_year_has_a_64_hex_pin_url_and_folder(self):
        self.assertEqual(sorted(manifest.PACKAGES), list(YEARS))
        for year, pkg in manifest.PACKAGES.items():
            with self.subTest(year=year):
                self.assertRegex(pkg.sha256, r"^[0-9a-f]{64}$")
                self.assertTrue(pkg.url.startswith(
                    "https://www.irs.gov/pub/irs-schema/py"))
                self.assertIn(f"py{year + 1}r", pkg.url)
                self.assertTrue(pkg.folder)
        self.assertEqual(len({p.sha256 for p in manifest.PACKAGES.values()}), 5)

    def test_stylesheet_dir_handles_the_unwrapped_package(self):
        self.assertEqual(manifest.stylesheet_dir(2024), "mef/Stylesheets/2024")
        self.assertEqual(manifest.stylesheet_dir(2025),
                         "PY2026R10/mef/Stylesheets/2025")
