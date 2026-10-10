(() => {
  const input = document.getElementById('id_photo');
  const image = document.querySelector('[data-photo-image]');
  if (!input || !image) return;
  const empty = document.querySelector('[data-photo-empty]');
  const status = document.querySelector('[data-photo-status]');
  const clear = document.getElementById('photo-clear_id');
  const x = document.getElementById('id_photo_x');
  const y = document.getElementById('id_photo_y');
  const zoom = document.getElementById('id_photo_zoom');
  const original = image.getAttribute('src') || '';
  let previewURL = '';
  function adjust() {
    image.style.objectPosition = `${x.value}% ${y.value}%`;
    image.style.transform = `scale(${zoom.value / 100})`;
  }
  function show(url) {
    image.hidden = !url;
    empty.hidden = Boolean(url);
    if (url) image.src = url;
    else image.removeAttribute('src');
    adjust();
  }
  input.addEventListener('change', () => {
    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = '';
    const file = input.files[0];
    status.textContent = '';
    if (!file) { show(clear && clear.checked ? '' : original); return; }
    if (file.size > 8 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      input.value = '';
      status.textContent = 'Choose a JPEG, PNG or WebP photo up to 8 MB.';
      show(clear && clear.checked ? '' : original);
      return;
    }
    if (clear) clear.checked = false;
    x.value = y.value = 50;
    zoom.value = 100;
    previewURL = URL.createObjectURL(file);
    show(previewURL);
    status.textContent = 'Photo ready. Save the category to keep your changes.';
  });
  if (clear) clear.addEventListener('change', () => {
    if (clear.checked) { input.value = ''; show(''); }
    else show(original);
    status.textContent = clear.checked ? 'Photo will be removed when you save.' : '';
  });
  document.querySelector('[data-photo-remove]').addEventListener('click', () => {
    input.value = '';
    if (clear) clear.checked = true;
    show('');
    status.textContent = 'Photo will be removed when you save.';
  });
  [x, y, zoom].forEach(control => control.addEventListener('input', adjust));
  document.querySelector('[data-photo-reset]').addEventListener('click', () => {
    x.value = y.value = 50; zoom.value = 100; adjust();
  });
  window.addEventListener('pagehide', () => { if (previewURL) URL.revokeObjectURL(previewURL); });
  adjust();
})();
