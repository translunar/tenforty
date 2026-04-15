"""Cross-check Schedule D native compute against the XLSX oracle.

Currently a skip-stub: the oracle flattener explicitly rejects
``scenario.form1099_b`` (see ``tenforty/oracle/flattener.py::_reject_unhandled``),
so there is no oracle-visible path for 1099-B capital gain activity. When
1099-B flattening is added, this test should come alive and compare
``sch_d['sch_d_line_16_total']`` against
``irs_round(f1040['capital_gain_loss'])``.
"""

import unittest

import pytest

from tenforty.oracle import flattener


class SchDOracleTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_oracle_cross_check_pending_1099b_flattener(self):
        if getattr(flattener, "_SUPPORTS_1099B", False):
            self.fail(
                "Oracle flattener now claims 1099-B support; "
                "replace this stub with a real cross-check."
            )
        self.skipTest(
            "Oracle flattener rejects 1099-B; Sch D oracle cross-check "
            "deferred until 1099-B flattening lands."
        )


if __name__ == "__main__":
    unittest.main()
