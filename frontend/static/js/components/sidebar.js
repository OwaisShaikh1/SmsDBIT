function initSidebar() {
  // Highlight current page
  const currentPage = window.location.pathname.split("/").pop();
  document.querySelectorAll(".sidebar a").forEach(link => {
    const href = link.getAttribute("href");

    // Skip dummy or logout links
    if (!href || href === "#" || href.includes("auth")) return;

    // Highlight only if it matches current page
    if (href.includes(currentPage)) link.classList.add("active");
  });


  // Determine user role
  const role = localStorage.getItem("role");
  const adminSection = document.querySelector(".admin-only");
  const teacherSection = document.querySelector(".teacher-only");

  if (role === "admin") {
    if (teacherSection) teacherSection.style.display = "none";
  } else if (role === "teacher") {
    if (adminSection) adminSection.style.display = "none";
  } else {
    alert("⚠️ You are not logged in. Redirecting to login...");
    window.location.href = "/frontend/templates/auth/login.html";
    return;
  }

  // Logout functionality
  const logoutLink = document.getElementById("logoutLink");
  if (logoutLink) {
    logoutLink.addEventListener("click", e => {
      e.preventDefault();
      localStorage.clear();
      alert("✅ You have been logged out.");
      window.location.href = "/frontend/templates/auth/login.html";
    });
  }
}
