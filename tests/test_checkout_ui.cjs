const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

async function page({ payload, fail = false, pickup = false, empty = false }) {
  function element(value = '') {
    return {
      value, dataset: {}, attributes: {}, hidden: false, disabled: false, children: [], textContent: '', listeners: {},
      append(...nodes) { nodes.forEach(child => { child.parent = this; this.children.push(child); }); },
      setAttribute(name, value) { this.attributes[name] = value; },
      closest(selector) {
        const key = selector === '[data-checkout-action]' ? 'checkoutAction' : 'checkoutId';
        return this.dataset[key] != null ? this : this.parent?.closest(selector);
      },
      querySelector(selector) {
        const action = selector.match(/data-checkout-action="(.*?)"/)?.[1];
        const nodes = this.children.flatMap(child => [child, ...descendants(child)]);
        return nodes.find(child => action ? child.dataset.checkoutAction === action : child.className === selector.slice(1));
      },
      replaceChildren() { this.children = []; this.textContent = ''; },
      addEventListener(type, callback) { this.listeners[type] = callback; },
      focus() {}, querySelectorAll() { return []; },
    };
  }
  function descendants(node) { return node.children.flatMap(child => [child, ...descendants(child)]); }
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
    quantity: 2, stock: 5, image: '/products/photos/1/' }]];
  const edits = [];
  const runtime = {
    document: {
      querySelector: node, createElement: element,
      querySelectorAll: selector => selector === '.checkout-delivery-only' ? [deliverySection] : [],
      addEventListener() {},
      dispatchEvent(event) { if (event.type === 'snapshot:edit-cart') edits.push(event.detail); },
    },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    sessionStorage: { getItem() { return JSON.stringify(records); } },
    fetch: async (url, options) => {
      request = JSON.parse(options.body);
      if (fail) throw Error('Network unavailable');
      return { ok: true, headers: { get() { return 'application/json'; } }, json: async () => payload };
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../catalog/static/catalog/checkout/checkout.js'), 'utf8'), runtime);
  await new Promise(resolve => setImmediate(resolve));
  return { node, form, request, deliverySection, edits };
}

function quote(canPlace = true) {
  return {
    items: [{ id: 'live-11', stock: 5, name: 'Milk', quantity: 2, unit_price: '75.00', regular_price: '100.00', line_total: '150.00', image: '/products/photos/1/' }],
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
  assert.equal(ui.node('#checkout-item-count').textContent, 'Total items in cart: 2');
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
  assert.equal(ui.node('#checkout-delivery-fee').textContent, 'Free');
});

test('empty cart shows recovery text rather than a blank summary', async () => {
  const ui = await page({ empty: true });
  assert.match(ui.node('#checkout-items').textContent, /cart is empty/);
  assert.equal(ui.node('#checkout-item-count').textContent, 'Total items in cart: 0');
  assert.equal(ui.node('#checkout-submit').disabled, true);
});

test('summary quantity and delete controls send edits to the shared cart', async () => {
  const ui = await page({ payload: quote() });
  const row = ui.node('#checkout-items').children[0];
  const plus = row.querySelector('[data-checkout-action="increase"]');
  ui.node('#checkout-items').listeners.click({ target: plus });
  assert.equal(ui.edits[0].action, 'increase');
  assert.equal(ui.edits[0].id, 'live-11');
  assert.equal(ui.edits[0].limit, 5);
  const remove = row.querySelector('[data-checkout-action="remove"]');
  assert.equal(remove.children[0].className, 'far fa-trash-alt');
  ui.node('#checkout-items').listeners.click({ target: remove });
  assert.equal(ui.edits[1].action, 'remove');
  ui.node('#checkout-clear-cart').listeners.click();
  assert.equal(ui.edits[2].action, 'clear');
});

test('stock limit disables increase and eligible shipping is labelled Free', async () => {
  const data = quote();
  data.items[0].stock = 2;
  data.delivery_fee = '0.00';
  data.free_delivery_remaining = '0.00';
  const ui = await page({ payload: data });
  const plus = ui.node('#checkout-items').children[0].querySelector('[data-checkout-action="increase"]');
  assert.equal(plus.disabled, true);
  ui.node('#checkout-items').listeners.click({ target: plus });
  assert.equal(ui.edits.length, 0);
  assert.equal(ui.node('#checkout-delivery-fee').textContent, 'Free');
  assert.equal(ui.node('#checkout-tax-row').hidden, true);
});
