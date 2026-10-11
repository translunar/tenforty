"""The depreciation audit workbook: `depreciation_audit_<year>.xlsx`.

Emitted beside the forms on every return that computes MACRS depreciation
from a `depreciable_assets` block. Every computed figure is a spreadsheet
formula over cells visible in the workbook; the Tie-outs sheet compares the
formula results against the figures the engine printed on the forms.

This module computes no tax. It transcribes the depreciation resolver's audit
trail (`resolver.audit_trail`) into cells -- inputs and table rates as values,
the arithmetic as formulas -- and owns all layout.

THE MIRROR. No spreadsheet engine runs, at emit or in the tests. Instead the
formula text written to each cell is evaluated here in Python (`evaluate`, a
small evaluator for exactly the functions this workbook writes) over the
written cells, and compared with the engine's own figure for that cell. A
difference of half a cent or more means the workbook would not reproduce the
filing, and the whole emit is refused (`depreciation_audit_unbuildable`).

Residual risk, stated rather than hidden: `evaluate` rounds as the engine
does (`irs_round`, half up). A real spreadsheet's ROUND agrees except
possibly where a product lands within floating-point error of a half
dollar; that cannot be checked without running one.

Sheets, in order: Tie-outs, Assets, Year-by-year, and 481(a) when the
scenario carries a `form_3115:` block.
"""
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter, range_boundaries

from tenforty.attestations import raise_scoped_refusal
from tenforty.forms import f4562 as form_4562
from tenforty.forms.depreciation import macrs
from tenforty.forms.depreciation.resolver import (
    MODE_ASSETS_OVERRIDDEN, ActivityAudit, AssetAudit, audit_trail,
)
from tenforty.rounding import irs_round

REFUSAL = "depreciation_audit_unbuildable"
EMITTED_KEY = "depreciation_audit"

TIE_OUTS = "Tie-outs"
ASSETS = "Assets"
YEAR_BY_YEAR = "Year-by-year"
SECTION_481A = "481(a)"

# How each Pub 946 Appendix A table is cited beside the rates read from it.
# A literal list on purpose: a table the engine learns to read must be added
# here before the workbook will cite it (tests enumerate the engine's tables
# against this).
_TABLE_CITATIONS: dict[str, str] = {
    "A-1": "Pub 946 Table A-1",
    "A-2": "Pub 946 Table A-2",
    "A-3": "Pub 946 Table A-3",
    "A-4": "Pub 946 Table A-4",
    "A-5": "Pub 946 Table A-5",
    "A-6": "Pub 946 Table A-6",
    "A-7a": "Pub 946 Table A-7a",
}
GRID_TABLES: frozenset[str] = frozenset(_TABLE_CITATIONS)

# Tie-out tolerance, in dollars: half a cent.
TOLERANCE = 0.005
VERDICT_FORMULA = '=IF(ABS(E{row})<0.005,"PASS","FAIL")'

TIE_OUT_HEADERS = (
    "Claim", "Computed", "Printed on form", "Source of printed figure",
    "Difference", "Verdict")
ASSET_HEADERS = (
    "Activity #", "Activity", "Description", "In service", "Method", "Life",
    "Convention", "Rate", "Basis", "Prior accumulated", "Deduction",
    "Accumulated after", "4562 line", "Provenance")
YEAR_HEADERS = (
    "Asset", "Recovery year", "Tax year", "Rate", "Deduction", "Cumulative",
    "Source")
OVERRIDE_HEADERS = {
    "A": "Activity #", "B": "Activity", "I": "Override amount",
    "J": "Restated engine amount", "N": "Provenance"}
SECTION_481A_HEADERS = (
    "Asset", "In service", "Claimed", "Allowable", "Adjustment", "Note",
    "Provenance")

