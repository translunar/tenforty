import unittest

from tenforty.models import (
    Address, EntityType, K1Allocation, K1AllocationEntity, K1AllocationShareholder,
)
from tenforty.orchestrator import _make_k1_from_1120s_allocation


def _address():
    return Address(street="1 Example Ave", city="Example City",
                   state="EX", zip_code="00000")


def _alloc(*, box_1=70_000.0, qbi=70_000.0, pct=100.0):
    return K1Allocation(
        entity=K1AllocationEntity(
            name="Example S-Corp Inc.", ein="00-0000000", address=_address()),
        shareholder=K1AllocationShareholder(
            name="Taxpayer A", ssn_or_ein="000-00-0000", address=_address()),
        ownership_percentage=pct,
        box_1_ordinary_business_income=box_1,
        box_17v_qbi=qbi,
    )


class BridgeCarriesQbiTests(unittest.TestCase):
    def test_qbi_crosses_the_bridge(self):
        k1 = _make_k1_from_1120s_allocation(_alloc(box_1=70_000.0, qbi=70_000.0))
        self.assertEqual(k1.qbi_amount, 70_000.0)

    def test_qbi_independent_of_ordinary_business_income(self):
        """An override makes QBI differ from box 1; the bridge must carry the
        QBI figure, not re-derive it from ordinary business income."""
        k1 = _make_k1_from_1120s_allocation(_alloc(box_1=70_000.0, qbi=80_000.0))
        self.assertEqual(k1.qbi_amount, 80_000.0)
        self.assertEqual(k1.ordinary_business_income, 70_000.0)

    def test_qbi_amount_is_a_float(self):
        """box_17v_qbi arrives as an int from irs_round; ScheduleK1.qbi_amount
        is typed float, so the bridge converts explicitly."""
        k1 = _make_k1_from_1120s_allocation(_alloc(qbi=70_000))
        self.assertIsInstance(k1.qbi_amount, float)

    def test_loss_qbi_crosses_intact(self):
        k1 = _make_k1_from_1120s_allocation(_alloc(box_1=-5_000.0, qbi=-5_000.0))
        self.assertEqual(k1.qbi_amount, -5_000.0)

    def test_existing_bridge_fields_still_carried(self):
        """Guard against the wire breaking what already worked."""
        k1 = _make_k1_from_1120s_allocation(_alloc())
        self.assertEqual(k1.entity_name, "Example S-Corp Inc.")
        self.assertEqual(k1.entity_ein, "00-0000000")
        self.assertEqual(k1.entity_type, EntityType.S_CORP)
        self.assertEqual(k1.ordinary_business_income, 70_000.0)
