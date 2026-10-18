"""Schedule 1 (Form 1040) emit declarations, TY2021-2025.

The adjudicated union of two independent authors
(/private/tmp/pilot-packet-sch_1/ADJUDICATION.md), on author A's structure:
each year's full line table is built from per-year text tables, and the year
is declared as a derive() diff from the previous one that must reproduce
that full table exactly (asserted at import). 2025 line 7's MeF element is
author A's (ruling 2).

Conventions (standing rulings): line universe = the official paper form,
each printed (section, line) once; unserved lines key="", single_state=
"nothing", reason "unmodeled: <official line text>"; descriptions =
stylesheet text verbatim, PAPER text wherever the stylesheet differs (the
paper's own "nonqualifed" typo on 8t kept literal); anchors only where the
default label row fails.

Year shape: 58 paper lines (2021) -> 63 (2022: other-income block 8a-8p
re-lettered and extended to 8u) -> 63 (2023) -> 64 (2024: 8v added) -> 64
(2025). Every non-header key binds the same line number every year, by
meaning: line 5 is the whole Schedule E total (not the personal-property
rental lines 8k/8l/24b); line 15 is the deductible part of SE tax.
"""
import dataclasses

from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "sch_1")
P1, P2 = "Part I", "Part II"
YEARS = (2021, 2022, 2023, 2024, 2025)


def _right_of(token):
    return NearLabel(phrase=token, relation=LabelRelation.RIGHT_OF)


# ------------------------------------------------- descriptions (verbatim)
_D21 = {
    ('Part I', '1'): 'Taxable refunds, credits, or offsets of state and local income taxes',
    ('Part I', '2a'): 'Alimony received',
    ('Part I', '2b'): 'Date of original divorce or separation agreement (see instructions)',
    ('Part I', '3'): 'Business income or (loss). Attach Schedule C',
    ('Part I', '4'): 'Other gains or (losses). Attach Form 4797',
    ('Part I', '5'): 'Rental real estate, royalties, partnerships, S corporations, trusts, etc. Attach Schedule E',
    ('Part I', '6'): 'Farm income or (loss). Attach Schedule F',
    ('Part I', '7'): 'Unemployment compensation',
    ('Part I', '8'): 'Other income:',
    ('Part I', '8a'): 'Net operating loss',
    ('Part I', '8b'): 'Gambling income',
    ('Part I', '8c'): 'Cancellation of debt',
    ('Part I', '8d'): 'Foreign earned income exclusion from Form 2555',
    ('Part I', '8e'): 'Taxable Health Savings Account distribution',
    ('Part I', '8f'): 'Alaska Permanent Fund dividends',
    ('Part I', '8g'): 'Jury duty pay',
    ('Part I', '8h'): 'Prizes and awards',
    ('Part I', '8i'): 'Activity not engaged in for profit income',
    ('Part I', '8j'): 'Stock options',
    ('Part I', '8k'): 'Income from the rental of personal property if you engaged in the rental for profit but were not in the business of renting such property',
    ('Part I', '8l'): 'Olympic and Paralympic medals and USOC prize money (see instructions)',
    ('Part I', '8m'): 'Section 951(a) inclusion (see instructions)',
    ('Part I', '8n'): 'Section 951A(a) inclusion (see instructions)',
    ('Part I', '8o'): 'Section 461(l) excess business loss adjustment',
    ('Part I', '8p'): 'Taxable distributions from an ABLE account (see instructions)',
    ('Part I', '8z'): 'Other income. List type and amount',
    ('Part I', '9'): 'Total other income. Add lines 8a through 8z',
    ('Part I', '10'): 'Combine lines 1 through 7 and 9. Enter here and on Form 1040, 1040-SR, or 1040-NR, line 8',
    ('Part II', '11'): 'Educator expenses',
    ('Part II', '12'): 'Certain business expenses of reservists, performing artists, and fee-basis government officials. Attach Form 2106',
    ('Part II', '13'): 'Health savings account deduction. Attach Form 8889',
    ('Part II', '14'): 'Moving expenses for members of the Armed Forces. Attach Form 3903',
    ('Part II', '15'): 'Deductible part of self-employment tax. Attach Schedule SE',
    ('Part II', '16'): 'Self-employed SEP, SIMPLE, and qualified plans',
    ('Part II', '17'): 'Self-employed health insurance deduction',
    ('Part II', '18'): 'Penalty on early withdrawal of savings',
    ('Part II', '19a'): 'Alimony paid',
    ('Part II', '19b'): "Recipient's SSN",
    ('Part II', '19c'): 'Date of original divorce or separation agreement (see instructions)',
    ('Part II', '20'): 'IRA Deduction',
    ('Part II', '21'): 'Student loan interest deduction',
    ('Part II', '22'): 'Reserved for future use',
    ('Part II', '23'): 'Archer MSA deduction',
    ('Part II', '24'): 'Other adjustments:',
    ('Part II', '24a'): 'Jury duty pay (see instructions)',
    ('Part II', '24b'): 'Deductible expenses related to income reported on line 8k from the rental of personal property engaged in for profit',
    ('Part II', '24c'): 'Nontaxable amount of the value of Olympic and Paralympic medals and USOC prize money reported on line 8l',
    ('Part II', '24d'): 'Reforestation amortization and expenses',
    ('Part II', '24e'): 'Repayment of supplemental unemployment benefits under the Trade Act of 1974',
    ('Part II', '24f'): 'Contributions to section 501(c)(18)(D) pension plans',
    ('Part II', '24g'): 'Contributions by certain chaplains to section 403(b) plans',
    ('Part II', '24h'): 'Attorney fees and court costs for actions involving certain unlawful discrimination claims (see instructions)',
    ('Part II', '24i'): 'Attorney fees and court costs you paid in connection with an award from the IRS for information you provided that helped the IRS detect tax law violations',
    ('Part II', '24j'): 'Housing deduction from Form 2555',
    ('Part II', '24k'): 'Excess deductions of section 67(e) expenses from Schedule K-1 (Form 1041)',
    ('Part II', '24z'): 'Other adjustments. List type and amount',
    ('Part II', '25'): 'Total other adjustments. Add lines 24a through 24z',
    ('Part II', '26'): 'Add lines 11 through 23 and 25. These are your adjustments to income. Enter here and on Form 1040 or 1040-SR, line 10, or Form 1040-NR, line 10a',
}
_TEXT_2022 = {  # vs 2021: changed text of existing lines, then lines new in 2022
    ('Part I', '8b'): 'Gambling',
    ('Part I', '8e'): 'Income from Form 8853',
    ('Part I', '8f'): 'Income from Form 8889',
    ('Part I', '8g'): 'Alaska Permanent Fund dividends',
    ('Part I', '8h'): 'Jury duty pay',
    ('Part I', '8i'): 'Prizes and awards',
    ('Part I', '8j'): 'Activity not engaged in for profit income',
    ('Part I', '8k'): 'Stock options',
    ('Part I', '8l'): 'Income from the rental of personal property if you engaged in the rental for profit but were not in the business of renting such property',
    ('Part I', '8m'): 'Olympic and Paralympic medals and USOC prize money (see instructions)',
    ('Part I', '8n'): 'Section 951(a) inclusion (see instructions)',
    ('Part I', '8o'): 'Section 951A(a) inclusion (see instructions)',
    ('Part I', '8p'): 'Section 461(l) excess business loss adjustment',
    ('Part I', '8q'): 'Taxable distributions from an ABLE account (see instructions)',
    ('Part I', '8r'): 'Scholarship and fellowship grants not reported on Form W-2',
    ('Part I', '8s'): 'Nontaxable amount of Medicaid waiver payments included on Form 1040, line 1a or 1d',
    ('Part I', '8t'): 'Pension or annuity from a nonqualifed deferred compensation plan or a nongovernmental section 457 plan',
    ('Part I', '8u'): 'Wages earned while incarcerated',
    ('Part II', '20'): 'IRA deduction',
    ('Part II', '24b'): 'Deductible expenses related to income reported on line 8l from the rental of personal property engaged in for profit',
    ('Part II', '24c'): 'Nontaxable amount of the value of Olympic and Paralympic medals and USOC prize money reported on line 8m',
}
_TEXT_2023 = {  # vs 2022: changed text of existing lines, then lines new in 2023
    ('Part I', '2b'): 'Date of original divorce or separation agreement (see instructions):',
    ('Part I', '8z'): 'Other income. List type and amount:',
    ('Part I', '10'): 'Combine lines 1 through 7 and 9. This is your additional income. Enter here and on Form 1040, 1040-SR, or 1040-NR, line 8',
    ('Part II', '19c'): 'Date of original divorce or separation agreement (see instructions):',
    ('Part II', '24z'): 'Other adjustments. List type and amount:',
    ('Part II', '26'): 'Add lines 11 through 23 and 25. These are your adjustments to income. Enter here and on Form 1040, 1040-SR, or 1040-NR, line 10',
}
_TEXT_2024 = {  # vs 2023: changed text of existing lines, then lines new in 2024
    ('Part I', '8v'): 'Digital assets received as ordinary income not reported elsewhere. See instructions.',
}
_TEXT_2025 = {  # vs 2024: changed text of existing lines, then lines new in 2025
    ('Part I', '4'): 'Other gains or (losses). Check if any from Form(s): 4797 4684',
    ('Part I', '7'): 'Unemployment compensation. If you repaid a 2025 overpayment (see instructions), check here and enter amount repaid:',
    ('Part II', '14'): 'Moving expenses for members of the Armed Forces. Attach Form 3903. If claiming only storage fees (see instructions), check here',
    ('Part II', '20'): 'IRA deduction. If you are married filing separately and lived apart from your spouse for the entire year (see instructions), check here',
}

