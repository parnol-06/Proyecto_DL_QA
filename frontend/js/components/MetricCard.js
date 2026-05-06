// components/MetricCard.js — Dashboard completo de métricas DeepEval.
// Incluye: radar SVG, texto accionable por métrica, umbral visible, pass/warn/fail.

const METRIC_META = {
  coverage: {
    label:       'Test Coverage',
    description: 'Qué tan bien los casos cubren todos los requerimientos de la historia de usuario.',
    threshold:   0.70,
    color:       'var(--green)',
  },
  relevancy: {
    label:       'Relevancy',
    description: 'Cuántos casos son directamente relevantes al requerimiento, sin desvíos fuera de alcance.',
    threshold:   0.70,
    color:       'var(--cyan)',
  },
  consistency: {
    label:       'Consistency',
    description: 'Coherencia interna entre pasos, precondiciones y resultado esperado de cada caso.',
    threshold:   0.65,
    color:       'var(--accent2)',
  },
  specificity: {
    label:       'Step Specificity',
    description: 'Qué tan específicos y accionables son los pasos (vs. genéricos o vagos).',
    threshold:   0.65,
    color:       'var(--amber)',
  },
  nonfunctional_balance: {
    label:       'Non-Functional Balance',
    description: 'Balance entre TCs funcionales y no funcionales (seguridad, rendimiento, usabilidad).',
    threshold:   0.60,
    color:       '#e879a0',
  },
};

const METRIC_ACTIONS = {
  coverage: {
    fail: 'Agrega casos para las funciones no cubiertas de la historia. Considera escenarios negativos y de borde.',
    warn: 'Faltan 1–2 escenarios para alcanzar el umbral. Revisa si hay funciones sin casos negativos.',
  },
  relevancy: {
    fail: 'Algunos casos no están alineados al requerimiento. Usa "Regenerar" en los casos de categorías secundarias.',
    warn: 'Revisa casos de usabilidad/compatibilidad para asegurar que se relacionen con la historia.',
  },
  consistency: {
    fail: 'Pasos y resultados esperados incoherentes. Usa el botón ⟳ en los casos con menor coherencia.',
    warn: 'Revisa precondiciones duplicadas o resultados esperados genéricos.',
  },
  specificity: {
    fail: 'Pasos demasiado genéricos. Sube la temperatura del modelo para obtener más detalle.',
    warn: 'Algunos pasos pueden especificar datos de prueba concretos (ej: email@test.com, contraseña123).',
  },
  nonfunctional_balance: {
    fail: 'Activa las categorías Seguridad, Rendimiento y Usabilidad en el panel izquierdo.',
    warn: 'Agrega contexto técnico en el campo "Contexto adicional" para más casos no funcionales.',
  },
};

// Mapeo métrica → shortkey para las barras del sidebar
const METRIC_KEY_MAP = {
  coverage: 'cov', relevancy: 'rel', consistency: 'con',
  specificity: 'spe', nonfunctional_balance: 'nfb',
};

function MetricCard(metricKey, score, reason = null) {
  const meta = METRIC_META[metricKey];
  if (!meta) return '';

  const pct          = Math.round(score * 100);
  const passed       = score >= meta.threshold;
  const near         = !passed && score >= meta.threshold - 0.10;
  const status       = passed ? 'pass' : near ? 'warn' : 'fail';
  const statusLabel  = { pass: 'PASS', warn: 'WARN', fail: 'FAIL' }[status];
  const thresholdPct = Math.round(meta.threshold * 100);
  const action       = !passed ? METRIC_ACTIONS[metricKey]?.[status] : null;

  // Razón que devuelve DeepEval (solo si no es genérica)
  const showReason = reason && reason !== 'N/A' && !reason.startsWith('Error:') && reason.length > 5;
  const reasonHtml = showReason
    ? `<details class="mc-reason">
         <summary>Ver razón del evaluador</summary>
         <p>${reason.slice(0, 400)}</p>
       </details>`
    : (reason && reason.startsWith('Error:')
        ? `<div class="mc-reason-error">⚠ ${reason.slice(0, 200)}</div>`
        : '');

  return `
    <div class="mc-card mc-${status}" data-metric="${metricKey}" title="${meta.description}">
      <div class="mc-header">
        <span class="mc-label">${meta.label}</span>
        <div class="mc-right">
          <span class="mc-score mc-s-${status}">${score.toFixed(2)}</span>
          <span class="mc-badge mc-b-${status}">${statusLabel}</span>
        </div>
      </div>
      <div class="mc-bar-wrap">
        <div class="mc-track">
          <div class="mc-fill" style="width:${pct}%;background:${meta.color}"></div>
          <div class="mc-thr" style="left:${thresholdPct}%">
            <div class="mc-thr-line" title="Umbral mínimo: ${meta.threshold}"></div>
            <span class="mc-thr-lbl">${meta.threshold}</span>
          </div>
        </div>
        <span class="mc-pct-lbl">${pct}%</span>
      </div>
      <p class="mc-desc">
        <span class="mc-info-icon">ℹ</span>
        ${meta.description}
      </p>
      ${action ? `
      <div class="mc-action mc-action-${status}">
        <span class="mc-action-icon">${status === 'fail' ? '⚠' : '→'}</span>
        <span>${action}</span>
      </div>` : ''}
      ${reasonHtml}
    </div>`;
}

