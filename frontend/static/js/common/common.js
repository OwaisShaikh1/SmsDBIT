// /frontend/static/js/common.js

function loadSidebar() {
  fetch("../../static/js/components/sidebar.html")
    .then(res => res.text())
    .then(html => {
      document.getElementById("sidebarContainer").innerHTML = html;

      // Sidebar HTML injected — now run sidebar.js logic
      if (typeof initSidebar === "function") {
        initSidebar();
      } else {
        console.error("initSidebar() not found — make sure sidebar.js is loaded before common.js");
      }
    })
    .catch(err => console.error("Sidebar failed to load:", err));
}

document.addEventListener("DOMContentLoaded", loadSidebar);
