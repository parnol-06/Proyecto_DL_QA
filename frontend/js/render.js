function catBadge(cat) {
  const map = {
    happy_path: 'badge-happy', edge_case: 'badge-edge',
    negative: 'badge-negative', security: 'badge-security',
    performance: 'badge-performance', usabilidad: 'badge-usabilidad',
    compatibilidad: 'badge-compatibilidad',
  };
  return map[cat] || 'badge-low';
}

function catLabel(cat) {
  return (cat || '').replace(/_/g, ' ');
}

function renderTC(tcs) {
  const empty = document.getElementById('empty-tc');
  const list  = document.getElementById('tc-list');
  const ctrl = document.getElementById('tc-controls');
  if (!tcs || !tcs.length) {
    empty.style.display = 'flex'; list.style.display = 'none'; if(ctrl) ctrl.style.display='none';
    const fw = document.getElementById('filterWrap');
    if (fw) fw.style.display = 'none';
    return;
  }
  empty.style.display = 'none'; list.style.display = 'flex'; if(ctrl) ctrl.style.display='flex';
  const sw = document.getElementById('tcSearchWrap'); if(sw) sw.style.display='';
  const fw = document.getElementById('filterWrap');
  if (fw) fw.style.display = '';
  document.getElementById('cnt-tc').textContent = tcs.length;

  list.innerHTML = tcs.map((tc, i) => `
    <div class="tc-card" id="tc-${i}" data-category="${tc.category || ''}" data-priority="${tc.priority || ''}" data-tcid="${tc.id || ''}">
      <div class="tc-header" onclick="toggleCard(${i})">
        <span class="tc-id">${tc.id || 'TC-' + String(i+1).padStart(3,'0')}</span>
        <span class="tc-title">${tc.title}</span>
        <div class="tc-badges">
          <span class="badge ${catBadge(tc.category)}">${catLabel(tc.category)}</span>
          <span class="badge badge-${tc.priority}">${tc.priority}</span>
        </div>
        <button class="btn-regen" title="Regenerar este caso" onclick="event.stopPropagation();regenerateTC(${i},'${tc.id || ''}','${tc.category || ''}')">⟳</button>
        <span class="badge-chevron">▾</span>
      </div>
      <div class="tc-body">
        <div class="field-label">Precondiciones</div>
        <ul class="steps-list">
          ${(tc.preconditions||[]).map(p => `<li style="list-style:disc;padding-left:14px;color:var(--muted2);font-size:12.5px">${p}</li>`).join('')}
        </ul>
        <div class="field-label">Pasos</div>
        <ol class="steps-list">${(tc.steps||[]).map(s => `<li>${s}</li>`).join('')}</ol>
        <div class="field-label">Resultado esperado</div>
        <div class="field-value">${tc.expected_result}</div>
        <div class="field-label">Tipo</div>
        <div class="field-value">${tc.test_type || 'functional'}</div>
      </div>
    </div>`).join('');
}

function renderEdge(edges) {
  const empty = document.getElementById('empty-edge');
  const list  = document.getElementById('edge-list');
  if (!edges || !edges.length) { empty.style.display = 'flex'; list.style.display = 'none'; return; }
  empty.style.display = 'none'; list.style.display = 'flex';
  document.getElementById('cnt-edge').textContent = edges.length;

  list.innerHTML = edges.map(e => `
    <div class="edge-card">
      <div class="card-top">
        <span class="card-title">${e.scenario}</span>
        <span class="card-id">${e.id}</span>
      </div>
      <div class="card-desc">${e.description}</div>
      <div class="card-meta">Riesgo: <span class="badge badge-${e.risk_level}" style="padding:1px 7px">${e.risk_level}</span></div>
    </div>`).join('');
}

function renderBugs(bugs) {
  const empty = document.getElementById('empty-bugs');
  const list  = document.getElementById('bug-list');
  if (!bugs || !bugs.length) { empty.style.display = 'flex'; list.style.display = 'none'; return; }
  empty.style.display = 'none'; list.style.display = 'flex';
  document.getElementById('cnt-bugs').textContent = bugs.length;

  list.innerHTML = bugs.map(b => `
    <div class="bug-card">
      <div class="card-top">
        <span class="card-title">${b.title}</span>
        <span class="card-id">${b.id}</span>
      </div>
      <div class="card-desc">${b.description}</div>
      <div class="card-meta" style="margin-top:10px">
        <span style="color:var(--muted)">Área: </span>${b.area} &nbsp;·&nbsp;
        Probabilidad: <span class="badge badge-${b.likelihood}" style="padding:1px 7px">${b.likelihood}</span>
      </div>
      ${b.suggested_test ? `<div style="margin-top:8px;padding:8px 10px;background:rgba(124,109,250,0.06);border:1px solid rgba(124,109,250,0.15);border-radius:7px;font-size:12px;color:var(--muted2)">💡 ${b.suggested_test}</div>` : ''}
    </div>`).join('');
}

