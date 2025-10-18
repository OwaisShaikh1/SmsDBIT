function initSidebar() {
  // Active link highlighting is handled by setActiveLink() in common.js
  // No need to duplicate the logic here


  // Determine user role
  const role = localStorage.getItem("role");
  const adminSection = document.querySelector(".admin-only");
  const teacherSection = document.querySelector(".teacher-only");
/*
  if (role === "admin") {
    if (teacherSection) teacherSection.style.display = "none";
  } else if (role === "teacher") {
    if (adminSection) adminSection.style.display = "none";
  } else {
    alert("⚠️ You are not logged in. Redirecting to login...");
    window.location.href = "auth/login/";
    return;
  }*/

  // Logout functionality
  const logoutLink = document.getElementById("logoutLink");
  if (logoutLink) {
    logoutLink.addEventListener("click", e => {
      e.preventDefault();
      localStorage.clear();
      alert("✅ You have been logged out.");
      window.location.href = "/login/";
    });
  }
}
