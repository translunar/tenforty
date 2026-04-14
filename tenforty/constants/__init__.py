"""Year-parameterized tax constants.

One module per tax year (e.g. `y2025.py`). Imports resolve at form-compute
time; adding a new year means dropping a new module plus updating the
per-form mapping for PDF fields that changed.
"""
