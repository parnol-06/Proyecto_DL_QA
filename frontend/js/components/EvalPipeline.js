// EvalPipeline.js — Visual step-by-step pipeline for DeepEval evaluation.
// States: idle (waiting for button) → running (metric by metric) → done (hides, dashboard appears).

const EVAL_STEPS = [
  { key: 'coverage',              name: 'Test Coverage',          color: 'var(--green)',   threshold: 0.60 },
  { key: 'relevancy',             name: 'Test Relevancy',         color: 'var(--cyan)',    threshold: 0.70 },
  { key: 'consistency',           name: 'Test Consistency',       color: 'var(--accent2)', threshold: 0.65 },
  { key: 'specificity',           name: 'Step Specificity',       color: 'var(--amber)',   threshold: 0.60 },
  { key: 'nonfunctional_balance', name: 'Non-Functional Balance', color: '#e879a0',        threshold: 0.55 },
];

const EvalPipeline = (() => {
  let _state     = 'idle';  // idle | running | done
  let _results   = {};
  let _startTime = null;
  let _clockId   = null;

  const $ = id => document.getElementById(id);

  function _stopClock() {
    if (_clockId) { clearInterval(_clockId); _clockId = null; }
  }

  function _startClock() {
    _stopClock();
    _clockId = setInterval(() => {
      const el = $('ep-clock');
      if (!el || !_startTime) return;
      const s = Math.round((Date.now() - _startTime) / 1000);
      el.textContent = s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
    }, 1000);
  }

  function _nodeHTML(step, idx) {
    if (!step?.key) return '';          // guard against undefined step (should never happen)
    const result        = _results[step.key];
    const completedCount = Object.keys(_results).length;
    const isActive      = _state === 'running' && idx === completedCount;

    let st = 'idle';
    if (result)   st = result.passed ? 'pass' : 'warn';
    else if (isActive) st = 'running';

    const dotInner = { idle: '', running: '·', pass: '✓', warn: '!' }[st];

    // Compute score string before the object literal — JS evaluates ALL values
    // eagerly regardless of which key is selected, so result.score would crash
    // whenever result is undefined (idle / running states).
    const _scoreStr = result?.score != null ? result.score.toFixed(2) : '—';
    const badge = {
      idle:    `<span class="ep-badge ep-b-idle">PENDIENTE</span>`,
      running: `<span class="ep-badge ep-b-running">EVALUANDO</span>`,
      pass:    `<span class="ep-badge ep-b-pass">PASS · ${_scoreStr}</span>`,
      warn:    `<span class="ep-badge ep-b-warn">WARN · ${_scoreStr}</span>`,
    }[st];

    const elapsed = result ? `<span class="ep-elapsed">${result.elapsed_ms}ms</span>` : '';

    const pct    = result?.score != null ? Math.round(result.score * 100) : 0;
    const thrPct = Math.round(step.threshold * 100);

    const hasReason = result?.reason && result.reason !== 'N/A' && !result.reason.startsWith('Error:');
    const reasonHtml = hasReason
      ? `<div class="ep-reason">${result.reason.slice(0, 160)}${result.reason.length > 160 ? '…' : ''}</div>`
      : result?.reason?.startsWith('Error:')
        ? `<div class="ep-reason ep-reason-err">⚠ ${result.reason.slice(0, 120)}</div>`
        : '';

    return `
      <div class="ep-node ep-n-${st}" id="ep-node-${step.key}">
        <div class="ep-node-row">
          <div class="ep-dot ep-d-${st}">${dotInner}</div>
          <span class="ep-step-name">${step.name}</span>
          ${elapsed}
          ${badge}
        </div>
        <div class="ep-bar-row">
          <div class="ep-bar-track">
            <div class="ep-bar-fill" style="width:${pct}%;background:${step.color}"></div>
            <div class="ep-thr" style="left:${thrPct}%" title="Umbral mínimo: ${step.threshold}"></div>
          </div>
          <span class="ep-pct">${result ? pct + '%' : '—'}</span>
        </div>
        ${reasonHtml}
      </div>
      ${idx < EVAL_STEPS.length - 1 ? '<div class="ep-conn"></div>' : ''}`;
  }

  function _render() {
    const el = $('eval-pipeline');
    if (!el) return;

    const done  = Object.keys(_results).length;
    const total = EVAL_STEPS.length;

    const subtitle =
      _state === 'idle'    ? 'Presiona <strong>Evaluar con DeepEval</strong> para analizar la calidad de los casos generados.'
      : _state === 'running' ? `Evaluando… <strong>${done} de ${total}</strong> métricas completadas`
      : '';

    el.innerHTML = `
      <div class="ep-hdr">
        <div class="ep-title-row">
          <span class="ep-title">◈  Pipeline DeepEval</span>
          <span class="ep-tag">5 métricas · Ollama local</span>
          ${_state === 'running' ? '<span class="ep-live-clock" id="ep-clock">0s</span>' : ''}
        </div>
        ${subtitle ? `<p class="ep-subtitle">${subtitle}</p>` : ''}
      </div>
      <div class="ep-steps">
        ${EVAL_STEPS.map((s, i) => _nodeHTML(s, i)).join('')}
      </div>`;
  }

  function _showPipeline() {
    const el = $('eval-pipeline');
    if (el) el.style.display = 'block';
    const empt = $('empty-metrics');
    if (empt) empt.style.display = 'none';
    const dash = $('metrics-dashboard-content');
    if (dash) dash.style.display = 'none';
  }

  function _hidePipeline() {
    const el = $('eval-pipeline');
    if (el) el.style.display = 'none';
  }

  return {
    /** Show waiting state — call after generation completes or on clear. */
    setIdle() {
      _state = 'idle'; _results = {};
      _stopClock();
      _showPipeline();
      _render();
    },

    /** Kick off running state — call when /evaluate/stream starts. */
    setRunning() {
      _state = 'running'; _results = {};
      _startTime = Date.now();
      _startClock();
      _showPipeline();
      _render();
    },

    /** Update a single metric node as its SSE event arrives. */
    updateMetric(metricKey, score, passed, elapsed_ms, reason) {
      _results[metricKey] = { score, passed, elapsed_ms: elapsed_ms || 0, reason: reason || '' };
      _render();
    },

    /** Hide the pipeline — call just before showing the full MetricCard dashboard. */
    setDone() {
      _state = 'done';
      _stopClock();
      _hidePipeline();
    },
  };
})();
