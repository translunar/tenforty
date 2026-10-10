"""MACRS mid-quarter percentage tables (Publication 946, Appendix A).

PENDING. The transcribed tables have not landed in this module yet. Until
they do, `TABLES_BY_QUARTER` refuses every read: no mid-quarter deduction
can be computed from a placeholder.

Shape the engine reads:
    TABLES_BY_QUARTER[placement quarter 1..4][class years][recovery year]
"""


class MidQuarterTablesNotLanded(RuntimeError):
    """A mid-quarter percentage was read before the tables landed."""


class _NotLanded:
    """Stands where the tables will be; any read of it raises."""

    def _refuse(self, *_args, **_kwargs):
        raise MidQuarterTablesNotLanded(
            "The MACRS mid-quarter tables have not landed in "
            "tenforty.params.macrs_mid_quarter. No mid-quarter depreciation "
            "can be computed until the transcribed tables replace this "
            "placeholder.")

    __getitem__ = __iter__ = __len__ = __contains__ = _refuse
    get = keys = values = items = _refuse


TABLES_BY_QUARTER = _NotLanded()
