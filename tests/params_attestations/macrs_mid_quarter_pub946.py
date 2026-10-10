"""MACRS mid-quarter percentage tables transcribed from IRS Publication 946
(2025 revision, p946.pdf, 113 pages), Appendix A.  Transcription copy B.
  Table A-2 (placed in service in first quarter):  PDF page 71
  Table A-3 (placed in service in second quarter): PDF page 72
  Table A-4 (placed in service in third quarter):  PDF page 72
  Table A-5 (placed in service in fourth quarter): PDF page 73
3-, 5-, 7-, 10-, 15-, 20-year property, mid-quarter convention.
Values are decimals of the printed percentages (58.33% -> 0.5833), transcribed
not computed. Transcribed 2026-10-10; verified against rendered page images.
Row shape: (recovery year, 3yr, 5yr, 7yr, 10yr, 15yr, 20yr); None is a cell
the table prints blank.
"""

A2_ROWS = (
    (1, 0.5833, 0.35, 0.25, 0.175, 0.0875, 0.06563),
    (2, 0.2778, 0.26, 0.2143, 0.165, 0.0913, 0.070),
    (3, 0.1235, 0.156, 0.1531, 0.132, 0.0821, 0.06482),
    (4, 0.0154, 0.1101, 0.1093, 0.1056, 0.0739, 0.05996),
    (5, None, 0.1101, 0.0875, 0.0845, 0.0665, 0.05546),
    (6, None, 0.0138, 0.0874, 0.0676, 0.0599, 0.0513),
    (7, None, None, 0.0875, 0.0655, 0.059, 0.04746),
    (8, None, None, 0.0109, 0.0655, 0.0591, 0.04459),
    (9, None, None, None, 0.0656, 0.059, 0.04459),
    (10, None, None, None, 0.0655, 0.0591, 0.04459),
    (11, None, None, None, 0.0082, 0.059, 0.04459),
    (12, None, None, None, None, 0.0591, 0.0446),
    (13, None, None, None, None, 0.059, 0.04459),
    (14, None, None, None, None, 0.0591, 0.0446),
    (15, None, None, None, None, 0.059, 0.04459),
    (16, None, None, None, None, 0.0074, 0.0446),
    (17, None, None, None, None, None, 0.04459),
    (18, None, None, None, None, None, 0.0446),
    (19, None, None, None, None, None, 0.04459),
    (20, None, None, None, None, None, 0.0446),
    (21, None, None, None, None, None, 0.00565),
)

A3_ROWS = (
    (1, 0.4167, 0.25, 0.1785, 0.125, 0.0625, 0.04688),
    (2, 0.3889, 0.30, 0.2347, 0.175, 0.0938, 0.07148),
    (3, 0.1414, 0.18, 0.1676, 0.14, 0.0844, 0.06612),
    (4, 0.053, 0.1137, 0.1197, 0.112, 0.0759, 0.06116),
    (5, None, 0.1137, 0.0887, 0.0896, 0.0683, 0.05658),
    (6, None, 0.0426, 0.0887, 0.0717, 0.0615, 0.05233),
    (7, None, None, 0.0887, 0.0655, 0.0591, 0.04841),
    (8, None, None, 0.0334, 0.0655, 0.059, 0.04478),
    (9, None, None, None, 0.0656, 0.0591, 0.04463),
    (10, None, None, None, 0.0655, 0.059, 0.04463),
    (11, None, None, None, 0.0246, 0.0591, 0.04463),
    (12, None, None, None, None, 0.059, 0.04463),
    (13, None, None, None, None, 0.0591, 0.04463),
    (14, None, None, None, None, 0.059, 0.04463),
    (15, None, None, None, None, 0.0591, 0.04462),
    (16, None, None, None, None, 0.0221, 0.04463),
    (17, None, None, None, None, None, 0.04462),
    (18, None, None, None, None, None, 0.04463),
    (19, None, None, None, None, None, 0.04462),
    (20, None, None, None, None, None, 0.04463),
    (21, None, None, None, None, None, 0.01673),
)

A4_ROWS = (
    (1, 0.25, 0.15, 0.1071, 0.075, 0.0375, 0.02813),
    (2, 0.50, 0.34, 0.2551, 0.185, 0.0963, 0.07289),
    (3, 0.1667, 0.204, 0.1822, 0.148, 0.0866, 0.06742),
    (4, 0.0833, 0.1224, 0.1302, 0.1184, 0.078, 0.06237),
    (5, None, 0.113, 0.093, 0.0947, 0.0702, 0.05769),
    (6, None, 0.0706, 0.0885, 0.0758, 0.0631, 0.05336),
    (7, None, None, 0.0886, 0.0655, 0.059, 0.04936),
    (8, None, None, 0.0553, 0.0655, 0.059, 0.04566),
    (9, None, None, None, 0.0656, 0.0591, 0.0446),
    (10, None, None, None, 0.0655, 0.059, 0.0446),
    (11, None, None, None, 0.041, 0.0591, 0.0446),
    (12, None, None, None, None, 0.059, 0.0446),
    (13, None, None, None, None, 0.0591, 0.04461),
    (14, None, None, None, None, 0.059, 0.0446),
    (15, None, None, None, None, 0.0591, 0.04461),
    (16, None, None, None, None, 0.0369, 0.0446),
    (17, None, None, None, None, None, 0.04461),
    (18, None, None, None, None, None, 0.0446),
    (19, None, None, None, None, None, 0.04461),
    (20, None, None, None, None, None, 0.0446),
    (21, None, None, None, None, None, 0.02788),
)

A5_ROWS = (
    (1, 0.0833, 0.05, 0.0357, 0.025, 0.0125, 0.00938),
    (2, 0.6111, 0.38, 0.2755, 0.195, 0.0988, 0.0743),
    (3, 0.2037, 0.228, 0.1968, 0.156, 0.0889, 0.06872),
    (4, 0.1019, 0.1368, 0.1406, 0.1248, 0.08, 0.06357),
    (5, None, 0.1094, 0.1004, 0.0998, 0.072, 0.0588),
    (6, None, 0.0958, 0.0873, 0.0799, 0.0648, 0.05439),
    (7, None, None, 0.0873, 0.0655, 0.059, 0.05031),
    (8, None, None, 0.0764, 0.0655, 0.059, 0.04654),
    (9, None, None, None, 0.0656, 0.059, 0.04458),  # FLAG: 15-yr 5.90 printed for years 7, 8 and 9 (A-2..A-4 alternate 5.90/5.91); transcribed as printed
    (10, None, None, None, 0.0655, 0.0591, 0.04458),
    (11, None, None, None, 0.0574, 0.059, 0.04458),
    (12, None, None, None, None, 0.0591, 0.04458),
    (13, None, None, None, None, 0.059, 0.04458),
    (14, None, None, None, None, 0.0591, 0.04458),
    (15, None, None, None, None, 0.059, 0.04458),
    (16, None, None, None, None, 0.0517, 0.04458),
    (17, None, None, None, None, None, 0.04458),
    (18, None, None, None, None, None, 0.04459),
    (19, None, None, None, None, None, 0.04458),
    (20, None, None, None, None, None, 0.04459),
    (21, None, None, None, None, None, 0.03901),
)

SOURCES: tuple[str, ...] = (
    "IRS Publication 946 (2025 revision), How To Depreciate Property, "
    "Appendix A, Table A-2 (p. 71), Table A-3 (p. 72), Table A-4 (p. 72), "
    "Table A-5 (p. 73). Transcription copy B, 2026-10-10.",
)
