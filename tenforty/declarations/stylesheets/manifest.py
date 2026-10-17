"""IRS MeF stylesheet packages, one per tax year, hash-pinned (spec §5.1).

The IRS publishes the XSL stylesheets that render an e-filed return as the
printed form at https://www.irs.gov/pub/irs-schema/. A package's "PY" number
is the PROCESSING year, one after the tax year. ``scripts/
fetch_irs_stylesheets.py`` downloads each package into
``~/.cache/tenforty/irs-stylesheets/`` (never into the repo) and refuses a
package whose sha256 differs from the pin below.
"""
from dataclasses import dataclass

URL_BASE = "https://www.irs.gov/pub/irs-schema/"


@dataclass(frozen=True)
class Package:
    url: str
    sha256: str
    folder: str  # the package's top folder inside the zip (varies by package)


PACKAGES: dict[int, Package] = {
    # TY2021: "PY 2022 Stylesheets Complete" (listing date 2022-05-20).
    2021: Package(
        url=URL_BASE + "py2022r1.zip",
        sha256="a416f318f452b50f8844f9450d278607108a9a51114d81833d7553c6eb5a30b7",
        folder="PY2022R12"),
    # TY2022: "TY 2022 Stylesheets" (2023-06-12).
    2022: Package(
        url=URL_BASE + "py2023r1.zip",
        sha256="eaebddc1b1b04b945b1748b15136408ee5dfecc8de612888260aedfd28b106f7",
        folder="PY2023R10"),
    # TY2023: "TY 2023 Stylesheets" (2024-06-06).
    2023: Package(
        url=URL_BASE + "py2024r1.zip",
        sha256="04756268735a28e5f7cbdc3c07c37b2336d68f05d1b448fd318c4b28b849e089",
        folder="PY2024R11"),
    # TY2024 (2025-04-18). This package has no PY<yyyy>R<n> wrapper: its top
    # folder is `mef` itself.
    2024: Package(
        url=URL_BASE + "py2025r1.zip",
        sha256="d9d47b48d15a01beaa4194e33cdd6fba357db7bc92ee8ea93657caa805c1ede5",
        folder="mef"),
    # TY2025 (2026-04-08); sha256 pinned by the spec's planner and matched on
    # re-download.
    2025: Package(
        url=URL_BASE + "py2026r1.zip",
        sha256="903d2d186da0615f626d0737b45933d8007628084be820a3d669d9ff7779b61a",
        folder="PY2026R10"),
}

# Form-years whose extraction is empty, each with its reason; recorded here,
# never skipped (the coverage test pins this exact list). Every XSL_NAME form
# IS present in Stylesheets/<tax year>/ of every package (checked against each
# package's own zip listing, 2026-10-17); these are layout gaps, not missing
# files. Form 8949's lines are per-transaction table columns, so there is no
# per-line label for a label-keyed cross-check; its declaration is built from
# the PDF inventory and repeat templates instead (team-lead ruling 2026-10-17).
_F8949_REASON = ("stylesheet present; layout is not label/desc line blocks "
                 "(box grid / transaction table)")
GAPS: dict[tuple[str, int], str] = {
    ("f8949", year): _F8949_REASON for year in (2021, 2022, 2023, 2024, 2025)
}


def stylesheet_dir(year: int) -> str:
    """The in-zip directory holding the tax year's IRS<form>.xsl files."""
    folder = PACKAGES[year].folder
    mef = folder if folder == "mef" else f"{folder}/mef"
    return f"{mef}/Stylesheets/{year}"


# Our form name -> the stylesheet's base name (Stylesheets/<year>/<name>.xsl).
XSL_NAME: dict[str, str] = {
    "1040": "IRS1040",
    "sch_1": "IRS1040Schedule1",
    "sch_2": "IRS1040Schedule2",
    "sch_a": "IRS1040ScheduleA",
    "sch_b": "IRS1040ScheduleB",
    "sch_c": "IRS1040ScheduleC",
    "sch_d": "IRS1040ScheduleD",
    "sch_e": "IRS1040ScheduleE",
    "sch_se": "IRS1040ScheduleSE",
    "4562": "IRS4562",
    "4868": "IRS4868",
    "8959": "IRS8959",
    "f8582": "IRS8582",
    "f8949": "IRS8949",
    "f8962": "IRS8962",
    "f8995": "IRS8995",
    "f1120s": "IRS1120S",
    "f1120s_k1": "IRS1120SScheduleK1",
    "f1040x": "IRS1040X",
    "f3115": "IRS3115",
}
