;(function(){
  const SIDEBAR_KEY = 'sidebar_html_v1';
  const SIDEBAR_URL = '/sidebar/';
  // Strategy: 'cache-first' will use session cache and NOT refetch.
  // 'stale-while-revalidate' will use cache then refresh in background.
  const DEFAULT_STRATEGY = 'cache-first';

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
      insertHtml(html);
      try{ sessionStorage.setItem(SIDEBAR_KEY, html); }catch(e){}
      return html;
    }catch(err){
      console.error('Sidebar load failed:', err);
      insertHtml('<div class="p-3 text-white bg-danger">Sidebar failed to load.</div>');
      return null;
    }
  }

  window.loadSidebar = async function(force=false){
    const container = document.getElementById('sidebarContainer');
    if(!container) return null;
    const strategy = window.SIDEBAR_LOAD_STRATEGY || DEFAULT_STRATEGY;

    if (!force){
      const cached = sessionStorage.getItem(SIDEBAR_KEY);
      if (cached){
        insertHtml(cached);
        if (strategy === 'stale-while-revalidate') {
          // refresh in background but don't block
          fetchSidebar();
        }
        return cached;
      }
    }

    // No cached content or forced fetch
    return await fetchSidebar();
  };

  document.addEventListener('DOMContentLoaded', ()=>{ window.loadSidebar(false); });
})();
