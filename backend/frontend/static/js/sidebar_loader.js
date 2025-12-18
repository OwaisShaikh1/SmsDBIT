;(function(){
  const SIDEBAR_URL = '/sidebar/';

  // In-memory / hidden DOM cache for the sidebar HTML. We preload the
  // fragment in the background and inject it into visible pages when ready.
  let cachedHtml = null;

  function createCacheContainer(){
    let cache = document.getElementById('sidebarCache');
    if (!cache) {
      cache = document.createElement('div');
      cache.id = 'sidebarCache';
      cache.style.display = 'none';
      document.body.appendChild(cache);
    }
    return cache;
  }

  function insertHtml(html){
    const container = document.getElementById('sidebarContainer');
    if(!container) return;
    container.innerHTML = html;
  }

  async function fetchSidebar(){
    try{
      const res = await fetch(SIDEBAR_URL, { credentials: 'same-origin' });
      if(!res.ok) throw new Error('Network response not ok');
      const html = await res.text();
      cachedHtml = html;
      try{ createCacheContainer().innerHTML = html; }catch(e){}
      return html;
    }catch(err){
      console.error('Sidebar load failed:', err);
      return null;
    }
  }

  // Preload sidebar into hidden cache. Safe to call multiple times.
  window.preloadSidebar = async function(){
    if (cachedHtml) return cachedHtml;
    try{
      const cache = document.getElementById('sidebarCache');
      if (cache && cache.innerHTML) {
        cachedHtml = cache.innerHTML;
        return cachedHtml;
      }
    }catch(e){}
    return await fetchSidebar();
  };

  // Inject cached sidebar into the visible container. If nothing cached,
  // trigger a background fetch and inject once it completes.
  window.injectSidebar = async function(){
    const container = document.getElementById('sidebarContainer');
    if(!container) return null;

    const cache = document.getElementById('sidebarCache');
    if (cache && cache.innerHTML) {
      insertHtml(cache.innerHTML);
      return cache.innerHTML;
    }

    if (cachedHtml) {
      insertHtml(cachedHtml);
      return cachedHtml;
    }

    // Last-resort: fetch and inject
    const html = await fetchSidebar();
    if (html) insertHtml(html);
    return html;
  };

  // On initial load: fetch in background, then inject (in case cache already had content).
  document.addEventListener('DOMContentLoaded', async ()=>{
    // Start background preload ASAP
    window.preloadSidebar();
    // Try to inject any cached HTML immediately (no flicker placeholder)
    window.injectSidebar();
  });

})();
