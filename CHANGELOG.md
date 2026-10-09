# Changelog

All notable changes to tenforty are recorded here. This project is pre-1.0;
breaking changes are called out explicitly.

## Unreleased

### Added

- **Amendment packets print the identity set.** Form 1040-X page 1 carries
  name, SSN, address and the filing-status checkbox; CA Schedule X carries
  name, SSN and the "Other" reason box; the amended Form 540 checks its
  AMENDED box. Previously all of these printed blank — re-emitted amendment
  packets differ from prior emits in these header cells. `PacketManifest`
  gains a `values` mapping (assembled 1040-X / Schedule X line values;
  excluded from equality and hash) for results snapshots.
- **Results snapshots and columnar cover sheets** (`tenforty.summary`).
  `write_results_snapshot` persists a return run's full results dict with
  metadata (year, label, scenario hash, emitted forms); `compose_cover`
  renders a one-page summary table from any set of snapshots — one column
  per return (a year, or side-by-side variants of the same year), a fixed
  general row vocabulary mirroring the 1040 (income by schedule family,
  computation, tax, state, amendment bottom lines), rows collapsing when
  empty everywhere except bottom lines, which always print.
- **Schedule C, Schedule SE and Schedule 2 PDF emission (tax years 2022–2025).**
  A return with `schedule_c_businesses` now emits a complete paper packet: one
  Schedule C per business (`f1040sc_<n>_<year>.pdf`, always numbered), one
  Schedule SE when self-employment tax is due, and Schedule 2. The emitted
  Schedule 1, Form 8959 and Form 8995 now receive the same Schedule C /
  Schedule SE figures as the compute path. `ScheduleCBusiness` gains
  `business_code` (Schedule C line B).
- **Schedule 2 now attaches to any natively-computed 2022–2025 return that
  owes an excess-APTC repayment or Additional Medicare Tax**, not only
  Schedule C returns. Re-emitting such a return produces a packet with one
  more form than before; this fills a gap where line 17 / line 23 printed with
  no detail schedule. Returns computed on the workbook path (non-single or
  EIC-possible filers) keep the previous convention, because their 1040 can
  carry AMT / NIIT that Schedule 2's modeled lines do not.
- **Form 8995 now attaches whenever a QBI deduction is claimed**, including a
  deduction that comes from Schedule C alone (previously only K-1 QBI
  attached it).
- **Year-coverage policy:** new features floor at tax year 2022.
- **Schedule C family extended to tax year 2021** (an exception to the floor
  above, for Schedule C, Schedule SE and Schedule 2 only). A tax-year 2021
  return with a Schedule C business now emits its packet instead of refusing,
  and any natively-computed tax-year 2021 return that owes an excess-APTC
  repayment, self-employment tax or Additional Medicare Tax now attaches
  Schedule 2. Re-emitting such a 2021 return produces a packet with one more
  form than before.

### Breaking

- **CA Schedule CA divergences: the `.ca.fods` worksheet round-trip is
  retired.** The FODS worksheet (auto-discovered as `<basename>.ca.fods`,
  hand-edited in LibreOffice, parsed at runtime) is no longer supported.
  Author your California divergences directly in the `.ca.yaml` instead:

  ```yaml
  ca540:
    divergences:
      - id: non-ca-muni-interest
        amount: 412
        note: "Vanguard national muni fund, non-CA portion per fund letter"
    reviewed:
      - prop22-wage-reclass
  ```

  Each `id` is validated at load time against the year's packaged CA
  divergence catalog (`tenforty/params/california/divergences/y<year>.yaml`),
  now the single runtime source of truth. For one release, a leftover
  `<basename>.ca.fods` file is detected and raises an explanatory error
  (rather than being silently ignored) pointing at the `.ca.yaml`
  `divergences:` / `reviewed:` format. Rationale and design:
  docs/specs/2026-07-19-ca-divergence-catalog-redesign.md §3.

  Removed with it: the `tenforty fods` CLI subcommand, the `tenforty ca`
  `--divergences` / `--no-fods` flags, the `scripts/build_sch_ca_fods.py`
  generator, the committed blank `.fods` worksheets, and the old
  `spreadsheets/california/<year>/sch_ca_divergences-<year>.catalog.yaml`
  catalogs (superseded by the packaged copies). The half-wired Schedule D
  (540) worksheet import is also retired; `CASchD540Adjustment` stays in the
  schema for the future CA Schedule D (540) divergence-compute follow-up.
