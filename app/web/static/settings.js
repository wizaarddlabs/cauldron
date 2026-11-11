// settings.js: provider/key field, pill and dropdown state, sort list, form checks.
document.addEventListener('DOMContentLoaded', function () {
  // Selected look for pills (CSS :has() covers modern browsers; this covers the rest).
  document.querySelectorAll('.pill input[type="checkbox"]').forEach(function (cb) {
    const pill = cb.closest('.pill');
    const update = () => pill.classList.toggle('selected', cb.checked);
    cb.addEventListener('change', update);
    update();
  });

  // Language dropdowns: summarise the selection in the toggle.
  document.querySelectorAll('.dropdown').forEach(function (dropdown) {
    const toggle = dropdown.querySelector('.dropdown-toggle');
    const inputs = Array.from(dropdown.querySelectorAll('input[type="checkbox"]'));
    const placeholder = toggle.textContent.trim();

    const updateToggle = function () {
      const selected = inputs.filter(i => i.checked).map(i => i.parentElement.textContent.trim());
      if (selected.length === 0) {
        toggle.textContent = placeholder;
      } else if (selected.length <= 2) {
        toggle.textContent = selected.join(', ');
      } else {
        toggle.textContent = `${selected.length} selected`;
      }
    };

    inputs.forEach(cb => cb.addEventListener('change', updateToggle));
    updateToggle();
  });

  // Close an open dropdown when tapping elsewhere.
  document.addEventListener('click', function (ev) {
    document.querySelectorAll('details.dropdown[open]').forEach(function (dropdown) {
      if (!dropdown.contains(ev.target)) {
        dropdown.removeAttribute('open');
      }
    });
  });

  // Provider: the API key field only matters when a debrid service is chosen.
  const providerSelect = document.querySelector('[data-provider-select]');
  const keyField = document.querySelector('[data-api-key-field]');
  const p2pHelp = document.querySelector('[data-p2p-help]');
  if (providerSelect && keyField) {
    const updateProvider = function () {
      const isP2P = providerSelect.value === 'p2p';
      keyField.hidden = isP2P;
      if (p2pHelp) p2pHelp.hidden = !isP2P;
    };
    providerSelect.addEventListener('change', function () {
      updateProvider();
      if (providerSelect.value !== 'p2p') {
        keyField.querySelector('input').focus();
      }
    });
    updateProvider();
  }

  const form = document.querySelector('form[action="/generate"]');
  if (form) {
    form.addEventListener('submit', function (ev) {
      const fail = function (message, field) {
        ev.preventDefault();
        showToast(message);
        if (field) field.focus();
      };

      if (providerSelect && providerSelect.value !== 'p2p') {
        const key = form.querySelector('input[name="api_key"]');
        if (key && !key.value.trim()) {
          const name = providerSelect.options[providerSelect.selectedIndex].text;
          return fail(`Enter your ${name} API key, or choose None (direct P2P).`, key);
        }
      }

      for (const n of form.querySelectorAll('input[type="number"]')) {
        if (n.value && Number(n.value) < 0) {
          const details = n.closest('details');
          if (details) details.open = true;
          return fail('Numbers must be 0 or more.', n);
        }
      }

      const checked = name => new Set(
        Array.from(form.querySelectorAll(`input[name="${name}"]:checked`)).map(el => el.value)
      );
      const excluded = checked('excluded_languages');
      for (const lang of checked('required_languages')) {
        if (excluded.has(lang)) {
          return fail(`A language can't be both required and excluded: ${lang}`);
        }
      }
    });
  }

  initSortableList();
});

function initSortableList() {
  const sortableList = document.getElementById('sortCriteria');
  const sortInput = document.getElementById('sortCriteriaInput');
  if (!sortableList || !sortInput) return;

  // Restore the saved order; criteria not in it keep their default order after.
  const saved = sortInput.value.split(',').map(s => s.trim()).filter(Boolean);
  if (saved.length > 0) {
    const items = Array.from(sortableList.querySelectorAll('.sortable-item'));
    const ordered = saved.map(v => items.find(i => i.dataset.value === v)).filter(Boolean);
    items.forEach(item => { if (!ordered.includes(item)) ordered.push(item); });
    ordered.forEach(item => sortableList.appendChild(item));
  }

  updateSortCriteria();
  updateButtonStates();
}

function moveItem(button, direction) {
  const item = button.closest('.sortable-item');
  const sortableList = item.parentElement;
  const items = Array.from(sortableList.querySelectorAll('.sortable-item'));
  const newIndex = items.indexOf(item) + direction;

  if (newIndex < 0 || newIndex >= items.length) return;

  if (direction === -1) {
    sortableList.insertBefore(item, items[newIndex]);
  } else {
    sortableList.insertBefore(items[newIndex], item);
  }

  updateSortCriteria();
  updateButtonStates();

  // Keep keyboard focus on the moved item's button (or its twin at the edges).
  (button.disabled ? item.querySelector('.sort-btn:not(:disabled)') : button)?.focus();

  const announcement = document.getElementById('sortAnnouncement');
  const label = item.querySelector('.sort-label');
  if (announcement && label) {
    const position = Array.from(sortableList.children).indexOf(item) + 1;
    announcement.textContent = `${label.textContent.trim()} moved to priority ${position}.`;
  }
}

function updateButtonStates() {
  const items = document.querySelectorAll('#sortCriteria .sortable-item');

  items.forEach((item, index) => {
    const rank = item.querySelector('.sort-rank');
    if (rank) rank.textContent = String(index + 1);
    item.querySelector('.sort-btn.up').disabled = index === 0;
    item.querySelector('.sort-btn.down').disabled = index === items.length - 1;
  });
}

function updateSortCriteria() {
  const sortInput = document.getElementById('sortCriteriaInput');
  if (!sortInput) return;

  sortInput.value = Array.from(document.querySelectorAll('#sortCriteria .sortable-item'))
    .map(item => item.dataset.value)
    .join(',');
}

function showToast(msg, timeout = 3000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }

  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  container.appendChild(t);

  setTimeout(() => { t.style.opacity = '0'; }, timeout);
  setTimeout(() => { t.remove(); }, timeout + 300);
}

function copyManifest() {
  const el = document.getElementById('manifestUrl');
  if (!el) return;
  const text = el.textContent.trim();

  const fallback = function () {
    // Select the text so the user can copy it by hand.
    const range = document.createRange();
    range.selectNodeContents(el);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    showToast('Press and hold (or Ctrl+C) to copy the selected URL');
  };

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => showToast('Addon URL copied'), fallback);
  } else {
    fallback();
  }
}