function renderCoverage(cov) {
  const empty   = document.getElementById('empty-cov');
  const content = document.getElementById('cov-content');
  if (!cov) { empty.style.display = 'flex'; content.style.display = 'none'; return; }
  empty.style.display = 'none'; content.style.display = 'block';

  const pct  = cov.estimated_coverage_percent || 0;
  const r    = 54;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;

  content.innerHTML = `
    <div class="coverage-grid">
      <div class="cov-stat">
        <div class="cov-stat-num">${cov.total_test_cases}</div>
        <div class="cov-stat-label">Casos de prueba totales</div>
      </div>
      <div class="cov-stat">
        <div class="cov-stat-num">${pct}%</div>
        <div class="cov-stat-label">Cobertura estimada</div>
      </div>
    </div>
    <div class="progress-ring-wrap">
      <svg class="ring" width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r="${r}" fill="none" stroke="var(--surface3)" stroke-width="8"/>
        <circle cx="70" cy="70" r="${r}" fill="none" stroke="var(--accent)" stroke-width="8"
          stroke-dasharray="${dash.toFixed(1)} ${circ.toFixed(1)}"
          stroke-dashoffset="${(circ*0.25).toFixed(1)}"
          stroke-linecap="round" transform="rotate(-90 70 70)"
          style="transition:stroke-dasharray 1s ease"/>
        <text x="70" y="65" text-anchor="middle" font-size="22" font-weight="800" fill="var(--accent2)">${pct}%</text>
        <text x="70" y="83" text-anchor="middle" font-size="11" fill="var(--muted)">coverage</text>
      </svg>
    </div>
    <div class="section-label" style="margin-bottom:10px">Categorías cubiertas</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px">
      ${(cov.categories_covered||[]).map(c => `<span class="badge ${catBadge(c)}">${catLabel(c)}</span>`).join('')}
    </div>
    ${cov.missing_areas && cov.missing_areas.length ? `
    <div class="section-label" style="margin-bottom:10px">Áreas sin cubrir</div>
    <div class="missing-list">
      ${cov.missing_areas.map(a => `<div class="missing-item">${a}</div>`).join('')}
    </div>` : ''}`;
}

function setMetric(key, val, estimated = false) {
  document.getElementById('bar-' + key).style.width = Math.round(val * 100) + '%';
  const scoreEl = document.getElementById('score-' + key);
  scoreEl.textContent = val.toFixed(2) + (estimated ? '*' : '');
  scoreEl.title = estimated ? 'Estimado localmente · usa "Evaluar con DeepEval" para métricas reales' : '';
  scoreEl.style.color = val >= 0.7 ? 'var(--green)' : val >= 0.5 ? 'var(--amber)' : 'var(--red)';
  const noteEl = document.getElementById('metrics-note');
  if (noteEl) noteEl.style.display = estimated ? 'block' : 'none';
}

function expandAll() {
  document.querySelectorAll('.tc-card').forEach(c => c.classList.add('open'));
}
function collapseAll() {
  document.querySelectorAll('.tc-card').forEach(c => c.classList.remove('open'));
}

function showMockMetrics(d) {
  const tc  = (d.test_cases||[]).length;
  const ed  = (d.edge_scenarios||[]).length;
  const bg  = (d.potential_bugs||[]).length;
  const pct = (d.coverage_summary||{}).estimated_coverage_percent || 0;
  setTimeout(() => {
    setMetric('cov', Math.min(0.99, 0.4 + tc*0.04 + pct/200), true);
    setMetric('rel', Math.min(0.99, 0.55 + ed*0.03 + tc*0.02), true);
    setMetric('con', Math.min(0.99, 0.5  + bg*0.04 + tc*0.025), true);
  }, 600);
}

function renderResult(d, skipTC = false) {
  if (!skipTC) renderTC(d.test_cases);
  renderEdge(d.edge_scenarios);
  renderBugs(d.potential_bugs);
  renderCoverage(d.coverage_summary);
  showMockMetrics(d);
  document.getElementById('exportBar').classList.add('visible');
}

function appendTC(tc) {
  const empty = document.getElementById('empty-tc');
  const list  = document.getElementById('tc-list');
  const ctrl  = document.getElementById('tc-controls');
  const sw    = document.getElementById('tcSearchWrap');
  const fw    = document.getElementById('filterWrap');
  if (!list) return;

  if (!list.children.length) {
    if (empty) empty.style.display = 'none';
    list.style.display = 'flex';
    if (ctrl) ctrl.style.display = 'flex';
    if (sw) sw.style.display = '';
    if (fw) fw.style.display = '';
  }

  const i = list.children.length;
  const cntEl = document.getElementById('cnt-tc');
  if (cntEl) cntEl.textContent = i + 1;

  const div = document.createElement('div');
  div.className = 'tc-card tc-card--entering';
  div.id = `tc-${i}`;
  div.dataset.category = tc.category || '';
  div.dataset.priority = tc.priority || '';
  div.dataset.tcid = tc.id || '';
  div.innerHTML = `
    <div class="tc-header" onclick="toggleCard(${i})">
      <span class="tc-id">${tc.id || 'TC-' + String(i + 1).padStart(3, '0')}</span>
      <span class="tc-title">${tc.title}</span>
      <div class="tc-badges">
        <span class="badge ${catBadge(tc.category)}">${catLabel(tc.category)}</span>
        <span class="badge badge-${tc.priority}">${tc.priority}</span>
      </div>
      <button class="btn-regen" title="Regenerar este caso" onclick="event.stopPropagation();regenerateTC(${i},'${tc.id || ''}','${tc.category || ''}')">⟳</button>
      <span class="badge-chevron">▾</span>
    </div>
    <div class="tc-body">
      <div class="field-label">Precondiciones</div>
      <ul class="steps-list">
        ${(tc.preconditions || []).map(p => `<li style="list-style:disc;padding-left:14px;color:var(--muted2);font-size:12.5px">${p}</li>`).join('')}
      </ul>
      <div class="field-label">Pasos</div>
      <ol class="steps-list">${(tc.steps || []).map(s => `<li>${s}</li>`).join('')}</ol>
      <div class="field-label">Resultado esperado</div>
      <div class="field-value">${tc.expected_result}</div>
      <div class="field-label">Tipo</div>
      <div class="field-value">${tc.test_type || 'functional'}</div>
    </div>`;
  list.appendChild(div);
  requestAnimationFrame(() => {
    setTimeout(() => div.classList.remove('tc-card--entering'), 350);
  });
}
