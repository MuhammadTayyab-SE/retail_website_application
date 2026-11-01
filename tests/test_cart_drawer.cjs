const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const path = require('node:path');

// Exercise the production drawer handlers without a browser or database.
function setup() {
  function element() {
    return {
      listeners: {}, attributes: {}, dataset: {}, children: [], hidden: false,
      addEventListener(type, callback) { this.listeners[type] = callback; },
      setAttribute(name, value) { this.attributes[name] = value; },
      replaceChildren() { this.children = []; },
      append(child) { child.parent = this; this.children.push(child); },
      closest(selector) {
        const key = selector === '[data-cart-action]' ? 'cartAction' : 'cartId';
        return this.dataset[key] != null ? this : this.parent?.closest(selector);
      },
      querySelector(selector) {
        const action = selector.match(/data-cart-action="(.*?)"/)?.[1];
        const nodes = this.children.flatMap(child => [child, ...descendants(child)]);
        return nodes.find(node => action ? node.dataset.cartAction === action : node.className === selector.slice(1));
      },
      focus() { this.focused = true; },
      click() { this.listeners.click({ target: this }); },
    };
  }
  function descendants(node) { return node.children.flatMap(child => [child, ...descendants(child)]); }
  const floating = element();
  const empty = element();
  const items = element();
  const clear = element();
  const close = element();
  const shopping = element();
  const amounts = [element(), element()];
  const counters = [element(), element()];
  const drawer = element();
  drawer.open = false;
  drawer.querySelector = selector => ({
    '.homepage-cart-empty': empty, '.homepage-cart-items': items,
    '.homepage-cart-clear': clear, '.homepage-cart-close': close, '.homepage-cart-shopping': shopping,
  })[selector];
  drawer.querySelectorAll = () => amounts;
  drawer.showModal = () => { drawer.open = true; };
  drawer.close = () => { drawer.open = false; drawer.listeners.close(); };
  drawer.getBoundingClientRect = () => ({ left: 100, right: 448, top: 0, bottom: 800 });
  const document = {
    body: { style: { overflow: 'auto' } }, listeners: {},
    querySelector: selector => ({
      '#homepage-cart-drawer': drawer, '.rtsb-cart-float-inner': floating,
    })[selector],
    querySelectorAll: () => counters,
    createElement: element,
    addEventListener(type, callback) { this.listeners[type] = callback; },
  };
  const source = fs.readFileSync(path.join(__dirname, '../catalog/static/catalog/home02/snapshot.js'), 'utf8');
  const initialization = source.slice(0, source.indexOf('  const heroSlider ='));
  const addItems = source.slice(source.indexOf("  document.addEventListener('snapshot:add-items'"), source.indexOf('  function showDialog('));
  vm.runInNewContext(`${initialization}\n${addItems}\n})();`, { document, status() {} });
  return { document, floating, drawer, empty, items, clear, close, amounts, counters, shopping };
}

test('floating div opens empty drawer and close restores scrolling and focus', () => {
  const ui = setup();
  ui.floating.click();
  assert.equal(ui.drawer.open, true);
  assert.equal(ui.empty.hidden, false);
  assert.equal(ui.items.hidden, true);
  assert.equal(ui.clear.disabled, true);
  assert.equal(ui.amounts[0].textContent, 'PKR 0.00');
  assert.equal(ui.document.body.style.overflow, 'hidden');
  assert.equal(ui.floating.attributes['aria-expanded'], 'true');
  ui.close.click();
  assert.equal(ui.drawer.open, false);
  assert.equal(ui.document.body.style.overflow, 'auto');
  assert.equal(ui.floating.focused, true);
  assert.equal(ui.floating.attributes['aria-expanded'], 'false');
});

