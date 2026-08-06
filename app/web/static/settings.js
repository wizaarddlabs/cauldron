// settings.js: search/filter language pills, add custom language chips, and simple validation
document.addEventListener('DOMContentLoaded', function(){
  // pill visuals
  document.querySelectorAll('.pill input[type="checkbox"]').forEach(function(cb){
    const label = cb.nextElementSibling;
    if(!label) return;
    const update = ()=> label.classList.toggle('selected', cb.checked);
    cb.addEventListener('change', update);
    update();
  });

  // dropdown behavior for language selectors using native details components
  document.querySelectorAll('.dropdown').forEach(function(dropdown){
    const toggle = dropdown.querySelector('.dropdown-toggle');
    const inputs = Array.from(dropdown.querySelectorAll('input[type="checkbox"]'));

    const updateToggle = function(){
      const selected = inputs.filter(i => i.checked).map(i => i.parentElement.textContent.trim());
      if(selected.length === 0){
        toggle.textContent = toggle.dataset.placeholder;
      } else if(selected.length === 1){
        toggle.textContent = selected[0];
      } else {
        toggle.textContent = `${selected.length} selected`;
      }
    };

    toggle.dataset.placeholder = toggle.textContent;
    updateToggle();

    dropdown.querySelectorAll('.dropdown-option input[type="checkbox"]').forEach(function(cb){
      cb.addEventListener('change', updateToggle);
    });
  });

  document.addEventListener('click', function(ev){
    document.querySelectorAll('details.dropdown[open]').forEach(function(dropdown){
      if(!dropdown.contains(ev.target)){
        dropdown.removeAttribute('open');
      }
    });
  });

  // form validation: numbers should be >= 0 and language groups must not conflict
  const form = document.querySelector('form[action="/generate"]');
  if(form){
    form.addEventListener('submit', function(ev){
      const nums = form.querySelectorAll('input[type="number"]');
      for(const n of nums){
        if(n.value && Number(n.value) < 0){
          showToast('Numeric values must be >= 0');
          ev.preventDefault();
          return false;
        }
      }

      const required = new Set(
        Array.from(form.querySelectorAll('input[name="required_languages"]:checked')).map(el => el.value)
      );
      const excluded = new Set(
        Array.from(form.querySelectorAll('input[name="excluded_languages"]:checked')).map(el => el.value)
      );

      for(const lang of required){
        if(excluded.has(lang)){
          showToast(`Language cannot be both required and excluded: ${lang}`);
          ev.preventDefault();
          return false;
        }
      }
    });
  }

  // Force inline styles on labels that wrap checkboxes to avoid CSS inheritance issues
  document.querySelectorAll('label').forEach(function(lbl){
    const cb = lbl.querySelector('input[type="checkbox"], input[type="radio"]');
    if(cb){
      lbl.style.display = 'inline-flex';
      lbl.style.alignItems = 'center';
      lbl.style.gap = '8px';
      lbl.style.marginTop = '0';
      cb.style.display = 'inline-block';
      cb.style.margin = '0 8px 0 0';
      cb.style.width = 'auto';
      cb.style.height = 'auto';
    }
  });

  // Initialize sortable list
  initSortableList();
});

function initSortableList() {
  const sortableList = document.getElementById('sortCriteria');
  const sortInput = document.getElementById('sortCriteriaInput');
  
  if (!sortableList || !sortInput) {
    console.log('Sortable list or input not found');
    return;
  }

  console.log('Initializing sortable list');

  // Initialize items from saved preferences
  const savedCriteria = sortInput.value.split(',').filter(s => s.trim());
  if (savedCriteria.length > 0 && savedCriteria[0]) {
    const items = Array.from(sortableList.querySelectorAll('.sortable-item'));
    const orderedItems = [];
    
    savedCriteria.forEach(value => {
      const item = items.find(i => i.dataset.value === value);
      if (item) orderedItems.push(item);
    });
    
    // Add any remaining items that weren't in saved criteria
    items.forEach(item => {
      if (!orderedItems.includes(item)) orderedItems.push(item);
    });
    
    orderedItems.forEach(item => sortableList.appendChild(item));
  }

  updateButtonStates();
}

function moveItem(button, direction) {
  const item = button.closest('.sortable-item');
  const sortableList = item.parentElement;
  const items = Array.from(sortableList.querySelectorAll('.sortable-item'));
  const currentIndex = items.indexOf(item);
  
  const newIndex = currentIndex + direction;
  
  if (newIndex >= 0 && newIndex < items.length) {
    if (direction === -1) {
      sortableList.insertBefore(item, items[newIndex]);
    } else {
      sortableList.insertBefore(items[newIndex], item);
    }
    
    updateSortCriteria();
    updateButtonStates();
  }
}

function updateButtonStates() {
  const sortableList = document.getElementById('sortCriteria');
  if (!sortableList) return;
  
  const items = sortableList.querySelectorAll('.sortable-item');
  
  items.forEach((item, index) => {
    const upBtn = item.querySelector('.sort-btn.up');
    const downBtn = item.querySelector('.sort-btn.down');
    
    if (upBtn) upBtn.disabled = index === 0;
    if (downBtn) downBtn.disabled = index === items.length - 1;
  });
}

function updateSortCriteria() {
  const sortableList = document.getElementById('sortCriteria');
  const sortInput = document.getElementById('sortCriteriaInput');
  
  if (!sortableList || !sortInput) return;
  
  const items = sortableList.querySelectorAll('.sortable-item');
  const criteria = Array.from(items).map(item => item.dataset.value);
  sortInput.value = criteria.join(',');
  console.log('Updated sort criteria:', criteria);
}

function addLanguageChip(text){
  const pills = document.querySelector('div.card h2 + .pills') || document.querySelector('.pills');
  if(!pills) return;
  const id = 'lang_' + text.toLowerCase().replace(/[^a-z0-9]+/g,'_');
  if(document.getElementById(id)) return;
  const div = document.createElement('div');
  div.className = 'pill';
  div.innerHTML = `<input id="${id}" type="checkbox" name="language" value="${text}"><label for="${id}">${text}</label>`;
  pills.appendChild(div);
  const cb = div.querySelector('input');
  const lbl = div.querySelector('label');
  cb.checked = true;
  lbl.classList.add('selected');
}

// Toast helper
function showToast(msg, timeout=2500){
  let container = document.getElementById('toast-container');
  if(!container){
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.position = 'fixed';
    container.style.right = '18px';
    container.style.bottom = '18px';
    container.style.zIndex = 9999;
    document.body.appendChild(container);
  }

  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  t.style.background = 'rgba(20,20,20,0.95)';
  t.style.color = '#ffd700';
  t.style.padding = '10px 14px';
  t.style.borderRadius = '8px';
  t.style.marginTop = '8px';
  t.style.boxShadow = '0 8px 24px rgba(0,0,0,0.6)';
  container.appendChild(t);

  setTimeout(()=>{ t.style.opacity = '0'; t.style.transition='opacity 250ms'; }, timeout);
  setTimeout(()=>{ try{ container.removeChild(t) }catch(e){} }, timeout + 300);
}

function copyManifest(){
  const el = document.getElementById('manifestUrl');
  if(!el) return;
  const text = el.textContent || el.innerText || '';
  if(navigator.clipboard){
    navigator.clipboard.writeText(text).then(()=> showToast('Manifest URL copied'))
  } else {
    showToast('Copy not supported in this browser');
  }
}