# MeF element per (year, line) for unserved lines: the stylesheet's single
# plain element (None for captions / reserved lines).
_STY_MEF = {
    (2021, ('Part I', '1')): 'StateLocalIncomeTaxRefundAmt',
    (2021, ('Part I', '2a')): 'TotalAlimonyReceivedAmt',
    (2021, ('Part I', '3')): 'BusinessIncomeLossAmt',
    (2021, ('Part I', '4')): 'OtherGainLossAmt',
    (2021, ('Part I', '5')): 'RentalRealEstateIncomeLossAmt',
    (2021, ('Part I', '6')): 'NetFarmProfitLossAmt',
    (2021, ('Part I', '7')): 'UnemploymentCompAmt',
    (2021, ('Part I', '8a')): 'NetOperatingLossDeductionAmt',
    (2021, ('Part I', '8b')): 'GamblingReportableWinningAmt',
    (2021, ('Part I', '8c')): 'DebtCancellationAmt',
    (2021, ('Part I', '8d')): 'TotalIncomeExclusionAmt',
    (2021, ('Part I', '8e')): 'TotalTaxableHSADistributionAmt',
    (2021, ('Part I', '8f')): 'AlaskaPermanentFundDivAmt',
    (2021, ('Part I', '8g')): 'JuryDutyPayAmt',
    (2021, ('Part I', '8h')): 'PrizesAwardsAmt',
    (2021, ('Part I', '8i')): 'ActivityNotForProfitIncmAmt',
    (2021, ('Part I', '8j')): 'StockOptionsAmt',
    (2021, ('Part I', '8k')): 'RentalIncomePersonalPropAmt',
    (2021, ('Part I', '8l')): 'OlympicParalympicMedalUSOCAmt',
    (2021, ('Part I', '8m')): 'Section951aInclusionAmt',
    (2021, ('Part I', '8n')): 'Section951AaInclusionAmt',
    (2021, ('Part I', '8o')): 'ExcessBusinessLossAmt',
    (2021, ('Part I', '8p')): 'TaxableABLEDistributionsAmt',
    (2021, ('Part I', '8z')): 'OtherIncomeTotalAmt',
    (2021, ('Part I', '9')): 'TotalOtherIncomeAmt',
    (2021, ('Part I', '10')): 'TotalAdditionalIncomeAmt',
    (2021, ('Part II', '11')): 'EducatorExpensesAmt',
    (2021, ('Part II', '12')): 'BusExpnsReservistsAndOthersAmt',
    (2021, ('Part II', '13')): 'HealthSavingsAccountDedAmt',
    (2021, ('Part II', '15')): 'DeductibleSelfEmploymentTaxAmt',
    (2021, ('Part II', '16')): 'SelfEmpldSepSimpleQlfyPlansAmt',
    (2021, ('Part II', '17')): 'SelfEmpldHealthInsDedAmt',
    (2021, ('Part II', '18')): 'PnltyOnErlyWthdrwOfSavingsAmt',
    (2021, ('Part II', '19a')): 'TotalAlimonyPaidAmt',
    (2021, ('Part II', '21')): 'StudentLoanInterestDedAmt',
    (2021, ('Part II', '23')): 'ArcherMSADeductionAmt',
    (2021, ('Part II', '24a')): 'JuryDutyPayDeductionAmt',
    (2021, ('Part II', '24b')): 'RntlIncmPrsnlPropExpnssDedAmt',
    (2021, ('Part II', '24c')): 'OlympcPrlympcMedalUSOCDedAmt',
    (2021, ('Part II', '24d')): 'RforAmortzExpnssDedAmt',
    (2021, ('Part II', '24e')): 'RepaymentSuppUnemplBnftDedAmt',
    (2021, ('Part II', '24f')): 'Sect501c18DContriDedAmt',
    (2021, ('Part II', '24g')): 'Section403bContriDedAmt',
    (2021, ('Part II', '24h')): 'AttyFeesCrtCostsDedAmt',
    (2021, ('Part II', '24i')): 'AttyFeesCrtCostsPdDedAmt',
    (2021, ('Part II', '24j')): 'HousingDeductionAmt',
    (2021, ('Part II', '24k')): 'Section67eExcessDeductionAmt',
    (2021, ('Part II', '24z')): 'OtherAdjustmentsTotalAmt',
    (2021, ('Part II', '25')): 'TotalOtherAdjustmentsAmt',
    (2022, ('Part I', '1')): 'StateLocalIncomeTaxRefundAmt',
    (2022, ('Part I', '2a')): 'TotalAlimonyReceivedAmt',
    (2022, ('Part I', '3')): 'BusinessIncomeLossAmt',
    (2022, ('Part I', '4')): 'OtherGainLossAmt',
    (2022, ('Part I', '5')): 'RentalRealEstateIncomeLossAmt',
    (2022, ('Part I', '6')): 'NetFarmProfitLossAmt',
    (2022, ('Part I', '7')): 'UnemploymentCompAmt',
    (2022, ('Part I', '8a')): 'NetOperatingLossDeductionAmt',
    (2022, ('Part I', '8b')): 'GamblingReportableWinningAmt',
    (2022, ('Part I', '8c')): 'DebtCancellationAmt',
    (2022, ('Part I', '8d')): 'TotalIncomeExclusionAmt',
    (2022, ('Part I', '8e')): 'TotArcherMSAMedcrLTCAmt',
    (2022, ('Part I', '8f')): 'TotHSADistriHDHPAmt',
    (2022, ('Part I', '8g')): 'AlaskaPermanentFundDivAmt',
    (2022, ('Part I', '8h')): 'JuryDutyPayAmt',
    (2022, ('Part I', '8i')): 'PrizesAwardsAmt',
    (2022, ('Part I', '8j')): 'ActivityNotForProfitIncmAmt',
    (2022, ('Part I', '8k')): 'StockOptionsAmt',
    (2022, ('Part I', '8l')): 'RentalIncomePersonalPropAmt',
    (2022, ('Part I', '8m')): 'OlympicParalympicMedalUSOCAmt',
    (2022, ('Part I', '8n')): 'Section951aInclusionAmt',
    (2022, ('Part I', '8o')): 'Section951AaInclusionAmt',
    (2022, ('Part I', '8p')): 'ExcessBusinessLossAmt',
    (2022, ('Part I', '8q')): 'TaxableABLEDistributionsAmt',
    (2022, ('Part I', '8r')): 'GrantsOrScholarshipsAmt',
    (2022, ('Part I', '8s')): 'NontxMedicaidWaiverPymtAmt',
    (2022, ('Part I', '8t')): 'NonqlfyDeferredCompensationAmt',
    (2022, ('Part I', '8u')): 'CertainPenalInstnWagesAmt',
    (2022, ('Part I', '8z')): 'OtherIncomeTotalAmt',
    (2022, ('Part I', '9')): 'TotalOtherIncomeAmt',
    (2022, ('Part I', '10')): 'TotalAdditionalIncomeAmt',
    (2022, ('Part II', '11')): 'EducatorExpensesAmt',
    (2022, ('Part II', '12')): 'BusExpnsReservistsAndOthersAmt',
    (2022, ('Part II', '13')): 'HealthSavingsAccountDedAmt',
    (2022, ('Part II', '15')): 'DeductibleSelfEmploymentTaxAmt',
    (2022, ('Part II', '16')): 'SelfEmpldSepSimpleQlfyPlansAmt',
    (2022, ('Part II', '17')): 'SelfEmpldHealthInsDedAmt',
    (2022, ('Part II', '18')): 'PnltyOnErlyWthdrwOfSavingsAmt',
    (2022, ('Part II', '19a')): 'TotalAlimonyPaidAmt',
    (2022, ('Part II', '21')): 'StudentLoanInterestDedAmt',
    (2022, ('Part II', '23')): 'ArcherMSADeductionAmt',
    (2022, ('Part II', '24a')): 'JuryDutyPayDeductionAmt',
    (2022, ('Part II', '24b')): 'RntlIncmPrsnlPropExpnssDedAmt',
    (2022, ('Part II', '24c')): 'OlympcPrlympcMedalUSOCDedAmt',
    (2022, ('Part II', '24d')): 'RforAmortzExpnssDedAmt',
    (2022, ('Part II', '24e')): 'RepaymentSuppUnemplBnftDedAmt',
    (2022, ('Part II', '24f')): 'Sect501c18DContriDedAmt',
    (2022, ('Part II', '24g')): 'Section403bContriDedAmt',
    (2022, ('Part II', '24h')): 'AttyFeesCrtCostsDedAmt',
    (2022, ('Part II', '24i')): 'AttyFeesCrtCostsPdDedAmt',
    (2022, ('Part II', '24j')): 'HousingDeductionAmt',
    (2022, ('Part II', '24k')): 'Section67eExcessDeductionAmt',
    (2022, ('Part II', '24z')): 'OtherAdjustmentsTotalAmt',
    (2022, ('Part II', '25')): 'TotalOtherAdjustmentsAmt',
    (2023, ('Part I', '1')): 'StateLocalIncomeTaxRefundAmt',
    (2023, ('Part I', '2a')): 'TotalAlimonyReceivedAmt',
    (2023, ('Part I', '3')): 'BusinessIncomeLossAmt',
    (2023, ('Part I', '4')): 'OtherGainLossAmt',
    (2023, ('Part I', '5')): 'RentalRealEstateIncomeLossAmt',
    (2023, ('Part I', '6')): 'NetFarmProfitLossAmt',
    (2023, ('Part I', '7')): 'UnemploymentCompAmt',
    (2023, ('Part I', '8a')): 'NetOperatingLossDeductionAmt',
    (2023, ('Part I', '8b')): 'GamblingReportableWinningAmt',
    (2023, ('Part I', '8c')): 'DebtCancellationAmt',
    (2023, ('Part I', '8d')): 'TotalIncomeExclusionAmt',
    (2023, ('Part I', '8e')): 'TotArcherMSAMedcrLTCAmt',
    (2023, ('Part I', '8f')): 'TotHSADistriHDHPAmt',
    (2023, ('Part I', '8g')): 'AlaskaPermanentFundDivAmt',
    (2023, ('Part I', '8h')): 'JuryDutyPayAmt',
    (2023, ('Part I', '8i')): 'PrizesAwardsAmt',
    (2023, ('Part I', '8j')): 'ActivityNotForProfitIncmAmt',
    (2023, ('Part I', '8k')): 'StockOptionsAmt',
    (2023, ('Part I', '8l')): 'RentalIncomePersonalPropAmt',
    (2023, ('Part I', '8m')): 'OlympicParalympicMedalUSOCAmt',
    (2023, ('Part I', '8n')): 'Section951aInclusionAmt',
    (2023, ('Part I', '8o')): 'Section951AaInclusionAmt',
    (2023, ('Part I', '8p')): 'ExcessBusinessLossAmt',
    (2023, ('Part I', '8q')): 'TaxableABLEDistributionsAmt',
    (2023, ('Part I', '8r')): 'GrantsOrScholarshipsAmt',
    (2023, ('Part I', '8s')): 'NontxMedicaidWaiverPymtAmt',
    (2023, ('Part I', '8t')): 'NonqlfyDeferredCompensationAmt',
    (2023, ('Part I', '8u')): 'CertainPenalInstnWagesAmt',
    (2023, ('Part I', '8z')): 'OtherIncomeTotalAmt',
    (2023, ('Part I', '9')): 'TotalOtherIncomeAmt',
    (2023, ('Part I', '10')): 'TotalAdditionalIncomeAmt',
    (2023, ('Part II', '11')): 'EducatorExpensesAmt',
    (2023, ('Part II', '12')): 'BusExpnsReservistsAndOthersAmt',
    (2023, ('Part II', '13')): 'HealthSavingsAccountDedAmt',
    (2023, ('Part II', '15')): 'DeductibleSelfEmploymentTaxAmt',
    (2023, ('Part II', '16')): 'SelfEmpldSepSimpleQlfyPlansAmt',
    (2023, ('Part II', '17')): 'SelfEmpldHealthInsDedAmt',
    (2023, ('Part II', '18')): 'PnltyOnErlyWthdrwOfSavingsAmt',
    (2023, ('Part II', '19a')): 'TotalAlimonyPaidAmt',
    (2023, ('Part II', '21')): 'StudentLoanInterestDedAmt',
    (2023, ('Part II', '23')): 'ArcherMSADeductionAmt',
    (2023, ('Part II', '24a')): 'JuryDutyPayDeductionAmt',
    (2023, ('Part II', '24b')): 'RntlIncmPrsnlPropExpnssDedAmt',
    (2023, ('Part II', '24c')): 'OlympcPrlympcMedalUSOCDedAmt',
    (2023, ('Part II', '24d')): 'RforAmortzExpnssDedAmt',
    (2023, ('Part II', '24e')): 'RepaymentSuppUnemplBnftDedAmt',
    (2023, ('Part II', '24f')): 'Sect501c18DContriDedAmt',
    (2023, ('Part II', '24g')): 'Section403bContriDedAmt',
    (2023, ('Part II', '24h')): 'AttyFeesCrtCostsDedAmt',
    (2023, ('Part II', '24i')): 'AttyFeesCrtCostsPdDedAmt',
    (2023, ('Part II', '24j')): 'HousingDeductionAmt',
    (2023, ('Part II', '24k')): 'Section67eExcessDeductionAmt',
    (2023, ('Part II', '24z')): 'OtherAdjustmentsTotalAmt',
    (2023, ('Part II', '25')): 'TotalOtherAdjustmentsAmt',
    (2024, ('Part I', '1')): 'StateLocalIncomeTaxRefundAmt',
    (2024, ('Part I', '2a')): 'TotalAlimonyReceivedAmt',
    (2024, ('Part I', '3')): 'BusinessIncomeLossAmt',
    (2024, ('Part I', '4')): 'OtherGainLossAmt',
    (2024, ('Part I', '5')): 'RentalRealEstateIncomeLossAmt',
    (2024, ('Part I', '6')): 'NetFarmProfitLossAmt',
    (2024, ('Part I', '7')): 'UnemploymentCompAmt',
    (2024, ('Part I', '8a')): 'NetOperatingLossDeductionAmt',
    (2024, ('Part I', '8b')): 'GamblingReportableWinningAmt',
    (2024, ('Part I', '8c')): 'DebtCancellationAmt',
    (2024, ('Part I', '8d')): 'TotalIncomeExclusionAmt',
    (2024, ('Part I', '8e')): 'TotArcherMSAMedcrLTCAmt',
    (2024, ('Part I', '8f')): 'TotHSADistriHDHPAmt',
    (2024, ('Part I', '8g')): 'AlaskaPermanentFundDivAmt',
    (2024, ('Part I', '8h')): 'JuryDutyPayAmt',
    (2024, ('Part I', '8i')): 'PrizesAwardsAmt',
    (2024, ('Part I', '8j')): 'ActivityNotForProfitIncmAmt',
    (2024, ('Part I', '8k')): 'StockOptionsAmt',
    (2024, ('Part I', '8l')): 'RentalIncomePersonalPropAmt',
    (2024, ('Part I', '8m')): 'OlympicParalympicMedalUSOCAmt',
    (2024, ('Part I', '8n')): 'Section951aInclusionAmt',
    (2024, ('Part I', '8o')): 'Section951AaInclusionAmt',
    (2024, ('Part I', '8p')): 'ExcessBusinessLossAmt',
    (2024, ('Part I', '8q')): 'TaxableABLEDistributionsAmt',
    (2024, ('Part I', '8r')): 'GrantsOrScholarshipsAmt',
    (2024, ('Part I', '8s')): 'NontxMedicaidWaiverPymtAmt',
    (2024, ('Part I', '8t')): 'NonqlfyDeferredCompensationAmt',
    (2024, ('Part I', '8u')): 'CertainPenalInstnWagesAmt',
    (2024, ('Part I', '8v')): 'DigitalAssetsAmt',
    (2024, ('Part I', '8z')): 'OtherIncomeTotalAmt',
    (2024, ('Part I', '9')): 'TotalOtherIncomeAmt',
    (2024, ('Part I', '10')): 'TotalAdditionalIncomeAmt',
    (2024, ('Part II', '11')): 'EducatorExpensesAmt',
    (2024, ('Part II', '12')): 'BusExpnsReservistsAndOthersAmt',
    (2024, ('Part II', '13')): 'HealthSavingsAccountDedAmt',
    (2024, ('Part II', '15')): 'DeductibleSelfEmploymentTaxAmt',
    (2024, ('Part II', '16')): 'SelfEmpldSepSimpleQlfyPlansAmt',
    (2024, ('Part II', '17')): 'SelfEmpldHealthInsDedAmt',
    (2024, ('Part II', '18')): 'PnltyOnErlyWthdrwOfSavingsAmt',
    (2024, ('Part II', '19a')): 'TotalAlimonyPaidAmt',
    (2024, ('Part II', '21')): 'StudentLoanInterestDedAmt',
    (2024, ('Part II', '23')): 'ArcherMSADeductionAmt',
    (2024, ('Part II', '24a')): 'JuryDutyPayDeductionAmt',
    (2024, ('Part II', '24b')): 'RntlIncmPrsnlPropExpnssDedAmt',
    (2024, ('Part II', '24c')): 'OlympcPrlympcMedalUSOCDedAmt',
    (2024, ('Part II', '24d')): 'RforAmortzExpnssDedAmt',
    (2024, ('Part II', '24e')): 'RepaymentSuppUnemplBnftDedAmt',
    (2024, ('Part II', '24f')): 'Sect501c18DContriDedAmt',
    (2024, ('Part II', '24g')): 'Section403bContriDedAmt',
    (2024, ('Part II', '24h')): 'AttyFeesCrtCostsDedAmt',
    (2024, ('Part II', '24i')): 'AttyFeesCrtCostsPdDedAmt',
    (2024, ('Part II', '24j')): 'HousingDeductionAmt',
    (2024, ('Part II', '24k')): 'Section67eExcessDeductionAmt',
    (2024, ('Part II', '24z')): 'OtherAdjustmentsTotalAmt',
    (2024, ('Part II', '25')): 'TotalOtherAdjustmentsAmt',
    (2025, ('Part I', '1')): 'StateLocalIncomeTaxRefundAmt',
    (2025, ('Part I', '2a')): 'TotalAlimonyReceivedAmt',
    (2025, ('Part I', '3')): 'BusinessIncomeLossAmt',
    (2025, ('Part I', '5')): 'RentalRealEstateIncomeLossAmt',
    (2025, ('Part I', '6')): 'NetFarmProfitLossAmt',
    (2025, ('Part I', '8a')): 'NetOperatingLossDeductionAmt',
    (2025, ('Part I', '8b')): 'GamblingReportableWinningAmt',
    (2025, ('Part I', '8c')): 'DebtCancellationAmt',
    (2025, ('Part I', '8d')): 'TotalIncomeExclusionAmt',
    (2025, ('Part I', '8e')): 'TotArcherMSAMedcrLTCAmt',
    (2025, ('Part I', '8f')): 'TotHSADistriHDHPAmt',
    (2025, ('Part I', '8g')): 'AlaskaPermanentFundDivAmt',
    (2025, ('Part I', '8h')): 'JuryDutyPayAmt',
    (2025, ('Part I', '8i')): 'PrizesAwardsAmt',
    (2025, ('Part I', '8j')): 'ActivityNotForProfitIncmAmt',
    (2025, ('Part I', '8k')): 'StockOptionsAmt',
    (2025, ('Part I', '8l')): 'RentalIncomePersonalPropAmt',
    (2025, ('Part I', '8m')): 'OlympicParalympicMedalUSOCAmt',
    (2025, ('Part I', '8n')): 'Section951aInclusionAmt',
    (2025, ('Part I', '8o')): 'Section951AaInclusionAmt',
    (2025, ('Part I', '8p')): 'ExcessBusinessLossAmt',
    (2025, ('Part I', '8q')): 'TaxableABLEDistributionsAmt',
    (2025, ('Part I', '8r')): 'GrantsOrScholarshipsAmt',
    (2025, ('Part I', '8s')): 'NontxMedicaidWaiverPymtAmt',
    (2025, ('Part I', '8t')): 'NonqlfyDeferredCompensationAmt',
    (2025, ('Part I', '8u')): 'CertainPenalInstnWagesAmt',
    (2025, ('Part I', '8v')): 'DigitalAssetsAmt',
    (2025, ('Part I', '8z')): 'OtherIncomeTotalAmt',
    (2025, ('Part I', '9')): 'TotalOtherIncomeAmt',
    (2025, ('Part I', '10')): 'TotalAdditionalIncomeAmt',
    (2025, ('Part II', '11')): 'EducatorExpensesAmt',
    (2025, ('Part II', '12')): 'BusExpnsReservistsAndOthersAmt',
    (2025, ('Part II', '13')): 'HealthSavingsAccountDedAmt',
    (2025, ('Part II', '15')): 'DeductibleSelfEmploymentTaxAmt',
    (2025, ('Part II', '16')): 'SelfEmpldSepSimpleQlfyPlansAmt',
    (2025, ('Part II', '17')): 'SelfEmpldHealthInsDedAmt',
    (2025, ('Part II', '18')): 'PnltyOnErlyWthdrwOfSavingsAmt',
    (2025, ('Part II', '19a')): 'TotalAlimonyPaidAmt',
    (2025, ('Part II', '21')): 'StudentLoanInterestDedAmt',
    (2025, ('Part II', '23')): 'ArcherMSADeductionAmt',
    (2025, ('Part II', '24a')): 'JuryDutyPayDeductionAmt',
    (2025, ('Part II', '24b')): 'RntlIncmPrsnlPropExpnssDedAmt',
    (2025, ('Part II', '24c')): 'OlympcPrlympcMedalUSOCDedAmt',
    (2025, ('Part II', '24d')): 'RforAmortzExpnssDedAmt',
    (2025, ('Part II', '24e')): 'RepaymentSuppUnemplBnftDedAmt',
    (2025, ('Part II', '24f')): 'Sect501c18DContriDedAmt',
    (2025, ('Part II', '24g')): 'Section403bContriDedAmt',
    (2025, ('Part II', '24h')): 'AttyFeesCrtCostsDedAmt',
    (2025, ('Part II', '24i')): 'AttyFeesCrtCostsPdDedAmt',
    (2025, ('Part II', '24j')): 'HousingDeductionAmt',
    (2025, ('Part II', '24k')): 'Section67eExcessDeductionAmt',
    (2025, ('Part II', '24z')): 'OtherAdjustmentsTotalAmt',
    (2025, ('Part II', '25')): 'TotalOtherAdjustmentsAmt',
}


