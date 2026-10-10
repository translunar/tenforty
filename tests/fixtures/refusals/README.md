Scenario fixtures that REFUSE at load, by design. Each is the firing case of
a named refusal. They live apart from `tests/fixtures/*.yaml` because several
tests sweep that directory and require every fixture in it to load.

`k1_partnership_passive.yaml` is the exception to "at load": it loads, and
refuses at COMPUTE (`passive_loss_limitation_not_applied` -- its passive K-1
carries a prior-year unallowed loss that Form 8582 takes in but the return
never deducts). It is here because it can no longer produce a return.