_SECTION_LINE = {
    "rental_properties": "Schedule E line 18",
    "schedule_c_businesses": "Schedule C line 13",
}
NO_MATCH_NOTE = "no matching depreciable asset"
INCOME_NOTE = (
    "tenforty does not carry the section 481(a) adjustment onto the "
    "return's income: the filer must include it in gross income, and the "
    "scenario's income figures must already include the portion taken into "
    "account this year.")


@dataclass(frozen=True)
class Form3115Figures:
    """What Form 3115 and its Schedule E statement print, as printed."""
    # Line 26, signed (positive = an increase in income).
    line_26: float
    year_of_change: int
    # One per statement row: (description, date placed in service,
    # depreciation claimed under the present method).
    assets: tuple[tuple[str, date, float], ...]


@dataclass(frozen=True)
class PrintedFigures:
    """The depreciation figures the engine filled into the forms this emit.
    A 4562 figure is None / absent when the form did not print it."""
    f4562_line_17: int | None = None
    # Section B row letter ("a".."j") -> column (g) deduction.
    f4562_line_19: Mapping[str, int] = field(default_factory=dict)
    f4562_line_22: int | None = None
    # (section, activity index) -> Schedule E line 18 / Schedule C line 13.
    # A line that printed nothing is absent and compares as zero.
    activity_lines: Mapping[tuple[str, int], int] = field(
        default_factory=dict)
    form_3115: Form3115Figures | None = None


# --- The mirror: a Python evaluation of the formulas this workbook writes ---

_TOKEN = re.compile(r"""
    \s*(?:
      (?P<number>\d+(?:\.\d+)?)
    | "(?P<string>[^"]*)"
    | (?P<sheet>'[^']+'|[A-Za-z_][A-Za-z0-9_]*)!
    | (?P<cell>\$?[A-Z]{1,3}\$?\d+)
    | (?P<name>[A-Z]+)(?=\()
    | (?P<op><=|>=|<>|[-+*/(),:<>=])
    )""", re.VERBOSE)


class FormulaError(ValueError):
    """A formula `evaluate` cannot read: not one this workbook writes."""