# ------------------------------------------------------------- bindings
# key, mef_element, comment. Every binding holds for 2021-2025.
_BOUND = {
    (P1, "1"): ("sch_1_line_1_taxable_refunds", "StateLocalIncomeTaxRefundAmt"),
    (P1, "3"): ("sch_1_line_3_business_income", "BusinessIncomeLossAmt"),
    # 4: 2025 adds 'Check if any from Form(s): 4797 4684' boxes on the line
    # (unserved sub-prints).
    (P1, "4"): ("sch_1_line_4_other_gains", "OtherGainLossAmt"),
    # 5 (seam): official "Rental real estate, royalties, partnerships, S
    # corporations, trusts, etc. Attach Schedule E". Seam candidates 8k/8l
    # and 24b are the RENTAL OF PERSONAL PROPERTY lines (income 8k in 2021,
    # 8l from 2022; expenses 24b) -- a different line family; the key's
    # "rental_re" (real estate) + "royalty" matches line 5 only.
    # PARTIAL-TOTAL RISK: the key name covers rental real estate and
    # royalties, but line 5 also carries partnership, S corporation, estate
    # and trust income (the whole Schedule E total). The printed value must
    # be that total, not the rental/royalty part alone.
    (P1, "5"): ("sch_1_line_5_rental_re_royalty", "RentalRealEstateIncomeLossAmt"),
    (P1, "6"): ("sch_1_line_6_farm_income", "NetFarmProfitLossAmt"),
    # 7: 2025 adds a repaid-overpayment checkbox and repaid-amount entry on
    # the line (unserved sub-prints).
    (P1, "7"): ("sch_1_line_7_unemployment", "UnemploymentCompAmt"),
    # 8z: auto_confirmed; official "Other income. List type and amount".
    # The type/description text entry on the same row has no key. NOTE: line
    # 9 "Total other income. Add lines 8a through 8z" has no key, so with a
    # nonzero 8z the form would print 8z but leave its own subtotal (9)
    # blank -- an emit gap to check, not a binding question.
    (P1, "8z"): ("sch_1_line_8z_other_income", "OtherIncomeTotalAmt"),
    # 9: official "Total other income. Add lines 8a through 8z". 8z is the
    # only modeled 8a-8z line, so the computation sets 9 = 8z.
    (P1, "9"): ("sch_1_line_9_total_other_income", "TotalOtherIncomeAmt"),
    # 10 (auto_confirmed except 2023 'disagree'): official "Combine lines 1
    # through 7 and 9" (2023+: "...This is your additional income").
    # PARTIAL-TOTAL RISK: 2a, 8a-8y and 9 are unmodeled but in the sum.
    (P1, "10"): ("sch_1_line_10_total_additional_income", "TotalAdditionalIncomeAmt"),
    (P2, "11"): ("sch_1_line_11_educator", "EducatorExpensesAmt"),
    (P2, "13"): ("sch_1_line_13_hsa", "HealthSavingsAccountDedAmt"),
    # 15: official "Deductible part of self-employment tax"; 1040
    # instructions (2024), Line 15: "The deductible part of your
    # self-employment tax is on line 13 of Schedule SE." The key name says
    # "se_tax" -- the printed value must be the deductible HALF (Sch SE line
    # 13), not the tax itself (Sch SE line 12 / Sch 2 line 4).
    (P2, "15"): ("sch_1_line_15_se_tax", "DeductibleSelfEmploymentTaxAmt"),
    (P2, "17"): ("sch_1_line_17_se_health", "SelfEmpldHealthInsDedAmt"),
    # 20: 2025 adds an MFS-lived-apart checkbox on the line (unserved).
    (P2, "20"): ("sch_1_line_20_ira", "IRADeductionAmt"),
    (P2, "21"): ("sch_1_line_21_student_loan_interest", "StudentLoanInterestDedAmt"),
    # 26 ('disagree' 2021-23, auto_confirmed 2024-25): official "Add lines 11
    # through 23 and 25. These are your adjustments to income." Key matches.
    # PARTIAL-TOTAL RISK: 12, 14, 16, 18, 19a, 23 and 25 are unmodeled but
    # in the sum.
    (P2, "26"): ("sch_1_line_26_total_adjustments", "TotalAdjustmentsAmt"),
}

