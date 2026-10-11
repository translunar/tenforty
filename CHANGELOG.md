# Changelog

All notable changes to tenforty are recorded here. This project is pre-1.0;
breaking changes are called out explicitly.

## Unreleased

### Added

- **Form 3115 (Application for Change in Accounting Method) emits for
  automatic change number 7.** A top-level `form_3115:` block prints Form
  3115 (Rev. December 2022) for an individual changing depreciation from an
  impermissible to a permissible method, with a generated statement for
  Schedule E lines 4a and 7 built from the block's per-asset rows. Both join
  the federal packet after Form 4562; the two together are also written as a
  standalone duplicate copy to sign, and `f3115_filing_manifest_<year>.txt`
  lists the statements the applicant must still attach and where the signed
  duplicate is filed. The section 481(a) adjustment is **stated, not
  computed**, and is not carried onto the return's income. The under-$50,000
  one-year election is made on the form (line 28 and its de minimis box).
  Text cells must be quoted strings (an unquoted `00.11` is a number to
  YAML and would print as `0.11`), amounts must be exact to the cent, and an
  empty `form_3115:` key refuses rather than being read as absent.
  Every answer is an explicit attestation with no default; any other change
  number, applicant type, or answer the form would need more machinery for
  (under examination, before Appeals or a court, a prior change within five
  years, and others) refuses by name. An amendment packet refuses a
  scenario carrying the block.
- **Depreciable assets are the depreciation source of truth, per activity.**
  Assets now nest under the activity that uses them
  (`rental_properties[n].depreciable_assets`,
  `schedule_c_businesses[n].depreciable_assets`) and one resolver supplies
  each activity's depreciation to every consumer: Schedule E line 18,
  Schedule C line 13, the excess-business-loss guard, the routing
  estimates, the workbook inputs and the CA divergence trigger. An activity
  has exactly one source — its asset list, or its stated `depreciation`
  amount. Each asset-mode activity's engine-computed and used figures are
  written to the results (`depreciation_recon_*` keys) and printed in a
  "Depreciation Reconciliation" section. Supported: 27.5-year and 39-year
  real property, and 3/5/7/10/15/20-year personal property with no bonus or
  section 179 history. Everything else refuses by name.
- **Schedule C line 13 (depreciation) prints and counts.** It previously
  refused any nonzero amount. Section 179 remains unmodeled.
- **Value-pinned depreciation override.** An asset-mode activity may carry
  `depreciation_override: {amount, restates_engine_amount, acknowledgment}`.
  The return uses `amount`; the override refuses if `restates_engine_amount`
  no longer equals what the engine computes, and in any year the activity
  places property in service.
- **Breaking: a stated `depreciation` amount needs an acknowledgment.** A
  rental property or Schedule C business that states `depreciation` without
  an asset list must set
  `acknowledges_depreciation_stated_outside_macrs: true` on that activity.
  Activities with no depreciation need nothing.
- **Breaking: top-level `depreciable_assets:` refuses at load**, with a
  pointer to the nested location. Nothing computed from it before (no form
  line read it), but a scenario that carried one — and emitted a Form 4562
  from it — now stops at load.
- **Breaking: `convention:` on an asset refuses at load.** The convention is
  computed from the recovery class.
- **Breaking: asset fields.** An asset placed in service before the return
  year must state `prior_depreciation`, which must equal the MACRS-table
  reconstruction unless `acknowledges_prior_depreciation_as_stated: true`.
  Personal property must state `no_bonus_or_section_179_history: true`
  unless the activity carries an acknowledged `depreciation_override` (the
  reconciliation then notes that the engine figure is not a claim of
  correctness); real property must not carry the field. A `disposed` asset,
  an unsupported recovery class, and asset mode on any rental other than the
  first all refuse.
- **Basis ceiling: lifetime depreciation never exceeds basis.** A year's
  deduction is the lesser of the table amount and the basis left after the
  depreciation already taken — the table reconstruction of the earlier
  years, or the stated prior when `acknowledges_prior_depreciation_as_stated`
  accepts one that differs from the tables. Each year's table amount is
  rounded to whole dollars on its own, so a lifetime of them can come out a
  dollar over basis; the last year is trimmed. It is asymmetric: an
  undershoot (rounding, or a stated prior below the tables) is not topped
  up. When the ceiling binds, the reconciliation says so
  (`depreciation_recon_*_basis_ceiling_bound`) and says which cause it was.
  The reconstruction that `prior_depreciation` is checked against is held
  to the same ceiling, so a fully depreciated asset's stated prior may need
  to drop by a dollar to keep reconciling.
