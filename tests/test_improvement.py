"""Automated checks verifying the small improvement added beyond BUSINESS_RULES.md.

Improvement:
1. Addition of Unmatched Payments metric (unmatched_count and unmatched_total) in overview summary.
2. Addition of is_overdue flag to open invoices past due date.
"""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting, importing


class ImprovementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test_improvement.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_unmatched_payments_total_in_overview(self):
        """Verify summary includes unmatched_count and unmatched_total."""
        overview = reporting.overview(self.db)
        summary = overview['summary']
        self.assertIn('unmatched_count', summary)
        self.assertIn('unmatched_total', summary)
        # In the seed data, there are no unmatched payments initially
        self.assertEqual(summary['unmatched_count'], 0)
        self.assertEqual(summary['unmatched_total'], 0.0)

        # Import an unmatched payment
        csv_payment = "payment_id,customer_id,invoice_number,amount\nPAY-UNMATCHED,MAPLE,NON-EXISTENT,75.50\n"
        importing.import_csv(self.db, csv_payment, 'payments')

        updated = reporting.overview(self.db)
        up_summary = updated['summary']
        self.assertEqual(up_summary['unmatched_count'], 1)
        self.assertEqual(up_summary['unmatched_total'], 75.50)

    def test_invoice_overdue_flag(self):
        """Verify open invoices past due date have is_overdue=True and paid/future invoices have is_overdue=False."""
        invoices = reporting.invoices(self.db)
        # In seed data, INV-100 (due 2026-09-01) is open and overdue
        inv_100 = next(i for i in invoices if i['invoice_number'] == 'INV-100')
        self.assertEqual(inv_100['status'], 'open')
        self.assertTrue(inv_100['is_overdue'])

        # In seed data, INV-101 (paid) should NOT be overdue even if due date passed
        inv_101 = next(i for i in invoices if i['invoice_number'] == 'INV-101')
        self.assertEqual(inv_101['status'], 'paid')
        self.assertFalse(inv_101['is_overdue'])

        # Insert a future open invoice (due 2099-01-01)
        future_inv = "customer_id,invoice_number,amount,due_date\nHARBOR,INV-FUTURE,100.00,2099-01-01\n"
        importing.import_csv(self.db, future_inv, 'invoices')

        updated_invoices = reporting.invoices(self.db)
        inv_future = next(i for i in updated_invoices if i['invoice_number'] == 'INV-FUTURE')
        self.assertEqual(inv_future['status'], 'open')
        self.assertFalse(inv_future['is_overdue'])


if __name__ == '__main__':
    unittest.main()
