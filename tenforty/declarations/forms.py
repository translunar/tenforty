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

``MODULES`` maps each graduated form to its declaration module: the one
place a consumer finds a form's module-level records (its witness
discrepancies, say). A form's catalog name is not always an importable
module name (Form 8959 is "8959"; its module is ``f8959``).
"""
from tenforty.declarations import registry
from tenforty.declarations import (
    f8959, sch_1, sch_2, sch_b, sch_c, sch_d, sch_se)


def modules_by_form(modules):
    """{FORM: module}; two modules declaring one form refuse."""
    by_form = {}
    for module in modules:
        if module.FORM in by_form:
            raise ValueError(
                f"{'/'.join(module.FORM)} is declared by two modules: "
                f"{by_form[module.FORM].__name__} and {module.__name__}.")
        by_form[module.FORM] = module
    return by_form


MODULES = modules_by_form((sch_se, sch_c, sch_2, sch_1, sch_d, f8959, sch_b))

for _module in MODULES.values():
    for _decl in _module.DECLARATIONS.values():
        registry.register(_decl)
