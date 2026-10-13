/* Local interactions for the captured UI. No WordPress/AJAX services run here. */
(() => {
  'use strict';
  const dialog = document.querySelector('#snapshot-dialog');
  const title = document.querySelector('#snapshot-dialog-title');
  const message = document.querySelector('#snapshot-dialog-message');
  const basket = new Map();
  const favourites = new Map();
  let statusTimer;

  function showDialog(heading, description) {
    title.textContent = heading;
    message.textContent = description;
    dialog.querySelectorAll('.snapshot-product-image').forEach(image => image.remove());
    if (!dialog.open) dialog.showModal();
  }

  function status(text) {
    const output = document.querySelector('#snapshot-status');
    output.textContent = text;
    output.hidden = false;
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => { output.hidden = true; }, 2500);
  }

  document.querySelectorAll('.rtsb-carousel-slider').forEach(element => {
    const options = JSON.parse(element.dataset.options || '{}');
    const widget = element.closest('.rtsb-elementor-container');
    options.navigation = {
      nextEl: widget.querySelector('.swiper-button-next'),
      prevEl: widget.querySelector('.swiper-button-prev'),
    };
    options.a11y = { enabled: true };
    if (window.Swiper) {
      new window.Swiper(element, options);
      element.classList.add('rtsb-swiper-initialized');
    }
    element.classList.remove('slider-loading');
  });

  document.querySelectorAll('.elementor-invisible').forEach(element => {
    element.classList.remove('elementor-invisible');
  });
  document.body.classList.replace('woocommerce-no-js', 'woocommerce-js');
  document.querySelectorAll('.rtsb-cart-icon-num').forEach(counter => {
    counter.textContent = '0';
  });
  document.querySelectorAll('.sidebarBtn').forEach(toggle => {
    toggle.setAttribute('role', 'button');
    toggle.setAttribute('tabindex', '0');
    toggle.setAttribute('aria-label', 'Toggle mobile navigation');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggle.click();
      }
    });
  });

  function filterProducts(category, query = '') {
    const widget = document.querySelector('[data-layout="zilly-slider-layout1"]');
    if (!widget) return;
    let shown = 0;
    widget.querySelectorAll('.rtsb-product').forEach(product => {
      const name = product.querySelector('.product-title')?.textContent.toLowerCase() || '';
      const matches = (!category || product.classList.contains(`product_cat-${category}`))
        && name.includes(query.toLowerCase());
      product.toggleAttribute('data-snapshot-hidden', !matches);
      if (matches) shown++;
    });
    const slider = widget.querySelector('.rtsb-carousel-slider');
    slider?.swiper?.update();
    slider?.swiper?.slideTo(0, 0);
    widget.scrollIntoView({ behavior: 'smooth', block: 'start' });
    status(shown ? `${shown} matching products` : 'No matching preview products. Select All to reset.');
  }

  document.querySelectorAll('.rtsb-filter-button-item').forEach(button => {
    button.setAttribute('role', 'button');
    button.tabIndex = 0;
    button.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        button.click();
      }
    });
  });

  document.addEventListener('submit', event => {
    event.preventDefault();
    const search = event.target.querySelector('input[name="s"]');
    if (search) {
      const category = event.target.querySelector('select[name="product_cat"]')?.value || '';
      filterProducts(category, search.value.trim());
    } else {
      showDialog('Store integration pending', 'This preview does not submit information. The form will be connected during dynamic integration.');
    }
  }, true);

  document.addEventListener('click', event => {
    if (event.target.closest('.snapshot-dialog-close')) { dialog.close(); return; }
    const mobileToggle = event.target.closest('.sidebarBtn');
    if (mobileToggle) {
      const open = document.body.classList.toggle('snapshot-menu-open');
      mobileToggle.setAttribute('aria-expanded', String(open));
      return;
    }
    const filter = event.target.closest('.rtsb-filter-button-item');
    if (filter) {
      event.preventDefault();
      const group = filter.closest('.rtsb-filter-item-wrap');
      group.querySelectorAll('.selected').forEach(item => item.classList.remove('selected'));
      filter.classList.add('selected');
      const term = filter.dataset.term;
      filterProducts(term === 'all' ? '' : term === '17' ? 'desserts' : 'beverage');
      return;
    }
    const control = event.target.closest('a, button');
    if (!control || control.closest('#snapshot-dialog')) return;
    const href = control.getAttribute('href') || '';
    const classes = control.className || '';
    const product = control.closest('.rtsb-product');
    const productTitle = product?.querySelector('.product-title')?.textContent.trim() || 'Product';
    const id = product?.dataset.id || productTitle;

    if (/add_to_cart|add-to-cart/.test(classes + href)) {
      event.preventDefault();
      const entry = basket.get(id) || { name: productTitle, quantity: 0 };
      entry.quantity++;
      basket.set(id, entry);
      document.querySelectorAll('.rtsb-cart-icon-num').forEach(counter => {
        counter.textContent = [...basket.values()].reduce((sum, item) => sum + item.quantity, 0);
      });
      status('Added to preview basket');
      return;
    }
    if (product && /wishlist/.test(classes)) {
      event.preventDefault();
      if (favourites.has(id)) favourites.delete(id); else favourites.set(id, productTitle);
      control.setAttribute('aria-pressed', String(favourites.has(id)));
      document.querySelectorAll('.rtsb-wishlist-counter').forEach(counter => { counter.textContent = favourites.size; });
      status(favourites.has(id) ? 'Added to wishlist' : 'Removed from wishlist');
      return;
    }
    if (/cart-icon|cart-float/.test(classes) || /\/cart\//.test(href)) {
      event.preventDefault();
      showDialog('Your basket', basket.size ? [...basket.values()].map(item => `${item.name} × ${item.quantity}`).join('\n\n') : 'Your basket is empty.');
      return;
    }
    if (/\/wishlist\//.test(href)) {
      event.preventDefault();
      showDialog('Your wishlist', favourites.size ? [...favourites.values()].join('\n\n') : 'Your wishlist is empty.');
      return;
    }
    if (/menu-trigger|meanmenu-reveal|sidebar-toggle/.test(classes)) {
      event.preventDefault();
      document.body.classList.toggle('snapshot-menu-open');
      const canvas = document.querySelector('.sidenav.sidecanvas');
      if (canvas) canvas.classList.toggle('open');
      return;
    }
    if (href.includes('/product-category/')) {
      event.preventDefault();
      filterProducts(href.split('/product-category/')[1].split('/')[0]);
      return;
    }
    if (product && (href.includes('/product/') || /quick-view|quickview/.test(classes))) {
      event.preventDefault();
      showDialog(productTitle, product.querySelector('.product-price')?.textContent.trim() || 'Product preview');
      const image = product.querySelector('.rtsb-product-image');
      if (image) {
        const preview = image.cloneNode();
        preview.className = 'snapshot-product-image';
        preview.removeAttribute('srcset');
        title.after(preview);
      }
      return;
    }
    if (href === '#' || href.startsWith('javascript:')) {
      event.preventDefault();
      return;
    }
    if (href && !href.startsWith('#')) {
      event.preventDefault();
      if (/home-02\/index.html$/.test(href) || href === '../index.html') {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else if (/\/shop\//.test(href)) {
        document.querySelector('[data-layout="zilly-slider-layout1"]')?.scrollIntoView({ behavior: 'smooth' });
      } else {
        showDialog(control.textContent.trim() || 'Store page', 'This destination will be connected when the static storefront becomes dynamic.');
      }
    }
  });

  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
})();