# MeF elements for unserved lines where the stylesheet's choice is not a
# single plain element.
_MEF_UNSERVED = {
    (P1, "2a"): "TotalAlimonyReceivedAmt",
    (P1, "2b"): "AlimonyReceivedGrp/DivorceOrSeparationAgreementDt",
    (P2, "14"): "MovingExpenseAmt",
    (P2, "19a"): "TotalAlimonyPaidAmt",
    (P2, "19b"): "AlimonyAmountGrp/RecipientSSN",
    (P2, "19c"): "AlimonyAmountGrp/DivorceOrSeparationAgreementDt",
}
_KIND = {(P1, "2b"): "date", (P2, "19b"): "ssn", (P2, "19c"): "date"}
# 19b/19c print inline (no right-margin box label), so the 2021-2023
# inventory extractor misses them; the 2024 inventory lists them.
_INVENTORY_EXEMPT = {
    (P2, "19b"): (2021, 2022, 2023),
    (P2, "19c"): (2021, 2022, 2023),
}
_EXEMPTION = ("the paper prints this line inline with no right-margin box "
              "label; the inventory extractor captures only box-labeled "
              "lines in this year (it lists it from 2024)")
_CAPTION = {(P1, "8"), (P2, "22"), (P2, "24")}  # no entry space

