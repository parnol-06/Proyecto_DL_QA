// render.js — Orquestación de render. Depende de TCCard.js y MetricCard.js.
// catBadge/catLabel están definidos en TCCard.js (se carga antes).

function renderTC(tcs) {
  const empty = document.getElementById('empty-tc');
  const list  = document.getElementById('tc-list');
  const ctrl  = document.getElementById('tc-controls');
  const sw    = document.getElementById('tcSearchWrap');
  const fw    = document.getElementById('filterWrap');

  if (!tcs || !tcs.length) {
    if (empty) empty.style.display = 'flex';
    if (list)  list.style.display  = 'none';
    if (ctrl)  ctrl.style.display  = 'none';
    if (sw)    sw.style.display    = 'none';
    if (fw)    fw.style.display    = 'none';
    return;
  }

  if (empty) empty.style.display = 'none';
  if (list)  list.style.display  = 'flex';
  if (ctrl)  ctrl.style.display  = 'flex';
  if (sw)    sw.style.display    = '';
  if (fw)    fw.style.display    = '';

  const cntEl = document.getElementById('cnt-tc');
  if (cntEl) cntEl.textContent = tcs.length;

  list.innerHTML = tcs.map((tc, i) => TCCard(tc, i)).join('');
}

function appendTC(tc) {
  const list = document.getElementById('tc-list');
  if (!list) return;

  // Always make the list visible — showStreamPreview() hides it without clearing children,
  // so the old children.length > 0 guard would leave it hidden on 2nd+ generations.
  list.style.display = 'flex';

  if (!list.children.length) {
    const empty = document.getElementById('empty-tc');
    if (empty) empty.style.display = 'none';
    const ctrl = document.getElementById('tc-controls');
    if (ctrl) ctrl.style.display = 'flex';
    const sw = document.getElementById('tcSearchWrap');
    if (sw) sw.style.display = '';
    const fw = document.getElementById('filterWrap');
    if (fw) fw.style.display = '';
  }

  const i     = list.children.length;
  const cntEl = document.getElementById('cnt-tc');
  if (cntEl) cntEl.textContent = i + 1;

  // Parsear el string completo de TCCard en un elemento real (elimina el doble-div bug)
  const wrap = document.createElement('div');
  wrap.innerHTML = TCCard(tc, i).trim();
  const div = wrap.firstElementChild;
  if (!div) return;
  div.classList.add('tc-card--entering');
  list.appendChild(div);
  requestAnimationFrame(() => setTimeout(() => div.classList.remove('tc-card--entering'), 350));
}

