"""Regression tests reproducing seeded defects and verifying business rules.

These tests establish baseline failures on the unpatched starter codebase,
proving the presence of the six seeded defects before repairs are applied.
"""
import io
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting, importing


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_reproduce_status_filter_open_returns_open_invoices(self):
        """Defect 1 Reproduction: Filtering by status='open' must return only open invoices.

        Before fix: In reporting.py line 22, {'open': 'paid'} returned paid invoices.
        """
        open_invoices = reporting.invoices(self.db, status='open')
        # Seed has 5 open invoices (INV-100, INV-200, INV-300, INV-201, INV-301) and 1 paid (INV-101)
        self.assertEqual(len(open_invoices), 5)
        for inv in open_invoices:
            self.assertEqual(inv['status'], 'open')
            self.assertGreater(inv['balance'], 0)

    def test_reproduce_payment_matching_must_not_match_by_amount_alone(self):
        """Defect 2 Reproduction: Payments must only attach if both customer_id and invoice_number match.

        Before fix: In matching.py, any invoice with matching amount was incorrectly attached.
        """
        # NORTH has INV-301 with amount 100.00.
        # MAPLE makes a payment of 100.00 for non-existent invoice NON-EXISTENT.
        csv_data = "payment_id,customer_id,invoice_number,amount\nPAY-WRONG,MAPLE,NON-EXISTENT,100.00\n"
        result = importing.import_csv(self.db, csv_data, 'payments')
        self.assertEqual(result['imported'], 1)

        # The payment should NOT be attached to NORTH's INV-301.
        north_inv = next(r for r in reporting.invoices(self.db) if r['customer_id'] == 'NORTH' and r['invoice_number'] == 'INV-301')
        self.assertEqual(north_inv['paid'], 0.0, "Payment should not be attached to NORTH's invoice")

        # The payment should appear in unmatched_payments
        overview = reporting.overview(self.db)
        unmatched_ids = [p['payment_id'] for p in overview['unmatched_payments']]
        self.assertIn('PAY-WRONG', unmatched_ids)

    def test_reproduce_duplicate_invoice_import_idempotency(self):
        """Defect 3 Reproduction: Re-importing identical invoice must be skipped without changing totals.

        Before fix: storage.py insert_invoice inserted duplicate rows.
        """
        # Re-import HARBOR / INV-100 (which exists in seed: amount 1250.00, due 2026-09-01)
        csv_identical = "customer_id,invoice_number,amount,due_date\nHARBOR,INV-100,1250.00,2026-09-01\n"
        res = importing.import_csv(self.db, csv_identical, 'invoices')
        self.assertEqual(res['skipped'], 1, "Identical re-imported invoice should be skipped")
        self.assertEqual(res['imported'], 0)

        # Overview count and outstanding should remain unchanged (6 invoices, 3209.99 outstanding)
        summary = reporting.overview(self.db)['summary']
        self.assertEqual(summary['invoice_count'], 6)
        self.assertEqual(summary['outstanding'], 3209.99)

        # Re-importing with different amount must be rejected
        csv_conflict = "customer_id,invoice_number,amount,due_date\nHARBOR,INV-100,999.00,2026-09-01\n"
        res2 = importing.import_csv(self.db, csv_conflict, 'invoices')
        self.assertEqual(res2['rejected'], 1, "Conflicting invoice identity should be rejected")
        self.assertEqual(res2['imported'], 0)

    def test_reproduce_partial_csv_rejection_processes_valid_rows(self):
        """Defect 4 Reproduction: An invalid row must not abort valid rows in the same CSV.

        Before fix: importing.py validated all rows in a list comprehension before processing,
        raising an uncaught exception on the invalid row and failing the entire import.
        """
        csv_mixed = (
            "customer_id,invoice_number,amount,due_date\n"
            "HARBOR,INV-VALID-1,50.00,2026-09-15\n"
            "NORTH,INV-INVALID,invalid-amount,2026-09-15\n"
            "MAPLE,INV-VALID-2,75.00,2026-09-16\n"
        )
        res = importing.import_csv(self.db, csv_mixed, 'invoices')
        self.assertEqual(res['imported'], 2)
        self.assertEqual(res['rejected'], 1)
        self.assertEqual(len(res['errors']), 1)
        self.assertEqual(res['errors'][0]['line'], 3)

        # Check valid invoices were actually stored
        inv_numbers = [r['invoice_number'] for r in reporting.invoices(self.db)]
        self.assertIn('INV-VALID-1', inv_numbers)
        self.assertIn('INV-VALID-2', inv_numbers)

    def test_reproduce_export_csv_preserves_cents_precision(self):
        """Defect 5 Reproduction: CSV export must not truncate cents (e.g. 19.99 to 19.98).

        Before fix: reporting.py export_csv did int(val * 100) / 100 which truncated floating points.
        """
        csv_out = reporting.export_csv(self.db)
        # Look for NORTH,INV-300: amount is 19.99, paid is 10.00, balance is 9.99
        lines = csv_out.strip().splitlines()
        north_line = next(line for line in lines if 'INV-300' in line)
        parts = north_line.split(',')
        # customer_id,invoice_number,amount,paid,balance,status
        self.assertEqual(parts[2], '19.99', "Amount should be 19.99, not 19.98")
        self.assertEqual(parts[3], '10.00', "Paid should be 10.00")
        self.assertEqual(parts[4], '9.99', "Balance should be 9.99, not 9.98")

    def test_custom_case_overpayment_handling(self):
        """Custom Input Case: Overpayment handling per BUSINESS_RULES.md.

        Rule: Overpayments are permitted: show negative balance, mark invoice 'paid',
        and do not deduct or reduce other invoices' outstanding amount.
        """
        # INV-301 for NORTH is 100.00. Apply a payment of 150.00.
        csv_payment = "payment_id,customer_id,invoice_number,amount\nPAY-OVER,NORTH,INV-301,150.00\n"
        res = importing.import_csv(self.db, csv_payment, 'payments')
        self.assertEqual(res['imported'], 1)

        inv = next(r for r in reporting.invoices(self.db) if r['customer_id'] == 'NORTH' and r['invoice_number'] == 'INV-301')
        self.assertEqual(inv['paid'], 150.00)
        self.assertEqual(inv['balance'], -50.00)
        self.assertEqual(inv['status'], 'paid')

        # Total outstanding should only sum positive balances (not subtract -50 from other invoices)
        # Original outstanding was 3209.99. INV-301 was 100.00.
        # Now INV-301 is paid, so outstanding should be 3209.99 - 100.00 = 3109.99
        summary = reporting.overview(self.db)['summary']
        self.assertEqual(summary['outstanding'], 3109.99)


if __name__ == '__main__':
    unittest.main()
