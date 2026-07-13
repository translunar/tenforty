import unittest

from tenforty.forms import f100s_k1
from tenforty.models import (
    Address, K1Allocation, K1AllocationEntity, K1AllocationShareholder,
)


def _addr():
    return Address(street="1 Example Ave", city="Example City",
                   state="EX", zip_code="00000")


def _alloc(pct, box1):
    return K1Allocation(
        entity=K1AllocationEntity(name="Example S-Corp Inc.",
                                  ein="00-0000000", address=_addr()),
        shareholder=K1AllocationShareholder(name="Shareholder",
                                            ssn_or_ein="000-00-0000",
                                            address=_addr()),
        ownership_percentage=pct,
        box_1_ordinary_business_income=box1,
    )


def _run(federal_allocs, ca_net):
    upstream = {
        "f1120s": {"f1120s_sch_k1_allocations": federal_allocs},
        "f100s": {"f100s_net_income_for_tax": ca_net},
    }
    return f100s_k1.compute(None, upstream)["f100s_k1_allocations"]


class F100SK1AllocationTests(unittest.TestCase):
    def test_single_shareholder_gets_full_columns(self):
        allocs = _run([_alloc(100.0, 100000.0)], ca_net=95000.0)
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs[0]["shareholder_index"], 0)
        self.assertEqual(allocs[0]["ownership_fraction"], 1.0)
        self.assertEqual(allocs[0]["federal_ordinary_income"], 100000.0)
        self.assertEqual(allocs[0]["ca_ordinary_income"], 95000.0)

    def test_two_shareholders_foot_to_totals(self):
        federal = [_alloc(60.0, 60000.0), _alloc(40.0, 40000.0)]
        ca_net = 100000.0
        allocs = _run(federal, ca_net)
        self.assertEqual(len(allocs), 2)
        # federal column mirrors the federal K-1 box 1 shares exactly
        self.assertEqual([a["federal_ordinary_income"] for a in allocs],
                         [60000.0, 40000.0])
        # CA column foots to the 100S net income (same plain pro-rata convention)
        self.assertAlmostEqual(
            sum(a["ca_ordinary_income"] for a in allocs), ca_net)
        self.assertAlmostEqual(allocs[0]["ca_ordinary_income"], ca_net * 0.6)
        self.assertAlmostEqual(allocs[1]["ca_ordinary_income"], ca_net * 0.4)
        self.assertEqual([a["shareholder_index"] for a in allocs], [0, 1])
