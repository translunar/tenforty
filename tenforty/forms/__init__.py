"""Per-form Python compute modules.

Each form module exposes:

    def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
        ...

Return values are keyed to PDF field names expected by the matching
mapping in `tenforty/mappings/pdf_<form>.py`, eliminating a separate
translation layer.
"""