def _tokens(text: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None or match.end() == pos:
            raise FormulaError(f"cannot read formula at {text[pos:]!r}")
        kind = match.lastgroup
        out.append((kind, match.group(kind)))
        pos = match.end()
    return out


def _round_half_up(value: float, digits: int) -> float:
    scale = 10 ** digits
    scaled = value * scale
    rounded = (math.floor(scaled + 0.5) if scaled >= 0
               else -math.floor(-scaled + 0.5))
    return rounded / scale


def _number(value) -> float:
    # An empty cell is zero in arithmetic, as in a spreadsheet.
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormulaError(f"arithmetic on a non-number: {value!r}")
    return value


def _flatten(args) -> list:
    out = []
    for arg in args:
        out.extend(arg if isinstance(arg, list) else [arg])
    return out


class _Evaluator:
    def __init__(self, workbook, sheet: str, text: str):
        self.workbook = workbook
        self.sheet = sheet
        self.tokens = _tokens(text)
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self, kind=None, value=None):
        token = self._peek()
        if (token is None or (kind is not None and token[0] != kind)
                or (value is not None and token[1] != value)):
            raise FormulaError(
                f"expected {value or kind}, found {token!r}")
        self.pos += 1
        return token

    def _op(self, *values) -> str | None:
        token = self._peek()
        if token is not None and token[0] == "op" and token[1] in values:
            self.pos += 1
            return token[1]
        return None

    def result(self):
        value = self._comparison()
        if self._peek() is not None:
            raise FormulaError(f"unexpected {self._peek()!r}")
        return value

    def _comparison(self):
        left = self._sum()
        op = self._op("<=", ">=", "<>", "<", ">", "=")
        if op is None:
            return left
        right = self._sum()
        return {
            "<": left < right, ">": left > right, "<=": left <= right,
            ">=": left >= right, "=": left == right, "<>": left != right,
        }[op]

    def _sum(self):
        value = self._product()
        while (op := self._op("+", "-")) is not None:
            other = _number(self._product())
            value = _number(value) + other if op == "+" else (
                _number(value) - other)
        return value

    def _product(self):
        value = self._unary()
        while (op := self._op("*", "/")) is not None:
            other = _number(self._unary())
            value = _number(value) * other if op == "*" else (
                _number(value) / other)
        return value

    def _unary(self):
        if self._op("-") is not None:
            return -_number(self._unary())
        return self._primary()

    def _primary(self):
        kind, text = self._take()
        if kind == "number":
            return float(text) if "." in text else int(text)
        if kind == "string":
            return text
        if kind == "name":
            return self._call(text)
        if kind == "sheet":
            return self._reference(text.strip("'"), self._take("cell")[1])
        if kind == "cell":
            return self._reference(self.sheet, text)
        if kind == "op" and text == "(":
            value = self._comparison()
            self._take("op", ")")
            return value
        raise FormulaError(f"unexpected {text!r}")

    def _reference(self, sheet: str, first: str):
        first = first.replace("$", "")
        if self._op(":") is None:
            return cell_value(self.workbook, sheet, first)
        last = self._take("cell")[1].replace("$", "")
        min_col, min_row, max_col, max_row = range_boundaries(
            f"{first}:{last}")
        return [
            cell_value(
                self.workbook, sheet, f"{get_column_letter(col)}{row}")
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)]

    def _call(self, name: str):
        self._take("op", "(")
        args = [self._comparison()]
        while self._op(",") is not None:
            args.append(self._comparison())
        self._take("op", ")")
        if name == "ROUND":
            value, digits = args
            return _round_half_up(_number(value), digits)
        if name == "MIN":
            return min(_number(v) for v in _flatten(args))
        if name == "MAX":
            return max(_number(v) for v in _flatten(args))
        if name == "ABS":
            (value,) = args
            return abs(_number(value))
        if name == "SUM":
            return sum(_number(v) for v in _flatten(args))
        if name == "SUMIF":
            keys, criterion, values = args
            return sum(
                _number(v) for k, v in zip(keys, values, strict=True)
                if k == criterion)
        if name == "IF":
            test, when_true, when_false = args
            return when_true if test else when_false
        raise FormulaError(f"unsupported function {name}")


def cell_value(workbook, sheet: str, coordinate: str):
    """The value of one cell: an input as written, a formula evaluated."""
    cell = workbook[sheet][coordinate]
    if cell.data_type == "f":
        return evaluate(workbook, sheet, cell.value)
    return cell.value


def evaluate(workbook, sheet: str, formula: str):
    """Evaluate ``formula`` (text beginning "=") as written on ``sheet`` of
    ``workbook``, following references to other cells and sheets.

    Reads exactly what this module writes: numbers, strings, cell and range
    references, + - * /, comparisons, and ROUND, MIN, MAX, ABS, SUM, SUMIF,
    IF. Anything else raises `FormulaError`."""
    if not formula.startswith("="):
        raise FormulaError(f"not a formula: {formula!r}")
    value = _Evaluator(workbook, sheet, formula[1:]).result()
    # A formula that is a bare reference to an empty cell shows zero.
    return 0 if value is None else value


# --- Layout ----------------------------------------------------------------

@dataclass(frozen=True)
class _Expectation:
    """The engine's figure for one formula cell, and whom to name if the
    formula does not reproduce it."""
    sheet: str
    coordinate: str
    expected: float
    subject: str
    fields: str


def _header(sheet, headers) -> None:
    for column, title in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=column, value=title)
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"


def _text(sheet, coordinate: str, value: str) -> None:
    """Write ``value`` as text, whatever it looks like: a description
    beginning "=" is a description, never a formula."""
    cell = sheet[coordinate]
    cell.value = value
    cell.data_type = "s"


def _convention_text(asset: AssetAudit) -> str:
    if asset.quarter is not None:
        return f"{asset.convention} (quarter {asset.quarter})"
    return asset.convention


