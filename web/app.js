const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });
const money = n => currency.format(n);
const text = (tag, value, className = '') => {
  const node = document.createElement(tag);
  node.textContent = value;
  node.className = className;
  return node;
};

async function refresh() {
  const status = document.querySelector('#status').value;
  const responses = await Promise.all([fetch('/api/overview'), fetch(`/api/invoices?status=${status}`)]);
  if (responses.some(r => !r.ok)) throw new Error('Could not refresh the register.');
  const [data, rows] = await Promise.all(responses.map(r => r.json()));
  document.querySelector('#invoice-count').textContent = data.summary.invoice_count;
  document.querySelector('#open-count').textContent = data.summary.open_count;
  document.querySelector('#outstanding').textContent = money(data.summary.outstanding);
  const unmatchedTotalEl = document.querySelector('#unmatched-total');
  if (unmatchedTotalEl) {
    unmatchedTotalEl.textContent = `${data.summary.unmatched_count ?? data.unmatched_payments.length} (${money(data.summary.unmatched_total ?? 0)})`;
  }
  const body = document.querySelector('#invoices');
  body.replaceChildren();
  rows.forEach(r => {
    const row = document.createElement('tr');
    [r.customer_name, r.invoice_number, r.due_date].forEach(v => row.append(text('td', v)));
    [r.amount, r.paid, r.balance].forEach(v => row.append(text('td', money(v), 'number')));
    const statusCell = text('td', r.status);
    if (r.is_overdue) {
      statusCell.append(text('span', ' Overdue', 'badge-overdue'));
    }
    row.append(statusCell);
    body.append(row);
  });
  const unmatched = document.querySelector('#unmatched');
  unmatched.replaceChildren(...data.unmatched_payments.map(p => text('li', `${p.payment_id} · ${p.customer_id} / ${p.invoice_number} · ${money(p.amount)}`)));
  if (!data.unmatched_payments.length) unmatched.append(text('li', 'No unmatched payments.'));
  document.querySelector('#page-error').textContent = '';
}

async function submitImport(form) {
  const feedback = form.querySelector('.feedback');
  const button = form.querySelector('button');
  const input = form.querySelector('input');
  button.disabled = true;
  feedback.textContent = 'Importing…';
  try {
    const file = input.files && input.files[0];
    if (!file) {
      feedback.textContent = 'Please choose a CSV file first.';
      return;
    }
    const csv = await file.text();
    const res = await fetch(`/api/import?kind=${form.dataset.kind}`, {
      method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: csv
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      feedback.textContent = `Import failed: ${data.error || res.statusText || 'Unknown error'}`;
      return;
    }
    let msg = `Import complete: ${data.imported} imported, ${data.skipped} skipped, ${data.rejected} rejected.`;
    if (data.errors && data.errors.length) {
      const errMsgs = data.errors.map(e => `  • Line ${e.line}: ${e.reason}`).join('\n');
      msg += `\nErrors:\n${errMsgs}`;
    }
    feedback.textContent = msg;
    input.value = '';
    await refresh();
  } catch (error) {
    feedback.textContent = `Import failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

document.querySelector('#status').addEventListener('change', () => refresh().catch(e => { document.querySelector('#page-error').textContent = e.message; }));
document.querySelectorAll('form[data-kind]').forEach(form => form.addEventListener('submit', e => { e.preventDefault(); submitImport(form); }));
refresh().catch(e => { document.querySelector('#page-error').textContent = e.message; });
