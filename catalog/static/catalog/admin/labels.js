(() => {
  'use strict';
  const form = document.querySelector('#label-settings-form');
  if (!form) return;
  const preview = form.querySelector('[data-label-preview]');
  const status = form.querySelector('[data-preview-status]');
  const editAddress = form.elements.correct_address;
  const addressFields = form.querySelector('[data-address-fields]');
  const itemList = form.querySelector('.label-item-list--scroll');
  let timer;
  let controller;

  function sizeItemList() {
    if (itemList) {
      const height = Array.from(itemList.children).slice(0, 8).reduce((sum, item) => sum + item.offsetHeight, 0);
      itemList.style.maxHeight = `${height + itemList.clientTop}px`;
    }
  }
  sizeItemList();
  window.addEventListener('resize', sizeItemList);
  document.fonts?.ready.then(sizeItemList);

  function toggleAddress() {
    if (!addressFields) return;
    addressFields.disabled = !editAddress.checked;
    addressFields.querySelectorAll('input').forEach(input => {
      input.disabled = !editAddress.checked;
      input.required = editAddress.checked && ['address', 'city'].includes(input.name);
    });
  }
  editAddress?.addEventListener('change', toggleAddress);
  toggleAddress();

  async function updatePreview() {
    controller?.abort();
    if (!form.checkValidity()) {
      status.textContent = 'Complete the required label fields to update the preview.';
      return;
    }
    const request = new AbortController();
    controller = request;
    const data = new FormData(form);
    data.set('action', 'preview');
    preview.setAttribute('aria-busy', 'true');
    status.textContent = 'Updating preview...';
    try {
      // The name="action" submit buttons shadow form.action in browsers.
      const response = await fetch(form.getAttribute('action') || window.location.href, {
        method: 'POST', body: data, credentials: 'same-origin', signal: request.signal,
      });
      if (response.redirected) throw new Error('Reload the page and sign in again to preview the label.');
      if (!response.ok) {
        const error = response.headers.get('Content-Type')?.includes('application/json') ? await response.json() : null;
        throw new Error(error?.error || 'Could not update the preview. Please try again.');
      }
      const html = await response.text();
      if (request.signal.aborted) return;
      preview.innerHTML = html;
      status.textContent = 'Preview updated. Save changes before opening or downloading the updated PDF.';
    } catch (error) {
      if (error.name !== 'AbortError') status.textContent = error.message;
    } finally {
      if (controller === request) preview.removeAttribute('aria-busy');
    }
  }

  form.addEventListener('input', event => {
    if (['radio', 'checkbox'].includes(event.target.type)) return;
    clearTimeout(timer);
    controller?.abort();
    timer = setTimeout(updatePreview, 300);
  });
  form.addEventListener('change', () => {
    clearTimeout(timer);
    updatePreview();
  });
})();
