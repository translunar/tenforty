"""Pixel-level PDF assertions: render a page with poppler and count dark
pixels inside a PDF-space rectangle.

Field state (``/AS``, ``/V``) is not pixels: a checkbox can be "checked" in
the field tree while its appearance stream draws nothing, so viewers and
printers show an empty box. These helpers render the page (``pdftoppm``) and
measure ink, so a test can assert that a mark is actually VISIBLE.

Reusable by any test module::

    from tests._pdf_pixels import dark_pixels_in_rect, checked_widgets

No third-party imaging dependency: ``pdftoppm -gray`` emits a binary PGM,
parsed here directly.
"""

import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader

DEFAULT_DPI = 150
DARK_THRESHOLD = 160  # 0=black .. 255=white; below this counts as ink


def render_gray(pdf_path, page_index: int, dpi: int = DEFAULT_DPI):
    """Render one page (0-based) to 8-bit grayscale. Returns (w, h, bytes)."""
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "pg"
        subprocess.run(
            ["pdftoppm", "-r", str(dpi), "-f", str(page_index + 1),
             "-l", str(page_index + 1), "-gray", str(pdf_path), str(prefix)],
            check=True, capture_output=True,
        )
        produced = sorted(Path(td).glob("pg*.pgm"))
        if len(produced) != 1:
            raise RuntimeError(f"pdftoppm produced {produced!r} for {pdf_path}")
        data = produced[0].read_bytes()
    # Binary PGM: "P5\n<w> <h>\n255\n<bytes>" (poppler writes no comments).
    parts = data.split(b"\n", 3)
    if parts[0] != b"P5":
        raise RuntimeError(f"unexpected PGM header {parts[0]!r}")
    w, h = (int(x) for x in parts[1].split())
    return w, h, parts[3]


def dark_pixels_in_rect(pdf_path, page_index: int, rect, dpi: int = DEFAULT_DPI,
                        inset: float = 2.0, threshold: int = DARK_THRESHOLD,
                        _render_cache: dict | None = None) -> int:
    """Count ink pixels inside ``rect`` = [x0, y0, x1, y1] in PDF points.

    ``inset`` (points) shrinks the rect on every side so the widget's own
    printed border (drawn at the box edge) is not counted as a mark.
    """
    reader = PdfReader(str(pdf_path))
    page = reader.pages[page_index]
    box = page.cropbox
    x_off, y_top = float(box.left), float(box.top)
    key = (str(pdf_path), page_index, dpi)
    if _render_cache is not None and key in _render_cache:
        w, h, buf = _render_cache[key]
    else:
        w, h, buf = render_gray(pdf_path, page_index, dpi)
        if _render_cache is not None:
            _render_cache[key] = (w, h, buf)
    scale = dpi / 72.0
    x0, y0, x1, y1 = (float(v) for v in rect)
    x0, x1 = min(x0, x1) + inset, max(x0, x1) - inset
    y0, y1 = min(y0, y1) + inset, max(y0, y1) - inset
    px0 = max(0, int((x0 - x_off) * scale))
    px1 = min(w, int((x1 - x_off) * scale) + 1)
    py0 = max(0, int((y_top - y1) * scale))
    py1 = min(h, int((y_top - y0) * scale) + 1)
    dark = 0
    for row in range(py0, py1):
        base = row * w
        seg = buf[base + px0: base + px1]
        dark += sum(1 for b in seg if b < threshold)
    return dark


def _field_name(widget) -> str:
    names = []
    node = widget
    while node is not None:
        if "/T" in node:
            names.append(str(node["/T"]))
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return ".".join(reversed(names))


def checked_widgets(pdf_path):
    """Yield (page_index, field_name, rect, state) for every button widget
    whose appearance state (/AS) is anything but Off."""
    reader = PdfReader(str(pdf_path))
    for pi, page in enumerate(reader.pages):
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            ft = w.get("/FT")
            if ft is None and "/Parent" in w:
                ft = w["/Parent"].get_object().get("/FT")
            if ft != "/Btn":
                continue
            state = w.get("/AS")
            if state is None or state == "/Off":
                continue
            yield pi, _field_name(w), [float(v) for v in w["/Rect"]], str(state)


def widget_rect(pdf_path, field_name: str, on_state: str | None = None):
    """(page_index, rect) of the widget named ``field_name`` (a radio kid is
    selected by its on-state name); raises KeyError if absent."""
    reader = PdfReader(str(pdf_path))
    for pi, page in enumerate(reader.pages):
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget" or _field_name(w) != field_name:
                continue
            if on_state is not None:
                ap = w.get("/AP")
                if ap is None or on_state not in ap["/N"]:
                    continue
            return pi, [float(v) for v in w["/Rect"]]
    raise KeyError(f"{field_name!r} (on_state={on_state!r}) not found in {pdf_path}")
