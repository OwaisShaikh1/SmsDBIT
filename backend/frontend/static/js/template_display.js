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
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">
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
        {${escapeHtml(name)}} <small>(${type})</small>
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