# ------------------------------------------------------------- anchors
# Only where the default label row fails. All measured per year.
_ALL = set(YEARS)
_ANCHORS = {
    # 5 (2021), 10 and 26 wrap, but each amount box sits alone on its row
    # and the default row label places it (ruled): no explicit anchor.
    # 8z: label row carries the caption; the amount entry (box label "8z",
    # x~395-406) is on the next row, which also holds the full-width
    # type/description text entry (x65-382) -- two entries on that row. The
    # box label sits immediately left of the amount entry (gap 4-6 pt).
    # "8z" also prints in line 9's text ("8a through 8z") with no entry box
    # within LABEL_GAP_PT to its right. (No field is mapped for 8z yet: the
    # known gap, graduation blocker sch_1-8z-9-mapping-gap.)
    (P1, "8z"): (_ALL, _right_of("8z")),
    # 2025 only: rows that gained boxes. 4: the entry row (y233) also holds
    # the Form 4797 / 4684 boxes. 7: label wraps (y269->y281) and the entry
    # row also holds the repaid-amount text entry. 20: label wraps
    # (y227->y239) and the entry row also holds the MFS-lived-apart box.
    # Each anchor is the box label immediately left of the amount entry
    # (gap 6-8 pt); the left-margin numbers have text, not entries, to their
    # right.
    (P1, "4"): ({2025}, _right_of("4")),
    (P1, "7"): ({2025}, _right_of("7")),
    (P2, "20"): ({2025}, _right_of("20")),
}


