"""Verification test ensuring that the owner's existing register is preserved.

Checks required by track-a/README.md and fixtures/README.md:
1. Verify exact match against fixtures/expected-records.json (9 invoices, 5 payments, 7 open, 3698.19 INR).
2. Verify unmatched payment KEEP-U1 remains unmatched (invoice_id is null).
3. Import a valid new invoice and a new payment on top of the fixture.
4. Close and re-open (simulating server restart) and verify all original and new records persist.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting, importing

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / 'fixtures' / 'existing-register.sqlite3'
EXPECTED_JSON = ROOT / 'fixtures' / 'expected-records.json'


class FixturePreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'preserved.sqlite3'
        shutil.copy2(FIXTURE_PATH, self.db_path)
        self.db = storage.connect(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_fixture_matches_expected_records(self):
        """Verify the restored fixture exactly matches fixtures/expected-records.json."""
        with open(EXPECTED_JSON, 'r', encoding='utf-8') as f:
            expected = json.load(f)

        overview = reporting.overview(self.db)
        summary = overview['summary']

        self.assertEqual(summary['invoice_count'], expected['summary']['invoice_count'])
        self.assertEqual(summary['open_count'], expected['summary']['open_count'])
        self.assertEqual(f"{summary['outstanding']:.2f}", expected['summary']['outstanding'])

        # Verify all invoices
        invoices = reporting.invoices(self.db, status='all')
        self.assertEqual(len(invoices), len(expected['invoices']))
        for exp_inv in expected['invoices']:
            actual = next((i for i in invoices if i['id'] == exp_inv['id']), None)
            self.assertIsNotNone(actual, f"Missing invoice id {exp_inv['id']}")
            self.assertEqual(actual['customer_id'], exp_inv['customer_id'])
            self.assertEqual(actual['invoice_number'], exp_inv['invoice_number'])
            self.assertEqual(f"{actual['amount']:.2f}", exp_inv['amount'])
            self.assertEqual(actual['due_date'], exp_inv['due_date'])

        # Verify payments and allocations
        raw_payments = [dict(r) for r in self.db.execute('SELECT * FROM payments ORDER BY payment_id').fetchall()]
        self.assertEqual(len(raw_payments), len(expected['payments']))
        for exp_pay in expected['payments']:
            act_pay = next((p for p in raw_payments if p['payment_id'] == exp_pay['payment_id']), None)
            self.assertIsNotNone(act_pay, f"Missing payment {exp_pay['payment_id']}")
            self.assertEqual(act_pay['customer_id'], exp_pay['customer_id'])
            self.assertEqual(act_pay['invoice_number'], exp_pay['invoice_number'])
            self.assertEqual(f"{act_pay['amount']:.2f}", exp_pay['amount'])
            self.assertEqual(act_pay['invoice_id'], exp_pay['invoice_id'])

        # Verify unmatched payment KEEP-U1
        unmatched_ids = [p['payment_id'] for p in overview['unmatched_payments']]
        self.assertIn('KEEP-U1', unmatched_ids)

    def test_import_and_persistence_across_restart(self):
        """Verify importing new valid records into the existing register and persisting across restart."""
        # Import new invoice for HARBOR
        csv_inv = "customer_id,invoice_number,amount,due_date\nHARBOR,NEW-INV-999,500.00,2026-09-20\n"
        res_inv = importing.import_csv(self.db, csv_inv, 'invoices')
        self.assertEqual(res_inv['imported'], 1)

        # Import payment for the new invoice
        csv_pay = "payment_id,customer_id,invoice_number,amount\nNEW-PAY-999,HARBOR,NEW-INV-999,200.00\n"
        res_pay = importing.import_csv(self.db, csv_pay, 'payments')
        self.assertEqual(res_pay['imported'], 1)

        # Simulate restart: close and reconnect
        self.db.close()
        self.db = storage.connect(self.db_path)

        # Verify count is now 10 invoices (9 original + 1 new)
        overview = reporting.overview(self.db)
        self.assertEqual(overview['summary']['invoice_count'], 10)

        # Verify new invoice balance
        new_inv = next(i for i in reporting.invoices(self.db) if i['invoice_number'] == 'NEW-INV-999')
        self.assertEqual(new_inv['amount'], 500.00)
        self.assertEqual(new_inv['paid'], 200.00)
        self.assertEqual(new_inv['balance'], 300.00)
        self.assertEqual(new_inv['status'], 'open')

        # Verify original fixture invoices are still present and unaltered
        inv_keep = next(i for i in reporting.invoices(self.db) if i['invoice_number'] == 'KEEP-700' and i['customer_id'] == 'HARBOR')
        self.assertEqual(inv_keep['paid'], 56.78)
        self.assertEqual(inv_keep['balance'], 400.00)


if __name__ == '__main__':
    unittest.main()
