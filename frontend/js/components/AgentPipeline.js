// components/AgentPipeline.js — Visualización en tiempo real del pipeline CrewAI.
// Mapea eventos SSE (agent_start, agent_done, case) a estados visuales de cada nodo.

const AgentPipeline = (() => {
  const _AGENTS = [
    { name: 'Generator', key: 'generator' },
    { name: 'Reviewer',  key: 'reviewer'  },
    { name: 'Optimizer', key: 'optimizer' },
  ];

  const _startMs = {};
  let   _tickHandle = null;

  // ── DOM helpers
  const _node = key => document.getElementById('ap-node-' + key);
  const _q    = (el, sel) => el && el.querySelector(sel);

  function _setText(node, sel, text) {
    const e = _q(node, sel);
    if (e) e.textContent = text;
  }

  function _show(node, sel, visible) {
    const e = _q(node, sel);
    if (e) e.style.display = visible ? 'block' : 'none';
  }

  function _fill(node, pct) {
    const e = _q(node, '.ap-progress-fill');
    if (e) e.style.width = Math.min(100, pct) + '%';
  }

  function _cfg(agentName) {
    return _AGENTS.find(a => a.name === agentName);
  }

  // ── Public API

  function show() {
    const el = document.getElementById('agentPipeline');
    if (el) el.classList.add('visible');
  }

  function hide() {
    const el = document.getElementById('agentPipeline');
    if (el) el.classList.remove('visible');
  }

  function reset() {
    _AGENTS.forEach(({ key }) => {
      const node = _node(key);
      if (!node) return;
      node.dataset.state = 'idle';
      _setText(node, '.ap-node-message', 'Waiting...');
      _setText(node, '.ap-node-elapsed', '');
      _setText(node, '.ap-node-stats', '');
      _show(node, '.ap-node-progress', false);
      _fill(node, 0);
      const details = _q(node, '.ap-node-details');
      if (details) { details.innerHTML = ''; details.style.display = 'none'; }
      const btn = _q(node, '.ap-expand-btn');
      if (btn) btn.style.display = 'none';
    });
    document.querySelectorAll('.ap-connector-line')
      .forEach(l => l.classList.remove('active'));
    _stopTick();
  }

  function agentStart(agentName, step) {
    const cfg = _cfg(agentName);
    if (!cfg) return;
    const node = _node(cfg.key);
    if (!node) return;

    _startMs[agentName] = Date.now();
    node.dataset.state = 'running';
    _setText(node, '.ap-node-message', _runMsg(agentName));
    _show(node, '.ap-node-progress', true);
    _fill(node, 3);

    // Activar conector del nodo anterior
    if (step > 1) {
      const connectors = document.querySelectorAll('.ap-connector-line');
      const prev = connectors[step - 2];
      if (prev) prev.classList.add('active');
    }

    _startTick();
  }

  function agentProgress(agentName, casesFound) {
    const cfg = _cfg(agentName);
    if (!cfg) return;
    const node = _node(cfg.key);
    if (!node || node.dataset.state !== 'running') return;

    const elapsed = _startMs[agentName]
      ? Math.round((Date.now() - _startMs[agentName]) / 1000) : 0;
    const pct = casesFound > 0
      ? Math.min(88, 10 + casesFound * 6)
      : Math.min(55, elapsed * 1.8);
    _fill(node, pct);

    const casesTxt = casesFound > 0 ? `${casesFound} cases · ` : '';
    _setText(node, '.ap-node-stats', `${casesTxt}${elapsed}s`);
  }

  function agentDone(agentName, step, summary, elapsedS) {
    const cfg = _cfg(agentName);
    if (!cfg) return;
    const node = _node(cfg.key);
    if (!node) return;

    node.dataset.state = 'done';
    _setText(node, '.ap-node-message', summary || 'Completed');
    _setText(node, '.ap-node-elapsed', `${elapsedS}s`);
    _show(node, '.ap-node-progress', true);
    _fill(node, 100);

    // Activar todos los conectores hasta este nodo
    document.querySelectorAll('.ap-connector-line').forEach((l, i) => {
      if (i < step - 1) l.classList.add('active');
    });
  }

  function agentError(agentName, msg) {
    const cfg = _cfg(agentName);
    if (!cfg) return;
    const node = _node(cfg.key);
    if (!node) return;
    node.dataset.state = 'error';
    _setText(node, '.ap-node-message', msg || 'Agent error');
    _stopTick();
  }

  // Muestra decisiones del Revisor en su nodo (APROBADO / RECHAZADO / MODIFICADO)
  function showDecisions(agentName, decisions) {
    if (!decisions || !decisions.length) return;
    const cfg = _cfg(agentName);
    if (!cfg) return;
    const node = _node(cfg.key);
    if (!node) return;

    const detailsEl = _q(node, '.ap-node-details');
    const btn       = _q(node, '.ap-expand-btn');
    if (!detailsEl) return;

    const VCLASS = {
      'APPROVED': 'ap-v-pass',
      'REJECTED': 'ap-v-fail',
      'MODIFIED': 'ap-v-mod',
    };

    detailsEl.innerHTML = decisions.slice(0, 6).map(d => `
      <div class="ap-decision">
        <span class="ap-d-id">${d.tc_id || d.id || ''}</span>
        <span class="ap-d-verdict ${VCLASS[d.verdict] || ''}">${d.verdict || ''}</span>
        ${d.reason ? `<span class="ap-d-reason">${d.reason}</span>` : ''}
      </div>`).join('');

    if (btn) {
      btn.style.display = 'flex';
      btn.onclick = () => {
        const isOpen = detailsEl.style.display !== 'none';
        detailsEl.style.display = isOpen ? 'none' : 'block';
        const lbl = btn.querySelector('.ap-expand-label');
        const arr = btn.querySelector('.ap-expand-arrow');
        if (lbl) lbl.textContent = isOpen ? 'Show decisions' : 'Hide';
        if (arr) arr.textContent = isOpen ? '▾' : '▴';
      };
    }
  }

  // ── Internals

  function _runMsg(name) {
    return ({
      'Generator': 'Generating test cases from the user story...',
      'Reviewer':  'Analysing quality and consistency of the cases...',
      'Optimizer': 'Optimising coverage and identifying critical gaps...',
    })[name] || 'Processing...';
  }

  function _startTick() {
    if (_tickHandle) return;
    _tickHandle = setInterval(() => {
      _AGENTS.forEach(({ name, key }) => {
        const node = _node(key);
        if (!node || node.dataset.state !== 'running') return;
        const elapsed = _startMs[name]
          ? Math.round((Date.now() - _startMs[name]) / 1000) : 0;
        const statsEl = _q(node, '.ap-node-stats');
        if (!statsEl) return;
        const cur = statsEl.textContent;
        // Mantiene el prefix "X casos · " y actualiza solo los segundos
        const match = cur.match(/^(.+·\s*)(\d+)s$/);
        if (match) {
          statsEl.textContent = match[1] + elapsed + 's';
        } else {
          statsEl.textContent = elapsed + 's';
        }
      });
    }, 1000);
  }

  function _stopTick() {
    if (_tickHandle) { clearInterval(_tickHandle); _tickHandle = null; }
  }

  return { show, hide, reset, agentStart, agentProgress, agentDone, agentError, showDecisions };
})();
