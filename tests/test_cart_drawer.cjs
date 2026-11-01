const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const path = require('node:path');

// Exercise the production drawer handlers without a browser or database.
function setup() {
  function element() {
    return {
      listeners: {}, attributes: {}, children: [], hidden: false,
      addEventListener(type, callback) { this.listeners[type] = callback; },
      setAttribute(name, value) { this.attributes[name] = value; },
      replaceChildren() { this.children = []; },
      append(child) { this.children.push(child); },
      focus() { this.focused = true; },
      click() { this.listeners.click({ target: this }); },
    };
  }
  const floating = element();
  const empty = element();
  const items = element();
  const clear = element();
  const close = element();
  const amounts = [element(), element()];
  const counters = [element(), element()];
  const drawer = element();
  drawer.open = false;
  drawer.querySelector = selector => ({
    '.homepage-cart-empty': empty, '.homepage-cart-items': items,
    '.homepage-cart-clear': clear, '.homepage-cart-close': close,
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
  return { document, floating, drawer, empty, items, clear, close, amounts, counters };
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
  assert.equal(ui.items.children[0].textContent, 'Milk × 2');
  assert.equal(ui.counters[0].textContent, 2);
  assert.equal(ui.amounts[0].textContent, 'Not calculated');
  assert.equal(ui.clear.disabled, false);
  ui.clear.click();
  assert.equal(ui.items.children.length, 0);
  assert.equal(ui.empty.hidden, false);
  assert.equal(ui.counters[0].textContent, '0');
  assert.equal(ui.clear.disabled, true);
});
