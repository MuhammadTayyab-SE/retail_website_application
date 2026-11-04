const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

test('format and color preview requests survive Save buttons named action', async () => {
  const url = 'http://localhost:8000/admin/orders/00000000-0000-0000-0000-000000000001/label/';
  const preview = { innerHTML: '', setAttribute() {}, removeAttribute() {} };
  const status = { textContent: '' };
  const requests = [];
  const form = {
    // Browsers expose the two name="action" buttons instead of the URL property.
    action: { toString: () => '[object RadioNodeList]' },
    values: { format: '4x6', palette: 'branded', csrfmiddlewaretoken: 'synthetic-token' },
    elements: {}, listeners: {}, checkValidity: () => true,
    getAttribute: () => null,
    querySelector: selector => ({ '[data-label-preview]': preview, '[data-preview-status]': status })[selector],
    addEventListener(type, callback) { this.listeners[type] = callback; },
  };
  class FormData extends Map {
    constructor(form) { super(Object.entries(form.values)); }
  }
  const runtime = {
    document: { querySelector: () => form },
    window: { location: { href: url }, addEventListener() {} },
    FormData, AbortController, setTimeout, clearTimeout,
    fetch: async (target, options) => {
      const destination = new URL(String(target), url).href;
      requests.push({ destination, data: options.body });
      return {
        ok: destination === url, redirected: false,
        headers: { get: () => 'text/html' },
        text: async () => `<article data-format="${options.body.get('format')}" data-palette="${options.body.get('palette')}"></article>`,
      };
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../catalog/static/catalog/admin/labels.js'), 'utf8'), runtime);
  assert.equal(requests.length, 0, 'opening the studio must not request a preview or download');
  for (const choice of [{ format: '4x4', palette: 'branded' }, { format: 'a4', palette: 'thermal' }]) {
    Object.assign(form.values, choice);
    form.listeners.change();
    await new Promise(resolve => setImmediate(resolve));
    const request = requests.at(-1);
    assert.equal(request.destination, url);
    assert.equal(request.data.get('action'), 'preview');
    assert.equal(request.data.get('csrfmiddlewaretoken'), 'synthetic-token');
    assert.match(preview.innerHTML, new RegExp(`data-format="${choice.format}"`));
    assert.match(preview.innerHTML, new RegExp(`data-palette="${choice.palette}"`));
    assert.match(status.textContent, /Preview updated/);
  }
});
