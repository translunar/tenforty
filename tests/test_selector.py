import unittest

from tenforty.selector import ChangedForm, changed_forms, dropped_forms


class ChangedFormsSelectorTests(unittest.TestCase):
    def test_value_change_selects_changed(self):
        filed = {"sch_a": {"f_1": 100, "f_2": 200}}
        corrected = {"sch_a": {"f_1": 150, "f_2": 200}}
        self.assertEqual(
            changed_forms(filed, corrected),
            [ChangedForm("sch_a", "changed")],
        )

    def test_new_form_selects_new(self):
        filed = {"sch_a": {"f_1": 100}}
        corrected = {"sch_a": {"f_1": 100}, "sch_b": {"f_1": 5}}
        self.assertEqual(
            changed_forms(filed, corrected),
            [ChangedForm("sch_b", "new")],
        )

    def test_untouched_form_not_selected(self):
        filed = {"sch_a": {"f_1": 100, "f_2": 200}}
        corrected = {"sch_a": {"f_1": 100, "f_2": 200}}
        self.assertEqual(changed_forms(filed, corrected), [])

    def test_filed_only_form_not_selected(self):
        filed = {"sch_a": {"f_1": 100}, "sch_b": {"f_1": 5}}
        corrected = {"sch_a": {"f_1": 100}}
        self.assertEqual(changed_forms(filed, corrected), [])

    def test_deterministic_order(self):
        filed = {}
        corrected = {
            "sch_c": {"f_1": 3},
            "sch_a": {"f_1": 1},
            "sch_b": {"f_1": 2},
        }
        self.assertEqual(
            changed_forms(filed, corrected),
            [
                ChangedForm("sch_a", "new"),
                ChangedForm("sch_b", "new"),
                ChangedForm("sch_c", "new"),
            ],
        )
    def test_filed_only_form_is_dropped_not_changed(self):
        filed = {"sch_a": {"f_1": 100}, "sch_b": {"f_1": 5}}
        corrected = {"sch_a": {"f_1": 100}}
        self.assertEqual(dropped_forms(filed, corrected), ["sch_b"])
        self.assertNotIn(
            "sch_b",
            [cf.form for cf in changed_forms(filed, corrected)],
        )

    def test_dropped_forms_deterministic_order(self):
        filed = {
            "sch_c": {"f_1": 3},
            "sch_a": {"f_1": 1},
            "sch_b": {"f_1": 2},
        }
        corrected = {"sch_a": {"f_1": 1}}
        self.assertEqual(dropped_forms(filed, corrected), ["sch_b", "sch_c"])


if __name__ == "__main__":
    unittest.main()