def _texts(year):
    d = dict(_D21)
    for y in YEARS[1:]:
        if y > year:
            break
        d.update(globals()[f"_TEXT_{y}"])
    return d


def _order(d):
    """Paper order: Part I then Part II, numeric, then sub-letter."""
    def k(i):
        num = "".join(c for c in i[1] if c.isdigit())
        return (i[0] != P1, int(num), i[1][len(num):])
    return sorted(d, key=k)


# Value-only lines (the sch_c / sch_2 precedent): forms/sch_1.py's return
# dict sets every non-header key unconditionally, zeros included, so no
# scenario can leave a bound line absent.
_EMITTED = ("the computation emits this key unconditionally on every "
            "Schedule 1 (forms/sch_1.py's return dict sets it, zero "
            "included), so its nothing state is unreachable")
_TOTALS = {(P1, "10"), (P2, "26")}
# Two-state bound lines: the computation leaves the key ABSENT when nothing is
# computed. Line 8z is a write-in: with no nonzero Form 1099-G type the
# computation emits no 8z keys (amount, type write-in, line 9 subtotal) and
# they stay blank (team-lead R2, sch_1-8z-9-mapping-gap lane), so 8z, its
# write-in (two-state by construction, see _8z_type_line) and 9 are observed
# in both states.
_TWO_STATE = {(P1, "8z"), (P1, "9")}
_TOTAL = (_EMITTED + "; on the paper it is the part total every filer "
          "completes: zero is a value")


