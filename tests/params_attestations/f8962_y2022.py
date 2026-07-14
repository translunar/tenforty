"""Air-gapped attestation of Form 8962 (Premium Tax Credit) params, tax
year 2022.

Two independent, mutually-blind transcribers each read ONLY the official
2022 IRS Form 8962 instructions (irs.gov) — no tenforty code, no other
year's data, no shared examples — and transcribed the FPL guideline, the
applicable-figure table (251 rows), the repayment-limitation table, and the
unemployment-compensation special rule. They agreed on every cell at zero
tolerance.
"""

SOURCES: tuple[str, ...] = (
    "2022 Instructions for Form 8962 (Premium Tax Credit) "
    "(https://www.irs.gov/pub/irs-prior/i8962--2022.pdf), Table 1-1/1-2 "
    "(federal poverty line, household size 1, 48 contiguous states + DC) "
    "and Table 2 (applicable figure).",
    "2022 Instructions for Form 8962 (Premium Tax Credit) "
    "(https://www.irs.gov/pub/irs-prior/i8962--2022.pdf), Line 28 "
    "instructions (repayment limitation, single filing status).",
    "https://www.irs.gov/pub/irs-prior/i8962--2022.pdf, Worksheet 2 "
    "(line 5 400%-FPL boundary determination).",
)

