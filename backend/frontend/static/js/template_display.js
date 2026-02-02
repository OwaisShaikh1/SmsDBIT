// static/js/template_display.js

document.addEventListener("DOMContentLoaded", loadTemplates);

async function loadTemplates() {
  try {
    const response = await fetch(`${window.API_BASE}/templates/`, {
      method: "GET",
      credentials: "include"
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = "/login/";
      return;
    }

    if (!response.ok) throw new Error("Failed to fetch templates");

    const templates = await response.json();
    renderTemplates(templates);
    updateStats(templates);

  } catch (err) {
    console.error(err);
    document.getElementById("templateTableBody").innerHTML =
      `<tr><td colspan="5" class="text-center text-danger py-4">
        Failed to load templates
      </td></tr>`;
  }
}

function renderTemplates(templates) {
  const tbody = document.getElementById("templateTableBody");
  tbody.innerHTML = "";

  if (!templates.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">
      No templates found
    </td></tr>`;
    return;
  }

  const statusMap = { approved: "success", pending: "warning", rejected: "danger" };
  const categoryMap = { student: "primary", teacher: "info", common: "success" };

  templates.forEach(t => {
    const variables = renderVariables(t.variable_schema);
    const created = new Date(t.created_at).toLocaleDateString();

    tbody.innerHTML += `
      <tr>
        <td>${escapeHtml(t.title || "-")}</td>
        <td><span class="badge bg-${categoryMap[t.category] || "secondary"}">
          ${escapeHtml(t.category || "-")}
        </span></td>
        <td>${variables}</td>
        <td><span class="badge bg-${statusMap[t.status] || "secondary"}">
          ${escapeHtml(t.status || "-")}
        </span></td>
        <td>${created}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="editTemplate(${t.id})" title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          <button class="btn btn-sm btn-danger" onclick="deleteTemplate(${t.id}, '${escapeHtml(t.title)}')" title="Delete">
            <i class="fas fa-trash"></i>
          </button>
        </td>
      </tr>
    `;
  });
}

function renderVariables(schema) {
  if (!schema) return "-";

  return Object.entries(schema).map(([name, meta]) => {
    const type = meta?.type || "unknown";
    return `
      <span class="variable-tag var-${type}">
        {#${escapeHtml(name)}#} <small>(${type})</small>
      </span>`;
  }).join(" ");
}

function updateStats(templates) {
  document.getElementById("totalTemplates").textContent = templates.length;
  document.getElementById("approvedCount").textContent =
    templates.filter(t => t.status === "approved").length;
  document.getElementById("pendingCount").textContent =
    templates.filter(t => t.status === "pending").length;
  document.getElementById("draftCount").textContent =
    templates.filter(t => t.status === "rejected").length;
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"'`=\/]/g, s => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
    "`": "&#x60;",
    "=": "&#x3D;",
    "/": "&#x2F;"
  })[s]);
}

// Edit template function
window.editTemplate = async function(templateId) {
  try {
    const response = await fetch(`${window.API_BASE}/templates/${templateId}/`, {
      method: "GET",
      credentials: "include"
    });

    if (response.status === 401 || response.status === 403) {
      alert("Session expired or unauthorized. Please log in again.");
      window.location.href = "/login/";
      return;
    }

    if (!response.ok) throw new Error("Failed to fetch template");

    const template = await response.json();
    
    // Populate edit modal
    document.getElementById('editTemplateId').value = template.id;
    document.getElementById('editTemplateTitle').value = template.title;
    document.getElementById('editTemplateCategory').value = template.category;
    document.getElementById('editTemplateContent').value = template.content;
    document.getElementById('editTemplateClassScope').value = template.class_scope || '';
    document.getElementById('editTemplateStatus').value = template.status;
    document.getElementById('editTemplateIsActive').checked = template.is_active;
    
    // Display variables in read-only format
    const varsDisplay = document.getElementById('editVariablesDisplay');
    if (template.variable_schema && Object.keys(template.variable_schema).length > 0) {
      varsDisplay.innerHTML = Object.entries(template.variable_schema).map(([name, meta]) => {
        const type = meta?.type || "string";
        const required = meta?.required ? "✓" : "";
        return `<span class="badge bg-secondary me-1">{#${name}#} (${type}) ${required}</span>`;
      }).join(" ");
    } else {
      varsDisplay.innerHTML = '<span class="text-muted">No variables</span>';
    }
    
    // Update character count
    const charCount = document.getElementById('editCharCount');
    if (charCount) charCount.textContent = `${template.content.length}/1600`;
    
    // Show modal
    const modalEl = document.getElementById('editTemplateModal');
    const modal = new bootstrap.Modal(modalEl);
    modal.show();

  } catch (err) {
    console.error('Error loading template:', err);
    alert(`Error loading template: ${err.message}`);
  }
};

// Save edited template
window.saveEditedTemplate = async function() {
  const templateId = document.getElementById('editTemplateId').value;
  const title = document.getElementById('editTemplateTitle')?.value.trim();
  const category = document.getElementById('editTemplateCategory')?.value;
  const content = document.getElementById('editTemplateContent')?.value.trim();
  const classScope = document.getElementById('editTemplateClassScope')?.value.trim() || null;
  const status = document.getElementById('editTemplateStatus')?.value;
  const isActive = document.getElementById('editTemplateIsActive')?.checked;

  if (!title || !category || !content) {
    alert('Please fill in all required fields (Title, Category, Content)');
    return;
  }

  const data = {
    title,
    category,
    content,
    class_scope: classScope,
    status,
    is_active: isActive
  };

  try {
    const res = await fetch(`${window.API_BASE}/templates/${templateId}/update/`, {
      method: 'PUT',
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
      let msg = 'Failed to update template';
      try { const err = await res.json(); if (err?.error) msg = err.error; } catch {}
      alert(msg);
      return;
    }

    const modalEl = document.getElementById('editTemplateModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    modal.hide();

    loadTemplates();
    alert('Template updated successfully!');
  } catch (err) {
    console.error('Error updating template:', err);
    alert(`Error: ${err.message}`);
  }
};

// Delete template function
window.deleteTemplate = async function(templateId, templateTitle) {
  if (!confirm(`Are you sure you want to delete the template "${templateTitle}"?\n\nThis action cannot be undone.`)) {
    return;
  }

  try {
    const res = await fetch(`${window.API_BASE}/templates/${templateId}/delete/`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      credentials: 'include'
    });

    if (res.status === 401 || res.status === 403) {
      alert('Session expired or unauthorized. Please log in again.');
      window.location.href = '/login/';
      return;
    }

    if (!res.ok) {
      let msg = 'Failed to delete template';
      try { const err = await res.json(); if (err?.error) msg = err.error; } catch {}
      alert(msg);
      return;
    }

    loadTemplates();
    alert('Template deleted successfully!');
  } catch (err) {
    console.error('Error deleting template:', err);
    alert(`Error: ${err.message}`);
  }
};

// Helper to get CSRF token
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
