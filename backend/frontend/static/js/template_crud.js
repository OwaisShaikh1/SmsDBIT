// static/js/template_crud.js

let variableCounter = 0;
let suggestionIndex = -1;

document.addEventListener("DOMContentLoaded", () => {
  const content = document.getElementById("templateContent");
  if (content) bindContentFieldListeners(content);
  updateVariableChips();
});

document.addEventListener('shown.bs.modal', function(ev){
  const modal = ev.target;
  if (modal && modal.id === 'addTemplateModal') {
    const content = document.getElementById('templateContent');
    if (content) bindContentFieldListeners(content);
    updateCharCount();
  }
});

/* ---------------- VARIABLES ---------------- */

window.addVariableRow = function () {
  const container = document.getElementById("variablesContainer");
  const rowId = variableCounter++;

  const row = document.createElement("div");
  row.className = "variable-row mb-2 p-2 border rounded bg-light";
  row.dataset.rowId = rowId;
  row.id = `varRow_${rowId}`;

  row.innerHTML = `
    <div class="row g-2 align-items-center">
      <div class="col-md-3">
        <input class="form-control form-control-sm var-name-input"
               data-row-id="${rowId}" placeholder="Variable name">
      </div>
      <div class="col-md-3">
        <select class="form-select form-select-sm var-type-select"
                data-row-id="${rowId}">
          <option value="string">String</option>
          <option value="integer">Integer</option>
          <option value="float">Float</option>
          <option value="date">Date</option>
          <option value="time">Time</option>
          <option value="boolean">Boolean</option>
          <option value="email">Email</option>
          <option value="phone">Phone</option>
        </select>
      </div>
      <div class="col-md-2">
        <div class="form-check mt-1">
          <input type="checkbox" class="form-check-input var-required-check" data-row-id="${rowId}">
          <label class="form-check-label" style="font-size: 0.875rem;">Required</label>
        </div>
      </div>
      <div class="col-md-2">
        <button class="btn btn-success btn-sm w-100" onclick="insertVariableIntoContent(${rowId})">➕ Insert</button>
      </div>
      <div class="col-md-2">
        <button class="btn btn-danger btn-sm w-100" onclick="removeVariableRow(${rowId})">🗑️ Delete</button>
      </div>
    </div>
  `;

  container.appendChild(row);
  row.querySelector(".var-name-input").addEventListener("input", updateVariableChips);
  row.querySelector(".var-type-select").addEventListener("change", updateVariableChips);
  updateVariableChips();
};

window.removeVariableRow = function (rowId) {
  document.getElementById(`varRow_${rowId}`)?.remove();
  updateVariableChips();
};

function getVariables() {
  return [...document.querySelectorAll(".variable-row")].map(row => {
    const id = row.dataset.rowId;
    const name = row.querySelector(`.var-name-input[data-row-id="${id}"]`)?.value.trim();
    const type = row.querySelector(`.var-type-select[data-row-id="${id}"]`)?.value || 'string';
    const required = row.querySelector(`.var-required-check[data-row-id="${id}"]`)?.checked;
    return name ? { name, type, required } : null;
  }).filter(Boolean);
}

function updateVariableChips() {
  const el = document.getElementById("variablesChips");
  const vars = getVariables();
  if (!vars.length) {
    el.innerHTML = `<div class="text-muted small">No variables yet</div>`;
    return;
  }
  el.innerHTML = vars.map(v => {
    const tag = `{#${v.name}#}`;
    return `<span class="variable-tag var-${v.type} var-chip" draggable="true" data-name="${v.name}" title="Drag or click to insert">${tag}</span>`;
  }).join(" ");

  el.querySelectorAll('.var-chip').forEach(chip => {
    chip.addEventListener('click', () => insertVariableByName(chip.dataset.name));
    chip.addEventListener('dragstart', ev => {
      const name = chip.dataset.name;
      ev.dataTransfer.setData('text/plain', `{#${name}#}`);
      ev.dataTransfer.effectAllowed = 'copy';
    });
  });
}

/* ---------------- CONTENT HELPERS ---------------- */

function bindContentFieldListeners(el) {
  if (!el || el.dataset.bound === '1') return;
  el.addEventListener("input", onContentInput);
  el.addEventListener("keydown", onContentKeydown);
  el.addEventListener('blur', () => setTimeout(hideSuggestions, 150));
  el.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  el.addEventListener('drop', e => { e.preventDefault(); const data = e.dataTransfer.getData('text/plain'); if (data) insertTextAtCaret(el, data); hideSuggestions(); });
  el.dataset.bound = '1';
}

function insertVariableByName(name) {
  const textarea = document.getElementById("templateContent");
  insertTextAtCaret(textarea, `{#${name}#}`);
  hideSuggestions();
}

function insertVariableIntoContent(rowId) {
  const name = document.querySelector(`.var-name-input[data-row-id="${rowId}"]`)?.value.trim();
  if (!name) return alert("Variable name required");
  insertVariableByName(name);
}

function insertTextAtCaret(el, text) {
  try {
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? start;
    if (typeof el.setRangeText === 'function') {
      el.setRangeText(text, start, end, 'end');
    } else {
      const before = el.value.substring(0, start);
      const after = el.value.substring(end);
      el.value = before + text + after;
      const caret = (before + text).length;
      el.setSelectionRange(caret, caret);
    }
    el.focus();
    el.dispatchEvent(new Event('input', { bubbles: true }));
    updateCharCount();
  } catch (e) {
    console.warn('Insert at caret failed:', e);
    el.value += text;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    updateCharCount();
  }
}