- **Mid-quarter convention is computed.** When personal property placed in
  service in the last three months of the year exceeds 40% of all personal
  property placed in service that year — across every activity on the
  return, real property excluded from both totals, strictly more than 40%
  (26 U.S.C. §168(d)(3)) — every personal-property asset placed that year
  is depreciated under the mid-quarter convention, from the table for the
  quarter it was placed in service (Publication 946 (2025), Appendix A,
  Tables A-2 through A-5, pp. 71–73). The comparison is made in whole
  cents, so bases that are exactly 40% never trip. This used to refuse; the
  `mid_quarter_convention` refusal is retired. The tables are transcribed
  twice, independently, and pinned to each other cell for cell. If an asset
  list places personal property this year while another activity states its
  depreciation as a single figure, the test still cannot be verified and
  the return refuses unless the top-level scenario key
  `acknowledges_no_personal_property_behind_stated_depreciation: true` is
  set.
- **Breaking: personal property placed in an earlier year states its
  convention.** The 40% test is run once, over the property placed in
  service in the return year. It is never run over an earlier year: this
  return's asset list is not that year's complete placements. So an asset
  in a 3-, 5-, 7-, 10-, 15- or 20-year class placed before the return year
  must state `convention: half-year`, or `convention: mid-quarter` with
  `quarter:` (1–4, the quarter of its own `date_placed_in_service`).
  Half-year is no longer assumed: a missing convention refuses, as does an
  unusable one. Its `prior_depreciation` is checked against the tables of
  the convention it states. Stating either key on real property (mid-month
  by statute) or on an asset placed in the return year (computed) refuses.
  **Every existing scenario with prior-year personal property needs the
  key added.**
- **Form 4562 column (f) prints the method the class takes**, spelled as
  the form's instructions spell it: `200 DB` for 3-, 5-, 7- and 10-year
  property, `150 DB` for 15- and 20-year property, `S/L` for real property
  (Publication 946, Chart 1). It previously printed `200DB` for every
  personal-property class — wrong for 15- and 20-year property — and only
  on the 2025 form; it is now filled on 2021–2024 as well. Column (e)
  prints `MQ` under the mid-quarter convention; under it, same-class assets
  placed in different quarters share their class row, with bases summed
  and the deduction the sum of the per-asset amounts.
- **Form 4562 rows 19a–19f print in the right columns on 2022–2024, and no
  year fills their shaded date cell.** On the 2022, 2023 and 2024 forms a
  personal-property row was written one column too far right (the date in
  the basis column, the basis under recovery period, the recovery period
  under convention, the convention under method). Separately, column (b),
  month and year placed in service, is shaded on rows 19a–19f — the form
  asks for it only on the residential and nonresidential rows — and the
  2021 and 2025 mappings wrote a date into it. Both are fixed on all five
  years. Any Form 4562 with a personal-property row should be re-emitted.
- **Outside the input space, by design: the alternative depreciation system
  and short tax years.** No scenario key can express either, the loader
  rejects any attempt to add one, and so there is no refusal for them and
  no path by which either could yield a wrong figure.
- **Breaking: Form 4562 is emitted only in a year property is placed in
  service** (Instructions for Form 4562, "Who Must File"). A return whose
  assets were all placed in earlier years no longer emits the form; its
  depreciation still prints on Schedule E line 18 / Schedule C line 13. The
  form remains one merged form per return, reading the nested assets;
  per-activity forms are not in this change. Because the merged form lists
  the engine's figures, a placement year on a return where any activity
  carries a `depreciation_override` refuses.
- **Listed property must be ruled out.** Form 4562 is required every year
  for a vehicle or other listed property, which tenforty does not model and
  cannot detect. A return listing any personal-property asset must set the
  top-level scenario key `acknowledges_no_listed_property: true`; without it
  the return refuses. Real-property-only returns are not asked.
- **Breaking: a negative stated rental `depreciation` refuses at load**, as
  negative Schedule C amounts already did.
- **Schedule C net losses.** A Schedule C business whose line 31 is a loss
  now computes and emits instead of refusing, when the new config
  attestation `acknowledges_sch_c_all_investment_at_risk` is true: box 32a is
  checked on each loss business, the loss flows to Schedule 1 line 3, no
  self-employment tax is figured on a net loss, and Form 8995 takes the loss
  as a negative QBI component (netted against other QBI, deduction floored at
  zero, remainder on the line 16 carryforward). Without the attestation a
  loss still refuses (Form 6198 is not modeled).
