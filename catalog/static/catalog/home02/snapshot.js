/* Local interactions for the captured UI. No WordPress/AJAX services run here. */
(() => {
  'use strict';
  const dialog = document.querySelector('#snapshot-dialog');
  const title = document.querySelector('#snapshot-dialog-title');
  const message = document.querySelector('#snapshot-dialog-message');
  const basket = new Map();
  const favourites = new Map();
  const comparisons = new Map();
  let statusTimer;

  const cartDrawer = document.querySelector('#homepage-cart-drawer');
  const floatingCart = document.querySelector('.rtsb-cart-float-inner');
  let previousBodyOverflow;
  const formatCartPrice = cents => `PKR ${(cents / 100).toFixed(2)}`;
  function cartPriceCents(value) {
    if (!/^\d+(\.\d{1,2})?$/.test(value || '')) return null;
    const [whole, fraction = ''] = value.split('.');
    const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    return Number.isSafeInteger(cents) ? cents : null;
  }
  function renderCartDrawer() {
    if (!cartDrawer) return;
    const empty = basket.size === 0;
    cartDrawer.querySelector('.homepage-cart-empty').hidden = !empty;
    const list = cartDrawer.querySelector('.homepage-cart-items');
    list.hidden = empty;
    list.replaceChildren();
    let total = 0;
    let pricesKnown = true;
    basket.forEach((item, id) => {
      const row = document.createElement('li');
      row.className = 'homepage-cart-item';
      row.dataset.cartId = id;
      if (item.image) {
        const image = document.createElement('img');
        image.src = item.image;
        image.alt = item.name;
        image.width = 72;
        image.height = 88;
        image.className = 'homepage-cart-item-image';
        row.append(image);
      } else {
        const placeholder = document.createElement('span');
        placeholder.className = 'homepage-cart-item-image-missing';
        placeholder.textContent = 'No photo';
        row.append(placeholder);
      }
      const details = document.createElement('div');
      details.className = 'homepage-cart-item-details';
      const name = document.createElement('h3');
      name.textContent = item.name;
      details.append(name);
      if (item.description) {
        const description = document.createElement('p');
        description.className = 'homepage-cart-item-description';
        description.textContent = item.description;
        description.title = item.description;
        details.append(description);
      }
      const prices = document.createElement('div');
      prices.className = 'homepage-cart-item-prices';
      const unitPrice = item.salePrice ?? item.price;
      if (item.salePrice != null && item.price != null) {
        const regular = document.createElement('del');
        regular.textContent = formatCartPrice(item.price);
        prices.append(regular);
      }
      const current = document.createElement('strong');
      current.textContent = unitPrice == null ? 'Price unavailable' : formatCartPrice(unitPrice);
      prices.append(current);
      details.append(prices);
      if (unitPrice == null || !Number.isSafeInteger(total + unitPrice * item.quantity)) pricesKnown = false;
      else total += unitPrice * item.quantity;
      const controls = document.createElement('div');
      controls.className = 'homepage-cart-item-controls';
      for (const action of ['decrease', 'increase', 'remove']) {
        const button = document.createElement('button');
        button.type = 'button';
        button.dataset.cartAction = action;
        button.setAttribute('aria-label', `${action === 'remove' ? 'Remove' : action === 'increase' ? 'Increase quantity of' : 'Decrease quantity of'} ${item.name}`);
        button.textContent = action === 'remove' ? 'Remove' : action === 'increase' ? '+' : '−';
        button.disabled = (action === 'decrease' && item.quantity <= 1)
          || (action === 'increase' && item.quantity >= item.stock);
        controls.append(button);
        if (action === 'decrease') {
          const quantity = document.createElement('span');
          quantity.className = 'homepage-cart-item-quantity';
          quantity.textContent = String(item.quantity);
          quantity.setAttribute('aria-label', `Quantity: ${item.quantity}`);
          controls.append(quantity);
        }
      }
      details.append(controls);
      row.append(details);
      list.append(row);
    });
    document.querySelectorAll('.rtsb-cart-icon-num').forEach(counter => {
      counter.textContent = [...basket.values()].reduce((sum, item) => sum + item.quantity, 0);
    });
    cartDrawer.querySelector('.homepage-cart-clear').disabled = empty;
    cartDrawer.querySelectorAll('[data-cart-subtotal], [data-cart-total]').forEach(amount => {
      amount.textContent = pricesKnown ? formatCartPrice(total) : 'Not calculated';
    });
  }
  if (cartDrawer && floatingCart) {
    floatingCart.addEventListener('click', () => {
      if (cartDrawer.open) return;
      renderCartDrawer();
      previousBodyOverflow = document.body.style.overflow;
      cartDrawer.showModal();
      document.body.style.overflow = 'hidden';
      floatingCart.setAttribute('aria-expanded', 'true');
      cartDrawer.querySelector('.homepage-cart-close').focus();
    });
    floatingCart.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        floatingCart.click();
      }
    });
    cartDrawer.querySelector('.homepage-cart-close').addEventListener('click', () => cartDrawer.close());
    cartDrawer.querySelector('.homepage-cart-items').addEventListener('click', event => {
      const button = event.target.closest('[data-cart-action]');
      if (!button || button.disabled) return;
      const id = button.closest('[data-cart-id]').dataset.cartId;
      const item = basket.get(id);
      if (!item) return;
      const action = button.dataset.cartAction;
      if (action === 'remove') basket.delete(id);
      else if (action === 'increase' && item.quantity < (item.stock ?? Number.MAX_SAFE_INTEGER)) item.quantity++;
      else if (action === 'decrease' && item.quantity > 1) item.quantity--;
      renderCartDrawer();
      const list = cartDrawer.querySelector('.homepage-cart-items');
      const updated = [...list.children].find(row => row.dataset.cartId === id);
      const focusTarget = updated?.querySelector(`[data-cart-action="${action}"]`);
      if (focusTarget && !focusTarget.disabled) focusTarget.focus();
      else if (updated) updated.querySelector('[data-cart-action="remove"]').focus();
      else if (list.children.length) list.children[0].querySelector('[data-cart-action="remove"]').focus();
      else cartDrawer.querySelector('.homepage-cart-shopping').focus();
      status(action === 'remove' ? 'Product removed from preview basket' : 'Preview basket quantity updated');
    });
    cartDrawer.addEventListener('click', event => {
      if (event.target !== cartDrawer) return;
      const bounds = cartDrawer.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom) cartDrawer.close();
    });
    cartDrawer.addEventListener('close', () => {
      document.body.style.overflow = previousBodyOverflow;
      floatingCart.setAttribute('aria-expanded', 'false');
      floatingCart.focus();
    });
    cartDrawer.querySelector('.homepage-cart-clear').addEventListener('click', () => {
      basket.clear();
      document.querySelectorAll('.rtsb-cart-icon-num').forEach(counter => { counter.textContent = '0'; });
      renderCartDrawer();
      cartDrawer.querySelector('.homepage-cart-shopping').focus();
      status('Preview basket cleared');
    });
  }

  const heroSlider = document.querySelector('#homepage-hero-slider');
  if (heroSlider && window.Swiper && heroSlider.querySelectorAll('.swiper-slide').length > 1) {
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let heroVisible = false;
    let heroHovered = false;
    const hero = new window.Swiper(heroSlider, {
      slidesPerView: 1,
      loop: true,
      speed: motionPreference.matches ? 0 : 650,
      autoplay: motionPreference.matches ? false : { delay: 6000, disableOnInteraction: false },
      navigation: { prevEl: heroSlider.querySelector('.homepage-hero-prev'), nextEl: heroSlider.querySelector('.homepage-hero-next') },
      pagination: { el: heroSlider.querySelector('.homepage-hero-pagination'), clickable: true },
      a11y: { enabled: true, prevSlideMessage: 'Previous promotion', nextSlideMessage: 'Next promotion' },
    });
    function updateHeroAutoplay() {
      hero.params.speed = motionPreference.matches ? 0 : 650;
      if (motionPreference.matches || document.hidden || !heroVisible || heroHovered || heroSlider.matches(':focus-within')) {
        hero.autoplay.stop();
      } else {
        hero.params.autoplay = { delay: 6000, disableOnInteraction: false };
        hero.autoplay.start();
      }
    }
    heroSlider.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse') return;
      heroHovered = true;
      updateHeroAutoplay();
    });
    heroSlider.addEventListener('pointerleave', () => { heroHovered = false; updateHeroAutoplay(); });
    heroSlider.addEventListener('focusin', updateHeroAutoplay);
    heroSlider.addEventListener('focusout', () => setTimeout(updateHeroAutoplay, 0));
    document.addEventListener('visibilitychange', updateHeroAutoplay);
    motionPreference.addEventListener('change', updateHeroAutoplay);
    new IntersectionObserver(entries => {
      heroVisible = entries[0].isIntersecting;
      updateHeroAutoplay();
    }).observe(heroSlider);
    updateHeroAutoplay();
  }

  const categoryTrack = document.querySelector('#homepage-category-track');
  if (categoryTrack) {
    const previous = document.querySelector('.homepage-category-arrow-prev');
    const next = document.querySelector('.homepage-category-arrow-next');
    const categoryPanel = categoryTrack.parentElement;
    const mobileCategories = window.matchMedia('(max-width: 1024px)');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let categoryTimer;
    let categoryHovered = false;
    let categoryDragging = false;
    let categoryVisible = false;
    function updateCategoryArrows() {
      previous.disabled = categoryTrack.scrollLeft <= 2;
      next.disabled = categoryTrack.scrollLeft + categoryTrack.clientWidth >= categoryTrack.scrollWidth - 2;
    }
    function moveCategories(direction) {
      const card = [...categoryTrack.querySelectorAll('.rtsb-category-grid')]
        .find(item => item.getClientRects().length);
      if (!card) return;
      const gap = parseFloat(getComputedStyle(categoryTrack).columnGap) || 0;
      categoryTrack.scrollBy({
        left: direction * (card.getBoundingClientRect().width + gap),
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      });
    }
    function scheduleCategoryAdvance() {
      clearTimeout(categoryTimer);
      if (!mobileCategories.matches || reducedMotion.matches || document.hidden || !categoryVisible
        || categoryHovered || categoryDragging || categoryPanel.matches(':focus-within')
        || categoryTrack.scrollWidth <= categoryTrack.clientWidth + 2) return;
      categoryTimer = setTimeout(() => {
        if (next.disabled) categoryTrack.scrollTo({ left: 0, behavior: 'smooth' });
        else moveCategories(1);
        scheduleCategoryAdvance();
      }, 6000);
    }
    categoryPanel.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse') return;
      categoryHovered = true;
      scheduleCategoryAdvance();
    });
    categoryPanel.addEventListener('pointerleave', () => {
      categoryHovered = false;
      scheduleCategoryAdvance();
    });
    categoryPanel.addEventListener('pointerdown', () => {
      categoryDragging = true;
      scheduleCategoryAdvance();
    });
    ['pointerup', 'pointercancel'].forEach(name => window.addEventListener(name, () => {
      if (!categoryDragging) return;
      categoryDragging = false;
      scheduleCategoryAdvance();
    }));
    categoryPanel.addEventListener('focusin', scheduleCategoryAdvance);
    categoryPanel.addEventListener('focusout', () => setTimeout(scheduleCategoryAdvance, 0));
    document.addEventListener('visibilitychange', scheduleCategoryAdvance);
    mobileCategories.addEventListener('change', scheduleCategoryAdvance);
    reducedMotion.addEventListener('change', scheduleCategoryAdvance);
    new IntersectionObserver(entries => {
      categoryVisible = entries[0].isIntersecting;
      scheduleCategoryAdvance();
    }).observe(categoryTrack);
    previous.addEventListener('click', () => moveCategories(-1));
    next.addEventListener('click', () => moveCategories(1));
    categoryTrack.addEventListener('scroll', updateCategoryArrows, { passive: true });
    categoryTrack.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        moveCategories(event.key === 'ArrowLeft' ? -1 : 1);
      }
    });
    new ResizeObserver(() => {
      updateCategoryArrows();
      scheduleCategoryAdvance();
    }).observe(categoryTrack);
    updateCategoryArrows();
  }

  document.addEventListener('snapshot:add-items', event => {
    event.detail.forEach(item => {
      const entry = basket.get(item.id) || { ...item, quantity: 0 };
      entry.quantity += item.quantity;
      basket.set(item.id, entry);
    });
    document.querySelectorAll('.rtsb-cart-icon-num').forEach(counter => {
      counter.textContent = [...basket.values()].reduce((sum, item) => sum + item.quantity, 0);
    });
    if (cartDrawer?.open) renderCartDrawer();
    status('Selected options added to preview basket');
  });

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
  document.querySelectorAll('.rtsb-products-container .price-wrapper').forEach(host => {
    if (host.querySelector('.retail-price-line') || !host.querySelector('.rtsb-promotion')) return;
    const line = document.createElement('div');
    line.className = 'retail-price-line';
    line.append(...host.childNodes);
    host.append(line);
  });
  const priceLines = [...document.querySelectorAll('.retail-price-line')];
  function fitPriceLine(line) {
    // Measure the unwrapped group before choosing the two-line sale layout.
    line.classList.remove('retail-price-wrap');
    const available = line.parentElement.clientWidth;
    const natural = line.offsetWidth;
    if (!document.body.classList.contains('page-id-178')) {
      if (available > 0 && natural > 0) {
        line.style.setProperty('--retail-price-scale', Math.min(1, available / natural));
      }
      return;
    }
    line.classList.toggle('retail-price-wrap', available > 0 && natural > available
      && !!line.querySelector('.rtsb-promotion'));
  }
  const priceObserver = new ResizeObserver(entries => {
    entries.forEach(entry => {
      const line = entry.target.querySelector('.retail-price-line');
      if (line) fitPriceLine(line);
    });
  });
  priceLines.forEach(line => {
    line.parentElement.classList.add('retail-price-host');
    priceObserver.observe(line.parentElement);
    fitPriceLine(line);
  });
  document.fonts.ready.then(() => priceLines.forEach(fitPriceLine));
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

  function closeCategoryMenus(except = null) {
    document.querySelectorAll('.category-search-dropdown-js .dropdown').forEach(dropdown => {
      if (dropdown === except) return;
      dropdown.querySelector('.rt-drop-menu')?.classList.remove('show');
      dropdown.querySelector('.cat-toggle')?.setAttribute('aria-expanded', 'false');
    });
  }
  document.addEventListener('keydown', event => {
    const dropdown = event.target.closest('.category-search-dropdown-js .dropdown');
    if (!dropdown) return;
    if (event.key === 'Escape') {
      closeCategoryMenus();
      dropdown.querySelector('.cat-toggle').focus();
    } else if (event.key === 'ArrowDown' && event.target.closest('.cat-toggle')) {
      event.preventDefault();
      if (event.target.closest('.cat-toggle').getAttribute('aria-expanded') !== 'true') {
        event.target.closest('.cat-toggle').click();
      }
      dropdown.querySelector('[role="option"]')?.focus();
    } else if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[role="option"]')) {
      event.preventDefault();
      event.target.click();
    }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.category-search-dropdown-js .dropdown')) closeCategoryMenus();
    const categoryToggle = event.target.closest('.cat-toggle');
    if (categoryToggle) {
      const dropdown = categoryToggle.closest('.dropdown');
      closeCategoryMenus(dropdown);
      const menu = dropdown.querySelector('.rt-drop-menu');
      const open = menu.classList.toggle('show');
      categoryToggle.setAttribute('aria-expanded', String(open));
      return;
    }
    const categoryOption = event.target.closest('.rt-drop-menu [data-slug]');
    if (categoryOption) {
      const dropdown = categoryOption.closest('.dropdown');
      dropdown.querySelector('[name="category"], [name="product_cat"]').value = categoryOption.dataset.slug;
      const label = categoryOption.textContent.trim();
      dropdown.querySelector('.cat-label').textContent = label;
      dropdown.querySelector('.cat-label').title = label;
      dropdown.querySelector('.rt-drop-menu').classList.remove('show');
      dropdown.querySelector('.cat-toggle').setAttribute('aria-expanded', 'false');
      dropdown.querySelector('.cat-toggle').focus();
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
    if (!control || control.closest('#snapshot-dialog, #homepage-cart-drawer')) return;
    if (control.closest('.product-page, #product-lightbox')) return;
    if (control.hasAttribute('data-product-page')) return;
    if (control.hasAttribute('data-live-catalogue') || control.hasAttribute('data-live-shop')) return;
    const href = control.getAttribute('href') || '';
    const classes = control.className || '';
    const product = control.closest('.rtsb-product, .shop-product');
    const productTitle = product?.querySelector('.product-title')?.textContent.trim() || 'Product';
    const id = product?.dataset.id || productTitle;

    if (/add_to_cart|add-to-cart/.test(classes + href)) {
      event.preventDefault();
      const data = control.closest('.homepage-card-actions')?.dataset;
      const entry = basket.get(id) || {
        name: productTitle, quantity: 0,
        description: data?.cartDescription || '',
        image: product?.querySelector('.homepage-featured-photo img, .rtsb-product-image, .rtsb-product-img img')?.src || '',
        price: cartPriceCents(data?.cartPrice),
        salePrice: cartPriceCents(data?.cartSalePrice),
        stock: data?.cartStock ? Number(data.cartStock) : Number.MAX_SAFE_INTEGER,
      };
      if (entry.quantity >= entry.stock) {
        status('Available stock limit reached');
        return;
      }
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
    if (product && control.classList.contains('rtsb-compare-btn')) {
      event.preventDefault();
      comparisons.set(id, `${productTitle}\n${product.querySelector('.product-price')?.textContent.trim() || ''}`);
      showDialog('Compare products', [...comparisons.values()].join('\n\n'));
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
        window.location.href = '/';
      } else if (/\/shop\//.test(href)) {
        window.location.href = '/shop/';
      } else {
        showDialog(control.textContent.trim() || 'Store page', 'This destination will be connected when the static storefront becomes dynamic.');
      }
    }
  });

  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
})();
