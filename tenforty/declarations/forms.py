"""The declared forms: one import per graduated form's declaration module.

Each imported module calls ``registry.register(...)`` at import time, so
importing this module populates the registry. ``registry`` imports this
module at its very bottom, after ``register`` is defined, which is what
breaks the cycle (registry -> forms -> <form> -> registry.register).

A form is imported here only in its graduation commit, together with its
removal from ``tenforty.verification.pending.PENDING_DECLARATIONS``: a
registered form that is still pending is a hard registry error (spec §10
D3). Declaration modules that are written but not yet graduated stay out of
this list and are inert.
"""
