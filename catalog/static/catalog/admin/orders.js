(() => {
  'use strict';
  const drawer = document.querySelector('#orders-drawer');
  if (!drawer) return;
  const content = document.querySelector('#orders-drawer-content');
  let trigger;
  let pending;
  let previousOverflow = '';
  async function openDetails(url, link) {
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    trigger = link;
    if (!drawer.open) {
      previousOverflow = document.body.style.overflow;
      drawer.showModal();
      document.body.style.overflow = 'hidden';
    }
    content.innerHTML = '<p class="orders-loading" role="status">Loading order details…</p>';
    try {
      const target = new URL(url, window.location.href);
      target.searchParams.set('panel', '1');
      const response = await fetch(target, { credentials: 'same-origin', signal: controller.signal });
      if (response.redirected) { window.location.assign(response.url); return; }
      if (!response.ok) throw Error('Unable to load this order. Close the panel and try again.');
      const html = await response.text();
      if (!controller.signal.aborted) content.innerHTML = html;
    } catch (error) {
      if (error.name !== 'AbortError') {
        const message = document.createElement('p');
        message.className = 'orders-loading';
        message.setAttribute('role', 'alert');
        message.textContent = error.message;
        content.replaceChildren(message);
      }
    }
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-order-detail]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    openDetails(link.href, link);
  });
  drawer.querySelector('[data-close-orders]').addEventListener('click', () => drawer.close());
  drawer.addEventListener('click', event => { if (event.target === drawer) drawer.close(); });
  drawer.addEventListener('close', () => {
    pending?.abort();
    content.replaceChildren();
    document.body.style.overflow = previousOverflow;
    trigger?.focus();
  });
  if (drawer.dataset.openUrl) openDetails(drawer.dataset.openUrl);
})();
