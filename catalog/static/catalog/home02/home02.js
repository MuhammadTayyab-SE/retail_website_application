(() => {
  'use strict';
  const dialog = document.querySelector('#product-dialog');
  const dialogContent = document.querySelector('#dialog-content');
  const basket = new Map();
  const saved = new Set();
  const cards = [...document.querySelectorAll('.featured-grid .product-card')];
  let toastTimer;

  function notify(message) {
    const toast = document.querySelector('.toast');
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 2400);
  }

  function openDialog(title, message) {
    dialogContent.replaceChildren();
    const heading = document.createElement('h2');
    heading.id = 'dialog-title';
    heading.textContent = title;
    const paragraph = document.createElement('p');
    paragraph.textContent = message;
    const note = document.createElement('p');
    note.className = 'preview-note';
    note.textContent = 'Storefront design preview. Checkout, accounts and live store integration will be connected later.';
    dialogContent.append(heading, paragraph, note);
    dialog.showModal();
  }

  function filterProducts(category = '', query = '') {
    let count = 0;
    cards.forEach(card => {
      const visible = (!category || card.dataset.productCategory.toLowerCase() === category.toLowerCase())
        && card.dataset.productName.includes(query.toLowerCase());
      card.hidden = !visible;
      if (visible) count++;
    });
    document.querySelectorAll('[data-filter]').forEach(button => {
      button.classList.toggle('selected', button.dataset.filter === category);
    });
    const feedback = document.querySelector('#search-feedback');
    feedback.hidden = !category && !query;
    feedback.textContent = count ? `${count} products found${query ? ` for “${query}”` : ''}.` : 'No matching products. Try All or another search.';
  }

  document.querySelector('.header-search').addEventListener('submit', event => {
    event.preventDefault();
    filterProducts(document.querySelector('#search-category').value, document.querySelector('#product-search').value.trim());
    document.querySelector('#featured').scrollIntoView({ behavior: 'smooth' });
  });

  document.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.matches('.dialog-close')) dialog.close();
    if (button.matches('[data-filter], [data-category]')) {
      const category = button.dataset.filter ?? button.dataset.category;
      filterProducts(category);
      document.querySelector('#search-category').value = category;
      document.querySelector('#product-search').value = '';
      document.querySelector('#featured').scrollIntoView({ behavior: 'smooth' });
    }
    if (button.matches('[data-slide]')) {
      const grid = document.querySelector('.featured-grid');
      const visible = [...grid.children].filter(card => !card.hidden);
      if (visible.length > 1) {
        if (button.dataset.slide === '1') grid.append(visible[0]);
        else grid.prepend(visible.at(-1));
      }
    }
    if (button.matches('[data-like]')) {
      const id = button.dataset.like;
      if (saved.has(id)) saved.delete(id); else saved.add(id);
      document.querySelectorAll(`[data-like="${id}"]`).forEach(item => {
        item.setAttribute('aria-pressed', String(saved.has(id)));
        item.textContent = saved.has(id) ? '♥' : '♡';
      });
      document.querySelector('#wishlist-count').textContent = saved.size;
    }
    if (button.matches('[data-add]')) {
      const id = button.dataset.add;
      const name = button.closest('.product-card').querySelector('h3').textContent.trim();
      const item = basket.get(id) || { name, quantity: 0 };
      item.quantity++;
      basket.set(id, item);
      document.querySelector('#cart-count').textContent = [...basket.values()].reduce((sum, entry) => sum + entry.quantity, 0);
      notify('Added to preview basket');
    }
    if (button.matches('[data-cart]')) {
      openDialog('Your basket', basket.size ? [...basket.values()].map(item => `${item.name} × ${item.quantity}`).join('\n\n') : 'Your basket is empty. Explore the featured products to get started.');
    }
    if (button.matches('[data-wishlist]')) {
      const names = cards.filter(card => saved.has(card.dataset.productId)).map(card => card.querySelector('h3').textContent.trim());
      openDialog('Your wishlist', names.length ? names.join('\n\n') : 'Save your favourites with the heart on each product.');
    }
    if (button.matches('[data-product-detail]')) {
      const card = button.closest('.product-card');
      openDialog(card.querySelector('h3').textContent.trim(), `${card.querySelector('.product-price').textContent} · ${card.dataset.productCategory}`);
      dialogContent.querySelector('h2').after(card.querySelector('.product-image img').cloneNode());
    }
    if (button.matches('[data-preview]')) openDialog(button.dataset.preview, 'This destination will be available when the store integration is added.');
    if (button.matches('.menu-toggle')) {
      const expanded = document.querySelector('.main-nav').classList.toggle('expanded');
      button.setAttribute('aria-expanded', String(expanded));
      if (expanded) document.querySelector('.main-nav summary').focus();
    }
  });

  document.querySelector('.newsletter').addEventListener('submit', event => {
    event.preventDefault();
    openDialog('Newsletter', 'Newsletter subscription will be enabled with the store integration. Your email has not been submitted.');
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
})();
