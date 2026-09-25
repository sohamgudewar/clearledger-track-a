# ClearLedger — Assessment Submission (Track A)

**Candidate:** Soham Gudewar ([sohamgudewar10@gmail.com](mailto:sohamgudewar10@gmail.com))  
**Track:** Track A — Product Engineering (Repair the Register)  
**Repository:** [https://github.com/sohamgudewar/clearledger-track-a](https://github.com/sohamgudewar/clearledger-track-a)  

---

## Quick Start (Run & Verify)

Requires **Python 3.10+** and a modern browser. **Zero external dependencies** (uses only Python's standard library).

```bash
# 1. Run all automated tests (15/15 passing):
python -m unittest discover -s tests -v

# 2. Restore the owner's existing historical register:
python restore_fixture.py --replace

# 3. Start the application:
python app.py
```

* Open **`http://127.0.0.1:8787`** in your browser.
* To reset to the original 6-invoice demo anytime: `python app.py reset-demo`.

---

## Engineering Approach

We took a rigorous, test-driven approach to investigate, repair, and verify ClearLedger:

1. **Investigation & Triage**: Traced the owner's reported issues and mapped them directly to [BUSINESS_RULES.md](BUSINESS_RULES.md).
2. **Reproduction Before Repair (TDD)**: Authored [`tests/test_regressions.py`](tests/test_regressions.py) to prove each seeded defect failed on the baseline codebase prior to making changes.
3. **Targeted Repairs**: Fixed all six seeded defects in the core ledger modules and frontend without breaking existing contracts or requiring unnecessary rewrites.
4. **Scope-Disciplined Improvement**: Implemented one high-value improvement addressing unapplied customer cash, backed by automated tests.
5. **Data Preservation & Restart Verification**: Restored the owner's register (`existing-register.sqlite3`) and proved 100% data preservation and persistence across app restarts via [`tests/test_fixture_preservation.py`](tests/test_fixture_preservation.py).

---

## What Was Repaired (The 6 Seeded Defects)

| Defect | Root Cause & Location | Fix Implemented |
|---|---|---|
| **1. Inverted Status Filter** | [`ledger/reporting.py`](ledger/reporting.py): `{'open': 'paid'}` dictionary typo returned paid invoices when filtering for open. | Fixed mapping so `/api/invoices?status=open` strictly returns open invoices (`balance > 0`). |
| **2. Heuristic Payment Matching** | [`ledger/matching.py`](ledger/matching.py): Auto-attached any invoice that shared the payment amount, even across different customers and invoice numbers. | Enforced strict matching on `(customer_id, invoice_number)`. Valid payments without a matching invoice remain safely in `unmatched_payments`. |
| **3. Duplicate Import Mutation** | [`ledger/storage.py`](ledger/storage.py): `insert_invoice()` unconditionally inserted rows without checking for existing identity. | Added idempotency check: re-importing identical invoices is skipped without altering totals; conflicting details raise a rejection. |
| **4. Whole-Batch CSV Abort** | [`ledger/importing.py`](ledger/importing.py): Evaluated all rows via list comprehension before processing; a single malformed row crashed the entire import. | Implemented per-row iteration and error handling. Valid rows are saved; invalid rows report CSV line numbers and reasons. |
| **5. Cents Truncation in Export** | [`ledger/reporting.py`](ledger/reporting.py): `int(val * 100) / 100` caused floating-point truncation (e.g. `19.99` exported as `19.98`). | Replaced with standard two-decimal rounding format (`f"{round(val, 2):.2f}"`), preserving exact cents. |
| **6. Blind UI Feedback** | [`web/app.js`](web/app.js): Hardcoded success message without inspecting HTTP status or response JSON. | Updated UI to show exact counts (`imported`, `skipped`, `rejected`), list line errors on partial rejection, and display clear HTTP 400 failure reasons. |

---

## The 1 Feature Improvement: Unmatched Payments Overview

* **The Problem:** In the starter app, unmatched payments (e.g. advance deposits or payments with unrecognized invoice numbers) were dumped into a plain bulleted list at the bottom of the page. The owner had no quick visibility into total unallocated cash without manually summing it up.
* **The Solution:** Added `unmatched_count` and `unmatched_total` to the `/api/overview` API and added a dedicated **4th summary card** to the top of the dashboard:
  > **Unmatched payments: `1 (₹33.33)`** (or `0 (₹0.00)` on demo)
* **The Value:** The owner now immediately sees both their total receivables (Outstanding) and total unapplied customer cash side-by-side upon opening the app.
* **Automated Check:** Verified in [`tests/test_improvement.py`](tests/test_improvement.py).

---

## Verification & Test Suite (15 / 15 Tests Passing)

All tests pass cleanly:
```bash
python -m unittest discover -s tests -v
```

* **`tests/test_smoke.py`** (5 tests): Starter smoke tests.
* **`tests/test_regressions.py`** (6 tests): Baseline defect reproductions (failing-before / passing-after) plus an overpayment edge-case check.
* **`tests/test_improvement.py`** (2 tests): Verifies dynamic calculation of unmatched payment metrics and invoice aging.
* **`tests/test_fixture_preservation.py`** (2 tests): Verifies 100% preservation of `fixtures/expected-records.json` (9 invoices, 5 payments, 7 open, INR 3,698.19) and restart persistence.

---

## Tool-Use Summary (Evaluation Requirement)

* **Tool & Model:** Antigravity IDE paired with Gemini 3.8 Flash (High).
* **Usage:** Assisted with fast codebase navigation, identifying seeded bugs against `BUSINESS_RULES.md`, authoring failing regression tests, and structuring fixture verification checks.
* **Key Decisions & Checks:**
  1. *Payment Matching:* Evaluated whether to support fuzzy matching; rejected this in favor of strict `(customer_id, invoice_number)` matching per the specification to prevent balance corruption.
  2. *Export Precision:* Caught that binary float truncation in `reporting.py` caused off-by-one cent errors in reports and replaced it with clean decimal rounding.
  3. *Fixture Preservation:* Rather than relying on manual checks, wrote an automated fixture test suite comparing against `expected-records.json` before and after simulated restarts.

---

For additional submission details and limits, see [HANDOVER.md](HANDOVER.md).