function updateCharCount() {
  const el = document.getElementById("templateContent");
  const cc = document.getElementById("charCount");
  if (el && cc) cc.textContent = `${el.value.length}/1600`;
}

/* ---------------- AUTOCOMPLETE ---------------- */

function onContentInput() {
  updateCharCount();
  maybeShowSuggestions();
}

function onContentKeydown(e) {
  const menu = document.getElementById('varSuggestions');
  if (!menu || menu.style.display === 'none') return;
  const items = Array.from(menu.querySelectorAll('.autocomplete-item'));
  if (!items.length) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    suggestionIndex = (suggestionIndex + 1) % items.length;
    items.forEach((el, idx) => el.classList.toggle('active', idx === suggestionIndex));
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    suggestionIndex = (suggestionIndex - 1 + items.length) % items.length;
    items.forEach((el, idx) => el.classList.toggle('active', idx === suggestionIndex));
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    e.preventDefault();
    const chosen = items[suggestionIndex >= 0 ? suggestionIndex : 0];
    if (chosen) chooseSuggestion(chosen.dataset.name);
  } else if (e.key === 'Escape') {
    hideSuggestions();
  }
}

function hideSuggestions() {
  const menu = document.getElementById('varSuggestions');
  if (menu) menu.style.display = 'none';
  suggestionIndex = -1;
}

function maybeShowSuggestions() {
  const textarea = document.getElementById('templateContent');
  const menu = document.getElementById('varSuggestions');
  if (!textarea || !menu) return;
  const pos = textarea.selectionStart || 0;
  const text = textarea.value || '';
  const upto = text.slice(0, pos);
  const startIdx = upto.lastIndexOf('{#');
  if (startIdx === -1) { hideSuggestions(); return; }
  if (upto.slice(startIdx).includes('#}')) { hideSuggestions(); return; }
  const partial = upto.slice(startIdx + 2).toLowerCase();
  const vars = getVariables();
  const matches = vars.filter(v => v.name.toLowerCase().startsWith(partial)).slice(0, 8);
  if (!matches.length) { hideSuggestions(); return; }

  menu.innerHTML = matches.map((v, i) => `
    <div class="autocomplete-item${i===0?' active':''}" data-name="${v.name}">
      <span class="name">${v.name}</span>
      <span class="type">${v.type}</span>
    </div>
  `).join('');
  suggestionIndex = 0;
  menu.style.display = 'block';
  menu.querySelectorAll('.autocomplete-item').forEach(item => {
    item.addEventListener('mousedown', e => { e.preventDefault(); chooseSuggestion(item.dataset.name); });
  });
}

function chooseSuggestion(name) {
  const textarea = document.getElementById('templateContent');
  const pos = textarea.selectionStart || 0;
  const text = textarea.value || '';
  const upto = text.slice(0, pos);
  const startIdx = upto.lastIndexOf('{#');
  if (startIdx === -1) { insertVariableByName(name); return; }
  try { textarea.setSelectionRange(startIdx, pos); } catch (e) {}
  insertTextAtCaret(textarea, `{#${name}#}`);
  hideSuggestions();
}

/* ---------------- SAVE TEMPLATE ---------------- */

window.saveTemplate = async function () {
  const title = (document.getElementById('templateTitle')?.value || '').trim();
  const category = document.getElementById('templateCategory')?.value || '';
  const content = (document.getElementById('templateContent')?.value || '').trim();
  const classScope = (document.getElementById('templateClassScope')?.value || '').trim() || null;

  if (!title || !category || !content) {
    alert('Please fill in all required fields (Title, Category, Content)');
    return;
  }

  const schemaEntries = getVariables().map(v => [v.name, { type: v.type, required: v.required }]);
  const data = {
    title,
    category,
    content,
    class_scope: classScope,
    variable_schema: schemaEntries.length ? Object.fromEntries(schemaEntries) : null,
    status: 'pending',
    is_active: true
  };

  try {
    const res = await fetch(`${window.API_BASE}/templates/create/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      credentials: 'include',
      body: JSON.stringify(data)
    });

    if (res.status === 401 || res.status === 403) {
      alert('Session expired or unauthorized. Please log in again.');
      window.location.href = '/login/';
      return;
    }

    if (!res.ok) {
      let msg = 'Failed to save template';
      try { const err = await res.json(); if (err?.error) msg = err.error; } catch {}
      alert(msg);
      return;
    }

    const modalEl = document.getElementById('addTemplateModal');
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.hide();

    document.getElementById('addTemplateForm')?.reset();
    const varsCont = document.getElementById('variablesContainer');
    if (varsCont) varsCont.innerHTML = '';
    const chips = document.getElementById('variablesChips');
    if (chips) chips.innerHTML = '<div class="text-muted small">No variables yet</div>';
    const cc = document.getElementById('charCount');
    if (cc) cc.textContent = '0/1600';
    variableCounter = 0;
    if (typeof loadTemplates === 'function') loadTemplates();
    alert('Template created successfully!');
  } catch (err) {
    console.error('Error creating template:', err);
    alert(`Error: ${err.message}`);
  }
};

/* ---------------- CSRF ---------------- */

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
