"""Fill every text field in a PDF with its own short name.

Used when building a new PdfXXXX mapping: probe the blank IRS template so the
rendered PDF can be inspected to identify which opaque field name corresponds
to which form line. Re-run this every year when the IRS re-issues a form, and
for any new PDF being wired into tenforty.

Usage:
    python scripts/probe_pdf_fields.py --pdf pdfs/federal/2025/f4868.pdf
    python scripts/probe_pdf_fields.py --pdf FORM.pdf --output /tmp/probed.pdf

Default output path is <input>.probe.pdf next to the input file. After
running, open the probed PDF (or render with `pdftoppm FOO.pdf FOO -png`) to
see which marker landed next to which printed label on the form.
"""

import argparse
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def probe(pdf_path: Path, output_path: Path) -> None:
    reader = PdfReader(pdf_path)
    fields = reader.get_fields() or {}

    print(f"=== {len(fields)} fields in {pdf_path.name} ===")
    probe_values: dict[str, str] = {}
    for name, field in fields.items():
        ft = field.get("/FT", "?")
        print(f"  {name!r}  FT={ft}")
        # Only /Tx (text) fields get probed — /Btn (checkbox) and /Ch (choice)
        # fields have no meaningful short-string probe value.
        if ft == "/Tx":
            short = name.split(".")[-1].replace("[0]", "")
            if len(short) > 8:
                short = short[-8:]
            probe_values[name] = short

    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, probe_values, auto_regenerate=False)

    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"\nWrote probe PDF to {output_path}")
    print("Open it or render pages with `pdftoppm` to read which marker landed where.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path, help="Path to blank PDF template")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output probed PDF (default: <input>.probe.pdf)")
    args = parser.parse_args()

    output = args.output or args.pdf.with_suffix(".probe.pdf")
    probe(args.pdf, output)


if __name__ == "__main__":
    main()
