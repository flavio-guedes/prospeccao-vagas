(() => {
  const DATA_URL = './data/scored_opportunities.json';
  const APPS_URL = './data/applications.json';
  const HISTORY_URL = './data/history.json';
  const SOURCES_URL = './data/sources.json';

  async function loadJSON(url) {
    const res = await fetch(url, {cache: 'no-store'});
    if (!res.ok) throw new Error(url + ' ' + res.status);
    return res.json();
  }

  function esc(str) {
    return (str || '').toString().replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function dotClass(priority) {
    const map = {
      'PRIORIDADE MÁXIMA': 'priority-max',
      'ALTA': 'high',
      'BOA': 'good',
      'SECUNDÁRIA': 'secondary',
      'DESCARTAR': 'discard',
    };
    return map[priority] || 'secondary';
  }

  function priorityLabel(priority) {
    if (!priority) return 'Sem score';
    if (priority === 'PRIORIDADE MÁXIMA') return '🔥 PRIORIDADE MÁXIMA';
    if (priority === 'ALTA') return '🟢 ALTA';
    if (priority === 'BOA') return '🟡 BOA';
    if (priority === 'SECUNDÁRIA') return '⚪ SECUNDÁRIA';
    if (priority === 'DESCARTAR') return '🔴 DESCARTAR';
    return priority;
  }

  function cardHTML(item) {
    const fit = item.fit_score ?? 0;
    const title = esc(item.role || 'Oportunidade');
    const company = esc(item.company);
    const location = esc(item.location);
    const model = esc(item.remote_type);
    const salary = esc(item.salary || 'Não informado');
    const currency = esc(item.currency || '');
    const source = esc(item.source);
    const published = esc(item.published_date || '');
    const url = item.url || '#';
    const status = esc(item.status || 'DISCOVERED');
    const matches = (item.matches || []).map(esc);
    const gaps = (item.gaps || []).map(esc);
    const priority = item.priority || '';

    return `
      <article class="card" data-id="${esc(item.opportunity_id)}" data-source="${esc(item.source)}" data-status="${status}" data-priority="${esc(priority)}">
        <div class="title">${priority ? `<span class="tag"><span class="dot ${dotClass(priority)}"></span>${priorityLabel(priority)}</span> ` : ''}${title}</div>
        <div class="meta">
          <span class="tag">🏢 ${company}</span>
          <span class="tag">📍 ${location}</span>
          <span class="tag">🌍 ${model}</span>
          <span class="tag">💰 ${currency} ${salary}</span>
          <span class="tag">📰 ${published ? new Date(published).toLocaleString('pt-BR') : ''}</span>
          <span class="tag">🔗 ${source}</span>
          <span class="tag">📌 ${status}</span>
          <span class="tag">🎯 FIT ${fit}</span>
        </div>
        <div class="actions">
          <a class="btn" href="${esc(url)}" target="_blank" rel="noopener">OPEN JOB</a>
          <button class="btn action-save">SALVAR</button>
          <button class="btn action-ready">PREPARAR CANDIDATURA</button>
          <button class="btn action-discard">DESCARTAR</button>
        </div>
        ${matches.length ? `<div class="meta">MATCH: ${matches.map(m => `<span class="tag">${m}</span>`).join(' ')}</div>` : ''}
        ${gaps.length ? `<div class="meta">GAPS: ${gaps.map(g => `<span class="tag">${g}</span>`).join(' ')}</div>` : ''}
      </article>
    `;
  }

  function aggregate(items, keyFn, count = 8) {
    const map = new Map();
    for (const item of items) {
      const values = Array.isArray(item[keyFn]) ? item[keyFn] : (item[keyFn] ? [item[keyFn]] : []);
      for (const value of values) {
        const k = String(value || '').trim();
        if (!k) continue;
        map.set(k, (map.get(k) || 0) + 1);
      }
    }
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, count)
      .map(([name, count]) => ({name, count}));
  }

  function renderList(id, data) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = data.map(x => `<li>${esc(x.name)} — ${x.count}</li>`).join('');
  }

  function renderMarketIntel(items) {
    renderList('top-roles', aggregate(items, 'role'));
    renderList('top-skills', aggregate(items, 'skills'));
    renderList('top-sources', aggregate(items, 'source'));
    const remote = items.filter(i => /remote/i.test(i.remote_type || '')).length;
    renderList('remote-breakdown', [{name:'Remote', count:remote},{name:'Não-remoto', count:items.length-remote}]);
  }

  function renderCards(containerId, list) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = list.map(cardHTML).join('');
    bindActions(container);
  }

  function bindActions(root) {
    root.querySelectorAll('.action-save').forEach(btn => btn.addEventListener('click', () => {
      const card = btn.closest('.card');
      if (!card) return;
      btn.textContent = 'SALVO';
      btn.disabled = true;
    }));
    root.querySelectorAll('.action-ready').forEach(btn => btn.addEventListener('click', () => {
      const card = btn.closest('.card');
      if (!card) return;
      btn.textContent = 'READY';
      btn.disabled = true;
    }));
    root.querySelectorAll('.action-discard').forEach(btn => btn.addEventListener('click', () => {
      const card = btn.closest('.card');
      if (!card) return;
      card.style.opacity = '0.45';
      btn.textContent = 'DESCARTADO';
      btn.disabled = true;
    }));
  }

  function applySort(list, sort) {
    return list.slice().sort((a, b) => {
      const fa = a.fit_score || 0;
      const fb = b.fit_score || 0;
      const pa = a.published_date || '';
      const pb = b.published_date || '';
      if (sort === 'fit_desc') return fb - fa;
      if (sort === 'fit_asc') return fa - fb;
      if (sort === 'date_desc') return pb.localeCompare(pa);
      if (sort === 'date_asc') return pa.localeCompare(pb);
      return 0;
    });
  }

  async function init() {
    let items = [];
    let apps = [];
    let history = [];
    let sources = [];
    try {
      items = await loadJSON(DATA_URL);
    } catch (e) {
      document.getElementById('cards-new').innerHTML = '<div class="card">Falha ao carregar dados do dashboard.</div>';
      return;
    }
    try { apps = await loadJSON(APPS_URL); } catch (e) {}
    try { history = await loadJSON(HISTORY_URL); } catch (e) {}
    try { sources = await loadJSON(SOURCES_URL); } catch (e) {}

    const byStatus = new Map();
    for (const app of apps || []) byStatus.set(app.status || 'UNKNOWN', (byStatus.get(app.status || 'UNKNOWN') || 0) + 1);

    document.getElementById('count-new').textContent = String(items.filter(i => i.freshness === 'NOVÍSSIMA').length);
    document.getElementById('count-highfit').textContent = String(items.filter(i => (i.fit_score || 0) >= 80).length);
    document.getElementById('count-remote').textContent = String(items.filter(i => /remote/i.test(i.remote_type || '')).length);
    document.getElementById('count-applied').textContent = String((byStatus.get('APPLIED') || 0) + (byStatus.get('SUBMIT') || 0));
    document.getElementById('count-interviews').textContent = String(byStatus.get('INTERVIEW') || 0);
    document.getElementById('count-offers').textContent = String(byStatus.get('OFFER') || 0);

    document.getElementById('ov-total').textContent = String(items.length);
    document.getElementById('ov-new').textContent = String(items.filter(i => i.freshness === 'NOVÍSSIMA').length);
    document.getElementById('ov-highfit').textContent = String(items.filter(i => (i.fit_score || 0) >= 80).length);
    document.getElementById('ov-remote').textContent = String(items.filter(i => /remote/i.test(i.remote_type || '')).length);
    document.getElementById('ov-applications').textContent = String(apps.length);
    const avgFit = items.length ? Math.round(items.reduce((sum, i) => sum + (i.fit_score || 0), 0) / items.length) : 0;
    document.getElementById('ov-avgfit').textContent = String(avgFit);

    const sourcesArr = Array.from(new Set(items.map(i => i.source || ''))).filter(Boolean);
    const statusesArr = Array.from(new Set(items.map(i => i.status || ''))).filter(Boolean);
    const prioritiesArr = Array.from(new Set(items.map(i => i.priority || ''))).filter(Boolean);
    const fillSelect = (id, values) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = '<option value="">Todos</option>' + values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    };
    fillSelect('filter-source', sourcesArr);
    fillSelect('filter-status', statusesArr);
    fillSelect('filter-priority', prioritiesArr);

    const newItems = items.filter(i => i.freshness === 'NOVÍSSIMA');
    const topFit = applySort(items, 'fit_desc').slice(0, 10);
    const pipeline = apps.length ? apps.slice().reverse() : [];

    renderCards('cards-new', newItems);
    renderCards('cards-topfit', topFit);
    renderCards('cards-pipeline', pipeline);
    renderMarketIntel(items);

    document.getElementById('history').textContent = JSON.stringify(history.slice(0, 50), null, 2);
    document.getElementById('sources').textContent = JSON.stringify(sources, null, 2);

    function applyFilters() {
      const query = document.getElementById('filter-query').value.toLowerCase();
      const source = document.getElementById('filter-source').value;
      const status = document.getElementById('filter-status').value;
      const priority = document.getElementById('filter-priority').value;
      const sort = document.getElementById('sort').value;
      const filtered = items.filter(item => {
        const text = [item.role, item.company, item.location, item.notes, item.url, ...(item.skills || [])].join(' ').toLowerCase();
        if (query && !text.includes(query)) return false;
        if (source && (item.source || '').toLowerCase() !== source.toLowerCase()) return false;
        if (status && (item.status || '').toLowerCase() !== status.toLowerCase()) return false;
        if (priority && (item.priority || '').toLowerCase() !== priority.toLowerCase()) return false;
        return true;
      });
      renderCards('cards-new', filtered.filter(i => i.freshness === 'NOVÍSSIMA'));
      renderCards('cards-topfit', applySort(filtered, 'fit_desc').slice(0, 10));
      renderMarketIntel(filtered);
    }

    document.getElementById('filter-query').addEventListener('input', applyFilters);
    document.getElementById('filter-source').addEventListener('change', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);
    document.getElementById('filter-priority').addEventListener('change', applyFilters);
    document.getElementById('sort').addEventListener('change', applyFilters);
  }

  init().catch(err => console.error(err));
})();
