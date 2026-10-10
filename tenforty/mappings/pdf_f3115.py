"""Form 3115 (Rev. December 2022) PDF field mapping.

Flat 1:1 compute-key -> AcroForm field path, for the keys
``forms.f3115.presentation_values`` produces. Every path is the template's own
``get_fields()`` key (pdfs/federal/revision_keyed/f3115.pdf, 354 fields, 294
widgets); each was tied to its printed line by comparing the widget rectangle
to the label positions on the page, and every /Btn on-state below is the
widget's own appearance state.

REVISION-KEYED, like Form 1040-X: one current revision serves every tax
year, so ``_MAPPINGS`` is keyed by revision string and ``get_mapping`` takes
``revision`` (``years.REVISION_KEYED_FORM_REVISIONS["f3115"]``).

Yes/No questions are two separate /Btn fields (``[0]`` on-state ``/Yes``,
``[1]`` on-state ``/No``); both sides are mapped, including the side v1
refuses to print, so the mapping states the form and the refusal ledger
states the scope.

NOT mapped (see ``forms.f3115``): f1_9 (applicant different from filer),
c1_2 (consolidated group), c1_3 (Form 2848), the other TypeOfApplicant and
type-of-change boxes, DCN cells (2)-(12), line 1b, lines 6b-6d, the other
line 7b boxes, lines 8b-8d, 10, 19, Part III, line 27's amount, the "Eligible
acquisition transaction election" box, Schedules A-D, the Schedule E line 2
and 3 write-ins, and the preparer block.
"""
from tenforty.mappings.registry import PdfFormMapping

_P1 = "topmostSubform[0].Page1[0]."
_P2 = "topmostSubform[0].Page2[0]."
_P3 = "topmostSubform[0].Page3[0]."
_P4 = "topmostSubform[0].Page4[0]."
_P8 = "topmostSubform[0].Page8[0]."

_TEXT: dict[str, str] = {
    "f3115_filer_name":             _P1 + "f1_1[0]",   # p1 Name of filer
    "f3115_street":                 _P1 + "f1_2[0]",   # p1 Number, street, room or suite
    "f3115_city_state_zip":         _P1 + "f1_3[0]",   # p1 City or town, state, ZIP
    "f3115_identification_number":  _P1 + "f1_4[0]",   # p1 Identification number (MaxLen 11)
    "f3115_business_activity_code": _P1 + "f1_5[0]",   # p1 Principal business activity code
    "f3115_tax_year_begins":        _P1 + "f1_6[0]",   # p1 Tax year of change begins (MaxLen 10)
    "f3115_tax_year_ends":          _P1 + "f1_7[0]",   # p1 Tax year of change ends (MaxLen 10)
    "f3115_contact_person":         _P1 + "f1_8[0]",   # p1 Name of contact person
    "f3115_contact_phone":          _P1 + "f1_10[0]",  # p1 Contact person's telephone number
    "f3115_dcn_1":                  _P1 + "f1_18[0]",  # p1 line 1a (1) DCN
    "f3115_signer_name":            _P1 + "f1_31[0]",  # p1 Sign Here: Name and title (print or type)
    "f3115_line26_adjustment":      _P4 + "f4_1[0]",   # p4 line 26 section 481(a) adjustment
}

# stem -> the Yes/No pair's field stem ("[0]" = Yes, "[1]" = No).
_YES_NO: dict[str, str] = {
    "f3115_correspondence": _P1 + "c1_1",   # p1 correspondence by fax / encrypted email
    "f3115_line2":          _P1 + "c1_7",   # p1 Part I line 2
    "f3115_line3":          _P1 + "c1_8",   # p1 Part I line 3
    "f3115_line4":          _P1 + "c1_9",   # p1 Part II line 4
    "f3115_line5":          _P1 + "c1_10",  # p1 Part II line 5
    "f3115_line6a":         _P2 + "c2_1",   # p2 line 6a
    "f3115_line7a":         _P2 + "c2_4",   # p2 line 7a
    "f3115_line8a":         _P2 + "c2_6",   # p2 line 8a
    "f3115_line11a":        _P2 + "c2_12",  # p2 line 11a
    "f3115_line12":         _P2 + "c2_13",  # p2 line 12
    "f3115_line13":         _P2 + "c2_14",  # p2 line 13
    "f3115_line17":         _P3 + "c3_1",   # p3 line 17
    "f3115_line18":         _P3 + "c3_2",   # p3 line 18
    "f3115_line25":         _P4 + "c4_0",   # p4 Part IV line 25
    "f3115_line27":         _P4 + "c4_1",   # p4 line 27
    "f3115_line28":         _P4 + "c4_2",   # p4 line 28
    "f3115_line29":         _P4 + "c4_4",   # p4 line 29
    "f3115_sch_e_line1":    _P8 + "c8_1",   # p8 Schedule E line 1
    "f3115_sch_e_line2":    _P8 + "c8_2",   # p8 Schedule E line 2
    "f3115_sch_e_line3":    _P8 + "c8_3",   # p8 Schedule E line 3
    "f3115_sch_e_line4b":   _P8 + "c8_4",   # p8 Schedule E line 4b
    "f3115_sch_e_line4c":   _P8 + "c8_5",   # p8 Schedule E line 4c
}

# Single boxes: compute key -> (field path, on-state).
_BOXES: dict[str, tuple[str, str]] = {
    # p1 Type of applicant: Individual
    "f3115_applicant_individual": (_P1 + "TypeOfApplicant[0].c1_4[0]", "/1"),
    # p1 Type of accounting method change: Depreciation or Amortization
    "f3115_change_depreciation": (_P1 + "c1_5[0]", "/1"),
    # p2 line 7b: Not under exam
    "f3115_line7b_not_under_exam": (_P2 + "c2_5[0]", "/1"),
    # p4 line 28: $50,000 de minimis election
    "f3115_line28_de_minimis": (_P4 + "c4_3[0]", "/90"),
}

_MAPPING: dict[str, str] = {
    **_TEXT,
    **{f"{stem}_yes": f"{path}[0]" for stem, path in _YES_NO.items()},
    **{f"{stem}_no": f"{path}[1]" for stem, path in _YES_NO.items()},
    **{key: path for key, (path, _state) in _BOXES.items()},
}

_CHECKBOX_STATES: dict[str, str] = {
    **{f"{stem}_yes": "/Yes" for stem in _YES_NO},
    **{f"{stem}_no": "/No" for stem in _YES_NO},
    **{key: state for key, (_path, state) in _BOXES.items()},
}


class PdfF3115(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for Form 3115 (Rev. December 2022). Flat 1:1,
    REVISION-keyed."""

    _FORM_NAME = "Form 3115"
    _MAPPINGS: dict[str, dict[str, str]] = {"rev-2022-12": _MAPPING}
    _CHECKBOX_STATES_BY_REVISION: dict[str, dict[str, str]] = {
        "rev-2022-12": _CHECKBOX_STATES}

    @classmethod
    def get_mapping(cls, revision: str) -> dict[str, str]:
        if revision not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} PDF mapping for revision {revision!r}")
        return cls._MAPPINGS[revision]

    @classmethod
    def get_checkbox_states(cls, revision: str) -> dict[str, str]:
        cls.get_mapping(revision)  # same unknown-revision refusal
        return cls._CHECKBOX_STATES_BY_REVISION[revision]


def get_mapping(revision: str) -> dict[str, str]:
    """Module-level accessor, as for Form 1040-X."""
    return PdfF3115.get_mapping(revision)
