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
      mobileHost.classList.remove('shop-filters-open');
      toggle?.setAttribute('aria-expanded', 'false');
    }
  }
  document.body.classList.add('shop-responsive-filters');
  smallScreen.addEventListener('change', placeFilters);
  placeFilters();
  document.querySelector('#shop-mobile-query')?.addEventListener('input', event => {
    form.querySelector('[name="q"]').value = event.target.value;
  });
  toggle?.addEventListener('click', () => {
    const open = mobileHost.classList.toggle('shop-filters-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
})();
