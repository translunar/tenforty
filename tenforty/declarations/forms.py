"""The graduated forms: each one's declaration module, registered here.

This module owns registration: for every graduated form it imports the
declaration module and registers each of its ``DECLARATIONS``. The
declaration modules themselves stay side-effect-free, so a test can import
one directly (before or after graduation) without touching the registry.
``registry`` imports this module at its very bottom, after ``register`` is
defined, which is what breaks the cycle (registry -> forms -> registry).

A form is added here only in its graduation commit, together with its
removal from ``tenforty.verification.pending.PENDING_DECLARATIONS``: a
registered form that is still pending is a hard registry error (spec §10
D3). Declaration modules written but not yet graduated stay out of this
list and are inert.
"""
from tenforty.declarations import registry
from tenforty.declarations import sch_1, sch_2, sch_c, sch_d, sch_se

for _module in (sch_se, sch_c, sch_2, sch_1, sch_d):
    for _decl in _module.DECLARATIONS.values():
        registry.register(_decl)
