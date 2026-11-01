(() => {
  'use strict';
  const data = JSON.parse(document.querySelector('#product-data').textContent);
  const main = document.querySelector('#product-image');
  const thumbnails = document.querySelector('#product-thumbnails');
  const lightbox = document.querySelector('#product-lightbox');
  const enlarged = document.querySelector('#product-lightbox-image');
  let images = [];
  let index = 0;
  const money = value => `PKR ${Number(value).toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  function showImage(next) {
    index = images.length ? (next + images.length) % images.length : 0;
    const image = images[index];
    main.hidden = !image;
    document.querySelector('#product-no-image').hidden = !!image;
    document.querySelector('#product-zoom').disabled = !image;
    if (image) {
      main.src = enlarged.src = image.src;
      main.alt = enlarged.alt = image.alt;
    } else {
      main.removeAttribute('src');
      enlarged.removeAttribute('src');
    }
    const count = images.length ? `${index + 1} / ${images.length}` : 'No images';
    document.querySelector('#product-image-count').textContent = count;
    document.querySelector('#product-lightbox-count').textContent = count;
    document.querySelectorAll('[data-gallery-step]').forEach(button => { button.disabled = images.length < 2; });
    thumbnails.querySelectorAll('button').forEach((button, position) => {
      button.setAttribute('aria-pressed', String(position === index));
    });
  }

  function viewOption(id) {
    const option = data.options.find(item => item.id === id) || data.options[0];
    document.querySelector('#product-price').textContent = money(option.price);
    document.querySelector('#product-regular-price').textContent = money(option.regular_price);
    document.querySelector('#product-description').textContent = option.description || 'No description available.';
    document.querySelector('#product-sku').textContent = option.sku || '—';
    document.querySelectorAll('[data-variant]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.variant === option.id));
    });
    images = data.photos.filter(image => image.variant === option.id && image.variant);
    images.push(...data.photos.filter(image => !image.variant));
    thumbnails.replaceChildren();
    images.forEach((image, position) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-label', `View image ${position + 1}: ${image.alt}`);
      const thumbnail = document.createElement('img');
      thumbnail.src = image.src;
      thumbnail.alt = '';
      thumbnail.width = thumbnail.height = 80;
      button.append(thumbnail);
      button.addEventListener('click', () => showImage(position));
      thumbnails.append(button);
    });
    showImage(0);
    const url = new URL(window.location.href);
    if (option.id) url.searchParams.set('variant', option.id);
    else url.searchParams.delete('variant');
    history.replaceState(null, '', url);
  }

  function selection() {
    if (!data.stock) return [];
    const rows = [...document.querySelectorAll('[data-variant-row]')];
    if (!rows.length) return [{ option: data.options[0], input: document.querySelector('#product-quantity') }];
    return rows.filter(row => row.querySelector('input[type="checkbox"]').checked).map(row => ({
      option: data.options.find(option => option.id === row.dataset.variantRow),
      input: row.querySelector('input[type="number"]'),
    }));
  }

  function updateTotal() {
    const items = selection();
    const valid = items.length && items.every(item => item.input.checkValidity());
    const count = items.reduce((sum, item) => sum + Number(item.input.value), 0);
    const total = items.reduce((sum, item) => sum + Number(item.option.price) * Number(item.input.value), 0);
    const output = document.querySelector('#product-selection-total');
    output.textContent = !data.stock ? '' : !items.length ? 'Select an option' : !valid ? 'Enter a valid quantity' : count > data.stock ? `Only ${data.stock} units available in total` : `${count} item${count === 1 ? '' : 's'} · ${money(total)}`;
    document.querySelector('#product-add').disabled = !valid || count > data.stock;
  }
  document.querySelectorAll('[data-variant]').forEach(button => {
    button.addEventListener('click', () => viewOption(button.dataset.variant));
  });
  document.querySelectorAll('.product-variant-check').forEach(input => {
    input.addEventListener('change', () => { if (input.checked) viewOption(input.value); updateTotal(); });
  });
  document.querySelectorAll('.product-summary input[type="number"]').forEach(input => input.addEventListener('input', updateTotal));
  document.querySelectorAll('[data-gallery-step]').forEach(button => {
    button.addEventListener('click', () => showImage(index + Number(button.dataset.galleryStep)));
  });
  document.querySelector('#product-zoom').addEventListener('click', () => lightbox.showModal());
  document.querySelector('#product-lightbox-close').addEventListener('click', () => lightbox.close());
  lightbox.addEventListener('click', event => { if (event.target === lightbox) lightbox.close(); });
  document.querySelector('.product-gallery').addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault(); showImage(index + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  lightbox.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault(); showImage(index + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  document.querySelector('#product-add').addEventListener('click', () => {
    updateTotal();
    if (document.querySelector('#product-add').disabled) return;
    document.dispatchEvent(new CustomEvent('snapshot:add-items', { detail: selection().map(item => ({
      id: `live-${data.product}:${item.option.id}`, name: `${data.name}${item.option.id ? ` — ${item.option.label}` : ''}`,
      quantity: Number(item.input.value),
    })) }));
  });
  viewOption(data.selected);
  updateTotal();
})();
