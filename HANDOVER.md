# Handover

- Name: Soham Gudewar
- Email used for this application: sohamgudewar10@gmail.com
- Chosen track: Track A (Repair the register)
- Why this track: I enjoy core systems engineering, test-driven debugging, and building dependable data integrity guarantees for financial and operational registers.
- Approximate total time, including setup and handover: ~3 hours 15 minutes

## Run and verify

Prerequisites: Python 3.10+ and a modern web browser. Zero external dependencies required (uses standard library).

```bash
# 1. Run all unit and regression tests (15 passing tests):
python -m unittest discover -s tests -v

# 2. Restore owner's existing register and start local server:
python restore_fixture.py --replace
python app.py
```
Open `http://127.0.0.1:8787` in your browser. To reset to the original 6-invoice demo, run `python app.py reset-demo`.

## What I delivered

I investigated and repaired all six seeded application defects across import, matching, reporting, and browser feedback, preserving all existing records:

1. **Payment Matching ([`ledger/matching.py`](ledger/matching.py))**: Removed heuristic amount-only matching. Payments now strictly attach only to invoices matching both `customer_id` and `invoice_number`. Unmatched valid payments remain safely in `unmatched_payments`.
2. **Status Filter ([`ledger/reporting.py`](ledger/reporting.py))**: Fixed dictionary mapping so `status=open` returns open invoices rather than paid ones.
3. **Import Idempotency ([`ledger/storage.py`](ledger/storage.py))**: Implemented duplicate checking in `insert_invoice`: re-importing identical invoices is skipped; re-importing conflicting details raises a rejection.
4. **Per-Row Error Handling ([`ledger/importing.py`](ledger/importing.py))**: Switched from list-comprehension validation to iterative row processing. Valid rows are imported; invalid rows are logged with 1-based CSV line numbers and rejection reasons.
5. **Cents Precision in Export ([`ledger/reporting.py`](ledger/reporting.py))**: Replaced floating-point truncation (`int(x * 100) / 100`) with rounded two-decimal formatting, preserving exact cents (e.g. `19.99` instead of `19.98`).
6. **Browser Feedback ([`web/app.js`](web/app.js))**: UI now shows exact counts (`imported`, `skipped`, `rejected`), lists line errors on partial rejection, and displays helpful failure messages on HTTP 400.

**Improvement beyond required repairs**:
- Added **Unmatched Payments metric** (count and total INR) to the overview stats (`reporting.py`, `index.html`, `app.js`).
- Added an **Overdue indicator badge** on open invoices whose due date has passed.
- Verified via [`tests/test_improvement.py`](tests/test_improvement.py).

## Evidence and limits

- **Failing-Before vs. Passing-After Reproduction**: Ran `python -m unittest tests/test_regressions.py -v`. On the unpatched code, 4 tests failed and 1 errored (confirming status inversion, amount-only matching, import duplicates, whole-batch aborts, and export cent truncation). After repairs, all 6 regression tests pass cleanly.
- **Changed-Input Case**: Designed an overpayment test case (`test_custom_case_overpayment_handling` in [`tests/test_regressions.py`](tests/test_regressions.py)). Confirmed that overpaying an invoice creates a negative balance, marks it `paid`, and does not deduct from other invoices' outstanding totals.
- **Fixture Preservation Check**: Restored fixture via [`tests/test_fixture_preservation.py`](tests/test_fixture_preservation.py). Verified that all 9 invoices, 5 payments, 7 open invoices, and starting total of INR 3,698.19 from `fixtures/expected-records.json` remain intact. Added new valid invoice and payment records, simulated an app restart, and verified persistence.
- **Limits & Real-World Steps**: Multi-user concurrency locks/transactions should be added before high-volume writes; pagination and database-level unique constraints should replace table scans for larger datasets.

## Tools and judgment

Used Antigravity IDE with Gemini 3.8 Flash (High):
1. *Defect Diagnosis*: Used AI to trace the disconnect between the overview and open invoice list to `reporting.py` line 22 (`{'open': 'paid'}`). Verified by inspecting the response of `/api/invoices?status=open`.
2. *Payment Matching Strategy*: Evaluated whether to auto-link by fuzzy amounts; rejected this approach per business rules in favor of strict `(customer_id, invoice_number)` linkage to prevent balance misallocation.
3. *Verification Rigor*: Directed AI to construct an automated fixture-preservation test suite comparing database state directly against `expected-records.json`, catching potential regressions during restarts.
