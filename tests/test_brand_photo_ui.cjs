const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function editor(original = '') {
  function element() {
    return { hidden: false, checked: false, textContent: '', listeners: {},
      addEventListener(type, callback) { this.listeners[type] = callback; } };
  }
  const form = element();
  const input = { ...element(), files: [], closest: () => form };
  Object.defineProperty(input, 'value', { set() { this.files = []; } });
  const image = { ...element(), src: original,
    getAttribute() { return this.src; }, removeAttribute() { this.src = ''; } };
  const empty = element(), name = element(), status = element(), remove = element();
  const clear = original ? element() : null;
  const nodes = { 'input[type="file"]': input, '[data-brand-image]': image,
    '[data-brand-image-empty]': empty, '[data-brand-image-name]': name,
    '[data-brand-image-status]': status, '[data-brand-image-remove]': remove,
    'input[name$="-clear"]': clear };
  const revoked = [], created = [], windowEvents = {};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../catalog/static/catalog/admin/brands.js'), 'utf8'), {
    document: { querySelectorAll: () => [{ querySelector: selector => nodes[selector] }] },
    window: { addEventListener(type, callback) { windowEvents[type] = callback; } },
    URL: { createObjectURL(file) { created.push(file); return `blob:brand-${created.length}`; },
      revokeObjectURL(url) { revoked.push(url); } }, queueMicrotask,
  });
  return { input, image, empty, name, status, remove, clear, revoked, created, windowEvents };
}

test('selected brand photos display immediately and release replaced object URLs', () => {
  const ui = editor();
  const first = { name: 'New brand.png' };
  ui.input.files = [first];
  ui.input.listeners.change();
  assert.equal(ui.image.src, 'blob:brand-1');
  assert.equal(ui.image.hidden, false);
  assert.equal(ui.empty.hidden, true);
  assert.equal(ui.name.textContent, first.name);
  assert.equal(ui.remove.hidden, false);
  ui.input.files = [{ name: 'Replacement.webp' }];
  ui.input.listeners.change();
  assert.deepEqual(ui.revoked, ['blob:brand-1']);
  ui.windowEvents.pagehide();
  assert.deepEqual(ui.revoked, ['blob:brand-1', 'blob:brand-2']);
});

test('removing an edited logo marks server removal and can restore the saved preview', () => {
  const saved = '/admin/catalog/brand/7/logo/';
  const ui = editor(saved);
  assert.equal(ui.image.src, saved);
  ui.input.files = [{ name: 'Pending logo.png' }];
  ui.clear.checked = true;
  ui.input.listeners.change();
  assert.equal(ui.clear.checked, false);
  ui.remove.listeners.click();
  assert.equal(ui.clear.checked, true);
  assert.equal(ui.input.files.length, 0);
  assert.equal(ui.image.hidden, true);
  assert.equal(ui.empty.hidden, false);
  assert.match(ui.status.textContent, /removed when you save/);
  assert.deepEqual(ui.revoked, ['blob:brand-1']);
  ui.clear.checked = false;
  ui.clear.listeners.change();
  assert.equal(ui.image.src, saved);
  assert.equal(ui.image.hidden, false);
  assert.equal(ui.name.textContent, 'Current logo');
});
