import unittest

from tenforty.params.f8962 import F8962Params, load


class F8962ParamsTests(unittest.TestCase):
    def test_loads_every_amendable_year(self):
        from tenforty import years as year_manifest
        for year in year_manifest.amendable_federal_years():
            with self.subTest(year=year):
                p = load(year)
                self.assertIsInstance(p, F8962Params)
                self.assertEqual(p.year, year)

    def test_unsupported_year_raises(self):
        with self.assertRaises(ValueError):
            load(1999)

    def test_unemployment_rule_only_2021(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertEqual(load(year).unemployment_rule, year == 2021)

    def test_line5_400_boundary_inclusive_only_2021(self):
        # 2021 Worksheet 2: "Is the result 400 or more? Yes -> enter 401"
        # (inclusive). 2022-2025 Worksheet 2: "more than 400% of the
        # federal poverty line -> enter 401" (strict).
        self.assertIs(load(2021).line5_400_boundary_inclusive, True)
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertIs(load(year).line5_400_boundary_inclusive, False)

    def test_applicable_figure_domain_edges_declared(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            p = load(year)
            with self.subTest(year=year):
                self.assertIn(p.applicable_figure_floor_pct, p.applicable_figures)
                self.assertIn(p.applicable_figure_ceiling_pct, p.applicable_figures)

    def test_repayment_caps_ascending_bands(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            bands = load(year).repayment_caps_single
            bounds = [b for b, _ in bands]
            with self.subTest(year=year):
                self.assertEqual(bounds, sorted(bounds))
