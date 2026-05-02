"""Cross-check Schedule D native compute against the XLSX oracle.

Currently a skip-stub: the oracle flattener does not yet support 1099-B
(no ``_flatten_1099_b_oracle`` routing path), so there is no oracle-visible
path for 1099-B capital gain activity. When oracle-side 1099-B flattening is
added and ``_SUPPORTS_1099B`` opts in, this test should come alive and compare
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
            "Oracle flattener does not yet support 1099-B for the Sch D "
            "cross-check; deferred until `_SUPPORTS_1099B` opts in."
        )


if __name__ == "__main__":
    unittest.main()