function _renderRadar(metricsObj) {
  const keys   = Object.keys(METRIC_META);
  const scores = keys.map(k => (typeof metricsObj[k] === 'number' ? metricsObj[k] : 0));
  const N = scores.length;
  const cx = 80, cy = 80, R = 58;

  const gridCircles = [0.25, 0.5, 0.75, 1].map(r =>
    `<circle cx="${cx}" cy="${cy}" r="${(R * r).toFixed(1)}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>`
  ).join('');

  const axes = keys.map((_, i) => {
    const a = (i / N) * 2 * Math.PI - Math.PI / 2;
    return `<line x1="${cx}" y1="${cy}" x2="${(cx + R * Math.cos(a)).toFixed(1)}" y2="${(cy + R * Math.sin(a)).toFixed(1)}" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>`;
  }).join('');

  const pts = scores.map((s, i) => {
    const a = (i / N) * 2 * Math.PI - Math.PI / 2;
    const r = R * Math.min(1, Math.max(0, s));
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(' ');

  const shortLabels = { coverage: 'Cov', relevancy: 'Rel', consistency: 'Con', specificity: 'Spe', nonfunctional_balance: 'NFR' };
  const labels = keys.map((k, i) => {
    const a  = (i / N) * 2 * Math.PI - Math.PI / 2;
    const lr = R + 16;
    const x  = (cx + lr * Math.cos(a)).toFixed(1);
    const y  = (cy + lr * Math.sin(a) + 4).toFixed(1);
    return `<text x="${x}" y="${y}" text-anchor="middle" font-size="8" fill="var(--muted)" font-family="var(--font-mono)">${shortLabels[k]}</text>`;
  }).join('');

  return `<svg width="160" height="160" viewBox="0 0 160 160" class="mc-radar">
    ${gridCircles}${axes}
    <polygon points="${pts}" fill="rgba(124,109,250,0.18)" stroke="var(--accent)" stroke-width="1.5" stroke-linejoin="round"/>
    ${labels}
  </svg>`;
}

function _renderCatDistribution(testCases) {
  if (!testCases || !testCases.length) return '';
  const catCount = {};
  testCases.forEach(tc => {
    const c = (tc.category || 'otro').toLowerCase();
    catCount[c] = (catCount[c] || 0) + 1;
  });
  const entries = Object.entries(catCount).sort((a, b) => b[1] - a[1]);
  const maxVal  = Math.max(...entries.map(e => e[1]));
  const total   = testCases.length;

  const CAT_COLORS = {
    happy_path: 'var(--green)', caso_limite: 'var(--amber)', negativo: 'var(--red)',
    seguridad: 'var(--accent2)', rendimiento: 'var(--cyan)', usabilidad: '#a78bfa', compatibilidad: '#6ee7b7',
  };

  return `
    <div class="mc-cat-dist">
      <div class="mc-cat-dist-title">Distribución de categorías <span class="mc-cat-dist-total">${total} casos</span></div>
      ${entries.map(([cat, count]) => {
        const pct   = Math.round((count / maxVal) * 100);
        const share = Math.round((count / total) * 100);
        const color = CAT_COLORS[cat] || 'var(--muted2)';
        return `
          <div class="mc-cat-row">
            <span class="mc-cat-name">${cat.replace(/_/g, ' ')}</span>
            <div class="mc-cat-bar-wrap">
              <div class="mc-cat-bar" style="width:${pct}%;background:${color}"></div>
            </div>
            <span class="mc-cat-count">${count} <span class="mc-cat-pct">(${share}%)</span></span>
          </div>`;
      }).join('')}
    </div>`;
}

function MetricCardPending(metricKey) {
  const meta = METRIC_META[metricKey];
  if (!meta) return '';
  const thresholdPct = Math.round(meta.threshold * 100);
  return `
    <div class="mc-card mc-pending" data-metric="${metricKey}" title="${meta.description}">
      <div class="mc-header">
        <span class="mc-label">${meta.label}</span>
        <div class="mc-right">
          <span class="mc-score" style="color:var(--muted)">—</span>
          <span class="mc-badge mc-b-pending">PENDIENTE</span>
        </div>
      </div>
      <div class="mc-bar-wrap">
        <div class="mc-track">
          <div class="mc-fill" style="width:0%;background:${meta.color};opacity:0.25"></div>
          <div class="mc-thr" style="left:${thresholdPct}%">
            <div class="mc-thr-line"></div>
            <span class="mc-thr-lbl">${meta.threshold}</span>
          </div>
        </div>
        <span class="mc-pct-lbl" style="color:var(--muted)">—</span>
      </div>
      <p class="mc-desc"><span class="mc-info-icon">ℹ</span>${meta.description}</p>
    </div>`;
}

function renderMetricsDashboard(metricsObj, reasonsObj = {}, testCases = null) {
  const contentEl = document.getElementById('metrics-dashboard-content');
  const emptyEl   = document.getElementById('empty-metrics');
  if (!contentEl) return;

  // null = reset total (llamado desde clearAll vía DOM directo, no llega aquí)
  if (!metricsObj) {
    contentEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'flex';
    return;
  }

  if (emptyEl) emptyEl.style.display = 'none';
  contentEl.style.display = 'block';

  const keys      = Object.keys(METRIC_META);
  const evaluated = keys.filter(k => typeof metricsObj[k] === 'number');
  const doneCount = evaluated.length;
  const total     = keys.length;

  // ── Sin métricas aún: mostrar las 5 en estado pendiente ──────────────────
  if (doneCount === 0) {
    contentEl.innerHTML = `
      <div class="mc-pending-header">
        <span class="mc-overall-label">Evaluación DeepEval</span>
        <span class="mc-real-tag">5 métricas · Ollama local</span>
        <p class="mc-pending-hint">
          Haz clic en <strong>Evaluar con DeepEval</strong> para analizar la calidad de la suite generada.
        </p>
      </div>
      <div class="mc-grid">
        ${keys.map(k => MetricCardPending(k)).join('')}
      </div>`;
    return;
  }

  // ── Con métricas (parcial o completo) ─────────────────────────────────────
  const scores     = evaluated.map(k => metricsObj[k]);
  const overall    = scores.reduce((a, b) => a + b, 0) / scores.length;
  const passCount  = evaluated.filter(k => metricsObj[k] >= METRIC_META[k].threshold).length;
  const isComplete = doneCount === total;

  const overallStatus = !isComplete   ? 'pending'
                      : overall >= 0.70 ? 'pass'
                      : overall >= 0.60 ? 'warn' : 'fail';
  const statusLabel   = { pass: 'PASS', warn: 'WARN', fail: 'FAIL', pending: `${doneCount}/${total}` }[overallStatus];
  const qualityText   = !isComplete
    ? `Evaluando… ${doneCount} de ${total} métricas completadas`
    : ({ pass: 'Suite de alta calidad — lista para producción',
         warn: 'Suite aceptable — hay mejoras recomendadas',
         fail: 'Suite necesita revisión antes de usarse' })[overallStatus];

  const radarSvg     = isComplete ? _renderRadar(metricsObj) : '';
  const scoreColor   = isComplete
    ? `mc-s-${overallStatus}`
    : 'style="color:var(--muted)"';
  const badgeClass   = isComplete ? `mc-b-${overallStatus}` : 'mc-b-pending';

  contentEl.innerHTML = `
    <div class="mc-overall">
      <div class="mc-overall-left">
        <span class="mc-overall-label">Evaluación DeepEval</span>
        <span class="mc-real-tag">real · Ollama local</span>
        <p class="mc-quality-text ${isComplete ? `mc-s-${overallStatus}` : ''}" style="${!isComplete ? 'color:var(--muted)' : ''}">${qualityText}</p>
        <div class="mc-pass-rate">
          <span class="mc-pass-pill">${passCount}/${doneCount} métricas PASS</span>
          ${testCases ? `<span class="mc-tc-pill">${testCases.length} test cases</span>` : ''}
        </div>
      </div>
      <div class="mc-overall-right">
        ${radarSvg}
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <span class="mc-overall-score ${isComplete ? scoreColor : ''}" ${!isComplete ? 'style="color:var(--muted)"' : ''}>${overall.toFixed(2)}</span>
          <span class="mc-badge ${badgeClass} mc-overall-badge">${statusLabel}</span>
        </div>
      </div>
    </div>

    ${_renderCatDistribution(testCases)}

    <div class="mc-grid">
      ${keys.map(k => {
        const v = metricsObj[k];
        return typeof v === 'number'
          ? MetricCard(k, v, reasonsObj[k] || null)
          : MetricCardPending(k);
      }).join('')}
    </div>`;

  // Sincronizar barras del sidebar
  evaluated.forEach(k => {
    const score    = metricsObj[k];
    const shortKey = METRIC_KEY_MAP[k];
    if (!shortKey) return;
    const bar     = document.getElementById('bar-' + shortKey);
    const scoreEl = document.getElementById('score-' + shortKey);
    if (bar) bar.style.width = Math.round(score * 100) + '%';
    if (scoreEl) {
      scoreEl.textContent = score.toFixed(2);
      scoreEl.style.color = score >= 0.70 ? 'var(--green)'
                          : score >= 0.55 ? 'var(--amber)' : 'var(--red)';
    }
  });
}
