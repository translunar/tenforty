"""Re-export shim: the pixel helpers moved to ``tenforty.verification.pixels``
(emit-verification harness check-suite lane). Every existing importer of
``tests._pdf_pixels`` keeps working unchanged."""
from tenforty.verification.pixels import *  # noqa: F401,F403
from tenforty.verification.pixels import (  # noqa: F401
    DARK_THRESHOLD,
    DEFAULT_DPI,
    checked_widgets,
    dark_pixels_in_rect,
    render_gray,
    widget_rect,
)
