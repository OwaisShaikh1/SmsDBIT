// Inject sidebar into the page
function loadSidebar() {
  fetch("sidebar.html")
    .then(res => res.text())
    .then(html => {
      document.getElementById("sidebarContainer").innerHTML = html;

      // Optional: highlight active link
      const current = window.location.pathname.split("/").pop();
      document.querySelectorAll(".sidebar a").forEach(link => {
        if (link.getAttribute("href") === current) {
          link.classList.add("active");
        }
      });
    });
}

// Call it when the DOM is ready
document.addEventListener("DOMContentLoaded", loadSidebar);