def _form_line(asset: AssetAudit, year: int) -> str:
    if asset.date_placed_in_service.year == year:
        return f"line 19{form_4562._CLASS_TO_ROW[asset.recovery_class]}"
    return "line 17"


def _field_path(asset: AssetAudit, name: str) -> str:
    return (f"{asset.section}[{asset.activity_index}]."
            f"depreciable_assets[{asset.asset_index}].{name}")


def _asset_provenance(asset: AssetAudit) -> str:
    basis = f"Basis: {_field_path(asset, 'basis')}"
    if asset.prior_depreciation is None:
        return f"{basis}. Prior accumulated: none (placed in service this year)"
    prior = f"Prior accumulated: {_field_path(asset, 'prior_depreciation')}"
    if asset.prior_acknowledged:
        prior += (" (stated, differs from the tables: "
                  "acknowledges_prior_depreciation_as_stated)")
    return f"{basis}. {prior}"


def _year_source(asset: AssetAudit, rate) -> str:
    table = _TABLE_CITATIONS[asset.table]
    if rate is None:
        return f"recovery period ended (no cell in {table})"
    if asset.convention == macrs.MID_MONTH:
        return f"{table}, month {asset.date_placed_in_service.month}"
    return table


def _subject(asset: AssetAudit) -> str:
    return f"asset {asset.description!r} on {asset.activity_label}"


