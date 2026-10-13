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
  document.querySelectorAll(
    '#rtsb-container-973080080 .product-title a, '
    + '#rtsb-container-973080080 .rtsb-single-cat a, '
    + '#rtsb-container-973080080 .price-wrapper, '
    + '#rtsb-container-973080080 .homepage-stock, '
    + '#rtsb-container-882578271 .product-title a'
  ).forEach(element => {
    element.title = element.textContent.replace(/\s+/g, ' ').trim();
  });
  const bestSelling = document.querySelector('.elementor-element-9f402fa');
  const bestSellingHeading = document.querySelector('.elementor-element-7fe13bc');
  const trending = document.querySelector('.elementor-element-2744989');
  const trendingHeading = document.querySelector('.elementor-element-0756d00');
  if (bestSelling && bestSellingHeading && trending && trendingHeading) {
    const desktop = window.matchMedia('(min-width: 1025px)');
    function matchProductSectionHeights() {
      if (!desktop.matches) {
        bestSelling.style.removeProperty('--best-selling-height');
        return;
      }
      const height = trending.getBoundingClientRect().bottom
        - bestSellingHeading.getBoundingClientRect().top
        - bestSellingHeading.getBoundingClientRect().height;
      bestSelling.style.setProperty('--best-selling-height', `${Math.max(0, height)}px`);
    }
    const sectionObserver = new ResizeObserver(matchProductSectionHeights);
    [trending, trendingHeading, bestSellingHeading,
      document.querySelector('.elementor-element-bf7cf88'),
      document.querySelector('.elementor-element-dd67aff')
    ].filter(Boolean).forEach(element => sectionObserver.observe(element));
    desktop.addEventListener('change', matchProductSectionHeights);
    window.addEventListener('resize', matchProductSectionHeights);
    matchProductSectionHeights();
  }
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
      const matches = (!category || product.dataset.categoryId === String(category))
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

  document.querySelectorAll('.rtsb-filter-button-item:not(a)').forEach(button => {
    button.setAttribute('role', 'button');
    button.tabIndex = 0;
    button.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        button.click();
      }
    });
  });
  document.querySelectorAll('.rt-drop-menu [role="option"]').forEach(option => {
    option.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        option.click();
      }
    });
  });

  document.addEventListener('submit', event => {
    if (event.target.hasAttribute('data-shop-filters')) return;
    event.preventDefault();
    const search = event.target.querySelector('input[name="s"], input[name="q"]');
    if (search) {
      const category = event.target.querySelector('[name="category"], [name="product_cat"]')?.value || '';
      if (event.target.dataset.liveCatalogue) {
        const parameters = new URLSearchParams({ q: search.value.trim() });
        if (category) parameters.set('category', category);
        window.location.href = `${event.target.dataset.liveCatalogue}?${parameters}#products`;
        return;
      }
      filterProducts(category, search.value.trim());
    } else {
      showDialog('Store integration pending', 'This preview does not submit information. The form will be connected during dynamic integration.');
    }
  }, true);

  document.addEventListener('click', event => {
    const categoryToggle = event.target.closest('.cat-toggle');
    if (categoryToggle) {
      const menu = categoryToggle.closest('.dropdown').querySelector('.rt-drop-menu');
      const open = menu.classList.toggle('show');
      categoryToggle.setAttribute('aria-expanded', String(open));
      return;
    }
    const categoryOption = event.target.closest('.rt-drop-menu [data-slug]');
    if (categoryOption) {
      const dropdown = categoryOption.closest('.dropdown');
      dropdown.querySelector('[name="category"], [name="product_cat"]').value = categoryOption.dataset.slug;
      dropdown.querySelector('.cat-label').textContent = categoryOption.textContent;
      dropdown.querySelector('.rt-drop-menu').classList.remove('show');
      dropdown.querySelector('.cat-toggle').setAttribute('aria-expanded', 'false');
      return;
    }
    if (event.target.closest('.snapshot-dialog-close')) { dialog.close(); return; }
    const mobileToggle = event.target.closest('.sidebarBtn');
    if (mobileToggle) {
      const open = document.body.classList.toggle('snapshot-menu-open');
      mobileToggle.setAttribute('aria-expanded', String(open));
      return;
    }
    const filter = event.target.closest('.rtsb-filter-button-item');
    if (filter) {
      if (filter.hasAttribute('data-live-catalogue')) return;
      event.preventDefault();
      const group = filter.closest('.rtsb-filter-item-wrap');
      group.querySelectorAll('.selected').forEach(item => item.classList.remove('selected'));
      filter.classList.add('selected');
      const term = filter.dataset.term;
      filterProducts(term === 'all' ? '' : term);
      return;
    }
    const control = event.target.closest('a, button');
    if (!control || control.closest('#snapshot-dialog')) return;
    if (control.hasAttribute('data-live-catalogue') || control.hasAttribute('data-live-shop')) return;
    const href = control.getAttribute('href') || '';
    const classes = control.className || '';
    const product = control.closest('.rtsb-product, .shop-product');
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
    if (product && (control.hasAttribute('data-product-detail') || href.includes('/product/') || /quick-view|quickview/.test(classes))) {
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
        window.location.href = '/shop/';
      } else {
        showDialog(control.textContent.trim() || 'Store page', 'This destination will be connected when the static storefront becomes dynamic.');
      }
    }
  });

  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
})();
