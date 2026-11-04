(() => {
  'use strict';
  document.querySelectorAll('[data-brand-editor]').forEach(editor => {
    const input = editor.querySelector('input[type="file"]');
    if (!input) return;
    const image = editor.querySelector('[data-brand-image]');
    const empty = editor.querySelector('[data-brand-image-empty]');
    const name = editor.querySelector('[data-brand-image-name]');
    const status = editor.querySelector('[data-brand-image-status]');
    const remove = editor.querySelector('[data-brand-image-remove]');
    const clear = editor.querySelector('input[name$="-clear"]');
    const original = image.getAttribute('src') || '';
    let objectUrl;
    function release() {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
    function update() {
      release();
      const file = input.files[0];
      const removed = clear?.checked;
      const source = removed ? '' : file ? (objectUrl = URL.createObjectURL(file)) : original;
      if (source) image.src = source;
      else image.removeAttribute('src');
      image.hidden = !source;
      empty.hidden = Boolean(source);
      remove.hidden = !source;
      name.textContent = file && !removed ? file.name : original && !removed ? 'Current logo' : 'Logo preview';
      status.textContent = removed ? 'Logo will be removed when you save.' : file ? 'Selected photo preview. Save changes to upload it.' : 'Select a photo to preview it before saving.';
    }
    input.addEventListener('change', () => {
      if (input.files.length && clear) clear.checked = false;
      update();
    });
    clear?.addEventListener('change', () => {
      if (clear.checked) input.value = '';
      update();
    });
    remove.addEventListener('click', () => {
      input.value = '';
      if (clear) clear.checked = Boolean(original);
      update();
    });
    input.closest('form')?.addEventListener('reset', () => queueMicrotask(update));
    window.addEventListener('pagehide', release);
  });
})();
