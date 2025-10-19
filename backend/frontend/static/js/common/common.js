// /frontend/static/js/common/common.js
// Common client-side logic for SMS Portal (API mounted under /api)

// Safe API_BASE initialization: read from window.API_BASE if present (set by inline script),
// otherwise fall back to '/api'. Using window avoids TDZ issues when a const API_BASE is declared later.
const API_BASE = (typeof window !== 'undefined' && window.API_BASE) ? window.API_BASE : '/api';
console.debug('common.js using API_BASE =', API_BASE);

function getAuthToken() {
  return localStorage.getItem('accessToken') || '';
}

function setAuthTokens(accessToken, refreshToken) {
  // Store in localStorage
  localStorage.setItem('accessToken', accessToken);
  localStorage.setItem('refreshToken', refreshToken);
  
  // Also store in cookies for backend views
  document.cookie = `accessToken=${accessToken}; path=/; SameSite=Lax`;
  document.cookie = `refreshToken=${refreshToken}; path=/; SameSite=Lax`;
}

function handleLogout() {
  localStorage.removeItem('accessToken');
  localStorage.removeItem('refreshToken');
  localStorage.removeItem('user');
  localStorage.removeItem('role');
  
  // Clear cookies
  document.cookie = 'accessToken=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
  document.cookie = 'refreshToken=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
  
  alert('You have been logged out.');
  // Use explicit redirect to frontend login route
  window.location.href = '/login/';
}

/**
 * authFetch: wrapper around fetch that attaches Authorization header automatically
 * returns the Response object (caller can parse .json() or .text())
 */
async function authFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = {
    ...(options.headers || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // default content-type if not multipart and not provided
  if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const finalOptions = { ...options, headers };
  const resp = await fetch(url, finalOptions);
  if (resp.status === 401 || resp.status === 403) {
    // token invalid or expired
    handleLogout();
  }
  return resp;
}

// safe fetch + parse JSON helper (used in some codepaths)
async function safeFetchJson(url, options = {}) {
  const resp = await authFetch(url, options);
  const contentType = resp.headers.get('content-type') || '';
  const text = await resp.text();

  if (!resp.ok) {
    let msg;
    if (contentType.includes('application/json')) {
      try {
        const json = JSON.parse(text);
        msg = json.detail || json.message || JSON.stringify(json);
      } catch (e) {
        msg = text.slice(0, 1000);
      }
    } else {
      msg = text.slice(0, 1000);
    }
    const err = new Error(`HTTP ${resp.status}: ${msg}`);
    err.status = resp.status;
    err.body = text;
    throw err;
  }

  if (contentType.includes('application/json')) {
    return JSON.parse(text);
  }

  return { _contentType: contentType, _text: text };
}

// Sidebar loader: fetch role-aware sidebar partial from backend
function loadSidebar() {
  const sidebarContainer = document.getElementById('sidebarContainer');
  if (!sidebarContainer) return;

  const token = getAuthToken();
  if (!token) {
    // If user not logged in, redirect to login
    // (development tip: comment this out if you want sidebar to load without auth)
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login/';
    }
    return;
  }

  // Try primary sidebar endpoint first
  authFetch(`${API_BASE}/sidebar/`, { method: 'GET' })
    .then(async (res) => {
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          handleLogout();
          return;
        }
        throw new Error(`Sidebar fetch failed: ${res.status} ${res.statusText}`);
      }
      const html = await res.text();
      sidebarContainer.innerHTML = html;
      setActiveLink();
      
      // Hide loader if it exists
      const loader = document.getElementById('sidebarLoader');
      if (loader) loader.remove();

      // init hook if sidebar provides a JS init function
      if (typeof initSidebar === 'function') initSidebar();

      // wire logout link
      const logoutLink = sidebarContainer.querySelector('a[href="/logout/"], a[href="/logout"]');
      if (logoutLink) {
        logoutLink.addEventListener('click', (ev) => {
          ev.preventDefault();
          handleLogout();
        });
      }
    })
    .catch((err) => {
      console.error('Primary sidebar failed to load:', err);
      
      // Fallback: show minimal sidebar with basic navigation
      showFallbackSidebar(sidebarContainer);
    });
}

// Fallback sidebar when dynamic loading fails
function showFallbackSidebar(container) {
  const fallbackHTML = `
    <div class="sidebar" style="height:100vh;background-color:#1e3a8a;color:white;padding:20px;">
      <h4 style="text-align:center;margin-bottom:25px;color:white;">SMS Portal</h4>
      <div style="color:white;padding:10px 20px;background:rgba(255,255,255,0.1);border-radius:4px;margin-bottom:20px;">
        <small>⚠️ Loading error - basic navigation</small>
      </div>
      <a href="/dashboard/" style="color:white;text-decoration:none;display:block;padding:10px 20px;border-radius:6px;margin:4px 0;">🏠 Dashboard</a>
      <a href="/send/" style="color:white;text-decoration:none;display:block;padding:10px 20px;border-radius:6px;margin:4px 0;">✉️ Send SMS</a>
      <a href="/history/" style="color:white;text-decoration:none;display:block;padding:10px 20px;border-radius:6px;margin:4px 0;">📜 History</a>
      <hr style="border-color:rgba(255,255,255,0.2);margin:10px 0;">
      <a href="/profile/" style="color:white;text-decoration:none;display:block;padding:10px 20px;border-radius:6px;margin:4px 0;">👤 Profile</a>
      <a href="#" onclick="window.AppAuth.handleLogout()" style="color:white;text-decoration:none;display:block;padding:10px 20px;border-radius:6px;margin:4px 0;">🚪 Logout</a>
    </div>
  `;
  container.innerHTML = fallbackHTML;
  
  // Hide loader if it exists
  const loader = document.getElementById('sidebarLoader');
  if (loader) loader.remove();
}

function setActiveLink() {
  const currentPath = window.location.pathname.replace(/\/+$/, '');
  const sidebarLinks = document.querySelectorAll('.sidebar a');

  sidebarLinks.forEach(link => {
    link.classList.remove('active');
    try {
      const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/+$/, '');
      // treat dashboard root mapping
      if (
        currentPath === linkPath ||
        (currentPath === '/' && (linkPath === '/dashboard' || linkPath === '/dashboard/'))
      ) {
        link.classList.add('active');
      }
    } catch (e) {
      // ignore malformed URLs
    }
  });
}

// verifyAuth: checks /api/auth/profile/ to ensure token is valid
async function verifyAuth() {
  const token = getAuthToken();
  if (!token) {
    // if current page is login, don't redirect to avoid loop
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login/';
    }
    return;
  }

  try {
    const resp = await authFetch(`${API_BASE}/auth/profile/`, { method: 'GET' });
    if (!resp.ok) {
      handleLogout();
      return;
    }
    // optionally update stored user info
    const data = await resp.json();
    if (data) {
      localStorage.setItem('user', JSON.stringify(data));
      localStorage.setItem('role', data.role || localStorage.getItem('role') || 'teacher');
    }
  } catch (err) {
    console.error('Auth check failed:', err);
    handleLogout();
  }
}

// exposes useful helper for other scripts to reuse
window.AppAuth = {
  API_BASE,
  getAuthToken,
  setAuthTokens,
  authFetch,
  safeFetchJson,
  verifyAuth,
  handleLogout
};

// initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', async () => {
  await verifyAuth();
  loadSidebar();
});