ATTESTED: dict[str, object] = {
    "year": 2022,
    # Table 1-1: 2022 Form 8962 uses the FPL guideline published in 2021
    # for a household of 1 in the 48 contiguous states + DC.
    "fpl_single_48": 12880,
    # ARPA-extended table domain, second year: 0.00 floor at 150% FPL
    # through the 0.085 ceiling at 400% FPL (no 400% subsidy cliff in 2022).
    "applicable_figure_floor_pct": 150,
    "applicable_figure_ceiling_pct": 400,
    # The unemployment-compensation special rule was a 2021-only ARPA
    # provision; it does not appear in the 2022 instructions.
    "unemployment_rule": False,
    # Worksheet 2, steps 3-4: "Multiply the amount on line 2 by 4.0. ...
    # Is the amount on line 1 more than [line 3]? ... more than 400% of
    # the federal poverty line. Enter 401 here and on line 5 of Form
    # 8962." — strict: exactly 400% leaves line 5 at 400.
    "line5_400_boundary_inclusive": False,
    # Line 28 repayment limitation table, single filing status:
    # <200% FPL -> $325; <300% -> $825; <400% -> $1,400; >=400% -> no limit.
    "repayment_caps_single": ((200, 325), (300, 825), (400, 1400)),
    # Table 2 (applicable figure), full published domain 150%-400% FPL,
    # transcribed verbatim, all 251 rows.
    "applicable_figures": {
        150: 0.0, 151: 0.0004, 152: 0.0008, 153: 0.0012, 154: 0.0016, 155: 0.002,
        156: 0.0024, 157: 0.0028, 158: 0.0032, 159: 0.0036, 160: 0.004, 161: 0.0044,
        162: 0.0048, 163: 0.0052, 164: 0.0056, 165: 0.006, 166: 0.0064, 167: 0.0068,
        168: 0.0072, 169: 0.0076, 170: 0.008, 171: 0.0084, 172: 0.0088, 173: 0.0092,
        174: 0.0096, 175: 0.01, 176: 0.0104, 177: 0.0108, 178: 0.0112, 179: 0.0116,
        180: 0.012, 181: 0.0124, 182: 0.0128, 183: 0.0132, 184: 0.0136, 185: 0.014,
        186: 0.0144, 187: 0.0148, 188: 0.0152, 189: 0.0156, 190: 0.016, 191: 0.0164,
        192: 0.0168, 193: 0.0172, 194: 0.0176, 195: 0.018, 196: 0.0184, 197: 0.0188,
        198: 0.0192, 199: 0.0196, 200: 0.02, 201: 0.0204, 202: 0.0208, 203: 0.0212,
        204: 0.0216, 205: 0.022, 206: 0.0224, 207: 0.0228, 208: 0.0232, 209: 0.0236,
        210: 0.024, 211: 0.0244, 212: 0.0248, 213: 0.0252, 214: 0.0256, 215: 0.026,
        216: 0.0264, 217: 0.0268, 218: 0.0272, 219: 0.0276, 220: 0.028, 221: 0.0284,
        222: 0.0288, 223: 0.0292, 224: 0.0296, 225: 0.03, 226: 0.0304, 227: 0.0308,
        228: 0.0312, 229: 0.0316, 230: 0.032, 231: 0.0324, 232: 0.0328, 233: 0.0332,
        234: 0.0336, 235: 0.034, 236: 0.0344, 237: 0.0348, 238: 0.0352, 239: 0.0356,
        240: 0.036, 241: 0.0364, 242: 0.0368, 243: 0.0372, 244: 0.0376, 245: 0.038,
        246: 0.0384, 247: 0.0388, 248: 0.0392, 249: 0.0396, 250: 0.04, 251: 0.0404,
        252: 0.0408, 253: 0.0412, 254: 0.0416, 255: 0.042, 256: 0.0424, 257: 0.0428,
        258: 0.0432, 259: 0.0436, 260: 0.044, 261: 0.0444, 262: 0.0448, 263: 0.0452,
        264: 0.0456, 265: 0.046, 266: 0.0464, 267: 0.0468, 268: 0.0472, 269: 0.0476,
        270: 0.048, 271: 0.0484, 272: 0.0488, 273: 0.0492, 274: 0.0496, 275: 0.05,
        276: 0.0504, 277: 0.0508, 278: 0.0512, 279: 0.0516, 280: 0.052, 281: 0.0524,
        282: 0.0528, 283: 0.0532, 284: 0.0536, 285: 0.054, 286: 0.0544, 287: 0.0548,
        288: 0.0552, 289: 0.0556, 290: 0.056, 291: 0.0564, 292: 0.0568, 293: 0.0572,
        294: 0.0576, 295: 0.058, 296: 0.0584, 297: 0.0588, 298: 0.0592, 299: 0.0596,
        300: 0.06, 301: 0.0603, 302: 0.0605, 303: 0.0608, 304: 0.061, 305: 0.0613,
        306: 0.0615, 307: 0.0618, 308: 0.062, 309: 0.0623, 310: 0.0625, 311: 0.0628,
        312: 0.063, 313: 0.0633, 314: 0.0635, 315: 0.0638, 316: 0.064, 317: 0.0643,
        318: 0.0645, 319: 0.0648, 320: 0.065, 321: 0.0653, 322: 0.0655, 323: 0.0658,
        324: 0.066, 325: 0.0663, 326: 0.0665, 327: 0.0668, 328: 0.067, 329: 0.0673,
        330: 0.0675, 331: 0.0678, 332: 0.068, 333: 0.0683, 334: 0.0685, 335: 0.0688,
        336: 0.069, 337: 0.0693, 338: 0.0695, 339: 0.0698, 340: 0.07, 341: 0.0703,
        342: 0.0705, 343: 0.0708, 344: 0.071, 345: 0.0713, 346: 0.0715, 347: 0.0718,
        348: 0.072, 349: 0.0723, 350: 0.0725, 351: 0.0728, 352: 0.073, 353: 0.0733,
        354: 0.0735, 355: 0.0738, 356: 0.074, 357: 0.0743, 358: 0.0745, 359: 0.0748,
        360: 0.075, 361: 0.0753, 362: 0.0755, 363: 0.0758, 364: 0.076, 365: 0.0763,
        366: 0.0765, 367: 0.0768, 368: 0.077, 369: 0.0773, 370: 0.0775, 371: 0.0778,
        372: 0.078, 373: 0.0783, 374: 0.0785, 375: 0.0788, 376: 0.079, 377: 0.0793,
        378: 0.0795, 379: 0.0798, 380: 0.08, 381: 0.0803, 382: 0.0805, 383: 0.0808,
        384: 0.081, 385: 0.0813, 386: 0.0815, 387: 0.0818, 388: 0.082, 389: 0.0823,
        390: 0.0825, 391: 0.0828, 392: 0.083, 393: 0.0833, 394: 0.0835, 395: 0.0838,
        396: 0.084, 397: 0.0843, 398: 0.0845, 399: 0.0848, 400: 0.085,
    },
}
