// components/StreamMonitor.js — Monitor en tiempo real del pipeline de agentes.
// Muestra qué agente está activo, un log de eventos y un mini-pipeline de estado.
// Reemplaza el streamPreview genérico en modo agentes.

const StreamMonitor = (() => {
  const MAX_LOG = 30;
  const AGENTS = [
    { name: 'Generador',   key: 'gen' },
    { name: 'Revisor',     key: 'rev' },
    { name: 'Optimizador', key: 'opt' },
  ];

  let _log       = [];
  let _startMs   = null;
  let _timerHnd  = null;

  // ── Public API

  function show() {
    _log = [];
    _startMs = Date.now();
    AGENTS.forEach(a => _setState(a.key, 'idle'));
    const el = document.getElementById('stream-monitor');
    if (el) el.classList.add('visible');
    _renderLog();
    _startTimer();
  }

  function hide() {
    const el = document.getElementById('stream-monitor');
    if (el) el.classList.remove('visible');
    _stopTimer();
  }

  function setAgent(agentName, step, total) {
    const agent = AGENTS.find(a => a.name === agentName);
    if (!agent) return;
    AGENTS.slice(0, AGENTS.indexOf(agent)).forEach(a => _setState(a.key, 'done'));
    _setState(agent.key, 'running');
    const cur = document.getElementById('sm-current');
    if (cur) cur.textContent = `${agentName} · paso ${step}/${total}`;
    _addLog(agentName, _runMsg(agentName), 'info');
  }

  function agentDone(agentName, elapsedS, summary) {
    const agent = AGENTS.find(a => a.name === agentName);
    if (agent) _setState(agent.key, 'done');
    const shortSummary = (summary || 'Completado').slice(0, 90);
    _addLog(agentName, `completado en ${elapsedS}s — ${shortSummary}`, 'done');
  }

  function addCase(tcId, category) {
    _addLog('Generador', `${tcId} generado (${category || 'general'})`, 'case');
  }

  function addDecision(tcId, verdict, reason) {
    const type = verdict === 'APROBADO' ? 'pass' : verdict === 'RECHAZADO' ? 'fail' : 'mod';
    const reasonStr = reason ? ' — ' + reason.slice(0, 55) : '';
    _addLog('Revisor', `${tcId} ${verdict}${reasonStr}`, type);
  }

  function addGap(gap) {
    const text = typeof gap === 'string' ? gap : (gap.reason || JSON.stringify(gap));
    _addLog('Optimizador', `Brecha: ${text.slice(0, 70)}`, 'warn');
  }

  function error(agentName, msg) {
    const agent = AGENTS.find(a => a.name === agentName);
    if (agent) _setState(agent.key, 'error');
    _addLog(agentName || 'Pipeline', 'ERROR: ' + (msg || 'error desconocido'), 'error');
  }

  // ── Internals

  function _addLog(agent, text, type) {
    const time = new Date().toLocaleTimeString('es', { hour12: false });
    _log.push({ time, agent, text, type });
    if (_log.length > MAX_LOG) _log.shift();
    _renderLog();
  }

  function _renderLog() {
    const el = document.getElementById('sm-log');
    if (!el) return;
    el.innerHTML = _log.slice(-10).map(e => `
      <div class="sm-entry sm-entry-${e.type}">
        <span class="sm-time">${e.time}</span>
        <span class="sm-agent">${e.agent}</span>
        <span class="sm-text">${e.text}</span>
      </div>`).join('');
    el.scrollTop = el.scrollHeight;
  }

  function _setState(key, state) {
    const el = document.getElementById('sm-agent-' + key);
    if (el) el.dataset.state = state;
  }

  function _runMsg(name) {
    return ({
      'Generador':   'Generando casos de prueba desde la historia de usuario...',
      'Revisor':     'Analizando calidad y coherencia de los casos...',
      'Optimizador': 'Optimizando cobertura e identificando brechas críticas...',
    })[name] || 'Procesando...';
  }

  function _startTimer() {
    _stopTimer();
    _timerHnd = setInterval(() => {
      const el = document.getElementById('sm-elapsed');
      if (el && _startMs) el.textContent = Math.round((Date.now() - _startMs) / 1000) + 's';
    }, 1000);
  }

  function _stopTimer() {
    if (_timerHnd) { clearInterval(_timerHnd); _timerHnd = null; }
  }

  return { show, hide, setAgent, agentDone, addCase, addDecision, addGap, error };
})();
