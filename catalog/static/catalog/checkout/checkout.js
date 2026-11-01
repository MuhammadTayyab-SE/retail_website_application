(() => {
  'use strict';
  const form = document.querySelector('#checkout-form');
  const submit = document.querySelector('#checkout-submit');
  const feedback = document.querySelector('#checkout-feedback');
  const money = value => value == null || !Number.isFinite(Number(value)) ? 'Pending' : `PKR ${Number(value).toFixed(2)}`;
  let quoteVersion = 0;
  let quoting = false;
  let placing = false;
  let lastQuotedCart = '';
  let quoteToken = '';
  const knownStock = new Map();
  function cartRecords() {
    try {
      const records = JSON.parse(sessionStorage.getItem('retail-preview-basket-v1') || '[]');
      if (!Array.isArray(records)) return [];
      return records.filter(record => Array.isArray(record) && record[1]
        && Number.isSafeInteger(record[1].quantity) && record[1].quantity > 0);
    } catch { return []; }
  }
  function cartItems() {
    return cartRecords().map(([id, item]) => ({ id, quantity: item.quantity }));
  }
  function renderSummary(data) {
    const host = document.querySelector('#checkout-items');
    const focusAction = document.activeElement?.dataset?.checkoutAction;
    const focusId = document.activeElement?.closest('[data-checkout-id]')?.dataset.checkoutId;
    host.replaceChildren();
    let count = 0;
    data.items.forEach(item => {
      count += item.quantity;
      if (!data.preview && item.stock != null) knownStock.set(item.id, item.stock);
      const row = document.createElement('div');
      row.className = 'checkout-order-item';
      row.dataset.checkoutId = item.id;
      row.dataset.stock = String(item.stock ?? Number.MAX_SAFE_INTEGER);
      const photo = document.createElement('div');
      photo.className = 'checkout-order-photo';
      if (item.image) {
        const image = document.createElement('img');
        image.src = item.image;
        image.alt = item.name;
        photo.append(image);
      } else photo.textContent = 'No photo';
      const details = document.createElement('div');
      details.className = 'checkout-order-details';
      const name = document.createElement('h3');
      name.textContent = item.name;
      const prices = document.createElement('div');
      prices.className = 'checkout-order-prices';
      if (Number(item.regular_price) > Number(item.unit_price)) {
        const regular = document.createElement('del');
        regular.textContent = money(item.regular_price);
        prices.append(regular);
      }
      const current = document.createElement('strong');
      current.textContent = money(item.unit_price);
      prices.append(current);
      const controls = document.createElement('div');
      controls.className = 'checkout-quantity-control';
      for (const action of ['decrease', 'increase']) {
        const button = document.createElement('button');
        button.type = 'button';
        button.dataset.checkoutAction = action;
        button.textContent = action === 'increase' ? '+' : '-';
        button.setAttribute('aria-label', `${action === 'increase' ? 'Increase' : 'Decrease'} quantity of ${item.name}`);
        button.disabled = placing || (action === 'decrease' && item.quantity <= 1)
          || (action === 'increase' && item.stock != null && item.quantity >= item.stock);
        controls.append(button);
        if (action === 'decrease') {
          const quantity = document.createElement('span');
          quantity.textContent = String(item.quantity);
          quantity.setAttribute('aria-label', `Quantity: ${item.quantity}`);
          controls.append(quantity);
        }
      }
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'checkout-delete-item';
      remove.dataset.checkoutAction = 'remove';
      remove.disabled = placing;
      remove.setAttribute('aria-label', `Delete ${item.name}`);
      const icon = document.createElement('i');
      icon.className = 'far fa-trash-alt';
      icon.setAttribute('aria-hidden', 'true');
      remove.append(icon);
      details.append(name, prices, controls);
      row.append(photo, details, remove);
      host.append(row);
    });
    if (focusAction) {
      const row = [...host.children].find(item => item.dataset.checkoutId === focusId);
      const target = row?.querySelector(`[data-checkout-action="${focusAction}"]`);
      if (target && !target.disabled) target.focus();
      else if (row) row.querySelector('[data-checkout-action="remove"]').focus();
      else if (host.children.length) host.children[0].querySelector('[data-checkout-action="remove"]').focus();
      else document.querySelector('#checkout-view-cart').focus();
    }
    if (!count) host.textContent = 'Your cart is empty. Return to Shop to add groceries.';
    document.querySelector('#checkout-item-count').textContent = String(count);
    document.querySelector('#checkout-item-count').setAttribute('aria-label', `${count} items`);
    document.querySelector('#checkout-clear-cart').disabled = !count || placing;
    document.querySelector('#checkout-subtotal').textContent = money(data.subtotal);
    const shipping = document.querySelector('#checkout-delivery-fee');
    const freeShipping = data.delivery_fee != null && Number(data.delivery_fee) === 0;
    shipping.textContent = freeShipping ? 'Free' : money(data.delivery_fee);
    shipping.dataset.free = String(freeShipping);
    document.querySelector('#checkout-tax').textContent = money(data.tax);
    document.querySelector('#checkout-tax-row').hidden = data.tax == null || Number(data.tax) === 0;
    document.querySelector('#checkout-total').textContent = money(data.total);
    const note = document.querySelector('#checkout-total-note');
    note.textContent = data.preview ? 'Checking current prices and availability...'
      : data.free_delivery_remaining == null ? '' : Number(data.free_delivery_remaining) > 0
        ? `Add ${money(data.free_delivery_remaining)} more to unlock free delivery.` : 'Free delivery unlocked.';
    const progress = document.querySelector('#checkout-delivery-progress');
    progress.hidden = data.free_delivery_threshold == null;
    document.querySelector('#checkout-delivery-progress-label').textContent = note.textContent;
    const threshold = Number(data.free_delivery_threshold);
    document.querySelector('#checkout-delivery-progress-bar').value = threshold > 0
      ? Math.min(100, Number(data.subtotal) / threshold * 100) : 100;
  }
  function renderPreview() {
    const items = cartRecords().map(([id, item]) => {
      const cents = item.salePrice ?? item.price;
      const unit = Number.isSafeInteger(cents) ? cents / 100 : null;
      return { id, stock: knownStock.get(id) ?? item.stock, name: item.name, image: item.image, quantity: item.quantity,
        unit_price: unit, regular_price: Number.isSafeInteger(item.price) ? item.price / 100 : null,
        line_total: unit == null ? null : unit * item.quantity };
    });
    renderSummary({ items, preview: true,
      subtotal: items.every(item => item.line_total != null)
        ? items.reduce((sum, item) => sum + item.line_total, 0) : null });
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
    renderPreview();
    if (!items.length) {
      document.querySelector('#checkout-items').textContent = 'Your cart is empty. Return to Shop to add groceries.';
      quoting = false;
      error('Your cart is empty.');
      return;
    }
    try {
      const data = await post(form.dataset.quoteUrl, { items, city: form.elements.city.value, delivery_method: form.elements.delivery_method.value });
      if (version !== quoteVersion || placing) return;
      renderSummary(data);
      lastQuotedCart = JSON.stringify(items);
      quoteToken = data.quote_token;
      error(data.error || '');
      submit.disabled = form.dataset.enabled !== 'true' || data.can_place_order !== true;
    } catch (failure) { if (version === quoteVersion) { error(failure.message); document.querySelector('#checkout-total-note').textContent = 'Cart prices are shown for reference. Your order must be verified before submission.'; } }
    finally { if (version === quoteVersion) quoting = false; }
  }
  document.querySelector('#checkout-items').addEventListener('click', event => {
    const button = event.target.closest('[data-checkout-action]');
    if (!button || button.disabled || placing) return;
    const row = button.closest('[data-checkout-id]');
    document.dispatchEvent(new CustomEvent('snapshot:edit-cart', { detail: {
      action: button.dataset.checkoutAction, id: row.dataset.checkoutId, limit: Number(row.dataset.stock),
    } }));
  });
  document.querySelector('#checkout-clear-cart').addEventListener('click', () => {
    if (placing) return;
    document.dispatchEvent(new CustomEvent('snapshot:edit-cart', { detail: { action: 'clear' } }));
    document.querySelector('#checkout-view-cart').focus();
  });
  document.querySelector('#checkout-view-cart').addEventListener('click', () => {
    if (!placing) document.querySelector('.rtsb-cart-float-inner')?.click();
  });
  form.addEventListener('input', event => { event.target.setCustomValidity?.(''); event.target.removeAttribute('aria-invalid'); });
  function updateFulfillment() {
    const pickup = form.elements.delivery_method.value === 'pickup';
    document.querySelectorAll('.checkout-delivery-only').forEach(section => {
      section.hidden = pickup;
      section.querySelectorAll('input, select, textarea').forEach(field => { field.disabled = pickup; });
    });
    form.elements.address.required = !pickup;
    form.elements.city.required = !pickup;
  }
  document.querySelectorAll('[name="delivery_method"]').forEach(option => {
    option.addEventListener('change', () => { updateFulfillment(); quote(); });
  });
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
  updateFulfillment();
  quote();
})();
