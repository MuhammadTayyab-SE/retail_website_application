const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const path = require('node:path');

// Exercise the production drawer handlers without a browser or database.
function setup(storage) {
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
  const addCard = source.slice(source.indexOf('    if (/add_to_cart|add-to-cart/'), source.indexOf('    if (product && /wishlist/'));
  const runtime = { document, status() {}, sessionStorage: storage };
  vm.runInNewContext(`${initialization}\n${addItems}
    globalThis.addCard = (product, control) => {
      const classes = 'rtsb-add-to-cart-btn', href = '#';
      const productTitle = product.name, id = product.dataset.id;
      const event = { preventDefault() {} };
      ${addCard}
    };
  })();`, runtime);
  return { document, floating, drawer, empty, items, clear, close, amounts, counters, shopping, addCard: runtime.addCard };
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
  assert.equal(remove.children[0].className, 'fas fa-trash-alt');
  assert.equal(remove.attributes['aria-label'], 'Delete Free product');
  assert.notEqual(remove.textContent, 'Remove');
  ui.items.listeners.click({ target: remove });
  assert.equal(ui.items.children.length, 1);
  assert.equal(ui.items.children[0].dataset.cartId, 'rice');
  assert.equal(ui.amounts[0].textContent, 'PKR 250.00');
});

test('Add to cart recovers regular and sale prices from older cached card HTML', () => {
  for (const sale of [false, true]) {
    const ui = setup();
    const priceHost = {
      querySelector: selector => selector === 'ins .amount'
        ? (sale ? { textContent: 'PKR 499.95' } : null)
        : { textContent: 'PKR 1,000.00' },
    };
    const product = {
      name: 'Milk', dataset: { id: 'milk' },
      querySelector: selector => selector === '.homepage-featured-price, .product-price'
        ? priceHost : { src: '/products/photos/1/' },
    };
    const control = { closest: () => ({ dataset: {} }) };
    ui.addCard(product, control);
    ui.floating.click();
    const prices = ui.items.children[0].querySelector('.homepage-cart-item-prices');
    assert.equal(prices.children[0].textContent, 'PKR 1000.00');
    if (sale) assert.equal(prices.children[1].textContent, 'PKR 499.95');
    assert.equal(ui.amounts[0].textContent, sale ? 'PKR 499.95' : 'PKR 1000.00');
  }
});

test('server price metadata takes precedence over stale visible card prices', () => {
  const ui = setup();
  const product = {
    name: 'Milk', dataset: { id: 'milk' },
    querySelector: selector => selector === '.homepage-featured-price, .product-price'
      ? { querySelector: () => ({ textContent: 'PKR 999.00' }) } : null,
  };
  const control = { closest: () => ({ dataset: { cartPrice: '390.00', cartSalePrice: '0.00', cartStock: '1' } }) };
  ui.addCard(product, control);
  ui.floating.click();
  const prices = ui.items.children[0].querySelector('.homepage-cart-item-prices');
  assert.equal(prices.children[0].textContent, 'PKR 390.00');
  assert.equal(prices.children[1].textContent, 'PKR 0.00');
  assert.equal(ui.amounts[0].textContent, 'PKR 0.00');
});

function tabStorage(initial = null) {
  let value = initial;
  return { getItem() { return value; }, setItem(key, next) { value = next; } };
}

test('cart details, quantities and deletion survive navigation between page instances', () => {
  const storage = tabStorage();
  const home = setup(storage);
  home.document.listeners['snapshot:add-items']({ detail: [{
    id: 'live-11', name: 'Milk', description: 'Full cream', image: '/products/photos/34/',
    quantity: 1, price: 39000, salePrice: 19500, stock: 3,
  }] });
  const shop = setup(storage);
  assert.equal(shop.counters[0].textContent, 1);
  shop.floating.click();
  assert.equal(shop.items.children[0].children[0].src, '/products/photos/34/');
  assert.equal(shop.items.children[0].querySelector('.homepage-cart-item-description').textContent, 'Full cream');
  const plus = shop.items.children[0].querySelector('[data-cart-action="increase"]');
  shop.items.listeners.click({ target: plus });
  const product = setup(storage);
  product.floating.click();
  assert.equal(product.counters[0].textContent, 2);
  assert.equal(product.amounts[0].textContent, 'PKR 390.00');
  const remove = product.items.children[0].querySelector('[data-cart-action="remove"]');
  product.items.listeners.click({ target: remove });
  const returned = setup(storage);
  assert.equal(returned.empty.hidden, false);
  assert.equal(returned.counters[0].textContent, 0);
});