def full_table(year):
    """``year``'s complete declared line table, in paper order."""
    return _full(year)


# Line 8z's type write-in, declared as its own line "8z(type)" (the
# computation's sch_1_line_8z_description): the paper's "List type and
# amount" entry. Neither witness lists it (the inventory and the stylesheet
# carry 8z's amount only), so it is inventory-exempt and its stylesheet
# finding is a documented witness discrepancy. Anchor, measured per year: the
# caption-row field sits right of the caption's last words (2021 prints them
# without the colon); 2025's single multiline field begins left of the
# caption on the same rows, so ON_ROW. Each phrase prints once on its page,
# and the anchor rejects the second description row and line 9.
_8Z_TYPE = (P1, "8z(type)")
_8Z_TYPE_KEY = "sch_1_line_8z_description"
_8Z_TYPE_EXEMPTION = ("the paper's 8z type write-in is an entry the "
                      "inventory extractor does not list (it lists line 8z's "
                      "amount only)")


def _8z_type_anchor(year):
    if year == 2021:
        return NearLabel("List type and amount", LabelRelation.RIGHT_OF)
    if year == 2025:
        return NearLabel("List type and amount:", LabelRelation.ON_ROW)
    return NearLabel("List type and amount:", LabelRelation.RIGHT_OF)