class _Builder:
    def __init__(self, resolved: tuple[ActivityAudit, ...],
                 printed: PrintedFigures, year: int):
        self.resolved = resolved
        self.printed = printed
        self.year = year
        self.workbook = Workbook()
        self.expectations: list[_Expectation] = []
        self.assets = [a for activity in resolved for a in activity.assets]
        self.last_asset_row = 1 + len(self.assets)
        # (section, activity index, asset index) -> row on each sheet.
        self.asset_rows: dict[tuple, int] = {}
        self.first_year_rows: dict[tuple, int] = {}
        self.override_rows: dict[tuple[str, int], int] = {}
        self.tie_outs = self.workbook.active
        self.tie_outs.title = TIE_OUTS
        self.assets_sheet = self.workbook.create_sheet(ASSETS)
        self.years_sheet = self.workbook.create_sheet(YEAR_BY_YEAR)

    def _expect(self, sheet, coordinate, expected, subject, fields) -> None:
        self.expectations.append(_Expectation(
            sheet.title, coordinate, expected, subject, fields))

    @staticmethod
    def _key(asset: AssetAudit) -> tuple:
        return (asset.section, asset.activity_index, asset.asset_index)

    def build(self):
        self._plan_rows()
        self._write_assets()
        self._write_years()
        self._write_overrides()
        self._write_tie_outs()
        if self.printed.form_3115 is not None:
            self._write_481a(self.printed.form_3115)
        return self.workbook

    def _plan_rows(self) -> None:
        year_row = 2
        for row, asset in enumerate(self.assets, start=2):
            self.asset_rows[self._key(asset)] = row
            self.first_year_rows[self._key(asset)] = year_row
            year_row += len(asset.years)

    def _write_assets(self) -> None:
        sheet = self.assets_sheet
        _header(sheet, ASSET_HEADERS)
        numbers = {
            (activity.section, activity.index): n
            for n, activity in enumerate(self.resolved, start=1)}
        for asset in self.assets:
            r = self.asset_rows[self._key(asset)]
            current_year_row = (
                self.first_year_rows[self._key(asset)] + len(asset.years) - 1)
            sheet[f"A{r}"] = numbers[(asset.section, asset.activity_index)]
            _text(sheet, f"B{r}", asset.activity_label)
            _text(sheet, f"C{r}", asset.description)
            sheet[f"D{r}"] = asset.date_placed_in_service
            sheet[f"E{r}"] = asset.method
            sheet[f"F{r}"] = asset.recovery_class
            sheet[f"G{r}"] = _convention_text(asset)
            sheet[f"H{r}"] = f"='{YEAR_BY_YEAR}'!D{current_year_row}"
            sheet[f"I{r}"] = asset.basis
            sheet[f"J{r}"] = (
                0 if asset.prior_depreciation is None
                else asset.prior_depreciation)
            sheet[f"K{r}"] = f"=ROUND(MAX(0,MIN(I{r}*H{r},I{r}-J{r})),0)"
            sheet[f"L{r}"] = f"=J{r}+K{r}"
            sheet[f"M{r}"] = _form_line(asset, self.year)
            _text(sheet, f"N{r}", _asset_provenance(asset))
            subject = _subject(asset)
            self._expect(sheet, f"H{r}", asset.current.rate or 0.0, subject,
                         "`recovery_class` / `date_placed_in_service`")
            self._expect(sheet, f"K{r}", asset.current.amount, subject,
                         "`basis` / `prior_depreciation`")

    def _write_years(self) -> None:
        sheet = self.years_sheet
        _header(sheet, YEAR_HEADERS)
        for asset in self.assets:
            r = self.asset_rows[self._key(asset)]
            first = self.first_year_rows[self._key(asset)]
            basis = f"{ASSETS}!$I${r}"
            for n, year in enumerate(asset.years, start=first):
                sheet[f"A{n}"] = f"={ASSETS}!C{r}"
                sheet[f"B{n}"] = year.recovery_year
                sheet[f"C{n}"] = year.tax_year
                sheet[f"D{n}"] = year.rate
                if n == first:
                    sheet[f"E{n}"] = f"=ROUND(MIN({basis}*D{n},{basis}),0)"
                    sheet[f"F{n}"] = f"=E{n}"
                else:
                    sheet[f"E{n}"] = (
                        f"=ROUND(MIN({basis}*D{n},{basis}-F{n - 1}),0)")
                    sheet[f"F{n}"] = f"=F{n - 1}+E{n}"
                sheet[f"G{n}"] = _year_source(asset, year.rate)
                subject = f"{_subject(asset)}, tax year {year.tax_year}"
                self._expect(sheet, f"E{n}", year.amount, subject, "`basis`")
                self._expect(sheet, f"F{n}", year.taken_before + year.amount,
                             subject, "`basis`")

    def _write_overrides(self) -> None:
        overridden = [a for a in self.resolved
                      if a.mode == MODE_ASSETS_OVERRIDDEN]
        if not overridden:
            return
        sheet = self.assets_sheet
        header_row = self.last_asset_row + 2
        for column, title in OVERRIDE_HEADERS.items():
            sheet[f"{column}{header_row}"] = title
            sheet[f"{column}{header_row}"].font = Font(bold=True)
        numbers = {id(a): n for n, a in enumerate(self.resolved, start=1)}
        for r, activity in enumerate(overridden, start=header_row + 1):
            self.override_rows[(activity.section, activity.index)] = r
            path = f"{activity.section}[{activity.index}].depreciation_override"
            sheet[f"A{r}"] = numbers[id(activity)]
            _text(sheet, f"B{r}", activity.label)
            sheet[f"I{r}"] = activity.override_amount
            sheet[f"J{r}"] = activity.restates_engine_amount
            _text(sheet, f"N{r}", (
                f"Override amount: {path}.amount (acknowledged; the forms "
                f"use this figure). Restated engine amount: "
                f"{path}.restates_engine_amount"))

    def _tie_out(self, claim: str, computed: str, printed, source: str,
                 expected: float, subject: str, fields: str) -> None:
        sheet = self.tie_outs
        r = sheet.max_row + 1
        _text(sheet, f"A{r}", claim)
        sheet[f"B{r}"] = computed
        sheet[f"C{r}"] = printed
        _text(sheet, f"D{r}", source)
        sheet[f"E{r}"] = f"=B{r}-C{r}"
        sheet[f"F{r}"] = VERDICT_FORMULA.format(row=r)
        self._expect(sheet, f"B{r}", expected, subject, fields)

    def _write_tie_outs(self) -> None:
        _header(self.tie_outs, TIE_OUT_HEADERS)
        last = self.last_asset_row
        lines = f"{ASSETS}!M2:M{last}"
        numbers = f"{ASSETS}!A2:A{last}"
        deductions = f"{ASSETS}!K2:K{last}"
        printed = self.printed
        whole = "the return's depreciable assets"

        def line_total(line: str) -> int:
            return sum(a.current.amount for a in self.assets
                       if _form_line(a, self.year) == line)

        if printed.f4562_line_17 is not None:
            self._tie_out(
                "Form 4562 line 17: MACRS deductions for assets placed in "
                f"service before {self.year}",
                f'=SUMIF({lines},"line 17",{deductions})',
                printed.f4562_line_17, "Form 4562 line 17 as printed",
                line_total("line 17"), whole, "Form 4562 line 17")
        for letter in sorted(printed.f4562_line_19):
            self._tie_out(
                f"Form 4562 line 19{letter}, column (g): depreciation "
                f"deduction",
                f'=SUMIF({lines},"line 19{letter}",{deductions})',
                printed.f4562_line_19[letter],
                f"Form 4562 line 19{letter} column (g) as printed",
                line_total(f"line 19{letter}"), whole,
                f"Form 4562 line 19{letter}")
        if printed.f4562_line_22 is not None:
            self._tie_out(
                "Form 4562 line 22: total depreciation",
                f"=SUM({deductions})",
                printed.f4562_line_22, "Form 4562 line 22 as printed",
                sum(a.current.amount for a in self.assets), whole,
                "Form 4562 line 22")
        for n, activity in enumerate(self.resolved, start=1):
            line = _SECTION_LINE[activity.section]
            if activity.section == "schedule_c_businesses":
                line = f"{line} (business {activity.index + 1})"
            key = (activity.section, activity.index)
            line_printed = printed.activity_lines.get(key, 0)
            asset_sum = f"=SUMIF({numbers},{n},{deductions})"
            if activity.mode != MODE_ASSETS_OVERRIDDEN:
                self._tie_out(
                    f"{line}: depreciation, {activity.label}", asset_sum,
                    line_printed, f"{line} as printed",
                    activity.engine_amount, activity.label, line)
                continue
            r = self.override_rows[key]
            self._tie_out(
                f"{line}: depreciation, {activity.label} "
                f"(depreciation_override in effect)",
                f"=ROUND({ASSETS}!I{r},0)", line_printed,
                f"{line} as printed",
                irs_round(activity.used_amount), activity.label,
                "`depreciation_override.amount`")
            self._tie_out(
                f"Engine figure restated by the override, {activity.label}",
                asset_sum, f"=ROUND({ASSETS}!J{r},0)",
                f"depreciation_override.restates_engine_amount "
                f"({ASSETS}!J{r}); not printed on a form",
                activity.engine_amount, activity.label,
                "`depreciation_override.restates_engine_amount`")

    def _write_481a(self, figures: Form3115Figures) -> None:
        sheet = self.workbook.create_sheet(SECTION_481A)
        _header(sheet, SECTION_481A_HEADERS)
        by_identity = {
            (a.description, a.date_placed_in_service): a for a in self.assets}
        last_prior_year = figures.year_of_change - 1
        r = 1
        for n, (description, placed, claimed) in enumerate(figures.assets):
            r += 1
            _text(sheet, f"A{r}", description)
            sheet[f"B{r}"] = placed
            sheet[f"C{r}"] = claimed
            _text(sheet, f"G{r}", (
                f"Claimed: form_3115.assets[{n}]."
                f"depreciation_claimed_present_method"))
            asset = by_identity.get((description, placed))
            if asset is None:
                _text(sheet, f"F{r}", NO_MATCH_NOTE)
                continue
            rows = [
                self.first_year_rows[self._key(asset)] + i
                for i, year in enumerate(asset.years)
                if year.tax_year == last_prior_year]
            if rows:
                sheet[f"D{r}"] = f"='{YEAR_BY_YEAR}'!F{rows[0]}"
            else:
                sheet[f"D{r}"] = 0
                _text(sheet, f"F{r}", (
                    f"no depreciation allowable before "
                    f"{figures.year_of_change}: placed in service in "
                    f"{placed.year}"))
            sheet[f"E{r}"] = f"=C{r}-D{r}"
        last = r
        net = last + 2
        _text(sheet, f"A{net}", "Net section 481(a) adjustment")
        sheet[f"E{net}"] = f"=SUM(E2:E{last})" if last >= 2 else 0
        _text(sheet, f"F{net}", (
            "claimed less allowable, matched assets only; positive is an "
            "increase in income"))
        stated = net + 1
        _text(sheet, f"A{stated}", "Stated section 481(a) adjustment")
        sheet[f"E{stated}"] = figures.line_26
        _text(sheet, f"F{stated}", INCOME_NOTE)
        _text(sheet, f"G{stated}", "form_3115.section_481a_adjustment")

        tie = self.tie_outs
        t = tie.max_row + 1
        _text(tie, f"A{t}", "Form 3115 line 26: net section 481(a) adjustment")
        tie[f"B{t}"] = f"='{SECTION_481A}'!E{net}"
        tie[f"C{t}"] = figures.line_26
        _text(tie, f"D{t}", (
            "Form 3115 line 26 as printed (stated: "
            "form_3115.section_481a_adjustment; tenforty does not compute "
            "or check it)"))
        tie[f"E{t}"] = f"=B{t}-C{t}"
        tie[f"F{t}"] = VERDICT_FORMULA.format(row=t)


