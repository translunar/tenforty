# Changelog

All notable changes to tenforty are recorded here. This project is pre-1.0;
breaking changes are called out explicitly.

## Unreleased

### Added

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
- **Year-coverage policy:** new features floor at tax year 2022. A tax-year
  2021 return with a Schedule C business computes as before but refuses at PDF
  emit, and tax-year 2021 packets do not gain a Schedule 2.

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