test('Clear All remains cleared after reload; malformed/blocked storage does not break cart', () => {
  const storage = tabStorage();
  const ui = setup(storage);
  ui.document.listeners['snapshot:add-items']({ detail: [{ id: 'rice', name: 'Rice', quantity: 1 }] });
  ui.floating.click();
  ui.clear.click();
  assert.equal(setup(storage).counters[0].textContent, 0);
  for (const bad of ['{bad JSON', '{}', '[["bad",{"name":"Bad","quantity":-2}]]']) {
    assert.equal(setup(tabStorage(bad)).counters[0].textContent, 0);
  }
  const blocked = setup({ getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); } });
  blocked.document.listeners['snapshot:add-items']({ detail: [{ id: 'rice', name: 'Rice', quantity: 1 }] });
  blocked.floating.click();
  assert.equal(blocked.counters[0].textContent, 1);
});

test('Shop cards use their product metadata and merge into the same cart across reloads', () => {
  const storage = tabStorage();
  const shop = setup(storage);
  const product = {
    name: 'Rice', dataset: { id: 'live-11', cartDescription: 'Basmati', cartPrice: '250.00', cartSalePrice: '', cartStock: '3' },
    querySelector: () => null,
  };
  shop.addCard(product, { closest: () => null });
  const nextPage = setup(storage);
  nextPage.addCard(product, { closest: () => null });
  nextPage.floating.click();
  assert.equal(nextPage.items.children.length, 1);
  assert.equal(nextPage.counters[0].textContent, 2);
  assert.equal(nextPage.amounts[0].textContent, 'PKR 500.00');
});

test('product-page Add to Cart sends complete details and stable standard/variant IDs', () => {
  const storage = tabStorage();
  const ui = setup(storage);
  let add;
  const button = { disabled: false, addEventListener(type, callback) { add = callback; } };
  const source = fs.readFileSync(path.join(__dirname, '../catalog/static/catalog/product/product.js'), 'utf8');
  const handler = source.slice(source.indexOf("  document.querySelector('#product-add').addEventListener"), source.indexOf('  viewOption(data.selected);'));
  const runtime = {
    data: { product: '11', name: 'Milk', stock: 3, photos: [{ variant: '', src: '/products/photos/34/' }] },
    selection: () => [{ option: { id: '', price: '195.00', regular_price: '390.00', description: 'Full cream' }, input: { value: '1' } }],
    updateTotal() {}, CustomEvent: class { constructor(type, payload) { this.type = type; this.detail = payload.detail; } },
    document: { querySelector: () => button, dispatchEvent: event => ui.document.listeners[event.type](event) },
  };
  vm.runInNewContext(handler, runtime);
  add();
  const nextPage = setup(storage);
  nextPage.floating.click();
  assert.equal(nextPage.items.children[0].dataset.cartId, 'live-11');
  assert.equal(nextPage.amounts[0].textContent, 'PKR 195.00');
  assert.equal(nextPage.items.children[0].children[0].src, '/products/photos/34/');
  runtime.selection = () => [{ option: { id: '7', label: 'Large', price: '500.00', regular_price: '500.00' }, input: { value: '1' } }];
  add();
  const variants = setup(storage);
  assert.equal(variants.items.children.length, 2);
  assert.equal(variants.items.children[1].dataset.cartId, 'live-11:7');
});
