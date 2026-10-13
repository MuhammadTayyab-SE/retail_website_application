(() => {
  'use strict';
  const form = document.querySelector('#shop-filters');
  document.querySelectorAll('[data-shop-submit]').forEach(control => {
    control.addEventListener('change', () => form.requestSubmit());
  });
  const toggle = document.querySelector('.product-filter-toggle');
  toggle?.addEventListener('click', () => {
    const open = toggle.closest('.rtsb-archive-filters').classList.toggle('shop-filters-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
})();
