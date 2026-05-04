import io
import unittest

from tenforty.__main__ import main


class FodsRedirectTests(unittest.TestCase):
    def test_fods_subcommand_prints_redirect_and_exits_zero(self):
        import sys
        old_argv, sys.argv = sys.argv, ["tenforty", "fods"]
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            rc = main()
        finally:
            captured = sys.stderr.getvalue()
            sys.argv = old_argv
            sys.stderr = old_stderr
        self.assertEqual(rc, 0)
        self.assertIn("tenforty ca", captured)
        self.assertIn(".fods", captured)