def _8z_type_line(year, description):
    return DeclaredLine(line=_8Z_TYPE[1], description=description,
                        key=_8Z_TYPE_KEY, kind="text", section=_8Z_TYPE[0],
                        anchor=_8z_type_anchor(year),
                        inventory_exemption=_8Z_TYPE_EXEMPTION)


def _full(year):
    d = _texts(year)
    out = []
    for i in _order(d):
        sec, line = i
        anchor = None
        if i in _ANCHORS and year in _ANCHORS[i][0]:
            anchor = _ANCHORS[i][1]
        if i in _BOUND:
            key, mef = _BOUND[i]
            two_state = i in _TWO_STATE
            out.append(DeclaredLine(line=line, description=d[i], key=key,
                                    kind="amount", section=sec, anchor=anchor,
                                    mef_element=mef,
                                    single_state=None if two_state else "value",
                                    single_state_reason=None if two_state else (
                                        _TOTAL if i in _TOTALS else _EMITTED)))
            if i == (P1, "8z"):
                out.append(_8z_type_line(year, d[i]))
        else:
            meaning = (("caption only, no entry space: " + d[i])
                       if i in _CAPTION else d[i])
            exempt = year in _INVENTORY_EXEMPT.get(i, ())
            out.append(DeclaredLine(
                line=line, description=d[i], key="", kind=_KIND.get(i, "amount"),
                section=sec, single_state="nothing",
                single_state_reason="unmodeled: " + meaning,
                mef_element=_MEF_UNSERVED.get(i, _STY_MEF.get((year, i))),
                inventory_exemption=_EXEMPTION if exempt else None))
    return tuple(out)


def _as_diff(prev, year):
    """``year`` as an explicit derive() diff from ``prev``: lines whose
    content changed are dropped and re-added, new lines are added."""
    full = {ln.line_id: ln for ln in _full(year)}
    old = {ln.line_id: ln for ln in prev.lines}
    assert set(old) <= set(full), "no paper line is ever removed 2021-2025"
    changed = [i for i in old if old[i] != full[i]]
    new = [i for i in full if i not in old]
    out = derive(prev, year, drop=changed,
                 add=[full[i] for i in changed + new])
    assert {ln.line_id: ln for ln in out.lines} == full, year
    return out


# The header keys are outside the line inventory; the 8z statement rows feed
# the attached statement, not a Schedule 1 field.
_NOT_PRINTED = {
    "sch_1_line_8z_statement_rows": (
        "intermediate: the 8z statement's (type, amount) rows; the emitter "
        "attaches the statement when there are two or more, and the 8z "
        "write-in then reads 'See statement'"),
    "taxpayer_name": ("presentation-only: page 1 header 'Name(s) shown on "
                      "Form 1040, 1040-SR, or 1040-NR', outside the line "
                      "inventory"),
    "taxpayer_ssn": ("presentation-only: page 1 header 'Your social "
                     "security number', outside the line inventory"),
}

SCH_1_2021 = FormDeclaration(form=FORM, key=2021, lines=_full(2021),
                             not_printed=_NOT_PRINTED)
SCH_1_2022 = _as_diff(SCH_1_2021, 2022)
SCH_1_2023 = _as_diff(SCH_1_2022, 2023)
SCH_1_2024 = _as_diff(SCH_1_2023, 2024)
SCH_1_2025 = _as_diff(SCH_1_2024, 2025)
DECLARATIONS = {d.key: d for d in
                (SCH_1_2021, SCH_1_2022, SCH_1_2023, SCH_1_2024, SCH_1_2025)}


# ---------------------------------------------------- witness records
# Keys are exact (section, printed line) ids: each entry suppresses exactly
# its own stylesheet cross-check finding in the years listed, and an entry
# the stylesheet in fact agrees with is stale
# (tenforty.verification.crosscheck.discrepancies_in_force). Only the 8z type
# write-in, which no stylesheet line names, draws a raw finding.
WITNESS_DISCREPANCIES = {
    _8Z_TYPE: (YEARS, "the stylesheet's line 8z lists only the amount "
               "element (OtherIncomeTotalAmt); the paper's 'List type and "
               "amount' write-in has no stylesheet line. Declared as its own "
               "line for the computation's type text"),
}
# Witness divergences that suppress no finding: documented so the
# paper-over-stylesheet choices and the witnesses' gaps are explained.
WITNESS_NOTES = {
    (P2, "24b"): ((2022,), "the 2022 stylesheet still cross-references line "
                  "8k (the 2021 numbering); the 2022 paper, after the 8-block "
                  "re-lettering, says line 8l. Description from the paper"),
    (P2, "24c"): ((2022,), "the 2022 stylesheet cross-references line 8l; "
                  "the 2022 paper says line 8m. Description from the paper"),
    (P2, "26"): ((2024, 2025), "the stylesheet reads 'on Form 1040, 1040-SR, "
                 "or Form 1040-NR, line 10'; the paper 'on Form 1040, 1040-SR, "
                 "or 1040-NR, line 10'. Description from the paper"),
    (P1, "8t"): ((2022, 2023, 2024, 2025), "the PAPER misspells "
                 "'nonqualifed'; the stylesheet spells 'nonqualified'. The "
                 "paper's text is kept literal (ruled)"),
    (P2, "19b"): ((2021, 2022, 2023), "absent from the inventory (inline "
                  "entry, no box label); the stylesheet lists it. Declared "
                  "with an inventory exemption"),
    (P2, "19c"): ((2021, 2022, 2023), "as 19b"),
    ("", "1099-K"): ((2024, 2025), "the paper prints an unlabeled Form "
                     "1099-K entry above Part I; neither witness lists it; not "
                     "declared (the line universe is labeled lines)"),
}
