# Changelog

All notable changes to tenforty are recorded here. This project is pre-1.0;
breaking changes are called out explicitly.

## Unreleased

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
