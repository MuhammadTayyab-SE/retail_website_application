(() => {
  'use strict';
  const form = document.querySelector('#shop-filters');
  document.querySelectorAll('[data-shop-submit]').forEach(control => {
    control.addEventListener('change', () => form.requestSubmit());
  });
  const toggle = document.querySelector('.product-filter-toggle');
  const panel = document.querySelector('.rtsb-archive-filters');
  const originalParent = panel?.parentElement;
  const mobileHost = document.querySelector('#shop-mobile-filters');
  const smallScreen = window.matchMedia('(max-width: 1024px)');
  function placeFilters() {
    if (!panel || !originalParent || !mobileHost) return;
    (smallScreen.matches ? mobileHost : originalParent).append(panel);
    if (!smallScreen.matches) {
      if (mobileHost.open) mobileHost.close();
    }
  }
  document.body.classList.add('shop-responsive-filters');
  smallScreen.addEventListener('change', placeFilters);
  placeFilters();
  document.querySelector('#shop-mobile-query')?.addEventListener('input', event => {
    form.querySelector('[name="q"]').value = event.target.value;
  });
  toggle?.addEventListener('click', () => {
    mobileHost.showModal();
    document.body.classList.add('shop-drawer-open');
    toggle.setAttribute('aria-expanded', 'true');
  });
  mobileHost?.querySelector('.shop-drawer-close').addEventListener('click', () => mobileHost.close());
  mobileHost?.addEventListener('click', event => {
    if (event.target !== mobileHost) return;
    const bounds = mobileHost.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom) mobileHost.close();
  });
  mobileHost?.addEventListener('close', () => {
    document.body.classList.remove('shop-drawer-open');
    toggle?.setAttribute('aria-expanded', 'false');
  });
  form?.addEventListener('submit', () => { if (mobileHost?.open) mobileHost.close(); });
})();
