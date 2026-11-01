const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

async function page({ payload, fail = false, pickup = false, empty = false }) {
  function element(value = '') {
    return {
      value, hidden: false, disabled: false, children: [], textContent: '', listeners: {},
      append(...nodes) { this.children.push(...nodes); },
      replaceChildren() { this.children = []; this.textContent = ''; },
      addEventListener(type, callback) { this.listeners[type] = callback; },
      focus() {}, querySelectorAll() { return []; },
    };
  }
  const nodes = new Map();
  const node = selector => { if (!nodes.has(selector)) nodes.set(selector, element()); return nodes.get(selector); };
  const form = node('#checkout-form');
  form.dataset = { quoteUrl: '/checkout/quote/', orderUrl: '/checkout/place/', enabled: 'true' };
  form.elements = {
    csrfmiddlewaretoken: element('test-token'), city: element('Lahore'), address: element('Address'),
    delivery_method: element(pickup ? 'pickup' : 'delivery'),
  };
  const deliverySection = element();
  deliverySection.querySelectorAll = () => [form.elements.city, form.elements.address];
  let request;
  const records = empty ? [] : [['live-11', { name: 'Milk', price: 10000, salePrice: 7500,
    quantity: 2, image: '/products/photos/1/' }]];
  const runtime = {
    document: {
      querySelector: node, createElement: element,
      querySelectorAll: selector => selector === '.checkout-delivery-only' ? [deliverySection] : [],
      addEventListener() {},
    },
    sessionStorage: { getItem() { return JSON.stringify(records); } },
    fetch: async (url, options) => {
      request = JSON.parse(options.body);
      if (fail) throw Error('Network unavailable');
      return { ok: true, headers: { get() { return 'application/json'; } }, json: async () => payload };
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../catalog/static/catalog/checkout/checkout.js'), 'utf8'), runtime);
  await new Promise(resolve => setImmediate(resolve));
  return { node, form, request, deliverySection };
}

function quote(canPlace = true) {
  return {
    items: [{ name: 'Milk', quantity: 2, unit_price: '75.00', regular_price: '100.00', line_total: '150.00', image: '/products/photos/1/' }],
    subtotal: '150.00', delivery_fee: '200.00', tax: '0.00', total: '350.00',
    free_delivery_threshold: '5000.00', free_delivery_remaining: '4850.00',
    can_place_order: canPlace, error: canPlace ? '' : 'The minimum order is PKR 1500.00.', quote_token: 'test-quote',
  };
}

test('below-minimum carts keep their authoritative summary visible', async () => {
  const ui = await page({ payload: quote(false) });
  assert.equal(ui.node('#checkout-items').children.length, 1);
  assert.equal(ui.node('#checkout-subtotal').textContent, 'PKR 150.00');
  assert.equal(ui.node('#checkout-total').textContent, 'PKR 350.00');
  assert.equal(ui.node('#checkout-submit').disabled, true);
  assert.match(ui.node('#checkout-feedback').textContent, /minimum order/);
});

test('network failure preserves cart item preview without inventing verified totals', async () => {
  const ui = await page({ fail: true });
  assert.equal(ui.node('#checkout-items').children.length, 1);
  assert.equal(ui.node('#checkout-item-count').textContent, '2 items');
  assert.equal(ui.node('#checkout-delivery-fee').textContent, 'Pending');
  assert.equal(ui.node('#checkout-submit').disabled, true);
  assert.equal(ui.node('#checkout-feedback').textContent, 'Network unavailable');
});

test('pickup quotes send fulfillment choice and do not require a delivery address', async () => {
  const data = quote();
  Object.assign(data, { delivery_fee: '0.00', total: '150.00', free_delivery_threshold: null, free_delivery_remaining: null });
  const ui = await page({ pickup: true, payload: data });
  assert.equal(ui.request.delivery_method, 'pickup');
  assert.equal(ui.form.elements.address.required, false);
  assert.equal(ui.form.elements.city.disabled, true);
  assert.equal(ui.deliverySection.hidden, true);
  assert.equal(ui.node('#checkout-delivery-progress').hidden, true);
  assert.equal(ui.node('#checkout-submit').disabled, false);
});

test('empty cart shows recovery text rather than a blank summary', async () => {
  const ui = await page({ empty: true });
  assert.match(ui.node('#checkout-items').textContent, /cart is empty/);
  assert.equal(ui.node('#checkout-item-count').textContent, '0 items');
  assert.equal(ui.node('#checkout-submit').disabled, true);
});
