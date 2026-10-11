"""Direct deposit of a refund: Form 1040 lines 35b-35d, Form 540 line 116.

Three optional scenario config fields, all or none:

  refund_routing_number   quoted string, 9 digits, ABA checksum
  refund_account_number   quoted string, 4-17 digits
  refund_account_type     "checking" or "savings"

They are return-level intent: "where a refund exists, deposit it here". The
1040 and the 540 share them, and each form decides for itself:

  the form shows a refund  -> its deposit boxes print
  the form shows no refund -> its deposit boxes stay blank (no refusal: a
                              federal refund beside a California balance due
                              is an ordinary return, and bank details on a
                              balance-due form would be an error)

Each form carries the twin pair pinning both halves. Fields set on a return
with no refund on either form therefore do nothing, by design.

Form 540 line 116 also has an amount box; with the whole refund going to one
account it carries the line 115 figure, from the same derivation as line 115.
Line 117 (a second account, for a split refund) is out of scope and stays
blank.

An amendment packet (Form 1040-X, amended 540) refuses the fields outright:
the IRS does not direct-deposit a paper-filed amended return.

Fixture numbers are fictional by construction:
  ROUTING 991234561 -- the ABA checksum is
      3*(d1+d4+d7) + 7*(d2+d5+d8) + (d3+d6+d9) = 0 mod 10;
      3*(9+2+5) + 7*(9+3+6) + (1+4+1) = 48 + 126 + 6 = 180.
      Its first two digits, 99, are outside every Federal Reserve routing
      prefix range (00-12, 21-32, 61-72, 80), so no bank has it.
  ACCOUNT 000123456789 -- leading zeros on purpose: they must survive.

Every field path is a literal, anchored to each year's blank template by the
TemplateAnchor classes -- never read from the mapping modules.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.attestations import (
    enforce_named_refusal, enforce_scoped_refusals,
)
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_f540 import PdfF540
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._ca_emit_helpers import emit_ca, make_ca_scenario
from tests.helpers import REPO_ROOT, SPREADSHEETS_DIR, make_simple_scenario

YEARS = (2021, 2022, 2023, 2024, 2025)

ROUTING = "991234561"
ACCOUNT = "000123456789"

_P2 = "topmostSubform[0].Page2[0]"
F1040 = {
    2021: {
        "routing": "topmostSubform[0].Page2[0].RoutingNo[0].f2_27[0]",
        "account": "topmostSubform[0].Page2[0].AccountNo[0].f2_28[0]",
        "checking": "topmostSubform[0].Page2[0].c2_06[0]",
        "savings": "topmostSubform[0].Page2[0].c2_06[1]",
    },
    2022: {
        "routing": "topmostSubform[0].Page2[0].RoutingNo[0].f2_25[0]",
        "account": "topmostSubform[0].Page2[0].AccountNo[0].f2_26[0]",
        "checking": "topmostSubform[0].Page2[0].c2_05[0]",
        "savings": "topmostSubform[0].Page2[0].c2_05[1]",
    },
    2023: {
        "routing": "topmostSubform[0].Page2[0].RoutingNo[0].f2_25[0]",
        "account": "topmostSubform[0].Page2[0].AccountNo[0].f2_26[0]",
        "checking": "topmostSubform[0].Page2[0].c2_5[0]",
        "savings": "topmostSubform[0].Page2[0].c2_5[1]",
    },
    2024: {
        "routing": "topmostSubform[0].Page2[0].RoutingNo[0].f2_25[0]",
        "account": "topmostSubform[0].Page2[0].AccountNo[0].f2_26[0]",
        "checking": "topmostSubform[0].Page2[0].c2_5[0]",
        "savings": "topmostSubform[0].Page2[0].c2_5[1]",
    },
    2025: {
        "routing": "topmostSubform[0].Page2[0].RoutingNo[0].f2_32[0]",
        "account": "topmostSubform[0].Page2[0].AccountNo[0].f2_33[0]",
        "checking": "topmostSubform[0].Page2[0].c2_16[0]",
        "savings": "topmostSubform[0].Page2[0].c2_16[1]",
    },
}
F1040_CHECKING_ON, F1040_SAVINGS_ON = "/1", "/2"

# Form 540 line 116 (and the line 115 refund cell its amount box repeats).
# `type` is the one radio field for 2021-2024 and (checking box, savings box)
# for 2025; `on` is (checking, savings) states.
F540 = {
    2021: {"routing": "5011", "account": "5013", "amount": "5010",
           "line_115": "5009", "line_99": "3020",
           "type": ("5012 RB",), "on": ("/0", "/1")},
    2022: {"routing": "5009", "account": "5011", "amount": "5012",
           "line_115": "5008", "line_99": "4004",
           "type": ("5010 RB",), "on": ("/0", "/1")},
    2023: {"routing": "5009", "account": "5011", "amount": "5012",
           "line_115": "5008", "line_99": "4004",
           "type": ("5010 RB",), "on": ("/0", "/1")},
    2024: {"routing": "540-5009", "account": "540-5011", "amount": "540-5008",
           "line_115": "540-5007", "line_99": "540-4004",
           "type": ("540-5010 RB",), "on": ("/Checking", "/Savings")},
    2025: {"routing": "540_form_5008", "account": "540_form_5010",
           "amount": "540_form_5011", "line_115": "540_form_5007",
           "line_99": "540_form_4004",
           "type": ("540_form_5009A CB", "540_form_5009B CB"),
           "on": ("/Yes", "/Yes")},
}
# Line 117 (the second account of a split refund): never filled.
F540_LINE_117 = {
    2021: ("5014", "5015", "5016 RB", "5017"),
    2022: ("5013", "5014 RB", "5015", "5016"),
    2023: ("5013", "5014 RB", "5015", "5016"),
    2024: ("540-5012", "540-5013", "540-5014 RB", "540-5015"),
    2025: ("540_form_5012", "540_form_5013A CB", "540_form_5013B CB",
           "540_form_5014", "540_form_5015"),
}


def _f1040_template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"


def _f540_template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "california" / str(year) / "f540.pdf"


def _widgets(page) -> list[dict]:
    """Every widget on a page: full field name, rect, inherited /MaxLen and
    /TU, and its own on-states."""
    found = []
    for annotation in page.get("/Annots", []):
        annotation = annotation.get_object()
        if annotation.get("/Subtype") != "/Widget":
            continue
        names, max_len, tooltip, node = [], None, None, annotation
        while node is not None:
            if "/T" in node:
                names.append(node["/T"])
            max_len = max_len or node.get("/MaxLen")
            tooltip = tooltip or node.get("/TU")
            node = node.get("/Parent")
            node = node.get_object() if node is not None else None
        left, bottom, right, top = (float(v) for v in annotation["/Rect"])
        appearance = annotation.get("/AP", {}).get("/N", {})
        states = sorted(k for k in appearance.keys() if k != "/Off") \
            if hasattr(appearance, "keys") else []
        found.append({
            "name": ".".join(reversed(names)), "left": left, "right": right,
            "bottom": bottom, "top": top, "max_len": max_len,
            "tooltip": str(tooltip or ""), "states": states})
    return found


def _text_positions(page) -> list[tuple[str, float, float]]:
    found = []

    def visit(text, cm, tm, _font_dict, _font_size):
        if text.strip():
            found.append((text.strip(), tm[4] + cm[4], tm[5] + cm[5]))

    page.extract_text(visitor_text=visit)
    return found


class TemplateAnchor1040Tests(unittest.TestCase):
    """What each blank Form 1040 says its line 35 widgets are."""

    def _page(self, year):
        return PdfReader(str(_f1040_template(year))).pages[1]

    def test_routing_and_account_are_the_templates_own_named_comb_fields(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_name = {w["name"]: w for w in _widgets(self._page(year))}
                routing = by_name[F1040[year]["routing"]]
                account = by_name[F1040[year]["account"]]
                self.assertIn(".RoutingNo[0].", routing["name"])
                self.assertIn(".AccountNo[0].", account["name"])
                self.assertEqual(routing["max_len"], 9)
                self.assertEqual(account["max_len"], 17)
                # Exactly one widget in each named container.
                names = list(by_name)
                self.assertEqual(
                    [n for n in names if ".RoutingNo[0]." in n],
                    [F1040[year]["routing"]])
                self.assertEqual(
                    [n for n in names if ".AccountNo[0]." in n],
                    [F1040[year]["account"]])

    def test_routing_and_account_sit_on_their_printed_rows(self):
        for year in YEARS:
            with self.subTest(year=year):
                page = self._page(year)
                by_name = {w["name"]: w for w in _widgets(page)}
                text = _text_positions(page)
                for key, label in (("routing", "Routing number"),
                                   ("account", "Account number")):
                    rows = [y for t, _x, y in text if t == label]
                    self.assertEqual(len(rows), 1, (label, rows))
                    widget = by_name[F1040[year][key]]
                    self.assertTrue(
                        widget["bottom"] - 2 <= rows[0] <= widget["top"],
                        (label, rows[0], widget))

    def test_the_savings_box_is_the_one_beside_the_word_savings(self):
        """The type boxes sit immediately left of their words. "Savings" is
        located in every year; "Checking" is the other box of the pair and
        sits to its left."""
        for year in YEARS:
            with self.subTest(year=year):
                page = self._page(year)
                by_name = {w["name"]: w for w in _widgets(page)}
                checking = by_name[F1040[year]["checking"]]
                savings = by_name[F1040[year]["savings"]]
                found = [(x, y) for t, x, y in _text_positions(page)
                         if t == "Savings"]
                self.assertEqual(len(found), 1, found)
                label_x, label_y = found[0]
                on_the_row = [
                    w for w in by_name.values()
                    if w["states"] and w["bottom"] - 3 <= label_y <= w["top"] + 3]
                self.assertEqual(
                    sorted(w["name"] for w in on_the_row),
                    sorted([checking["name"], savings["name"]]))
                self.assertTrue(0 < label_x - savings["right"] < 10)
                self.assertLess(checking["right"], savings["left"])
                self.assertEqual(checking["states"], [F1040_CHECKING_ON])
                self.assertEqual(savings["states"], [F1040_SAVINGS_ON])

    def test_the_word_checking_is_printed_before_the_word_savings(self):
        for year in YEARS:
            with self.subTest(year=year):
                words = [t for t, _x, _y in _text_positions(self._page(year))
                         if t in ("Checking", "Savings")]
                self.assertEqual(words, ["Checking", "Savings"])


class TemplateAnchor540Tests(unittest.TestCase):
    """Each Form 540 line 116 widget, by the template's own tooltip."""

    def _by_name(self, year):
        found: dict[str, list[dict]] = {}
        for page in PdfReader(str(_f540_template(year))).pages:
            for widget in _widgets(page):
                found.setdefault(widget["name"], []).append(widget)
        return found

    def test_routing_and_account_tooltips_name_line_116(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_name = self._by_name(year)
                (routing,) = by_name[F540[year]["routing"]]
                (account,) = by_name[F540[year]["account"]]
                self.assertIn("Line 116.", routing["tooltip"])
                self.assertIn("routing number", routing["tooltip"])
                self.assertEqual(routing["max_len"], 9)
                self.assertEqual(
                    account["tooltip"].strip(), "Line 116. Account number.")

    def test_type_control_tooltips_and_states(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_name = self._by_name(year)
                checking_on, savings_on = F540[year]["on"]
                if len(F540[year]["type"]) == 1:
                    kids = by_name[F540[year]["type"][0]]
                    self.assertEqual(len(kids), 2)
                    for kid in kids:
                        self.assertIn(
                            "Line 116. Account type.", kid["tooltip"])
                    upper, lower = sorted(
                        kids, key=lambda w: w["bottom"], reverse=True)
                    # "Checking" is printed above "Savings" on the form.
                    self.assertEqual(upper["states"], [checking_on])
                    self.assertEqual(lower["states"], [savings_on])
                else:
                    (checking,) = by_name[F540[year]["type"][0]]
                    (savings,) = by_name[F540[year]["type"][1]]
                    self.assertIn("Line 116. Account type.",
                                  checking["tooltip"])
                    self.assertIn("Checking.", checking["tooltip"])
                    self.assertIn("Line 116. Account type.",
                                  savings["tooltip"])
                    self.assertIn("Savings.", savings["tooltip"])
                    self.assertEqual(checking["states"], [checking_on])
                    self.assertEqual(savings["states"], [savings_on])

    def test_checking_is_printed_above_savings(self):
        """Holds the 2021-2024 radio's upper-is-checking reading: on the
        page with line 116, each "Checking" is above its "Savings"."""
        for year in YEARS:
            with self.subTest(year=year):
                page = PdfReader(str(_f540_template(year))).pages[4]
                text = _text_positions(page)
                checking = sorted(
                    (y for t, _x, y in text if t == "Checking"), reverse=True)
                savings = sorted(
                    (y for t, _x, y in text if t == "Savings"), reverse=True)
                self.assertEqual((len(checking), len(savings)), (2, 2))
                # Line 116's pair is the upper one.
                self.assertGreater(checking[0], savings[0])
                self.assertGreater(savings[0], checking[1])

    def test_amount_box_and_line_115_tooltips(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_name = self._by_name(year)
                (amount,) = by_name[F540[year]["amount"]]
                self.assertIn("All or the following amount of my refund",
                              amount["tooltip"])
                self.assertNotIn("Line 117", amount["tooltip"])
                (line_115,) = by_name[F540[year]["line_115"]]
                self.assertIn("Line 115. Refund or no amount due",
                              line_115["tooltip"])
                (line_99,) = by_name[F540[year]["line_99"]]
                self.assertIn("Line 99. Overpaid tax available this year",
                              line_99["tooltip"])

    def test_line_117_is_other_widgets(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_name = self._by_name(year)
                ours = {F540[year]["routing"], F540[year]["account"],
                        F540[year]["amount"], *F540[year]["type"]}
                for name in F540_LINE_117[year]:
                    self.assertNotIn(name, ours)
                    self.assertIn("Line 117", by_name[name][0]["tooltip"])


def _with_deposit(scenario, *, routing=ROUTING, account=ACCOUNT,
                  account_type="checking", **config_changes):
    return dataclasses.replace(scenario, config=dataclasses.replace(
        scenario.config, refund_routing_number=routing,
        refund_account_number=account, refund_account_type=account_type,
        **config_changes))


def _federal(year: int, *, withheld: float = 30_000.0):
    """A single W-2 filer; 30,000 withheld on 100,000 of wages is a refund,
    0 withheld is a balance due."""
    base = make_simple_scenario()
    w2 = dataclasses.replace(base.w2s[0], federal_tax_withheld=withheld)
    return dataclasses.replace(
        base, w2s=[w2], config=dataclasses.replace(
            base.config, year=year, first_name="Test", last_name="Filer",
            ssn="000-00-0000", acknowledges_no_source_documents=True))


class Mapping1040Tests(unittest.TestCase):
    def test_keys_map_to_the_anchored_literals(self):
        for year in YEARS:
            mapping = Pdf1040.get_mapping(year)
            states = Pdf1040.get_checkbox_states(year)
            with self.subTest(year=year):
                self.assertEqual(
                    mapping.get("refund_routing_number"),
                    F1040[year]["routing"])
                self.assertEqual(
                    mapping.get("refund_account_number"),
                    F1040[year]["account"])
                self.assertEqual(
                    mapping.get("refund_account_type_checking"),
                    F1040[year]["checking"])
                self.assertEqual(
                    mapping.get("refund_account_type_savings"),
                    F1040[year]["savings"])
                self.assertEqual(
                    states.get("refund_account_type_checking"),
                    F1040_CHECKING_ON)
                self.assertEqual(
                    states.get("refund_account_type_savings"),
                    F1040_SAVINGS_ON)


def _values(pdf_path) -> dict[str, str]:
    return {name: str(field.get("/V") or "")
            for name, field in
            (PdfReader(str(pdf_path)).get_fields() or {}).items()}


class _FederalEmitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self._n = 0

    def _emit(self, scenario) -> tuple[dict, dict]:
        self._n += 1
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.tmp / f"work{self._n}")
        results = orchestrator.compute_federal(scenario)
        emitted = orchestrator.emit_pdfs(
            scenario, results, self.tmp / f"out{self._n}")
        return results, _values(emitted["1040"])


class Emitted1040Tests(_FederalEmitCase):
    def test_refund_return_prints_routing_type_and_account(self):
        for year in YEARS:
            for account_type, on, off in (
                    ("checking", "checking", "savings"),
                    ("savings", "savings", "checking")):
                with self.subTest(year=year, account_type=account_type):
                    results, values = self._emit(_with_deposit(
                        _federal(year), account_type=account_type))
                    self.assertGreater(results["refund"], 0)
                    paths = F1040[year]
                    self.assertEqual(values[paths["routing"]], ROUTING)
                    self.assertEqual(values[paths["account"]], ACCOUNT)
                    on_state = (F1040_CHECKING_ON if on == "checking"
                                else F1040_SAVINGS_ON)
                    self.assertEqual(values[paths[on]], on_state)
                    self.assertIn(values[paths[off]], ("", "/Off"))

    def test_without_the_fields_the_boxes_stay_blank(self):
        """The twin: same refund return, no deposit fields."""
        for year in YEARS:
            with self.subTest(year=year):
                results, values = self._emit(_federal(year))
                self.assertGreater(results["refund"], 0)
                paths = F1040[year]
                self.assertEqual(values[paths["routing"]], "")
                self.assertEqual(values[paths["account"]], "")
                self.assertIn(values[paths["checking"]], ("", "/Off"))
                self.assertIn(values[paths["savings"]], ("", "/Off"))


class NoRefund1040Tests(_FederalEmitCase):
    """The other half of the twin: the fields are set, the form shows no
    refund, and every deposit box is provably blank."""

    def test_balance_due_return_prints_none_of_the_fields(self):
        for year in YEARS:
            for account_type in ("checking", "savings"):
                with self.subTest(year=year, account_type=account_type):
                    results, values = self._emit(_with_deposit(
                        _federal(year, withheld=0.0),
                        account_type=account_type))
                    self.assertEqual(results["refund"], 0)
                    self.assertGreater(results["amount_owed"], 0)
                    paths = F1040[year]
                    self.assertEqual(values[paths["routing"]], "")
                    self.assertEqual(values[paths["account"]], "")
                    self.assertIn(values[paths["checking"]], ("", "/Off"))
                    self.assertIn(values[paths["savings"]], ("", "/Off"))
                    self.assertEqual(
                        [name for name, value in values.items()
                         if ROUTING in value or ACCOUNT in value], [])


class Mapping540Tests(unittest.TestCase):
    def test_line_116_cells_are_gated_derivations_not_plain_mappings(self):
        """A plain key -> cell mapping would print the numbers whether or
        not the return shows a refund. Each line 116 cell is instead a
        derivation at the anchored literal, and no `f540_refund_*` key is
        mapped straight to a cell."""
        for year in YEARS:
            with self.subTest(year=year):
                mapping = PdfF540.get_mapping(year)
                derivations = PdfF540.get_derivations(year)
                self.assertEqual(
                    [key for key in mapping if key.startswith("f540_refund_")],
                    [])
                paths = F540[year]
                for name in (paths["routing"], paths["account"],
                             paths["amount"], *paths["type"]):
                    self.assertIn(name, derivations)
                    self.assertNotIn(name, mapping.values())

    def test_nothing_maps_or_derives_line_117(self):
        for year in YEARS:
            with self.subTest(year=year):
                targets = (set(PdfF540.get_mapping(year).values())
                           | set(PdfF540.get_derivations(year)))
                for name in F540_LINE_117[year]:
                    self.assertNotIn(name, targets)

    def test_the_amount_box_is_the_line_115_derivation_itself(self):
        """Not a second computation: for any results, the amount box's
        derivation returns what the line 115 derivation returns when the
        fields are set, and nothing when they are not."""
        for year in YEARS:
            derivations = PdfF540.get_derivations(year)
            amount = derivations[F540[year]["amount"]]
            line_115 = derivations[F540[year]["line_115"]]
            scenario = _with_deposit(
                make_ca_scenario(year, state_tax_withheld=9_000.0))
            results, _pdfs = emit_ca(scenario)
            with self.subTest(year=year):
                self.assertGreater(line_115(results), 0)
                self.assertEqual(amount(results), line_115(results))
                bare = {k: v for k, v in results.items()
                        if not k.startswith("f540_refund_")}
                self.assertIsNone(amount(bare))


class Emitted540Tests(unittest.TestCase):
    def test_refund_return_prints_routing_type_and_account(self):
        for year in YEARS:
            for index, account_type in enumerate(("checking", "savings")):
                with self.subTest(year=year, account_type=account_type):
                    scenario = _with_deposit(
                        make_ca_scenario(year, state_tax_withheld=9_000.0),
                        account_type=account_type)
                    _results, pdfs = emit_ca(scenario)
                    values = _values(pdfs["f540"])
                    paths = F540[year]
                    self.assertEqual(values[paths["routing"]], ROUTING)
                    self.assertEqual(values[paths["account"]], ACCOUNT)
                    if len(paths["type"]) == 1:
                        self.assertEqual(
                            values[paths["type"][0]], paths["on"][index])
                    else:
                        self.assertEqual(
                            values[paths["type"][index]], paths["on"][index])
                        self.assertIn(
                            values[paths["type"][1 - index]], ("", "/Off"))
                    self.assertNotEqual(values[paths["line_115"]], "")
                    self.assertEqual(
                        values[paths["amount"]], values[paths["line_115"]])
                    for name in F540_LINE_117[year]:
                        self.assertIn(values[name], ("", "/Off"), name)

    def test_line_116_amount_follows_line_115_when_it_differs_from_line_99(
            self):
        """Interest and penalties (line 112) come out of the refund, so
        line 115 is 125 less than the line 99 overpayment. The deposit
        amount is the line 115 figure -- a gate or an amount wired to line
        99 prints the larger number here."""
        for year in YEARS:
            with self.subTest(year=year):
                scenario = _with_deposit(
                    make_ca_scenario(year, state_tax_withheld=9_000.0))
                _results, pdfs = emit_ca(
                    scenario, ca540={"interest_and_penalties": 125.0})
                values = _values(pdfs["f540"])
                paths = F540[year]
                line_99 = int(values[paths["line_99"]].replace(",", ""))
                line_115 = int(values[paths["line_115"]].replace(",", ""))
                self.assertEqual(line_99 - line_115, 125)
                self.assertEqual(
                    values[paths["amount"]], values[paths["line_115"]])
                self.assertNotEqual(
                    values[paths["amount"]], values[paths["line_99"]])
                self.assertEqual(values[paths["routing"]], ROUTING)

    def test_interest_that_consumes_the_overpayment_blanks_line_116(self):
        """Line 99 shows an overpayment, but line 112 is larger, so the
        return owes (line 114) and line 115 is blank: no deposit boxes,
        though line 99 alone would have said "refund"."""
        for year in YEARS:
            with self.subTest(year=year):
                scenario = _with_deposit(
                    make_ca_scenario(year, state_tax_withheld=9_000.0))
                _results, pdfs = emit_ca(
                    scenario, ca540={"interest_and_penalties": 50_000.0})
                values = _values(pdfs["f540"])
                paths = F540[year]
                self.assertGreater(
                    int(values[paths["line_99"]].replace(",", "")), 0)
                self.assertEqual(values[paths["line_115"]], "")
                self.assertEqual(values[paths["routing"]], "")
                self.assertEqual(values[paths["account"]], "")
                self.assertEqual(values[paths["amount"]], "")
                for name in paths["type"]:
                    self.assertIn(values[name], ("", "/Off"))

    def test_without_the_fields_line_116_stays_blank(self):
        for year in YEARS:
            with self.subTest(year=year):
                _results, pdfs = emit_ca(
                    make_ca_scenario(year, state_tax_withheld=9_000.0))
                values = _values(pdfs["f540"])
                paths = F540[year]
                self.assertNotEqual(values[paths["line_115"]], "")
                self.assertEqual(values[paths["routing"]], "")
                self.assertEqual(values[paths["account"]], "")
                self.assertEqual(values[paths["amount"]], "")
                for name in paths["type"]:
                    self.assertIn(values[name], ("", "/Off"))


class NoRefund540Tests(unittest.TestCase):
    """The other half of the twin: the fields are set, the 540 shows no
    refund, and every line 116 box is provably blank."""

    def test_balance_due_return_prints_none_of_the_fields(self):
        for year in YEARS:
            for account_type in ("checking", "savings"):
                with self.subTest(year=year, account_type=account_type):
                    _results, pdfs = emit_ca(_with_deposit(
                        make_ca_scenario(year, state_tax_withheld=0.0),
                        account_type=account_type))
                    values = _values(pdfs["f540"])
                    paths = F540[year]
                    self.assertEqual(values[paths["line_115"]], "")
                    self.assertEqual(values[paths["routing"]], "")
                    self.assertEqual(values[paths["account"]], "")
                    self.assertEqual(values[paths["amount"]], "")
                    for name in paths["type"]:
                        self.assertIn(values[name], ("", "/Off"))
                    self.assertEqual(
                        [name for name, value in values.items()
                         if ROUTING in value or ACCOUNT in value], [])


class LoadRefusalTests(unittest.TestCase):
    """The shape and format rules, each with the valid twin beside it."""

    def _refuses(self, pattern, **fields):
        scenario = _with_deposit(_federal(2025), **fields)
        with self.assertRaisesRegex(ValueError, pattern):
            enforce_scoped_refusals(scenario, "load")

    def test_the_valid_set_and_the_empty_set_are_silent(self):
        enforce_scoped_refusals(_with_deposit(_federal(2025)), "load")
        enforce_scoped_refusals(
            _with_deposit(_federal(2025), account_type="savings"), "load")
        enforce_scoped_refusals(_federal(2025), "load")

    def test_a_partial_set_refuses_naming_what_is_missing(self):
        for missing in ("routing", "account", "account_type"):
            with self.subTest(missing=missing):
                key = {"routing": "refund_routing_number",
                       "account": "refund_account_number",
                       "account_type": "refund_account_type"}[missing]
                self._refuses(
                    rf"all three or none.*missing.*`{key}`",
                    **{missing: None})

    def test_a_single_field_refuses_naming_the_other_two(self):
        keys = {"routing": "refund_routing_number",
                "account": "refund_account_number",
                "account_type": "refund_account_type"}
        for only in keys:
            with self.subTest(only=only):
                fields = {name: None for name in keys if name != only}
                scenario = _with_deposit(_federal(2025), **fields)
                with self.assertRaisesRegex(
                        ValueError, r"all three or none") as cm:
                    enforce_scoped_refusals(scenario, "load")
                missing = str(cm.exception).split("missing", 1)[1]
                for name, key in keys.items():
                    if name == only:
                        self.assertNotIn(f"`{key}`", missing)
                    else:
                        self.assertIn(f"`{key}`", missing)

    def test_digits_outside_ascii_are_refused(self):
        """str.isdigit() accepts fullwidth and Arabic-Indic digits; a form
        cannot carry them. Each value below has a valid length, and the
        fullwidth routing number is 991234561 digit for digit."""
        fullwidth_routing = "\uff19\uff19\uff11\uff12\uff13\uff14\uff15\uff16\uff11"
        arabic_indic_account = "\u0661\u0662\u0663\u0664\u0665\u0666"
        self.assertTrue(fullwidth_routing.isdigit())
        self.assertEqual(len(fullwidth_routing), 9)
        self.assertTrue(arabic_indic_account.isdigit())
        self._refuses(
            r"`refund_routing_number`.*other than the digits 0-9",
            routing=fullwidth_routing)
        self._refuses(
            r"`refund_account_number`.*other than the digits 0-9",
            account=arabic_indic_account)
        self._refuses(
            r"`refund_account_number`.*other than the digits 0-9",
            account="12345\uff16")

    def test_routing_number_must_be_nine_digits_passing_the_checksum(self):
        for bad in ("991234562",     # checksum off by one
                    "99123456",      # 8 digits
                    "9912345610",    # 10 digits
                    "99123456a",     # a letter
                    "991 23456",     # a space
                    "",              # empty
                    991234561):      # unquoted in YAML: a number
            with self.subTest(routing=bad):
                self._refuses(
                    r"`refund_routing_number`.*9 digits.*checksum",
                    routing=bad)

    def test_account_number_must_be_four_to_seventeen_digits(self):
        for bad in ("123",                   # 3 digits
                    "123456789012345678",    # 18 digits
                    "1234-5678",             # a hyphen
                    "12 345678",             # a space
                    "ABCD1234",              # letters
                    "",                      # empty
                    123456789):              # unquoted in YAML: a number
            with self.subTest(account=bad):
                self._refuses(
                    r"`refund_account_number`.*4 to 17 digits", account=bad)

    def test_account_number_length_boundaries_are_accepted(self):
        for good in ("1234", "12345678901234567"):
            with self.subTest(account=good):
                enforce_scoped_refusals(
                    _with_deposit(_federal(2025), account=good), "load")

    def test_account_type_must_be_checking_or_savings(self):
        for bad in ("Checking", "chequing", "", " checking", True, 1):
            with self.subTest(account_type=bad):
                self._refuses(
                    r"`refund_account_type`.*\"checking\" or \"savings\"",
                    account_type=bad)

    def test_an_unquoted_yaml_number_is_refused_at_load(self):
        """End to end through the loader: YAML reads an unquoted routing
        number as an integer, which would drop leading zeros."""
        from tests.helpers import scope_out_attestation_defaults
        config = {
            "year": 2025, "filing_status": "single",
            "birthdate": "1990-06-15", "state": "CA",
            **scope_out_attestation_defaults(),
            "refund_account_number": ACCOUNT,
            "refund_account_type": "checking",
        }
        with tempfile.TemporaryDirectory() as tmp:
            quoted = Path(tmp) / "quoted.yaml"
            quoted.write_text(yaml.safe_dump(
                {"config": {**config, "refund_routing_number": ROUTING}}))
            self.assertEqual(
                load_scenario(quoted).config.refund_routing_number, ROUTING)
            unquoted = Path(tmp) / "unquoted.yaml"
            unquoted.write_text(yaml.safe_dump(
                {"config": {**config,
                            "refund_routing_number": int(ROUTING)}}))
            with self.assertRaisesRegex(
                    ValueError, r"`refund_routing_number`.*quoted"):
                load_scenario(unquoted)


class AmendmentPacketRefusalTests(unittest.TestCase):
    REFUSAL = (r"amendment packet.*direct deposit.*"
               r"paper-filed amended return")

    def _ask(self, original, amended):
        enforce_named_refusal(
            "direct_deposit_in_amendment_packet",
            {"original": original, "amended": amended})

    def test_fields_on_either_scenario_refuse(self):
        plain, with_fields = _federal(2024), _with_deposit(_federal(2024))
        for label, original, amended in (
                ("amended", plain, with_fields),
                ("original", with_fields, plain)):
            with self.subTest(carrier=label):
                with self.assertRaisesRegex(
                        NotImplementedError, self.REFUSAL) as cm:
                    self._ask(original, amended)
                self.assertIn(label, str(cm.exception))

    def test_a_packet_without_the_fields_is_silent(self):
        self._ask(_federal(2024), _federal(2024))

    def test_run_amendment_packet_asks_before_writing_anything(self):
        """The orchestrator entry point poses the question first: nothing
        else about the packet is needed to reach it, and no file exists
        afterwards."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "packet"
            orchestrator = ReturnOrchestrator(
                spreadsheets_dir=SPREADSHEETS_DIR, work_dir=Path(tmp) / "w")
            with self.assertRaisesRegex(NotImplementedError, self.REFUSAL):
                orchestrator.run_amendment_packet(
                    _federal(2024), _with_deposit(_federal(2024)),
                    case=None, filed_path=Path(tmp) / "none.pdf",
                    ca_filed_path=Path(tmp) / "none_ca.pdf", output_dir=out)
            self.assertFalse(out.exists())


class LoaderBypassedCallerTests(_FederalEmitCase):
    """A scenario built in memory and handed straight to the emit step never
    passed the loader. A bad set still cannot print."""

    BAD_SETS = (
        ("checksum", {"routing": "991234562"}, r"`refund_routing_number`"),
        ("partial", {"account": None}, r"all three or none"),
        ("letters", {"account": "ABCD1234"}, r"`refund_account_number`"),
        ("type", {"account_type": "Checking"}, r"`refund_account_type`"),
    )

    def test_emit_pdfs_refuses_a_hand_built_bad_set_and_writes_no_1040(self):
        good = _federal(2025)
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.tmp / "work")
        results = orchestrator.compute_federal(good)
        self.assertGreater(results["refund"], 0)
        for label, fields, pattern in self.BAD_SETS:
            with self.subTest(bad=label):
                out = self.tmp / f"out_{label}"
                with self.assertRaisesRegex(ValueError, pattern):
                    orchestrator.emit_pdfs(
                        _with_deposit(good, **fields), results, out)
                self.assertEqual(list(out.glob("f1040*.pdf")), [])
        # Twin: the same call with the valid set prints.
        emitted = orchestrator.emit_pdfs(
            _with_deposit(good), results, self.tmp / "out_good")
        self.assertEqual(
            _values(emitted["1040"])[F1040[2025]["routing"]], ROUTING)

    def test_the_value_builders_themselves_refuse(self):
        """The guard inside the one read path, with no ledger pass in front
        of it: the 1040 value builder and the Form 540 presentation keys."""
        from tenforty.forms import f540 as form_f540
        for label, fields, pattern in self.BAD_SETS:
            bad = _with_deposit(_federal(2025), **fields)
            with self.subTest(bad=label, form="1040"):
                with self.assertRaisesRegex(ValueError, pattern):
                    ReturnOrchestrator._form_1040_direct_deposit_values(
                        bad, {"refund": 100})
            with self.subTest(bad=label, form="540"):
                with self.assertRaisesRegex(ValueError, pattern):
                    form_f540.presentation_keys(bad.config, bad.w2s, 2025)
        good = _with_deposit(_federal(2025))
        self.assertEqual(
            ReturnOrchestrator._form_1040_direct_deposit_values(
                good, {"refund": 100})["refund_routing_number"], ROUTING)
        self.assertEqual(
            form_f540.presentation_keys(good.config, good.w2s, 2025)[
                "f540_refund_routing_number"], ROUTING)


class SnapshotRedactionTests(unittest.TestCase):
    """`summary.write_results_snapshot` serializes the whole results dict,
    and the California results carry the deposit numbers on their way to
    the form. The snapshot never contains them."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_a_deposit_carrying_ca_snapshot_contains_neither_number(self):
        from tenforty import summary
        scenario = _with_deposit(
            make_ca_scenario(2024, state_tax_withheld=9_000.0))
        results, _pdfs = emit_ca(scenario)
        # The premise: the numbers ARE in the dict being snapshotted.
        self.assertEqual(results["f540_refund_routing_number"], ROUTING)
        self.assertEqual(results["f540_refund_account_number"], ACCOUNT)
        path = summary.write_results_snapshot(
            results, self.tmp / "snap.json", year=2024, label="CA")
        text = path.read_text()
        self.assertNotIn(ROUTING, text)
        self.assertNotIn(ACCOUNT, text)
        loaded = summary.load_results_snapshot(path)["results"]
        self.assertNotIn("f540_refund_routing_number", loaded)
        self.assertNotIn("f540_refund_account_number", loaded)
        # Everything else is still there, including the account type.
        self.assertEqual(loaded["f540_refund_account_type"], "checking")
        self.assertEqual(
            set(results) - set(loaded),
            {"f540_refund_routing_number", "f540_refund_account_number"})
        # The caller's dict is not modified.
        self.assertEqual(results["f540_refund_routing_number"], ROUTING)

    def test_redaction_reaches_any_key_ending_in_the_two_suffixes(self):
        """By key suffix, at any depth -- so a future field is covered."""
        from tenforty import summary
        results = {
            "refund_routing_number": ROUTING,
            "some_future_account_number": ACCOUNT,
            "nested": {"x_routing_number": ROUTING, "kept": 1,
                       "rows": [{"y_account_number": ACCOUNT, "kept": 2}]},
            "routing_number_count": 3,          # suffix does not match
            "account_number_note": "kept",      # suffix does not match
        }
        path = summary.write_results_snapshot(
            results, self.tmp / "snap.json", year=2024, label="x")
        text = path.read_text()
        self.assertNotIn(ROUTING, text)
        self.assertNotIn(ACCOUNT, text)
        self.assertEqual(summary.load_results_snapshot(path)["results"], {
            "nested": {"kept": 1, "rows": [{"kept": 2}]},
            "routing_number_count": 3,
            "account_number_note": "kept",
        })

    def test_a_snapshot_without_deposit_keys_is_byte_identical(self):
        """The twin: with nothing to redact, the file is exactly what the
        unredacted serialization of the same dict would be."""
        import json
        from tenforty import summary
        results, _pdfs = emit_ca(
            make_ca_scenario(2024, state_tax_withheld=9_000.0))
        self.assertEqual(
            [k for k in results if k.endswith(
                ("_routing_number", "_account_number"))], [])
        path = summary.write_results_snapshot(
            results, self.tmp / "snap.json", year=2024, label="CA")
        loaded = json.loads(path.read_text())
        expected = json.dumps({
            "schema": summary.SNAPSHOT_SCHEMA, "year": 2024, "label": "CA",
            "created_at": loaded["created_at"], "scenario": None,
            "emitted": [], "results": dict(results),
        }, indent=2, default=str) + "\n"
        self.assertEqual(path.read_text(), expected)


if __name__ == "__main__":
    unittest.main()
