class FormMapping:
    """Base class for form mappings. Subclasses define INPUTS and OUTPUTS by year."""

    INPUTS: dict[int, dict[str, str]] = {}
    OUTPUTS: dict[int, dict[str, str]] = {}

    @classmethod
    def get_inputs(cls, year: int) -> dict[str, str]:
        if year not in cls.INPUTS:
            raise ValueError(f"No input mapping for year {year} in {cls.__name__}")
        return cls.INPUTS[year]

    @classmethod
    def get_outputs(cls, year: int) -> dict[str, str]:
        if year not in cls.OUTPUTS:
            raise ValueError(f"No output mapping for year {year} in {cls.__name__}")
        return cls.OUTPUTS[year]

    @classmethod
    def inherit(cls, base_year: int, overrides: dict[str, str],
                source: str = "inputs") -> dict[str, str]:
        """Create a new year's mapping by overriding specific fields from base_year."""
        base = cls.INPUTS if source == "inputs" else cls.OUTPUTS
        if base_year not in base:
            raise ValueError(f"No {source} mapping for year {base_year} in {cls.__name__}")
        return {**base[base_year], **overrides}


class PdfFormMapping[MappingT]:
    """Base class for PDF field mappings keyed by tax year.

    Subclasses declare two class attributes:

    - ``_FORM_NAME`` — display name interpolated into the unknown-year
      error (e.g. ``"Schedule B"``, ``"Form 1040"``).
    - ``_MAPPINGS`` — dict mapping tax year to the form's per-year
      mapping payload. The payload type is subclass-defined; ``MappingT``
      is the type parameter so subclasses can express it precisely
      (e.g. ``dict[str, str]`` for flat 1:1 mappings, or richer shapes
      for forms that partition their payload into scalars and repeaters).
    """

    _FORM_NAME: str
    _MAPPINGS: dict[int, MappingT]

    @classmethod
    def get_mapping(cls, year: int) -> MappingT:
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} PDF mapping for year {year}"
            )
        return cls._MAPPINGS[year]


def inherit_pdf_fields(
    base: dict[str, str],
    *,
    root_swap: tuple[str, str] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a year's PDF field dict from another year's.

    IRS re-issues often keep a form's field tree intact and only rename
    the root widget container (form1[0] <-> topmostSubform[0]). root_swap
    applies that rename to every value; overrides then replaces the fields
    that genuinely moved. Keys are never added or removed — a form whose
    key set changes between years needs an explicit dict, not inherit.
    """
    if root_swap is not None:
        old_root, new_root = root_swap
        derived = {k: v.replace(old_root, new_root) for k, v in base.items()}
    else:
        derived = dict(base)
    if overrides:
        unknown = set(overrides) - set(base)
        if unknown:
            raise ValueError(
                f"inherit_pdf_fields overrides for unknown keys: {sorted(unknown)}")
        derived.update(overrides)
    return derived
