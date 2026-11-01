(() => {
  'use strict';
  const form = document.querySelector('#checkout-form');
  const submit = document.querySelector('#checkout-submit');
  const feedback = document.querySelector('#checkout-feedback');
  const money = value => `PKR ${Number(value).toFixed(2)}`;
  let quoteVersion = 0;
  let quoting = false;
  let placing = false;
  let lastQuotedCart = '';
  let quoteToken = '';
  function cartItems() {
    try {
      const records = JSON.parse(sessionStorage.getItem('retail-preview-basket-v1') || '[]');
      if (!Array.isArray(records)) return [];
      return records.filter(record => Array.isArray(record) && record[1]).map(([id, item]) => ({ id, quantity: item.quantity }));
    } catch { return []; }
  }
  function error(message, focus = false) {
    feedback.textContent = message;
    feedback.hidden = !message;
    if (focus) feedback.focus();
  }
  async function post(url, data) {
    const response = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value },
      body: JSON.stringify(data),
    });
    if (!response.headers.get('Content-Type')?.includes('application/json')) {
      throw Error('The server could not process checkout. Reload this page and try again.');
    }
    const payload = await response.json();
    if (!response.ok) {
      if (payload.fields) {
        form.querySelectorAll('[aria-invalid]').forEach(field => field.removeAttribute('aria-invalid'));
        for (const [name, messages] of Object.entries(payload.fields)) {
          const field = form.elements.namedItem(name);
          if (field instanceof HTMLElement) {
            field.setAttribute('aria-invalid', 'true');
            field.setCustomValidity(messages.map(item => item.message).join(' '));
          }
        }
        form.reportValidity();
      }
      throw Error(payload.error || 'The request could not be completed.');
    }
    return payload;
  }
  async function quote() {
    const version = ++quoteVersion;
    quoting = true;
    submit.disabled = true;
    const items = cartItems();
    if (!items.length) {
      document.querySelector('#checkout-items').textContent = 'Your cart is empty. Return to Shop to add groceries.';
      quoting = false;
      error('Your cart is empty.');
      return;
    }
    try {
      const data = await post(form.dataset.quoteUrl, { items, city: form.elements.city.value });
      if (version !== quoteVersion || placing) return;
      const host = document.querySelector('#checkout-items');
      host.replaceChildren();
      let count = 0;
      data.items.forEach(item => {
        count += item.quantity;
        const row = document.createElement('div');
        row.className = 'checkout-order-item';
        const image = document.createElement('img');
        if (item.image) { image.src = item.image; image.alt = item.name; }
        else { image.hidden = true; }
        const details = document.createElement('div');
        const name = document.createElement('h3');
        name.textContent = item.name;
        const quantity = document.createElement('p');
        quantity.textContent = `Qty ${item.quantity} · ${money(item.unit_price)} each`;
        details.append(name, quantity);
        const amount = document.createElement('strong');
        amount.textContent = money(item.line_total);
        row.append(image, details, amount);
        host.append(row);
      });
      document.querySelector('#checkout-item-count').textContent = `${count} item${count === 1 ? '' : 's'}`;
      document.querySelector('#checkout-subtotal').textContent = money(data.subtotal);
      document.querySelector('#checkout-delivery-fee').textContent = money(data.delivery_fee);
      document.querySelector('#checkout-tax').textContent = money(data.tax);
      document.querySelector('#checkout-total').textContent = money(data.total);
      const note = document.querySelector('#checkout-total-note');
      note.textContent = data.free_delivery_remaining == null ? '' : Number(data.free_delivery_remaining) > 0
        ? `Add ${money(data.free_delivery_remaining)} more to unlock free delivery.` : 'Free delivery unlocked.';
      const progress = document.querySelector('#checkout-delivery-progress');
      progress.hidden = data.free_delivery_threshold == null;
      document.querySelector('#checkout-delivery-progress-label').textContent = note.textContent;
      const threshold = Number(data.free_delivery_threshold);
      document.querySelector('#checkout-delivery-progress-bar').value = threshold > 0
        ? Math.min(100, Number(data.subtotal) / threshold * 100) : 100;
      lastQuotedCart = JSON.stringify(items);
      quoteToken = data.quote_token;
      error('');
      submit.disabled = form.dataset.enabled !== 'true';
    } catch (failure) { if (version === quoteVersion) error(failure.message); }
    finally { if (version === quoteVersion) quoting = false; }
  }
  form.addEventListener('input', event => { event.target.setCustomValidity?.(''); event.target.removeAttribute('aria-invalid'); });
  form.elements.city.addEventListener('change', quote);
  document.addEventListener('snapshot:basket-changed', quote);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (placing || quoting || submit.disabled || !form.reportValidity()) return;
    const items = cartItems();
    if (JSON.stringify(items) !== lastQuotedCart) { await quote(); error('Your cart changed. Review the updated total and place your order again.', true); return; }
    placing = true;
    submit.disabled = true;
    submit.textContent = 'Placing order…';
    try {
      const data = await post(form.dataset.orderUrl, { items, quote_token: quoteToken, details: Object.fromEntries(new FormData(form)) });
      try {
        const purchased = new Map(items.map(item => [item.id, item.quantity]));
        const remaining = JSON.parse(sessionStorage.getItem('retail-preview-basket-v1') || '[]')
          .map(([id, item]) => [id, { ...item, quantity: item.quantity - (purchased.get(id) || 0) }])
          .filter(([, item]) => item.quantity > 0);
        sessionStorage.setItem('retail-preview-basket-v1', JSON.stringify(remaining));
      } catch { /* The order exists even if browser storage became unavailable. */ }
      window.location.assign(data.confirmation_url);
    } catch (failure) {
      placing = false;
      submit.textContent = 'Place order';
      // Refresh prices and stock after an unsuccessful placement before another attempt.
      await quote();
      error(failure.message, true);
    }
  });
  quote();
})();
