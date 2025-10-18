// /frontend/static/js/common.js

function loadSidebar() {
  fetch('/sidebar/')  // Django endpoint
    .then(res => res.text())
    .then(html => {
      document.getElementById("sidebarContainer").innerHTML = html;

      // Set active link based on current page
      setActiveLink();

      // Sidebar HTML injected — now run sidebar.js logic if available
      if (typeof initSidebar === "function") {
        initSidebar();
      }
    })
    .catch(err => console.error("Sidebar failed to load:", err));
}

function setActiveLink() {
  const currentPath = window.location.pathname;
  const sidebarLinks = document.querySelectorAll('.sidebar a');
  
  sidebarLinks.forEach(link => {
    link.classList.remove('active');
    const linkPath = new URL(link.href).pathname;
    
    // Exact match only, with special case for root
    if (currentPath === linkPath || 
        (currentPath === '/' && linkPath === '/dashboard/')) {
      link.classList.add('active');
    }
  });
}

document.addEventListener("DOMContentLoaded", loadSidebar);