- **S corporation K-1 losses check Schedule E line 28 column (e).** A K-1
  from an S corporation whose Part II row nets to a loss now checks "basis
  computation is required" (tax years 2022-2025; other years refuse at emit)
  and is gated on the new attestation
  `acknowledges_form_7203_attached_separately`. Form 7203 itself is not
  produced; amendment packet manifests name it as a hand attachment. The gate
  runs on the native compute path and at emit; a compute-only run on the
  workbook path does not enforce it. **Breaking:** such a return previously
  computed with no gate.
- **Form 8995 line 16 prints its magnitude.** The loss-carryforward cell has
  preprinted parentheses; it previously received the signed value and read
  "( -N )". Re-emitted loss-year Forms 8995 differ in that cell.
- **§461(l) excess-business-loss guard.** A return whose business losses
  (Schedule C losses + K-1 business loss boxes + rental property losses, in
  whole dollars as the forms print them, with no business income netted)
  exceed the year's Form 461 threshold is
  refused, in every supported tax year. New `FederalParams` field
  `excess_business_loss_threshold`.

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
- **Direct deposit of a refund on original returns.** Three optional
  `config` fields, all or none: `refund_routing_number`,
  `refund_account_number` (both QUOTED strings — an unquoted number loses
  leading zeros and is refused) and `refund_account_type` (`"checking"` or
  `"savings"`). They print on Form 1040 lines 35b–35d and on California
  Form 540 line 116, whose amount box carries the line 115 refund. The
  fields are shared by both returns and each form decides for itself: a
  form showing a refund prints them, a form showing none leaves its deposit
  boxes blank. On a return with no refund on either form they therefore
  print nowhere, without a message. Load refuses a partial set, a routing
  number that is not 9 digits passing the ABA checksum, an account number
  that is not 4–17 digits, and any other account type. Out of scope: a
  split refund (Form 8888; Form 540 line 117), and amended returns — an
  amendment packet refuses the fields, because there is no direct deposit
  on a paper-filed amended return. To amend a return whose original
  scenario carries the fields, remove them from that scenario first.
  Account numbers are digits only; an alphanumeric account number is
  refused. A results snapshot (`write_results_snapshot`) never contains a
  routing or account number: keys ending `_routing_number` or
  `_account_number` are left out.

### Changed

- **MACRS table amounts round from the exact decimal product.** A year's
  table amount is basis × percentage, rounded half-up to whole dollars. The
  product was taken in binary floating point, which lands a dollar short
  whenever the true product ends in exactly .50 and the float falls just
  under it: a 27.5-year asset placed in June on a 25,000 basis is
  1.970% × 25,000 = 492.50, which printed 492 and now prints 493. The
  product is now exact decimal arithmetic, rounded once. Affected amounts
  move up by exactly one dollar; every other amount is unchanged. Because
  a stated `prior_depreciation` is checked against the same table amounts,
  an asset whose earlier years include such a product reconstructs a
  dollar higher per affected year and its stated prior must match.
- **Both new attestations are required in every scenario config** (load
  refuses when either is unset), like the existing scope-out attestations.
- **Schedule E lines 30 and 31 now print** on every return with a K-1 (they
  were mapped but never computed, so line 32 had no printed addends).
- **EIC routing estimate counts Schedule C losses.** A filer whose wages
  clear the EIC ceiling but whose wages less a Schedule C loss do not is no
  longer routed to the native 1040 path, which performs no EIC math.

- **Form 4562 prints prior-year assets on line 17, not line 19.** In a year
  that places property in service on a return that also carries assets
  placed in earlier years, the earlier assets used to merge into their
  line 19 class row (under the earliest in-service date, with the bases
  summed). Line 19 now lists only property placed in service during the
  return year; the MACRS deduction on everything placed earlier is one
  amount on line 17 (new result key `f4562_line_17`). Line 22 is their sum
  and is unchanged in amount. Any Form 4562 emitted for such a year should
  be re-emitted.
- **Form 4562 prints the SSN in the identifying-number box for 2022-2025.**
  Those years put it in the middle header box ("Business or activity to
  which this form relates") and left "Identifying number" blank. 2021 was
  already correct. Any 2022-2025 Form 4562 should be re-emitted.
- **Form 4562 fills "Business or activity to which this form relates".**
  The box carries the one activity that lists the form's assets, named as
  its own schedule names it: a rental's address (Schedule E line 1a) or a
  business's description (Schedule C line A). It stays blank when that
  activity has no name or when assets are listed on more than one activity
  (new result key `f4562_business_or_activity`).
- **Form 4562 line 22 prints on line 22 for 2022-2024.** Those years mapped
  the total to the line 25 box on page 2 (special depreciation allowance
  for listed property). 2021 and 2025 were already correct. Any 2022-2024
  Form 4562 should be re-emitted.

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