def _figure(value) -> str:
    """A number as a reader writes it: 500, not 500.0."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _year_of(resolved: tuple[ActivityAudit, ...]) -> int:
    return resolved[0].assets[0].current.tax_year


def _mirror_mismatches(workbook, expectations) -> list[str]:
    reasons = []
    for e in expectations:
        try:
            got = cell_value(workbook, e.sheet, e.coordinate)
            differs = abs(got - e.expected) >= TOLERANCE
        except (FormulaError, TypeError) as error:
            got, differs = f"unreadable ({error})", True
        if differs:
            reasons.append(
                f"{e.subject}: the workbook formula at "
                f"{e.sheet}!{e.coordinate} gives {_figure(got)} where the "
                f"engine's figure is {_figure(e.expected)} (inputs: "
                f"{e.fields})")
    return reasons


def _build(resolved, printed):
    builder = _Builder(resolved, printed, _year_of(resolved))
    workbook = builder.build()
    return workbook, _mirror_mismatches(workbook, builder.expectations)


def unbuildable_reasons(scenario) -> list[str]:
    """Why this return's audit workbook cannot be built; empty when it can
    (and for a return with no asset-mode depreciation, which has none).

    The offenders predicate of the `depreciation_audit_unbuildable` refusal.
    The reasons do not depend on the printed figures, so it runs before any
    form is prepared."""
    resolved = audit_trail(scenario)
    if not resolved:
        return []
    return _build(resolved, PrintedFigures())[1]


def write_depreciation_audit(
        resolved: tuple[ActivityAudit, ...], printed: PrintedFigures,
        out_path: Path) -> Path:
    """Write the audit workbook for ``resolved`` (a non-empty
    `resolver.audit_trail`) and the figures ``printed`` on the forms.

    Refuses, through the registry, when a formula does not reproduce the
    engine's figure or the file cannot be written; nothing is left at
    ``out_path`` then."""
    workbook, reasons = _build(resolved, printed)
    if reasons:
        raise_scoped_refusal(REFUSAL, reasons)
    out_path = Path(out_path)
    try:
        workbook.save(out_path)
    except OSError as error:
        out_path.unlink(missing_ok=True)
        raise_scoped_refusal(
            REFUSAL, [f"{out_path.name} could not be written ({error})"])
    return out_path
