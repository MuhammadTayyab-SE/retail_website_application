(() => {
  'use strict';
  const filters = document.querySelector('[data-order-filters]');
  if (filters) {
    const selection = filters.elements.date_mode;
    function updateDateFields() {
      const single = selection.value === 'single';
      filters.querySelectorAll('[data-date-range], [data-single-date]').forEach(group => {
        const visible = group.hasAttribute('data-single-date') === single;
        group.hidden = !visible;
        group.querySelectorAll('input').forEach(input => { input.disabled = !visible; });
      });
    }
    selection.addEventListener('change', updateDateFields);
    updateDateFields();
  }
  document.querySelector('#orders-print')?.addEventListener('click', () => window.print());
})();