test('keyboard opens drawer, inside clicks preserve it, backdrop closes it', () => {
  const ui = setup();
  for (const key of ['Enter', ' ']) {
    let prevented = false;
    ui.floating.listeners.keydown({ key, preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assert.equal(ui.drawer.open, true);
    ui.drawer.listeners.click({ target: ui.drawer, clientX: 150, clientY: 200 });
    assert.equal(ui.drawer.open, true);
    ui.drawer.listeners.click({ target: ui.drawer, clientX: 50, clientY: 200 });
    assert.equal(ui.drawer.open, false);
  }
});

test('preview items and counts survive opening; Clear All returns to empty state', () => {
  const ui = setup();
  ui.document.listeners['snapshot:add-items']({ detail: [{ id: 'milk', name: 'Milk', quantity: 2 }] });
  ui.floating.click();
  assert.equal(ui.empty.hidden, true);
  assert.equal(ui.items.children[0].querySelector('.homepage-cart-item-details').children[0].textContent, 'Milk');
  assert.equal(ui.items.children[0].querySelector('.homepage-cart-item-quantity').textContent, '2');
  assert.equal(ui.counters[0].textContent, 2);
  assert.equal(ui.amounts[0].textContent, 'Not calculated');
  assert.equal(ui.clear.disabled, false);
  ui.clear.click();
  assert.equal(ui.items.children.length, 0);
  assert.equal(ui.empty.hidden, false);
  assert.equal(ui.counters[0].textContent, 0);
  assert.equal(ui.clear.disabled, true);
});

test('populated rows show product details and server prices, including a full discount', () => {
  const ui = setup();
  ui.document.listeners['snapshot:add-items']({ detail: [{
    id: 'milk', name: '<b>Milk</b>', description: 'Full cream, 1L', image: '/products/photos/1/',
    price: 39000, salePrice: 19500, stock: 3, quantity: 2,
  }] });
  ui.floating.click();
  const row = ui.items.children[0];
  assert.equal(row.children[0].src, '/products/photos/1/');
  assert.equal(row.children[0].alt, '<b>Milk</b>');
  const details = row.querySelector('.homepage-cart-item-details');
  assert.equal(details.children[0].textContent, '<b>Milk</b>');
  assert.equal(details.children[0].children.length, 0);
  assert.equal(row.querySelector('.homepage-cart-item-description').textContent, 'Full cream, 1L');
  const prices = row.querySelector('.homepage-cart-item-prices');
  assert.equal(prices.children[0].textContent, 'PKR 390.00');
  assert.equal(prices.children[1].textContent, 'PKR 195.00');
  assert.equal(ui.amounts[0].textContent, 'PKR 390.00');
});

test('quantity controls respect stock and minimum, update count/total, and remove last item', () => {
  const ui = setup();
  ui.document.listeners['snapshot:add-items']({ detail: [{
    id: 'milk', name: 'Milk', price: 14995, stock: 2, quantity: 1,
  }] });
  ui.floating.click();
  const button = action => ui.items.children[0].querySelector(`[data-cart-action="${action}"]`);
  const activate = action => ui.items.listeners.click({ target: button(action) });
  assert.equal(button('decrease').disabled, true);
  activate('decrease');
  assert.equal(ui.counters[0].textContent, 1);
  activate('increase');
  assert.equal(ui.counters[0].textContent, 2);
  assert.equal(ui.amounts[0].textContent, 'PKR 299.90');
  assert.equal(button('increase').disabled, true);
  activate('increase');
  assert.equal(ui.counters[0].textContent, 2);
  activate('decrease');
  assert.equal(ui.counters[0].textContent, 1);
  assert.equal(ui.amounts[0].textContent, 'PKR 149.95');
  activate('remove');
  assert.equal(ui.items.children.length, 0);
  assert.equal(ui.empty.hidden, false);
  assert.equal(ui.counters[0].textContent, 0);
  assert.equal(ui.amounts[0].textContent, 'PKR 0.00');
  assert.equal(ui.shopping.focused, true);
});

test('zero sale price is retained and removing one row keeps other basket products', () => {
  const ui = setup();
  ui.document.listeners['snapshot:add-items']({ detail: [
    { id: 'free', name: 'Free product', price: 10000, salePrice: 0, stock: 1, quantity: 1 },
    { id: 'rice', name: 'Rice', price: 25000, stock: 3, quantity: 1 },
  ] });
  ui.floating.click();
  assert.equal(ui.items.children[0].querySelector('.homepage-cart-item-prices').children[1].textContent, 'PKR 0.00');
  assert.equal(ui.amounts[0].textContent, 'PKR 250.00');
  const remove = ui.items.children[0].querySelector('[data-cart-action="remove"]');
  ui.items.listeners.click({ target: remove });
  assert.equal(ui.items.children.length, 1);
  assert.equal(ui.items.children[0].dataset.cartId, 'rice');
  assert.equal(ui.amounts[0].textContent, 'PKR 250.00');
});