function renderEdge(edges) {
  const empty = document.getElementById('empty-edge');
  const list  = document.getElementById('edge-list');
  if (!edges || !edges.length) {
    if (empty) empty.style.display = 'flex';
    if (list)  list.style.display  = 'none';
    document.getElementById('cnt-edge').textContent = '0';
    return;
  }
  if (empty) empty.style.display = 'none';
  if (list)  list.style.display  = 'flex';
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
  if (!bugs || !bugs.length) {
    if (empty) empty.style.display = 'flex';
    if (list)  list.style.display  = 'none';
    document.getElementById('cnt-bugs').textContent = '0';
    return;
  }
  if (empty) empty.style.display = 'none';
  if (list)  list.style.display  = 'flex';
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
      ${b.suggested_test ? `<div class="bug-hint">💡 ${b.suggested_test}</div>` : ''}
    </div>`).join('');
}

function renderCoverage(cov) {
  const empty   = document.getElementById('empty-cov');
  const content = document.getElementById('cov-content');
  if (!cov) {
    if (empty)   empty.style.display   = 'flex';
    if (content) content.style.display = 'none';
    return;
  }
  if (empty)   empty.style.display   = 'none';
  if (content) content.style.display = 'block';

  const pct      = Math.round(cov.estimated_coverage_percent || 0);
  const r        = 52;
  const circ     = 2 * Math.PI * r;
  const dash     = Math.max(0, Math.min(circ, (pct / 100) * circ));
  const gap      = circ - dash;
  const ringColor = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--accent)' : 'var(--amber)';
  const covered   = cov.categories_covered || [];
  const missing   = cov.missing_areas || [];
  const total     = cov.total_test_cases || 0;

  content.innerHTML = `
    <div class="cov-layout">

      <!-- Donut ring centrado -->
      <div class="cov-ring-wrap">
        <svg class="ring" width="140" height="140" viewBox="0 0 140 140">
          <circle cx="70" cy="70" r="${r}" fill="none" stroke="var(--surface3)" stroke-width="10"/>
          <circle cx="70" cy="70" r="${r}" fill="none" stroke="${ringColor}" stroke-width="10"
            stroke-dasharray="${dash.toFixed(2)} ${gap.toFixed(2)}"
            stroke-linecap="round"
            transform="rotate(-90 70 70)"
            style="transition:stroke-dasharray 0.9s ease"/>
          <text x="70" y="64" text-anchor="middle" font-size="24" font-weight="800" fill="${ringColor}">${pct}%</text>
          <text x="70" y="80" text-anchor="middle" font-size="10" fill="var(--muted)">cobertura</text>
        </svg>
      </div>

      <!-- Stats en columna -->
      <div class="cov-stats-col">
        <div class="cov-stat-mini">
          <span class="cov-stat-mini-num">${total}</span>
          <span class="cov-stat-mini-lbl">Test Cases</span>
        </div>
        <div class="cov-stat-mini">
          <span class="cov-stat-mini-num">${covered.length}</span>
          <span class="cov-stat-mini-lbl">Categorías</span>
        </div>
        <div class="cov-stat-mini">
          <span class="cov-stat-mini-num" style="color:${missing.length ? 'var(--amber)' : 'var(--green)'}">${missing.length}</span>
          <span class="cov-stat-mini-lbl">Sin cubrir</span>
        </div>
      </div>
    </div>

    <!-- Categorías cubiertas -->
    ${covered.length ? `
    <div class="cov-section-label">Categorías cubiertas</div>
    <div class="cov-cats">
      ${covered.map(c => `<span class="badge ${catBadge(c)}">${catLabel(c)}</span>`).join('')}
    </div>` : ''}

    <!-- Áreas faltantes -->
    ${missing.length ? `
    <div class="cov-section-label" style="margin-top:12px">Áreas sin cubrir</div>
    <div class="missing-list">
      ${missing.map(a => `<div class="missing-item">${a}</div>`).join('')}
    </div>` : `<div class="cov-all-good">✓ Todas las áreas cubiertas</div>`}`;
}

// Actualiza los 4 KPIs del header
function updateKPIs(d, overallScore = null) {
  const el = id => document.getElementById(id);
  const tc = el('kpi-tc-val');
  const bg = el('kpi-bugs-val');
  const cv = el('kpi-coverage-val');
  const sc = el('kpi-score-val');

  if (tc) tc.textContent = d?.test_cases?.length ?? '—';
  if (bg) bg.textContent = d?.potential_bugs?.length ?? '—';
  if (cv) cv.textContent = d?.coverage_summary?.estimated_coverage_percent != null
                           ? d.coverage_summary.estimated_coverage_percent + '%' : '—';
  if (sc && overallScore !== null) {
    sc.textContent = overallScore.toFixed(2);
    sc.style.color = overallScore >= 0.70 ? 'var(--green)'
                   : overallScore >= 0.50 ? 'var(--amber)' : 'var(--red)';
  }
}

// Actualiza las barras del sidebar (valores reales, sin estimaciones)
function setMetric(key, val) {
  const bar     = document.getElementById('bar-' + key);
  const scoreEl = document.getElementById('score-' + key);
  if (bar) bar.style.width = Math.round(val * 100) + '%';
  if (scoreEl) {
    scoreEl.textContent = val.toFixed(2);
    scoreEl.style.color = val >= 0.70 ? 'var(--green)'
                        : val >= 0.50 ? 'var(--amber)' : 'var(--red)';
  }
}

function setMetricState(key, state) {
  const dot = document.getElementById('rpdot-' + key);
  if (dot) dot.dataset.state = state;
}

function expandAll() {
  document.querySelectorAll('.tc-card').forEach(c => c.classList.add('open'));
}

function collapseAll() {
  document.querySelectorAll('.tc-card').forEach(c => c.classList.remove('open'));
}

function renderResult(d, skipTC = false) {
  if (!d) return;
  if (!skipTC) renderTC(d.test_cases);
  renderEdge(d.edge_scenarios);
  renderBugs(d.potential_bugs);
  renderCoverage(d.coverage_summary);
  document.getElementById('exportBar').classList.add('visible');
  updateKPIs(d);
  // Pre-poblar las 5 métricas DeepEval en estado pendiente
  renderMetricsDashboard({});
  // setWorkflowStep se llama desde app.js después de invocar renderResult
}
