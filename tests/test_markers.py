"""Regression test: ensure the 'oracle' pytest marker is registered."""

import unittest

import pytest


class OracleMarkerTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_oracle_marker_registered(self):
        # If the marker were unregistered, pytest would emit
        # PytestUnknownMarkWarning at collection time. Running the suite
        # with -W error::pytest.PytestUnknownMarkWarning turns that into a
        # hard failure; this trivial body is the sentinel test for that.
        self.assertTrue(True)
